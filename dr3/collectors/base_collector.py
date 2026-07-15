"""
DR3 Intelligence Platform — Base Collector

Abstract base class for all data collectors.
Every collector (GitHub API, HTTP scraper, Dorking, etc.)
inherits from this base and implements the collect() method.

Design: Strategy pattern — the Investigation Orchestrator
doesn't know or care HOW data is collected. It just calls
collector.collect(target) and gets a CollectionResult.
"""

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from typing import List, Optional

import aiohttp
from aiohttp import ClientSession, ClientTimeout, TCPConnector

from ..core.constants import DEFAULT_USER_AGENTS, DEFAULT_TIMEOUT, MAX_CONNECTIONS
from ..core.enums import CheckStatus, CollectionMethod
from ..core.models import CollectionResult, SiteConfig

logger = logging.getLogger("dr3.collector")


class BaseCollector(ABC):
    """
    Abstract base for all data collectors.

    Subclasses must implement:
      - collect(username, ...) → CollectionResult
      - platform_name → str
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Name of the platform this collector targets."""
        ...

    @abstractmethod
    async def collect(self, username: str, **kwargs) -> CollectionResult:
        """
        Collect identity data for a username on this platform.

        Returns a CollectionResult with all extracted data,
        or a NOT_FOUND/ERROR result.
        """
        ...

    async def close(self) -> None:
        """Cleanup resources. Override if needed."""
        pass


class HttpCollector(BaseCollector):
    """
    Generic HTTP-based collector for sites.json platforms.

    This is the equivalent of the old checker.py but redesigned:
    - Returns CollectionResult (not CheckResult)
    - Extracts richer metadata
    - Classifies collection method
    - No false confidence inflation
    """

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        max_connections: int = MAX_CONNECTIONS,
        proxy: Optional[str] = None,
    ):
        self.timeout = timeout
        self.max_connections = max_connections
        self.proxy = proxy

    @property
    def platform_name(self) -> str:
        return "generic_http"

    async def close(self) -> None:
        pass

    async def collect(self, username: str, **kwargs) -> CollectionResult:
        """Not used directly — use check_site instead."""
        return CollectionResult(platform="generic", status=CheckStatus.ERROR)

    async def check_site(
        self, site: SiteConfig, username: str
    ) -> CollectionResult:
        """
        Check a single site from sites.json for a username.

        Returns a rich CollectionResult with extracted metadata.
        """
        import re
        import time
        from urllib.parse import quote

        start_time = time.monotonic()

        # Validate username format
        if site.regex_check:
            if not re.search(site.regex_check, username):
                return CollectionResult(
                    platform=site.name,
                    status=CheckStatus.RESTRICTED,
                    error_message=f"Username format not supported: {site.regex_check}",
                    tags=site.tags,
                )

        # Build URLs
        user_url = site.url.replace("{username}", quote(username))
        user_url = user_url.replace("{urlMain}", site.url_main)
        user_url = user_url.replace("{urlSubpath}", site.url_subpath)
        user_url = re.sub(r"(?<!:)/+", "/", user_url)

        probe_url = user_url
        if site.url_probe:
            probe_url = site.url_probe.replace("{username}", username)
            probe_url = probe_url.replace("{urlMain}", site.url_main)
            probe_url = probe_url.replace("{urlSubpath}", site.url_subpath)

        if site.get_params:
            params = "&".join(f"{k}={v}" for k, v in site.get_params.items())
            separator = "&" if "?" in probe_url else "?"
            probe_url += separator + params

        headers = {
            "User-Agent": random.choice(DEFAULT_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "close",
        }
        headers.update(site.headers)

        method = "head" if (site.check_type == "status_code" and site.request_head_only) else "get"
        allow_redirects = site.check_type != "response_url"

        try:
            connector = TCPConnector(limit=self.max_connections, ssl=True, ttl_dns_cache=300, enable_cleanup_closed=True)
            async with ClientSession(connector=connector, trust_env=True, timeout=ClientTimeout(total=self.timeout)) as session:
                request_fn = session.get if method == "get" else session.head

                async with request_fn(
                    url=probe_url,
                    headers=headers,
                    allow_redirects=allow_redirects,
                    proxy=self.proxy,
                ) as response:
                    http_status = response.status
                    html_text = ""

                    if method == "get":
                        try:
                            content = await response.read()
                            charset = response.charset or "utf-8"
                            html_text = content.decode(charset, errors="ignore")
                        except Exception:
                            html_text = ""

                    elapsed = time.monotonic() - start_time

                    # Check for site-specific errors
                    if html_text:
                        for flag, msg in site.errors.items():
                            if flag in html_text:
                                return CollectionResult(
                                    platform=site.name,
                                    status=CheckStatus.ERROR,
                                    http_status=http_status,
                                    response_time=elapsed,
                                    error_message=f"Site error: {msg}",
                                    tags=site.tags,
                                )

                    # Determine if found
                    status = self._evaluate_check(site, html_text, http_status)

                    # Determine collection method quality
                    if method == "head" or not html_text:
                        collection_method = CollectionMethod.STATUS_CODE
                    else:
                        collection_method = CollectionMethod.PROFILE_SCRAPE

                    # Extract metadata if found
                    extracted = {}
                    if status == CheckStatus.FOUND and html_text:
                        extracted = self._extract_metadata(html_text)

                    # Determine platform tier
                    from ..core.constants import TIER_1_PLATFORMS, TIER_2_PLATFORMS
                    from ..core.enums import PlatformTier
                    if site.name in TIER_1_PLATFORMS:
                        tier = PlatformTier.TIER_1
                    elif site.name in TIER_2_PLATFORMS:
                        tier = PlatformTier.TIER_2
                    else:
                        tier = PlatformTier.TIER_3

                    return CollectionResult(
                        platform=site.name,
                        status=status,
                        collection_method=collection_method,
                        username=username,
                        display_name=extracted.get("og_title", ""),
                        bio=extracted.get("meta_description", "") or extracted.get("og_description", ""),
                        avatar_url=extracted.get("og_image", ""),
                        profile_url=user_url,
                        http_status=http_status,
                        response_time=elapsed,
                        tags=site.tags,
                        platform_tier=tier,
                        extra_data=extracted,

                    )

        except asyncio.TimeoutError:
            return CollectionResult(
                platform=site.name,
                status=CheckStatus.ERROR,
                response_time=time.monotonic() - start_time,
                error_message="Request timeout",
                tags=site.tags,
            )
        except aiohttp.ClientConnectorError as e:
            return CollectionResult(
                platform=site.name,
                status=CheckStatus.ERROR,
                response_time=time.monotonic() - start_time,
                error_message=f"Connection failed: {str(e)[:100]}",
                tags=site.tags,
            )
        except Exception as e:
            return CollectionResult(
                platform=site.name,
                status=CheckStatus.ERROR,
                response_time=time.monotonic() - start_time,
                error_message=f"Unexpected: {str(e)[:100]}",
                tags=site.tags,
            )

    def _evaluate_check(
        self, site: SiteConfig, html_text: str, status_code: int
    ) -> CheckStatus:
        """Evaluate HTTP result based on site's check method."""
        check_type = site.check_type

        if check_type == "message":
            is_absent = any(flag in html_text for flag in site.absence_strs)
            is_present = (
                any(flag in html_text for flag in site.presence_strs)
                if site.presence_strs else True
            )
            if not is_absent and is_present:
                return CheckStatus.FOUND
            return CheckStatus.NOT_FOUND

        elif check_type == "status_code":
            if 200 <= status_code < 300:
                return CheckStatus.FOUND
            return CheckStatus.NOT_FOUND

        elif check_type == "response_url":
            is_present = (
                any(flag in html_text for flag in site.presence_strs)
                if site.presence_strs else True
            )
            if 200 <= status_code < 300 and is_present:
                return CheckStatus.FOUND
            return CheckStatus.NOT_FOUND

        return CheckStatus.UNCERTAIN

    def _extract_metadata(self, html_text: str) -> dict:
        """Extract metadata from HTML response."""
        import re
        data = {}

        # Title
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html_text, re.IGNORECASE)
        if title_match:
            data["page_title"] = title_match.group(1).strip()

        # Meta description
        desc_match = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
            html_text, re.IGNORECASE,
        )
        if desc_match:
            data["meta_description"] = desc_match.group(1).strip()

        # OpenGraph
        for og_prop in ["og:title", "og:description", "og:image", "og:url"]:
            og_match = re.search(
                rf'<meta[^>]+property=["\']{ re.escape(og_prop) }["\'][^>]+content=["\']([^"\']+)',
                html_text, re.IGNORECASE,
            )
            if og_match:
                key = og_prop.replace("og:", "og_")
                data[key] = og_match.group(1).strip()

        return data
