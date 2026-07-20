"""Utility functions for sanitizing sensitive data"""

import re
from typing import Any, Dict, List, Union

FORBIDDEN_KEYS = {"password", "token", "secret", "authorization", "apikey", "api_key", "access_token", "refresh_token"}

# Patterns for detecting secrets in stack traces
SECRET_PATTERNS = [
    r'(?i)(?:api[_-]?key|token|secret|password|authorization)\s*[=:]\s*["\']?([a-zA-Z0-9_\-\.]+)["\']?',
    r'Bearer\s+[a-zA-Z0-9_\-\.]+',
    r'Authorization:\s*[a-zA-Z0-9_\-\.]+',
]


def sanitize_error_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively sanitize a dictionary by removing forbidden keys and
    redacting secrets in strings (including stack traces).
    
    Args:
        payload: Dictionary to sanitize (e.g., error.extra_data)
    
    Returns:
        Sanitized dictionary with forbidden keys removed and secrets redacted
    """
    if not isinstance(payload, dict):
        return payload
    
    sanitized = {}
    for key, value in payload.items():
        # Skip forbidden keys (case-insensitive)
        if key.lower() in FORBIDDEN_KEYS:
            continue
        
        # Recursively sanitize nested dictionaries
        if isinstance(value, dict):
            sanitized[key] = sanitize_error_payload(value)
        # Sanitize lists of dictionaries
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_error_payload(item) if isinstance(item, dict) else _sanitize_string_value(item)
                for item in value
            ]
        # Sanitize string values (including stack traces)
        elif isinstance(value, str):
            sanitized[key] = _sanitize_string_value(value)
        else:
            sanitized[key] = value
    
    return sanitized


def _sanitize_string_value(value: str) -> str:
    """
    Redact secrets from a string value.
    """
    if not isinstance(value, str):
        return value
    
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = re.sub(pattern, '[REDACTED]', redacted, flags=re.IGNORECASE)
    
    return redacted