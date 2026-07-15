"""
Telegram Collector (Web Parsing)
"""
import logging
import time
from bs4 import BeautifulSoup
import aiohttp

from ...core.enums import CheckStatus, CollectionMethod
from ...core.models import CollectionResult
from ..base_collector import BaseCollector

logger = logging.getLogger("dr3.collectors.telegram")

class TelegramCollector(BaseCollector):
    """Collector for Telegram (t.me)."""

    def __init__(self):
        pass

    @property
    def platform_name(self) -> str:
        return "Telegram"

    async def collect(self, username: str, **kwargs) -> CollectionResult:
        start_time = time.monotonic()
        url = f"https://t.me/{username}"

        try:
            async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"}) as session:
                async with session.get(url, timeout=10) as response:
                    html = await response.text()
                    elapsed = time.monotonic() - start_time

                soup = BeautifulSoup(html, "html.parser")
                
                # Check for existence
                title_tag = soup.find("div", class_="tgme_page_title")
                extra_tag = soup.find("div", class_="tgme_page_extra")
                desc_tag = soup.find("div", class_="tgme_page_description")
                photo_tag = soup.find("img", class_="tgme_page_photo_image")
                
                # Telegram shows "If you have Telegram, you can contact @username right away."
                # even for non-existent users, but for existing users, it shows tgme_page_title
                if not title_tag or not title_tag.text.strip():
                    return CollectionResult(
                        platform=self.platform_name,
                        status=CheckStatus.NOT_FOUND,
                        collection_method=CollectionMethod.PROFILE_SCRAPE,
                        username=username,
                        response_time=elapsed,
                    )

                display_name = title_tag.text.strip()
                bio = desc_tag.text.strip() if desc_tag else ""
                avatar_url = photo_tag["src"] if photo_tag and photo_tag.has_attr("src") else ""
                
                extra_text = extra_tag.text.strip() if extra_tag else ""
                followers = 0
                if "subscribers" in extra_text.lower():
                    try:
                        num_str = extra_text.split(" ")[0].replace(",", "").replace("K", "000").replace("M", "000000")
                        followers = int(float(num_str))
                    except:
                        pass

                return CollectionResult(
                    platform=self.platform_name,
                    status=CheckStatus.FOUND,
                    collection_method=CollectionMethod.PROFILE_SCRAPE,
                    username=username,
                    profile_url=url,
                    display_name=display_name,
                    bio=bio,
                    avatar_url=avatar_url,
                    followers=followers,
                    response_time=elapsed,
                )

        except Exception as e:
            logger.error(f"Telegram collection error: {e}")
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
