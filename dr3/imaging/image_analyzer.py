"""
DR3 Intelligence Platform — Image Analyzer

Analyzes collected images using:
1. Gemini Vision API (primary) — full AI analysis
2. EXIF metadata extraction (always available)
3. Basic image properties (always available)

When Gemini is available, provides:
- Face description
- Landmark detection
- OCR text extraction
- Object/scene identification
- Location estimation
- Weather/time estimation

When Gemini is NOT available, provides:
- EXIF metadata (GPS, camera, timestamp)
- Image dimensions and properties
- Color analysis
"""

import base64
import json
import logging
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Dict, List, Optional

logger = logging.getLogger("dr3.imaging.analyzer")


@dataclass
class ImageAnalysis:
    """Analysis results for a single image."""
    image_id: str = ""
    image_url: str = ""
    source_platform: str = ""
    source_username: str = ""
    
    # AI Analysis (Gemini Vision)
    description: str = ""
    faces_detected: int = 0
    face_description: str = ""
    landmarks: List[str] = field(default_factory=list)
    ocr_text: List[str] = field(default_factory=list)
    objects: List[str] = field(default_factory=list)
    scene_type: str = ""       # indoor, outdoor, portrait, etc.
    
    # Location estimation
    estimated_country: str = ""
    estimated_city: str = ""
    estimated_region: str = ""
    location_confidence: float = 0.0
    location_evidence: str = ""
    
    # Environmental
    weather: str = ""
    time_of_day: str = ""
    season: str = ""
    
    # EXIF metadata
    exif_gps_lat: Optional[float] = None
    exif_gps_lon: Optional[float] = None
    exif_camera: str = ""
    exif_datetime: str = ""
    exif_software: str = ""
    
    # Image properties
    dominant_colors: List[str] = field(default_factory=list)
    
    # Scoring
    analysis_confidence: float = 0.0
    analysis_method: str = ""   # "gemini_vision" or "exif_only"

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "image_id": self.image_id,
            "image_url": self.image_url,
            "source_platform": self.source_platform,
            "source_username": self.source_username,
            "description": self.description,
            "faces_detected": self.faces_detected,
            "face_description": self.face_description,
            "landmarks": self.landmarks,
            "ocr_text": self.ocr_text,
            "objects": self.objects,
            "scene_type": self.scene_type,
            "estimated_country": self.estimated_country,
            "estimated_city": self.estimated_city,
            "estimated_region": self.estimated_region,
            "location_confidence": self.location_confidence,
            "location_evidence": self.location_evidence,
            "weather": self.weather,
            "time_of_day": self.time_of_day,
            "season": self.season,
            "exif_camera": self.exif_camera,
            "exif_datetime": self.exif_datetime,
            "exif_software": self.exif_software,
            "dominant_colors": self.dominant_colors,
            "analysis_confidence": round(self.analysis_confidence, 2),
            "analysis_method": self.analysis_method,
        }
        if self.exif_gps_lat is not None:
            d["exif_gps"] = {"lat": self.exif_gps_lat, "lon": self.exif_gps_lon}
        return d


class ImageAnalyzer:
    """
    Analyzes images using Gemini Vision (primary) or EXIF-only (fallback).
    """

    def __init__(self, gemini_api_key: str = ""):
        self.gemini_key = gemini_api_key
        self._gemini_model = None

    async def analyze_all(self, assets: list, progress_callback=None) -> List[ImageAnalysis]:
        """
        Analyze all collected image assets.
        
        Args:
            assets: List of ImageAsset with image_bytes
            progress_callback: Async function for updates
            
        Returns:
            List of ImageAnalysis results
        """
        results = []
        total = len(assets)

        for i, asset in enumerate(assets):
            if not asset.image_bytes:
                continue

            if progress_callback and i % 3 == 0:
                await progress_callback(f"تحليل الصورة {i+1}/{total}: {asset.source_platform}/{asset.source_username}")

            analysis = await self._analyze_single(asset)
            if analysis:
                results.append(analysis)

        logger.info(f"Analyzed {len(results)} images ({self._method_label()})")
        return results

    async def _analyze_single(self, asset) -> Optional[ImageAnalysis]:
        """Analyze a single image."""
        analysis = ImageAnalysis(
            image_id=asset.id,
            image_url=asset.url,
            source_platform=asset.source_platform,
            source_username=asset.source_username,
        )

        # Always extract EXIF
        self._extract_exif(asset.image_bytes, analysis)

        # Always extract basic properties
        self._extract_properties(asset.image_bytes, analysis)

        # Try Gemini Vision if available
        if self.gemini_key:
            await self._analyze_with_gemini(asset.image_bytes, analysis)
            analysis.analysis_method = "gemini_vision"
        else:
            analysis.analysis_method = "exif_only"
            analysis.analysis_confidence = 0.3  # Lower confidence for EXIF-only

        return analysis

    def _extract_exif(self, image_bytes: bytes, analysis: ImageAnalysis):
        """Extract EXIF metadata from image."""
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS

            img = Image.open(BytesIO(image_bytes))
            exif_data = img._getexif()
            if not exif_data:
                return

            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)

                if tag == "Make" or tag == "Model":
                    camera_part = str(value).strip()
                    if analysis.exif_camera:
                        analysis.exif_camera += " " + camera_part
                    else:
                        analysis.exif_camera = camera_part

                elif tag == "DateTime" or tag == "DateTimeOriginal":
                    analysis.exif_datetime = str(value)

                elif tag == "Software":
                    analysis.exif_software = str(value)

                elif tag == "GPSInfo":
                    gps = {}
                    for gps_tag_id, gps_value in value.items():
                        gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                        gps[gps_tag] = gps_value

                    lat = self._gps_to_decimal(
                        gps.get("GPSLatitude"),
                        gps.get("GPSLatitudeRef")
                    )
                    lon = self._gps_to_decimal(
                        gps.get("GPSLongitude"),
                        gps.get("GPSLongitudeRef")
                    )
                    if lat is not None and lon is not None:
                        analysis.exif_gps_lat = lat
                        analysis.exif_gps_lon = lon
                        analysis.location_confidence = 0.95
                        analysis.location_evidence = "GPS coordinates from EXIF metadata"
                        logger.info(f"EXIF GPS found: {lat}, {lon}")

        except Exception as e:
            logger.debug(f"EXIF extraction failed: {e}")

    def _extract_properties(self, image_bytes: bytes, analysis: ImageAnalysis):
        """Extract basic image properties and dominant colors."""
        try:
            from PIL import Image

            img = Image.open(BytesIO(image_bytes))
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')

            # Dominant colors — sample 5 most common
            small = img.resize((50, 50))
            pixels = list(small.getdata())
            
            from collections import Counter
            color_counts = Counter(pixels)
            top_colors = color_counts.most_common(5)
            analysis.dominant_colors = [
                f"#{r:02x}{g:02x}{b:02x}" for (r, g, b), _ in top_colors
            ]

        except Exception as e:
            logger.debug(f"Property extraction failed: {e}")

    async def _analyze_with_gemini(self, image_bytes: bytes, analysis: ImageAnalysis):
        """Analyze image using Gemini Vision API."""
        try:
            import google.generativeai as genai
            
            if not self._gemini_model:
                genai.configure(api_key=self.gemini_key)
                self._gemini_model = genai.GenerativeModel("gemini-2.0-flash")

            # Encode image as base64
            b64_image = base64.b64encode(image_bytes).decode("utf-8")
            
            prompt = """Analyze this image for an OSINT investigation. Return a JSON object with these fields:

{
  "description": "Brief description of what's in the image",
  "faces_detected": 0,
  "face_description": "Description of any faces (age range, gender, distinguishing features). Empty if no faces.",
  "landmarks": ["List of any recognizable landmarks, buildings, or places"],
  "ocr_text": ["Any readable text in the image"],
  "objects": ["Notable objects: vehicles, signs, flags, clothing brands, etc."],
  "scene_type": "portrait / outdoor / indoor / urban / nature / screenshot / logo / other",
  "estimated_country": "Country if identifiable, empty if uncertain",
  "estimated_city": "City if identifiable, empty if uncertain",
  "location_confidence": 0.0,
  "location_evidence": "What clues led to the location estimate",
  "weather": "Weather conditions if applicable",
  "time_of_day": "day / night / sunset / dawn / unknown",
  "season": "If determinable from vegetation/clothing"
}

Rules:
- Only state what you can actually see
- Never guess names or identities  
- Confidence 0.0-1.0 for location
- Empty string if uncertain
- Return ONLY valid JSON, no markdown"""

            response = self._gemini_model.generate_content([
                prompt,
                {"mime_type": "image/jpeg", "data": b64_image}
            ])

            if response and response.text:
                text = response.text.strip()
                # Strip markdown code fences if present
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
                
                data = json.loads(text)
                
                analysis.description = data.get("description", "")
                analysis.faces_detected = data.get("faces_detected", 0)
                analysis.face_description = data.get("face_description", "")
                analysis.landmarks = data.get("landmarks", [])
                analysis.ocr_text = data.get("ocr_text", [])
                analysis.objects = data.get("objects", [])
                analysis.scene_type = data.get("scene_type", "")
                
                if not analysis.estimated_country:
                    analysis.estimated_country = data.get("estimated_country", "")
                if not analysis.estimated_city:
                    analysis.estimated_city = data.get("estimated_city", "")
                analysis.estimated_region = data.get("estimated_region", "")
                
                loc_conf = data.get("location_confidence", 0)
                if loc_conf > analysis.location_confidence:
                    analysis.location_confidence = loc_conf
                    analysis.location_evidence = data.get("location_evidence", "")
                
                analysis.weather = data.get("weather", "")
                analysis.time_of_day = data.get("time_of_day", "")
                analysis.season = data.get("season", "")
                analysis.analysis_confidence = 0.85

                logger.info(
                    f"Gemini analysis: {analysis.source_platform}/{analysis.source_username} — "
                    f"faces={analysis.faces_detected}, scene={analysis.scene_type}"
                )

        except ImportError:
            logger.warning("google-generativeai not installed — using EXIF-only fallback")
            analysis.analysis_method = "exif_only"
            analysis.analysis_confidence = 0.3
        except json.JSONDecodeError as e:
            logger.warning(f"Gemini returned invalid JSON: {e}")
            analysis.analysis_confidence = 0.3
        except Exception as e:
            logger.warning(f"Gemini Vision analysis failed: {e}")
            analysis.analysis_confidence = 0.3

    @staticmethod
    def _gps_to_decimal(coords, ref) -> Optional[float]:
        """Convert EXIF GPS coordinates to decimal degrees."""
        if not coords or not ref:
            return None
        try:
            degrees = float(coords[0])
            minutes = float(coords[1])
            seconds = float(coords[2])
            decimal = degrees + (minutes / 60) + (seconds / 3600)
            if ref in ['S', 'W']:
                decimal = -decimal
            return round(decimal, 6)
        except (ValueError, TypeError, IndexError):
            return None

    def _method_label(self) -> str:
        return "Gemini Vision" if self.gemini_key else "EXIF-only"
