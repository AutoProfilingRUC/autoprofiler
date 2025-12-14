"""Sampling profiler integration via external ``py-spy`` binary.

The collector never modifies the target process. Instead it shells out to
``py-spy record`` to capture stack samples for a fixed duration. When the
binary is missing, the collector degrades gracefully by emitting a warning
artifact instead of raising an exception.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models import ProfileArtifact
from .base import Collector


class PySpyCollector(Collector):
    """External sampling collector built on ``py-spy``."""

    def __init__(
        self, duration: float = 5.0, output_dir: Optional[Path] = None, flamegraph: bool = True
    ) -> None:
        super().__init__(category="cpu")
        self.duration = duration
        self.output_dir = output_dir or Path.cwd()
        self.flamegraph = flamegraph
        self._process: Optional[subprocess.Popen[str]] = None
        self._output_file: Optional[Path] = None
        self._disabled_reason: Optional[str] = None
        self._stderr: str = ""

    def start(self, pid: int) -> None:
        pyspy_path = shutil.which("py-spy")
        if not pyspy_path:
            self._disabled_reason = "py-spy not available in PATH"
            return

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        suffix = "svg" if self.flamegraph else "raw"
        self._output_file = Path(self.output_dir) / f"pyspy_{timestamp}.{suffix}"

        command: List[str] = [
            pyspy_path,
            "record",
            "-p",
            str(pid),
            "--duration",
            str(self.duration),
            "-o",
            str(self._output_file),
        ]
        if not self.flamegraph:
            command.extend(["--format", "raw"])

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

        stderr_output = ""
        if self._process:
            _, stderr_output = self._process.communicate()
            self._stderr = stderr_output

        metrics = {
            "duration_sec": float(self.duration),
            "status": "captured" if self._output_file else "not_started",
        }
        if self._stderr:
            metrics["stderr"] = self._stderr

        raw_files: List[str] = []
        if self._output_file and self._output_file.exists():
            raw_files.append(str(self._output_file))
        else:
            metrics["status"] = "no_output"

        return ProfileArtifact(
            collector=self.__class__.__name__,
            category=self.category,
            timestamp=self._stamp(),
            metrics=metrics,
            raw_files=raw_files,
        )
