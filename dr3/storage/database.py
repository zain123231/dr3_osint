"""
DR3 Intelligence Platform — SQLite Database Layer

Design philosophy:
  - Single-file database (no external dependencies)
  - Schema encodes the intelligence ontology
  - Every entity, relationship, and evidence is persisted
  - Investigations are resumable and archivable
  - JSON fields for flexible metadata storage

Why SQLite over PostgreSQL:
  - Zero configuration (works on any machine)
  - Single file (portable, backupable)
  - Sufficient performance for OSINT workloads
  - Full JSON support via json_extract()
  - WAL mode for concurrent reads
  - Can migrate to PostgreSQL later if needed
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("dr3.storage")

# ═══════════════════════════════════════════════════════════════
# SCHEMA
# ═══════════════════════════════════════════════════════════════

SCHEMA_SQL = """
-- ══════════════════════════════════════
-- Investigations
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS investigations (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'created',
    current_phase TEXT NOT NULL DEFAULT 'seed_resolution',
    initial_query TEXT NOT NULL,
    query_type TEXT NOT NULL DEFAULT 'username',
    seed_node_id TEXT,
    overall_confidence REAL DEFAULT 0,
    max_expansion_depth INTEGER DEFAULT 3,
    max_nodes INTEGER DEFAULT 50,
    total_platforms_checked INTEGER DEFAULT 0,
    expansion_depth_reached INTEGER DEFAULT 0,
    ai_analysis TEXT DEFAULT '',
    cross_platform_analysis TEXT DEFAULT '',
    risk_assessment TEXT DEFAULT '',
    suggested_next_steps TEXT DEFAULT '[]',
    identity_profile TEXT DEFAULT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    completed_at TEXT
);

-- ══════════════════════════════════════
-- Identity Nodes (graph vertices)
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'account',
    platform TEXT NOT NULL DEFAULT '',
    username TEXT DEFAULT '',
    profile_url TEXT DEFAULT '',
    display_name TEXT DEFAULT '',
    bio TEXT DEFAULT '',
    avatar_url TEXT DEFAULT '',
    avatar_hash TEXT DEFAULT '',
    website TEXT DEFAULT '',
    email TEXT DEFAULT '',
    location TEXT DEFAULT '',
    language TEXT DEFAULT '',
    company TEXT DEFAULT '',
    account_created TEXT DEFAULT '',
    last_active TEXT DEFAULT '',
    followers INTEGER DEFAULT 0,
    following INTEGER DEFAULT 0,
    posts INTEGER DEFAULT 0,
    confidence REAL DEFAULT 0,
    confidence_level TEXT DEFAULT 'unsubstantiated',
    is_seed INTEGER DEFAULT 0,
    depth INTEGER DEFAULT 0,
    platform_tier TEXT DEFAULT 'tier_3',
    collection_method TEXT DEFAULT 'status_code',
    tags TEXT DEFAULT '[]',
    extra_data TEXT DEFAULT '{}',
    discovered_at TEXT NOT NULL,
    FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_nodes_investigation ON nodes(investigation_id);
CREATE INDEX IF NOT EXISTS idx_nodes_platform ON nodes(platform);
CREATE INDEX IF NOT EXISTS idx_nodes_username ON nodes(username);

-- ══════════════════════════════════════
-- Identity Edges (graph relationships)
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS edges (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL DEFAULT 'possible_match',
    strength REAL DEFAULT 0,
    explanation TEXT DEFAULT '',
    discovered_at TEXT NOT NULL,
    FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES nodes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_edges_investigation ON edges(investigation_id);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);

-- ══════════════════════════════════════
-- Evidence
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    edge_id TEXT,
    node_id TEXT,
    evidence_type TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'positive',
    quality TEXT NOT NULL DEFAULT 'moderate',
    weight REAL NOT NULL DEFAULT 0,
    raw_weight REAL NOT NULL DEFAULT 0,
    reliability REAL DEFAULT 50,
    source_platform TEXT DEFAULT '',
    source_entity_id TEXT DEFAULT '',
    target_platform TEXT DEFAULT '',
    target_entity_id TEXT DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    explanation TEXT DEFAULT '',
    collection_method TEXT DEFAULT 'profile_scrape',
    raw_data TEXT DEFAULT '{}',
    verified INTEGER DEFAULT 0,
    verification_method TEXT DEFAULT '',
    discovered_at TEXT NOT NULL,
    FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
    FOREIGN KEY (edge_id) REFERENCES edges(id) ON DELETE SET NULL,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence_investigation ON evidence(investigation_id);
CREATE INDEX IF NOT EXISTS idx_evidence_edge ON evidence(edge_id);
CREATE INDEX IF NOT EXISTS idx_evidence_category ON evidence(category);

-- ══════════════════════════════════════
-- Watchlist (Continuous Monitoring)
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS watchlist (
    id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    last_checked TEXT,
    created_at TEXT NOT NULL
);

-- ══════════════════════════════════════
-- Timeline Events
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS timeline_events (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    platform TEXT DEFAULT '',
    event_type TEXT NOT NULL,
    event_date TEXT,
    description TEXT DEFAULT '',
    confidence REAL DEFAULT 50,
    FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_timeline_investigation ON timeline_events(investigation_id);
"""


class Database:
    """
    SQLite database manager for the intelligence platform.

    Features:
      - Auto-creates schema on first use
      - WAL mode for concurrent reads
      - Context manager for transactions
      - JSON serialization helpers
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_directory()
        self._init_db()

    def _ensure_directory(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _init_db(self) -> None:
        """Initialize database with schema."""
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            # Enable WAL mode for concurrent reads
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
        logger.info(f"Database initialized: {self.db_path}")

    @contextmanager
    def _connect(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Investigation CRUD ──

    def save_investigation(self, inv) -> None:
        """Save or update an investigation."""
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO investigations
                (id, status, current_phase, initial_query, query_type,
                 seed_node_id, overall_confidence, max_expansion_depth,
                 max_nodes, total_platforms_checked, expansion_depth_reached,
                 ai_analysis, cross_platform_analysis, risk_assessment,
                 suggested_next_steps, identity_profile,
                 created_at, updated_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                inv.id, inv.status.value, inv.current_phase.value,
                inv.initial_query, inv.query_type.value,
                inv.seed_node_id, inv.identity_profile.overall_confidence if inv.identity_profile else 0,
                inv.max_expansion_depth, inv.max_nodes,
                inv.total_platforms_checked, inv.expansion_depth_reached,
                inv.ai_analysis, inv.cross_platform_analysis,
                inv.risk_assessment,
                json.dumps(inv.suggested_next_steps, ensure_ascii=False),
                json.dumps(inv.identity_profile.to_dict(), ensure_ascii=False) if inv.identity_profile else None,
                inv.created_at.isoformat(),
                inv.updated_at.isoformat() if inv.updated_at else None,
                inv.completed_at.isoformat() if inv.completed_at else None,
            ))

    def get_investigation(self, investigation_id: str) -> Optional[Dict]:
        """Load investigation metadata (without full graph)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM investigations WHERE id = ?",
                (investigation_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_investigations(self, limit: int = 50) -> List[Dict]:
        """List recent investigations."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM investigations ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_investigation(self, investigation_id: str) -> None:
        """Delete an investigation and all related data (cascade)."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM investigations WHERE id = ?",
                (investigation_id,)
            )

    # ── Node CRUD ──

    def save_node(self, investigation_id: str, node) -> None:
        """Save or update a node."""
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO nodes
                (id, investigation_id, entity_type, platform, username,
                 profile_url, display_name, bio, avatar_url, avatar_hash,
                 website, email, location, language, company,
                 account_created, last_active,
                 followers, following, posts,
                 confidence, confidence_level, is_seed, depth,
                 platform_tier, collection_method,
                 tags, extra_data, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node.id, investigation_id,
                node.entity_type.value, node.platform, node.username,
                node.profile_url, node.display_name,
                node.bio, node.avatar_url, node.avatar_hash,
                node.website, node.email, node.location,
                node.language, node.company,
                node.account_created, node.last_active,
                node.followers, node.following, node.posts,
                node.confidence, node.confidence_level.value,
                1 if node.is_seed else 0, node.depth,
                node.platform_tier.value, node.collection_method.value,
                json.dumps(node.tags, ensure_ascii=False),
                json.dumps(node.extra_data, ensure_ascii=False),
                node.discovered_at.isoformat(),
            ))

    def get_nodes(self, investigation_id: str) -> List[Dict]:
        """Get all nodes for an investigation."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM nodes WHERE investigation_id = ? ORDER BY confidence DESC",
                (investigation_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Edge CRUD ──

    def save_edge(self, investigation_id: str, edge) -> None:
        """Save or update an edge."""
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO edges
                (id, investigation_id, source_id, target_id,
                 relationship_type, strength, explanation, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                edge.id, investigation_id,
                edge.source_id, edge.target_id,
                edge.relationship_type.value,
                edge.strength, edge.explanation,
                edge.discovered_at.isoformat(),
            ))

    def get_edges(self, investigation_id: str) -> List[Dict]:
        """Get all edges for an investigation."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM edges WHERE investigation_id = ?",
                (investigation_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Evidence CRUD ──

    def save_evidence(self, investigation_id: str, ev, edge_id: str = None, node_id: str = None) -> None:
        """Save a piece of evidence."""
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO evidence
                (id, investigation_id, edge_id, node_id,
                 evidence_type, category, quality,
                 weight, raw_weight, reliability,
                 source_platform, source_entity_id,
                 target_platform, target_entity_id,
                 description, explanation,
                 collection_method, raw_data,
                 verified, verification_method, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ev.id, investigation_id, edge_id, node_id,
                ev.evidence_type.value, ev.category.value, ev.quality.value,
                ev.weight, ev.raw_weight, ev.reliability,
                ev.source_platform, ev.source_entity_id,
                ev.target_platform, ev.target_entity_id,
                ev.description, ev.explanation,
                ev.collection_method.value,
                json.dumps(ev.raw_data, ensure_ascii=False),
                1 if ev.verified else 0, ev.verification_method,
                ev.discovered_at.isoformat(),
            ))

    def get_evidence(self, investigation_id: str, edge_id: str = None) -> List[Dict]:
        """Get evidence, optionally filtered by edge."""
        with self._connect() as conn:
            if edge_id:
                rows = conn.execute(
                    "SELECT * FROM evidence WHERE investigation_id = ? AND edge_id = ?",
                    (investigation_id, edge_id)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM evidence WHERE investigation_id = ? ORDER BY weight DESC",
                    (investigation_id,)
                ).fetchall()
            return [dict(r) for r in rows]

    # ── Timeline CRUD ──

    def save_timeline_event(self, investigation_id: str, event) -> None:
        """Save a timeline event."""
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO timeline_events
                (id, investigation_id, node_id, platform,
                 event_type, event_date, description, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.id, investigation_id, event.node_id,
                event.platform, event.event_type,
                event.event_date.isoformat() if event.event_date else None,
                event.description, event.confidence,
            ))

    def get_timeline(self, investigation_id: str) -> List[Dict]:
        """Get timeline events ordered chronologically."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM timeline_events WHERE investigation_id = ? ORDER BY event_date ASC",
                (investigation_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Watchlist CRUD ──

    def add_to_watchlist(self, query: str) -> None:
        import uuid
        from datetime import datetime
        wid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO watchlist (id, query, status, created_at)
                VALUES (?, ?, ?, ?)
            """, (wid, query, 'active', now))

    def get_watchlist(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM watchlist ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    # ── Statistics ──

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._connect() as conn:
            inv_count = conn.execute("SELECT COUNT(*) FROM investigations").fetchone()[0]
            node_count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            edge_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            ev_count = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
            return {
                "investigations": inv_count,
                "nodes": node_count,
                "edges": edge_count,
                "evidence": ev_count,
            }
