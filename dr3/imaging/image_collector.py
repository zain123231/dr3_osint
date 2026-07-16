"""
DR3 Intelligence Platform — Public Image Collector v2

Collects ALL publicly available images from investigation results:
1. Profile avatars from discovered nodes
2. Gravatar from discovered emails
3. Reddit user's image posts (via JSON API)
4. Bing Image Search dorking for target username
5. og:image meta tags from discovered profile URLs

Stores full metadata: URL, platform, post_url, date, caption,
hashtags, username. Rate-limited and deduplicated.
"""

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger("dr3.imaging.collector")

MAX_IMAGES = 50
DOWNLOAD_TIMEOUT = 12
CONCURRENT_DOWNLOADS = 5


@dataclass
class ImageAsset:
    """A single collected image with full metadata."""
    id: str = ""
    url: str = ""
    source_type: str = ""       # avatar, gravatar, og_image, reddit_post, bing_search
    source_platform: str = ""
    source_node_id: str = ""
    source_username: str = ""
    image_bytes: bytes = b""
    content_type: str = ""
    width: int = 0
    height: int = 0
    file_size: int = 0
    # v2 metadata
    post_url: str = ""          # Original post URL
    caption: str = ""           # Post caption / alt text
    hashtags: List[str] = field(default_factory=list)
    date: str = ""              # ISO date string

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "source_type": self.source_type,
            "source_platform": self.source_platform,
            "source_node_id": self.source_node_id,
            "source_username": self.source_username,
            "content_type": self.content_type,
            "width": self.width,
            "height": self.height,
            "file_size": self.file_size,
            "post_url": self.post_url,
            "caption": self.caption,
            "hashtags": self.hashtags,
            "date": self.date,
        }


class ImageCollector:
    """
    Collects publicly available images from investigation nodes.

    Sources:
    1. avatar_url from discovered IdentityNodes
    2. Gravatar from discovered email addresses
    3. Reddit image posts (JSON API)
    4. Bing Image Search for username
    5. og:image from profile pages
    """

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._semaphore = asyncio.Semaphore(CONCURRENT_DOWNLOADS)
        self._seen_urls = set()

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
            )
        return self._session

    async def collect(self, investigation, progress_callback=None) -> List[ImageAsset]:
        """Collect images from all sources."""
        image_items = []

        if progress_callback:
            await progress_callback("بدء جمع الصور العامة من جميع المصادر...")

        # ── Source 1: Avatars from discovered nodes ──
        for node_id, node in investigation.nodes.items():
            if node.avatar_url and self._is_valid_image_url(node.avatar_url):
                image_items.append({
                    "url": node.avatar_url.strip(),
                    "source_type": "avatar",
                    "source_platform": node.platform,
                    "source_node_id": node.id,
                    "source_username": node.username,
                    "post_url": node.profile_url or "",
                    "caption": f"Profile photo — {node.platform}",
                    "date": getattr(node, 'account_created', '') or "",
                })

        # ── Source 2: Gravatar from emails ──
        seen_emails = set()
        for node in investigation.nodes.values():
            email = getattr(node, 'email', '') or ''
            if email and email not in seen_emails:
                seen_emails.add(email)
                image_items.append({
                    "url": self._gravatar_url(email),
                    "source_type": "gravatar",
                    "source_platform": "Gravatar",
                    "source_node_id": node.id,
                    "source_username": email,
                    "post_url": f"https://gravatar.com/{hashlib.md5(email.strip().lower().encode()).hexdigest()}",
                    "caption": f"Gravatar for {email}",
                    "date": "",
                })

        # ── Source 3: og:image from profile pages ──
        og_targets = [
            n for n in investigation.nodes.values()
            if n.profile_url and n.platform not in ("Gravatar", "LeakCheck / Breach Data", "Leak/Document", "Dark Web")
        ][:8]  # Limit to 8 profile pages

        if progress_callback:
            await progress_callback(f"جلب og:image من {len(og_targets)} صفحة ملف شخصي...")

        og_tasks = [self._fetch_og_image(n) for n in og_targets]
        og_results = await asyncio.gather(*og_tasks, return_exceptions=True)
        for result in og_results:
            if isinstance(result, dict) and result.get("url"):
                image_items.append(result)

        # ── Source 4: Reddit image posts ──
        reddit_nodes = [n for n in investigation.nodes.values() if n.platform.lower() == "reddit"]
        for rn in reddit_nodes[:3]:
            if progress_callback:
                await progress_callback(f"جلب صور Reddit للمستخدم {rn.username}...")
            reddit_images = await self._fetch_reddit_images(rn.username, rn.id)
            image_items.extend(reddit_images)

        # ── Source 5: Bing Image Search dorking ──
        queries = set()
        if hasattr(investigation, 'initial_query') and investigation.initial_query:
            queries.add(investigation.initial_query)
        for node in investigation.nodes.values():
            if node.is_seed and node.username:
                queries.add(node.username)

        for q in list(queries)[:2]:
            if progress_callback:
                await progress_callback(f"بحث Bing Images عن '{q}'...")
            bing_images = await self._bing_image_search(q)
            image_items.extend(bing_images)

        # ── Deduplicate by URL ──
        unique_items = []
        for item in image_items:
            url_hash = hashlib.md5(item["url"].encode()).hexdigest()[:16]
            if url_hash not in self._seen_urls:
                self._seen_urls.add(url_hash)
                unique_items.append(item)

        # Limit
        unique_items = unique_items[:MAX_IMAGES]

        if progress_callback:
            await progress_callback(f"تحميل {len(unique_items)} صورة عامة...")

        logger.info(f"Collecting {len(unique_items)} images from {len(investigation.nodes)} nodes")

        # ── Download all images ──
        tasks = [self._download_image(item) for item in unique_items]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        assets = []
        for i, result in enumerate(results):
            if isinstance(result, ImageAsset) and result.image_bytes:
                assets.append(result)
            elif isinstance(result, Exception):
                logger.debug(f"Download failed: {unique_items[i]['url']}: {result}")

        if progress_callback:
            await progress_callback(f"تم تحميل {len(assets)} صورة بنجاح من أصل {len(unique_items)}")

        logger.info(f"Successfully collected {len(assets)} images")
        return assets

    async def _fetch_og_image(self, node) -> dict:
        """Fetch og:image meta tag from a profile page."""
        try:
            session = await self._get_session()
            async with session.get(node.profile_url, allow_redirects=True) as resp:
                if resp.status != 200:
                    return {}
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                og_img = soup.find("meta", property="og:image")
                if og_img and og_img.get("content"):
                    img_url = og_img["content"]
                    if img_url and img_url.startswith("http") and self._is_valid_image_url(img_url):
                        # Check for og:description as caption
                        caption = ""
                        og_desc = soup.find("meta", property="og:description")
                        if og_desc and og_desc.get("content"):
                            caption = og_desc["content"][:200]
                        return {
                            "url": img_url,
                            "source_type": "og_image",
                            "source_platform": node.platform,
                            "source_node_id": node.id,
                            "source_username": node.username,
                            "post_url": node.profile_url,
                            "caption": caption,
                            "date": "",
                        }
        except Exception as e:
            logger.debug(f"og:image fetch failed for {node.profile_url}: {e}")
        return {}

    async def _fetch_reddit_images(self, username: str, node_id: str) -> List[dict]:
        """Fetch image posts from Reddit user's submissions."""
        images = []
        try:
            session = await self._get_session()
            url = f"https://www.reddit.com/user/{username}/submitted.json?limit=25&sort=new"
            async with session.get(url, headers={"User-Agent": "DR3_OSINT/3.0"}) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                posts = data.get("data", {}).get("children", [])
                for post in posts:
                    pd = post.get("data", {})
                    post_url = f"https://www.reddit.com{pd.get('permalink', '')}"
                    img_url = pd.get("url_overridden_by_dest", "") or pd.get("url", "")

                    # Check if it's an image URL
                    if not img_url:
                        continue
                    if not any(ext in img_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                        # Check for Reddit preview images
                        preview = pd.get("preview", {})
                        if preview and preview.get("images"):
                            img_url = preview["images"][0].get("source", {}).get("url", "")
                            img_url = img_url.replace("&amp;", "&")
                        else:
                            continue

                    if not img_url or not img_url.startswith("http"):
                        continue

                    # Extract date
                    created_utc = pd.get("created_utc", 0)
                    from datetime import datetime
                    date_str = datetime.utcfromtimestamp(created_utc).isoformat() if created_utc else ""

                    images.append({
                        "url": img_url,
                        "source_type": "reddit_post",
                        "source_platform": "Reddit",
                        "source_node_id": node_id,
                        "source_username": username,
                        "post_url": post_url,
                        "caption": pd.get("title", "")[:200],
                        "hashtags": [],
                        "date": date_str,
                    })

                    if len(images) >= 10:
                        break

        except Exception as e:
            logger.debug(f"Reddit image fetch failed for {username}: {e}")
        return images

    async def _bing_image_search(self, query: str) -> List[dict]:
        """Search Bing Images for public images of the target."""
        images = []
        try:
            session = await self._get_session()
            search_url = f"https://www.bing.com/images/search?q={quote(query)}&first=1&count=15"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            }
            async with session.get(search_url, headers=headers) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")

                # Extract image URLs from Bing results
                img_links = soup.find_all("a", class_="iusc")
                for link in img_links[:10]:
                    m_attr = link.get("m", "")
                    if not m_attr:
                        continue
                    import json
                    try:
                        m_data = json.loads(m_attr)
                        img_url = m_data.get("murl", "")
                        page_url = m_data.get("purl", "")
                        title = m_data.get("t", "")
                    except (json.JSONDecodeError, TypeError):
                        continue

                    if not img_url or not img_url.startswith("http"):
                        continue
                    if not self._is_valid_image_url(img_url):
                        continue

                    images.append({
                        "url": img_url,
                        "source_type": "bing_search",
                        "source_platform": "Bing Images",
                        "source_node_id": "",
                        "source_username": query,
                        "post_url": page_url,
                        "caption": title[:200] if title else "",
                        "date": "",
                    })

        except Exception as e:
            logger.debug(f"Bing image search failed for '{query}': {e}")
        return images

    async def _download_image(self, item: dict) -> ImageAsset:
        """Download a single image with rate limiting."""
        async with self._semaphore:
            session = await self._get_session()
            try:
                async with session.get(item["url"]) as resp:
                    if resp.status != 200:
                        return ImageAsset()

                    content_type = resp.headers.get("Content-Type", "")
                    if not any(t in content_type for t in ["image/", "octet-stream"]):
                        return ImageAsset()

                    data = await resp.read()
                    if len(data) > 8 * 1024 * 1024 or len(data) < 200:
                        return ImageAsset()

                    width, height = 0, 0
                    try:
                        from PIL import Image
                        img = Image.open(BytesIO(data))
                        width, height = img.size
                    except Exception:
                        pass

                    asset_id = hashlib.md5(data).hexdigest()[:12]

                    return ImageAsset(
                        id=asset_id,
                        url=item["url"],
                        source_type=item.get("source_type", ""),
                        source_platform=item.get("source_platform", ""),
                        source_node_id=item.get("source_node_id", ""),
                        source_username=item.get("source_username", ""),
                        image_bytes=data,
                        content_type=content_type,
                        width=width,
                        height=height,
                        file_size=len(data),
                        post_url=item.get("post_url", ""),
                        caption=item.get("caption", ""),
                        hashtags=item.get("hashtags", []),
                        date=item.get("date", ""),
                    )

            except asyncio.TimeoutError:
                return ImageAsset()
            except Exception as e:
                logger.debug(f"Error downloading {item['url']}: {e}")
                return ImageAsset()

    def _is_valid_image_url(self, url: str) -> bool:
        if not url or not url.startswith("http"):
            return False
        skip = ["default_profile", "default-user", "no-avatar", "placeholder",
                "blank.gif", "1x1", "spacer.gif", "/static/img/default"]
        url_lower = url.lower()
        return not any(p in url_lower for p in skip)

    @staticmethod
    def _gravatar_url(email: str) -> str:
        email_hash = hashlib.md5(email.strip().lower().encode()).hexdigest()
        return f"https://www.gravatar.com/avatar/{email_hash}?s=200&d=404"

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
