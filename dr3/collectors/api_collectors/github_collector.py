"""
DR3 Intelligence Platform — GitHub API Collector

GitHub is the HIGHEST PRIORITY seed platform because:
  1. Public API with no authentication required
  2. Richest identity data: name, bio, website, email, avatar, location, company
  3. Public repos reveal linked accounts (Twitter username, website links)
  4. Created_at timestamp for timeline
  5. High reliability — data is user-entered, not scraped

This collector demonstrates the IDEAL pattern for platform-specific collectors.
"""

import logging
from typing import Optional

import aiohttp
from aiohttp import ClientTimeout

from ...core.constants import DEFAULT_USER_AGENTS
from ...core.enums import CheckStatus, CollectionMethod, PlatformTier
from ...core.models import CollectionResult
from ..base_collector import BaseCollector

logger = logging.getLogger("dr3.collector.github")


class GitHubCollector(BaseCollector):
    """
    Collects rich identity data from GitHub's public API.

    API endpoint: https://api.github.com/users/{username}
    Rate limit: 60 requests/hour (unauthenticated), 5000/hour (with token)
    """

    API_BASE = "https://api.github.com"
    PLATFORM = "GitHub"

    def __init__(self, token: str = ""):
        self.token = token

    @property
    def platform_name(self) -> str:
        return "GitHub"

    async def close(self) -> None:
        pass

    async def collect(self, username: str, **kwargs) -> CollectionResult:
        """Collect identity data from GitHub API."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "DR3-Intelligence-Platform/3.0",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        try:
            async with aiohttp.ClientSession(
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=ClientTimeout(total=15)
            ) as session:
                # ── 1. Get user profile ──
                async with session.get(
                    f"{self.API_BASE}/users/{username}",
                    headers=headers,
                ) as response:
                    if response.status == 404:
                        return CollectionResult(
                            platform=self.PLATFORM,
                            status=CheckStatus.NOT_FOUND,
                            collection_method=CollectionMethod.DIRECT_API,
                            username=username,
                            platform_tier=PlatformTier.TIER_1,
                        )
                    elif response.status == 403:
                        logger.warning("GitHub API rate limited")
                        return CollectionResult(
                            platform=self.PLATFORM,
                            status=CheckStatus.ERROR,
                            collection_method=CollectionMethod.DIRECT_API,
                            error_message="GitHub API rate limited",
                            platform_tier=PlatformTier.TIER_1,
                        )
                    elif response.status != 200:
                        return CollectionResult(
                            platform=self.PLATFORM,
                            status=CheckStatus.ERROR,
                            collection_method=CollectionMethod.DIRECT_API,
                            http_status=response.status,
                            error_message=f"GitHub API returned {response.status}",
                            platform_tier=PlatformTier.TIER_1,
                        )

                    user = await response.json()

                # ── 2. Get top repos (for links and usernames) ──
                public_links = []
                discovered_usernames = []

                try:
                    async with session.get(
                        f"{self.API_BASE}/users/{username}/repos?per_page=5&sort=updated",
                        headers=headers,
                    ) as repos_response:
                        if repos_response.status == 200:
                            repos = await repos_response.json()
                            for repo in repos:
                                if repo.get("homepage"):
                                    public_links.append(repo["homepage"])
                except Exception as e:
                    logger.debug(f"Failed to fetch repos: {e}")

                # ── 3. Extract all identity data ──
                # Twitter username is exposed in GitHub API
                twitter = user.get("twitter_username", "")
                if twitter:
                    discovered_usernames.append(twitter)
                    public_links.append(f"https://twitter.com/{twitter}")

                # Blog/website
                blog = user.get("blog", "")
                if blog:
                    if not blog.startswith("http"):
                        blog = f"https://{blog}"
                    public_links.append(blog)

                # Bio may contain links or usernames
                bio = user.get("bio") or ""

                return CollectionResult(
                    platform=self.PLATFORM,
                    status=CheckStatus.FOUND,
                    collection_method=CollectionMethod.DIRECT_API,
                    username=user.get("login", username),
                    display_name=user.get("name") or "",
                    bio=bio,
                    avatar_url=user.get("avatar_url") or "",
                    website=blog,
                    email=user.get("email") or "",
                    location=user.get("location") or "",
                    company=user.get("company") or "",
                    profile_url=user.get("html_url", f"https://github.com/{username}"),
                    created_at=user.get("created_at") or "",
                    last_active=user.get("updated_at") or "",
                    followers=user.get("followers", 0),
                    following=user.get("following", 0),
                    posts=user.get("public_repos", 0),
                    public_links=public_links,
                    discovered_usernames=discovered_usernames,
                    platform_tier=PlatformTier.TIER_1,
                    extra_data={
                        "twitter_username": twitter,
                        "hireable": user.get("hireable"),
                        "public_gists": user.get("public_gists", 0),
                        "type": user.get("type", "User"),
                    },
                )

        except aiohttp.ClientError as e:
            logger.error(f"GitHub API error: {e}")
            return CollectionResult(
                platform=self.PLATFORM,
                status=CheckStatus.ERROR,
                collection_method=CollectionMethod.DIRECT_API,
                error_message=str(e)[:200],
                platform_tier=PlatformTier.TIER_1,
            )
        except Exception as e:
            logger.error(f"GitHub collector error: {e}")
            return CollectionResult(
                platform=self.PLATFORM,
                status=CheckStatus.ERROR,
                collection_method=CollectionMethod.DIRECT_API,
                error_message=str(e)[:200],
                platform_tier=PlatformTier.TIER_1,
            )
