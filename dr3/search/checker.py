"""
DR3 OSINT — Async HTTP Checker
Handles all HTTP requests to check username existence on sites.
Uses connection pooling, timeouts, and error handling.
"""

import asyncio
import logging
import random
import ssl
from typing import Optional, Tuple
from urllib.parse import quote

import aiohttp
from aiohttp import ClientSession, ClientTimeout, TCPConnector

from ..core.constants import DEFAULT_USER_AGENTS
from ..core.enums import CheckMethod, CheckStatus
from ..core.exceptions import SiteCheckError
from ..core.models import CheckResult, SiteConfig

logger = logging.getLogger("dr3.checker")


class HttpChecker:
    """Async HTTP checker for verifying username existence on sites."""

    def __init__(
        self,
        timeout: int = 15,
        max_connections: int = 50,
        proxy: Optional[str] = None,
    ):
        self.timeout = timeout
        self.max_connections = max_connections
        self.proxy = proxy
        self._session: Optional[ClientSession] = None
        self._connector: Optional[TCPConnector] = None

    async def _get_session(self) -> ClientSession:
        """Get or create a shared aiohttp session with connection pooling."""
        if self._session is None or self._session.closed:
            self._connector = TCPConnector(
                limit=self.max_connections,
                ssl=False,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
            )
            self._session = ClientSession(
                connector=self._connector,
                trust_env=True,
                timeout=ClientTimeout(total=self.timeout),
            )
        return self._session

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            # Allow time for connections to close
            await asyncio.sleep(0.1)

    def _get_headers(self, site: SiteConfig) -> dict:
        """Build request headers."""
        headers = {
            "User-Agent": random.choice(DEFAULT_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "close",
        }
        headers.update(site.headers)
        return headers

    def _build_url(self, site: SiteConfig, username: str) -> str:
        """Build the URL to check for the username."""
        url = site.url.replace("{username}", quote(username))
        url = url.replace("{urlMain}", site.url_main)
        url = url.replace("{urlSubpath}", site.url_subpath)
        # Fix double slashes (but not in protocol)
        import re
        url = re.sub(r"(?<!:)/+", "/", url)
        return url

    def _build_probe_url(self, site: SiteConfig, username: str, user_url: str) -> str:
        """Build the probe URL (may differ from user-visible URL)."""
        if site.url_probe:
            url = site.url_probe.replace("{username}", username)
            url = url.replace("{urlMain}", site.url_main)
            url = url.replace("{urlSubpath}", site.url_subpath)
            return url
        return user_url

    async def check_site(self, site: SiteConfig, username: str) -> CheckResult:
        """Check a single site for the username."""
        import time
        start_time = time.monotonic()

        # Validate username format
        if site.regex_check:
            import re
            if not re.search(site.regex_check, username):
                return CheckResult(
                    site_name=site.name,
                    url="",
                    status=CheckStatus.ILLEGAL,
                    url_main=site.url_main,
                    error_message=f"Username format not supported: {site.regex_check}",
                    tags=site.tags,
                )

        # Build URLs
        user_url = self._build_url(site, username)
        probe_url = self._build_probe_url(site, username, user_url)

        # Add GET params
        if site.get_params:
            params = "&".join(f"{k}={v}" for k, v in site.get_params.items())
            separator = "&" if "?" in probe_url else "?"
            probe_url += separator + params

        try:
            html_text, status_code, error = await self._make_request(
                url=probe_url,
                headers=self._get_headers(site),
                allow_redirects=(site.check_type != "response_url"),
                method="head" if (site.check_type == "status_code" and site.request_head_only) else "get",
            )

            if error:
                elapsed = time.monotonic() - start_time
                return CheckResult(
                    site_name=site.name,
                    url=user_url,
                    status=CheckStatus.ERROR,
                    url_main=site.url_main,
                    response_time=elapsed,
                    error_message=error,
                    tags=site.tags,
                )

            # Check for site-specific errors
            if html_text:
                for flag, msg in site.errors.items():
                    if flag in html_text:
                        elapsed = time.monotonic() - start_time
                        return CheckResult(
                            site_name=site.name,
                            url=user_url,
                            status=CheckStatus.ERROR,
                            url_main=site.url_main,
                            response_time=elapsed,
                            error_message=f"Site error: {msg}",
                            tags=site.tags,
                        )

            # Determine result based on check type
            status = self._evaluate_result(site, html_text or "", status_code)

            elapsed = time.monotonic() - start_time

            # Extract profile data if found
            extracted = {}
            if status == CheckStatus.CLAIMED and html_text:
                extracted = self._extract_basic_data(html_text, site)

            return CheckResult(
                site_name=site.name,
                url=user_url,
                status=status,
                url_main=site.url_main,
                http_status=status_code,
                response_time=elapsed,
                extracted_data=extracted,
                tags=site.tags,
            )

        except Exception as e:
            elapsed = time.monotonic() - start_time
            logger.debug(f"Unexpected error checking {site.name}: {e}")
            return CheckResult(
                site_name=site.name,
                url=user_url,
                status=CheckStatus.ERROR,
                url_main=site.url_main,
                response_time=elapsed,
                error_message=str(e),
                tags=site.tags,
            )

    async def _make_request(
        self,
        url: str,
        headers: dict,
        allow_redirects: bool = True,
        method: str = "get",
    ) -> Tuple[Optional[str], int, Optional[str]]:
        """Make an HTTP request and return (html_text, status_code, error)."""
        try:
            session = await self._get_session()
            request_method = session.get if method == "get" else session.head

            async with request_method(
                url=url,
                headers=headers,
                allow_redirects=allow_redirects,
                proxy=self.proxy,
            ) as response:
                status_code = response.status
                if method == "head":
                    return "", status_code, None

                try:
                    content = await response.read()
                    charset = response.charset or "utf-8"
                    html_text = content.decode(charset, errors="ignore")
                except Exception:
                    html_text = ""

                if status_code == 0:
                    return html_text, 0, "Connection lost"

                return html_text, status_code, None

        except asyncio.TimeoutError:
            return None, 0, "Request timeout"
        except aiohttp.ClientConnectorError as e:
            return None, 0, f"Connection failed: {str(e)[:100]}"
        except aiohttp.ServerDisconnectedError:
            return None, 0, "Server disconnected"
        except Exception as e:
            if isinstance(e, (ssl.SSLError, ssl.SSLCertVerificationError)):
                return None, 0, f"SSL error: {str(e)[:100]}"
            return None, 0, f"Unexpected: {str(e)[:100]}"

    def _evaluate_result(
        self, site: SiteConfig, html_text: str, status_code: int
    ) -> CheckStatus:
        """Evaluate check result based on site's check method."""
        check_type = site.check_type

        if check_type == "message":
            # Check for absence indicators
            is_absent = any(flag in html_text for flag in site.absence_strs)
            # Check for presence indicators
            is_present = (
                any(flag in html_text for flag in site.presence_strs)
                if site.presence_strs
                else True
            )
            if not is_absent and is_present:
                return CheckStatus.CLAIMED
            return CheckStatus.AVAILABLE

        elif check_type == "status_code":
            if 200 <= status_code < 300:
                return CheckStatus.CLAIMED
            return CheckStatus.AVAILABLE

        elif check_type == "response_url":
            is_present = (
                any(flag in html_text for flag in site.presence_strs)
                if site.presence_strs
                else True
            )
            if 200 <= status_code < 300 and is_present:
                return CheckStatus.CLAIMED
            return CheckStatus.AVAILABLE

        return CheckStatus.UNKNOWN

    def _extract_basic_data(self, html_text: str, site: SiteConfig) -> dict:
        """Extract basic profile data from HTML response."""
        import re
        data = {}

        # Try to extract common metadata
        # Title
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html_text, re.IGNORECASE)
        if title_match:
            data["page_title"] = title_match.group(1).strip()

        # Meta description
        desc_match = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
            html_text,
            re.IGNORECASE,
        )
        if desc_match:
            data["meta_description"] = desc_match.group(1).strip()

        # OpenGraph data
        for og_prop in ["og:title", "og:description", "og:image", "og:url"]:
            og_match = re.search(
                rf'<meta[^>]+property=["\']{ re.escape(og_prop) }["\'][^>]+content=["\']([^"\']+)',
                html_text,
                re.IGNORECASE,
            )
            if og_match:
                key = og_prop.replace("og:", "og_")
                data[key] = og_match.group(1).strip()

        return data
