"""Validate redirect URLs and enforce allowlist for APL."""
from urllib.parse import urlparse

from app.core.config import REDIRECT_ALLOWLIST


# Dangerous or non-http(s) schemes
BLOCKED_SCHEMES = frozenset(
    {"javascript", "data", "vbscript", "file", "blob", ""}
)


def validate_redirect_url(url: str) -> tuple[bool, str | None, str | None]:
    """
    Validate redirect URL and check allowlist.

    Returns:
        (True, None, None) if valid and allowed.
        (False, error_message, error_type) if invalid or not allowed.
        error_type is "invalid" (400) or "forbidden" (403).
    """
    if not url or not url.strip():
        return False, "Redirect URL is required", "invalid"

    url = url.strip()

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL", "invalid"

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        if scheme in BLOCKED_SCHEMES or not scheme:
            return False, "Redirect URL must use http or https", "invalid"
        return False, "Redirect URL must use http or https", "invalid"

    netloc = (parsed.netloc or "").lower()
    if not netloc:
        return False, "Invalid URL host", "invalid"

    if REDIRECT_ALLOWLIST:
        # Allowlist is set: host must be in the list (without port for comparison)
        host = netloc.split(":")[0]
        if host not in REDIRECT_ALLOWLIST:
            return False, "Redirect domain is not in the allowlist", "forbidden"

    return True, None, None
