"""
DR3 Intelligence Platform — Investigation Orchestrator

The master controller that coordinates the entire investigation pipeline.

This is the equivalent of the old SearchEngine, but redesigned as
an intelligence investigation orchestrator. It manages the full
lifecycle through 8 phases:

  1. Seed Resolution      → Find first trusted identity
  2. Evidence Extraction   → Extract identity attributes
  3. Identity Expansion    → Discover related accounts
  4. Correlation          → Link identities with evidence
  5. Verification         → Eliminate false positives
  6. AI Analysis          → Generate insights and hypotheses
  7. Profile Building     → Construct digital identity profile
  8. Report Generation    → Produce intelligence report

Design: Event-driven with progress callbacks for real-time UI updates.
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from ..core.enums import (
    ConfidenceLevel,
    InvestigationPhase,
    InvestigationStatus,
    QueryType,
    RiskLevel,
)
from ..core.models import (
    DigitalIdentityProfile,
    Investigation,
    InvestigationProgress,
)
from ..intelligence.confidence_engine import ConfidenceEngine
from ..intelligence.evidence_engine import EvidenceEngine
from ..investigation.identity_expander import IdentityExpander
from ..investigation.seed_resolver import SeedResolver
from ..search.sites_db import SitesDatabase
from ..storage.database import Database
from ..search.dorking import DorkingEngine
from ..investigation.reverse_image import ReverseImageEngine
from ..collectors.api_collectors.breach_collector import BreachCollector
from ..collectors.api_collectors.archive_collector import ArchiveCollector

logger = logging.getLogger("dr3.orchestrator")


class InvestigationOrchestrator:
    """
    Master coordinator for the investigation pipeline.

    Usage:
        orchestrator = InvestigationOrchestrator(db, sites_db, config)
        investigation = await orchestrator.run(
            query="dr3",
            query_type=QueryType.USERNAME,
            progress_callback=ws_send,
        )
    """

    def __init__(
        self,
        database: Database,
        sites_db: SitesDatabase,
        gemini_key: str = "",
        github_token: str = "",
    ):
        self.db = database
        self.sites_db = sites_db
        self.gemini_key = gemini_key
        self.github_token = github_token

        # Engines
        self.evidence_engine = EvidenceEngine()
        self.confidence_engine = ConfidenceEngine()

    async def run(
        self,
        query: str,
        query_type: QueryType = QueryType.USERNAME,
        max_depth: int = 3,
        max_nodes: int = 50,
        progress_callback: Optional[Callable] = None,
    ) -> Investigation:
        """
        Run a complete investigation from start to finish.

        Args:
            query: The search target (username, email, URL, etc.)
            query_type: Type of the query
            max_depth: Maximum expansion depth
            max_nodes: Maximum graph nodes
            progress_callback: Async function for progress updates

        Returns:
            Completed Investigation object with full graph, profile, report
        """
        # Create investigation
        investigation = Investigation(
            initial_query=query,
            query_type=query_type,
            max_expansion_depth=max_depth,
            max_nodes=max_nodes,
        )
        investigation.status = InvestigationStatus.RUNNING

        async def emit(phase: str, progress: float, message: str, **kwargs):
            """Emit progress update."""
            if progress_callback:
                update = InvestigationProgress(
                    investigation_id=investigation.id,
                    phase=phase,
                    progress=progress,
                    message=message,
                    discovered_nodes=investigation.node_count,
                    discovered_edges=investigation.edge_count,
                    **kwargs,
                )
                await progress_callback(update.to_dict())

        try:
            # ═══════════════════════════════════════════════════
            # PHASE 1: SEED RESOLUTION
            # ═══════════════════════════════════════════════════
            queries = [q.strip() for q in query.split(",") if q.strip()]
            
            investigation.current_phase = InvestigationPhase.SEED_RESOLUTION
            await emit("seed_resolution", 5, f"بدء التحقيق للبحث عن: {', '.join(queries)}...")

            seed_resolver = SeedResolver(
                self.sites_db,
                github_token=self.github_token,
            )

            all_seed_nodes = []
            investigation.total_platforms_checked = 0

            for q in queries:
                async def seed_progress(msg):
                    await emit("seed_resolution", 10, f"[{q}] {msg}")

                seed_node, seed_results = await seed_resolver.resolve(
                    q, progress_callback=seed_progress
                )

                if not seed_node:
                    await emit("seed_resolution", 15, f"[{q}] لم يُعثر على هوية أولية — بحث موسع...")
                    from ..core.enums import EntityType
                    from ..core.models import IdentityNode
                    seed_node = IdentityNode(
                        entity_type=EntityType.ACCOUNT,
                        platform="Unknown",
                        username=q,
                        is_seed=True,
                        depth=0,
                    )

                investigation.add_node(seed_node)
                all_seed_nodes.append(seed_node)
                investigation.total_platforms_checked += len(seed_results)
                
                # Add cross-referencing tag to seeds if multiple queries
                if len(queries) > 1:
                    seed_node.tags.append("Target: " + q)

            if all_seed_nodes:
                investigation.seed_node_id = all_seed_nodes[0].id

            await emit(
                "seed_resolution", 20,
                f"تم تحديد {len(all_seed_nodes)} حسابات أساسية للتحقيق.",
                new_nodes=[n.to_dict() for n in all_seed_nodes],
            )

            await seed_resolver.close()

            # ═══════════════════════════════════════════════════
            # PHASE 2-3: IDENTITY EXPANSION
            # ═══════════════════════════════════════════════════
            investigation.current_phase = InvestigationPhase.IDENTITY_EXPANSION
            await emit("identity_expansion", 25, "بدء توسيع التحقيق...")

            expander = IdentityExpander(self.sites_db)

            async def expansion_progress(msg):
                # Map expansion progress to 25-65% range
                progress_val = 25 + (investigation.node_count / max_nodes) * 40
                await emit(
                    "identity_expansion",
                    min(progress_val, 65),
                    msg,
                )

            investigation = await expander.expand(
                investigation,
                progress_callback=expansion_progress,
                pre_discovered_results=seed_results,
            )

            await emit(
                "identity_expansion", 65,
                f"تم اكتشاف {investigation.node_count} حساب و {investigation.edge_count} علاقة",
            )

            # ═══════════════════════════════════════════════════
            # PHASE 3.5: ADVANCED OSINT SOURCES
            # ═══════════════════════════════════════════════════
            investigation.current_phase = InvestigationPhase.CORRELATION
            await emit("correlation", 68, "جلب مصادر استخباراتية متقدمة (Breach, Leaks, Archive)...")
            
            from ..core.enums import EntityType, CheckStatus, RelationType
            from ..core.models import IdentityNode, IdentityEdge
            
            for q in queries:
                # Breach Check
                breach_col = BreachCollector()
                b_res = await breach_col.collect(q)
                if b_res.status == CheckStatus.FOUND:
                    b_node = IdentityNode(
                        entity_type=EntityType.ACCOUNT,
                        platform=b_res.platform,
                        username=q,
                        profile_url=b_res.profile_url,
                        extra_data=b_res.extra_data,
                        confidence=60.0,
                        depth=1
                    )
                    investigation.add_node(b_node)
                    investigation.add_edge(IdentityEdge(source_id=investigation.seed_node_id, target_id=b_node.id, relationship_type=RelationType.ASSOCIATED, strength=60.0, explanation="has_breach_data"))
                
                # Leak Check
                dork_eng = DorkingEngine()
                leaks = await dork_eng.search_leaks(q)
                for leak in leaks:
                    l_node = IdentityNode(
                        entity_type=EntityType.ACCOUNT,
                        platform="Leak/Document",
                        username=leak["title"][:50],
                        profile_url=leak["url"],
                        confidence=40.0,
                        depth=1
                    )
                    investigation.add_node(l_node)
                    investigation.add_edge(IdentityEdge(source_id=investigation.seed_node_id, target_id=l_node.id, relationship_type=RelationType.ASSOCIATED, strength=40.0, explanation="found_in_leak"))

                # Dark Web Check
                dark_leaks = await dork_eng.search_darkweb(q)
                for dark in dark_leaks:
                    d_node = IdentityNode(
                        entity_type=EntityType.ACCOUNT,
                        platform="Dark Web",
                        username=dark["title"][:50],
                        profile_url=dark["url"],
                        confidence=30.0,
                        depth=1
                    )
                    investigation.add_node(d_node)
                    investigation.add_edge(IdentityEdge(source_id=investigation.seed_node_id, target_id=d_node.id, relationship_type=RelationType.ASSOCIATED, strength=30.0, explanation="dark_web_mention"))

            # Archive Check (Top 2 nodes)
            arch_col = ArchiveCollector()
            arch_targets = [n for n in investigation.nodes.values() if n.profile_url and n.platform not in ["LeakCheck / Breach Data", "Leak/Document"]][:2]
            for targ in arch_targets:
                a_res = await arch_col.collect(targ.profile_url)
                if a_res.status == CheckStatus.FOUND:
                    a_node = IdentityNode(
                        entity_type=EntityType.ACCOUNT,
                        platform=a_res.platform,
                        username=f"Archive: {targ.platform}",
                        profile_url=a_res.profile_url,
                        extra_data=a_res.extra_data,
                        confidence=50.0,
                        depth=targ.depth + 1
                    )
                    investigation.add_node(a_node)
                    investigation.add_edge(IdentityEdge(source_id=targ.id, target_id=a_node.id, relationship_type=RelationType.ASSOCIATED, strength=50.0, explanation="has_archive"))
                    
            # Reverse Image Search
            rev_eng = ReverseImageEngine()
            for n in list(investigation.nodes.values()):
                if n.avatar_url:
                    links = rev_eng.get_reverse_search_links(n.avatar_url)
                    if links:
                        if not n.extra_data:
                            n.extra_data = {}
                        n.extra_data["reverse_image"] = links

            # ═══════════════════════════════════════════════════
            # PHASE 4: CORRELATION
            # ═══════════════════════════════════════════════════
            await emit("correlation", 70, "ربط الهويات وتقييم العلاقات...")

            # Re-score all nodes with full graph context
            for node in investigation.nodes.values():
                if node.is_seed:
                    node.confidence = 100.0
                    node.confidence_level = ConfidenceLevel.CONFIRMED
                    continue

                edges = investigation.get_node_edges(node.id)
                if edges:
                    best_edge = max(edges, key=lambda e: e.strength)
                    self.confidence_engine.score_node(
                        node, best_edge.evidence_chain
                    )

            # ═══════════════════════════════════════════════════
            # PHASE 5: VERIFICATION & SNA
            # ═══════════════════════════════════════════════════
            investigation.current_phase = InvestigationPhase.VERIFICATION
            await emit("verification", 75, "التحقق من النتائج وحساب درجة المركزية (SNA)...")

            # Verification: remove nodes with zero meaningful evidence
            nodes_to_keep = {}
            for nid, node in investigation.nodes.items():
                edges = investigation.get_node_edges(nid)
                degree = len(edges)
                
                if not node.extra_data:
                    node.extra_data = {}
                node.extra_data["centrality"] = degree
                
                # Tag Central Nodes vs Burner
                if degree >= 3 and node.confidence >= 60:
                    node.tags.append("Main Hub 🌟")
                elif degree == 1 and node.confidence < 40 and not node.is_seed:
                    node.tags.append("Burner / Isolate 👻")

                if node.is_seed or node.confidence > 5:
                    nodes_to_keep[nid] = node
                else:
                    logger.debug(f"Removing zero-confidence node: {node.label}")

            investigation.nodes = nodes_to_keep

            # Clean orphan edges
            valid_node_ids = set(investigation.nodes.keys())
            edges_to_keep = {}
            for eid, edge in investigation.edges.items():
                if edge.source_id in valid_node_ids and edge.target_id in valid_node_ids:
                    edges_to_keep[eid] = edge
            investigation.edges = edges_to_keep

            # ═══════════════════════════════════════════════════
            # PHASE 6: AI ANALYSIS
            # ═══════════════════════════════════════════════════
            investigation.current_phase = InvestigationPhase.AI_ANALYSIS
            await emit("ai_analysis", 80, "تحليل ذكي للنتائج...")

            analysis = await self._run_ai_analysis(investigation)
            investigation.ai_analysis = analysis.get("ai_analysis", "")
            investigation.cross_platform_analysis = analysis.get("cross_platform", "")
            investigation.risk_assessment = analysis.get("risk_assessment", "")
            investigation.suggested_next_steps = analysis.get("next_steps", [])

            # ═══════════════════════════════════════════════════
            # PHASE 7: PROFILE BUILDING
            # ═══════════════════════════════════════════════════
            investigation.current_phase = InvestigationPhase.PROFILE_BUILDING
            await emit("profile_building", 90, "بناء ملف الهوية الرقمية...")

            profile = self._build_identity_profile(investigation)
            investigation.identity_profile = profile

            # Score overall investigation
            self.confidence_engine.score_investigation(investigation)

            # ═══════════════════════════════════════════════════
            # PHASE 8: COMPLETE
            # ═══════════════════════════════════════════════════
            investigation.current_phase = InvestigationPhase.REPORT_GENERATION
            investigation.status = InvestigationStatus.COMPLETED
            investigation.completed_at = datetime.now()

            # Save to database
            self._save_investigation(investigation)

            await emit(
                "complete", 100,
                investigation.executive_summary,
                is_complete=True,
            )

            logger.info(
                f"Investigation complete: {investigation.id} — "
                f"{investigation.node_count} nodes, "
                f"{investigation.edge_count} edges, "
                f"{investigation.duration_seconds:.1f}s"
            )

            return investigation

        except Exception as e:
            logger.error(f"Investigation failed: {e}", exc_info=True)
            investigation.status = InvestigationStatus.FAILED
            await emit("error", 0, f"فشل التحقيق: {str(e)}")
            raise

    async def run_case(
        self,
        case_name: str,
        evidence: Dict[str, Any],
        max_depth: int = 3,
        max_nodes: int = 80,
        progress_callback: Optional[Callable] = None,
    ) -> Investigation:
        """
        Run a multi-evidence case investigation.

        This is the core of DR3's intelligence capability. Instead of
        searching for a single username, the investigator provides
        multiple evidence types which are cross-correlated.

        Args:
            case_name: Human-readable name for this case
            evidence: Dict containing evidence fields:
                - usernames: List[str] — Known usernames
                - emails: List[str] — Known email addresses
                - phone_numbers: List[str] — Known phone numbers
                - websites: List[str] — Known websites/URLs
                - locations: List[str] — Known locations
                - known_accounts: Dict[str, str] — Platform→username map
                - notes: str — Free-text investigator notes
            max_depth: Maximum expansion depth
            max_nodes: Maximum graph nodes
            progress_callback: Async function for progress updates

        Returns:
            Merged Investigation with cross-evidence correlation
        """
        from ..core.enums import EntityType, RelationType
        from ..core.models import IdentityNode, IdentityEdge
        from ..core.evidence import Evidence, EvidenceChain
        from ..core.enums import (
            EvidenceType, EvidenceCategory, EvidenceQuality,
        )

        # ── Gather all query targets ──
        usernames = [u.strip() for u in evidence.get("usernames", []) if u.strip()]
        emails = [e.strip() for e in evidence.get("emails", []) if e.strip()]
        phones = [p.strip() for p in evidence.get("phone_numbers", []) if p.strip()]
        websites = [w.strip() for w in evidence.get("websites", []) if w.strip()]
        locations = [l.strip() for l in evidence.get("locations", []) if l.strip()]
        known_accounts = evidence.get("known_accounts", {})
        notes = evidence.get("notes", "")

        # Build query list — usernames first, then email prefixes
        queries = list(usernames)
        for email in emails:
            prefix = email.split("@")[0] if "@" in email else email
            if prefix not in queries:
                queries.append(prefix)
        for platform, username in known_accounts.items():
            if username not in queries:
                queries.append(username)

        if not queries:
            raise ValueError("No searchable evidence provided")

        # ── Create master investigation ──
        primary_query = queries[0] if queries else case_name
        master_query = ", ".join(queries[:5])

        async def emit(phase, progress, message, **kwargs):
            if progress_callback:
                update = InvestigationProgress(
                    investigation_id="case",
                    phase=phase,
                    progress=progress,
                    message=message,
                    discovered_nodes=0,
                    discovered_edges=0,
                    **kwargs,
                )
                await progress_callback(update.to_dict())

        await emit("seed_resolution", 2, f"بدء تحقيق القضية: {case_name}")
        await emit("seed_resolution", 3,
                    f"أدلة: {len(usernames)} أسماء مستخدمين, "
                    f"{len(emails)} بريد, {len(phones)} هاتف, "
                    f"{len(websites)} مواقع, {len(known_accounts)} حسابات معروفة")

        # ── Run investigation using comma-separated queries ──
        # The existing run() method already supports comma-separated queries
        await emit("seed_resolution", 5, "تشغيل محرك التحقيق الموحد...")

        investigation = await self.run(
            query=master_query,
            query_type=QueryType.USERNAME,
            max_depth=max_depth,
            max_nodes=max_nodes,
            progress_callback=progress_callback,
        )

        # ── Post-processing: inject case evidence as additional nodes ──
        await emit("correlation", 92, "ربط الأدلة المتعددة عبر القضية...")

        seed_id = investigation.seed_node_id

        # Add email evidence nodes
        for email in emails:
            email_node = IdentityNode(
                entity_type=EntityType.EMAIL,
                platform="Email",
                username=email,
                email=email,
                confidence=85.0,
                depth=0,
                is_seed=False,
            )
            email_node.tags.append("Case Evidence: Email")
            investigation.add_node(email_node)
            if seed_id:
                ev = Evidence(
                    evidence_type=EvidenceType.SAME_EMAIL,
                    category=EvidenceCategory.POSITIVE,
                    quality=EvidenceQuality.STRONG,
                    weight=8.0,
                    raw_weight=10.0,
                    description=f"بريد إلكتروني مقدم كدليل: {email}",
                    source_platform="Case Evidence",
                )
                chain = EvidenceChain(
                    conclusion=f"Email evidence: {email}",
                    evidence=[ev],
                )
                edge = IdentityEdge(
                    source_id=seed_id,
                    target_id=email_node.id,
                    relationship_type=RelationType.USES,
                    strength=85.0,
                    explanation=f"Email provided as case evidence",
                )
                edge.evidence_chain = chain
                investigation.add_edge(edge)

            # Cross-correlate: check if any discovered node has this email
            for node in list(investigation.nodes.values()):
                if node.email and node.email.lower() == email.lower() and node.id != email_node.id:
                    node.confidence = min(100.0, node.confidence + 15.0)
                    node.tags.append("Email Match ✓")
                    cross_ev = Evidence(
                        evidence_type=EvidenceType.SAME_EMAIL,
                        category=EvidenceCategory.POSITIVE,
                        quality=EvidenceQuality.DEFINITIVE,
                        weight=12.0,
                        raw_weight=12.0,
                        description=f"البريد {email} يطابق بريد الحساب على {node.platform}",
                    )
                    cross_chain = EvidenceChain(
                        conclusion=f"Cross-evidence email match",
                        evidence=[cross_ev],
                    )
                    cross_edge = IdentityEdge(
                        source_id=email_node.id,
                        target_id=node.id,
                        relationship_type=RelationType.SAME_PERSON,
                        strength=95.0,
                        explanation=f"Email cross-match: {email}",
                    )
                    cross_edge.evidence_chain = cross_chain
                    investigation.add_edge(cross_edge)

        # Add phone evidence nodes
        for phone in phones:
            phone_node = IdentityNode(
                entity_type=EntityType.PHONE,
                platform="Phone",
                username=phone,
                confidence=80.0,
                depth=0,
                is_seed=False,
            )
            phone_node.tags.append("Case Evidence: Phone")
            investigation.add_node(phone_node)
            if seed_id:
                edge = IdentityEdge(
                    source_id=seed_id,
                    target_id=phone_node.id,
                    relationship_type=RelationType.USES,
                    strength=80.0,
                    explanation=f"Phone provided as case evidence",
                )
                investigation.add_edge(edge)

        # Add website evidence nodes
        for website in websites:
            web_node = IdentityNode(
                entity_type=EntityType.DOMAIN,
                platform="Website",
                username=website,
                profile_url=website,
                confidence=75.0,
                depth=0,
                is_seed=False,
            )
            web_node.tags.append("Case Evidence: Website")
            investigation.add_node(web_node)
            if seed_id:
                ev = Evidence(
                    evidence_type=EvidenceType.SAME_WEBSITE,
                    category=EvidenceCategory.POSITIVE,
                    quality=EvidenceQuality.STRONG,
                    weight=7.0,
                    raw_weight=8.0,
                    description=f"موقع مقدم كدليل: {website}",
                    source_platform="Case Evidence",
                )
                chain = EvidenceChain(
                    conclusion=f"Website evidence: {website}",
                    evidence=[ev],
                )
                edge = IdentityEdge(
                    source_id=seed_id,
                    target_id=web_node.id,
                    relationship_type=RelationType.OWNS,
                    strength=75.0,
                    explanation=f"Website provided as case evidence",
                )
                edge.evidence_chain = chain
                investigation.add_edge(edge)

            # Cross-correlate: check if any node links to this website
            for node in list(investigation.nodes.values()):
                if node.website and website.lower() in node.website.lower():
                    node.confidence = min(100.0, node.confidence + 10.0)
                    node.tags.append("Website Match ✓")

        # Add location evidence — boost matching nodes
        for loc in locations:
            loc_lower = loc.lower()
            for node in investigation.nodes.values():
                if node.location and loc_lower in node.location.lower():
                    node.confidence = min(100.0, node.confidence + 5.0)
                    node.tags.append(f"Location Match: {loc}")

        # Add known accounts — boost matching nodes or create direct links
        for platform, username in known_accounts.items():
            for node in investigation.nodes.values():
                if (node.platform.lower() == platform.lower() and
                        node.username.lower() == username.lower()):
                    node.confidence = min(100.0, node.confidence + 20.0)
                    node.confidence_level = ConfidenceLevel.CONFIRMED
                    node.tags.append("Known Account ✓")

        # Attach case notes to investigation
        if notes:
            investigation.executive_summary = (
                f"ملاحظات المحقق: {notes}\n\n" +
                (investigation.executive_summary or "")
            )

        # ── Re-score everything with the new evidence ──
        for node in investigation.nodes.values():
            if node.is_seed:
                continue
            edges = investigation.get_node_edges(node.id)
            if edges:
                best_edge = max(edges, key=lambda e: e.strength)
                self.confidence_engine.score_node(
                    node, best_edge.evidence_chain
                )

        # Re-build profile with enriched data
        profile = self._build_identity_profile(investigation)
        investigation.identity_profile = profile
        self.confidence_engine.score_investigation(investigation)

        # Update counts
        investigation.confirmed_count = len(investigation.confirmed_nodes)

        # Save
        self._save_investigation(investigation)

        return investigation

    def _build_identity_profile(
        self, investigation: Investigation
    ) -> DigitalIdentityProfile:
        """Build a digital identity profile from investigation data."""
        profile = DigitalIdentityProfile()

        seed = investigation.seed_node
        if not seed:
            return profile

        # Primary name: most common display name across confirmed accounts
        names = {}
        for node in investigation.confirmed_nodes:
            if node.display_name:
                name = node.display_name.strip()
                names[name] = names.get(name, 0) + 1

        if names:
            profile.primary_name = max(names, key=names.get)
        elif seed.display_name:
            profile.primary_name = seed.display_name

        # Collect unique identity attributes
        all_usernames = set()
        all_emails = set()
        all_websites = set()
        all_locations = set()
        all_languages = set()

        for node in investigation.nodes.values():
            if node.username:
                all_usernames.add(node.username)
            if node.email:
                all_emails.add(node.email)
            if node.website:
                all_websites.add(node.website)
            if node.location:
                all_locations.add(node.location)
            if node.language:
                all_languages.add(node.language)

        profile.known_usernames = sorted(all_usernames)
        profile.known_emails = sorted(all_emails)
        profile.known_websites = sorted(all_websites)
        profile.known_locations = sorted(all_locations)
        profile.known_languages = sorted(all_languages)

        # Bio summary
        if seed.bio:
            profile.bio_summary = seed.bio[:500]

        # Confirmed platforms
        for node in sorted(
            investigation.nodes.values(),
            key=lambda n: n.confidence, reverse=True,
        ):
            entry = {
                "platform": node.platform,
                "username": node.username,
                "url": node.profile_url,
                "confidence": round(node.confidence, 1),
                "confidence_level": node.confidence_level.value,
                "display_name": node.display_name,
            }
            if node.confidence >= 70:
                profile.confirmed_platforms.append(entry)
            elif node.confidence >= 30:
                profile.probable_platforms.append(entry)

        # Risk assessment
        confirmed_count = len(profile.confirmed_platforms)
        if confirmed_count >= 10:
            profile.risk_level = RiskLevel.CRITICAL
            profile.risk_explanation = (
                f"تواجد مؤكد على {confirmed_count} منصة — بصمة رقمية واسعة جداً"
            )
        elif confirmed_count >= 5:
            profile.risk_level = RiskLevel.HIGH
            profile.risk_explanation = (
                f"تواجد مؤكد على {confirmed_count} منصات — بصمة رقمية كبيرة"
            )
        elif confirmed_count >= 3:
            profile.risk_level = RiskLevel.MODERATE
            profile.risk_explanation = (
                f"تواجد مؤكد على {confirmed_count} منصات — تواجد معتدل"
            )
        else:
            profile.risk_level = RiskLevel.LOW
            profile.risk_explanation = (
                f"تواجد محدود ({confirmed_count} منصات مؤكدة)"
            )

        return profile

    async def _run_ai_analysis(
        self, investigation: Investigation
    ) -> Dict[str, Any]:
        """Run AI analysis on the investigation results."""
        result = {
            "ai_analysis": "",
            "cross_platform": "",
            "risk_assessment": "",
            "next_steps": [],
        }

        # Build analysis context
        seed = investigation.seed_node
        nodes = list(investigation.nodes.values())
        confirmed = investigation.confirmed_nodes

        if not nodes:
            return result

        # Cross-platform analysis (rule-based)
        platforms = [n.platform for n in confirmed]
        names = list(set(n.display_name for n in confirmed if n.display_name))
        locations = list(set(n.location for n in nodes if n.location))

        cross_parts = []
        if len(platforms) > 1:
            cross_parts.append(
                f"تم تأكيد التواجد على {len(platforms)} منصات: "
                + "، ".join(platforms[:10])
            )
        if len(names) == 1:
            cross_parts.append(
                f"اسم موحد عبر المنصات: '{names[0]}' — يعزز الثقة"
            )
        elif len(names) > 1:
            cross_parts.append(
                f"أسماء متعددة مكتشفة: {', '.join(names[:5])} — يتطلب تحقيق إضافي"
            )
        if len(locations) == 1:
            cross_parts.append(
                f"موقع جغرافي موحد: '{locations[0]}'"
            )

        result["cross_platform"] = ". ".join(cross_parts)

        # Next steps
        steps = []
        if investigation.identity_profile:
            profile = investigation.identity_profile
            if profile.known_emails:
                steps.append("التحقق من عناوين البريد الإلكتروني المكتشفة عبر خدمات breach lookup")
            if profile.known_websites:
                steps.append("تحليل WHOIS للمواقع الإلكترونية المكتشفة")
        if len(confirmed) > 0:
            steps.append("مراجعة يدوية للحسابات المؤكدة والتحقق من المحتوى")
        if investigation.edge_count > 0:
            steps.append("فحص الروابط المتبادلة بين الحسابات المكتشفة")

        result["next_steps"] = steps

        # AI analysis (if Gemini available)
        if self.gemini_key:
            try:
                ai_text = await self._gemini_analysis(investigation)
                result["ai_analysis"] = ai_text
            except Exception as e:
                logger.error(f"AI analysis failed: {e}")
                result["ai_analysis"] = self._rule_based_analysis(investigation)
        else:
            result["ai_analysis"] = self._rule_based_analysis(investigation)

        return result

    async def _gemini_analysis(self, investigation: Investigation) -> str:
        """Run Gemini AI analysis on investigation data."""
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.gemini_key)
            model = genai.GenerativeModel("gemini-2.0-flash")

            # Build concise context
            seed = investigation.seed_node
            confirmed = investigation.confirmed_nodes

            platforms_info = "\n".join(
                f"- {n.platform}: @{n.username} (ثقة {n.confidence:.0f}%)"
                + (f" — {n.display_name}" if n.display_name else "")
                for n in sorted(confirmed, key=lambda x: x.confidence, reverse=True)[:15]
            )

            all_evidence = investigation.all_evidence
            positive_ev = [e for e in all_evidence if e.is_positive and e.is_actionable]
            negative_ev = [e for e in all_evidence if e.is_negative]

            evidence_summary = "\n".join(
                f"+ {e.description}" for e in positive_ev[:10]
            )
            if negative_ev:
                evidence_summary += "\n" + "\n".join(
                    f"- {e.description}" for e in negative_ev[:5]
                )

            prompt = f"""أنت محلل استخبارات رقمية محترف. حلل نتائج التحقيق التالية وقدم تقييماً مختصراً.

الهدف: {investigation.initial_query}
الهوية الأولية: {seed.label if seed else 'غير معروف'}
عدد المنصات المؤكدة: {len(confirmed)}
عدد المنصات المكتشفة: {investigation.node_count}

المنصات المؤكدة:
{platforms_info}

ملخص الأدلة:
{evidence_summary}

قدم تحليلاً مختصراً (5-8 جمل) يشمل:
1. ملخص الهوية الرقمية المكتشفة
2. مستوى الثقة وأسبابه
3. التحليل النفسي والمشاعر (Sentiment Analysis) بناءً على النبذات (Bios) المكتشفة
4. اللغة السائدة والاهتمامات المشتركة
5. تقييم المخاطر الرقمية

أجب بالعربية فقط. كن دقيقاً ومهنياً."""

            response = await model.generate_content_async(prompt)
            return response.text.strip()

        except ImportError:
            return self._rule_based_analysis(investigation)
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return self._rule_based_analysis(investigation)

    def _rule_based_analysis(self, investigation: Investigation) -> str:
        """Fallback rule-based analysis when AI is not available."""
        import re
        confirmed = investigation.confirmed_nodes
        total = investigation.node_count

        if not confirmed:
            return (
                f"التحقيق في '{investigation.initial_query}' لم يسفر عن حسابات مؤكدة بدرجة عالية. "
                f"تم اكتشاف {total} حساب محتمل لكن بأدلة غير كافية. "
                f"يُوصى بالتحقق اليدوي."
            )

        parts = [
            f"التحقيق في '{investigation.initial_query}' كشف عن {len(confirmed)} حساب مؤكد "
            f"من أصل {total} حساب مكتشف."
        ]

        seed = investigation.seed_node
        if seed and seed.display_name:
            parts.append(f"الاسم الأساسي المكتشف: {seed.display_name}.")

        platforms = [n.platform for n in confirmed]
        if platforms:
            parts.append(f"المنصات المؤكدة: {', '.join(platforms[:8])}.")

        # Language & Sentiment Fallback
        bios = [n.bio for n in confirmed if n.bio]
        if bios:
            full_bio_text = " ".join(bios)
            arabic_chars = len(re.findall(r'[\u0600-\u06FF]', full_bio_text))
            english_chars = len(re.findall(r'[a-zA-Z]', full_bio_text))
            
            if arabic_chars > english_chars:
                lang = "العربية"
            elif english_chars > arabic_chars:
                lang = "الإنجليزية"
            else:
                lang = "مزيج من اللغات"
                
            parts.append(f"التحليل اللغوي للنبذات يشير إلى أن اللغة السائدة هي {lang}.")
            parts.append("التحليل النفسي غير متاح (يتطلب تفعيل Gemini AI).")

        all_evidence = investigation.all_evidence
        definitive = [e for e in all_evidence if e.quality.value == "definitive" and e.is_positive]
        if definitive:
            parts.append(
                f"تم العثور على {len(definitive)} دليل قاطع يربط بين الحسابات."
            )

        negative = [e for e in all_evidence if e.is_negative]
        if negative:
            parts.append(
                f"⚠ لوحظ {len(negative)} دليل سلبي يتطلب مراجعة."
            )

        return " ".join(parts)

    def _save_investigation(self, investigation: Investigation) -> None:
        """Save complete investigation to database."""
        try:
            self.db.save_investigation(investigation)

            for node in investigation.nodes.values():
                self.db.save_node(investigation.id, node)

            for edge in investigation.edges.values():
                self.db.save_edge(investigation.id, edge)
                for ev in edge.evidence_chain.evidence:
                    self.db.save_evidence(
                        investigation.id, ev, edge_id=edge.id
                    )

        except Exception as e:
            logger.error(f"Failed to save investigation: {e}")
