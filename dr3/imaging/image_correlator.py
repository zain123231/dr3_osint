"""
DR3 Intelligence Platform — Image Correlator v2

Cross-correlates image analysis with OSINT data and
produces the combined ImageIntelligenceReport.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger("dr3.imaging.correlator")


@dataclass
class ImageIntelligenceReport:
    """Combined image + geolocation intelligence."""
    total_images_collected: int = 0
    total_images_analyzed: int = 0

    # Image data
    images: List[dict] = field(default_factory=list)
    analyses: List[dict] = field(default_factory=list)
    face_matches: List[dict] = field(default_factory=list)
    correlations: List[dict] = field(default_factory=list)

    # Geolocation
    geolocation: dict = field(default_factory=dict)

    # Aggregates
    faces_detected: int = 0
    all_ocr_text: List[str] = field(default_factory=list)
    all_landmarks: List[str] = field(default_factory=list)
    all_objects: List[str] = field(default_factory=list)
    unique_locations: List[str] = field(default_factory=list)
    gps_points: List[dict] = field(default_factory=list)

    assessment: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_images_collected": self.total_images_collected,
            "total_images_analyzed": self.total_images_analyzed,
            "images": self.images,
            "analyses": self.analyses,
            "face_matches": self.face_matches,
            "correlations": self.correlations,
            "geolocation": self.geolocation,
            "faces_detected": self.faces_detected,
            "all_ocr_text": self.all_ocr_text,
            "all_landmarks": self.all_landmarks,
            "all_objects": self.all_objects,
            "unique_locations": self.unique_locations,
            "gps_points": self.gps_points,
            "assessment": self.assessment,
            "confidence": round(self.confidence, 2),
        }


class ImageCorrelator:
    """Cross-correlates image findings with OSINT investigation data."""

    def correlate(self, assets, analyses, hash_matches, investigation, geo_report=None):
        """Produce combined image intelligence report."""
        report = ImageIntelligenceReport(
            total_images_collected=len(assets),
            total_images_analyzed=len(analyses),
            face_matches=[m.to_dict() for m in hash_matches],
            analyses=[a.to_dict() for a in analyses],
            images=[a.to_dict() for a in assets],
        )

        if geo_report:
            report.geolocation = geo_report.to_dict()

        correlations = []
        total_faces = 0
        locations = set()
        ocr_texts = set()
        landmarks_all = set()
        objects_all = set()
        gps_points = []

        for analysis in analyses:
            total_faces += analysis.faces_detected

            if analysis.estimated_country:
                locations.add(analysis.estimated_country)
            if analysis.estimated_city:
                loc = f"{analysis.estimated_city}, {analysis.estimated_country}" if analysis.estimated_country else analysis.estimated_city
                locations.add(loc)

            lat = analysis.estimated_lat or analysis.exif_gps_lat
            lon = analysis.estimated_lon or analysis.exif_gps_lon
            if lat is not None:
                gps_points.append({
                    "lat": lat, "lon": lon,
                    "source": f"{analysis.source_platform}/{analysis.source_username}",
                    "image_id": analysis.image_id,
                    "confidence": analysis.location_confidence,
                    "location": analysis.estimated_city or analysis.estimated_country or "",
                })

            for text in analysis.ocr_text:
                if text.strip():
                    ocr_texts.add(text.strip())
            for lm in analysis.landmarks:
                if lm.strip():
                    landmarks_all.add(lm.strip())
            for obj in analysis.objects:
                if obj.strip():
                    objects_all.add(obj.strip())

        report.faces_detected = total_faces
        report.unique_locations = list(locations)
        report.all_ocr_text = list(ocr_texts)[:30]
        report.all_landmarks = list(landmarks_all)[:20]
        report.all_objects = list(objects_all)[:30]
        report.gps_points = gps_points

        # ── Face match correlations ──
        for match in hash_matches:
            correlations.append({
                "type": "face_match",
                "description": (
                    f"تطابق بصري بين {match.image_a_platform}/{match.image_a_username} "
                    f"و {match.image_b_platform}/{match.image_b_username}"
                ),
                "confidence": match.similarity,
                "evidence": f"Perceptual hash similarity: {match.similarity:.1%}",
            })

        # ── Location correlations with profile data ──
        profile_locations = set()
        for node in investigation.nodes.values():
            loc = getattr(node, 'location', '') or ''
            if loc.strip():
                profile_locations.add(loc.strip().lower())

        for analysis in analyses:
            if analysis.estimated_country:
                est = analysis.estimated_country.lower()
                for prof in profile_locations:
                    if est in prof or prof in est:
                        correlations.append({
                            "type": "location_match",
                            "description": f"موقع الصورة ({analysis.estimated_country}) يتطابق مع الموقع المعروف",
                            "confidence": analysis.location_confidence,
                            "evidence": "; ".join(analysis.location_reasons[:3]) if analysis.location_reasons else "Location match",
                        })
                        break

        # ── OCR text correlations ──
        targets = set()
        for node in investigation.nodes.values():
            if node.username:
                targets.add(node.username.lower())
            email = getattr(node, 'email', '') or ''
            if email:
                targets.add(email.lower())

        for analysis in analyses:
            for ocr in analysis.ocr_text:
                ocr_lower = ocr.lower()
                for target in targets:
                    if len(target) >= 3 and (target in ocr_lower or ocr_lower in target):
                        correlations.append({
                            "type": "text_match",
                            "description": f"نص مستخرج من الصورة يطابق بيانات التحقيق: '{ocr}'",
                            "confidence": 0.7,
                            "evidence": f"OCR '{ocr}' matches '{target}'",
                        })
                        break

        report.correlations = correlations

        # ── Assessment ──
        parts = []
        if assets:
            parts.append(f"تم جمع {len(assets)} صورة عامة.")
        if total_faces > 0:
            parts.append(f"تم اكتشاف {total_faces} وجه.")
        if hash_matches:
            parts.append(f"{len(hash_matches)} تطابق بصري بين الحسابات.")
        if geo_report and geo_report.most_probable_location:
            parts.append(
                f"الموقع الأكثر احتمالاً: {geo_report.most_probable_location} "
                f"({geo_report.most_probable_confidence:.0%})."
            )
        if locations:
            parts.append(f"المواقع المقدرة: {', '.join(list(locations)[:5])}.")
        if ocr_texts:
            parts.append(f"نصوص مستخرجة: {len(ocr_texts)} نص.")
        if gps_points:
            parts.append(f"{len(gps_points)} إحداثية GPS/تقديرية.")

        report.assessment = " ".join(parts) if parts else "لم يتم اكتشاف معلومات إضافية من الصور."

        confidence = 0.2
        if hash_matches: confidence += 0.15
        if total_faces > 0: confidence += 0.1
        if locations: confidence += 0.15
        if correlations: confidence += 0.1
        if gps_points: confidence += 0.15
        if geo_report and geo_report.most_probable_location: confidence += 0.1
        report.confidence = min(confidence, 0.95)

        logger.info(
            f"Image Intel: {len(assets)} images, {total_faces} faces, "
            f"{len(hash_matches)} matches, {len(correlations)} correlations"
        )

        return report
