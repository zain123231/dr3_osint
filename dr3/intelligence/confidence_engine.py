"""
DR3 Intelligence Platform — Confidence Engine

Computes confidence scores from evidence chains.

CRITICAL DESIGN DECISIONS:

1. NO arbitrary minimum confidence.
   The old system gave 15% minimum just for finding an account.
   The new system: 0 evidence = 0 confidence. Period.

2. Confidence is evidence-quality-driven, NOT evidence-quantity-driven.
   50 weak evidence items should NOT inflate confidence.
   1 definitive evidence item SHOULD create high confidence.

3. Negative evidence actively REDUCES confidence.
   The old system ignored negative evidence entirely.

4. Every score has a complete explanation.
   An analyst can read WHY the system assigned 73%.

5. Overall investigation confidence is based on the STRONGEST
   evidence chain, not the average of all nodes.
   Average is meaningless — it's diluted by low-confidence nodes.
"""

import logging
from typing import Dict, List, Tuple

from ..core.enums import ConfidenceLevel, EvidenceQuality, EvidenceCategory
from ..core.evidence import Evidence, EvidenceChain
from ..core.models import IdentityNode, Investigation

logger = logging.getLogger("dr3.confidence_engine")


class ConfidenceEngine:
    """
    Computes explainable confidence scores from evidence.

    Input: EvidenceChain (a set of evidence for/against a conclusion)
    Output: (score: float, level: ConfidenceLevel, explanation: str)
    """

    def score_evidence_chain(
        self, chain: EvidenceChain
    ) -> Tuple[float, ConfidenceLevel, str]:
        """
        Compute confidence from an evidence chain.

        Algorithm:
          1. Check for definitive evidence → immediate high confidence
          2. Count strong evidence → base confidence
          3. Count moderate evidence → incremental boost
          4. Apply negative evidence penalties
          5. Weak/circumstantial evidence → context only, no boost
          6. Generate explanation
        """
        if not chain.evidence:
            return (0.0, ConfidenceLevel.UNSUBSTANTIATED, "لا توجد أدلة")

        # ── Classify evidence by quality and category ──
        positive = chain.positive_evidence
        negative = chain.negative_evidence
        conflicting = chain.conflicting_evidence
        missing = chain.missing_evidence

        definitive = [
            e for e in positive
            if e.quality == EvidenceQuality.DEFINITIVE
        ]
        strong = [
            e for e in positive
            if e.quality == EvidenceQuality.STRONG
        ]
        moderate = [
            e for e in positive
            if e.quality == EvidenceQuality.MODERATE
        ]
        weak = [
            e for e in positive
            if e.quality in (EvidenceQuality.WEAK, EvidenceQuality.CIRCUMSTANTIAL)
        ]

        # ── Step 1: Base confidence from evidence quality ──
        if definitive:
            base = 92.0
            base_reason = f"دليل قاطع: {definitive[0].description}"
        elif len(strong) >= 3:
            base = 80.0
            base_reason = f"{len(strong)} أدلة قوية تدعم الاستنتاج"
        elif len(strong) == 2:
            base = 72.0
            base_reason = f"دليلين قويين يدعمان الاستنتاج"
        elif len(strong) == 1:
            base = 58.0
            base_reason = f"دليل قوي واحد: {strong[0].description}"
        elif len(moderate) >= 3:
            base = 52.0
            base_reason = f"{len(moderate)} أدلة متوسطة"
        elif len(moderate) == 2:
            base = 42.0
            base_reason = f"دليلين متوسطين"
        elif len(moderate) == 1:
            base = 30.0
            base_reason = f"دليل متوسط واحد: {moderate[0].description}"
        elif weak:
            base = 12.0
            base_reason = f"{len(weak)} أدلة ضعيفة فقط — غير كافية"
        else:
            base = 0.0
            base_reason = "لا توجد أدلة ذات معنى"

        # ── Step 2: Incremental boost from additional evidence ──
        # Strong evidence beyond the base
        if definitive and len(strong) > 0:
            base = min(base + len(strong) * 2, 98.0)
        # Moderate evidence as reinforcement (only if we have strong base)
        if base >= 50 and moderate:
            boost = min(len(moderate) * 2, 8)
            base = min(base + boost, 95.0)

        # ── Step 3: Negative evidence penalty ──
        penalty = 0.0
        penalty_reasons = []

        for neg_ev in negative:
            neg_impact = abs(neg_ev.weight) * 0.7  # 70% of negative weight
            penalty += neg_impact
            penalty_reasons.append(
                f"-{neg_impact:.0f}: {neg_ev.description}"
            )

        # Conflicting evidence adds uncertainty
        if conflicting:
            penalty += len(conflicting) * 3
            penalty_reasons.append(
                f"-{len(conflicting) * 3}: {len(conflicting)} أدلة متناقضة"
            )

        # Missing evidence reduces confidence slightly
        if missing and base > 30:
            missing_penalty = min(len(missing) * 2, 10)
            penalty += missing_penalty
            penalty_reasons.append(
                f"-{missing_penalty}: {len(missing)} أدلة مفقودة"
            )

        # ── Step 4: Final score ──
        final = max(0.0, min(100.0, base - penalty))
        level = ConfidenceLevel.from_score(final)

        # ── Step 5: Build explanation ──
        explanation_parts = [f"الأساس: {base:.0f}% — {base_reason}"]

        if penalty > 0:
            explanation_parts.append(
                f"الخصومات: -{penalty:.0f}% — " +
                "; ".join(penalty_reasons)
            )

        explanation_parts.append(f"النتيجة: {final:.0f}% ({level.value})")

        explanation = " | ".join(explanation_parts)

        return (round(final, 1), level, explanation)

    def score_node(
        self,
        node: IdentityNode,
        evidence_chain: EvidenceChain,
    ) -> IdentityNode:
        """
        Score a single node with its evidence chain.
        Updates node.confidence, node.confidence_level, node.evidence_chain.
        """
        score, level, explanation = self.score_evidence_chain(evidence_chain)
        node.confidence = score
        node.confidence_level = level
        node.evidence_chain = evidence_chain
        node.evidence_chain.conclusion = (
            f"ثقة {score:.0f}% أن {node.label} ينتمي لنفس الهوية"
        )
        return node

    def score_investigation(
        self, investigation: Investigation
    ) -> Investigation:
        """
        Compute overall investigation confidence.

        Strategy: Overall confidence = confidence of the strongest
        connected cluster in the graph, NOT the average.

        Rationale: If we have 5 confirmed accounts and 20 weak ones,
        the average would be misleadingly low. The intelligence value
        is in the 5 confirmed accounts.
        """
        if not investigation.nodes:
            if investigation.identity_profile:
                investigation.identity_profile.overall_confidence = 0
                investigation.identity_profile.overall_confidence_level = (
                    ConfidenceLevel.UNSUBSTANTIATED
                )
            return investigation

        # Get confirmed nodes (confidence >= 70)
        confirmed = investigation.confirmed_nodes
        all_nodes = list(investigation.nodes.values())

        if confirmed:
            # Overall = average of top confirmed nodes
            top_scores = sorted(
                [n.confidence for n in confirmed], reverse=True
            )[:10]
            overall = sum(top_scores) / len(top_scores)
        else:
            # No confirmed — use best score with a cap
            best = max(n.confidence for n in all_nodes)
            overall = min(best, 49.9)  # Can't be "high" without confirmations

        overall = round(overall, 1)
        level = ConfidenceLevel.from_score(overall)

        # Build explanation
        total = len(all_nodes)
        confirmed_count = len(confirmed)
        evidence_count = len(investigation.all_evidence)

        positive_count = sum(
            1 for e in investigation.all_evidence
            if e.category == EvidenceCategory.POSITIVE
        )
        negative_count = sum(
            1 for e in investigation.all_evidence
            if e.category == EvidenceCategory.NEGATIVE
        )

        explanation = (
            f"الثقة الإجمالية {overall:.0f}% مبنية على {confirmed_count} حساب مؤكد "
            f"من أصل {total} مكتشف، مدعومة بـ {positive_count} دليل إيجابي "
            f"و {negative_count} دليل سلبي من أصل {evidence_count} دليل."
        )

        if investigation.identity_profile:
            investigation.identity_profile.overall_confidence = overall
            investigation.identity_profile.overall_confidence_level = level
            investigation.identity_profile.confidence_explanation = explanation
            investigation.identity_profile.total_evidence_count = evidence_count
            investigation.identity_profile.positive_evidence_count = positive_count
            investigation.identity_profile.negative_evidence_count = negative_count
            investigation.identity_profile.definitive_evidence_count = sum(
                1 for e in investigation.all_evidence
                if e.quality == EvidenceQuality.DEFINITIVE and e.is_positive
            )

        return investigation
