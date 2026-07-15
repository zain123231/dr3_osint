"""
DR3 Intelligence Platform — FastAPI Application

Complete REST API + WebSocket for the intelligence platform.
Redesigned from a single search endpoint to a full investigation API.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..config import Config
from ..core.enums import QueryType
from ..investigation.orchestrator import InvestigationOrchestrator
from ..search.sites_db import SitesDatabase
from ..storage.database import Database

logger = logging.getLogger("dr3.api")

# ── Initialize ──
Config.ensure_dirs()
db = Database(str(Config.DB_PATH))
sites_db = SitesDatabase().load_from_file(str(Config.SITES_FILE))

app = FastAPI(
    title="DR3 Intelligence Platform",
    description="AI-Powered Digital Identity Intelligence Platform",
    version="3.0.0",
)

# ── Static files ──
WEB_DIR = Path(__file__).parent.parent / "web"
app.mount(
    "/static",
    StaticFiles(directory=str(WEB_DIR / "static")),
    name="static",
)

# ── Background Monitor ──
async def watchlist_monitor():
    """Background task to periodically run searches on the watchlist."""
    logger.info("Watchlist Monitor started.")
    while True:
        try:
            items = db.get_watchlist()
            for item in items:
                if item["status"] == "active":
                    logger.info(f"Monitor checking target: {item['query']}")
                    # Placeholder for automated scan trigger
            await asyncio.sleep(60 * 60) # Run every hour
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Watchlist monitor error: {e}")
            await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(watchlist_monitor())


# ═══════════════════════════════════════════════════════════════
# WEB UI
# ═══════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the main web interface."""
    index_path = WEB_DIR / "index.html"
    return FileResponse(str(index_path))


# ═══════════════════════════════════════════════════════════════
# SYSTEM API
# ═══════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health_check():
    """System health and stats."""
    stats = db.get_stats()
    return {
        "status": "operational",
        "version": "3.0.0",
        "platform": "DR3 Intelligence Platform",
        "sites_total": sites_db.total_count,
        "sites_enabled": sites_db.enabled_count,
        "ai_available": Config.ai_available(),
        "database_stats": stats,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/stats")
async def get_stats():
    """Database statistics."""
    return db.get_stats()


# ═══════════════════════════════════════════════════════════════
# INVESTIGATION API
# ═══════════════════════════════════════════════════════════════

@app.get("/api/investigations")
async def list_investigations(limit: int = Query(50, le=200)):
    """List recent investigations."""
    investigations = db.list_investigations(limit=limit)
    return {"investigations": investigations, "total": len(investigations)}


@app.get("/api/investigations/{investigation_id}")
async def get_investigation(investigation_id: str):
    """Get investigation details."""
    inv = db.get_investigation(investigation_id)
    if not inv:
        return JSONResponse(
            status_code=404,
            content={"error": "Investigation not found"},
        )

    nodes = db.get_nodes(investigation_id)
    edges = db.get_edges(investigation_id)
    evidence = db.get_evidence(investigation_id)
    timeline = db.get_timeline(investigation_id)

    return {
        "investigation": inv,
        "nodes": nodes,
        "edges": edges,
        "evidence": evidence,
        "timeline": timeline,
    }


@app.delete("/api/investigations/{investigation_id}")
async def delete_investigation(investigation_id: str):
    """Delete an investigation."""
    db.delete_investigation(investigation_id)
    return {"status": "deleted", "id": investigation_id}


@app.get("/api/investigations/{investigation_id}/graph")
async def get_graph(investigation_id: str):
    """Get graph data for visualization."""
    nodes = db.get_nodes(investigation_id)
    edges = db.get_edges(investigation_id)
    inv = db.get_investigation(investigation_id)

    return {
        "nodes": nodes,
        "edges": edges,
        "seed_node_id": inv.get("seed_node_id") if inv else None,
    }


# ═══════════════════════════════════════════════════════════════
# WATCHLIST API
# ═══════════════════════════════════════════════════════════════

class WatchlistRequest(BaseModel):
    query: str

@app.post("/api/watchlist")
async def add_watchlist(req: WatchlistRequest):
    """Add a query to the continuous monitoring watchlist."""
    db.add_to_watchlist(req.query)
    return {"status": "added", "query": req.query}

@app.get("/api/watchlist")
async def list_watchlist():
    """List all queries in the watchlist."""
    return {"watchlist": db.get_watchlist()}


@app.get("/api/investigations/{investigation_id}/evidence")
async def get_evidence(investigation_id: str):
    """Get all evidence for an investigation."""
    evidence = db.get_evidence(investigation_id)
    return {"evidence": evidence, "total": len(evidence)}


@app.get("/api/investigations/{investigation_id}/timeline")
async def get_timeline(investigation_id: str):
    """Get timeline events."""
    timeline = db.get_timeline(investigation_id)
    return {"timeline": timeline}


@app.get("/api/investigations/{investigation_id}/report/export")
async def export_report(investigation_id: str, format: str = "json"):
    """Export investigation report."""
    inv = db.get_investigation(investigation_id)
    if not inv:
        return JSONResponse(status_code=404, content={"error": "Not found"})

    nodes = db.get_nodes(investigation_id)
    edges = db.get_edges(investigation_id)
    evidence = db.get_evidence(investigation_id)
    
    from ..reporting.report_generator import ReportGenerator
    generator = ReportGenerator()

    if format == "json":
        return generator.generate_json(inv, nodes, edges, evidence)
    elif format == "html":
        html = generator.generate_html(inv, nodes, edges, evidence)
        return HTMLResponse(content=html)

    return JSONResponse(status_code=400, content={"error": "Invalid format"})


# ═══════════════════════════════════════════════════════════════
# WEBSOCKET — LIVE INVESTIGATION
# ═══════════════════════════════════════════════════════════════

@app.websocket("/ws/investigate")
async def websocket_investigation(ws: WebSocket):
    """
    WebSocket endpoint for live investigations.

    Client sends: { "query": "dr3", "query_type": "username", ... }
    Server sends: progress updates and final results
    """
    await ws.accept()

    try:
        # Receive investigation request
        raw = await ws.receive_text()
        request = json.loads(raw)

        query = request.get("query", "").strip()
        query_type_str = request.get("query_type", "username")
        max_depth = request.get("max_depth", Config.DEFAULT_MAX_DEPTH)
        max_nodes = request.get("max_nodes", Config.DEFAULT_MAX_NODES)

        if not query:
            await ws.send_json({"type": "error", "error": "Empty query"})
            return

        query_type = QueryType(query_type_str)

        # Send started
        await ws.send_json({
            "type": "started",
            "query": query,
            "query_type": query_type.value,
        })

        # Create orchestrator
        orchestrator = InvestigationOrchestrator(
            database=db,
            sites_db=sites_db,
            gemini_key=Config.GEMINI_API_KEY,
            github_token=Config.GITHUB_TOKEN,
        )

        # Progress callback
        async def send_progress(data: dict):
            try:
                await ws.send_json({"type": "progress", **data})
            except Exception:
                pass

        # Run investigation
        investigation = await orchestrator.run(
            query=query,
            query_type=query_type,
            max_depth=max_depth,
            max_nodes=max_nodes,
            progress_callback=send_progress,
        )

        # Send complete
        await ws.send_json({
            "type": "complete",
            "investigation": investigation.to_dict(),
        })

    except WebSocketDisconnect:
        logger.info("Client disconnected during investigation")
    except json.JSONDecodeError:
        await ws.send_json({"type": "error", "error": "Invalid JSON"})
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await ws.send_json({"type": "error", "error": str(e)})
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# WEBSOCKET — CASE-BASED INVESTIGATION (Multi-Evidence)
# ═══════════════════════════════════════════════════════════════

@app.websocket("/ws/investigate-case")
async def websocket_case_investigation(ws: WebSocket):
    """
    WebSocket endpoint for multi-evidence case investigations.

    Client sends:
    {
        "case_name": "Target Alpha",
        "evidence": {
            "usernames": ["dr3", "dr3sec"],
            "emails": ["user@example.com"],
            "phone_numbers": ["+964..."],
            "websites": ["https://example.com"],
            "locations": ["Iraq"],
            "known_accounts": {"github": "dr3"},
            "notes": "Known researcher"
        }
    }
    """
    await ws.accept()

    try:
        raw = await ws.receive_text()
        request = json.loads(raw)

        case_name = request.get("case_name", "Unnamed Case").strip()
        evidence = request.get("evidence", {})

        if not evidence:
            await ws.send_json({"type": "error", "error": "No evidence provided"})
            return

        # Send started
        await ws.send_json({
            "type": "started",
            "query": case_name,
            "query_type": "case",
            "case_mode": True,
        })

        orchestrator = InvestigationOrchestrator(
            database=db,
            sites_db=sites_db,
            gemini_key=Config.GEMINI_API_KEY,
            github_token=Config.GITHUB_TOKEN,
        )

        async def send_progress(data: dict):
            try:
                await ws.send_json({"type": "progress", **data})
            except Exception:
                pass

        investigation = await orchestrator.run_case(
            case_name=case_name,
            evidence=evidence,
            max_depth=request.get("max_depth", Config.DEFAULT_MAX_DEPTH),
            max_nodes=request.get("max_nodes", Config.DEFAULT_MAX_NODES),
            progress_callback=send_progress,
        )

        await ws.send_json({
            "type": "complete",
            "investigation": investigation.to_dict(),
        })

    except WebSocketDisconnect:
        logger.info("Client disconnected during case investigation")
    except json.JSONDecodeError:
        await ws.send_json({"type": "error", "error": "Invalid JSON"})
    except ValueError as e:
        try:
            await ws.send_json({"type": "error", "error": str(e)})
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Case WebSocket error: {e}", exc_info=True)
        try:
            await ws.send_json({"type": "error", "error": str(e)})
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY — Old WebSocket endpoint
# ═══════════════════════════════════════════════════════════════

@app.websocket("/ws/search")
async def websocket_search_compat(ws: WebSocket):
    """
    Backward-compatible WebSocket endpoint.
    Maps old {username, top_sites, tags} to new investigation API.
    """
    await ws.accept()

    try:
        raw = await ws.receive_text()
        request = json.loads(raw)

        username = request.get("username", "").strip()
        if not username:
            await ws.send_json({"type": "error", "error": "No username"})
            return

        await ws.send_json({
            "type": "started",
            "username": username,
        })

        orchestrator = InvestigationOrchestrator(
            database=db,
            sites_db=sites_db,
            gemini_key=Config.GEMINI_API_KEY,
            github_token=Config.GITHUB_TOKEN,
        )

        async def send_progress(data: dict):
            try:
                # Map new progress to old format
                progress = data.get("progress", 0)
                message = data.get("message", "")
                nodes = data.get("discovered_nodes", 0)

                await ws.send_json({
                    "type": "progress",
                    "progress": progress,
                    "message": message,
                    "checked_sites": data.get("checked_platforms", 0),
                    "total_sites": data.get("total_platforms", 0),
                    "found_count": nodes,
                })
            except Exception:
                pass

        investigation = await orchestrator.run(
            query=username,
            query_type=QueryType.USERNAME,
            progress_callback=send_progress,
        )

        # Map to old report format for backward compat
        report = _investigation_to_legacy_report(investigation)
        await ws.send_json({"type": "complete", "report": report})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "error": str(e)})
        except Exception:
            pass


def _investigation_to_legacy_report(investigation) -> dict:
    """Map Investigation to old report format for backward compatibility."""
    nodes = list(investigation.nodes.values())
    profile = investigation.identity_profile

    # Build legacy profiles list
    profiles = []
    for node in sorted(nodes, key=lambda n: n.confidence, reverse=True):
        if node.is_seed:
            continue
        evidence_list = []
        edges = investigation.get_node_edges(node.id)
        for edge in edges:
            for ev in edge.evidence_chain.evidence:
                evidence_list.append({
                    "description": ev.description,
                    "weight": ev.weight,
                })

        profiles.append({
            "site_name": node.platform,
            "url": node.profile_url,
            "confidence_score": node.confidence,
            "confidence_level": node.confidence_level.value,
            "display_name": node.display_name,
            "bio": node.bio,
            "avatar_url": node.avatar_url,
            "tags": node.tags,
            "evidence": evidence_list,
            "fallback_used": node.collection_method.value == "search_engine",
        })

    return {
        "search_id": investigation.id,
        "target_username": investigation.initial_query,
        "total_sites_checked": investigation.total_platforms_checked,
        "total_found": investigation.node_count - 1,  # minus seed
        "total_confirmed": len(investigation.confirmed_nodes),
        "overall_confidence": profile.overall_confidence if profile else 0,
        "executive_summary": investigation.executive_summary,
        "cross_platform_analysis": investigation.cross_platform_analysis,
        "risk_assessment": investigation.risk_assessment,
        "ai_analysis": investigation.ai_analysis,
        "suggested_next_steps": investigation.suggested_next_steps,
        "duration_seconds": round(investigation.duration_seconds, 1),
        "profiles": profiles,
        # New fields
        "identity_profile": profile.to_dict() if profile else None,
        "graph": investigation.to_graph_dict(),
    }
