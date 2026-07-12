"""
DR3 OSINT — Central Configuration
"""

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .core.constants import (
    DEFAULT_MAX_CONNECTIONS,
    DEFAULT_TIMEOUT,
    DEFAULT_TOP_SITES,
    DEFAULT_RETRIES,
)


@dataclass
class Config:
    """Central configuration for DR3 OSINT platform."""

    # Paths
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent)
    data_dir: Path = field(default_factory=lambda: Path(__file__).parent / "data")
    sites_db_path: str = ""
    reports_dir: str = ""

    # Search settings
    timeout: int = DEFAULT_TIMEOUT
    max_connections: int = DEFAULT_MAX_CONNECTIONS
    top_sites: int = DEFAULT_TOP_SITES
    retries: int = DEFAULT_RETRIES

    # AI settings
    gemini_api_key: Optional[str] = None
    ai_enabled: bool = False

    # Server settings
    host: str = "127.0.0.1"
    port: int = 8000
    secret_key: str = ""
    debug: bool = False

    # Logging
    log_level: str = "INFO"

    def __post_init__(self):
        if not self.sites_db_path:
            self.sites_db_path = str(self.data_dir / "sites.json")
        if not self.reports_dir:
            self.reports_dir = str(self.base_dir.parent / "reports")
        if not self.secret_key:
            self.secret_key = secrets.token_hex(32)

        # Load from environment
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", self.gemini_api_key)
        self.ai_enabled = bool(self.gemini_api_key)
        self.debug = os.environ.get("DR3_DEBUG", "").lower() in ("1", "true", "yes")
        self.log_level = os.environ.get("DR3_LOG_LEVEL", self.log_level)

        env_port = os.environ.get("DR3_PORT")
        if env_port:
            self.port = int(env_port)

        # Ensure dirs exist
        os.makedirs(self.reports_dir, exist_ok=True)


# Global config singleton
config = Config()
