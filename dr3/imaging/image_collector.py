"""
DR3 Intelligence Platform — Image Collector

Collects publicly available images from investigation results:
- Profile avatars from discovered accounts
- Gravatar images from discovered emails
- Open Graph images from profile pages
- Website favicons

Design: Non-blocking async with rate limiting and timeouts.
Maximum 20 images per investigation for performance.
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger("dr3.imaging.collector")

# Rate limiting
MAX_IMAGES = 20
DOWNLOAD_TIMEOUT = 10  # seconds per image
CONCURRENT_DOWNLOADS = 3


@dataclass
class ImageAsset:
    """A single collected image with metadata."""
    id: str = ""
    url: str = ""
    source_type: str = ""       # avatar, gravatar, og_image, favicon
    source_platform: str = ""   # GitHub, Reddit, etc.
    source_node_id: str = ""    # Link back to the IdentityNode
    source_username: str = ""
    image_bytes: bytes = b""
    content_type: str = ""
    width: int = 0
    height: int = 0
    file_size: int = 0

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
        }


class ImageCollector:
    """
    Collects publicly available images from investigation nodes.
    
    Sources:
    1. avatar_url from discovered IdentityNodes
    2. Gravatar from discovered email addresses
    3. og:image from profile URLs (lightweight HEAD/fetch)
    """

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._semaphore = asyncio.Semaphore(CONCURRENT_DOWNLOADS)

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
        return self._session

    async def collect(self, investigation, progress_callback=None) -> List[ImageAsset]:
        """
        Collect images from all nodes in the investigation.
        
        Args:
            investigation: Investigation object with nodes
            progress_callback: Async function for updates
            
        Returns:
            List of ImageAsset with downloaded image bytes
        """
        image_urls = []
        
        # 1. Collect avatar URLs from discovered nodes
        for node_id, node in investigation.nodes.items():
            if node.avatar_url and node.avatar_url.strip():
                # Skip default/placeholder avatars
                url = node.avatar_url.strip()
                if self._is_valid_image_url(url):
                    image_urls.append({
                        "url": url,
                        "source_type": "avatar",
                        "source_platform": node.platform,
                        "source_node_id": node.id,
                        "source_username": node.username,
                    })

        # 2. Collect Gravatar from discovered emails
        seen_emails = set()
        for node in investigation.nodes.values():
            email = getattr(node, 'email', '') or ''
            if email and email not in seen_emails:
                seen_emails.add(email)
                gravatar_url = self._gravatar_url(email)
                image_urls.append({
                    "url": gravatar_url,
                    "source_type": "gravatar",
                    "source_platform": "Gravatar",
                    "source_node_id": node.id,
                    "source_username": email,
                })

        # Deduplicate by URL
        seen_urls = set()
        unique_urls = []
        for item in image_urls:
            normalized = item["url"].split("?")[0].lower()
            if normalized not in seen_urls:
                seen_urls.add(normalized)
                unique_urls.append(item)

        # Limit to MAX_IMAGES
        unique_urls = unique_urls[:MAX_IMAGES]
        
        if progress_callback:
            await progress_callback(f"جمع {len(unique_urls)} صورة عامة من الحسابات المكتشفة...")

        logger.info(f"Collecting {len(unique_urls)} images from {len(investigation.nodes)} nodes")

        # 3. Download all images concurrently (with semaphore)
        tasks = [self._download_image(item) for item in unique_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        assets = []
        for i, result in enumerate(results):
            if isinstance(result, ImageAsset) and result.image_bytes:
                assets.append(result)
            elif isinstance(result, Exception):
                logger.debug(f"Image download failed: {unique_urls[i]['url']}: {result}")

        if progress_callback:
            await progress_callback(f"تم تحميل {len(assets)} صورة بنجاح من أصل {len(unique_urls)}")

        logger.info(f"Successfully collected {len(assets)} images")
        return assets

    async def _download_image(self, item: dict) -> ImageAsset:
        """Download a single image with rate limiting."""
        async with self._semaphore:
            session = await self._get_session()
            try:
                async with session.get(item["url"]) as resp:
                    if resp.status != 200:
                        return ImageAsset()
                    
                    content_type = resp.headers.get("Content-Type", "")
                    if not content_type.startswith("image/"):
                        return ImageAsset()
                    
                    # Limit to 5MB
                    data = await resp.read()
                    if len(data) > 5 * 1024 * 1024:
                        return ImageAsset()
                    if len(data) < 100:
                        # Too small, likely a 1x1 pixel
                        return ImageAsset()

                    # Get dimensions using Pillow
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
                        source_type=item["source_type"],
                        source_platform=item["source_platform"],
                        source_node_id=item["source_node_id"],
                        source_username=item["source_username"],
                        image_bytes=data,
                        content_type=content_type,
                        width=width,
                        height=height,
                        file_size=len(data),
                    )

            except asyncio.TimeoutError:
                logger.debug(f"Timeout downloading {item['url']}")
                return ImageAsset()
            except Exception as e:
                logger.debug(f"Error downloading {item['url']}: {e}")
                return ImageAsset()

    def _is_valid_image_url(self, url: str) -> bool:
        """Filter out default/placeholder avatar URLs."""
        if not url:
            return False
        
        # Skip common default avatar patterns
        skip_patterns = [
            "default_profile",
            "default-user",
            "no-avatar",
            "placeholder",
            "blank.gif",
            "1x1",
            "spacer.gif",
            "default.jpg",
            "/static/img/default",
        ]
        url_lower = url.lower()
        for pattern in skip_patterns:
            if pattern in url_lower:
                return False
        
        # Must be http(s)
        if not url.startswith("http"):
            return False
            
        return True

    @staticmethod
    def _gravatar_url(email: str) -> str:
        """Generate Gravatar URL from email address."""
        email_hash = hashlib.md5(email.strip().lower().encode()).hexdigest()
        return f"https://www.gravatar.com/avatar/{email_hash}?s=200&d=404"

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
