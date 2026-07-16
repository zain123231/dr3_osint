"""
DR3 Intelligence Platform — Geolocation Intelligence Engine

Clusters image analysis results by location, calculates
"Most Probable Location" with weighted confidence,
detects movement patterns, and generates the final
GeolocationReport.
"""

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("dr3.imaging.geo")


@dataclass
class LocationCluster:
    """A cluster of images estimated to be from the same location."""
    location_name: str = ""
    country: str = ""
    city: str = ""
    state: str = ""
    image_count: int = 0
    avg_confidence: float = 0.0
    landmarks: List[str] = field(default_factory=list)
    image_ids: List[str] = field(default_factory=list)
    lat: Optional[float] = None
    lon: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "location_name": self.location_name,
            "country": self.country,
            "city": self.city,
            "state": self.state,
            "image_count": self.image_count,
            "avg_confidence": round(self.avg_confidence, 2),
            "landmarks": self.landmarks,
            "image_ids": self.image_ids,
        }
        if self.lat is not None:
            d["lat"] = self.lat
            d["lon"] = self.lon
        return d


@dataclass
class MovementEvent:
    """A location at a point in time."""
    date: str = ""
    location: str = ""
    country: str = ""
    city: str = ""
    confidence: float = 0.0
    image_id: str = ""
    image_url: str = ""
    platform: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "location": self.location,
            "country": self.country,
            "city": self.city,
            "confidence": round(self.confidence, 2),
            "image_id": self.image_id,
            "image_url": self.image_url,
            "platform": self.platform,
        }


@dataclass
class GeolocationReport:
    """Complete geolocation intelligence report."""
    most_probable_location: str = ""
    most_probable_country: str = ""
    most_probable_city: str = ""
    most_probable_confidence: float = 0.0
    evidence_summary: str = ""
    evidence_count: int = 0

    location_clusters: List[dict] = field(default_factory=list)
    repeated_landmarks: List[str] = field(default_factory=list)
    repeated_places: List[str] = field(default_factory=list)
    movement_timeline: List[dict] = field(default_factory=list)

    map_markers: List[dict] = field(default_factory=list)
    country_distribution: Dict[str, int] = field(default_factory=dict)
    city_distribution: Dict[str, int] = field(default_factory=dict)

    total_images: int = 0
    total_with_location: int = 0
    total_with_gps: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "most_probable_location": self.most_probable_location,
            "most_probable_country": self.most_probable_country,
            "most_probable_city": self.most_probable_city,
            "most_probable_confidence": round(self.most_probable_confidence, 2),
            "evidence_summary": self.evidence_summary,
            "evidence_count": self.evidence_count,
            "location_clusters": self.location_clusters,
            "repeated_landmarks": self.repeated_landmarks,
            "repeated_places": self.repeated_places,
            "movement_timeline": self.movement_timeline,
            "map_markers": self.map_markers,
            "country_distribution": self.country_distribution,
            "city_distribution": self.city_distribution,
            "total_images": self.total_images,
            "total_with_location": self.total_with_location,
            "total_with_gps": self.total_with_gps,
        }


class GeolocationEngine:
    """
    Clusters image analyses by location and produces
    the final GeolocationReport.
    """

    def analyze(self, assets: list, analyses: list) -> GeolocationReport:
        """
        Produce geolocation intelligence from image analyses.

        Args:
            assets: List of ImageAsset
            analyses: List of ImageAnalysis

        Returns:
            GeolocationReport
        """
        report = GeolocationReport(total_images=len(assets))

        # Build lookup
        analysis_map = {a.image_id: a for a in analyses}
        asset_map = {a.id: a for a in assets}

        # ── Collect location data ──
        located = []  # Analyses with location estimates
        countries = Counter()
        cities = Counter()
        all_landmarks = Counter()
        map_markers = []

        for analysis in analyses:
            has_location = bool(analysis.estimated_country or analysis.estimated_city)
            has_gps = analysis.estimated_lat is not None

            if has_gps:
                report.total_with_gps += 1

            if has_location or has_gps:
                report.total_with_location += 1
                located.append(analysis)

            if analysis.estimated_country:
                countries[analysis.estimated_country] += 1
            if analysis.estimated_city:
                city_key = f"{analysis.estimated_city}, {analysis.estimated_country}" if analysis.estimated_country else analysis.estimated_city
                cities[city_key] += 1

            for lm in analysis.landmarks:
                if lm.strip():
                    all_landmarks[lm.strip()] += 1

            # Map markers
            lat = analysis.estimated_lat or analysis.exif_gps_lat
            lon = analysis.estimated_lon or analysis.exif_gps_lon
            if lat is not None and lon is not None:
                asset = asset_map.get(analysis.image_id)
                map_markers.append({
                    "lat": lat,
                    "lon": lon,
                    "image_id": analysis.image_id,
                    "image_url": analysis.image_url,
                    "platform": analysis.source_platform,
                    "username": analysis.source_username,
                    "location": analysis.estimated_city or analysis.estimated_country or "Unknown",
                    "confidence": analysis.location_confidence,
                    "reasons": analysis.location_reasons[:5],
                    "description": analysis.description[:100],
                    "post_url": asset.post_url if asset else "",
                })

        report.map_markers = map_markers
        report.country_distribution = dict(countries.most_common(10))
        report.city_distribution = dict(cities.most_common(10))

        # ── Repeated landmarks ──
        report.repeated_landmarks = [lm for lm, count in all_landmarks.most_common(10) if count >= 1]

        # ── Location clusters ──
        clusters = {}
        for analysis in located:
            # Cluster key: city if available, else country
            key = analysis.estimated_city or analysis.estimated_country or "Unknown"
            if key not in clusters:
                clusters[key] = LocationCluster(
                    location_name=key,
                    country=analysis.estimated_country,
                    city=analysis.estimated_city,
                    state=analysis.estimated_state,
                )
            c = clusters[key]
            c.image_count += 1
            c.image_ids.append(analysis.image_id)
            c.avg_confidence = (
                (c.avg_confidence * (c.image_count - 1) + analysis.location_confidence)
                / c.image_count
            )
            for lm in analysis.landmarks:
                if lm.strip() and lm.strip() not in c.landmarks:
                    c.landmarks.append(lm.strip())
            if analysis.estimated_lat is not None and c.lat is None:
                c.lat = analysis.estimated_lat
                c.lon = analysis.estimated_lon

        sorted_clusters = sorted(
            clusters.values(),
            key=lambda c: c.image_count * c.avg_confidence,
            reverse=True,
        )
        report.location_clusters = [c.to_dict() for c in sorted_clusters]

        # Repeated places
        report.repeated_places = [
            c.location_name for c in sorted_clusters if c.image_count >= 2
        ]

        # ── Most Probable Location ──
        if sorted_clusters:
            top = sorted_clusters[0]
            report.most_probable_location = top.location_name
            report.most_probable_country = top.country
            report.most_probable_city = top.city
            report.most_probable_confidence = min(top.avg_confidence + 0.05 * top.image_count, 0.98)

            # Evidence summary
            parts = []
            parts.append(f"{top.image_count} صور تشير إلى هذا الموقع")
            if top.landmarks:
                parts.append(f"{len(top.landmarks)} معلم مكتشف: {', '.join(top.landmarks[:4])}")
            if report.repeated_places:
                parts.append(f"{len(report.repeated_places)} مواقع متكررة")

            report.evidence_summary = ". ".join(parts)
            report.evidence_count = top.image_count

        # ── Movement Timeline ──
        timeline = []
        for analysis in analyses:
            asset = asset_map.get(analysis.image_id)
            date = (asset.date if asset else "") or analysis.exif_datetime or ""
            location = analysis.estimated_city or analysis.estimated_country or ""

            if date or location:
                timeline.append(MovementEvent(
                    date=date,
                    location=location,
                    country=analysis.estimated_country,
                    city=analysis.estimated_city,
                    confidence=analysis.location_confidence,
                    image_id=analysis.image_id,
                    image_url=analysis.image_url,
                    platform=analysis.source_platform,
                ))

        # Sort by date
        timeline.sort(key=lambda e: e.date or "")
        report.movement_timeline = [e.to_dict() for e in timeline]

        logger.info(
            f"Geolocation: {report.total_with_location}/{report.total_images} located, "
            f"most probable: {report.most_probable_location} ({report.most_probable_confidence:.0%})"
        )

        return report
