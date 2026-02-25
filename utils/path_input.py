"""
User path input normalization helpers.
"""
from __future__ import annotations


_QUOTE_PAIRS = (
    ('"', '"'),
    ("'", "'"),
    ("“", "”"),
    ("‘", "’"),
)


def normalize_user_path(value: str) -> str:
    text = str(value or "").strip()
    if len(text) < 2:
        return text
    for left, right in _QUOTE_PAIRS:
        if text.startswith(left) and text.endswith(right):
            return text[1:-1].strip()
    return text

