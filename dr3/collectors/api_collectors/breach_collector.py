"""
Breach Collector — Checks if a username/email appears in known data breaches.

Uses the free XposedOrNot API (no API key required) to check for breaches.
Falls back to providing manual verification links if the API is unavailable.
"""
import logging
import time
import aiohttp
from aiohttp import ClientTimeout

from ...core.enums import CheckStatus, CollectionMethod
from ...core.models import CollectionResult
from ..base_collector import BaseCollector

logger = logging.getLogger("dr3.collectors.breach")


class BreachCollector(BaseCollector):
    """
    Checks for data breaches using the free XposedOrNot API.
    
    XposedOrNot is a free, no-API-key breach database.
    Endpoint: https://api.xposedornot.com/v1/check-email/{email}
    Returns 200 with breach data if found, 404 if not found.
    """

    XPOSED_API = "https://api.xposedornot.com/v1/check-email"

    @property
    def platform_name(self) -> str:
        return "LeakCheck / Breach Data"

    async def close(self) -> None:
        pass

    async def collect(self, username: str, **kwargs) -> CollectionResult:
        start_time = time.monotonic()

        # Try common email patterns
        email_candidates = []
        if "@" in username:
            email_candidates.append(username)
        else:
            email_candidates.append(f"{username}@gmail.com")

        breaches_found = []
        for email in email_candidates:
            try:
                async with aiohttp.ClientSession(
                    timeout=ClientTimeout(total=10)
                ) as session:
                    url = f"{self.XPOSED_API}/{email}"
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            # XposedOrNot returns breach details
                            if data and data.get("breaches"):
                                breach_list = data["breaches"]
                                if isinstance(breach_list, list):
                                    breaches_found.extend(breach_list)
                                elif isinstance(breach_list, dict):
                                    breaches_found.append(breach_list)
                        # 404 = not found in any breach — this is normal
            except Exception as e:
                logger.debug(f"Breach check error for {email}: {e}")

        elapsed = time.monotonic() - start_time

        if breaches_found:
            breach_count = len(breaches_found)
            logger.info(f"Found {breach_count} breach(es) for {username}")
            return CollectionResult(
                platform=self.platform_name,
                status=CheckStatus.FOUND,
                collection_method=CollectionMethod.DIRECT_API,
                username=username,
                profile_url=f"https://xposedornot.com/search?email={email_candidates[0]}",
                response_time=elapsed,
                extra_data={
                    "breach_count": breach_count,
                    "breaches": [str(b)[:100] for b in breaches_found[:10]],
                    "manual_check_hibp": f"https://haveibeenpwned.com/account/{username}",
                }
            )
        else:
            return CollectionResult(
                platform=self.platform_name,
                status=CheckStatus.NOT_FOUND,
                collection_method=CollectionMethod.DIRECT_API,
                username=username,
                response_time=elapsed,
                extra_data={
                    "manual_check_hibp": f"https://haveibeenpwned.com/account/{username}",
                }
            )
