"""
Instagram Collector (Direct HTML Title Parsing)
"""
import logging
import time
from bs4 import BeautifulSoup
import aiohttp

from ...core.enums import CheckStatus, CollectionMethod
from ...core.models import CollectionResult
from ..base_collector import BaseCollector

logger = logging.getLogger("dr3.collectors.instagram")

class InstagramCollector(BaseCollector):
    """Collector for Instagram via direct request."""

    def __init__(self):
        pass

    @property
    def platform_name(self) -> str:
        return "Instagram"

    async def collect(self, username: str, **kwargs) -> CollectionResult:
        start_time = time.monotonic()
        url = f"https://www.instagram.com/{username}/"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=True) as response:
                    elapsed = time.monotonic() - start_time
                    html = await response.text()

            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            
            if not title_tag:
                return CollectionResult(
                    platform=self.platform_name,
                    status=CheckStatus.NOT_FOUND,
                    collection_method=CollectionMethod.PROFILE_SCRAPE,
                    username=username,
                    response_time=elapsed,
                )

            title_text = title_tag.text.strip()
            
            if title_text == "Instagram" or title_text == "Page Not Found \u2022 Instagram":
                return CollectionResult(
                    platform=self.platform_name,
                    status=CheckStatus.NOT_FOUND,
                    collection_method=CollectionMethod.PROFILE_SCRAPE,
                    username=username,
                    response_time=elapsed,
                )

            # e.g., "Mark Zuckerberg (@zuck) \u2022 Instagram photos and videos"
            display_name = ""
            if "(@" in title_text:
                display_name = title_text.split("(@")[0].strip()
            else:
                display_name = title_text.split(" \u2022 ")[0].strip()

            # Extract Meta Tags for Bio and Avatar
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
            logger.error(f"Instagram collection error: {e}")
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
