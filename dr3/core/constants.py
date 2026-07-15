"""
DR3 Intelligence Platform — Constants

Design philosophy:
  Constants are not arbitrary numbers. Every constant encodes
  a policy decision about how the intelligence system operates.
  Each constant is documented with WHY that value was chosen.
"""

from typing import Dict, List, Set

# ═══════════════════════════════════════════════════════════════
# EVIDENCE WEIGHTS — Maximum possible weight for each evidence type
#
# These are CEILINGS, not fixed values. The actual weight is
# computed by the Evidence Engine based on quality, reliability,
# and context. A DEFINITIVE direct link gets full weight.
# A CIRCUMSTANTIAL same_username gets a fraction.
# ═══════════════════════════════════════════════════════════════

EVIDENCE_MAX_WEIGHTS: Dict[str, float] = {
    # ── Definitive (can prove identity alone) ──
    "direct_link": 40.0,           # Account A explicitly links to B
    "same_email": 40.0,            # Same verified email address
    "verified_ownership": 45.0,    # Platform-verified ownership

    # ── Strong Identity ──
    "same_display_name": 25.0,     # Identical display/real name
    "same_avatar": 30.0,          # Perceptual hash match (>95%)
    "similar_avatar": 15.0,       # Partial match (80-95%)
    "same_bio": 20.0,             # Bio text >80% match
    "similar_bio": 10.0,          # Bio text 60-80% match

    # ── Moderate ──
    "exact_username": 20.0,        # Same username string
    "similar_username": 10.0,      # Username variation
    "same_website": 25.0,         # Same personal website/domain
    "same_location": 12.0,        # Same geographic location
    "shared_connection": 15.0,    # Mutual follow/link

    # ── Weak ──
    "same_language": 5.0,          # Same primary language
    "similar_activity": 5.0,      # Similar activity patterns
    "temporal_correlation": 8.0,  # Created in same period

    # ── Platform ──
    "platform_reliability": 10.0,  # Source platform tier bonus
    "profile_completeness": 8.0,  # Rich profile data bonus

    # ── Negative (penalties — subtracted) ──
    "different_name": -20.0,       # Conflicting display names
    "different_avatar": -10.0,     # Clearly different avatars
    "different_location": -12.0,   # Conflicting locations
    "different_language": -8.0,    # Different primary languages
    "temporal_impossibility": -25.0,  # Impossible timeline
}

# ═══════════════════════════════════════════════════════════════
# QUALITY MULTIPLIERS
#
# Evidence weight is multiplied by quality factor.
# A "definitive" quality evidence gets full weight.
# A "circumstantial" quality evidence gets only 10%.
# This prevents weak evidence from inflating scores.
# ═══════════════════════════════════════════════════════════════

QUALITY_MULTIPLIERS: Dict[str, float] = {
    "definitive": 1.0,        # Full weight
    "strong": 0.8,            # 80% of max weight
    "moderate": 0.5,          # 50% of max weight
    "weak": 0.2,              # 20% of max weight — minimal impact
    "circumstantial": 0.05,   # 5% — effectively zero impact on confidence
}

# ═══════════════════════════════════════════════════════════════
# CONFIDENCE THRESHOLDS
# ═══════════════════════════════════════════════════════════════

CONFIDENCE_CONFIRMED = 90.0
CONFIDENCE_HIGH = 70.0
CONFIDENCE_MODERATE = 50.0
CONFIDENCE_LOW = 30.0
CONFIDENCE_SPECULATIVE = 10.0

# ═══════════════════════════════════════════════════════════════
# INVESTIGATION LIMITS
#
# These limits prevent unbounded investigation expansion.
# They are tuned for practical investigations — not arbitrary.
# ═══════════════════════════════════════════════════════════════

# Maximum depth of identity expansion (seed → hop1 → hop2 → ...)
# Why 3: Beyond 3 hops, correlation confidence degrades rapidly.
MAX_EXPANSION_DEPTH = 3

# Maximum total nodes in investigation graph
# Why 50: More nodes means exponential correlation work. 50 is
# enough for a thorough investigation without performance issues.
MAX_GRAPH_NODES = 50

# Minimum evidence quality to trigger expansion
# Why 50: Only expand when we have at least moderate confidence.
# Expanding on weak evidence causes false positive cascades.
EXPANSION_CONFIDENCE_THRESHOLD = 50.0

# Maximum platforms to check during seed resolution
# Why 20: Seed resolution checks Tier 1 platforms only.
# Checking more wastes time before we know what to look for.
SEED_RESOLUTION_MAX_PLATFORMS = 20

# Maximum concurrent HTTP connections per collector
MAX_CONNECTIONS = 50

# HTTP request timeout in seconds
DEFAULT_TIMEOUT = 15

# Maximum retries for failed requests
DEFAULT_RETRIES = 1

# ═══════════════════════════════════════════════════════════════
# PLATFORM TIERS
#
# Tier 1: Rich API, reliable data, high user base.
#   These are checked FIRST during seed resolution because
#   they provide the richest identity data.
#
# Tier 2: Significant platforms with moderate data.
#   Checked during expansion phase.
#
# Tier 3: Everything else — used for breadth, not depth.
# ═══════════════════════════════════════════════════════════════

TIER_1_PLATFORMS: List[str] = [
    "GitHub", "Twitter", "Instagram", "Reddit", "LinkedIn",
    "Facebook", "YouTube", "TikTok", "Pinterest", "Twitch",
    "Steam", "Discord", "Spotify", "Medium", "Telegram", "Snapchat",
]

TIER_2_PLATFORMS: List[str] = [
    "Behance", "DeviantArt", "Flickr", "SoundCloud", "Vimeo",
    "GitLab", "Bitbucket", "Patreon", "Gravatar", "Keybase",
    "HackerNews", "StackOverflow", "Dribbble", "Mastodon",
]

# Platforms that reliably provide rich identity data for seed resolution
# Order matters — checked in this order during seed resolution
SEED_PRIORITY_PLATFORMS: List[str] = [
    "GitHub",       # Richest public API: name, bio, website, email, avatar, repos
    "Reddit",       # Public API: post history, comment patterns, about
    "Twitter",      # Bio, website, location, avatar, display name
    "Instagram",    # Bio, website, avatar, display name
    "LinkedIn",     # Professional identity — rich but hard to access
    "YouTube",      # Channel description, links, about page
    "Medium",       # Bio, links, writing style
    "Keybase",      # Cryptographic identity proofs!
    "Steam",        # Profile, community links
    "Twitch",       # Bio, links, panels
]

# ═══════════════════════════════════════════════════════════════
# FALSE POSITIVE PREVENTION
# ═══════════════════════════════════════════════════════════════

# Patterns in page title/body that indicate the account does NOT exist
FALSE_POSITIVE_PATTERNS: List[str] = [
    "page not found",
    "404",
    "this page doesn't exist",
    "account suspended",
    "account deactivated",
    "user not found",
    "profile not found",
    "this account has been suspended",
]

# Patterns that indicate a generic/template page (not a real profile)
GENERIC_PAGE_PATTERNS: List[str] = [
    "sign up",
    "create account",
    "register",
    "join now",
    "create your",
    "get started",
    "log in to",
]

# Patterns that indicate anti-bot protection (unreliable result)
ANTIBOT_PATTERNS: List[str] = [
    "captcha",
    "cloudflare",
    "access denied",
    "please verify",
    "rate limit",
    "too many requests",
    "unusual traffic",
]

# Characters not allowed in usernames (for input validation)
BAD_USERNAME_CHARS: str = "#%&*+/\\=?@{|}"

# ═══════════════════════════════════════════════════════════════
# HTTP
# ═══════════════════════════════════════════════════════════════

DEFAULT_USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
]

# ═══════════════════════════════════════════════════════════════
# SIMILARITY THRESHOLDS
# ═══════════════════════════════════════════════════════════════

# Minimum string similarity ratio to consider names "matching"
NAME_SIMILARITY_THRESHOLD = 0.85

# Minimum bio similarity to consider bios "matching"
BIO_SIMILARITY_THRESHOLD = 0.60

# Minimum username similarity to consider "related"
USERNAME_SIMILARITY_THRESHOLD = 0.80

# Perceptual hash distance for avatar "same" (lower = more similar)
AVATAR_HASH_EXACT_THRESHOLD = 5       # Nearly identical
AVATAR_HASH_SIMILAR_THRESHOLD = 12    # Visually similar
