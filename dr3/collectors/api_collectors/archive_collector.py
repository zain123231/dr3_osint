import logging
import time
import aiohttp
from ...core.enums import CheckStatus, CollectionMethod
from ...core.models import CollectionResult
from ..base_collector import BaseCollector

logger = logging.getLogger("dr3.collectors.archive")

class ArchiveCollector(BaseCollector):
    @property
    def platform_name(self) -> str:
        return "Wayback Machine"

    async def close(self) -> None:
        pass

    async def collect(self, url: str, **kwargs) -> CollectionResult:
        start_time = time.monotonic()
        api_url = f"https://archive.org/wayback/available?url={url}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        snapshots = data.get("archived_snapshots", {})
                        if "closest" in snapshots and snapshots["closest"].get("available"):
                            archive_url = snapshots["closest"]["url"]
                            return CollectionResult(
                                platform=self.platform_name,
                                status=CheckStatus.FOUND,
                                collection_method=CollectionMethod.DIRECT_API,
                                username=url, # using url as username field for generic response
                                profile_url=archive_url,
                                response_time=time.monotonic() - start_time,
                                extra_data={"timestamp": snapshots["closest"].get("timestamp")}
                            )
        except Exception as e:
            logger.error(f"Archive error: {e}")
            
        return CollectionResult(
            platform=self.platform_name,
            status=CheckStatus.NOT_FOUND,
            collection_method=CollectionMethod.DIRECT_API,
            username=url,
            response_time=time.monotonic() - start_time
        )
