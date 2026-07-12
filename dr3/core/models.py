"""
DR3 OSINT — Data Models (Pydantic)
All core data structures used throughout the platform.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .enums import (
    CheckMethod,
    CheckStatus,
    ConfidenceLevel,
    EvidenceType,
)


@dataclass
class SiteConfig:
    """Configuration for a single site in the database."""
    name: str
    url_main: str
    url: str
    check_type: str = "status_code"
    url_probe: Optional[str] = None
    url_subpath: str = ""
    username_claimed: str = ""
    username_unclaimed: str = ""
    regex_check: Optional[str] = None
    disabled: bool = False
    similar_search: bool = False
    ignore_403: bool = False
    tags: List[str] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    presence_strs: List[str] = field(default_factory=list)
    absence_strs: List[str] = field(default_factory=list)
    request_head_only: bool = False
    get_params: Dict[str, Any] = field(default_factory=dict)
    alexa_rank: Optional[int] = None
    engine: Optional[str] = None
    engine_data: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    protocol: str = ""
    activation: Dict[str, Any] = field(default_factory=dict)
    site_type: str = "username"

    @property
    def is_enabled(self) -> bool:
        return not self.disabled

    @property
    def reliability_score(self) -> float:
        """Calculate site reliability based on check method and configuration."""
        score = 50.0
        if self.check_type == "message":
            if self.absence_strs and self.presence_strs:
                score = 85.0
            elif self.absence_strs or self.presence_strs:
                score = 65.0
        elif self.check_type == "status_code":
            score = 60.0
        elif self.check_type == "response_url":
            score = 70.0
        if self.alexa_rank and self.alexa_rank < 10000:
            score += 10
        elif self.alexa_rank and self.alexa_rank < 100000:
            score += 5
        return min(score, 100.0)


@dataclass
class CheckResult:
    """Result of checking a single site for a username."""
    site_name: str
    url: str
    status: CheckStatus
    url_main: str = ""
    http_status: int = 0
    response_time: float = 0.0
    error_message: str = ""
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    fallback_used: bool = False

    @property
    def is_found(self) -> bool:
        return self.status == CheckStatus.CLAIMED


@dataclass
class Evidence:
    """A piece of evidence supporting identity correlation."""
    evidence_type: EvidenceType
    description: str
    weight: float
    source_site: str = ""
    target_site: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProfileData:
    """Extracted profile data from a found account."""
    site_name: str
    url: str
    username: str
    display_name: str = ""
    bio: str = ""
    avatar_url: str = ""
    location: str = ""
    email: str = ""
    website: str = ""
    language: str = ""
    created_at: str = ""
    followers: int = 0
    following: int = 0
    posts: int = 0
    tags: List[str] = field(default_factory=list)
    extra_data: Dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.POSSIBLE
    evidence: List[Evidence] = field(default_factory=list)
    is_false_positive: bool = False
    false_positive_reason: str = ""
    fallback_used: bool = False


@dataclass
class IdentityReport:
    """Complete identity investigation report."""
    target_username: str
    search_id: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_sites_checked: int = 0
    total_found: int = 0
    total_confirmed: int = 0
    total_possible: int = 0
    overall_confidence: float = 0.0
    overall_confidence_level: ConfidenceLevel = ConfidenceLevel.POSSIBLE
    profiles: List[ProfileData] = field(default_factory=list)
    evidence_summary: List[Evidence] = field(default_factory=list)
    cross_platform_analysis: str = ""
    ai_analysis: str = ""
    risk_assessment: str = ""
    suggested_next_steps: List[str] = field(default_factory=list)

    @property
    def executive_summary(self) -> str:
        confirmed = len([p for p in self.profiles if p.confidence_score >= 70])
        possible = len([p for p in self.profiles if 30 <= p.confidence_score < 70])
        return (
            f"Investigation of username '{self.target_username}' across "
            f"{self.total_sites_checked} platforms identified "
            f"{confirmed} confirmed accounts and {possible} possible matches. "
            f"Overall confidence: {self.overall_confidence:.1f}% "
            f"({self.overall_confidence_level.value.replace('_', ' ').title()})."
        )

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0


@dataclass
class SearchProgress:
    """Real-time search progress for WebSocket updates."""
    search_id: str
    phase: str
    progress: float  # 0-100
    total_sites: int = 0
    checked_sites: int = 0
    found_count: int = 0
    current_site: str = ""
    message: str = ""
    is_complete: bool = False
    results: Optional[List[Dict[str, Any]]] = None
