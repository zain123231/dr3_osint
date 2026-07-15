"""
DR3 Intelligence Platform — Identity & Investigation Models

Entity-centric design: Everything is an Entity with properties and
relationships. The investigation graph IS the intelligence product,
not a side-effect of data collection.

Model hierarchy:
  Investigation
    └── InvestigationGraph
          ├── IdentityNode (accounts, emails, domains, etc.)
          ├── IdentityEdge (relationships with evidence chains)
          └── EvidenceChain (per-edge evidence)
    └── DigitalIdentityProfile (the intelligence product)
    └── IntelligenceReport (the final output)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .enums import (
    CheckStatus,
    CollectionMethod,
    ConfidenceLevel,
    EntityType,
    InvestigationPhase,
    InvestigationStatus,
    PlatformTier,
    QueryType,
    RelationType,
    RiskLevel,
)
from .evidence import Evidence, EvidenceChain


# ═══════════════════════════════════════════════════════════════
# COLLECTION RESULTS
# ═══════════════════════════════════════════════════════════════

@dataclass
class CollectionResult:
    """
    Raw data collected from a single platform.

    This is the OUTPUT of a Collector — not yet analyzed or scored.
    It contains everything the collector could extract.
    The Evidence Engine will later evaluate this data.
    """
    platform: str
    status: CheckStatus = CheckStatus.NOT_FOUND
    collection_method: CollectionMethod = CollectionMethod.STATUS_CODE

    # Identity data extracted
    username: str = ""
    display_name: str = ""
    bio: str = ""
    avatar_url: str = ""
    website: str = ""
    email: str = ""
    location: str = ""
    language: str = ""
    company: str = ""
    profile_url: str = ""

    # Temporal data
    created_at: str = ""
    last_active: str = ""

    # Social metrics
    followers: int = 0
    following: int = 0
    posts: int = 0

    # Expansion targets — new leads for the investigation
    public_links: List[str] = field(default_factory=list)
    discovered_usernames: List[str] = field(default_factory=list)
    mentioned_emails: List[str] = field(default_factory=list)
    mentioned_names: List[str] = field(default_factory=list)

    # Raw data for deep analysis
    extra_data: Dict[str, Any] = field(default_factory=dict)
    raw_html: str = ""

    # HTTP metadata
    http_status: int = 0
    response_time: float = 0.0
    error_message: str = ""

    # Platform metadata
    tags: List[str] = field(default_factory=list)
    platform_tier: PlatformTier = PlatformTier.TIER_3
    fallback_used: bool = False

    @property
    def is_found(self) -> bool:
        return self.status == CheckStatus.FOUND

    @property
    def identity_richness(self) -> int:
        """
        How many identity-relevant fields are populated.
        Used to rank seed candidates — richer = better seed.
        """
        fields = [
            self.display_name, self.bio, self.avatar_url,
            self.website, self.email, self.location,
            self.company, self.created_at,
        ]
        return sum(1 for f in fields if f and str(f).strip())

    @property
    def has_expansion_targets(self) -> bool:
        """Whether this result provides new leads for expansion."""
        return bool(
            self.public_links or
            self.discovered_usernames or
            self.mentioned_emails or
            self.mentioned_names or
            self.website or
            self.email
        )


@dataclass
class SearchTarget:
    """A target for identity expansion — a new lead to investigate."""
    query: str
    query_type: QueryType
    source_platform: str = ""
    source_entity_id: str = ""
    depth: int = 0                # How many hops from the seed
    priority: float = 0.0        # Higher = investigate sooner


# ═══════════════════════════════════════════════════════════════
# GRAPH ENTITIES
# ═══════════════════════════════════════════════════════════════

@dataclass
class IdentityNode:
    """
    A node in the intelligence graph.

    Every discovered entity (account, email, domain, etc.)
    becomes a node. Nodes have properties and are connected
    by edges (IdentityEdge) with evidence chains.

    Design note: Nodes store extracted identity data, NOT
    raw collection data. The collector produces a CollectionResult;
    the extractor transforms it into IdentityNode properties.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    entity_type: EntityType = EntityType.ACCOUNT

    # Platform identity
    platform: str = ""
    username: str = ""
    profile_url: str = ""

    # Identity attributes
    display_name: str = ""
    bio: str = ""
    avatar_url: str = ""
    avatar_hash: str = ""          # Perceptual hash for comparison
    website: str = ""
    email: str = ""
    location: str = ""
    language: str = ""
    company: str = ""
    external_links: List[str] = field(default_factory=list)

    # Temporal
    account_created: str = ""
    last_active: str = ""

    # Social
    followers: int = 0
    following: int = 0
    posts: int = 0

    # Scoring
    confidence: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.UNSUBSTANTIATED
    evidence_chain: EvidenceChain = field(default_factory=EvidenceChain)

    # Graph metadata
    is_seed: bool = False
    depth: int = 0                 # Hops from seed
    platform_tier: PlatformTier = PlatformTier.TIER_3
    collection_method: CollectionMethod = CollectionMethod.STATUS_CODE

    # Tags and extra data
    tags: List[str] = field(default_factory=list)
    extra_data: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    discovered_at: datetime = field(default_factory=datetime.now)

    @property
    def identity_richness(self) -> int:
        fields = [
            self.display_name, self.bio, self.avatar_url,
            self.website, self.email, self.location,
            self.company, self.account_created,
        ]
        return sum(1 for f in fields if f and str(f).strip())

    @property
    def label(self) -> str:
        """Human-readable label for graph display."""
        if self.display_name:
            return f"{self.display_name} ({self.platform})"
        if self.username:
            return f"@{self.username} ({self.platform})"
        return f"{self.platform}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "entity_type": self.entity_type.value,
            "platform": self.platform,
            "username": self.username,
            "profile_url": self.profile_url,
            "display_name": self.display_name,
            "bio": self.bio[:300] if self.bio else "",
            "avatar_url": self.avatar_url,
            "website": self.website,
            "email": self.email,
            "location": self.location,
            "language": self.language,
            "company": self.company,
            "external_links": self.external_links,
            "account_created": self.account_created,
            "followers": self.followers,
            "following": self.following,
            "posts": self.posts,
            "confidence": round(self.confidence, 1),
            "confidence_level": self.confidence_level.value,
            "is_seed": self.is_seed,
            "depth": self.depth,
            "platform_tier": self.platform_tier.value,
            "tags": self.tags,
            "discovered_at": self.discovered_at.isoformat(),
            "evidence_summary": self.evidence_chain.to_dict(),
        }


@dataclass
class IdentityEdge:
    """
    A relationship between two nodes in the intelligence graph.

    Every edge has:
      - A type (SAME_PERSON, LIKELY_SAME, DIRECT_LINK, etc.)
      - An evidence chain (why we believe this relationship exists)
      - A strength score (derived from evidence chain)
      - A human-readable explanation

    Design note: Edges are directional but semantically bidirectional.
    "A links to B" creates an edge from A to B, but the intelligence
    applies to both nodes.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    source_id: str = ""
    target_id: str = ""
    relationship_type: RelationType = RelationType.POSSIBLE_MATCH
    evidence_chain: EvidenceChain = field(default_factory=EvidenceChain)
    strength: float = 0.0
    explanation: str = ""
    discovered_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship_type": self.relationship_type.value,
            "strength": round(self.strength, 1),
            "explanation": self.explanation,
            "evidence": self.evidence_chain.to_dict(),
        }


# ═══════════════════════════════════════════════════════════════
# INTELLIGENCE PRODUCTS
# ═══════════════════════════════════════════════════════════════

@dataclass
class DigitalIdentityProfile:
    """
    The PRIMARY intelligence product of an investigation.

    This is NOT "a list of found accounts."
    This is a reconstructed digital identity — what an
    intelligence analyst would produce after manual investigation.

    It answers: "Who is this person, based on their digital footprint?"
    """
    # Identity summary
    primary_name: str = ""
    known_usernames: List[str] = field(default_factory=list)
    known_emails: List[str] = field(default_factory=list)
    known_websites: List[str] = field(default_factory=list)
    known_locations: List[str] = field(default_factory=list)
    known_languages: List[str] = field(default_factory=list)
    probable_profession: str = ""
    bio_summary: str = ""

    # Platform presence
    confirmed_platforms: List[Dict[str, Any]] = field(default_factory=list)
    probable_platforms: List[Dict[str, Any]] = field(default_factory=list)

    # Confidence and Scoring
    identity_score: float = 0.0
    overall_confidence: float = 0.0
    overall_confidence_level: ConfidenceLevel = ConfidenceLevel.UNSUBSTANTIATED
    confidence_explanation: str = ""

    # Risk assessment
    risk_level: RiskLevel = RiskLevel.MINIMAL
    risk_explanation: str = ""

    # Evidence summary
    total_evidence_count: int = 0
    positive_evidence_count: int = 0
    negative_evidence_count: int = 0
    definitive_evidence_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_name": self.primary_name,
            "known_usernames": self.known_usernames,
            "known_emails": self.known_emails,
            "known_websites": self.known_websites,
            "known_locations": self.known_locations,
            "known_languages": self.known_languages,
            "probable_profession": self.probable_profession,
            "bio_summary": self.bio_summary,
            "confirmed_platforms": self.confirmed_platforms,
            "probable_platforms": self.probable_platforms,
            "identity_score": round(self.identity_score, 1),
            "overall_confidence": round(self.overall_confidence, 1),
            "overall_confidence_level": self.overall_confidence_level.value,
            "confidence_explanation": self.confidence_explanation,
            "risk_level": self.risk_level.value,
            "risk_explanation": self.risk_explanation,
            "total_evidence_count": self.total_evidence_count,
            "positive_evidence_count": self.positive_evidence_count,
            "negative_evidence_count": self.negative_evidence_count,
            "definitive_evidence_count": self.definitive_evidence_count,
        }


@dataclass
class TimelineEvent:
    """A single event in the investigation timeline."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    node_id: str = ""
    platform: str = ""
    event_type: str = ""           # account_created, first_post, last_active
    event_date: Optional[datetime] = None
    description: str = ""
    confidence: float = 50.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node_id": self.node_id,
            "platform": self.platform,
            "event_type": self.event_type,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "description": self.description,
            "confidence": round(self.confidence, 1),
        }


# ═══════════════════════════════════════════════════════════════
# INVESTIGATION
# ═══════════════════════════════════════════════════════════════

@dataclass
class Investigation:
    """
    The top-level container for an entire investigation.

    An investigation starts with a query and produces:
      1. A graph of discovered entities and relationships
      2. A digital identity profile
      3. An intelligence report

    The investigation is stateful and resumable — it can be
    paused, expanded, and continued.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: InvestigationStatus = InvestigationStatus.CREATED
    current_phase: InvestigationPhase = InvestigationPhase.SEED_RESOLUTION

    # Query
    initial_query: str = ""
    query_type: QueryType = QueryType.USERNAME

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Graph
    nodes: Dict[str, IdentityNode] = field(default_factory=dict)
    edges: Dict[str, IdentityEdge] = field(default_factory=dict)
    seed_node_id: Optional[str] = None

    # Results
    identity_profile: Optional[DigitalIdentityProfile] = None
    timeline_events: List[TimelineEvent] = field(default_factory=list)

    # AI Analysis
    ai_analysis: str = ""
    cross_platform_analysis: str = ""
    risk_assessment: str = ""
    suggested_next_steps: List[str] = field(default_factory=list)

    # Statistics
    total_platforms_checked: int = 0
    expansion_depth_reached: int = 0

    # Configuration (per-investigation overrides)
    max_expansion_depth: int = 3
    max_nodes: int = 50

    # Extra data (plugins, image intelligence, etc.)
    extra_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def seed_node(self) -> Optional[IdentityNode]:
        if self.seed_node_id and self.seed_node_id in self.nodes:
            return self.nodes[self.seed_node_id]
        return None

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def confirmed_nodes(self) -> List[IdentityNode]:
        return [
            n for n in self.nodes.values()
            if n.confidence >= 70
        ]

    @property
    def duration_seconds(self) -> float:
        end = self.completed_at or datetime.now()
        return (end - self.created_at).total_seconds()

    @property
    def all_evidence(self) -> List[Evidence]:
        """Collect all evidence from all edges."""
        evidence = []
        for edge in self.edges.values():
            evidence.extend(edge.evidence_chain.evidence)
        return evidence

    @property
    def executive_summary(self) -> str:
        confirmed = len(self.confirmed_nodes)
        total = self.node_count
        if total == 0:
            return (
                f"التحقيق في '{self.initial_query}' لم يسفر عن نتائج مؤكدة."
            )
        profile = self.identity_profile
        name = profile.primary_name if profile and profile.primary_name else self.initial_query
        conf = profile.overall_confidence if profile else 0
        return (
            f"التحقيق في '{self.initial_query}' كشف عن {confirmed} حساب مؤكد "
            f"من أصل {total} حساب مكتشف عبر {self.total_platforms_checked} منصة. "
            f"الثقة الإجمالية: {conf:.0f}%. "
            f"الاسم الأساسي المكتشف: {name}."
        )

    def add_node(self, node: IdentityNode) -> None:
        self.nodes[node.id] = node
        self.updated_at = datetime.now()

    def add_edge(self, edge: IdentityEdge) -> None:
        self.edges[edge.id] = edge
        self.updated_at = datetime.now()

    def get_node_edges(self, node_id: str) -> List[IdentityEdge]:
        """Get all edges connected to a node."""
        return [
            e for e in self.edges.values()
            if e.source_id == node_id or e.target_id == node_id
        ]

    def get_connected_nodes(self, node_id: str) -> List[IdentityNode]:
        """Get all nodes directly connected to a given node."""
        connected_ids = set()
        for edge in self.get_node_edges(node_id):
            if edge.source_id == node_id:
                connected_ids.add(edge.target_id)
            else:
                connected_ids.add(edge.source_id)
        return [self.nodes[nid] for nid in connected_ids if nid in self.nodes]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status.value,
            "current_phase": self.current_phase.value,
            "initial_query": self.initial_query,
            "query_type": self.query_type.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": round(self.duration_seconds, 1),
            "seed_node_id": self.seed_node_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "confirmed_count": len(self.confirmed_nodes),
            "total_platforms_checked": self.total_platforms_checked,
            "expansion_depth_reached": self.expansion_depth_reached,
            "executive_summary": self.executive_summary,
            "identity_profile": self.identity_profile.to_dict() if self.identity_profile else None,
            "ai_analysis": self.ai_analysis,
            "cross_platform_analysis": self.cross_platform_analysis,
            "risk_assessment": self.risk_assessment,
            "suggested_next_steps": self.suggested_next_steps,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": {eid: e.to_dict() for eid, e in self.edges.items()},
            "timeline": [t.to_dict() for t in self.timeline_events],
            "extra_data": self.extra_data,
        }

    def to_graph_dict(self) -> Dict[str, Any]:
        """Serialize only graph data (for frontend visualization)."""
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
            "seed_node_id": self.seed_node_id,
        }


# ═══════════════════════════════════════════════════════════════
# PROGRESS TRACKING (WebSocket)
# ═══════════════════════════════════════════════════════════════

@dataclass
class InvestigationProgress:
    """Real-time progress update for WebSocket communication."""
    investigation_id: str
    phase: str
    progress: float              # 0-100
    message: str = ""
    total_platforms: int = 0
    checked_platforms: int = 0
    discovered_nodes: int = 0
    discovered_edges: int = 0
    current_platform: str = ""
    is_complete: bool = False

    # Live data — sent incrementally
    new_nodes: List[Dict[str, Any]] = field(default_factory=list)
    new_edges: List[Dict[str, Any]] = field(default_factory=list)
    new_evidence: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "investigation_id": self.investigation_id,
            "phase": self.phase,
            "progress": round(self.progress, 1),
            "message": self.message,
            "total_platforms": self.total_platforms,
            "checked_platforms": self.checked_platforms,
            "discovered_nodes": self.discovered_nodes,
            "discovered_edges": self.discovered_edges,
            "current_platform": self.current_platform,
            "is_complete": self.is_complete,
            "new_nodes": self.new_nodes,
            "new_edges": self.new_edges,
            "new_evidence": self.new_evidence,
        }


# ═══════════════════════════════════════════════════════════════
# SITE CONFIG (retained from original for sites.json compat)
# ═══════════════════════════════════════════════════════════════

@dataclass
class SiteConfig:
    """Configuration for a single site in the sites database."""
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
    priority: int = 999
    protocol: str = ""
    activation: Dict[str, Any] = field(default_factory=dict)
    site_type: str = "username"

    @property
    def is_enabled(self) -> bool:
        return not self.disabled

    @property
    def reliability_score(self) -> float:
        """Platform reliability based on check method and config."""
        score = 40.0
        if self.check_type == "message":
            if self.absence_strs and self.presence_strs:
                score = 80.0
            elif self.absence_strs or self.presence_strs:
                score = 60.0
        elif self.check_type == "status_code":
            score = 45.0   # Lower than before — status_code alone is weak
        elif self.check_type == "response_url":
            score = 65.0
        if self.alexa_rank and self.alexa_rank < 10000:
            score += 10
        elif self.alexa_rank and self.alexa_rank < 100000:
            score += 5
        return min(score, 100.0)
