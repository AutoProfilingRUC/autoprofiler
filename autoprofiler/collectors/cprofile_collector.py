"""Execution wrapper that records cProfile statistics for opaque commands.

The collector wraps the target command using ``python -m cProfile`` because
it is the only reliable way to gather call-level statistics without knowing
anything about the target program. The raw ``.pstats`` file is preserved so
results are reproducible and can be re-analyzed later.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pstats

from ..models import ProfileArtifact
from .base import Collector


class CProfileCollector(Collector):
    """Collector that wraps execution with the built-in cProfile module."""

    def __init__(self, output_dir: Optional[Path] = None, top_n: int = 10) -> None:
        super().__init__(category="cpu")
        self.output_dir = output_dir or Path.cwd()
        self.top_n = top_n
        self._output_file: Optional[Path] = None

    def prepare_command(self, command: List[str]) -> List[str]:
        """Prefix the target command with ``python -m cProfile``.

        The output path is derived deterministically from the current UTC
        timestamp to avoid collisions while keeping artifacts easy to locate.
        """

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        self._output_file = Path(self.output_dir) / f"cprofile_{timestamp}.pstats"
        return [sys.executable, "-m", "cProfile", "-o", str(self._output_file), *command]

    def start(self, pid: int) -> None:  # noqa: ARG002 - pid recorded for interface compliance
        self._started_at = datetime.utcnow()

    def stop(self) -> ProfileArtifact:
        metrics = self._extract_metrics()
        raw_files: List[str] = []
        if self._output_file and self._output_file.exists():
            raw_files.append(str(self._output_file))
        return ProfileArtifact(
            collector=self.__class__.__name__,
            category=self.category,
            timestamp=self._stamp(),
            metrics=metrics,
            raw_files=raw_files,
        )

    def _extract_metrics(self) -> Dict[str, Any]:
        if not self._output_file or not self._output_file.exists():
            return {"total_calls": 0.0, "total_time": 0.0, "top_functions": []}

        stats = pstats.Stats(str(self._output_file))
        total_calls = float(stats.total_calls)
        total_time = float(stats.total_tt)

        top_functions = self._top_functions(stats)
        return {
            "total_calls": total_calls,
            "total_time": total_time,
            "top_functions": top_functions,
        }

    def _top_functions(self, stats: pstats.Stats) -> List[Dict[str, Any]]:
        sorted_entries = sorted(
            stats.stats.items(), key=lambda entry: entry[1][3], reverse=True
        )
        top_entries = []
        for (filename, line_no, func_name), values in sorted_entries[: self.top_n]:
            _, call_count, _, cumulative_time, _ = values
            top_entries.append(
                {
                    "function": f"{filename}:{line_no}:{func_name}",
                    "call_count": float(call_count),
                    "cumulative_time": float(cumulative_time),
                }
            )
        return top_entries
