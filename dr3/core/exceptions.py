"""
DR3 Intelligence Platform — Custom Exceptions

Exception hierarchy is designed for:
  - Granular error handling at each pipeline stage
  - Meaningful error messages for investigators
  - Distinction between recoverable and fatal errors
"""


class DR3Error(Exception):
    """Base exception for DR3 Intelligence Platform."""
    pass


# ── Investigation Errors ──

class InvestigationError(DR3Error):
    """Error during investigation lifecycle."""
    pass


class SeedResolutionError(InvestigationError):
    """Failed to resolve a seed identity."""
    pass


class ExpansionError(InvestigationError):
    """Error during identity expansion."""
    pass


class ExpansionLimitReached(InvestigationError):
    """Investigation hit expansion limits (max depth or max nodes)."""
    def __init__(self, limit_type: str, current: int, maximum: int):
        self.limit_type = limit_type
        self.current = current
        self.maximum = maximum
        super().__init__(
            f"Expansion limit reached: {limit_type} "
            f"({current}/{maximum})"
        )


# ── Collection Errors ──

class CollectionError(DR3Error):
    """Error during data collection."""
    pass


class PlatformCheckError(CollectionError):
    """Error checking a specific platform."""
    def __init__(self, platform: str, error_type: str, detail: str = ""):
        self.platform = platform
        self.error_type = error_type
        self.detail = detail
        super().__init__(f"[{platform}] {error_type}: {detail}")


class RateLimitError(CollectionError):
    """Rate limit exceeded on a platform."""
    def __init__(self, platform: str, retry_after: float = 0):
        self.platform = platform
        self.retry_after = retry_after
        super().__init__(
            f"Rate limited by {platform}"
            + (f" (retry after {retry_after}s)" if retry_after else "")
        )


# ── Intelligence Errors ──

class EvidenceError(DR3Error):
    """Error in evidence evaluation."""
    pass


class ConfidenceError(DR3Error):
    """Error in confidence calculation."""
    pass


class CorrelationError(DR3Error):
    """Error during identity correlation."""
    pass


class AIAnalysisError(DR3Error):
    """Error during AI analysis."""
    pass


# ── Storage Errors ──

class StorageError(DR3Error):
    """Error in database operations."""
    pass


class DatabaseError(StorageError):
    """Error loading or processing the database."""
    pass


# ── Configuration Errors ──

class ConfigurationError(DR3Error):
    """Invalid configuration."""
    pass


# ── Report Errors ──

class ReportGenerationError(DR3Error):
    """Error generating reports."""
    pass
