"""
Customer-Facing Message Sanitization and Security Module.

Ensures that internal system paths, API keys, credentials, and technical
stack traces are never exposed to customers. All detailed technical
information is preserved exclusively in internal loggers.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger("Sanitizer")

# Patterns matching sensitive credentials or internal technical data
API_KEY_PATTERNS = [
    re.compile(r"gsk_[A-Za-z0-9_-]{16,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]+=*", re.IGNORECASE),
    re.compile(r"key-[A-Za-z0-9_-]{16,}", re.IGNORECASE),
    re.compile(r"api[_-]?key[\"'\s:=]+([A-Za-z0-9_-]{16,})", re.IGNORECASE),
]

# Patterns matching internal file paths (Windows and POSIX)
WINDOWS_PATH_PATTERN = re.compile(r"[A-Za-z]:\\(?:[^<>:\"/\\|?*\r\n]+\\)*[^<>:\"/\\|?*\r\n]*")
POSIX_PATH_PATTERN = re.compile(r"(?:/[a-zA-Z0-9_\.-]+){2,}")

# Patterns matching stack traces or internal Python exception markers
TECHNICAL_ERROR_PATTERNS = [
    re.compile(r"Traceback \(most recent call last\):", re.IGNORECASE),
    re.compile(r"File \".*\", line \d+.*", re.IGNORECASE),
    re.compile(r"groq\.[A-Za-z0-9_.]+", re.IGNORECASE),
    re.compile(r"httpx\.[A-Za-z0-9_.]+", re.IGNORECASE),
    re.compile(r"openai\.[A-Za-z0-9_.]+", re.IGNORECASE),
    re.compile(r"json\.decoder\.[A-Za-z0-9_.]+", re.IGNORECASE),
]


def mask_sensitive_data(text: str) -> str:
    """
    Mask any API keys, tokens, or authorization headers in a text string.
    Suitable for logging or sanitizing error messages.
    """
    if not text:
        return ""

    sanitized = text
    for pattern in API_KEY_PATTERNS:
        sanitized = pattern.sub("[REDACTED_API_KEY]", sanitized)
    return sanitized


def sanitize_customer_message(
    message: str,
    fallback_message: str = "We encountered a temporary issue while processing your request. Please try again in a moment.",
) -> str:
    """
    Sanitize text intended for customer display or voice synthesis.
    Strips internal paths, raw stack traces, and API keys.
    If the message is overly technical, returns a safe fallback message.
    """
    if not message or not str(message).strip():
        return fallback_message

    cleaned = str(message).strip()

    # Redact any API keys
    cleaned = mask_sensitive_data(cleaned)

    # If message contains stack trace or low-level library markers, replace with friendly fallback
    for tech_pat in TECHNICAL_ERROR_PATTERNS:
        if tech_pat.search(cleaned):
            logger.debug("Message contained technical patterns, substituting friendly fallback.")
            return fallback_message

    # Replace local Windows/Unix file paths with generic file references
    cleaned = WINDOWS_PATH_PATTERN.sub("the audio file", cleaned)
    cleaned = POSIX_PATH_PATTERN.sub("the audio file", cleaned)

    return cleaned
