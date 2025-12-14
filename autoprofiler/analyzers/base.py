"""
Analyzer interface for transforming artifacts into findings.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List

from ..models import Finding, ProfileArtifact


class Analyzer(ABC):
    """Abstract analyzer contract."""

    @abstractmethod
    def analyze(self, artifacts: Iterable[ProfileArtifact]) -> List[Finding]:
        """Produce structured findings from raw artifacts."""
