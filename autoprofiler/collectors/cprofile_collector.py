"""Execution wrapper that records cProfile statistics for opaque commands.

The collector wraps the target command using ``python -m cProfile`` because
it is the only reliable way to gather call-level statistics without knowing
anything about the target program. The raw ``.pstats`` file is preserved so
results are reproducible and can be re-analyzed later.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import pstats

from ..models import ProfileArtifact
from .base import Collector

logger = logging.getLogger(__name__)


class CProfileCollector(Collector):
    """Collector that wraps execution with the built-in cProfile module."""

    def __init__(self, output_dir: Optional[Path] = None, top_n: int = 10) -> None:
        super().__init__(category="cpu")
        self.output_dir = output_dir or Path.cwd()
        self.top_n = top_n
        self._output_file: Optional[Path] = None
        self._command_line: Optional[List[str]] = None

    def prepare_command(self, command: List[str]) -> List[str]:
        """Prefix the target command with ``python -m cProfile``.

        The output path is derived deterministically from the current UTC
        timestamp to avoid collisions while keeping artifacts easy to locate.
        """

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        self._output_file = Path(self.output_dir) / f"cprofile_{timestamp}.pstats"
        if command and _looks_like_python(command[0]):
            wrapped = [
                command[0],
                "-m",
                "cProfile",
                "-o",
                str(self._output_file),
                *command[1:],
            ]
        else:
            wrapped = [
                sys.executable,
                "-m",
                "cProfile",
                "-o",
                str(self._output_file),
                *command,
            ]
        self._command_line = wrapped
        logger.debug("CProfileCollector wrapping command: %s", self._command_line)
        return list(self._command_line)

    def start(self, pid: int | List[int]) -> None:  # noqa: ARG002 - pid recorded for interface compliance
        self._started_at = datetime.now(timezone.utc)

    def stop(self) -> ProfileArtifact:
        metrics = self._extract_metrics()
        if self._command_line:
            metrics["command_line"] = list(self._command_line)
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
        warnings: List[str] = []
        status = "ok"
        reason: Optional[str] = None
        if not self._output_file or not self._output_file.exists():
            warnings.append("cProfile output missing (prof file missing)")
            status = "missing"
            reason = "prof file missing"
            return {
                "total_calls": 0.0,
                "total_time": 0.0,
                "top_functions": [],
                "status": status,
                "reason": reason,
                "warnings": warnings,
                "cprofile_empty": 1.0,
            }

        if self._output_file.stat().st_size == 0:
            warnings.append(
                "cProfile output file empty; target may have exited before profiler started"
            )
            status = "empty_file"
            reason = "prof file empty"
            return {
                "total_calls": 0.0,
                "total_time": 0.0,
                "top_functions": [],
                "status": status,
                "reason": reason,
                "warnings": warnings,
                "cprofile_empty": 1.0,
            }

        try:
            stats = pstats.Stats(str(self._output_file))
        except Exception as exc:  # noqa: BLE001 - surface parsing failures to report
            warnings.append(f"cProfile stats parse failed: {exc}")
            status = "parse_error"
            reason = "stats parse failed"
            return {
                "total_calls": 0.0,
                "total_time": 0.0,
                "top_functions": [],
                "status": status,
                "reason": reason,
                "warnings": warnings,
                "cprofile_empty": 1.0,
            }

        total_calls = float(stats.total_calls)
        total_time = float(stats.total_tt)

        top_functions = self._top_functions(stats)
        cprofile_empty = 1.0 if total_calls == 0.0 and total_time == 0.0 else 0.0
        if cprofile_empty:
            status = "empty"
            reason = "stats empty"
            warnings.append(
                "cProfile stats empty; Python work may be in child processes or native extensions"
            )

        return {
            "total_calls": total_calls,
            "total_time": total_time,
            "top_functions": top_functions,
            "status": status,
            "reason": reason,
            "warnings": warnings,
            "cprofile_empty": cprofile_empty,
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


def _looks_like_python(executable: str) -> bool:
    name = Path(executable).name
    if executable == sys.executable:
        return True
    return name == "python" or name.startswith("python")
