"""
Process utilities for resolving and expanding PID lists.
"""

from __future__ import annotations

import importlib.util
from typing import Iterable, List


def _ensure_psutil_available() -> None:
    if importlib.util.find_spec("psutil") is None:
        raise RuntimeError("psutil is required for process utilities.")


def resolve_pids_by_name(name: str) -> List[int]:
    _ensure_psutil_available()
    import psutil  # noqa: WPS433 - optional dependency

    matches: List[int] = []
    for proc in psutil.process_iter(attrs=["name"]):
        if proc.info.get("name") == name:
            matches.append(proc.pid)
    return matches


def expand_process_tree(pids: Iterable[int]) -> List[int]:
    _ensure_psutil_available()
    import psutil  # noqa: WPS433 - optional dependency

    expanded: List[int] = []
    for pid in pids:
        try:
            root = psutil.Process(pid)
            expanded.append(pid)
            expanded.extend(child.pid for child in root.children(recursive=True))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return sorted(set(expanded))
