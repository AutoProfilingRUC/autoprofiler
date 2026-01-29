"""
CLI entry point for AutoProfiler.
"""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .analyzers.diagnosis_analyzer import DiagnosisAnalyzer
from .collectors.cprofile_collector import CProfileCollector
from .collectors.perf_collector import PerfCollector
from .collectors.psutil_process_collector import PsutilProcessCollector
from .collectors.pyspy_collector import PySpyCollector
from .models import TargetProgram
from .processes import expand_process_tree, resolve_pids_by_name
from .reporting.session_reporter import (
    build_session_report,
    render_terminal_summary,
    write_json_report,
)
from .runner import AttachRunner, Runner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autoprofiler")
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--duration", type=float, default=None)
    common.add_argument("--sample-interval", type=float, default=100.0)
    common.add_argument("--include-children", action="store_true")
    common.add_argument("--output", type=str, default=None)
    common.add_argument("--collect", type=str, default=None)

    run_parser = subparsers.add_parser("run", parents=[common])
    run_parser.add_argument("--cwd", type=str, default=None)
    run_parser.add_argument("--env", action="append", default=[])
    run_parser.add_argument("cmd", nargs=argparse.REMAINDER)

    attach_parser = subparsers.add_parser("attach", parents=[common])
    attach_parser.add_argument("--pid", action="append", type=int, default=[])
    attach_parser.add_argument("--name", type=str, default=None)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    output_dir = _resolve_output_dir(args.output)
    platform_name = platform.system().lower()
    collectors = _resolve_collectors(
        args.collect,
        output_dir=output_dir,
        sample_interval_ms=args.sample_interval,
        duration=args.duration,
        include_children=args.include_children,
        platform_name=platform_name,
    )

    try:
        if args.command == "run":
            command = _normalize_command(args.cmd)
            if not command:
                parser.error("run requires a command after --")
            try:
                env = _parse_env(args.env)
            except ValueError as exc:
                parser.error(str(exc))
            target = TargetProgram(
                command=_apply_collector_wrappers(command, collectors),
                cwd=args.cwd,
                env=env,
                timeout=args.duration,
            )

            session = _run_with_collectors(target, collectors)
            report = _build_report(session, "run", platform_name, command, None)
        else:
            pids = _resolve_attach_pids(args.pid, args.name)
            if args.include_children:
                pids = expand_process_tree(pids)
            if not pids:
                parser.error("attach requires at least one pid or --name to match processes")
            duration = args.duration or 30.0
            session = _attach_with_collectors(pids, duration, collectors)
            report = _build_report(session, "attach", platform_name, None, pids)

        report_path = write_json_report(report, output_dir)
        print(render_terminal_summary(report))
        print(f"JSON report written to {report_path}")
        return 0
    except KeyboardInterrupt:
        print("Interrupted; stopping collectors.", file=sys.stderr)
        return 130


def _resolve_output_dir(output: Optional[str]) -> Path:
    if output:
        return Path(output)
    return Path.cwd() / "autoprofiler-output" / _timestamp()


def _timestamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _parse_env(env_entries: List[str]) -> Dict[str, str]:
    env: Dict[str, str] = {}
    for entry in env_entries:
        if "=" not in entry:
            raise ValueError(f"Invalid --env value: {entry}. Expected KEY=VALUE.")
        key, value = entry.split("=", 1)
        env[key] = value
    return env


def _normalize_command(cmd: List[str]) -> List[str]:
    if not cmd:
        return []
    if cmd[0] == "--":
        return cmd[1:]
    return cmd


def _resolve_collectors(
    collect_option: Optional[str],
    output_dir: Path,
    sample_interval_ms: float,
    duration: Optional[float],
    include_children: bool,
    platform_name: str,
):
    requested = _parse_collectors(collect_option, platform_name)
    collectors = []
    for name in requested:
        if name == "psutil":
            collectors.append(
                PsutilProcessCollector(
                    sample_interval=sample_interval_ms / 1000.0,
                    include_children=include_children,
                )
            )
        elif name == "perf":
            collectors.append(
                PerfCollector(
                    output_dir=output_dir,
                    duration=duration,
                    include_children=include_children,
                )
            )
        elif name == "cprofile":
            collectors.append(
                CProfileCollector(output_dir=output_dir, include_children=include_children)
            )
        elif name == "pyspy":
            collectors.append(PySpyCollector(duration=duration or 5.0, output_dir=output_dir))
    return collectors


def _parse_collectors(collect_option: Optional[str], platform_name: str) -> List[str]:
    if collect_option:
        return [item.strip().lower() for item in collect_option.split(",") if item.strip()]
    if platform_name == "linux":
        return ["psutil", "perf"]
    return ["psutil"]


def _apply_collector_wrappers(command: List[str], collectors) -> List[str]:
    wrapped = list(command)
    for collector in collectors:
        prepare = getattr(collector, "prepare_command", None)
        if callable(prepare):
            wrapped = prepare(wrapped)
    return wrapped


def _resolve_attach_pids(pids: List[int], name: Optional[str]) -> List[int]:
    if pids:
        return pids
    if name:
        return resolve_pids_by_name(name)
    return []


def _run_with_collectors(target: TargetProgram, collectors):
    try:
        return Runner().run(target, collectors)
    except KeyboardInterrupt:
        for collector in collectors:
            collector.stop()
        raise


def _attach_with_collectors(pids: List[int], duration: float, collectors):
    try:
        return AttachRunner().run(pids, duration, collectors)
    except KeyboardInterrupt:
        for collector in collectors:
            collector.stop()
        raise


def _build_report(
    session,
    mode: str,
    platform_name: str,
    command: Optional[List[str]],
    pids: Optional[List[int]],
):
    diagnosis_finding = DiagnosisAnalyzer().analyze(
        _extract_timeseries(session.artifacts)
    )
    diagnosis_payload = [
        {"label": finding.label, "confidence": finding.confidence, "evidence": finding.evidence}
        for finding in diagnosis_finding
    ]
    return build_session_report(
        session,
        mode=mode,
        platform=platform_name,
        command=command,
        pids=pids,
        diagnosis=diagnosis_payload,
    )


def _extract_timeseries(artifacts):
    for artifact in artifacts:
        metrics = artifact.metrics
        if isinstance(metrics, dict) and "timeseries" in metrics:
            return metrics.get("timeseries", [])
    return []


if __name__ == "__main__":
    sys.exit(main())
