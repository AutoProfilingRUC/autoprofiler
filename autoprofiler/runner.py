"""
Subprocess runner responsible for executing opaque target programs.

The runner only controls process lifecycle and captures stdout/stderr.
It provides hooks for collectors to attach to the spawned PID without
modifying the target program itself.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from typing import Iterable, List

from .models import ExecutionResult, ProfilingSession, ProfileArtifact, TargetProgram
from .collectors.base import Collector


class Runner:
    """Launches target programs under profiling collectors."""

    def run(self, target: TargetProgram, collectors: Iterable[Collector]) -> ProfilingSession:
        started_at = datetime.utcnow()
        launch_command = self._prepare_command(target.command, collectors)
        process = subprocess.Popen(
            launch_command,
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
            for collector in collectors:
                artifacts.append(collector.stop())

        finished_at = datetime.utcnow()
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
    def _prepare_command(command: List[str], collectors: Iterable[Collector]) -> List[str]:
        prepared_command = list(command)
        for collector in collectors:
            prepared_command = collector.prepare_command(prepared_command)
        return prepared_command

    @staticmethod
    def _build_env(target: TargetProgram) -> dict:
        env = os.environ.copy()
        if target.env:
            env.update(target.env)
        return env
