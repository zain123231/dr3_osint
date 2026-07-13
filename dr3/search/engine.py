"""
DR3 OSINT — Main Search Engine
Orchestrates the multi-stage search pipeline.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from ..core.constants import BAD_USERNAME_CHARS
from ..core.enums import CheckStatus, SearchPhase
from ..core.models import CheckResult, IdentityReport, ProfileData, SearchProgress, SiteConfig
from .checker import HttpChecker
from .dorking import DorkingEngine
from .sites_db import SitesDatabase

logger = logging.getLogger("dr3.engine")


class SearchEngine:
    """
    Main search engine — orchestrates the multi-stage search pipeline.

    Pipeline stages:
    1. Pre-processing: validate input, generate variations
    2. Searching: parallel HTTP checks
    3. Validating: filter false positives
    4. Analyzing: AI analysis + confidence scoring
    5. Post-processing: ranking + report generation
    """

    def __init__(
        self,
        db: SitesDatabase,
        timeout: int = 15,
        max_connections: int = 50,
        proxy: Optional[str] = None,
    ):
        self.db = db
        self.timeout = timeout
        self.max_connections = max_connections
        self.proxy = proxy
        self._checker = HttpChecker(
            timeout=timeout,
            max_connections=max_connections,
            proxy=proxy,
        )
        self._dorking = DorkingEngine(timeout=timeout)

    async def close(self):
        """Cleanup resources."""
        await self._checker.close()

    async def search(
        self,
        username: str,
        top_sites: int = 500,
        tags: Optional[List[str]] = None,
        site_names: Optional[List[str]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> IdentityReport:
        """
        Execute a full search for a username.
        Returns a complete IdentityReport.
        """
        search_id = str(uuid.uuid4())[:8]
        started_at = datetime.now()

        logger.info(f"[{search_id}] Starting search for '{username}'")

        # ── Stage 1: Pre-processing ──
        if progress_callback:
            await progress_callback(SearchProgress(
                search_id=search_id,
                phase=SearchPhase.PREPROCESSING.value,
                progress=0,
                message=f"Preparing search for '{username}'...",
            ))

        # Validate username
        errors = self._validate_username(username)
        if errors:
            return IdentityReport(
                target_username=username,
                search_id=search_id,
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Get sites to check
        sites = self.db.get_ranked_sites(
            top=top_sites,
            tags=tags,
            names=site_names,
            include_disabled=False,
        )

        if not sites:
            logger.warning(f"[{search_id}] No sites to check")
            return IdentityReport(
                target_username=username,
                search_id=search_id,
                started_at=started_at,
                completed_at=datetime.now(),
            )

        total_sites = len(sites)
        logger.info(f"[{search_id}] Checking {total_sites} sites...")

        # ── Stage 2: Searching ──
        if progress_callback:
            await progress_callback(SearchProgress(
                search_id=search_id,
                phase=SearchPhase.SEARCHING.value,
                progress=5,
                total_sites=total_sites,
                message=f"Searching across {total_sites} platforms...",
            ))

        raw_results = await self._parallel_search(
            username, sites, search_id, progress_callback
        )

        # ── Stage 3: Validating ──
        if progress_callback:
            await progress_callback(SearchProgress(
                search_id=search_id,
                phase=SearchPhase.VALIDATING.value,
                progress=75,
                total_sites=total_sites,
                checked_sites=total_sites,
                found_count=len([r for r in raw_results if r.is_found]),
                message="Validating results and filtering false positives...",
            ))

        validated_results = self._validate_results(raw_results, username)

        # ── Stage 4: Analyzing ──
        if progress_callback:
            await progress_callback(SearchProgress(
                search_id=search_id,
                phase=SearchPhase.ANALYZING.value,
                progress=85,
                total_sites=total_sites,
                checked_sites=total_sites,
                found_count=len(validated_results),
                message="Analyzing identity correlations...",
            ))

        profiles = self._build_profiles(validated_results, username)

        # ── Stage 5: Post-processing ──
        if progress_callback:
            await progress_callback(SearchProgress(
                search_id=search_id,
                phase=SearchPhase.POSTPROCESSING.value,
                progress=95,
                total_sites=total_sites,
                checked_sites=total_sites,
                found_count=len(profiles),
                message="Generating investigation report...",
            ))

        # Build final report
        report = self._build_report(
            username=username,
            search_id=search_id,
            started_at=started_at,
            profiles=profiles,
            total_sites=total_sites,
        )

        if progress_callback:
            await progress_callback(SearchProgress(
                search_id=search_id,
                phase="complete",
                progress=100,
                total_sites=total_sites,
                checked_sites=total_sites,
                found_count=len(profiles),
                message="Investigation complete.",
                is_complete=True,
            ))

        logger.info(
            f"[{search_id}] Search complete: {len(profiles)} profiles found "
            f"in {report.duration_seconds:.1f}s"
        )

        return report

    def _validate_username(self, username: str) -> List[str]:
        """Validate username input."""
        errors = []
        if not username or not username.strip():
            errors.append("Username cannot be empty")
        elif len(username) < 2:
            errors.append("Username too short")
        elif len(username) > 64:
            errors.append("Username too long")
        else:
            bad_chars = set(BAD_USERNAME_CHARS) & set(username)
            if bad_chars:
                errors.append(f"Unsupported characters: {', '.join(bad_chars)}")
        return errors

    async def _parallel_search(
        self,
        username: str,
        sites: List[SiteConfig],
        search_id: str,
        progress_callback: Optional[Callable],
    ) -> List[CheckResult]:
        """Execute parallel checks across all sites."""
        results: List[CheckResult] = []
        semaphore = asyncio.Semaphore(self.max_connections)
        total = len(sites)
        checked = 0

        async def check_with_semaphore(site: SiteConfig) -> CheckResult:
            nonlocal checked
            async with semaphore:
                try:
                    # SPECIAL CASE: Instagram and other SPA hard targets
                    # These sites always return HTTP 200 with generic JS payloads,
                    # so standard HTTP checking is useless. We bypass it and force Dorking.
                    if self._dorking._is_hard_target(site):
                        logger.debug(f"Special case triggered: Forcing Dorking for {site.name}")
                        fallback_result = await self._dorking.fallback_check(site, username)
                        if fallback_result:
                            result = fallback_result
                        else:
                            # If dorking completely fails to execute, return as ERROR or AVAILABLE
                            result = CheckResult(
                                site_name=site.name,
                                url=site.url.replace("{username}", username),
                                status=CheckStatus.AVAILABLE,
                                url_main=site.url_main,
                                tags=site.tags,
                                fallback_used=True
                            )
                    else:
                        result = await self._checker.check_site(site, username)
                except Exception as e:
                    logger.debug(f"Error checking {site.name}: {e}")
                    result = CheckResult(
                        site_name=site.name,
                        url="",
                        status=CheckStatus.ERROR,
                        url_main=site.url_main,
                        error_message=str(e),
                        tags=site.tags,
                    )

                checked += 1
                if progress_callback and checked % 10 == 0:
                    found = len([r for r in results if r.is_found])
                    progress = 5 + int(70 * checked / total)
                    await progress_callback(SearchProgress(
                        search_id=search_id,
                        phase=SearchPhase.SEARCHING.value,
                        progress=progress,
                        total_sites=total,
                        checked_sites=checked,
                        found_count=found,
                        current_site=site.name,
                        message=f"Checking {site.name}...",
                    ))

                return result

        # Run all checks concurrently
        tasks = [check_with_semaphore(site) for site in sites]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return list(results)

    def _validate_results(
        self, results: List[CheckResult], username: str
    ) -> List[CheckResult]:
        """
        Validate results and filter false positives.
        This is the critical quality gate.
        """
        validated = []
        from ..core.constants import FALSE_POSITIVE_PATTERNS

        for result in results:
            if not result.is_found:
                continue

            is_false_positive = False
            fp_reason = ""

            # Check 1: Page title contains false positive patterns
            page_title = result.extracted_data.get("page_title", "").lower()
            for pattern in FALSE_POSITIVE_PATTERNS:
                if pattern in page_title:
                    is_false_positive = True
                    fp_reason = f"Page title indicates non-existence: '{pattern}'"
                    break

            # Check 2: Meta description contains false positive patterns
            if not is_false_positive:
                meta_desc = result.extracted_data.get("meta_description", "").lower()
                for pattern in ["sign up", "create account", "register", "join"]:
                    if pattern in meta_desc and username.lower() not in meta_desc:
                        is_false_positive = True
                        fp_reason = f"Generic page detected: '{pattern}' in description"
                        break

            # Check 3: Status code edge cases
            if not is_false_positive:
                if result.http_status == 200 and result.extracted_data.get("page_title", "").strip() == "":
                    # 200 with empty title is suspicious for many sites
                    pass  # Don't reject, but lower confidence later

            if not is_false_positive:
                validated.append(result)
            else:
                logger.debug(f"Filtered false positive: {result.site_name} - {fp_reason}")

        return validated

    def _build_profiles(
        self, results: List[CheckResult], username: str
    ) -> List[ProfileData]:
        """Build ProfileData objects from validated results."""
        from ..intelligence.confidence import ConfidenceScorer
        scorer = ConfidenceScorer()

        profiles = []
        for result in results:
            profile = ProfileData(
                site_name=result.site_name,
                url=result.url,
                username=username,
                display_name=result.extracted_data.get("og_title", ""),
                bio=result.extracted_data.get("meta_description", "")
                    or result.extracted_data.get("og_description", ""),
                avatar_url=result.extracted_data.get("og_image", ""),
                tags=result.tags,
                extra_data=result.extracted_data,
                fallback_used=getattr(result, "fallback_used", False)
            )

            # Calculate confidence score
            profile = scorer.score_profile(profile, username)
            profiles.append(profile)

        # Sort by confidence (highest first)
        profiles.sort(key=lambda p: p.confidence_score, reverse=True)

        return profiles

    def _build_report(
        self,
        username: str,
        search_id: str,
        started_at: datetime,
        profiles: List[ProfileData],
        total_sites: int,
    ) -> IdentityReport:
        """Build the final investigation report."""
        completed_at = datetime.now()
        confirmed = [p for p in profiles if p.confidence_score >= 70]
        possible = [p for p in profiles if 30 <= p.confidence_score < 70]

        # Collect all evidence
        all_evidence = []
        for profile in profiles:
            all_evidence.extend(profile.evidence)

        # Calculate overall confidence
        if profiles:
            overall = sum(p.confidence_score for p in profiles) / len(profiles)
        else:
            overall = 0.0

        from ..core.enums import ConfidenceLevel

        report = IdentityReport(
            target_username=username,
            search_id=search_id,
            started_at=started_at,
            completed_at=completed_at,
            total_sites_checked=total_sites,
            total_found=len(profiles),
            total_confirmed=len(confirmed),
            total_possible=len(possible),
            overall_confidence=overall,
            overall_confidence_level=ConfidenceLevel.from_score(overall),
            profiles=profiles,
            evidence_summary=all_evidence,
            suggested_next_steps=self._generate_next_steps(profiles, username),
        )

        return report

    def _generate_next_steps(
        self, profiles: List[ProfileData], username: str
    ) -> List[str]:
        """Generate investigation next steps based on findings."""
        steps = []

        if not profiles:
            steps.append(f"No accounts found for '{username}'. Try searching with username variations.")
            steps.append("Consider checking other identifier types (email, phone).")
            return steps

        # Suggest deeper investigation for high-confidence profiles
        high_conf = [p for p in profiles if p.confidence_score >= 70]
        if high_conf:
            steps.append(
                f"Manually verify the {len(high_conf)} high-confidence profiles "
                f"for additional identifying information."
            )

        # Check for email/website leads
        has_websites = any(p.extra_data.get("og_url") for p in profiles)
        if has_websites:
            steps.append("Follow up on discovered website links for additional OSINT.")

        # Username variations
        steps.append(f"Search for common variations: {username}_, _{username}, {username}123")

        # Cross-reference
        if len(profiles) >= 3:
            steps.append(
                "Cross-reference discovered profiles to identify shared connections "
                "and confirm identity correlation."
            )

        return steps
