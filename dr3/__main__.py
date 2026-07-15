"""
DR3 Intelligence Platform — Entry Point
"""

import logging
import sys

import uvicorn

from .config import Config


def main():
    """Start the DR3 Intelligence Platform."""
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    logger = logging.getLogger("dr3")

    print()
    print("  ╔═══════════════════════════════════════════════════╗")
    print("  ║   DR3 Intelligence Platform v3.0                 ║")
    print("  ║   AI-Powered Digital Identity Intelligence       ║")
    print("  ╠═══════════════════════════════════════════════════╣")
    print(f"  ║   🌐 http://127.0.0.1:{Config.PORT:<24}║")
    print(f"  ║   🤖 AI: {'Active (Gemini)' if Config.ai_available() else 'Rule-based':<32}║")
    print(f"  ║   🔑 GitHub Token: {'Active' if Config.GITHUB_TOKEN else 'Not set':<24}║")
    print("  ╚═══════════════════════════════════════════════════╝")
    print()

    uvicorn.run(
        "dr3.api.app:app",
        host="127.0.0.1",
        port=Config.PORT,
        log_level=Config.LOG_LEVEL.lower(),
        reload=Config.DEBUG,
    )


if __name__ == "__main__":
    main()
