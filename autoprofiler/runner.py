"""
Subprocess runner responsible for executing opaque target programs.

The runner only controls process lifecycle and captures stdout/stderr.
It provides hooks for collectors to attach to the spawned PID without
modifying the target program itself.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Iterable, List

from .models import ExecutionResult, ProfilingSession, ProfileArtifact, TargetProgram
from .collectors.base import Collector


class Runner:
    """Launches target programs under profiling collectors."""

    logger = logging.getLogger(__name__)

    def run(self, target: TargetProgram, collectors: Iterable[Collector]) -> ProfilingSession:
        started_at = datetime.now(timezone.utc)
        command = self._resolve_command(target.command)
        if command != target.command:
            self.logger.debug("Runner normalized command from %s to %s", target.command, command)
        self.logger.debug(
            "Runner launching command: %s (cwd=%s)",
            command,
            target.cwd,
        )
        process = subprocess.Popen(
            command,
            cwd=target.cwd,
            env=self._build_env(target),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        artifacts: List[ProfileArtifact] = []
        for collector in collectors:
            # 中英文注释: 每个采集器都在独立的观察通道上工作 (collectors observe independently)
            collector.start(process.pid)

        try:
            stdout, stderr = process.communicate(timeout=target.timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        finally:
            if stdout:
                self.logger.debug("Runner captured stdout: %s", stdout)
            if stderr:
                self.logger.debug("Runner captured stderr: %s", stderr)
            for collector in collectors:
                artifacts.append(collector.stop())

        finished_at = datetime.now(timezone.utc)
        execution = ExecutionResult(
            pid=process.pid,
            returncode=process.returncode,
            started_at=started_at,
            finished_at=finished_at,
            stdout=stdout,
            stderr=stderr,
        )

        return ProfilingSession(
            target=target,
            execution=execution,
            artifacts=artifacts,
            findings=[],
        )

    @staticmethod
    def _build_env(target: TargetProgram) -> dict:
        env = os.environ.copy()
        if target.env:
            env.update(target.env)
        return env

    @staticmethod
    def _resolve_command(command: List[str]) -> List[str]:
        if not command:
            return command
        resolved = list(command)
        executable = str(resolved[0] or "")
        lowered = executable.lower()
        # Linux images may only provide `python3`; map bare `python` to current interpreter.
        if lowered in {"python", "python.exe"} and shutil.which(executable) is None:
            resolved[0] = sys.executable
        return resolved


class AttachRunner:
    """Attach to running PIDs without spawning a subprocess."""

    def run(
        self, pids: List[int], duration: float, collectors: Iterable[Collector]
    ) -> ProfilingSession:
        started_at = datetime.now(timezone.utc)
        artifacts: List[ProfileArtifact] = []

        for collector in collectors:
            collector.start(pids)

        try:
            time.sleep(duration)
        finally:
            for collector in collectors:
                artifacts.append(collector.stop())

        finished_at = datetime.now(timezone.utc)
        execution = ExecutionResult(
            pid=pids[0] if pids else None,
            returncode=None,
            started_at=started_at,
            finished_at=finished_at,
            stdout="",
            stderr="",
        )

        return ProfilingSession(
            target=TargetProgram(command=[], cwd=None, env=None, timeout=None),
            execution=execution,
            artifacts=artifacts,
            findings=[],
        )
