"""
Linux perf collector for CPU sampling.

This collector shells out to ``perf record`` and captures perf.data
for post-processing (e.g., flamegraphs) outside AutoProfiler.
"""

from __future__ import annotations

import shutil
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..models import ProfileArtifact
from .base import Collector


class PerfCollector(Collector):
    """Best-effort perf record collector for Linux."""

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        duration: Optional[float] = None,
        include_children: bool = False,
    ) -> None:
        super().__init__(category="cpu")
        self.output_dir = output_dir or Path.cwd()
        self.duration = duration
        self.include_children = include_children
        self._process: Optional[subprocess.Popen[str]] = None
        self._output_file: Optional[Path] = None
        self._disabled_reason: Optional[str] = None
        self._stderr: str = ""
        self._warnings: List[str] = []

    def start(self, pid: int | List[int]) -> None:
        perf_path = shutil.which("perf")
        if not perf_path:
            self._disabled_reason = "perf not available in PATH"
            return

        pids = [pid] if isinstance(pid, int) else list(pid)
        pid_arg = ",".join(str(proc_pid) for proc_pid in pids)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        self._output_file = Path(self.output_dir) / f"perf_{timestamp}.data"

        command: List[str] = [
            perf_path,
            "record",
            "-g",
            "-o",
            str(self._output_file),
            "-p",
            pid_arg,
        ]
        if self.duration:
            command.extend(["--", "sleep", str(self.duration)])

        self._process = subprocess.Popen(  # noqa: S603 - external tool invocation is intentional
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def stop(self) -> ProfileArtifact:
        if self._disabled_reason:
            return ProfileArtifact(
                collector=self.__class__.__name__,
                category=self.category,
                timestamp=self._stamp(),
                metrics={"status": "unavailable", "reason": self._disabled_reason},
                raw_files=[],
            )

        if self._process and self._process.poll() is None:
            self._process.send_signal(signal.SIGINT)

        stderr_output = ""
        if self._process:
            _, stderr_output = self._process.communicate()
            self._stderr = stderr_output.strip()

        metrics = {
            "duration_sec": float(self.duration) if self.duration else None,
            "status": "captured" if self._output_file else "not_started",
            "include_children": self.include_children,
        }
        if self._stderr:
            metrics["stderr"] = self._stderr
            if "permission" in self._stderr.lower():
                self._warnings.append("perf permission denied; see README for sysctl hints.")

        raw_files: List[str] = []
        if self._output_file and self._output_file.exists():
            raw_files.append(str(self._output_file))
            readme_path = self._write_readme()
            if readme_path:
                raw_files.append(str(readme_path))
        else:
            metrics["status"] = "no_output"

        if self._warnings:
            metrics["warnings"] = self._warnings

        return ProfileArtifact(
            collector=self.__class__.__name__,
            category=self.category,
            timestamp=self._stamp(),
            metrics=metrics,
            raw_files=raw_files,
        )

    def _write_readme(self) -> Optional[Path]:
        if not self._output_file:
            return None
        readme_path = self._output_file.with_suffix(".README.txt")
        data_name = self._output_file.name
        content = (
            f"{data_name} captured. To generate a flamegraph:\n"
            f"  perf script -i {data_name} | stackcollapse-perf.pl > out.folded\n"
            "  flamegraph.pl out.folded > flamegraph.svg\n"
            "Tools: https://github.com/brendangregg/FlameGraph\n"
        )
        readme_path.write_text(content, encoding="utf-8")
        return readme_path
