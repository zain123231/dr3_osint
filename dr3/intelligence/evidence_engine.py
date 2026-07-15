"""
DR3 Intelligence Platform — Evidence Engine

The Evidence Engine is the JUDICIAL SYSTEM of the platform.
It evaluates raw data and produces classified, weighted, explained evidence.

Core responsibilities:
  1. Evaluate collection results → produce Evidence objects
  2. Compare two nodes → produce cross-platform evidence
  3. Classify evidence quality (DEFINITIVE → CIRCUMSTANTIAL)
  4. Detect negative and conflicting evidence
  5. Detect MISSING evidence (expected but absent)
  6. Ensure every weight is explainable

Design principle: NO evidence is created without an explanation.
If the system cannot explain WHY something is evidence, it is not evidence.
"""

import difflib
import logging
from typing import List, Optional, Tuple

from ..core.constants import (
    AVATAR_HASH_EXACT_THRESHOLD,
    AVATAR_HASH_SIMILAR_THRESHOLD,
    BIO_SIMILARITY_THRESHOLD,
    EVIDENCE_MAX_WEIGHTS,
    NAME_SIMILARITY_THRESHOLD,
    QUALITY_MULTIPLIERS,
    SEED_PRIORITY_PLATFORMS,
    TIER_1_PLATFORMS,
    TIER_2_PLATFORMS,
    USERNAME_SIMILARITY_THRESHOLD,
)
from ..core.enums import (
    CollectionMethod,
    EvidenceCategory,
    EvidenceQuality,
    EvidenceType,
    PlatformTier,
)
from ..core.evidence import Evidence, EvidenceChain
from ..core.models import CollectionResult, IdentityNode

logger = logging.getLogger("dr3.evidence_engine")


class EvidenceEngine:
    """
    Evaluates raw data and produces intelligence-grade evidence.

    Every method returns Evidence objects with:
      - Type, category, quality
      - Computed weight (max_weight × quality_multiplier)
      - Human-readable description and explanation
      - Source provenance
    """

    def evaluate_collection(
        self,
        result: CollectionResult,
        target_username: str,
    ) -> List[Evidence]:
        """
        Evaluate a single collection result against the search target.
        Produces evidence for a NEW node (not cross-platform).

        This is called during seed resolution and initial checks.
        """
        evidence_list = []

        if not result.is_found:
            return evidence_list

        # ── 1. Username Match ──
        username_ev = self._evaluate_username_match(
            found_username=result.username or target_username,
            target_username=target_username,
            platform=result.platform,
            collection_method=result.collection_method,
        )
        if username_ev:
            evidence_list.append(username_ev)

        # ── 2. Platform Reliability ──
        platform_ev = self._evaluate_platform_reliability(
            platform=result.platform,
            platform_tier=result.platform_tier,
            collection_method=result.collection_method,
        )
        evidence_list.append(platform_ev)

        # ── 3. Profile Completeness ──
        completeness_ev = self._evaluate_profile_completeness(
            result=result,
        )
        evidence_list.append(completeness_ev)

        # ── 4. Collection Method Quality ──
        if result.collection_method == CollectionMethod.STATUS_CODE:
            # Status code only — flag as circumstantial
            evidence_list.append(Evidence(
                evidence_type=EvidenceType.PLATFORM_RELIABILITY,
                category=EvidenceCategory.CIRCUMSTANTIAL,
                quality=EvidenceQuality.CIRCUMSTANTIAL,
                weight=self._compute_weight("platform_reliability", EvidenceQuality.CIRCUMSTANTIAL),
                raw_weight=EVIDENCE_MAX_WEIGHTS["platform_reliability"],
                source_platform=result.platform,
                description=f"النتيجة تعتمد على status code فقط — لا بيانات هوية مستخرجة",
                explanation=(
                    "HTTP status code 200 لا يثبت وجود حساب حقيقي. "
                    "كثير من المواقع ترجع 200 لصفحات تسجيل أو صفحات عامة."
                ),
                collection_method=result.collection_method,
            ))

        return evidence_list

    def evaluate_cross_platform(
        self,
        node_a: IdentityNode,
        node_b: IdentityNode,
    ) -> EvidenceChain:
        """
        Compare two nodes and produce a cross-platform evidence chain.

        This is the CORE intelligence function — it determines
        whether two accounts belong to the same person.

        Returns an EvidenceChain with positive, negative, AND missing evidence.
        """
        chain = EvidenceChain(
            conclusion=f"هل {node_a.label} و {node_b.label} نفس الشخص؟"
        )

        # ── Positive Evidence ──

        # 1. Display Name comparison
        if node_a.display_name and node_b.display_name:
            name_ev = self._compare_names(
                node_a.display_name, node_b.display_name,
                node_a.platform, node_b.platform,
                node_a.id, node_b.id,
            )
            chain.add(name_ev)
        elif node_a.display_name or node_b.display_name:
            # One has a name, the other doesn't — missing evidence
            chain.add(Evidence(
                evidence_type=EvidenceType.SAME_DISPLAY_NAME,
                category=EvidenceCategory.MISSING,
                quality=EvidenceQuality.WEAK,
                weight=0,
                source_platform=node_a.platform,
                target_platform=node_b.platform,
                source_entity_id=node_a.id,
                target_entity_id=node_b.id,
                description=(
                    f"اسم العرض غير متاح على {node_b.platform if node_a.display_name else node_a.platform} "
                    f"— لا يمكن مقارنة الأسماء"
                ),
                explanation="دليل مفقود: لو كان نفس الشخص، توقعنا وجود اسم عرض للمقارنة",
            ))

        # 2. Bio comparison
        if node_a.bio and node_b.bio and len(node_a.bio) > 15 and len(node_b.bio) > 15:
            bio_ev = self._compare_bios(
                node_a.bio, node_b.bio,
                node_a.platform, node_b.platform,
                node_a.id, node_b.id,
            )
            chain.add(bio_ev)

        # 3. Avatar comparison
        if node_a.avatar_hash and node_b.avatar_hash:
            avatar_ev = self._compare_avatars(
                node_a.avatar_hash, node_b.avatar_hash,
                node_a.platform, node_b.platform,
                node_a.id, node_b.id,
            )
            chain.add(avatar_ev)

        # 4. Website comparison
        if node_a.website and node_b.website:
            if self._normalize_url(node_a.website) == self._normalize_url(node_b.website):
                chain.add(Evidence(
                    evidence_type=EvidenceType.SAME_WEBSITE,
                    category=EvidenceCategory.POSITIVE,
                    quality=EvidenceQuality.STRONG,
                    weight=self._compute_weight("same_website", EvidenceQuality.STRONG),
                    raw_weight=EVIDENCE_MAX_WEIGHTS["same_website"],
                    source_platform=node_a.platform,
                    target_platform=node_b.platform,
                    source_entity_id=node_a.id,
                    target_entity_id=node_b.id,
                    description=f"نفس الموقع الإلكتروني على {node_a.platform} و {node_b.platform}: {node_a.website}",
                    explanation="مشاركة نفس الموقع الشخصي دليل قوي — المواقع الشخصية فريدة",
                ))

        # 5. Email comparison
        if node_a.email and node_b.email:
            if node_a.email.lower() == node_b.email.lower():
                chain.add(Evidence(
                    evidence_type=EvidenceType.SAME_EMAIL,
                    category=EvidenceCategory.POSITIVE,
                    quality=EvidenceQuality.DEFINITIVE,
                    weight=self._compute_weight("same_email", EvidenceQuality.DEFINITIVE),
                    raw_weight=EVIDENCE_MAX_WEIGHTS["same_email"],
                    source_platform=node_a.platform,
                    target_platform=node_b.platform,
                    source_entity_id=node_a.id,
                    target_entity_id=node_b.id,
                    description=f"نفس الإيميل على {node_a.platform} و {node_b.platform}: {node_a.email}",
                    explanation="نفس عنوان البريد الإلكتروني = دليل قاطع على نفس الهوية",
                ))

        # 6. Location comparison
        if node_a.location and node_b.location:
            loc_ev = self._compare_locations(
                node_a.location, node_b.location,
                node_a.platform, node_b.platform,
                node_a.id, node_b.id,
            )
            chain.add(loc_ev)

        # 7. Username comparison (cross-platform)
        if node_a.username and node_b.username:
            uname_ev = self._evaluate_username_match(
                found_username=node_b.username,
                target_username=node_a.username,
                platform=node_b.platform,
                collection_method=node_b.collection_method,
                source_platform=node_a.platform,
                source_entity_id=node_a.id,
                target_entity_id=node_b.id,
            )
            if uname_ev:
                chain.add(uname_ev)

        return chain

    def detect_direct_links(
        self,
        source_node: IdentityNode,
        all_nodes: List[IdentityNode],
    ) -> List[Evidence]:
        """
        Detect if a node's profile links directly to other known nodes.

        Direct links are DEFINITIVE evidence — the highest quality possible.
        Example: GitHub profile contains a link to their Twitter.
        """
        direct_evidence = []
        source_links = []

        # Collect all links from source node
        if source_node.website:
            source_links.append(source_node.website)
        source_links.extend(source_node.external_links)

        if not source_links:
            return direct_evidence

        for target in all_nodes:
            if target.id == source_node.id:
                continue
            if not target.profile_url:
                continue

            target_url_normalized = self._normalize_url(target.profile_url)

            for link in source_links:
                link_normalized = self._normalize_url(link)
                if target_url_normalized and link_normalized and (
                    target_url_normalized in link_normalized or
                    link_normalized in target_url_normalized
                ):
                    direct_evidence.append(Evidence(
                        evidence_type=EvidenceType.DIRECT_LINK,
                        category=EvidenceCategory.POSITIVE,
                        quality=EvidenceQuality.DEFINITIVE,
                        weight=self._compute_weight("direct_link", EvidenceQuality.DEFINITIVE),
                        raw_weight=EVIDENCE_MAX_WEIGHTS["direct_link"],
                        source_platform=source_node.platform,
                        target_platform=target.platform,
                        source_entity_id=source_node.id,
                        target_entity_id=target.id,
                        description=(
                            f"رابط مباشر: {source_node.platform}/@{source_node.username} "
                            f"يحتوي رابط لـ {target.platform}/@{target.username}"
                        ),
                        explanation=(
                            "رابط مباشر من حساب لآخر = دليل قاطع. "
                            "فقط صاحب الحساب يمكنه إضافة روابط في ملفه الشخصي."
                        ),
                        raw_data={"link": link, "target_url": target.profile_url},
                    ))
                    break  # One direct link per target is enough

        return direct_evidence

    # ══════════════════════════════════════════════════════════
    # INTERNAL EVALUATION METHODS
    # ══════════════════════════════════════════════════════════

    def _evaluate_username_match(
        self,
        found_username: str,
        target_username: str,
        platform: str,
        collection_method: CollectionMethod,
        source_platform: str = "",
        source_entity_id: str = "",
        target_entity_id: str = "",
    ) -> Optional[Evidence]:
        """Evaluate how well a found username matches the target."""
        target_lower = target_username.lower()
        found_lower = found_username.lower()

        if found_lower == target_lower:
            # Exact match quality depends on collection method
            if collection_method in (CollectionMethod.DIRECT_API, CollectionMethod.PROFILE_SCRAPE):
                quality = EvidenceQuality.MODERATE
            else:
                quality = EvidenceQuality.WEAK

            return Evidence(
                evidence_type=EvidenceType.EXACT_USERNAME,
                category=EvidenceCategory.POSITIVE,
                quality=quality,
                weight=self._compute_weight("exact_username", quality),
                raw_weight=EVIDENCE_MAX_WEIGHTS["exact_username"],
                source_platform=source_platform or platform,
                target_platform=platform,
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                description=f"تطابق تام لاسم المستخدم '{found_username}' على {platform}",
                explanation=(
                    f"اسم المستخدم مطابق تماماً. "
                    f"الجودة {'متوسطة' if quality == EvidenceQuality.MODERATE else 'ضعيفة'} "
                    f"لأن أسماء المستخدمين الشائعة قد تكون لأشخاص مختلفين."
                ),
                collection_method=collection_method,
            )
        else:
            ratio = difflib.SequenceMatcher(None, found_lower, target_lower).ratio()
            if ratio >= USERNAME_SIMILARITY_THRESHOLD:
                return Evidence(
                    evidence_type=EvidenceType.SIMILAR_USERNAME,
                    category=EvidenceCategory.POSITIVE,
                    quality=EvidenceQuality.WEAK,
                    weight=self._compute_weight("similar_username", EvidenceQuality.WEAK) * ratio,
                    raw_weight=EVIDENCE_MAX_WEIGHTS["similar_username"],
                    source_platform=source_platform or platform,
                    target_platform=platform,
                    source_entity_id=source_entity_id,
                    target_entity_id=target_entity_id,
                    description=(
                        f"اسم مستخدم متشابه: '{found_username}' ↔ '{target_username}' "
                        f"({ratio:.0%} تطابق) على {platform}"
                    ),
                    explanation=(
                        "أسماء مستخدمين متشابهة لكنها ليست متطابقة. "
                        "دليل ضعيف وحده — يحتاج أدلة إضافية."
                    ),
                    collection_method=collection_method,
                )
        return None

    def _evaluate_platform_reliability(
        self,
        platform: str,
        platform_tier: PlatformTier,
        collection_method: CollectionMethod,
    ) -> Evidence:
        """Evaluate how reliable the source platform is."""
        if platform in TIER_1_PLATFORMS or platform_tier == PlatformTier.TIER_1:
            quality = EvidenceQuality.MODERATE
            weight_key = "platform_reliability"
            description = f"{platform} منصة من المستوى الأول — بيانات موثوقة"
        elif platform in TIER_2_PLATFORMS or platform_tier == PlatformTier.TIER_2:
            quality = EvidenceQuality.WEAK
            weight_key = "platform_reliability"
            description = f"{platform} منصة من المستوى الثاني"
        else:
            quality = EvidenceQuality.CIRCUMSTANTIAL
            weight_key = "platform_reliability"
            description = f"{platform} منصة غير مصنفة"

        return Evidence(
            evidence_type=EvidenceType.PLATFORM_RELIABILITY,
            category=EvidenceCategory.POSITIVE,
            quality=quality,
            weight=self._compute_weight(weight_key, quality),
            raw_weight=EVIDENCE_MAX_WEIGHTS[weight_key],
            source_platform=platform,
            description=description,
            explanation=f"المنصات ذات المستوى الأعلى توفر بيانات أكثر موثوقية",
            collection_method=collection_method,
        )

    def _evaluate_profile_completeness(self, result: CollectionResult) -> Evidence:
        """Evaluate how complete the profile data is."""
        richness = result.identity_richness

        if richness >= 5:
            quality = EvidenceQuality.MODERATE
            description = f"ملف شخصي غني ({richness}/8 حقول)"
        elif richness >= 3:
            quality = EvidenceQuality.WEAK
            description = f"ملف شخصي متوسط ({richness}/8 حقول)"
        else:
            quality = EvidenceQuality.CIRCUMSTANTIAL
            description = f"ملف شخصي فقير ({richness}/8 حقول)"

        return Evidence(
            evidence_type=EvidenceType.PROFILE_COMPLETENESS,
            category=EvidenceCategory.POSITIVE,
            quality=quality,
            weight=self._compute_weight("profile_completeness", quality),
            raw_weight=EVIDENCE_MAX_WEIGHTS["profile_completeness"],
            source_platform=result.platform,
            description=description,
            explanation="الملفات الشخصية الغنية بالمعلومات تشير لحساب حقيقي نشط",
            collection_method=result.collection_method,
        )

    def _compare_names(
        self,
        name_a: str, name_b: str,
        platform_a: str, platform_b: str,
        id_a: str, id_b: str,
    ) -> Evidence:
        """Compare display names between two nodes."""
        ratio = difflib.SequenceMatcher(
            None, name_a.lower().strip(), name_b.lower().strip()
        ).ratio()

        if ratio >= 0.95:
            return Evidence(
                evidence_type=EvidenceType.SAME_DISPLAY_NAME,
                category=EvidenceCategory.POSITIVE,
                quality=EvidenceQuality.STRONG,
                weight=self._compute_weight("same_display_name", EvidenceQuality.STRONG),
                raw_weight=EVIDENCE_MAX_WEIGHTS["same_display_name"],
                source_platform=platform_a,
                target_platform=platform_b,
                source_entity_id=id_a,
                target_entity_id=id_b,
                description=f"اسم عرض متطابق: '{name_a}' ↔ '{name_b}' ({ratio:.0%})",
                explanation="الأسماء الكاملة المتطابقة دليل قوي — خاصة إذا كانت غير شائعة",
                raw_data={"name_a": name_a, "name_b": name_b, "similarity": ratio},
            )
        elif ratio >= NAME_SIMILARITY_THRESHOLD:
            return Evidence(
                evidence_type=EvidenceType.SAME_DISPLAY_NAME,
                category=EvidenceCategory.POSITIVE,
                quality=EvidenceQuality.MODERATE,
                weight=self._compute_weight("same_display_name", EvidenceQuality.MODERATE) * ratio,
                raw_weight=EVIDENCE_MAX_WEIGHTS["same_display_name"],
                source_platform=platform_a,
                target_platform=platform_b,
                source_entity_id=id_a,
                target_entity_id=id_b,
                description=f"اسم عرض متشابه: '{name_a}' ↔ '{name_b}' ({ratio:.0%})",
                explanation="أسماء متشابهة لكن غير متطابقة — دليل متوسط",
                raw_data={"name_a": name_a, "name_b": name_b, "similarity": ratio},
            )
        else:
            # Different names — negative evidence
            return Evidence(
                evidence_type=EvidenceType.DIFFERENT_NAME,
                category=EvidenceCategory.NEGATIVE,
                quality=EvidenceQuality.MODERATE,
                weight=self._compute_weight("different_name", EvidenceQuality.MODERATE),
                raw_weight=EVIDENCE_MAX_WEIGHTS["different_name"],
                source_platform=platform_a,
                target_platform=platform_b,
                source_entity_id=id_a,
                target_entity_id=id_b,
                description=f"أسماء عرض مختلفة: '{name_a}' ≠ '{name_b}' ({ratio:.0%})",
                explanation="أسماء مختلفة تماماً تُضعف فرضية أن الحسابات لنفس الشخص",
                raw_data={"name_a": name_a, "name_b": name_b, "similarity": ratio},
            )

    def _compare_bios(
        self,
        bio_a: str, bio_b: str,
        platform_a: str, platform_b: str,
        id_a: str, id_b: str,
    ) -> Evidence:
        """Compare biographies between two nodes."""
        ratio = difflib.SequenceMatcher(
            None, bio_a.lower().strip(), bio_b.lower().strip()
        ).ratio()

        if ratio >= 0.80:
            return Evidence(
                evidence_type=EvidenceType.SAME_BIO,
                category=EvidenceCategory.POSITIVE,
                quality=EvidenceQuality.STRONG,
                weight=self._compute_weight("same_bio", EvidenceQuality.STRONG),
                raw_weight=EVIDENCE_MAX_WEIGHTS["same_bio"],
                source_platform=platform_a,
                target_platform=platform_b,
                source_entity_id=id_a,
                target_entity_id=id_b,
                description=f"سيرة ذاتية متطابقة بين {platform_a} و {platform_b} ({ratio:.0%})",
                explanation="نفس النص في السيرة الذاتية دليل قوي على نفس الشخص",
                raw_data={"similarity": ratio},
            )
        elif ratio >= BIO_SIMILARITY_THRESHOLD:
            return Evidence(
                evidence_type=EvidenceType.SIMILAR_BIO,
                category=EvidenceCategory.POSITIVE,
                quality=EvidenceQuality.MODERATE,
                weight=self._compute_weight("similar_bio", EvidenceQuality.MODERATE) * ratio,
                raw_weight=EVIDENCE_MAX_WEIGHTS["similar_bio"],
                source_platform=platform_a,
                target_platform=platform_b,
                source_entity_id=id_a,
                target_entity_id=id_b,
                description=f"سيرة ذاتية متشابهة بين {platform_a} و {platform_b} ({ratio:.0%})",
                explanation="نصوص متشابهة في السيرة — دليل متوسط",
                raw_data={"similarity": ratio},
            )
        else:
            return Evidence(
                evidence_type=EvidenceType.SIMILAR_BIO,
                category=EvidenceCategory.CIRCUMSTANTIAL,
                quality=EvidenceQuality.CIRCUMSTANTIAL,
                weight=0,
                source_platform=platform_a,
                target_platform=platform_b,
                source_entity_id=id_a,
                target_entity_id=id_b,
                description=f"سير ذاتية مختلفة بين {platform_a} و {platform_b} ({ratio:.0%})",
                explanation="عدم تشابه السيرة لا ينفي بالضرورة — الناس تكتب سير مختلفة",
            )

    def _compare_avatars(
        self,
        hash_a: str, hash_b: str,
        platform_a: str, platform_b: str,
        id_a: str, id_b: str,
    ) -> Evidence:
        """Compare avatar perceptual hashes."""
        try:
            distance = self._hamming_distance(hash_a, hash_b)
        except (ValueError, TypeError):
            return Evidence(
                evidence_type=EvidenceType.SIMILAR_AVATAR,
                category=EvidenceCategory.CIRCUMSTANTIAL,
                quality=EvidenceQuality.CIRCUMSTANTIAL,
                weight=0,
                source_platform=platform_a,
                target_platform=platform_b,
                source_entity_id=id_a,
                target_entity_id=id_b,
                description="لا يمكن مقارنة صور الملفات الشخصية (hash غير صالح)",
                explanation="فشل تقني في المقارنة — لا تأثير على الثقة",
            )

        if distance <= AVATAR_HASH_EXACT_THRESHOLD:
            return Evidence(
                evidence_type=EvidenceType.SAME_AVATAR,
                category=EvidenceCategory.POSITIVE,
                quality=EvidenceQuality.STRONG,
                weight=self._compute_weight("same_avatar", EvidenceQuality.STRONG),
                raw_weight=EVIDENCE_MAX_WEIGHTS["same_avatar"],
                source_platform=platform_a,
                target_platform=platform_b,
                source_entity_id=id_a,
                target_entity_id=id_b,
                description=f"صورة ملف شخصي متطابقة بين {platform_a} و {platform_b} (distance={distance})",
                explanation="نفس الصورة بالضبط — دليل قوي (يُعزز بأدلة أخرى)",
                raw_data={"distance": distance},
            )
        elif distance <= AVATAR_HASH_SIMILAR_THRESHOLD:
            return Evidence(
                evidence_type=EvidenceType.SIMILAR_AVATAR,
                category=EvidenceCategory.POSITIVE,
                quality=EvidenceQuality.MODERATE,
                weight=self._compute_weight("similar_avatar", EvidenceQuality.MODERATE),
                raw_weight=EVIDENCE_MAX_WEIGHTS["similar_avatar"],
                source_platform=platform_a,
                target_platform=platform_b,
                source_entity_id=id_a,
                target_entity_id=id_b,
                description=f"صورة ملف شخصي متشابهة بين {platform_a} و {platform_b} (distance={distance})",
                explanation="صور متشابهة لكن غير متطابقة — قد تكون نسخة معدلة",
                raw_data={"distance": distance},
            )
        else:
            return Evidence(
                evidence_type=EvidenceType.DIFFERENT_AVATAR,
                category=EvidenceCategory.NEGATIVE,
                quality=EvidenceQuality.WEAK,
                weight=self._compute_weight("different_avatar", EvidenceQuality.WEAK),
                raw_weight=EVIDENCE_MAX_WEIGHTS["different_avatar"],
                source_platform=platform_a,
                target_platform=platform_b,
                source_entity_id=id_a,
                target_entity_id=id_b,
                description=f"صور ملفات شخصية مختلفة بين {platform_a} و {platform_b} (distance={distance})",
                explanation="صور مختلفة — دليل سلبي ضعيف (الناس تستخدم صور مختلفة على منصات مختلفة)",
                raw_data={"distance": distance},
            )

    def _compare_locations(
        self,
        loc_a: str, loc_b: str,
        platform_a: str, platform_b: str,
        id_a: str, id_b: str,
    ) -> Evidence:
        """Compare geographic locations."""
        ratio = difflib.SequenceMatcher(
            None, loc_a.lower().strip(), loc_b.lower().strip()
        ).ratio()

        if ratio >= 0.8:
            return Evidence(
                evidence_type=EvidenceType.SAME_LOCATION,
                category=EvidenceCategory.POSITIVE,
                quality=EvidenceQuality.WEAK,  # Locations are weak evidence alone
                weight=self._compute_weight("same_location", EvidenceQuality.WEAK),
                raw_weight=EVIDENCE_MAX_WEIGHTS["same_location"],
                source_platform=platform_a,
                target_platform=platform_b,
                source_entity_id=id_a,
                target_entity_id=id_b,
                description=f"نفس الموقع الجغرافي: '{loc_a}' ↔ '{loc_b}'",
                explanation="نفس الموقع — دليل ضعيف وحده (ملايين الناس في كل مدينة)",
            )
        elif ratio < 0.3 and len(loc_a) > 3 and len(loc_b) > 3:
            return Evidence(
                evidence_type=EvidenceType.DIFFERENT_LOCATION,
                category=EvidenceCategory.NEGATIVE,
                quality=EvidenceQuality.WEAK,
                weight=self._compute_weight("different_location", EvidenceQuality.WEAK),
                raw_weight=EVIDENCE_MAX_WEIGHTS["different_location"],
                source_platform=platform_a,
                target_platform=platform_b,
                source_entity_id=id_a,
                target_entity_id=id_b,
                description=f"مواقع جغرافية مختلفة: '{loc_a}' ≠ '{loc_b}'",
                explanation="مواقع مختلفة — دليل سلبي ضعيف (الناس تنتقل أو تكتب أماكن مختلفة)",
            )
        else:
            return Evidence(
                evidence_type=EvidenceType.SAME_LOCATION,
                category=EvidenceCategory.CIRCUMSTANTIAL,
                quality=EvidenceQuality.CIRCUMSTANTIAL,
                weight=0,
                source_platform=platform_a,
                target_platform=platform_b,
                source_entity_id=id_a,
                target_entity_id=id_b,
                description=f"مواقع غير قابلة للمقارنة: '{loc_a}' ↔ '{loc_b}'",
                explanation="لا يمكن استنتاج شيء من مقارنة هذه المواقع",
            )

    # ══════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ══════════════════════════════════════════════════════════

    def _compute_weight(self, evidence_type_key: str, quality: EvidenceQuality) -> float:
        """Compute evidence weight = max_weight × quality_multiplier."""
        max_weight = EVIDENCE_MAX_WEIGHTS.get(evidence_type_key, 0)
        multiplier = QUALITY_MULTIPLIERS.get(quality.value, 0.1)
        return round(max_weight * multiplier, 2)

    def _normalize_url(self, url: str) -> str:
        """Normalize a URL for comparison."""
        url = url.lower().strip().rstrip("/")
        for prefix in ("https://www.", "http://www.", "https://", "http://"):
            if url.startswith(prefix):
                url = url[len(prefix):]
                break
        return url

    def _hamming_distance(self, hash_a: str, hash_b: str) -> int:
        """Compute Hamming distance between two hex hashes."""
        if len(hash_a) != len(hash_b):
            raise ValueError("Hash lengths differ")
        return sum(c1 != c2 for c1, c2 in zip(hash_a, hash_b))
