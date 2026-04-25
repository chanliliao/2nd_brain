from __future__ import annotations

import base64
import re

_INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(?:previous|all\s+prior)\s+instructions"
    r"|disregard\s+your\s+instructions"
    r"|forget\s+your\s+instructions"
    r"|new\s+instructions\s*:"
    r"|system\s+prompt\s*:)",
    re.IGNORECASE,
)

_XML_ROLE_TAGS = re.compile(
    r"</?(?:system|human|assistant)[^>]*>",
    re.IGNORECASE,
)

_BASE64_BLOB = re.compile(r"[A-Za-z0-9+/]{500,}={0,2}")


def sanitize_text(text: str) -> str:
    """Return cleaned text safe to include in a prompt."""
    if not text:
        return text
    text = _XML_ROLE_TAGS.sub("", text)
    text = _INJECTION_PATTERNS.sub("[REDACTED]", text)
    text = _BASE64_BLOB.sub("[BASE64_REDACTED]", text)
    return text


def sanitize_github_pr(pr: dict) -> dict:
    """Return a shallow copy with title, body sanitized."""
    copy = dict(pr)
    for field in ("title", "body"):
        if field in copy and isinstance(copy[field], str):
            copy[field] = sanitize_text(copy[field])
    return copy
