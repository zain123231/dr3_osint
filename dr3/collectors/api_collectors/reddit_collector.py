"""
Reddit API Collector
"""
import logging
import time
from typing import Any, Dict, List

from aiohttp import ClientSession, ClientTimeout

from ...core.enums import CheckStatus, CollectionMethod, PlatformTier
from ...core.models import CollectionResult
from ..base_collector import BaseCollector

logger = logging.getLogger("dr3.collectors.reddit")

class RedditCollector(BaseCollector):
    """Identity data collector using Reddit JSON API."""

    API_BASE = "https://www.reddit.com"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    @property
    def platform_name(self) -> str:
        return "Reddit"

    async def close(self) -> None:
        pass

    async def collect(self, username: str, **kwargs) -> CollectionResult:
        start_time = time.monotonic()
        
        try:
            async with ClientSession() as session:
                async with session.get(
                    f"{self.API_BASE}/user/{username}/about.json",
                    headers={"User-Agent": "Mozilla/5.0 DR3_OSINT/3.0"},
                    timeout=ClientTimeout(total=10)
                ) as response:
                    elapsed = time.monotonic() - start_time
                    if response.status == 200:
                        data = await response.json()
                        user = data.get("data", {})
                        
                        if not user or user.get("is_suspended"):
                            return CollectionResult(
                                platform=self.platform_name,
                                status=CheckStatus.NOT_FOUND,
                                collection_method=CollectionMethod.DIRECT_API,
                                username=username,
                                response_time=elapsed,
                            )
                            
                        return CollectionResult(
                            platform=self.platform_name,
                            status=CheckStatus.FOUND,
                            collection_method=CollectionMethod.DIRECT_API,
                            username=user.get("name", username),
                            display_name=user.get("subreddit", {}).get("title", ""),
                            bio=user.get("subreddit", {}).get("public_description", ""),
                            avatar_url=user.get("snoovatar_img", "") or user.get("icon_img", ""),
                            profile_url=f"https://www.reddit.com/user/{username}",
                            http_status=200,
                            response_time=elapsed,
                            platform_tier=PlatformTier.TIER_1,
                            extra_data={
                                "created_utc": user.get("created_utc"),
                                "link_karma": user.get("link_karma"),
                                "comment_karma": user.get("comment_karma"),
                                "is_employee": user.get("is_employee"),
                            }
                        )
                    else:
                        return CollectionResult(
                            platform=self.platform_name,
                            status=CheckStatus.NOT_FOUND,
                            collection_method=CollectionMethod.DIRECT_API,
                            username=username,
                            response_time=elapsed,
                        )

        except Exception as e:
            logger.error(f"Reddit collection error: {e}", exc_info=True)
            return CollectionResult(
                platform=self.platform_name,
                status=CheckStatus.ERROR,
                error_message=str(e),
                collection_method=CollectionMethod.DIRECT_API,
                response_time=time.monotonic() - start_time,
            )
