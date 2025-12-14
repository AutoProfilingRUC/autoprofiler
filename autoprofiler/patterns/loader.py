"""
Pattern loading utilities.

Patterns are defined declaratively in YAML, never hardcoded in logic.
"""

from __future__ import annotations

import pathlib
from typing import Any, Dict, List

import yaml


def load_patterns(path: pathlib.Path) -> List[Dict[str, Any]]:
    """Load performance patterns from a YAML file."""

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or []
    if not isinstance(data, list):
        raise ValueError("Pattern file must define a list of pattern entries.")
    return data
