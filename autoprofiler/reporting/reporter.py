"""
Reporter utilities for producing human-readable and machine-readable outputs.
"""

from __future__ import annotations

import json
from typing import List

from ..models import ProfilingSession


def render_markdown(session: ProfilingSession) -> str:
    lines: List[str] = []
    lines.append(f"# AutoProfiler Report for `{ ' '.join(session.target.command) }`")
    lines.append("")
    lines.append("## Execution Summary")
    lines.append(f"- PID: {session.execution.pid}")
    lines.append(f"- Return Code: {session.execution.returncode}")
    lines.append(f"- Started At: {session.execution.started_at.isoformat()}")
    lines.append(f"- Finished At: {session.execution.finished_at.isoformat()}")
    lines.append(f"- Duration (s): {(session.execution.finished_at - session.execution.started_at).total_seconds():.3f}")
    lines.append("")

    lines.append("## Artifacts")
    for artifact in session.artifacts:
        lines.append(f"- {artifact.collector} ({artifact.category}): {artifact.metrics}")
    lines.append("")

    if not session.findings:
        lines.append("## Findings")
        lines.append("- No patterns matched; consider running with additional collectors.")
    else:
        lines.append("## Findings")
        for finding in session.findings:
            lines.append(f"- **{finding.pattern_id}** (confidence {finding.confidence:.2f}): {finding.summary}")
            lines.append(f"  - Evidence: {finding.evidence}")
            for suggestion in finding.suggestions:
                lines.append(f"  - Suggestion: {suggestion}")
    lines.append("")

    lines.append("## Verification Steps")
    lines.append("- Re-run the profiler to confirm reproducibility.")
    lines.append("- Compare metrics across runs to track regression or improvement.")
    return "\n".join(lines)


def render_findings_json(session: ProfilingSession) -> str:
    payload = {
        "target": {
            "command": session.target.command,
            "cwd": session.target.cwd,
            "timeout": session.target.timeout,
        },
        "execution": {
            "pid": session.execution.pid,
            "returncode": session.execution.returncode,
            "started_at": session.execution.started_at.isoformat(),
            "finished_at": session.execution.finished_at.isoformat(),
        },
        "artifacts": [
            {
                "collector": artifact.collector,
                "category": artifact.category,
                "timestamp": artifact.timestamp,
                "metrics": artifact.metrics,
                "raw_files": artifact.raw_files,
            }
            for artifact in session.artifacts
        ],
        "findings": [
            {
                "finding_id": finding.finding_id,
                "pattern_id": finding.pattern_id,
                "location": finding.location,
                "evidence": finding.evidence,
                "confidence": finding.confidence,
                "summary": finding.summary,
                "suggestions": finding.suggestions,
            }
            for finding in session.findings
        ],
    }
    return json.dumps(payload, indent=2)
