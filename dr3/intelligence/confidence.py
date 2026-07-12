"""
DR3 OSINT — Confidence Scoring Engine
Calculates evidence-based confidence scores for profile matches.
Every score has an explainable reason.
"""

import difflib
import logging
from typing import List

from ..core.constants import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_VERY_HIGH,
    EVIDENCE_WEIGHTS,
    TIER_1_PLATFORMS,
    TIER_2_PLATFORMS,
)
from ..core.enums import ConfidenceLevel, EvidenceType
from ..core.models import Evidence, ProfileData

logger = logging.getLogger("dr3.confidence")


class ConfidenceScorer:
    """
    Calculates confidence scores based on explainable evidence.
    Every score is justified — no random numbers.
    """

    def score_profile(self, profile: ProfileData, target_username: str) -> ProfileData:
        """Calculate confidence score for a single profile."""
        evidence_list: List[Evidence] = []
        total_weight = 0.0

        # ── Evidence 1: Username match ──
        username_evidence = self._evaluate_username(
            profile.username, target_username, profile.site_name
        )
        if username_evidence:
            evidence_list.append(username_evidence)
            total_weight += username_evidence.weight

        # ── Evidence 2: Platform reliability ──
        platform_evidence = self._evaluate_platform(profile.site_name)
        if platform_evidence:
            evidence_list.append(platform_evidence)
            total_weight += platform_evidence.weight

        # ── Evidence 3: Profile completeness ──
        completeness_evidence = self._evaluate_completeness(profile)
        if completeness_evidence:
            evidence_list.append(completeness_evidence)
            total_weight += completeness_evidence.weight

        # ── Evidence 4: Display name presence ──
        if profile.display_name:
            dn_evidence = Evidence(
                evidence_type=EvidenceType.SAME_DISPLAY_NAME,
                description=f"Display name detected: '{profile.display_name}'",
                weight=5.0,
                source_site=profile.site_name,
            )
            evidence_list.append(dn_evidence)
            total_weight += dn_evidence.weight

        # ── Evidence 5: Bio/description presence ──
        if profile.bio and len(profile.bio) > 20:
            bio_evidence = Evidence(
                evidence_type=EvidenceType.SIMILAR_BIO,
                description=f"Bio detected ({len(profile.bio)} chars)",
                weight=5.0,
                source_site=profile.site_name,
            )
            evidence_list.append(bio_evidence)
            total_weight += bio_evidence.weight

        # ── Evidence 6: Avatar presence ──
        if profile.avatar_url:
            avatar_evidence = Evidence(
                evidence_type=EvidenceType.SAME_AVATAR,
                description="Profile image detected",
                weight=5.0,
                source_site=profile.site_name,
            )
            evidence_list.append(avatar_evidence)
            total_weight += avatar_evidence.weight

        # Normalize to 0-100 scale
        # Max possible weight: 30 (username) + 10 (platform) + 10 (completeness) +
        #                      5 (display) + 5 (bio) + 5 (avatar) = 65
        max_possible = 65.0
        confidence = min(100.0, (total_weight / max_possible) * 100)

        # Ensure minimum threshold based on having found the account
        confidence = max(confidence, 15.0)  # At least 15% if account exists

        profile.confidence_score = round(confidence, 1)
        profile.confidence_level = ConfidenceLevel.from_score(confidence)
        profile.evidence = evidence_list

        return profile

    def score_cross_platform(
        self, profiles: List[ProfileData], target_username: str
    ) -> List[ProfileData]:
        """
        Cross-platform scoring: compare profiles against each other
        to find additional evidence of identity correlation.
        """
        if len(profiles) < 2:
            return profiles

        for i, profile_a in enumerate(profiles):
            for j, profile_b in enumerate(profiles):
                if i >= j:
                    continue

                cross_evidence = []

                # Compare display names
                if profile_a.display_name and profile_b.display_name:
                    name_ratio = difflib.SequenceMatcher(
                        None,
                        profile_a.display_name.lower(),
                        profile_b.display_name.lower(),
                    ).ratio()
                    if name_ratio >= 0.8:
                        ev = Evidence(
                            evidence_type=EvidenceType.SAME_DISPLAY_NAME,
                            description=(
                                f"Similar display name across {profile_a.site_name} "
                                f"and {profile_b.site_name}: "
                                f"'{profile_a.display_name}' ↔ '{profile_b.display_name}' "
                                f"({name_ratio:.0%} match)"
                            ),
                            weight=EVIDENCE_WEIGHTS["same_display_name"] * name_ratio,
                            source_site=profile_a.site_name,
                            target_site=profile_b.site_name,
                        )
                        cross_evidence.append(ev)

                # Compare bios
                if (
                    profile_a.bio
                    and profile_b.bio
                    and len(profile_a.bio) > 20
                    and len(profile_b.bio) > 20
                ):
                    bio_ratio = difflib.SequenceMatcher(
                        None,
                        profile_a.bio.lower(),
                        profile_b.bio.lower(),
                    ).ratio()
                    if bio_ratio >= 0.6:
                        ev = Evidence(
                            evidence_type=EvidenceType.SIMILAR_BIO,
                            description=(
                                f"Similar bio across {profile_a.site_name} "
                                f"and {profile_b.site_name} "
                                f"({bio_ratio:.0%} match)"
                            ),
                            weight=EVIDENCE_WEIGHTS["similar_bio"] * bio_ratio,
                            source_site=profile_a.site_name,
                            target_site=profile_b.site_name,
                        )
                        cross_evidence.append(ev)

                # Compare avatars (URL-based)
                if profile_a.avatar_url and profile_b.avatar_url:
                    if profile_a.avatar_url == profile_b.avatar_url:
                        ev = Evidence(
                            evidence_type=EvidenceType.SAME_AVATAR,
                            description=(
                                f"Same profile image across {profile_a.site_name} "
                                f"and {profile_b.site_name}"
                            ),
                            weight=EVIDENCE_WEIGHTS["same_avatar"],
                            source_site=profile_a.site_name,
                            target_site=profile_b.site_name,
                        )
                        cross_evidence.append(ev)

                # Add cross-platform evidence to both profiles
                for ev in cross_evidence:
                    profile_a.evidence.append(ev)
                    profile_b.evidence.append(ev)
                    bonus = ev.weight * 0.3  # 30% of evidence weight as bonus
                    profile_a.confidence_score = min(
                        100, profile_a.confidence_score + bonus
                    )
                    profile_b.confidence_score = min(
                        100, profile_b.confidence_score + bonus
                    )

        # Recalculate confidence levels
        for profile in profiles:
            profile.confidence_level = ConfidenceLevel.from_score(
                profile.confidence_score
            )

        return profiles

    def _evaluate_username(
        self, found_username: str, target_username: str, site_name: str
    ) -> Evidence:
        """Evaluate username match strength."""
        target_lower = target_username.lower()
        found_lower = found_username.lower()

        if found_lower == target_lower:
            return Evidence(
                evidence_type=EvidenceType.EXACT_USERNAME,
                description=f"Exact username match on {site_name}",
                weight=EVIDENCE_WEIGHTS["exact_username"],
                source_site=site_name,
            )
        else:
            ratio = difflib.SequenceMatcher(None, found_lower, target_lower).ratio()
            if ratio >= 0.8:
                return Evidence(
                    evidence_type=EvidenceType.SIMILAR_USERNAME,
                    description=(
                        f"Similar username on {site_name}: "
                        f"'{found_username}' ({ratio:.0%} match)"
                    ),
                    weight=EVIDENCE_WEIGHTS["similar_username"] * ratio,
                    source_site=site_name,
                )
        return Evidence(
            evidence_type=EvidenceType.EXACT_USERNAME,
            description=f"Username found on {site_name}",
            weight=EVIDENCE_WEIGHTS["exact_username"] * 0.5,
            source_site=site_name,
        )

    def _evaluate_platform(self, site_name: str) -> Evidence:
        """Evaluate platform reliability."""
        if site_name in TIER_1_PLATFORMS:
            return Evidence(
                evidence_type=EvidenceType.PLATFORM_RELIABILITY,
                description=f"{site_name} is a Tier 1 (highly reliable) platform",
                weight=10.0,
                source_site=site_name,
            )
        elif site_name in TIER_2_PLATFORMS:
            return Evidence(
                evidence_type=EvidenceType.PLATFORM_RELIABILITY,
                description=f"{site_name} is a Tier 2 (reliable) platform",
                weight=7.0,
                source_site=site_name,
            )
        else:
            return Evidence(
                evidence_type=EvidenceType.PLATFORM_RELIABILITY,
                description=f"{site_name}: standard platform",
                weight=3.0,
                source_site=site_name,
            )

    def _evaluate_completeness(self, profile: ProfileData) -> Evidence:
        """Evaluate how complete the profile data is."""
        fields = [
            profile.display_name,
            profile.bio,
            profile.avatar_url,
            profile.location,
            profile.website,
        ]
        filled = sum(1 for f in fields if f)
        total = len(fields)

        if filled >= 3:
            return Evidence(
                evidence_type=EvidenceType.ACTIVITY_PATTERN,
                description=f"Rich profile data ({filled}/{total} fields populated)",
                weight=10.0,
                source_site=profile.site_name,
            )
        elif filled >= 1:
            return Evidence(
                evidence_type=EvidenceType.ACTIVITY_PATTERN,
                description=f"Partial profile data ({filled}/{total} fields populated)",
                weight=5.0,
                source_site=profile.site_name,
            )
        return Evidence(
            evidence_type=EvidenceType.ACTIVITY_PATTERN,
            description="Minimal profile data available",
            weight=2.0,
            source_site=profile.site_name,
        )
