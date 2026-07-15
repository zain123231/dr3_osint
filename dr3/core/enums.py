"""
DR3 Intelligence Platform — Enumerations

Every enumeration represents a domain concept in the intelligence model.
Each value is chosen to be:
  - Semantically precise (no ambiguous catch-all values)
  - Serialization-safe (string-backed for JSON/DB)
  - Extensible (new values can be added without breaking existing data)

Design rationale: String enums over integer enums because
intelligence data must be human-readable in every storage layer
(DB, JSON exports, logs, reports). A row in the evidence table
should be understandable without a lookup table.
"""

from enum import Enum


# ═══════════════════════════════════════════════════════════════
# INVESTIGATION LIFECYCLE
# ═══════════════════════════════════════════════════════════════

class InvestigationStatus(str, Enum):
    """Lifecycle state of an investigation."""
    CREATED = "created"          # Investigation record created, not started
    RUNNING = "running"          # Actively collecting/analyzing
    PAUSED = "paused"            # Paused by user or system (resumable)
    COMPLETED = "completed"      # All phases finished successfully
    FAILED = "failed"            # Terminated due to unrecoverable error
    ARCHIVED = "archived"        # Completed and archived for long-term storage


class InvestigationPhase(str, Enum):
    """
    Ordered phases of the investigation pipeline.

    Each phase has a clear entry condition, exit condition,
    and produces specific artifacts.
    """
    SEED_RESOLUTION = "seed_resolution"      # Find the first trusted identity
    EVIDENCE_EXTRACTION = "evidence_extraction"  # Extract identity attributes from seed
    IDENTITY_EXPANSION = "identity_expansion"    # Discover related accounts
    CORRELATION = "correlation"              # Link identities with evidence chains
    VERIFICATION = "verification"            # Validate findings, eliminate false positives
    AI_ANALYSIS = "ai_analysis"              # AI-driven hypothesis generation
    PROFILE_BUILDING = "profile_building"    # Construct digital identity profile
    REPORT_GENERATION = "report_generation"  # Generate intelligence report
    IMAGE_INTELLIGENCE = "image_intelligence"  # Public image analysis & correlation


class QueryType(str, Enum):
    """Type of the initial investigation query."""
    USERNAME = "username"
    EMAIL = "email"
    FULL_NAME = "full_name"
    PHONE = "phone"
    URL = "url"
    DOMAIN = "domain"


# ═══════════════════════════════════════════════════════════════
# ENTITY MODEL
# ═══════════════════════════════════════════════════════════════

class EntityType(str, Enum):
    """
    Types of entities in the intelligence graph.

    In Palantir's ontology, everything is an entity or a relationship.
    We model the same: every discoverable thing is an entity with
    a type, properties, and connections.
    """
    IDENTITY = "identity"        # A resolved digital identity (person)
    ACCOUNT = "account"          # A platform account (may or may not be linked)
    EMAIL = "email"              # An email address entity
    PHONE = "phone"              # A phone number entity
    DOMAIN = "domain"            # A domain/website entity
    ORGANIZATION = "organization"  # A company/org entity
    LOCATION = "location"        # A geographic location entity
    IMAGE = "image"              # A profile image entity (for visual intelligence)
    USERNAME = "username"        # A username as a standalone entity


# ═══════════════════════════════════════════════════════════════
# EVIDENCE SYSTEM
# ═══════════════════════════════════════════════════════════════

class EvidenceCategory(str, Enum):
    """
    Directional classification of evidence.

    Intelligence analysts must see not just supporting evidence,
    but also contradicting and missing evidence. This prevents
    confirmation bias — one of the biggest risks in OSINT.
    """
    POSITIVE = "positive"            # Supports the hypothesis (accounts are related)
    NEGATIVE = "negative"            # Contradicts the hypothesis
    CONFLICTING = "conflicting"      # Contradicts other evidence (ambiguous)
    MISSING = "missing"              # Expected evidence that is absent
    CIRCUMSTANTIAL = "circumstantial"  # Neither confirms nor denies alone


class EvidenceQuality(str, Enum):
    """
    Quality tier of evidence.

    Inspired by NATO's intelligence grading system (A1-F6),
    adapted for digital identity investigation.

    The key insight: evidence quality determines whether it can
    INCREASE confidence. Low-quality evidence can only provide
    context — it must never inflate scores.
    """
    DEFINITIVE = "definitive"        # Irrefutable (direct cross-link between accounts)
    STRONG = "strong"                # Highly reliable (same name + same avatar + same bio)
    MODERATE = "moderate"            # Reasonably reliable (same username on reliable platform)
    WEAK = "weak"                    # Low reliability (same language, same country)
    CIRCUMSTANTIAL = "circumstantial"  # No standalone value (status code 200 only)


class EvidenceType(str, Enum):
    """
    Specific type of evidence discovered.

    Each type has a defined maximum weight and quality ceiling.
    For example, SHARED_LINK can be DEFINITIVE, but SAME_LANGUAGE
    can never be higher than WEAK.
    """
    # ── Direct Links (can be DEFINITIVE) ──
    DIRECT_LINK = "direct_link"          # Account A links to Account B
    SAME_EMAIL = "same_email"            # Same email on two platforms
    VERIFIED_OWNERSHIP = "verified_ownership"  # Platform-verified (e.g., verified domain)

    # ── Strong Identity Signals ──
    SAME_DISPLAY_NAME = "same_display_name"  # Identical display name
    SAME_AVATAR = "same_avatar"          # Perceptual hash match (>95%)
    SIMILAR_AVATAR = "similar_avatar"    # Perceptual hash partial match (80-95%)
    SAME_BIO = "same_bio"               # Bio text match (>80%)
    SIMILAR_BIO = "similar_bio"         # Bio text partial match (60-80%)

    # ── Moderate Signals ──
    EXACT_USERNAME = "exact_username"    # Same username string
    SIMILAR_USERNAME = "similar_username"  # Username variation (dr3 → dr3iq)
    SAME_WEBSITE = "same_website"        # Same personal website
    SAME_LOCATION = "same_location"      # Same geographic location
    SHARED_CONNECTION = "shared_connection"  # Mutual link/follow

    # ── Weak Signals ──
    SAME_LANGUAGE = "same_language"      # Same primary language
    SIMILAR_ACTIVITY = "similar_activity"  # Similar activity patterns
    TEMPORAL_CORRELATION = "temporal_correlation"  # Accounts created in same period

    # ── Platform-Level ──
    PLATFORM_RELIABILITY = "platform_reliability"  # Reliability of the source platform
    PROFILE_COMPLETENESS = "profile_completeness"  # How complete the profile data is

    # ── Negative Evidence ──
    DIFFERENT_NAME = "different_name"        # Conflicting display names
    DIFFERENT_AVATAR = "different_avatar"     # Clearly different avatars
    DIFFERENT_LOCATION = "different_location"  # Conflicting locations
    DIFFERENT_LANGUAGE = "different_language"  # Different primary languages
    TEMPORAL_IMPOSSIBILITY = "temporal_impossibility"  # Impossible timeline


# ═══════════════════════════════════════════════════════════════
# CONFIDENCE SYSTEM
# ═══════════════════════════════════════════════════════════════

class ConfidenceLevel(str, Enum):
    """
    Human-readable confidence tier.

    Each level maps to a numeric range AND a specific meaning
    for investigators. The descriptions are prescriptive —
    they tell the analyst exactly how to treat the result.
    """
    CONFIRMED = "confirmed"      # 90-100%: Verified with definitive evidence
    HIGH = "high"                # 70-89%: Strong evidence, high reliability
    MODERATE = "moderate"        # 50-69%: Reasonable evidence, verify recommended
    LOW = "low"                  # 30-49%: Limited evidence, manual review required
    SPECULATIVE = "speculative"  # 10-29%: Insufficient evidence, unreliable
    UNSUBSTANTIATED = "unsubstantiated"  # 0-9%: No meaningful evidence

    @classmethod
    def from_score(cls, score: float) -> "ConfidenceLevel":
        if score >= 90:
            return cls.CONFIRMED
        elif score >= 70:
            return cls.HIGH
        elif score >= 50:
            return cls.MODERATE
        elif score >= 30:
            return cls.LOW
        elif score >= 10:
            return cls.SPECULATIVE
        else:
            return cls.UNSUBSTANTIATED


# ═══════════════════════════════════════════════════════════════
# GRAPH MODEL
# ═══════════════════════════════════════════════════════════════

class RelationType(str, Enum):
    """
    Types of relationships between entities in the intelligence graph.

    Each relationship type has semantics that affect how
    confidence propagates through the graph.
    """
    DIRECT_LINK = "direct_link"        # A explicitly links to B (highest trust)
    SAME_PERSON = "same_person"        # A and B are the same person (confirmed)
    LIKELY_SAME = "likely_same"        # A and B are likely the same person
    POSSIBLE_MATCH = "possible_match"  # A and B might be the same person
    OWNS = "owns"                      # Entity owns another (person → domain)
    USES = "uses"                      # Entity uses another (person → email)
    MENTIONS = "mentions"              # A mentions B (weaker than link)
    ASSOCIATED = "associated"          # General association
    CONTRADICTS = "contradicts"        # Evidence suggests NOT same person


# ═══════════════════════════════════════════════════════════════
# COLLECTION & PLATFORM
# ═══════════════════════════════════════════════════════════════

class CollectionMethod(str, Enum):
    """How data was collected — affects evidence reliability."""
    DIRECT_API = "direct_api"          # Official platform API (highest reliability)
    PROFILE_SCRAPE = "profile_scrape"  # HTML scraping of profile page
    SEARCH_ENGINE = "search_engine"    # Search engine dorking (Bing, Google)
    STATUS_CODE = "status_code"        # HTTP status code only (lowest reliability)
    CACHED = "cached"                  # From cache/previous investigation


class PlatformTier(str, Enum):
    """
    Platform reliability tier.

    Tier 1: Major platforms with rich APIs and reliable data.
    Tier 2: Significant platforms with moderate data.
    Tier 3: Smaller or less reliable platforms.
    """
    TIER_1 = "tier_1"  # GitHub, Twitter, LinkedIn, Reddit, Instagram
    TIER_2 = "tier_2"  # Behance, GitLab, Medium, Keybase
    TIER_3 = "tier_3"  # Everything else


class CheckStatus(str, Enum):
    """Result of checking a single platform for an entity."""
    FOUND = "found"          # Account exists and is active
    NOT_FOUND = "not_found"  # Account does not exist
    UNCERTAIN = "uncertain"  # Could not determine (blocked, timeout, etc.)
    ERROR = "error"          # Technical error during check
    RESTRICTED = "restricted"  # Account exists but is private/restricted


# ═══════════════════════════════════════════════════════════════
# REPORTING
# ═══════════════════════════════════════════════════════════════

class ReportFormat(str, Enum):
    """Supported report export formats."""
    HTML = "html"
    JSON = "json"
    PDF = "pdf"


class RiskLevel(str, Enum):
    """Digital exposure risk assessment level."""
    CRITICAL = "critical"    # Extreme digital footprint, highly identifiable
    HIGH = "high"            # Significant exposure across many platforms
    MODERATE = "moderate"    # Moderate presence, some privacy measures
    LOW = "low"              # Limited digital footprint
    MINIMAL = "minimal"      # Very little public presence
