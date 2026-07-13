"""
DR3 OSINT — FastAPI Application
Main API server with WebSocket support for real-time search updates.
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..config import config
from ..core.enums import ConfidenceLevel
from ..core.models import IdentityReport, SearchProgress
from ..intelligence.ai_analyzer import AIAnalyzer
from ..intelligence.confidence import ConfidenceScorer
from ..search.engine import SearchEngine
from ..search.sites_db import SitesDatabase

logger = logging.getLogger("dr3.api")

# ── App Setup ──
app = FastAPI(
    title="DR3 OSINT Intelligence Platform",
    description="AI-Powered Digital Intelligence Platform for OSINT Investigation",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
web_dir = Path(__file__).parent.parent / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir / "static")), name="static")

# ── Global State ──
db: Optional[SitesDatabase] = None
active_searches: Dict[str, IdentityReport] = {}
search_history: list = []

REPORTS_DIR = Path(__file__).parent.parent / "data" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def get_db() -> SitesDatabase:
    """Get or initialize the sites database."""
    global db
    if db is None:
        db = SitesDatabase()
        db.load_from_file(config.sites_db_path)
        logger.info(f"Loaded {db.total_count} sites from database")
    return db


# ── Routes ──

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main SPA page."""
    index_path = web_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse("<h1>DR3 OSINT — Frontend not found</h1>")


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    database = get_db()
    return {
        "status": "ok",
        "version": "2.0.0",
        "sites_loaded": database.total_count,
        "sites_enabled": database.enabled_count,
        "ai_available": bool(config.gemini_api_key),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/stats")
async def stats():
    """Get database statistics."""
    database = get_db()
    stats = database.get_stats()
    return stats


@app.get("/api/tags")
async def get_tags():
    """Get all available tags."""
    database = get_db()
    return {"tags": database.all_tags}


@app.get("/api/search/history")
async def get_search_history():
    """Get recent search history."""
    return {"searches": search_history[-20:]}  # Last 20


@app.get("/api/report/{search_id}")
async def get_report(search_id: str):
    """Get a completed search report."""
    if search_id in active_searches:
        return _serialize_report(active_searches[search_id])
        
    json_path = REPORTS_DIR / f"{search_id}.json"
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    return JSONResponse(
        status_code=404,
        content={"error": "Report not found"},
    )


@app.get("/api/report/{search_id}/export")
async def export_report(search_id: str, format: str = Query("json")):
    """Export report in specified format."""
    if format == "json":
        if search_id in active_searches:
            return _serialize_report(active_searches[search_id])
        json_path = REPORTS_DIR / f"{search_id}.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
    elif format == "html":
        if search_id in active_searches:
            html = generate_html_report(active_searches[search_id])
            return HTMLResponse(content=html)
        html_path = REPORTS_DIR / f"{search_id}.html"
        if html_path.exists():
            with open(html_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
    else:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unsupported format: {format}"},
        )

    return JSONResponse(
        status_code=404,
        content={"error": "Report not found"},
    )


# ── WebSocket Search ──

@app.websocket("/ws/search")
async def websocket_search(websocket: WebSocket):
    """WebSocket endpoint for real-time search with progress updates."""
    await websocket.accept()
    logger.info("WebSocket connection established")

    try:
        while True:
            # Wait for search request
            data = await websocket.receive_text()
            request = json.loads(data)

            username = request.get("username", "").strip()
            if not username:
                await websocket.send_json({"error": "Username is required"})
                continue

            top_sites = int(request.get("top_sites", config.top_sites))
            tags = request.get("tags", [])

            search_id = str(uuid.uuid4())[:8]

            # Progress callback
            async def on_progress(progress: SearchProgress):
                try:
                    await websocket.send_json({
                        "type": "progress",
                        "search_id": progress.search_id,
                        "phase": progress.phase,
                        "progress": progress.progress,
                        "total_sites": progress.total_sites,
                        "checked_sites": progress.checked_sites,
                        "found_count": progress.found_count,
                        "current_site": progress.current_site,
                        "message": progress.message,
                        "is_complete": progress.is_complete,
                    })
                except Exception:
                    pass

            # Send initial acknowledgment
            await websocket.send_json({
                "type": "started",
                "search_id": search_id,
                "username": username,
                "message": f"Starting investigation for '{username}'...",
            })

            # Run search
            database = get_db()
            engine = SearchEngine(
                db=database,
                timeout=config.timeout,
                max_connections=config.max_connections,
                proxy=None,
            )

            try:
                report = await engine.search(
                    username=username,
                    top_sites=top_sites,
                    tags=tags if tags else None,
                    progress_callback=on_progress,
                )

                # Cross-platform scoring
                scorer = ConfidenceScorer()
                report.profiles = scorer.score_cross_platform(
                    report.profiles, username
                )

                # AI analysis
                analyzer = AIAnalyzer(api_key=config.gemini_api_key)
                report = await analyzer.analyze_report(report)

                # Sync search_id: engine generates its own, override
                # so report.search_id matches the key we store it under
                report.search_id = search_id

                # Store report
                active_searches[search_id] = report
                
                # Save to disk for persistence
                try:
                    report_data = _serialize_report(report)
                    with open(REPORTS_DIR / f"{search_id}.json", "w", encoding="utf-8") as f:
                        json.dump(report_data, f, ensure_ascii=False, indent=2)
                        
                    html_content = generate_html_report(report)
                    with open(REPORTS_DIR / f"{search_id}.html", "w", encoding="utf-8") as f:
                        f.write(html_content)
                except Exception as e:
                    logger.error(f"Failed to save report to disk: {e}")

                search_history.append({
                    "search_id": search_id,
                    "username": username,
                    "timestamp": datetime.now().isoformat(),
                    "found": report.total_found,
                    "confirmed": report.total_confirmed,
                })

                # Send complete results
                await websocket.send_json({
                    "type": "complete",
                    "search_id": search_id,
                    "report": _serialize_report(report),
                })

            except Exception as e:
                logger.error(f"Search error: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "search_id": search_id,
                    "error": str(e),
                })
            finally:
                await engine.close()

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


# ── Helpers ──

def _serialize_report(report: IdentityReport) -> dict:
    """Serialize a report to JSON-safe dict."""
    profiles = []
    for p in report.profiles:
        evidence_list = []
        for ev in p.evidence:
            evidence_list.append({
                "type": ev.evidence_type.value,
                "description": ev.description,
                "weight": round(ev.weight, 1),
                "source_site": ev.source_site,
                "target_site": ev.target_site,
            })
        profiles.append({
            "site_name": p.site_name,
            "url": p.url,
            "username": p.username,
            "display_name": p.display_name,
            "bio": p.bio[:500] if p.bio else "",
            "avatar_url": p.avatar_url,
            "location": p.location,
            "tags": p.tags,
            "confidence_score": round(p.confidence_score, 1),
            "confidence_level": p.confidence_level.value,
            "fallback_used": p.fallback_used,
            "evidence": evidence_list,
        })

    return {
        "search_id": report.search_id,
        "target_username": report.target_username,
        "started_at": report.started_at.isoformat() if report.started_at else None,
        "completed_at": report.completed_at.isoformat() if report.completed_at else None,
        "duration_seconds": round(report.duration_seconds, 2),
        "total_sites_checked": report.total_sites_checked,
        "total_found": report.total_found,
        "total_confirmed": report.total_confirmed,
        "total_possible": report.total_possible,
        "overall_confidence": round(report.overall_confidence, 1),
        "overall_confidence_level": report.overall_confidence_level.value,
        "executive_summary": report.executive_summary,
        "profiles": profiles,
        "cross_platform_analysis": report.cross_platform_analysis,
        "ai_analysis": report.ai_analysis,
        "risk_assessment": report.risk_assessment,
        "suggested_next_steps": report.suggested_next_steps,
    }


def generate_html_report(report: IdentityReport) -> str:
    """Generate a standalone HTML report."""
    profiles_html = ""
    for p in report.profiles:
        level_class = {
            "very_high": "confidence-very-high",
            "high": "confidence-high",
            "medium": "confidence-medium",
            "low": "confidence-low",
            "possible": "confidence-possible",
        }.get(p.confidence_level.value, "confidence-possible")

        evidence_html = "".join(
            f"<li>{ev.description} <span class='weight'>+{ev.weight:.0f}</span></li>"
            for ev in p.evidence
        )

        profiles_html += f"""
        <div class="profile-card">
            <div class="profile-header">
                <div class="profile-info">
                    <h3>{p.site_name}</h3>
                    <a href="{p.url}" target="_blank">{p.url}</a>
                    {f'<p class="display-name">{p.display_name}</p>' if p.display_name else ''}
                </div>
                <div class="confidence-badge {level_class}">
                    {p.confidence_score:.0f}%
                </div>
            </div>
            {f'<p class="bio">{p.bio[:200]}</p>' if p.bio else ''}
            <div class="evidence-list">
                <strong>Evidence:</strong>
                <ul>{evidence_html}</ul>
            </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>DR3 OSINT Report — {report.target_username}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #0a0e17; color: #e4e4e7; padding: 2rem; }}
        .report {{ max-width: 1000px; margin: 0 auto; }}
        h1 {{ color: #00d4ff; margin-bottom: 0.5rem; }}
        h2 {{ color: #00d4ff; margin: 2rem 0 1rem; border-bottom: 1px solid #1e293b; padding-bottom: 0.5rem; }}
        .meta {{ color: #9ca3af; margin-bottom: 2rem; }}
        .summary {{ background: #111827; border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; border-left: 4px solid #00d4ff; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .stat-card {{ background: #111827; border-radius: 8px; padding: 1rem; text-align: center; }}
        .stat-value {{ font-size: 2rem; font-weight: bold; color: #00d4ff; }}
        .stat-label {{ color: #9ca3af; font-size: 0.85rem; }}
        .profile-card {{ background: #111827; border-radius: 12px; padding: 1.25rem; margin-bottom: 1rem; }}
        .profile-header {{ display: flex; justify-content: space-between; align-items: flex-start; }}
        .profile-info h3 {{ color: #e4e4e7; }}
        .profile-info a {{ color: #00d4ff; text-decoration: none; font-size: 0.9rem; }}
        .display-name {{ color: #9ca3af; font-size: 0.9rem; margin-top: 0.25rem; }}
        .confidence-badge {{ padding: 0.5rem 1rem; border-radius: 8px; font-weight: bold; font-size: 1.1rem; }}
        .confidence-very-high {{ background: rgba(0,255,136,0.2); color: #00ff88; }}
        .confidence-high {{ background: rgba(0,212,255,0.2); color: #00d4ff; }}
        .confidence-medium {{ background: rgba(255,170,0,0.2); color: #ffaa00; }}
        .confidence-low {{ background: rgba(255,51,102,0.15); color: #ff6b6b; }}
        .confidence-possible {{ background: rgba(156,163,175,0.15); color: #9ca3af; }}
        .bio {{ color: #9ca3af; font-size: 0.9rem; margin: 0.75rem 0; font-style: italic; }}
        .evidence-list {{ font-size: 0.85rem; color: #9ca3af; margin-top: 0.75rem; }}
        .evidence-list ul {{ list-style: none; padding: 0; }}
        .evidence-list li {{ padding: 0.25rem 0; padding-left: 1rem; position: relative; }}
        .evidence-list li::before {{ content: "•"; position: absolute; left: 0; color: #00d4ff; }}
        .weight {{ color: #00ff88; font-size: 0.8rem; }}
        .analysis {{ background: #111827; border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; line-height: 1.6; }}
        .footer {{ text-align: center; color: #4b5563; margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #1e293b; }}
    </style>
</head>
<body>
    <div class="report">
        <h1>🔍 DR3 OSINT Investigation Report</h1>
        <p class="meta">Target: <strong>{report.target_username}</strong> | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Duration: {report.duration_seconds:.1f}s</p>

        <h2>Executive Summary</h2>
        <div class="summary">{report.executive_summary}</div>

        <div class="stats">
            <div class="stat-card"><div class="stat-value">{report.total_sites_checked}</div><div class="stat-label">Sites Checked</div></div>
            <div class="stat-card"><div class="stat-value">{report.total_found}</div><div class="stat-label">Accounts Found</div></div>
            <div class="stat-card"><div class="stat-value">{report.total_confirmed}</div><div class="stat-label">Confirmed</div></div>
            <div class="stat-card"><div class="stat-value">{report.overall_confidence:.0f}%</div><div class="stat-label">Avg. Confidence</div></div>
        </div>

        <h2>Cross-Platform Analysis</h2>
        <div class="analysis">{report.cross_platform_analysis or 'No analysis available.'}</div>

        <h2>Risk Assessment</h2>
        <div class="analysis">{report.risk_assessment or 'No assessment available.'}</div>

        <h2>Intelligence Analysis</h2>
        <div class="analysis">{report.ai_analysis or 'No analysis available.'}</div>

        <h2>Detected Accounts ({report.total_found})</h2>
        {profiles_html}

        <h2>Suggested Next Steps</h2>
        <div class="analysis">
            <ul>{''.join(f'<li style="margin-bottom:0.5rem">{s}</li>' for s in report.suggested_next_steps)}</ul>
        </div>

        <div class="footer">
            <p>Generated by DR3 OSINT Intelligence Platform v2.0.0</p>
        </div>
    </div>
</body>
</html>"""
