"""
DR3 Intelligence Platform — Identity Expander

Phase 2-3 of the investigation pipeline.

This is the HEART of the new platform. The old system checked
3000 sites for one username. The new system:

  1. Takes the seed identity
  2. Extracts expansion targets (names, emails, links, usernames)
  3. For each target, searches relevant platforms
  4. Evaluates evidence for each discovery
  5. Adds high-confidence discoveries to the graph
  6. Repeats until max depth or max nodes reached

The expansion is BREADTH-FIRST with QUALITY GATES:
  - Only expand nodes with confidence >= EXPANSION_THRESHOLD
  - Only expand up to MAX_EXPANSION_DEPTH hops
  - Only allow MAX_GRAPH_NODES total nodes
"""

import asyncio
import logging
from typing import Callable, Dict, List, Optional, Set

from ..collectors.base_collector import HttpCollector
from ..core.constants import (
    EXPANSION_CONFIDENCE_THRESHOLD,
    MAX_EXPANSION_DEPTH,
    MAX_GRAPH_NODES,
)
from ..core.enums import (
    CheckStatus,
    CollectionMethod,
    EntityType,
    PlatformTier,
    QueryType,
    RelationType,
)
from ..core.evidence import EvidenceChain
from ..core.models import (
    CollectionResult,
    IdentityEdge,
    IdentityNode,
    Investigation,
    SearchTarget,
    SiteConfig,
)
from ..intelligence.confidence_engine import ConfidenceEngine
from ..intelligence.evidence_engine import EvidenceEngine
from ..search.sites_db import SitesDatabase

logger = logging.getLogger("dr3.expander")


class IdentityExpander:
    """
    Expands an investigation from a seed identity outward.

    Think of it as a wave propagation:
      Seed (depth 0)
        → Discovered accounts (depth 1)
          → Further discoveries (depth 2)
            → ...up to max_depth

    At each depth, only HIGH-CONFIDENCE discoveries propagate.
    """

    def __init__(self, sites_db: SitesDatabase):
        self.sites_db = sites_db
        self.evidence_engine = EvidenceEngine()
        self.confidence_engine = ConfidenceEngine()
        self.http_collector = HttpCollector()

    async def expand(
        self,
        investigation: Investigation,
        progress_callback: Optional[Callable] = None,
        pre_discovered_results: Optional[List[CollectionResult]] = None,
    ) -> Investigation:
        """
        Run identity expansion from the seed outward.

        Modifies the investigation in-place:
          - Adds nodes
          - Adds edges with evidence chains
          - Updates confidence scores
        """
        seed = investigation.seed_node
        if not seed:
            logger.warning("No seed node — cannot expand")
            return investigation

        max_depth = investigation.max_expansion_depth
        max_nodes = investigation.max_nodes

        # Track what we've already investigated
        investigated_queries: Set[str] = set()
        investigated_queries.add(investigation.initial_query.lower())

        # ── Depth 0: Broad check for the original username ──
        if progress_callback:
            await progress_callback("توسيع التحقيق: فحص المنصات...")

        initial_results = await self._broad_check(
            investigation.initial_query,
            progress_callback=progress_callback,
        )
        
        if pre_discovered_results:
            # Add API results from seed resolver that were NOT chosen as seed
            for r in pre_discovered_results:
                # Avoid duplicates
                if not any(x.platform == r.platform for x in initial_results):
                    initial_results.append(r)

        for result in initial_results:
            if not result.is_found:
                continue
            if result.platform == seed.platform:
                continue  # Skip seed platform
            if investigation.node_count >= max_nodes:
                break

            # Create node and evaluate evidence
            node = self._result_to_node(result, depth=1)
            chain = self.evidence_engine.evaluate_cross_platform(seed, node)
            chain.evidence.extend(
                self.evidence_engine.evaluate_collection(result, investigation.initial_query)
            )

            self.confidence_engine.score_node(node, chain)

            # Only add if confidence is meaningful
            if node.confidence > 5:
                investigation.add_node(node)

                # Create edge
                edge = IdentityEdge(
                    source_id=seed.id,
                    target_id=node.id,
                    evidence_chain=chain,
                    strength=node.confidence,
                )
                self._classify_edge(edge)
                investigation.add_edge(edge)

                investigation.total_platforms_checked += 1

        # ── Depth 1+: Expansion from seed's expansion targets ──
        expansion_queue = self._extract_expansion_targets(seed)

        current_depth = 1
        while expansion_queue and current_depth <= max_depth:
            if investigation.node_count >= max_nodes:
                logger.info(f"Max nodes ({max_nodes}) reached")
                break

            if progress_callback:
                await progress_callback(
                    f"توسيع التحقيق: عمق {current_depth}/{max_depth} "
                    f"({investigation.node_count} عقدة، {len(expansion_queue)} هدف)"
                )

            next_queue = []
            for target in expansion_queue:
                if target.query.lower() in investigated_queries:
                    continue
                investigated_queries.add(target.query.lower())

                if investigation.node_count >= max_nodes:
                    break

                # Search for this target
                results = await self._targeted_search(
                    target, progress_callback
                )

                for result in results:
                    if not result.is_found:
                        continue

                    # Check if platform already in graph
                    if self._platform_exists(investigation, result.platform, result.username):
                        continue

                    if investigation.node_count >= max_nodes:
                        break

                    node = self._result_to_node(result, depth=target.depth + 1)

                    # Evaluate evidence against seed
                    chain = self.evidence_engine.evaluate_cross_platform(seed, node)
                    chain.evidence.extend(
                        self.evidence_engine.evaluate_collection(
                            result, target.query
                        )
                    )

                    self.confidence_engine.score_node(node, chain)

                    if node.confidence > 5:
                        investigation.add_node(node)

                        edge = IdentityEdge(
                            source_id=seed.id,
                            target_id=node.id,
                            evidence_chain=chain,
                            strength=node.confidence,
                        )
                        self._classify_edge(edge)
                        investigation.add_edge(edge)

                        # If high confidence, extract more targets
                        if (
                            node.confidence >= EXPANSION_CONFIDENCE_THRESHOLD
                            and target.depth + 1 < max_depth
                        ):
                            new_targets = self._extract_expansion_targets(node)
                            for nt in new_targets:
                                nt.depth = target.depth + 1
                            next_queue.extend(new_targets)

            expansion_queue = next_queue
            current_depth += 1
            investigation.expansion_depth_reached = current_depth

        # ── Detect direct links across all nodes ──
        if progress_callback:
            await progress_callback("كشف الروابط المباشرة بين الحسابات...")

        all_nodes = list(investigation.nodes.values())
        for node in all_nodes:
            direct_evidence = self.evidence_engine.detect_direct_links(
                node, all_nodes
            )
            for ev in direct_evidence:
                target_id = ev.target_entity_id
                if target_id in investigation.nodes:
                    # Find or create edge
                    existing_edge = self._find_edge(
                        investigation, node.id, target_id
                    )
                    if existing_edge:
                        existing_edge.evidence_chain.add(ev)
                        # Re-score
                        score, level, expl = self.confidence_engine.score_evidence_chain(
                            existing_edge.evidence_chain
                        )
                        existing_edge.strength = score
                        self._classify_edge(existing_edge)
                    else:
                        chain = EvidenceChain()
                        chain.add(ev)
                        edge = IdentityEdge(
                            source_id=node.id,
                            target_id=target_id,
                            evidence_chain=chain,
                            strength=ev.weight,
                        )
                        self._classify_edge(edge)
                        investigation.add_edge(edge)

        await self.http_collector.close()
        return investigation

    async def _broad_check(
        self,
        username: str,
        max_sites: int = 200,
        progress_callback: Optional[Callable] = None,
    ) -> List[CollectionResult]:
        """Check many platforms for a username (breadth search)."""
        sites = self.sites_db.enabled_sites[:max_sites]
        results = []

        batch_size = 20
        total = len(sites)

        for i in range(0, total, batch_size):
            batch = sites[i:i + batch_size]
            tasks = [
                self.http_collector.check_site(site, username)
                for site in batch
            ]
            batch_results = await asyncio.gather(
                *tasks, return_exceptions=True
            )

            for r in batch_results:
                if isinstance(r, CollectionResult):
                    results.append(r)

            if progress_callback and (i + batch_size) % 60 == 0:
                checked = min(i + batch_size, total)
                found = sum(1 for r in results if r.is_found)
                await progress_callback(
                    f"فحص عام: {checked}/{total} منصة (وجد: {found})"
                )

        return results

    async def _targeted_search(
        self,
        target: SearchTarget,
        progress_callback: Optional[Callable] = None,
    ) -> List[CollectionResult]:
        """Search for a specific target (name, email, etc.)."""
        results = []

        if target.query_type == QueryType.USERNAME:
            # Check relevant platforms for username
            sites = self.sites_db.enabled_sites[:50]
            tasks = [
                self.http_collector.check_site(site, target.query)
                for site in sites
            ]
            batch_results = await asyncio.gather(
                *tasks, return_exceptions=True
            )
            for r in batch_results:
                if isinstance(r, CollectionResult):
                    results.append(r)

        return results

    def _extract_expansion_targets(
        self, node: IdentityNode
    ) -> List[SearchTarget]:
        """Extract new investigation targets from a node."""
        targets = []
        extra = node.extra_data or {}

        # Discovered usernames
        for uname in extra.get("discovered_usernames", []):
            if uname and uname.strip():
                targets.append(SearchTarget(
                    query=uname.strip(),
                    query_type=QueryType.USERNAME,
                    source_platform=node.platform,
                    source_entity_id=node.id,
                    priority=3.0,
                ))

        # Website
        if node.website:
            targets.append(SearchTarget(
                query=node.website,
                query_type=QueryType.URL,
                source_platform=node.platform,
                source_entity_id=node.id,
                priority=2.0,
            ))

        # Email
        if node.email:
            targets.append(SearchTarget(
                query=node.email,
                query_type=QueryType.EMAIL,
                source_platform=node.platform,
                source_entity_id=node.id,
                priority=4.0,
            ))

        return targets

    def _result_to_node(
        self, result: CollectionResult, depth: int = 1
    ) -> IdentityNode:
        """Convert CollectionResult to IdentityNode."""
        return IdentityNode(
            entity_type=EntityType.ACCOUNT,
            platform=result.platform,
            username=result.username,
            profile_url=result.profile_url,
            display_name=result.display_name,
            bio=result.bio,
            avatar_url=result.avatar_url,
            website=result.website,
            email=result.email,
            location=result.location,
            language=result.language,
            company=result.company,
            external_links=result.public_links,
            account_created=result.created_at,
            last_active=result.last_active,
            followers=result.followers,
            following=result.following,
            posts=result.posts,
            depth=depth,
            platform_tier=result.platform_tier,
            collection_method=result.collection_method,
            tags=result.tags,
            extra_data=result.extra_data,
        )

    def _platform_exists(
        self, investigation: Investigation, platform: str, username: str
    ) -> bool:
        """Check if a platform/username combo already exists in the graph."""
        for node in investigation.nodes.values():
            if (
                node.platform == platform
                and node.username.lower() == username.lower()
            ):
                return True
        return False

    def _find_edge(
        self,
        investigation: Investigation,
        source_id: str,
        target_id: str,
    ) -> Optional[IdentityEdge]:
        """Find an existing edge between two nodes."""
        for edge in investigation.edges.values():
            if (
                (edge.source_id == source_id and edge.target_id == target_id)
                or (edge.source_id == target_id and edge.target_id == source_id)
            ):
                return edge
        return None

    def _classify_edge(self, edge: IdentityEdge) -> None:
        """Classify edge relationship type based on strength."""
        if edge.evidence_chain.has_definitive:
            edge.relationship_type = RelationType.SAME_PERSON
        elif edge.strength >= 70:
            edge.relationship_type = RelationType.LIKELY_SAME
        elif edge.strength >= 40:
            edge.relationship_type = RelationType.POSSIBLE_MATCH
        else:
            edge.relationship_type = RelationType.ASSOCIATED

        edge.explanation = edge.evidence_chain.build_explanation()
