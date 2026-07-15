"""
DR3 OSINT — Deep Search Engine (Dorking)
Provides fallback searching via Bing for hard targets like Instagram/LinkedIn.

Yahoo: DEAD (returns HTTP 500 on all requests as of 2025+).
DuckDuckGo HTML: BLOCKED (returns CAPTCHA / anomaly challenge on automated requests).
Bing: WORKING — primary and only engine used.
"""

import asyncio
import logging
import random
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import aiohttp
from bs4 import BeautifulSoup

from ..core.constants import DEFAULT_USER_AGENTS
from ..core.enums import CheckStatus, CollectionMethod
from ..core.models import SiteConfig, CollectionResult

logger = logging.getLogger("dr3.dorking")


class DorkingEngine:
    """Uses Search Engine Dorks via Bing to bypass WAFs for hard targets."""

    BING_URL = "https://www.bing.com/search"
    MAX_RETRIES = 2
    RETRY_BASE_DELAY = 2.0  # seconds

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(2)  # Limit concurrent dorks
        # We only apply Dorking to known hard targets to save time
        self.hard_targets = {
            "instagram", "instagram.com",
            "linkedin", "linkedin.com",
            "tiktok", "tiktok.com",
            "facebook", "facebook.com",
            "snapchat", "snapchat.com",
            "twitter", "twitter.com",
            "x.com"
        }

    def _is_hard_target(self, site: SiteConfig) -> bool:
        """Check if the site is a known hard target."""
        name_lower = site.name.lower()
        url_main_lower = site.url_main.lower()

        for target in self.hard_targets:
            if target in name_lower or target in url_main_lower:
                return True
        return False

    def _build_headers(self) -> dict:
        """Build realistic browser headers."""
        return {
            "User-Agent": random.choice(DEFAULT_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def _fetch_with_retry(self, session: aiohttp.ClientSession, url: str,
                                 params: dict, headers: dict,
                                 site_name: str) -> Optional[str]:
        """Fetch a URL with retry and exponential backoff."""
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 429:
                        delay = self.RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0.5, 1.5)
                        logger.warning(
                            f"Dorking: Bing rate-limited (429) for {site_name}, "
                            f"retrying in {delay:.1f}s (attempt {attempt + 1}/{self.MAX_RETRIES + 1})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    elif response.status >= 500:
                        delay = self.RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0.5, 1.5)
                        logger.warning(
                            f"Dorking: Bing returned {response.status} for {site_name}, "
                            f"retrying in {delay:.1f}s (attempt {attempt + 1}/{self.MAX_RETRIES + 1})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.warning(f"Dorking: Bing returned status {response.status} for {site_name}")
                        return None
            except asyncio.TimeoutError:
                logger.debug(f"Dorking: Bing timed out for {site_name} (attempt {attempt + 1})")
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_BASE_DELAY)
                    continue
            except Exception as e:
                logger.debug(f"Dorking: Bing error for {site_name}: {e}")
                return None

        logger.warning(f"Dorking: Bing failed after {self.MAX_RETRIES + 1} attempts for {site_name}")
        return None

    def _check_results(self, html_text: str, domain: str, username: str) -> bool:
        """
        Analyze Bing search results HTML to determine if a profile was found.

        Uses multiple detection methods:
        1. href links containing domain + username
        2. <cite> elements (Bing shows URLs in these)
        3. Proximity check: domain and username appear near each other in text
        """
        username_lower = username.lower()
        domain_lower = domain.lower()

        # Method 1: Look for links containing the domain and username
        links = re.findall(r'href="(https?://[^"]+)"', html_text)
        for link in links:
            link_lower = link.lower()
            if domain_lower in link_lower and username_lower in link_lower:
                return True

        # Method 2: Check <cite> elements (Bing shows result URLs here)
        cites = re.findall(r'<cite[^>]*>(.*?)</cite>', html_text, re.DOTALL)
        for cite in cites:
            cite_lower = cite.lower()
            if domain_lower in cite_lower and username_lower in cite_lower:
                return True

        # Method 3: Check if domain and username co-occur in the page text
        # This catches cases where Bing renders the URL in snippets or titles
        text_lower = html_text.lower()
        if domain_lower in text_lower and username_lower in text_lower:
            # Verify they appear in a result context (not just in the query echo)
            # Look for them appearing near each other (within 200 chars)
            for match in re.finditer(re.escape(domain_lower), text_lower):
                start = max(0, match.start() - 100)
                end = min(len(text_lower), match.end() + 200)
                nearby_text = text_lower[start:end]
                if username_lower in nearby_text:
                    return True

        return False

    async def fallback_check(self, site: SiteConfig, username: str) -> Optional[CollectionResult]:
        """Perform a dork search via Bing if the site is a hard target."""
        if not self._is_hard_target(site):
            return None

        logger.info(f"Initiating Deep Search (Dorking) for {site.name} -> {username}")

        # Build Dork Query
        domain = site.url_main.replace("https://", "").replace("http://", "").strip("/")
        if "www." in domain:
            domain = domain.replace("www.", "")

        dork = f'site:{domain} "{username}"'
        expected_url = site.url.replace("{username}", username)

        try:
            # Delay between requests to avoid rate limiting
            await asyncio.sleep(random.uniform(1.0, 2.5))

            async with self._semaphore:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as session:
                    headers = self._build_headers()
                    params = {"q": dork}

                    html_text = await self._fetch_with_retry(
                        session, self.BING_URL, params, headers, site.name
                    )

                    if html_text is None:
                        return None

                    found = self._check_results(html_text, domain, username)

                    if found:
                        logger.info(f"Deep Search found match for {username} on {site.name}")
                        return CollectionResult(
                            platform=site.name,
                            profile_url=expected_url,
                            status=CheckStatus.FOUND,
                            collection_method=CollectionMethod.SEARCH_ENGINE,
                            username=username,
                            http_status=200,
                            response_time=0.0,
                            tags=site.tags,
                            fallback_used=True,
                            extra_data={"dork_match": True}
                        )
                    else:
                        logger.debug(f"Deep Search found NO match for {username} on {site.name}")
                        return CollectionResult(
                            platform=site.name,
                            profile_url=expected_url,
                            status=CheckStatus.NOT_FOUND,
                            collection_method=CollectionMethod.SEARCH_ENGINE,
                            username=username,
                            http_status=404,
                            response_time=0.0,
                            tags=site.tags,
                            fallback_used=True
                        )

        except Exception as e:
            logger.error(f"Dorking engine error: {e}")
            return None

    async def search_leaks(self, username: str) -> list[dict]:
        """Perform a dork search for leaks on pastebin sites."""
        logger.info(f"Initiating Leak Search for {username}")
        
        leak_sites = ["pastebin.com", "ghostbin.com", "trello.com"]
        site_query = " OR ".join([f"site:{s}" for s in leak_sites])
        dork = f'({site_query}) "{username}"'
        
        results = []
        try:
            await asyncio.sleep(random.uniform(1.0, 2.0))
            async with self._semaphore:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as session:
                    headers = self._build_headers()
                    params = {"q": dork}
                    
                    html_text = await self._fetch_with_retry(
                        session, self.BING_URL, params, headers, "LeakSearch"
                    )
                    
                    if html_text:
                        # Extract basic links from Bing
                        links = re.findall(r'<a[^>]+href="(https?://(pastebin\.com|ghostbin\.com|trello\.com)[^"]+)"', html_text)
                        titles = re.findall(r'<h2[^>]*><a[^>]*>(.*?)</a></h2>', html_text)
                        
                        seen = set()
                        for i, match in enumerate(links):
                            url = match[0] if isinstance(match, tuple) else match
                            if url not in seen and not "microsoft.com" in url:
                                seen.add(url)
                                # Clean title tags
                                title = re.sub(r'<[^>]+>', '', titles[i]) if i < len(titles) else "Document"
                                results.append({"title": title, "url": url, "source": "Bing Dork"})
        except Exception as e:
            logger.error(f"Leak search error: {e}")
            
        return results

    async def search_darkweb(self, username: str) -> list[dict]:
        """Perform a search for the username on the Dark Web via Ahmia.fi (Clearweb Tor gateway)."""
        logger.info(f"Initiating Dark Web Search for {username}")
        
        results = []
        try:
            await asyncio.sleep(random.uniform(1.0, 2.0))
            async with self._semaphore:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as session:
                    headers = self._build_headers()
                    # Ahmia uses /search/?q=...
                    url = "https://ahmia.fi/search/"
                    params = {"q": username}
                    
                    async with session.get(url, params=params, headers=headers) as response:
                        if response.status == 200:
                            html_text = await response.text()
                            
                            # Parse Ahmia results: <li class="result"> <h4> <a href="...">Title</a> </h4> <cite>...onion</cite>
                            links = re.findall(r'<cite>([^<]+\.onion[^<]*)</cite>', html_text)
                            titles = re.findall(r'<h4>\s*<a[^>]*>(.*?)</a>\s*</h4>', html_text, re.DOTALL)
                            
                            seen = set()
                            for i, match in enumerate(links):
                                url = "http://" + match.strip() if not match.startswith("http") else match.strip()
                                if url not in seen:
                                    seen.add(url)
                                    title = re.sub(r'<[^>]+>', '', titles[i]).strip() if i < len(titles) else "Dark Web Link"
                                    results.append({"title": title, "url": url, "source": "Ahmia.fi"})
                                    
        except Exception as e:
            logger.error(f"Dark Web search error: {e}")
            
        return results
