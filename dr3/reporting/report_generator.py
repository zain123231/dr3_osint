"""
DR3 Intelligence Platform — Professional Report Generator

Generates comprehensive intelligence dossiers in multiple formats:
- JSON: Machine-readable structured data
- HTML: Print-ready professional dossier with full RTL Arabic support
"""
import json
from datetime import datetime
from typing import Any, Dict, List


class ReportGenerator:
    """Generates professional intelligence dossiers."""

    def generate_json(self, inv: Dict[str, Any], nodes: List[Dict[str, Any]],
                      edges: List[Dict[str, Any]], evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a complete JSON report from dicts."""
        profile = inv.get("identity_profile") or {}
        if isinstance(profile, str):
            try:
                profile = json.loads(profile)
            except Exception:
                profile = {}

        return {
            "metadata": {
                "investigation_id": inv.get("id", ""),
                "target": inv.get("initial_query", ""),
                "generated_at": datetime.now().isoformat(),
                "duration_seconds": round(inv.get("duration_seconds", 0), 1),
                "status": inv.get("status", ""),
                "classification": "UNCLASSIFIED",
                "version": "3.0",
            },
            "executive_summary": inv.get("executive_summary", ""),
            "risk_assessment": {
                "level": profile.get("risk_level", "unknown"),
                "explanation": profile.get("risk_explanation", ""),
            },
            "identity_profile": profile,
            "ai_analysis": inv.get("ai_analysis", ""),
            "cross_platform_analysis": inv.get("cross_platform_analysis", ""),
            "suggested_next_steps": inv.get("suggested_next_steps", []),
            "statistics": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "confirmed_nodes": len([n for n in nodes if n.get("confidence", 0) >= 70]),
                "total_platforms_checked": inv.get("total_platforms_checked", 0),
            },
            "nodes": nodes,
            "edges": edges,
            "evidence": evidence,
        }

    def generate_html(self, inv: Dict[str, Any], nodes: List[Dict[str, Any]],
                      edges: List[Dict[str, Any]], evidence: List[Dict[str, Any]]) -> str:
        """Generate a professional intelligence dossier HTML report."""
        json_data = self.generate_json(inv, nodes, edges, evidence)
        profile = json_data.get("identity_profile") or {}
        stats = json_data["statistics"]

        primary_name = profile.get("primary_name") or inv.get("initial_query", "Unknown")
        risk_level = profile.get("risk_level", "unknown")
        risk_exp = profile.get("risk_explanation", "")
        overall_conf = profile.get("overall_confidence", 0)

        # Classification
        report_id = inv.get("id", "")[:8].upper()
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        date_short = datetime.now().strftime("%Y-%m-%d")

        # Collect identity attributes
        usernames = profile.get("known_usernames", [])
        emails = profile.get("known_emails", [])
        websites = profile.get("known_websites", [])
        locations = profile.get("known_locations", [])
        languages = profile.get("known_languages", [])
        bio = profile.get("bio_summary", "")

        # Sort nodes by confidence
        sorted_nodes = sorted(nodes, key=lambda n: n.get("confidence", 0), reverse=True)
        confirmed_nodes = [n for n in sorted_nodes if n.get("confidence", 0) >= 70 and not n.get("is_seed")]
        probable_nodes = [n for n in sorted_nodes if 40 <= n.get("confidence", 0) < 70 and not n.get("is_seed")]
        speculative_nodes = [n for n in sorted_nodes if n.get("confidence", 0) < 40 and not n.get("is_seed")]

        # Build confirmed platforms table
        confirmed_rows = ""
        for i, n in enumerate(confirmed_nodes, 1):
            conf = n.get("confidence", 0)
            conf_color = "#00ff66" if conf >= 90 else "#00eaff" if conf >= 70 else "#ffb000"
            tags = ", ".join(n.get("tags", [])[:3]) if n.get("tags") else "—"
            url = n.get("profile_url", "")
            confirmed_rows += f"""
            <tr>
                <td>{i}</td>
                <td><strong>{_esc(n.get('platform', ''))}</strong></td>
                <td dir="ltr">@{_esc(n.get('username', ''))}</td>
                <td>{_esc(n.get('display_name', '') or '—')}</td>
                <td style="color:{conf_color}; font-weight:bold;">{conf:.0f}%</td>
                <td class="tags">{_esc(tags)}</td>
                <td><a href="{_esc(url)}" target="_blank" rel="noopener">رابط</a></td>
            </tr>"""

        # Build probable platforms table
        probable_rows = ""
        for i, n in enumerate(probable_nodes, 1):
            conf = n.get("confidence", 0)
            url = n.get("profile_url", "")
            probable_rows += f"""
            <tr>
                <td>{i}</td>
                <td>{_esc(n.get('platform', ''))}</td>
                <td dir="ltr">@{_esc(n.get('username', ''))}</td>
                <td style="color:#ffb000;">{conf:.0f}%</td>
                <td><a href="{_esc(url)}" target="_blank" rel="noopener">رابط</a></td>
            </tr>"""

        # Build evidence table
        evidence_rows = ""
        sorted_evidence = sorted(evidence, key=lambda e: abs(e.get("weight", 0)), reverse=True)
        for i, ev in enumerate(sorted_evidence[:25], 1):
            w = ev.get("weight", 0)
            cat = ev.get("category", "positive")
            quality = ev.get("quality", "moderate")
            weight_color = "#00ff66" if w > 0 else "#ff3b3b"
            cat_ar = {"positive": "إيجابي", "negative": "سلبي", "missing": "مفقود",
                      "conflicting": "متعارض", "circumstantial": "ظرفي"}.get(cat, cat)
            quality_ar = {"definitive": "قاطع", "strong": "قوي", "moderate": "متوسط",
                          "weak": "ضعيف", "unreliable": "غير موثوق"}.get(quality, quality)
            evidence_rows += f"""
            <tr>
                <td>{i}</td>
                <td>{_esc(ev.get('description', ''))}</td>
                <td>{_esc(cat_ar)}</td>
                <td>{_esc(quality_ar)}</td>
                <td style="color:{weight_color}; font-weight:bold;">{w:+.1f}</td>
            </tr>"""

        # Next steps list
        next_steps = inv.get("suggested_next_steps") or []
        next_steps_html = "\n".join(f"<li>{_esc(s)}</li>" for s in next_steps) if next_steps else "<li>لا توجد خطوات مقترحة.</li>"

        # Risk badge class
        risk_class = f"risk-{risk_level}" if risk_level in ("critical", "high", "moderate", "low") else "risk-low"

        html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DR3 — تقرير استخباراتي: {_esc(primary_name)}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Kufi+Arabic:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

        :root {{
            --bg: #050505;
            --bg-section: #0a0e14;
            --bg-card: #0d1117;
            --border: #1a2332;
            --border-accent: #0d3347;
            --text: #c9d1d9;
            --text-muted: #6b7b8d;
            --text-heading: #e6edf3;
            --accent: #00eaff;
            --accent-purple: #b53cff;
            --green: #00ff66;
            --amber: #ffb000;
            --red: #ff3b3b;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Noto Kufi Arabic', 'Segoe UI', sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.8;
            font-size: 14px;
        }}

        /* ── Print Styles ── */
        @media print {{
            body {{ background: #fff; color: #111; font-size: 11pt; }}
            .page-break {{ page-break-before: always; }}
            .no-print {{ display: none !important; }}
            .container {{ max-width: 100%; padding: 0; }}
            .card {{ border: 1px solid #ddd; background: #fff; }}
            h1, h2, h3 {{ color: #111; }}
            a {{ color: #0066cc; }}
            table {{ font-size: 10pt; }}
            .header-bar {{ background: #1a1a2e !important; -webkit-print-color-adjust: exact; }}
        }}

        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 0 1.5rem;
        }}

        /* ── Header ── */
        .header-bar {{
            background: linear-gradient(135deg, #0a0e14 0%, #0d1a2a 100%);
            border-bottom: 2px solid var(--accent);
            padding: 2rem 0;
            margin-bottom: 2rem;
        }}

        .header-inner {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }}

        .header-logo {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--accent);
            letter-spacing: 3px;
        }}

        .header-logo span {{
            color: var(--accent-purple);
        }}

        .header-meta {{
            text-align: left;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: var(--text-muted);
            line-height: 1.8;
        }}

        .classification {{
            display: inline-block;
            padding: 0.2rem 1rem;
            border: 1px solid var(--border);
            border-radius: 3px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            letter-spacing: 3px;
            color: var(--text-muted);
            text-transform: uppercase;
            text-align: center;
            margin-bottom: 1rem;
        }}

        /* ── Headings ── */
        h1 {{
            font-size: 1.4rem;
            color: var(--text-heading);
            font-weight: 700;
            margin: 2rem 0 0.5rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
        }}

        h1 .section-number {{
            color: var(--accent);
            font-family: 'JetBrains Mono', monospace;
            font-weight: 400;
            margin-left: 0.5rem;
        }}

        h2 {{
            font-size: 1.1rem;
            color: var(--accent);
            font-weight: 600;
            margin: 1.5rem 0 0.5rem;
        }}

        h3 {{
            font-size: 0.95rem;
            color: var(--text-heading);
            font-weight: 600;
            margin: 1rem 0 0.3rem;
        }}

        /* ── Cards ── */
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }}

        .card-accent {{
            border-right: 3px solid var(--accent);
        }}

        .card-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
        }}

        /* ── Subject Card ── */
        .subject-card {{
            display: flex;
            gap: 2rem;
            align-items: flex-start;
        }}

        .subject-avatar {{
            width: 80px;
            height: 80px;
            border-radius: 50%;
            border: 3px solid var(--accent);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2.5rem;
            background: var(--bg-section);
            flex-shrink: 0;
        }}

        .subject-avatar img {{
            width: 100%;
            height: 100%;
            border-radius: 50%;
            object-fit: cover;
        }}

        .subject-info {{
            flex: 1;
        }}

        .subject-name {{
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-heading);
            margin-bottom: 0.3rem;
        }}

        .subject-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            margin-top: 0.5rem;
        }}

        .meta-item {{
            font-size: 0.85rem;
            color: var(--text-muted);
        }}

        .meta-item strong {{
            color: var(--text);
        }}

        /* ── Stats Grid ── */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1rem;
            margin: 1.5rem 0;
        }}

        .stat-box {{
            text-align: center;
            padding: 1rem;
            background: var(--bg-section);
            border: 1px solid var(--border);
            border-radius: 6px;
        }}

        .stat-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.5rem;
            font-weight: 700;
        }}

        .stat-label {{
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 0.3rem;
        }}

        /* ── Risk Badge ── */
        .risk-badge {{
            display: inline-block;
            padding: 0.3rem 1.2rem;
            border-radius: 4px;
            font-weight: 700;
            font-size: 0.85rem;
            letter-spacing: 1px;
        }}

        .risk-critical {{ background: rgba(255,59,59,0.15); color: var(--red); border: 1px solid rgba(255,59,59,0.3); }}
        .risk-high {{ background: rgba(255,176,0,0.15); color: var(--amber); border: 1px solid rgba(255,176,0,0.3); }}
        .risk-moderate {{ background: rgba(0,234,255,0.15); color: var(--accent); border: 1px solid rgba(0,234,255,0.3); }}
        .risk-low {{ background: rgba(0,255,102,0.15); color: var(--green); border: 1px solid rgba(0,255,102,0.3); }}

        /* ── Confidence Bar ── */
        .confidence-bar-outer {{
            width: 100%;
            height: 8px;
            background: var(--bg);
            border-radius: 4px;
            overflow: hidden;
            margin: 0.5rem 0;
        }}

        .confidence-bar-inner {{
            height: 100%;
            border-radius: 4px;
            background: linear-gradient(90deg, var(--accent), var(--green));
        }}

        /* ── Tables ── */
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.88rem;
        }}

        thead th {{
            background: var(--bg-section);
            color: var(--accent);
            font-weight: 600;
            padding: 0.7rem 0.5rem;
            text-align: right;
            border-bottom: 2px solid var(--border-accent);
            font-size: 0.8rem;
            letter-spacing: 0.5px;
        }}

        tbody td {{
            padding: 0.6rem 0.5rem;
            border-bottom: 1px solid var(--border);
            vertical-align: middle;
        }}

        tbody tr:hover {{
            background: rgba(0, 234, 255, 0.03);
        }}

        .tags {{
            font-size: 0.78rem;
            color: var(--text-muted);
        }}

        a {{
            color: var(--accent);
            text-decoration: none;
        }}

        a:hover {{
            text-decoration: underline;
        }}

        /* ── Lists ── */
        ul {{
            padding-right: 1.5rem;
            margin: 0.5rem 0;
        }}

        li {{
            margin-bottom: 0.4rem;
        }}

        /* ── Blockquote ── */
        blockquote {{
            border-right: 3px solid var(--accent-purple);
            padding: 0.8rem 1.2rem;
            margin: 1rem 0;
            background: rgba(181, 60, 255, 0.05);
            border-radius: 0 4px 4px 0;
            font-style: italic;
            color: var(--text-muted);
        }}

        /* ── Footer ── */
        .report-footer {{
            text-align: center;
            padding: 2rem 0;
            margin-top: 3rem;
            border-top: 1px solid var(--border);
            font-size: 0.78rem;
            color: var(--text-muted);
        }}

        .report-footer .brand {{
            font-family: 'JetBrains Mono', monospace;
            color: var(--accent);
            font-weight: 600;
        }}

        /* ── Responsive ── */
        @media (max-width: 768px) {{
            .card-grid {{ grid-template-columns: 1fr; }}
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .subject-card {{ flex-direction: column; align-items: center; text-align: center; }}
            .header-inner {{ flex-direction: column; gap: 1rem; }}
        }}
    </style>
</head>
<body>
    <!-- ═══════════════════════════════════════════════ -->
    <!-- HEADER                                        -->
    <!-- ═══════════════════════════════════════════════ -->
    <div class="header-bar">
        <div class="container">
            <div class="classification">UNCLASSIFIED — DR3 INTELLIGENCE REPORT</div>
            <div class="header-inner">
                <div>
                    <div class="header-logo">DR<span>3</span> INTELLIGENCE</div>
                    <div style="color: var(--text-muted); font-size: 0.85rem; margin-top: 0.3rem;">
                        تقرير استخبارات الهوية الرقمية — Digital Identity Intelligence Report
                    </div>
                </div>
                <div class="header-meta">
                    Report ID: {report_id}<br>
                    Date: {date_str}<br>
                    Duration: {json_data['metadata']['duration_seconds']}s<br>
                    Version: 3.0
                </div>
            </div>
        </div>
    </div>

    <div class="container">

        <!-- ═══════════════════════════════════════════ -->
        <!-- SECTION 1: SUBJECT OVERVIEW                -->
        <!-- ═══════════════════════════════════════════ -->
        <h1><span class="section-number">§1</span> ملخص الهدف — Subject Overview</h1>

        <div class="card card-accent">
            <div class="subject-card">
                <div class="subject-avatar">👤</div>
                <div class="subject-info">
                    <div class="subject-name">{_esc(primary_name)}</div>
                    <div style="color: var(--text-muted); font-size: 0.85rem;">
                        الهدف الأولي: <strong dir="ltr" style="color: var(--accent);">{_esc(inv.get('initial_query', ''))}</strong>
                    </div>
                    <div class="subject-meta">
                        {f'<div class="meta-item">📍 <strong>{_esc(locations[0])}</strong></div>' if locations else ''}
                        {f'<div class="meta-item">🌐 <strong>{_esc(", ".join(languages[:3]))}</strong></div>' if languages else ''}
                        {f'<div class="meta-item">📧 <strong dir="ltr">{_esc(emails[0])}</strong></div>' if emails else ''}
                        <div class="meta-item">🔗 <strong>{stats['confirmed_nodes']} حسابات مؤكدة</strong></div>
                    </div>
                </div>
            </div>

            {f'<blockquote>{_esc(bio[:300])}</blockquote>' if bio else ''}

            <div style="margin-top: 1rem;">
                <span class="risk-badge {risk_class}">{risk_level.upper() if risk_level else 'UNKNOWN'}</span>
                <span style="margin-right: 1rem; color: var(--text-muted); font-size: 0.85rem;">{_esc(risk_exp)}</span>
            </div>

            <div style="margin-top: 1rem;">
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem;">
                    <span>الثقة الإجمالية</span>
                    <span style="font-family: 'JetBrains Mono', monospace; color: var(--green);">{overall_conf:.0f}%</span>
                </div>
                <div class="confidence-bar-outer">
                    <div class="confidence-bar-inner" style="width: {overall_conf}%;"></div>
                </div>
            </div>
        </div>

        <!-- Stats Grid -->
        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-value" style="color: var(--accent);">{stats['total_platforms_checked']}</div>
                <div class="stat-label">منصات تم فحصها</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" style="color: var(--green);">{stats['total_nodes']}</div>
                <div class="stat-label">حسابات مكتشفة</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" style="color: var(--green);">{stats['confirmed_nodes']}</div>
                <div class="stat-label">حسابات مؤكدة</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" style="color: var(--amber);">{stats['total_edges']}</div>
                <div class="stat-label">علاقات مكتشفة</div>
            </div>
        </div>

        <!-- Identity Attributes -->
        {self._render_identity_attributes(usernames, emails, websites, locations, languages)}

        <!-- ═══════════════════════════════════════════ -->
        <!-- SECTION 2: EXECUTIVE SUMMARY               -->
        <!-- ═══════════════════════════════════════════ -->
        <h1><span class="section-number">§2</span> الملخص التنفيذي — Executive Summary</h1>
        <div class="card">
            <p style="white-space: pre-wrap; line-height: 2;">{_esc(json_data['executive_summary'] or 'لا يوجد ملخص تنفيذي.')}</p>
        </div>

        <!-- ═══════════════════════════════════════════ -->
        <!-- SECTION 3: ANALYSIS                        -->
        <!-- ═══════════════════════════════════════════ -->
        <h1 class="page-break"><span class="section-number">§3</span> التحليل — Analysis</h1>

        <div class="card-grid">
            <div class="card">
                <h3>🧠 تحليل الذكاء الاصطناعي</h3>
                <p style="white-space: pre-wrap;">{_esc(json_data['ai_analysis'] or 'التحليل غير متوفر — يتطلب تفعيل Gemini API.')}</p>
            </div>
            <div class="card">
                <h3>🔗 التحليل عبر المنصات</h3>
                <p style="white-space: pre-wrap;">{_esc(json_data['cross_platform_analysis'] or 'لا يوجد تحليل عبر المنصات.')}</p>
            </div>
        </div>

        <!-- ═══════════════════════════════════════════ -->
        <!-- SECTION 4: CONFIRMED ACCOUNTS              -->
        <!-- ═══════════════════════════════════════════ -->
        <h1><span class="section-number">§4</span> الحسابات المؤكدة — Confirmed Accounts ({len(confirmed_nodes)})</h1>

        <div class="card" style="overflow-x: auto;">
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>المنصة</th>
                        <th>اسم المستخدم</th>
                        <th>الاسم</th>
                        <th>الثقة</th>
                        <th>العلامات</th>
                        <th>الرابط</th>
                    </tr>
                </thead>
                <tbody>
                    {confirmed_rows if confirmed_rows else '<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">لا توجد حسابات مؤكدة.</td></tr>'}
                </tbody>
            </table>
        </div>

        <!-- ═══════════════════════════════════════════ -->
        <!-- SECTION 5: PROBABLE ACCOUNTS               -->
        <!-- ═══════════════════════════════════════════ -->
        {f'''
        <h1><span class="section-number">§5</span> حسابات محتملة — Probable Matches ({len(probable_nodes)})</h1>
        <div class="card" style="overflow-x: auto;">
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>المنصة</th>
                        <th>اسم المستخدم</th>
                        <th>الثقة</th>
                        <th>الرابط</th>
                    </tr>
                </thead>
                <tbody>
                    {probable_rows if probable_rows else '<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">لا توجد.</td></tr>'}
                </tbody>
            </table>
        </div>
        ''' if probable_nodes else ''}

        <!-- ═══════════════════════════════════════════ -->
        <!-- SECTION 6: EVIDENCE LOG                    -->
        <!-- ═══════════════════════════════════════════ -->
        <h1 class="page-break"><span class="section-number">§6</span> سجل الأدلة — Evidence Log ({len(evidence)})</h1>

        <div class="card" style="overflow-x: auto;">
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>الوصف</th>
                        <th>التصنيف</th>
                        <th>الجودة</th>
                        <th>الوزن</th>
                    </tr>
                </thead>
                <tbody>
                    {evidence_rows if evidence_rows else '<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">لا توجد أدلة مسجلة.</td></tr>'}
                </tbody>
            </table>
        </div>

        <!-- ═══════════════════════════════════════════ -->
        <!-- SECTION 7: NEXT STEPS                      -->
        <!-- ═══════════════════════════════════════════ -->
        <h1><span class="section-number">§7</span> الخطوات التالية — Recommended Actions</h1>
        <div class="card">
            <ul>
                {next_steps_html}
            </ul>
        </div>

        <!-- ═══════════════════════════════════════════ -->
        <!-- FOOTER                                     -->
        <!-- ═══════════════════════════════════════════ -->
        <div class="report-footer">
            <div class="classification" style="margin-bottom: 1rem;">UNCLASSIFIED — END OF REPORT</div>
            <div>
                Generated by <span class="brand">DR3 Intelligence Platform v3.0</span><br>
                Report ID: {report_id} | Date: {date_short} | Pages: Auto<br>
                صُنع للمحللين — Built for Analysts
            </div>
        </div>

    </div>
</body>
</html>"""
        return html

    def _render_identity_attributes(self, usernames, emails, websites, locations, languages):
        """Render identity attributes section if any data exists."""
        if not any([usernames, emails, websites, locations, languages]):
            return ""

        items = []
        if usernames:
            items.append(f"""
                <div class="card" style="padding: 1rem;">
                    <h3 style="font-size: 0.85rem; margin-bottom: 0.5rem;">👤 أسماء المستخدمين ({len(usernames)})</h3>
                    <div dir="ltr" style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; word-break: break-all;">
                        {', '.join(f'<span style="color:var(--accent);">@{_esc(u)}</span>' for u in usernames[:15])}
                    </div>
                </div>""")
        if emails:
            items.append(f"""
                <div class="card" style="padding: 1rem;">
                    <h3 style="font-size: 0.85rem; margin-bottom: 0.5rem;">📧 عناوين البريد ({len(emails)})</h3>
                    <div dir="ltr" style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;">
                        {', '.join(f'<span style="color:var(--green);">{_esc(e)}</span>' for e in emails[:10])}
                    </div>
                </div>""")
        if websites:
            items.append(f"""
                <div class="card" style="padding: 1rem;">
                    <h3 style="font-size: 0.85rem; margin-bottom: 0.5rem;">🌐 مواقع إلكترونية ({len(websites)})</h3>
                    <div dir="ltr" style="font-size: 0.85rem;">
                        {', '.join(f'<a href="{_esc(w)}" target="_blank">{_esc(w)}</a>' for w in websites[:10])}
                    </div>
                </div>""")
        if locations:
            items.append(f"""
                <div class="card" style="padding: 1rem;">
                    <h3 style="font-size: 0.85rem; margin-bottom: 0.5rem;">📍 مواقع جغرافية ({len(locations)})</h3>
                    <div style="font-size: 0.85rem;">{', '.join(_esc(l) for l in locations[:10])}</div>
                </div>""")
        if languages:
            items.append(f"""
                <div class="card" style="padding: 1rem;">
                    <h3 style="font-size: 0.85rem; margin-bottom: 0.5rem;">🗣 لغات ({len(languages)})</h3>
                    <div style="font-size: 0.85rem;">{', '.join(_esc(l) for l in languages[:10])}</div>
                </div>""")

        return f"""
        <h2>📋 سمات الهوية المكتشفة</h2>
        <div class="card-grid">
            {''.join(items)}
        </div>"""


def _esc(val):
    """Escape HTML characters."""
    if not val:
        return ""
    return (str(val)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
