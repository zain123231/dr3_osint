"""
DR3 Intelligence Platform — Image Correlator

Cross-correlates image analysis findings with existing OSINT data:
- OCR text matched against usernames, emails, domains
- Estimated locations matched against known profile locations
- Face groups confirm/deny same-person hypothesis
- EXIF timestamps vs account creation dates

Produces a combined ImageIntelligenceReport.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger("dr3.imaging.correlator")


@dataclass 
class ImageCorrelation:
    """A single correlation finding."""
    correlation_type: str = ""   # face_match, location_match, text_match, timeline_match
    description: str = ""
    confidence: float = 0.0
    evidence: str = ""
    source_image_id: str = ""
    related_node_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.correlation_type,
            "description": self.description,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
            "source_image_id": self.source_image_id,
            "related_node_id": self.related_node_id,
        }


@dataclass
class ImageIntelligenceReport:
    """Combined image intelligence assessment."""
    total_images_collected: int = 0
    total_images_analyzed: int = 0
    face_matches: List[dict] = field(default_factory=list)
    analyses: List[dict] = field(default_factory=list)
    correlations: List[dict] = field(default_factory=list)
    images: List[dict] = field(default_factory=list)
    
    # Aggregate findings
    faces_detected: int = 0
    unique_locations: List[str] = field(default_factory=list)
    all_ocr_text: List[str] = field(default_factory=list)
    all_landmarks: List[str] = field(default_factory=list)
    all_objects: List[str] = field(default_factory=list)
    
    # Locations with GPS
    gps_points: List[dict] = field(default_factory=list)
    
    # Overall assessment
    assessment: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_images_collected": self.total_images_collected,
            "total_images_analyzed": self.total_images_analyzed,
            "face_matches": self.face_matches,
            "analyses": self.analyses,
            "correlations": self.correlations,
            "images": self.images,
            "faces_detected": self.faces_detected,
            "unique_locations": self.unique_locations,
            "all_ocr_text": self.all_ocr_text,
            "all_landmarks": self.all_landmarks,
            "all_objects": self.all_objects,
            "gps_points": self.gps_points,
            "assessment": self.assessment,
            "confidence": round(self.confidence, 2),
        }


class ImageCorrelator:
    """
    Cross-correlates image findings with OSINT investigation data.
    """

    def correlate(
        self,
        assets: list,
        analyses: list,
        hash_matches: list,
        investigation,
    ) -> ImageIntelligenceReport:
        """
        Produce combined image intelligence report.
        
        Args:
            assets: List of ImageAsset
            analyses: List of ImageAnalysis
            hash_matches: List of HashMatch
            investigation: The Investigation object
            
        Returns:
            ImageIntelligenceReport with all findings
        """
        report = ImageIntelligenceReport(
            total_images_collected=len(assets),
            total_images_analyzed=len(analyses),
            face_matches=[m.to_dict() for m in hash_matches],
            analyses=[a.to_dict() for a in analyses],
            images=[a.to_dict() for a in assets],
        )

        correlations = []

        # ── 1. Face Match Correlations ──
        for match in hash_matches:
            corr = ImageCorrelation(
                correlation_type="face_match",
                description=(
                    f"تطابق بصري بين صورة {match.image_a_platform}/{match.image_a_username} "
                    f"و {match.image_b_platform}/{match.image_b_username}"
                ),
                confidence=match.similarity,
                evidence=f"Perceptual hash similarity: {match.similarity:.1%}",
                source_image_id=match.image_a_id,
            )
            correlations.append(corr)

        # ── 2. Aggregate Findings ──
        total_faces = 0
        locations = set()
        ocr_texts = []
        landmarks_all = []
        objects_all = []
        gps_points = []

        for analysis in analyses:
            total_faces += analysis.faces_detected

            # Locations
            if analysis.estimated_country:
                locations.add(analysis.estimated_country)
            if analysis.estimated_city:
                locations.add(f"{analysis.estimated_city}, {analysis.estimated_country}")

            # GPS
            if analysis.exif_gps_lat is not None:
                gps_points.append({
                    "lat": analysis.exif_gps_lat,
                    "lon": analysis.exif_gps_lon,
                    "source": f"{analysis.source_platform}/{analysis.source_username}",
                    "image_id": analysis.image_id,
                })

            # OCR
            for text in analysis.ocr_text:
                if text.strip():
                    ocr_texts.append(text.strip())

            # Landmarks
            for lm in analysis.landmarks:
                if lm.strip():
                    landmarks_all.append(lm.strip())

            # Objects
            for obj in analysis.objects:
                if obj.strip():
                    objects_all.append(obj.strip())

        report.faces_detected = total_faces
        report.unique_locations = list(locations)
        report.all_ocr_text = list(set(ocr_texts))
        report.all_landmarks = list(set(landmarks_all))
        report.all_objects = list(set(objects_all))[:20]  # Cap at 20
        report.gps_points = gps_points

        # ── 3. Location Correlation ──
        # Compare image-estimated locations with profile locations
        profile_locations = set()
        for node in investigation.nodes.values():
            loc = getattr(node, 'location', '') or ''
            if loc.strip():
                profile_locations.add(loc.strip().lower())

        for analysis in analyses:
            if analysis.estimated_country:
                est_loc = analysis.estimated_country.lower()
                for prof_loc in profile_locations:
                    if est_loc in prof_loc or prof_loc in est_loc:
                        corr = ImageCorrelation(
                            correlation_type="location_match",
                            description=(
                                f"موقع الصورة ({analysis.estimated_country}) "
                                f"يتطابق مع الموقع المعروف من الملف الشخصي"
                            ),
                            confidence=analysis.location_confidence,
                            evidence=analysis.location_evidence or "Location match between image analysis and profile data",
                            source_image_id=analysis.image_id,
                        )
                        correlations.append(corr)
                        break

        # ── 4. OCR Text Correlation ──
        # Check if OCR text matches any usernames, emails, or domains
        target_strings = set()
        for node in investigation.nodes.values():
            if node.username:
                target_strings.add(node.username.lower())
            if node.email:
                target_strings.add(node.email.lower())
            if node.website:
                target_strings.add(node.website.lower())

        for analysis in analyses:
            for ocr in analysis.ocr_text:
                ocr_lower = ocr.lower()
                for target in target_strings:
                    if target in ocr_lower or ocr_lower in target:
                        corr = ImageCorrelation(
                            correlation_type="text_match",
                            description=f"نص مستخرج من الصورة يطابق بيانات التحقيق: '{ocr}'",
                            confidence=0.7,
                            evidence=f"OCR text '{ocr}' matches investigation data '{target}'",
                            source_image_id=analysis.image_id,
                        )
                        correlations.append(corr)
                        break

        report.correlations = [c.to_dict() for c in correlations]

        # ── 5. Overall Assessment ──
        assessment_parts = []
        if len(assets) > 0:
            assessment_parts.append(f"تم جمع {len(assets)} صورة عامة من الحسابات المكتشفة.")
        if total_faces > 0:
            assessment_parts.append(f"تم اكتشاف {total_faces} وجه في الصور.")
        if hash_matches:
            assessment_parts.append(
                f"تم اكتشاف {len(hash_matches)} تطابق بصري بين الحسابات "
                f"(يشير إلى احتمال أن نفس الشخص)."
            )
        if locations:
            assessment_parts.append(f"المواقع المقدرة: {', '.join(locations)}.")
        if ocr_texts:
            assessment_parts.append(f"نصوص مستخرجة: {', '.join(ocr_texts[:5])}.")
        if gps_points:
            assessment_parts.append(f"تم اكتشاف {len(gps_points)} إحداثيات GPS.")

        report.assessment = " ".join(assessment_parts) if assessment_parts else "لم يتم اكتشاف معلومات استخباراتية إضافية من الصور."
        
        # Confidence based on findings richness
        confidence = 0.3  # Base
        if hash_matches:
            confidence += 0.2
        if total_faces > 0:
            confidence += 0.1
        if locations:
            confidence += 0.1
        if correlations:
            confidence += 0.1
        if gps_points:
            confidence += 0.1
        report.confidence = min(confidence, 0.95)

        logger.info(
            f"Image Intelligence: {len(assets)} images, {total_faces} faces, "
            f"{len(hash_matches)} matches, {len(correlations)} correlations"
        )

        return report
