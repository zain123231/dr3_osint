"""
DR3 OSINT — Entry Point
Run with: python -m dr3
"""

import argparse
import asyncio
import logging
import sys

from .config import config


def main():
    parser = argparse.ArgumentParser(
        description="DR3 OSINT — AI-Powered Digital Intelligence Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.port,
        help=f"Port to run the web server on (default: {config.port})",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=config.host,
        help=f"Host to bind to (default: {config.host})",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=config.debug,
        help="Run in debug mode",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )

    logger = logging.getLogger("dr3")
    logger.info("=" * 60)
    logger.info("  DR3 OSINT Intelligence Platform v2.0.0")
    logger.info("=" * 60)
    logger.info(f"  Server: http://{args.host}:{args.port}")
    logger.info(f"  AI: {'Enabled (Gemini)' if config.ai_enabled else 'Disabled (rule-based)'}")
    logger.info(f"  Debug: {args.debug}")
    logger.info("=" * 60)

    # Run server
    try:
        import uvicorn
        uvicorn.run(
            "dr3.api.app:app",
            host=args.host,
            port=args.port,
            reload=args.debug,
            log_level="info" if not args.debug else "debug",
        )
    except ImportError:
        logger.error("uvicorn is not installed. Install with: pip install uvicorn")
        sys.exit(1)


if __name__ == "__main__":
    main()
