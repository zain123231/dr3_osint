"""
DR3 Intelligence Platform — Configuration

Central configuration with environment variable overrides.
"""

import os
from pathlib import Path
from typing import Optional


class Config:
    """Application configuration."""

    # ── Paths ──
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
    SITES_FILE = DATA_DIR / "sites.json"
    DB_DIR = BASE_DIR / "db"
    DB_PATH = DB_DIR / "dr3_intelligence.db"

    # ── Server ──
    PORT: int = int(os.getenv("DR3_PORT", "8000"))
    DEBUG: bool = os.getenv("DR3_DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("DR3_LOG_LEVEL", "INFO")

    # ── AI ──
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # ── API Tokens ──
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")

    # ── Investigation Defaults ──
    DEFAULT_MAX_DEPTH: int = int(os.getenv("DR3_MAX_DEPTH", "3"))
    DEFAULT_MAX_NODES: int = int(os.getenv("DR3_MAX_NODES", "50"))
    DEFAULT_TIMEOUT: int = int(os.getenv("DR3_TIMEOUT", "15"))
    MAX_CONNECTIONS: int = int(os.getenv("DR3_MAX_CONNECTIONS", "50"))

    @classmethod
    def ensure_dirs(cls) -> None:
        """Ensure required directories exist."""
        cls.DB_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def ai_available(cls) -> bool:
        return bool(cls.GEMINI_API_KEY)
