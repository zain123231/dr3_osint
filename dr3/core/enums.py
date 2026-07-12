"""
DR3 OSINT — Enumerations
"""

from enum import Enum


class CheckStatus(str, Enum):
    """Status of a username check on a site."""
    CLAIMED = "claimed"
    AVAILABLE = "available"
    UNKNOWN = "unknown"
    ILLEGAL = "illegal"
    ERROR = "error"


class ConfidenceLevel(str, Enum):
    """Confidence level for identity matching."""
    VERY_HIGH = "very_high"    # 90-100%
    HIGH = "high"              # 70-89%
    MEDIUM = "medium"          # 50-69%
    LOW = "low"                # 30-49%
    POSSIBLE = "possible"      # 0-29%

    @classmethod
    def from_score(cls, score: float) -> "ConfidenceLevel":
        if score >= 90:
            return cls.VERY_HIGH
        elif score >= 70:
            return cls.HIGH
        elif score >= 50:
            return cls.MEDIUM
        elif score >= 30:
            return cls.LOW
        else:
            return cls.POSSIBLE


class CheckMethod(str, Enum):
    """Method used to check username existence."""
    STATUS_CODE = "status_code"
    MESSAGE = "message"
    RESPONSE_URL = "response_url"


class SearchPhase(str, Enum):
    """Phases of the search pipeline."""
    PREPROCESSING = "preprocessing"
    SEARCHING = "searching"
    VALIDATING = "validating"
    ANALYZING = "analyzing"
    POSTPROCESSING = "postprocessing"


class EvidenceType(str, Enum):
    """Types of evidence for identity correlation."""
    EXACT_USERNAME = "exact_username"
    SIMILAR_USERNAME = "similar_username"
    SAME_DISPLAY_NAME = "same_display_name"
    SIMILAR_BIO = "similar_bio"
    SAME_AVATAR = "same_avatar"
    SAME_LOCATION = "same_location"
    SAME_LANGUAGE = "same_language"
    SHARED_LINKS = "shared_links"
    SAME_EMAIL = "same_email"
    ACTIVITY_PATTERN = "activity_pattern"
    PLATFORM_RELIABILITY = "platform_reliability"


class ReportFormat(str, Enum):
    """Supported report export formats."""
    HTML = "html"
    PDF = "pdf"
    JSON = "json"
