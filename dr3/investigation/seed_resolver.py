"""
DR3 Intelligence Platform — Seed Resolver

Phase 1 of the investigation pipeline.

Purpose: Find the FIRST RELIABLE IDENTITY — the account with
the richest identity data that will serve as the foundation
for the entire investigation.

The old system checked 3000 sites blindly.
The new system checks 10-20 HIGH-VALUE platforms first,
picks the richest result, and builds from there.

Selection criteria (in order):
  1. Identity richness (how many fields are populated)
  2. Platform tier (Tier 1 > Tier 2 > Tier 3)
  3. Collection method quality (API > Scrape > Status code)
  4. Has expansion targets (links, emails, usernames)
"""

import asyncio
import logging
from typing import Callable, List, Optional, Tuple

from ..collectors.api_collectors.github_collector import GitHubCollector
from ..collectors.api_collectors.reddit_collector import RedditCollector
from ..collectors.api_collectors.twitter_collector import TwitterCollector
from ..collectors.base_collector import HttpCollector
from ..core.constants import SEED_PRIORITY_PLATFORMS
from ..core.enums import (
    CheckStatus,
    CollectionMethod,
    EntityType,
    PlatformTier,
)
from ..core.models import CollectionResult, IdentityNode, SiteConfig
from ..search.sites_db import SitesDatabase

logger = logging.getLogger("dr3.seed_resolver")


class SeedResolver:
    """
    Resolves the initial seed identity for an investigation.

    Strategy:
      1. First, try dedicated API collectors (GitHub, etc.)
         These provide the richest data.
      2. Then, try Tier 1 platforms via HTTP collector.
      3. Pick the result with the highest identity richness.
      4. Convert to IdentityNode as the seed.
    """

    def __init__(self, sites_db: SitesDatabase, github_token: str = ""):
        self.sites_db = sites_db
        self.github_token = github_token
        self.http_collector = HttpCollector()

    async def resolve(
        self,
        username: str,
        progress_callback: Optional[Callable] = None,
    ) -> Tuple[Optional[IdentityNode], List[CollectionResult]]:
        """
        Find the best seed identity for a username.

        Returns:
          - seed_node: The best IdentityNode (or None if nothing found)
          - all_results: All CollectionResults from seed resolution
        """
        all_results: List[CollectionResult] = []
        candidates: List[CollectionResult] = []

        # ── Phase A: API Collectors (highest quality) ──
        if progress_callback:
            await progress_callback("فحص APIs المباشرة (GitHub, Reddit)...")

        api_results = await self._check_api_collectors(username)
        all_results.extend(api_results)

        for result in api_results:
            if result.is_found:
                candidates.append(result)
                logger.info(
                    f"[SEED] API candidate: {result.platform} "
                    f"(richness={result.identity_richness})"
                )

        # ── Phase B: Tier 1 HTTP platforms ──
        if progress_callback:
            await progress_callback("فحص المنصات ذات الأولوية...")

        tier1_sites = self._get_seed_sites()
        http_results = await self._check_http_batch(username, tier1_sites, progress_callback)
        all_results.extend(http_results)

        for result in http_results:
            if result.is_found:
                candidates.append(result)

        # ── Phase C: Select best seed ──
        if not candidates:
            logger.warning(f"[SEED] No candidates found for '{username}'")
            return None, all_results

        # Sort by: identity_richness DESC, has_expansion_targets DESC, tier
        candidates.sort(
            key=lambda r: (
                r.identity_richness,
                1 if r.has_expansion_targets else 0,
                3 if r.platform_tier == PlatformTier.TIER_1 else (
                    2 if r.platform_tier == PlatformTier.TIER_2 else 1
                ),
                1 if r.collection_method == CollectionMethod.DIRECT_API else 0,
            ),
            reverse=True,
        )

        best = candidates[0]
        logger.info(
            f"[SEED] Selected: {best.platform} "
            f"(richness={best.identity_richness}, "
            f"method={best.collection_method.value})"
        )

        # Convert to IdentityNode
        seed_node = self._result_to_node(best, is_seed=True)

        return seed_node, all_results

    async def _check_api_collectors(
        self, username: str
    ) -> List[CollectionResult]:
        """Check dedicated API collectors in parallel."""
        from ..collectors.api_collectors.telegram_collector import TelegramCollector
        from ..collectors.api_collectors.instagram_collector import InstagramCollector
        from ..collectors.api_collectors.facebook_collector import FacebookCollector

        collectors = [
            GitHubCollector(token=self.github_token or None),
            RedditCollector(),
            TwitterCollector(),
            TelegramCollector(),
            InstagramCollector(),
            FacebookCollector(),
        ]

        async def _safe_collect(collector):
            """Run a collector with error handling."""
            try:
                return await collector.collect(username)
            except Exception as e:
                logger.error(f"{collector.platform_name} collector failed: {e}")
                return None

        # Run ALL collectors in parallel
        raw_results = await asyncio.gather(
            *[_safe_collect(c) for c in collectors]
        )

        return [r for r in raw_results if r is not None]

    async def _check_http_batch(
        self,
        username: str,
        sites: List[SiteConfig],
        progress_callback: Optional[Callable] = None,
    ) -> List[CollectionResult]:
        """Check multiple sites concurrently via HTTP."""
        results = []

        # Batch in groups of 10 for controlled concurrency
        batch_size = 10
        total = len(sites)

        for i in range(0, total, batch_size):
            batch = sites[i:i + batch_size]
            tasks = [
                self.http_collector.check_site(site, username)
                for site in batch
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, CollectionResult):
                    results.append(result)
                elif isinstance(result, Exception):
                    logger.debug(f"Site check failed: {result}")

            if progress_callback:
                checked = min(i + batch_size, total)
                found = sum(1 for r in results if r.is_found)
                await progress_callback(
                    f"فحص Seed: {checked}/{total} منصة (وجد: {found})"
                )

        return results

    def _get_seed_sites(self) -> List[SiteConfig]:
        """Get sites suitable for seed resolution."""
        sites = self.sites_db.enabled_sites

        # Filter: only seed priority platforms AND sites with good check methods
        seed_sites = []
        other_tier1 = []

        for site in sites:
            if site.name in SEED_PRIORITY_PLATFORMS:
                seed_sites.append(site)
            elif site.name in (
                "Twitter", "Instagram", "LinkedIn", "Facebook", "YouTube",
                "TikTok", "Pinterest", "Twitch", "Steam", "Discord",
                "Spotify", "Telegram", "Snapchat"
            ):
                other_tier1.append(site)

        # Prioritize seed platforms, then other Tier 1
        result = seed_sites + other_tier1[:10]

        # Limit to 20 total for seed resolution
        return result[:20]

    def _result_to_node(
        self, result: CollectionResult, is_seed: bool = False
    ) -> IdentityNode:
        """Convert a CollectionResult to an IdentityNode."""
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
            is_seed=is_seed,
            depth=0,
            platform_tier=result.platform_tier,
            collection_method=result.collection_method,
            tags=result.tags,
            extra_data={
                **result.extra_data,
                "public_links": result.public_links,
                "discovered_usernames": result.discovered_usernames,
                "mentioned_emails": result.mentioned_emails,
                "mentioned_names": result.mentioned_names,
            },
        )

    async def close(self) -> None:
        await self.http_collector.close()
