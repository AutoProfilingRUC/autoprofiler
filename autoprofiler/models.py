"""
Core data models for the AutoProfiler pipeline.

These dataclasses follow the contracts outlined in CODEX_SPEC.md,
ensuring analyzers and collectors can exchange data without relying on
internal knowledge of the profiled program.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TargetProgram:
    """Immutable description of a program to be profiled.

    The program is treated as an opaque executable command. No assumptions
    are made about the underlying code or frameworks.
    """

    command: List[str]
    cwd: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    timeout: Optional[float] = None


@dataclass
class ProfileArtifact:
    """Raw collector output conforming to the profiling contract."""

    collector: str
    category: str
    timestamp: str
    metrics: Dict[str, Any]
    raw_files: List[str] = field(default_factory=list)


@dataclass
class Finding:
    """Structured analyzer output, backed by quantitative evidence."""

    finding_id: str
    pattern_id: str
    location: Optional[str]
    evidence: Dict[str, Any]
    confidence: float
    summary: str
    suggestions: List[str]


@dataclass
class ExecutionResult:
    """Execution metadata captured by the runner."""

    pid: Optional[int]
    returncode: Optional[int]
    started_at: datetime
    finished_at: datetime
    stdout: str
    stderr: str


@dataclass
class ProfilingSession:
    """Container for the full profiling session output."""

    target: TargetProgram
    execution: ExecutionResult
    artifacts: List[ProfileArtifact]
    findings: List[Finding] = field(default_factory=list)
