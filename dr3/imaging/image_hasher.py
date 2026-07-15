"""
DR3 Intelligence Platform — Image Perceptual Hasher

Computes perceptual hashes for image similarity comparison.
Groups images by visual similarity to detect same face/image
across different platforms.

Uses: pHash (perceptual), aHash (average), dHash (difference)
"""

import logging
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("dr3.imaging.hasher")

# Similarity threshold (0-1, higher = more similar)
SIMILARITY_THRESHOLD = 0.80  # 80% similar = probable match


@dataclass
class HashMatch:
    """A pair of images that are visually similar."""
    image_a_id: str = ""
    image_b_id: str = ""
    image_a_platform: str = ""
    image_b_platform: str = ""
    image_a_username: str = ""
    image_b_username: str = ""
    image_a_url: str = ""
    image_b_url: str = ""
    similarity: float = 0.0
    hash_type: str = "phash"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_a_id": self.image_a_id,
            "image_b_id": self.image_b_id,
            "image_a_platform": self.image_a_platform,
            "image_b_platform": self.image_b_platform,
            "image_a_username": self.image_a_username,
            "image_b_username": self.image_b_username,
            "image_a_url": self.image_a_url,
            "image_b_url": self.image_b_url,
            "similarity": round(self.similarity, 3),
            "hash_type": self.hash_type,
        }


class ImageHasher:
    """
    Computes perceptual hashes for images and finds similar pairs.
    
    Three hash algorithms are used:
    - pHash (perceptual): Best for general image similarity
    - aHash (average): Good for overall brightness patterns
    - dHash (difference): Good for structural patterns
    
    The combined similarity score uses weighted average.
    """

    def compute_hashes(self, assets: list) -> Dict[str, dict]:
        """
        Compute perceptual hashes for all image assets.
        
        Args:
            assets: List of ImageAsset objects with image_bytes
            
        Returns:
            Dict mapping asset_id -> {phash, ahash, dhash, image_obj}
        """
        try:
            import imagehash
            from PIL import Image
        except ImportError:
            logger.warning("imagehash/Pillow not installed — skipping hash computation")
            return {}

        hashes = {}
        for asset in assets:
            if not asset.image_bytes:
                continue
            try:
                img = Image.open(BytesIO(asset.image_bytes))
                # Convert to RGB if needed (some PNGs have alpha)
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                
                phash = imagehash.phash(img, hash_size=12)
                ahash = imagehash.average_hash(img, hash_size=12)
                dhash = imagehash.dhash(img, hash_size=12)
                
                hashes[asset.id] = {
                    "phash": phash,
                    "ahash": ahash,
                    "dhash": dhash,
                    "asset": asset,
                }
                logger.debug(f"Computed hashes for {asset.source_platform}/{asset.source_username}: phash={phash}")
                
            except Exception as e:
                logger.debug(f"Failed to hash image {asset.id}: {e}")
                continue

        return hashes

    def find_matches(self, assets: list) -> List[HashMatch]:
        """
        Find all pairs of visually similar images.
        
        Args:
            assets: List of ImageAsset objects
            
        Returns:
            List of HashMatch objects sorted by similarity (descending)
        """
        hashes = self.compute_hashes(assets)
        if len(hashes) < 2:
            return []

        matches = []
        ids = list(hashes.keys())

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                id_a, id_b = ids[i], ids[j]
                h_a, h_b = hashes[id_a], hashes[id_b]
                
                # Skip comparing same platform (e.g. two GitHub results)
                if (h_a["asset"].source_platform == h_b["asset"].source_platform 
                    and h_a["asset"].source_username == h_b["asset"].source_username):
                    continue

                similarity = self._compute_similarity(h_a, h_b)
                
                if similarity >= SIMILARITY_THRESHOLD:
                    match = HashMatch(
                        image_a_id=id_a,
                        image_b_id=id_b,
                        image_a_platform=h_a["asset"].source_platform,
                        image_b_platform=h_b["asset"].source_platform,
                        image_a_username=h_a["asset"].source_username,
                        image_b_username=h_b["asset"].source_username,
                        image_a_url=h_a["asset"].url,
                        image_b_url=h_b["asset"].url,
                        similarity=similarity,
                        hash_type="combined",
                    )
                    matches.append(match)
                    logger.info(
                        f"Image match: {h_a['asset'].source_platform}/{h_a['asset'].source_username} "
                        f"↔ {h_b['asset'].source_platform}/{h_b['asset'].source_username} "
                        f"({similarity:.1%})"
                    )

        # Sort by similarity descending
        matches.sort(key=lambda m: m.similarity, reverse=True)
        return matches

    def _compute_similarity(self, h_a: dict, h_b: dict) -> float:
        """
        Compute weighted similarity score between two hash sets.
        
        Uses: 50% pHash + 30% aHash + 20% dHash
        Hamming distance is normalized to 0-1 similarity.
        """
        max_bits = 12 * 12  # hash_size^2

        phash_dist = h_a["phash"] - h_b["phash"]
        ahash_dist = h_a["ahash"] - h_b["ahash"]
        dhash_dist = h_a["dhash"] - h_b["dhash"]

        phash_sim = max(0, 1 - (phash_dist / max_bits))
        ahash_sim = max(0, 1 - (ahash_dist / max_bits))
        dhash_sim = max(0, 1 - (dhash_dist / max_bits))

        # Weighted average
        combined = (phash_sim * 0.5) + (ahash_sim * 0.3) + (dhash_sim * 0.2)
        return combined
