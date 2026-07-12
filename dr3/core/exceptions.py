"""
DR3 OSINT — Custom Exceptions
"""


class DR3Error(Exception):
    """Base exception for DR3 OSINT."""
    pass


class SearchError(DR3Error):
    """Error during search operations."""
    pass


class SiteCheckError(DR3Error):
    """Error checking a specific site."""
    def __init__(self, site_name: str, error_type: str, detail: str = ""):
        self.site_name = site_name
        self.error_type = error_type
        self.detail = detail
        super().__init__(f"[{site_name}] {error_type}: {detail}")


class DatabaseError(DR3Error):
    """Error loading or processing the sites database."""
    pass


class AIAnalysisError(DR3Error):
    """Error during AI analysis."""
    pass


class ReportGenerationError(DR3Error):
    """Error generating reports."""
    pass


class ConfigurationError(DR3Error):
    """Invalid configuration."""
    pass


class RateLimitError(DR3Error):
    """Rate limit exceeded."""
    pass
