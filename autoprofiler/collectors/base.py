"""
Collector interfaces for AutoProfiler.

Collectors attach to an existing PID and observe performance data without
modifying the target program or assuming its internal structure.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from ..models import ProfileArtifact


class Collector(ABC):
    """Abstract base class for data acquisition collectors."""

    def __init__(self, category: str) -> None:
        self.category = category
        self._started_at: Optional[datetime] = None

    def prepare_command(self, command: List[str]) -> List[str]:
        """Allow collectors to wrap or adjust the launch command.

        The default implementation returns the original command unchanged so
        collectors that only attach post-launch do not need to override it.
        """

        return command

    @abstractmethod
    def start(self, pid: int) -> None:
        """Attach to the target process.

        Collectors should capture any required context here, but they must
        avoid interfering with the target program's execution.
        """

    @abstractmethod
    def stop(self) -> ProfileArtifact:
        """Produce a ProfileArtifact summarizing observed data."""

    def _stamp(self) -> str:
        return datetime.utcnow().isoformat()
