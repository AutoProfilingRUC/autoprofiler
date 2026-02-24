"""
Structured JSON reporting for CLI workflows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from ..models import ProfilingSession, ProfileArtifact


def build_session_report(
    session: ProfilingSession,
    mode: str,
    platform: str,
    command: Optional[List[str]] = None,
    pids: Optional[List[int]] = None,
    diagnosis: Optional[List[Dict[str, object]]] = None,
) -> Dict[str, object]:
    timeseries: List[Dict[str, object]] = []
    summary: Dict[str, object] = {}
    warnings: List[str] = []
    artifacts_payload: List[Dict[str, object]] = []
    collector_commands: Dict[str, object] = {}
    cprofile_status: Optional[str] = None
    cprofile_empty = False
    child_cpu_avg: Optional[float] = None
    child_process_avg: Optional[float] = None
    psutil_include_children = False

    for artifact in session.artifacts:
        artifacts_payload.append(_artifact_payload(artifact))
        metrics = artifact.metrics
        if isinstance(metrics, dict):
            command_line = metrics.get("command_line")
            if command_line:
                collector_commands[artifact.collector] = command_line
            if "timeseries" in metrics and isinstance(metrics["timeseries"], list):
                timeseries = metrics["timeseries"]
            if "summary" in metrics and isinstance(metrics["summary"], dict):
                summary = metrics["summary"]
                child_summary = metrics["summary"].get("child_cpu_percent", {})
                if isinstance(child_summary, dict):
                    avg = child_summary.get("avg")
                    if isinstance(avg, (int, float)):
                        child_cpu_avg = float(avg)
                child_process_summary = metrics["summary"].get("child_process_count", {})
                if isinstance(child_process_summary, dict):
                    avg = child_process_summary.get("avg")
                    if isinstance(avg, (int, float)):
                        child_process_avg = float(avg)
            artifact_warnings = metrics.get("warnings")
            if isinstance(artifact_warnings, list):
                warnings.extend(str(value) for value in artifact_warnings)
            if metrics.get("status") == "unavailable":
                reason = metrics.get("reason", "collector unavailable")
                warnings.append(f"{artifact.collector}: {reason}")
            if artifact.collector == "CProfileCollector":
                cprofile_status = metrics.get("status")
                cprofile_empty = bool(metrics.get("cprofile_empty"))
            if artifact.collector == "PsutilProcessCollector":
                psutil_include_children = bool(metrics.get("include_children"))

    report = {
        "schema_version": "1.0",
        "metadata": {
            "mode": mode,
            "command": command or session.target.command,
            "pids": pids or ([session.execution.pid] if session.execution.pid else []),
            "platform": platform,
            "started_at": session.execution.started_at.isoformat(),
            "finished_at": session.execution.finished_at.isoformat(),
        },
        "timeseries": timeseries,
        "summary": summary,
        "artifacts": artifacts_payload,
        "diagnosis": diagnosis or [],
        "warnings": warnings,
    }
    if collector_commands:
        report["metadata"]["collector_commands"] = collector_commands
    if cprofile_status and psutil_include_children:
        warnings.append(
            "cProfile only profiles the attached Python process; child process call stacks are not captured"
        )
    if child_process_avg and child_process_avg > 0 and (not child_cpu_avg or child_cpu_avg > 0):
        warnings.append(
            "child process activity detected; cProfile attached to parent may miss child workload"
        )
    if cprofile_empty and child_cpu_avg and child_cpu_avg > 10.0:
        warnings.append(
            "cProfile did not capture child process work; consider profiling children "
            "or aggregating system CPU across the process tree"
        )
    if cprofile_status and cprofile_status != "ok" and not warnings:
        warnings.append(f"CProfileCollector reported status={cprofile_status}")
    return report


def write_json_report(report: Dict[str, object], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "profile_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report_path


def render_terminal_summary(report: Dict[str, object]) -> str:
    metadata = report.get("metadata", {})
    timeseries = report.get("timeseries", [])
    warnings = report.get("warnings", [])
    diagnosis = report.get("diagnosis", [])

    lines = [
        "AutoProfiler Summary",
        f"Mode: {metadata.get('mode')}",
        f"Command: {' '.join(metadata.get('command') or [])}",
        f"PIDs: {metadata.get('pids')}",
        f"Platform: {metadata.get('platform')}",
        f"Samples: {len(timeseries)}",
    ]
    if diagnosis:
        lines.append("Diagnosis:")
        for finding in diagnosis:
            lines.append(
                f"  - {finding.get('label')} (confidence={finding.get('confidence')})"
            )
    if warnings:
        lines.append("Warnings:")
        for warning in warnings:
            lines.append(f"  - {warning}")
    return "\n".join(lines)


def _artifact_payload(artifact: ProfileArtifact) -> Dict[str, object]:
    return {
        "collector": artifact.collector,
        "category": artifact.category,
        "timestamp": artifact.timestamp,
        "metrics": artifact.metrics,
        "files": artifact.raw_files,
    }
