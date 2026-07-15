"""
DR3 Intelligence Platform — Evidence Model

The Evidence model is the atomic unit of intelligence in the platform.
Every conclusion, every confidence score, every relationship in the
graph is backed by one or more Evidence objects.

Design philosophy (inspired by Palantir's provenance model):
  - Every fact has a source
  - Every source has a reliability rating
  - Every conclusion is traceable to its evidence
  - Absence of evidence IS evidence (MISSING category)
  - Contradictory evidence is explicitly tracked (CONFLICTING category)
  - No conclusion should ever be made without explainable justification

An investigator should be able to:
  1. See a confidence score
  2. Click "Why?"
  3. See every piece of evidence that contributed
  4. For each piece, see the quality, source, and reasoning
  5. See what evidence is MISSING or CONTRADICTING
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .enums import (
    CollectionMethod,
    EvidenceCategory,
    EvidenceQuality,
    EvidenceType,
)


@dataclass
class Evidence:
    """
    A single piece of evidence in an investigation.

    This is the fundamental building block of the intelligence system.
    Everything — confidence scores, relationship strength, identity
    profiles — is derived from Evidence objects.

    Attributes:
        id: Unique identifier for this evidence.
        evidence_type: What kind of evidence (SAME_EMAIL, DIRECT_LINK, etc.).
        category: Direction (POSITIVE, NEGATIVE, CONFLICTING, MISSING).
        quality: How reliable is this evidence (DEFINITIVE → CIRCUMSTANTIAL).

        source_platform: Platform where this evidence was found.
        source_entity_id: Entity that produced this evidence.
        target_platform: Platform of the related entity (for cross-platform evidence).
        target_entity_id: Entity this evidence points to.

        weight: Computed weight (evidence_max_weight × quality_multiplier).
        raw_weight: Maximum possible weight for this evidence type.
        reliability: Source reliability score (0-100).

        description: Human-readable description of what was found.
        explanation: Human-readable explanation of WHY this weight was assigned.
        raw_data: The actual data that constitutes this evidence.

        collection_method: How this evidence was collected.
        discovered_at: When this evidence was discovered.
        verified: Whether this evidence has been cross-verified.
        verification_method: How it was verified (if applicable).
    """
    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    # Classification
    evidence_type: EvidenceType = EvidenceType.EXACT_USERNAME
    category: EvidenceCategory = EvidenceCategory.POSITIVE
    quality: EvidenceQuality = EvidenceQuality.MODERATE

    # Source & Target
    source_platform: str = ""
    source_entity_id: str = ""
    target_platform: str = ""
    target_entity_id: str = ""

    # Scoring
    weight: float = 0.0         # Computed: raw_weight × quality_multiplier
    raw_weight: float = 0.0     # Max possible weight for this type
    reliability: float = 50.0   # Source reliability (0-100)

    # Human-readable
    description: str = ""
    explanation: str = ""

    # Data
    raw_data: Dict[str, Any] = field(default_factory=dict)

    # Provenance
    collection_method: CollectionMethod = CollectionMethod.PROFILE_SCRAPE
    discovered_at: datetime = field(default_factory=datetime.now)
    verified: bool = False
    verification_method: str = ""

    @property
    def is_positive(self) -> bool:
        return self.category == EvidenceCategory.POSITIVE

    @property
    def is_negative(self) -> bool:
        return self.category == EvidenceCategory.NEGATIVE

    @property
    def is_conflicting(self) -> bool:
        return self.category == EvidenceCategory.CONFLICTING

    @property
    def is_actionable(self) -> bool:
        """Evidence is actionable if it can meaningfully affect confidence."""
        return self.quality in (
            EvidenceQuality.DEFINITIVE,
            EvidenceQuality.STRONG,
            EvidenceQuality.MODERATE,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-safe dictionary."""
        return {
            "id": self.id,
            "evidence_type": self.evidence_type.value,
            "category": self.category.value,
            "quality": self.quality.value,
            "source_platform": self.source_platform,
            "source_entity_id": self.source_entity_id,
            "target_platform": self.target_platform,
            "target_entity_id": self.target_entity_id,
            "weight": round(self.weight, 2),
            "raw_weight": round(self.raw_weight, 2),
            "reliability": round(self.reliability, 2),
            "description": self.description,
            "explanation": self.explanation,
            "collection_method": self.collection_method.value,
            "discovered_at": self.discovered_at.isoformat(),
            "verified": self.verified,
        }


@dataclass
class EvidenceChain:
    """
    An ordered collection of evidence supporting a specific conclusion.

    For example, the conclusion "GitHub/dr3 and Twitter/dr3iq are the
    same person" would have an EvidenceChain containing:
      - POSITIVE: Same display name (Strong)
      - POSITIVE: Similar username (Moderate)
      - POSITIVE: GitHub links to Twitter (Definitive)
      - NEGATIVE: Different location (Weak)
      - MISSING: No bio on Twitter to compare

    The chain provides:
      - Net confidence: How confident are we in this conclusion?
      - Explanation: Why this confidence level?
      - Transparency: What evidence supports AND contradicts?
    """
    conclusion: str = ""
    evidence: List[Evidence] = field(default_factory=list)

    @property
    def positive_evidence(self) -> List[Evidence]:
        return [e for e in self.evidence if e.is_positive]

    @property
    def negative_evidence(self) -> List[Evidence]:
        return [e for e in self.evidence if e.is_negative]

    @property
    def conflicting_evidence(self) -> List[Evidence]:
        return [e for e in self.evidence if e.is_conflicting]

    @property
    def missing_evidence(self) -> List[Evidence]:
        return [e for e in self.evidence
                if e.category == EvidenceCategory.MISSING]

    @property
    def actionable_evidence(self) -> List[Evidence]:
        """Only evidence with quality >= MODERATE."""
        return [e for e in self.evidence if e.is_actionable]

    @property
    def positive_weight(self) -> float:
        return sum(e.weight for e in self.positive_evidence)

    @property
    def negative_weight(self) -> float:
        return sum(abs(e.weight) for e in self.negative_evidence)

    @property
    def has_definitive(self) -> bool:
        return any(
            e.quality == EvidenceQuality.DEFINITIVE and e.is_positive
            for e in self.evidence
        )

    @property
    def strong_count(self) -> int:
        return sum(
            1 for e in self.evidence
            if e.quality == EvidenceQuality.STRONG and e.is_positive
        )

    @property
    def net_weight(self) -> float:
        """Net evidence weight (positive minus negative penalties)."""
        return self.positive_weight - (self.negative_weight * 0.7)

    def add(self, evidence: Evidence) -> None:
        self.evidence.append(evidence)

    def build_explanation(self) -> str:
        """Generate human-readable explanation of the evidence chain."""
        parts = []

        if self.has_definitive:
            def_ev = [e for e in self.positive_evidence
                      if e.quality == EvidenceQuality.DEFINITIVE]
            parts.append(
                f"تم التأكيد بدليل قاطع: {def_ev[0].description}"
            )

        strong = [e for e in self.positive_evidence
                  if e.quality == EvidenceQuality.STRONG]
        if strong:
            parts.append(
                f"{len(strong)} دليل قوي: " +
                "; ".join(e.description for e in strong[:3])
            )

        moderate = [e for e in self.positive_evidence
                    if e.quality == EvidenceQuality.MODERATE]
        if moderate:
            parts.append(
                f"{len(moderate)} دليل متوسط: " +
                "; ".join(e.description for e in moderate[:3])
            )

        if self.negative_evidence:
            parts.append(
                f"⚠ {len(self.negative_evidence)} دليل سلبي: " +
                "; ".join(e.description for e in self.negative_evidence[:2])
            )

        if self.missing_evidence:
            parts.append(
                f"🔍 {len(self.missing_evidence)} دليل مفقود: " +
                "; ".join(e.description for e in self.missing_evidence[:2])
            )

        return " | ".join(parts) if parts else "لا توجد أدلة كافية"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conclusion": self.conclusion,
            "evidence_count": len(self.evidence),
            "positive_count": len(self.positive_evidence),
            "negative_count": len(self.negative_evidence),
            "conflicting_count": len(self.conflicting_evidence),
            "missing_count": len(self.missing_evidence),
            "net_weight": round(self.net_weight, 2),
            "has_definitive": self.has_definitive,
            "explanation": self.build_explanation(),
            "evidence": [e.to_dict() for e in self.evidence],
        }
