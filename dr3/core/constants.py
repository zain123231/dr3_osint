"""
DR3 OSINT — Constants
"""

# Evidence weights for confidence scoring
EVIDENCE_WEIGHTS = {
    "exact_username": 30.0,
    "similar_username": 15.0,
    "same_display_name": 20.0,
    "similar_bio": 20.0,
    "same_avatar": 25.0,
    "same_location": 15.0,
    "same_language": 10.0,
    "shared_links": 20.0,
    "same_email": 30.0,
    "activity_pattern": 10.0,
    "platform_reliability": 5.0,
}

# Confidence thresholds
CONFIDENCE_VERY_HIGH = 90.0
CONFIDENCE_HIGH = 70.0
CONFIDENCE_MEDIUM = 50.0
CONFIDENCE_LOW = 30.0

# Search defaults
DEFAULT_TIMEOUT = 15
DEFAULT_MAX_CONNECTIONS = 50
DEFAULT_TOP_SITES = 3000
DEFAULT_RETRIES = 1

# HTTP
DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# Characters not supported in usernames
BAD_USERNAME_CHARS = "#%&*+/\\=?@{|}"

# Platform tiers for reliability ranking
TIER_1_PLATFORMS = [
    "GitHub", "Twitter", "Instagram", "Reddit", "LinkedIn", "Facebook",
    "YouTube", "TikTok", "Pinterest", "Twitch", "Steam", "Discord",
    "Spotify", "Medium", "Telegram", "Snapchat",
]

TIER_2_PLATFORMS = [
    "Behance", "DeviantArt", "Flickr", "SoundCloud", "Vimeo",
    "GitLab", "Bitbucket", "Patreon", "Gravatar", "Keybase",
]

# Common false positive indicators
FALSE_POSITIVE_PATTERNS = [
    "page not found",
    "404",
    "this page doesn't exist",
    "account suspended",
    "account deactivated",
    "sign up",
    "create account",
    "register",
    "join now",
    "captcha",
    "cloudflare",
    "access denied",
]
