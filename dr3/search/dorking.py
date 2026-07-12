"""
DR3 OSINT — Deep Search Engine (Dorking)
Provides fallback searching via DuckDuckGo for hard targets like Instagram/LinkedIn.
"""

import asyncio
import logging
import random
from typing import Optional, List
from urllib.parse import quote

import aiohttp

from ..core.constants import DEFAULT_USER_AGENTS
from ..core.enums import CheckStatus
from ..core.models import SiteConfig, CheckResult

logger = logging.getLogger("dr3.dorking")

class DorkingEngine:
    """Uses Search Engine Dorks to bypass WAFs for hard targets."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.base_url = "https://search.yahoo.com/search"
        self._semaphore = asyncio.Semaphore(2)  # Limit concurrent dorks to prevent 500 errors
        # We only apply Dorking to known hard targets to save time and avoid IP bans
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

    async def fallback_check(self, site: SiteConfig, username: str) -> Optional[CheckResult]:
        """Perform a dork search if the site is a hard target."""
        if not self._is_hard_target(site):
            return None

        logger.info(f"Initiating Deep Search (Dorking) for {site.name} -> {username}")
        
        # Build Dork Query
        domain = site.url_main.replace("https://", "").replace("http://", "").strip("/")
        if "www." in domain:
            domain = domain.replace("www.", "")
            
        dork = f"site:{domain} \"{username}\""
        
        headers = {
            "User-Agent": random.choice(DEFAULT_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        params = {"p": dork}
        
        try:
            # Wait a random bit to spread out requests
            await asyncio.sleep(random.uniform(0.5, 3.0))
            
            async with self._semaphore:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as session:
                    async with session.get(self.base_url, params=params, headers=headers) as response:
                        if response.status != 200:
                            logger.warning(f"Dorking Engine: Yahoo returned status {response.status} for {site.name}")
                            return None
                            
                        html_text = await response.text()
                    
                    # Very simple parsing: look for the expected URL pattern in the search results
                    expected_path = f"/{username}"
                    expected_url = site.url.replace("{username}", username)
                    
                    # We check if the search results contain a link to the profile
                    import re
                    # Look for links in the search results
                    links = re.findall(r'href="([^"]+)"', html_text)
                    
                    found = False
                    for link in links:
                        # Clean up the link (DDG sometimes redirects)
                        if domain in link.lower() and username.lower() in link.lower():
                            # Strong indication
                            found = True
                            break
                            
                    # Alternatively, check if the exact URL or a close variation is present in snippet text
                    if not found and expected_path.lower() in html_text.lower() and domain in html_text.lower():
                        found = True
                        
                    if found:
                        logger.info(f"Deep Search found match for {username} on {site.name}")
                        return CheckResult(
                            site_name=site.name,
                            url=expected_url,
                            status=CheckStatus.CLAIMED,
                            url_main=site.url_main,
                            http_status=200,
                            response_time=0.0,
                            tags=site.tags,
                            fallback_used=True,
                            extracted_data={"dork_match": True}
                        )
                    else:
                        logger.debug(f"Deep Search found NO match for {username} on {site.name}")
                        # Return AVAILABLE instead of UNKNOWN because we thoroughly checked via search engine
                        return CheckResult(
                            site_name=site.name,
                            url=expected_url,
                            status=CheckStatus.AVAILABLE,
                            url_main=site.url_main,
                            http_status=404,
                            response_time=0.0,
                            tags=site.tags,
                            fallback_used=True
                        )

        except Exception as e:
            logger.error(f"Dorking engine error: {e}")
            return None
