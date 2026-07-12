"""
DR3 OSINT — Sites Database Loader
Loads and manages the sites database from JSON, with filtering and ranking.
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..core.models import SiteConfig

logger = logging.getLogger("dr3.sites_db")


class SitesDatabase:
    """Manages the database of sites that can be checked for usernames."""

    def __init__(self):
        self._sites: List[SiteConfig] = []
        self._engines: Dict[str, Dict[str, Any]] = {}
        self._tags: List[str] = []

    @property
    def sites(self) -> List[SiteConfig]:
        return self._sites

    @property
    def enabled_sites(self) -> List[SiteConfig]:
        return [s for s in self._sites if s.is_enabled]

    @property
    def total_count(self) -> int:
        return len(self._sites)

    @property
    def enabled_count(self) -> int:
        return len(self.enabled_sites)

    @property
    def all_tags(self) -> List[str]:
        tags = set()
        for site in self._sites:
            tags.update(site.tags)
        return sorted(tags)

    def load_from_file(self, filepath: str) -> "SitesDatabase":
        """Load sites database from a JSON file."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Sites database not found: {filepath}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return self._load_from_dict(data)

    def _load_from_dict(self, data: dict) -> "SitesDatabase":
        """Parse JSON data into SiteConfig objects."""
        engines_data = data.get("engines", {})
        sites_data = data.get("sites", {})
        self._tags = data.get("tags", [])

        # Load engines
        for engine_name, engine_info in engines_data.items():
            self._engines[engine_name] = engine_info

        # Load sites
        for site_name, site_info in sites_data.items():
            try:
                site = self._parse_site(site_name, site_info)
                self._sites.append(site)
            except Exception as e:
                logger.debug(f"Skipping site {site_name}: {e}")

        logger.info(f"Loaded {len(self._sites)} sites ({self.enabled_count} enabled)")
        return self

    def _parse_site(self, name: str, info: Dict[str, Any]) -> SiteConfig:
        """Parse a single site entry from the database."""
        # Apply engine defaults if applicable
        engine_name = info.get("engine")
        if engine_name and engine_name in self._engines:
            engine_data = self._engines[engine_name].get("site", {})
            merged = {**engine_data, **info}
        else:
            merged = info

        # Map camelCase keys to snake_case
        def to_snake(s: str) -> str:
            return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()

        mapped = {}
        for k, v in merged.items():
            mapped[to_snake(k)] = v

        return SiteConfig(
            name=name,
            url_main=mapped.get("url_main", ""),
            url=mapped.get("url", ""),
            check_type=mapped.get("check_type", "status_code"),
            url_probe=mapped.get("url_probe"),
            url_subpath=mapped.get("url_subpath", ""),
            username_claimed=mapped.get("username_claimed", ""),
            username_unclaimed=mapped.get("username_unclaimed", ""),
            regex_check=mapped.get("regex_check"),
            disabled=mapped.get("disabled", False),
            similar_search=mapped.get("similar_search", False),
            ignore_403=mapped.get("ignore403", False),
            tags=mapped.get("tags", []),
            headers=mapped.get("headers", {}),
            errors=mapped.get("errors", {}),
            presence_strs=mapped.get("presense_strs", mapped.get("presence_strs", [])),
            absence_strs=mapped.get("absence_strs", []),
            request_head_only=mapped.get("request_head_only", False),
            get_params=mapped.get("get_params", {}),
            alexa_rank=mapped.get("alexa_rank"),
            engine=engine_name,
            engine_data=mapped.get("engine_data", {}),
            source=mapped.get("source"),
            protocol=mapped.get("protocol", ""),
            activation=mapped.get("activation", {}),
            site_type=mapped.get("type", "username"),
        )

    def get_ranked_sites(
        self,
        top: int = sys.maxsize,
        tags: Optional[List[str]] = None,
        names: Optional[List[str]] = None,
        include_disabled: bool = False,
        id_type: str = "username",
    ) -> List[SiteConfig]:
        """Get filtered and ranked list of sites."""
        filtered = []
        norm_tags = [t.lower() for t in (tags or [])]
        norm_names = [n.lower() for n in (names or [])]

        for site in self._sites:
            # Filter disabled
            if site.disabled and not include_disabled:
                continue

            # Filter by ID type
            if site.site_type != id_type:
                continue

            # Filter by tags
            if norm_tags:
                site_tags = [t.lower() for t in site.tags]
                engine_match = site.engine and site.engine.lower() in norm_tags
                tag_match = bool(set(site_tags) & set(norm_tags))
                if not (engine_match or tag_match):
                    continue

            # Filter by names
            if norm_names:
                name_match = site.name.lower() in norm_names
                url_match = any(n in site.url_main.lower() for n in norm_names)
                if not (name_match or url_match):
                    continue

            filtered.append(site)

        # Sort by Alexa rank (lower = more popular = first)
        filtered.sort(key=lambda s: s.alexa_rank or sys.maxsize)

        return filtered[:top]

    def get_site_by_name(self, name: str) -> Optional[SiteConfig]:
        """Find a site by name."""
        for site in self._sites:
            if site.name.lower() == name.lower():
                return site
        return None

    def extract_username_from_url(self, url: str) -> Optional[Tuple[str, str]]:
        """Try to extract a username from a URL by matching against known sites."""
        url_lower = url.lower()
        for site in self._sites:
            if not site.url:
                continue
            # Build a basic pattern from the site URL template
            try:
                pattern_base = site.url.split("{username}")[0]
                # Remove template variables
                pattern_base = re.sub(r"\{[^}]+\}", "", pattern_base)
                if pattern_base and pattern_base in url:
                    # Extract the username part
                    remaining = url[len(pattern_base):]
                    username = remaining.split("/")[0].split("?")[0]
                    if username:
                        return username, site.name
            except Exception:
                continue
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        tag_counts: Dict[str, int] = {}
        for site in self._sites:
            for tag in site.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        return {
            "total_sites": self.total_count,
            "enabled_sites": self.enabled_count,
            "disabled_sites": self.total_count - self.enabled_count,
            "total_tags": len(self.all_tags),
            "top_tags": sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:20],
            "engines": list(self._engines.keys()),
        }
