"""
DR3 Intelligence Platform — Image Analyzer v2

Deep geolocation analysis using Gemini Vision API.
For EVERY image: detect landmarks, estimate location with
confidence score and detailed reasons.

Fallback: EXIF metadata + basic properties when no API key.
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
    """Complete analysis results for a single image."""
    image_id: str = ""
    image_url: str = ""
    source_platform: str = ""
    source_username: str = ""

    # AI Analysis
    description: str = ""
    faces_detected: int = 0
    face_description: str = ""
    landmarks: List[str] = field(default_factory=list)
    ocr_text: List[str] = field(default_factory=list)
    objects: List[str] = field(default_factory=list)
    scene_type: str = ""

    # Deep geolocation
    estimated_country: str = ""
    estimated_state: str = ""
    estimated_city: str = ""
    estimated_district: str = ""
    location_confidence: float = 0.0
    location_reasons: List[str] = field(default_factory=list)

    # Environment
    weather: str = ""
    time_of_day: str = ""
    season: str = ""
    architecture_style: str = ""
    vegetation_type: str = ""
    language_detected: str = ""
    transportation: List[str] = field(default_factory=list)

    # EXIF
    exif_gps_lat: Optional[float] = None
    exif_gps_lon: Optional[float] = None
    exif_camera: str = ""
    exif_datetime: str = ""
    exif_software: str = ""

    # Properties
    dominant_colors: List[str] = field(default_factory=list)
    analysis_confidence: float = 0.0
    analysis_method: str = ""

    # Estimated coordinates from AI
    estimated_lat: Optional[float] = None
    estimated_lon: Optional[float] = None

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
            "estimated_state": self.estimated_state,
            "estimated_city": self.estimated_city,
            "estimated_district": self.estimated_district,
            "location_confidence": round(self.location_confidence, 2),
            "location_reasons": self.location_reasons,
            "weather": self.weather,
            "time_of_day": self.time_of_day,
            "season": self.season,
            "architecture_style": self.architecture_style,
            "vegetation_type": self.vegetation_type,
            "language_detected": self.language_detected,
            "transportation": self.transportation,
            "exif_camera": self.exif_camera,
            "exif_datetime": self.exif_datetime,
            "exif_software": self.exif_software,
            "dominant_colors": self.dominant_colors,
            "analysis_confidence": round(self.analysis_confidence, 2),
            "analysis_method": self.analysis_method,
        }
        if self.exif_gps_lat is not None:
            d["exif_gps"] = {"lat": self.exif_gps_lat, "lon": self.exif_gps_lon}
        if self.estimated_lat is not None:
            d["estimated_coords"] = {"lat": self.estimated_lat, "lon": self.estimated_lon}
        return d


class ImageAnalyzer:
    """Analyzes images with Gemini Vision for deep geolocation."""

    GEOLOCATION_PROMPT = """You are an expert OSINT geolocation analyst. Analyze this image and provide intelligence.

Return ONLY a valid JSON object with these fields:

{
  "description": "Brief description of image content",
  "faces_detected": 0,
  "face_description": "Age range, gender, distinguishing visible features. Empty if no faces.",
  "landmarks": ["Any recognizable landmarks, famous buildings, monuments, bridges, mountains"],
  "ocr_text": ["Any readable text: signs, shop names, vehicle plates, banners, menus"],
  "objects": ["Notable objects: vehicles, flags, clothing brands, food, devices, weapons, tools"],
  "scene_type": "portrait / outdoor / indoor / urban / nature / screenshot / logo / aerial / street",
  "estimated_country": "Country name if identifiable",
  "estimated_state": "State/province if identifiable",
  "estimated_city": "City if identifiable",
  "estimated_district": "District/neighborhood if identifiable",
  "estimated_lat": null,
  "estimated_lon": null,
  "location_confidence": 0.0,
  "location_reasons": ["List every clue: street signs, architecture, vegetation, language, landmarks, terrain, road markings, license plates, shop names, building style, climate indicators"],
  "weather": "Weather conditions visible",
  "time_of_day": "day / night / sunset / dawn / golden_hour / unknown",
  "season": "Season if determinable",
  "architecture_style": "Islamic / European / East Asian / Modern / Colonial / etc.",
  "vegetation_type": "Desert / Tropical / Temperate / Mediterranean / etc.",
  "language_detected": "Language of visible text",
  "transportation": ["Types of vehicles, road infrastructure visible"]
}

RULES:
- Be thorough. List EVERY geographic clue you see.
- For location_confidence: 0.0 = no clue, 0.3 = vague continent, 0.5 = likely country, 0.7 = likely city, 0.9 = specific location
- If you recognize a specific landmark, set confidence high and provide coordinates
- For estimated_lat/lon: provide approximate coordinates if confidence >= 0.5, otherwise null
- List ALL reasons for your location estimate
- Never guess identities or names of people
- Return ONLY valid JSON, no markdown fences"""

    def __init__(self, gemini_api_key: str = ""):
        self.gemini_key = gemini_api_key
        self._model = None

    async def analyze_all(self, assets: list, progress_callback=None) -> List[ImageAnalysis]:
        """Analyze all images."""
        results = []
        total = len(assets)

        for i, asset in enumerate(assets):
            if not asset.image_bytes:
                continue

            if progress_callback:
                pct = int((i / max(total, 1)) * 100)
                await progress_callback(
                    f"تحليل الصورة {i+1}/{total}: {asset.source_platform}/{asset.source_username} [{pct}%]"
                )

            analysis = await self._analyze_single(asset)
            if analysis:
                results.append(analysis)

        method = "Gemini Vision" if self.gemini_key else "EXIF-only"
        logger.info(f"Analyzed {len(results)} images ({method})")
        return results

    async def _analyze_single(self, asset) -> Optional[ImageAnalysis]:
        analysis = ImageAnalysis(
            image_id=asset.id,
            image_url=asset.url,
            source_platform=asset.source_platform,
            source_username=asset.source_username,
        )

        self._extract_exif(asset.image_bytes, analysis)
        self._extract_properties(asset.image_bytes, analysis)

        if self.gemini_key:
            await self._analyze_with_gemini(asset.image_bytes, analysis)
            analysis.analysis_method = "gemini_vision"
        else:
            analysis.analysis_method = "exif_only"
            analysis.analysis_confidence = 0.2

        return analysis

    def _extract_exif(self, image_bytes: bytes, analysis: ImageAnalysis):
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS

            img = Image.open(BytesIO(image_bytes))
            exif_data = img._getexif()
            if not exif_data:
                return

            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag in ("Make", "Model"):
                    part = str(value).strip()
                    if analysis.exif_camera:
                        analysis.exif_camera += " " + part
                    else:
                        analysis.exif_camera = part
                elif tag in ("DateTime", "DateTimeOriginal"):
                    analysis.exif_datetime = str(value)
                elif tag == "Software":
                    analysis.exif_software = str(value)
                elif tag == "GPSInfo":
                    gps = {}
                    for gps_tag_id, gps_value in value.items():
                        gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                        gps[gps_tag] = gps_value
                    lat = self._gps_to_decimal(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
                    lon = self._gps_to_decimal(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))
                    if lat is not None and lon is not None:
                        analysis.exif_gps_lat = lat
                        analysis.exif_gps_lon = lon
                        analysis.estimated_lat = lat
                        analysis.estimated_lon = lon
                        analysis.location_confidence = max(analysis.location_confidence, 0.95)
                        analysis.location_reasons.append("GPS coordinates from EXIF metadata")
        except Exception as e:
            logger.debug(f"EXIF extraction failed: {e}")

    def _extract_properties(self, image_bytes: bytes, analysis: ImageAnalysis):
        try:
            from PIL import Image
            from collections import Counter

            img = Image.open(BytesIO(image_bytes))
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')
            small = img.resize((50, 50))
            pixels = list(small.getdata())
            color_counts = Counter(pixels)
            top_colors = color_counts.most_common(5)
            analysis.dominant_colors = [f"#{r:02x}{g:02x}{b:02x}" for (r, g, b), _ in top_colors]
        except Exception as e:
            logger.debug(f"Property extraction failed: {e}")

    async def _analyze_with_gemini(self, image_bytes: bytes, analysis: ImageAnalysis):
        try:
            import google.generativeai as genai

            if not self._model:
                genai.configure(api_key=self.gemini_key)
                self._model = genai.GenerativeModel("gemini-2.0-flash")

            b64 = base64.b64encode(image_bytes).decode("utf-8")

            response = self._model.generate_content([
                self.GEOLOCATION_PROMPT,
                {"mime_type": "image/jpeg", "data": b64}
            ])

            if not response or not response.text:
                return

            text = response.text.strip()
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

            analysis.estimated_country = data.get("estimated_country", "")
            analysis.estimated_state = data.get("estimated_state", "")
            analysis.estimated_city = data.get("estimated_city", "")
            analysis.estimated_district = data.get("estimated_district", "")
            analysis.location_confidence = max(
                analysis.location_confidence,
                data.get("location_confidence", 0)
            )
            analysis.location_reasons.extend(data.get("location_reasons", []))

            # Coordinates from AI
            est_lat = data.get("estimated_lat")
            est_lon = data.get("estimated_lon")
            if est_lat is not None and est_lon is not None:
                if analysis.estimated_lat is None:
                    analysis.estimated_lat = est_lat
                    analysis.estimated_lon = est_lon

            analysis.weather = data.get("weather", "")
            analysis.time_of_day = data.get("time_of_day", "")
            analysis.season = data.get("season", "")
            analysis.architecture_style = data.get("architecture_style", "")
            analysis.vegetation_type = data.get("vegetation_type", "")
            analysis.language_detected = data.get("language_detected", "")
            analysis.transportation = data.get("transportation", [])
            analysis.analysis_confidence = 0.85

            logger.info(
                f"Gemini geo: {analysis.source_platform}/{analysis.source_username} → "
                f"{analysis.estimated_city or analysis.estimated_country or 'unknown'} "
                f"({analysis.location_confidence:.0%})"
            )

        except ImportError:
            analysis.analysis_method = "exif_only"
            analysis.analysis_confidence = 0.2
        except json.JSONDecodeError as e:
            logger.warning(f"Gemini returned invalid JSON: {e}")
            analysis.analysis_confidence = 0.2
        except Exception as e:
            logger.warning(f"Gemini analysis failed: {e}")
            analysis.analysis_confidence = 0.2

    @staticmethod
    def _gps_to_decimal(coords, ref) -> Optional[float]:
        if not coords or not ref:
            return None
        try:
            d = float(coords[0])
            m = float(coords[1])
            s = float(coords[2])
            dec = d + (m / 60) + (s / 3600)
            if ref in ('S', 'W'):
                dec = -dec
            return round(dec, 6)
        except (ValueError, TypeError, IndexError):
            return None
