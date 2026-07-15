"""
Twitter API / Scraping Collector
"""
import logging
import time
import aiohttp

from ...core.enums import CheckStatus, CollectionMethod, PlatformTier
from ...core.models import CollectionResult
from ..base_collector import BaseCollector

logger = logging.getLogger("dr3.collectors.twitter")

class TwitterCollector(BaseCollector):
    """Collector for Twitter/X using the syndication API."""

    def __init__(self):
        pass

    @property
    def platform_name(self) -> str:
        return "Twitter"

    async def collect(self, username: str, **kwargs) -> CollectionResult:
        start_time = time.monotonic()
        url = f"https://twitter.com/{username}"

        try:
            async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/115.0.0.0 Safari/537.36"}) as session:
                async with session.get(url, timeout=10) as response:
                    elapsed = time.monotonic() - start_time
                    
                    if response.status == 400 or response.status == 404:
                        return CollectionResult(
                            platform=self.platform_name,
                            status=CheckStatus.NOT_FOUND,
                            collection_method=CollectionMethod.PROFILE_SCRAPE,
                            username=username,
                            response_time=elapsed,
                        )

                    try:
                        html = await response.text()
                    except aiohttp.client_exceptions.ClientPayloadError as e:
                        logger.warning(f"Failed to read full response for {username}: {e}")
                        # If the payload fails to read fully, we can't reliably parse it, so return NOT_FOUND or ERROR.
                        return CollectionResult(
                            platform=self.platform_name,
                            status=CheckStatus.ERROR,
                            collection_method=CollectionMethod.PROFILE_SCRAPE,
                            username=username,
                            response_time=elapsed,
                            error_message="Payload error",
                        )
                    
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, "html.parser")
                    title_tag = soup.find("title")
                    title_text = title_tag.text.strip() if title_tag else ""
                    
                    if title_text == "X" or title_text == "Twitter" or not title_text or "Profile / X" in title_text:
                        return CollectionResult(
                            platform=self.platform_name,
                            status=CheckStatus.NOT_FOUND,
                            collection_method=CollectionMethod.PROFILE_SCRAPE,
                            username=username,
                            response_time=elapsed,
                        )
                        
                    # Format: "Elon Musk (@elonmusk) / X"
                    display_name = ""
                    if "(@" in title_text:
                        display_name = title_text.split("(@")[0].strip()
                    else:
                        display_name = title_text.split(" / ")[0].strip()

                    # Extract Meta Tags
                    bio = ""
                    avatar_url = ""
                    meta_desc = soup.find("meta", property="og:description")
                    if meta_desc and meta_desc.get("content"):
                        bio = meta_desc["content"]
                    
                    meta_img = soup.find("meta", property="og:image")
                    if meta_img and meta_img.get("content"):
                        avatar_url = meta_img["content"]

                    return CollectionResult(
                        platform=self.platform_name,
                        status=CheckStatus.FOUND,
                        collection_method=CollectionMethod.PROFILE_SCRAPE,
                        username=username,
                        profile_url=url,
                        display_name=display_name,
                        bio=bio,
                        avatar_url=avatar_url,
                        response_time=elapsed,
                    )

        except Exception as e:
            logger.error(f"Twitter collection error: {e}")
            return CollectionResult(
                platform=self.platform_name,
                status=CheckStatus.ERROR,
                collection_method=CollectionMethod.PROFILE_SCRAPE,
                username=username,
                response_time=time.monotonic() - start_time,
                error_message=str(e),
            )

    async def close(self) -> None:
        pass
