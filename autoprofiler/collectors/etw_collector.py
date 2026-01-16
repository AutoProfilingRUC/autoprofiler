"""
ETW collector placeholder for Windows profiling.

This stub documents where Event Tracing for Windows support would be wired in.
"""

from __future__ import annotations

from typing import List

from ..models import ProfileArtifact
from .base import Collector


class EtwCollector(Collector):
    """Placeholder ETW collector (not yet implemented)."""

    def __init__(self) -> None:
        super().__init__(category="cpu")

    def start(self, pid: int | List[int]) -> None:
        raise NotImplementedError("ETW collection is not implemented in the MVP.")

    def stop(self) -> ProfileArtifact:
        raise NotImplementedError("ETW collection is not implemented in the MVP.")
