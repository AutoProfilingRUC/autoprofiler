"""Demonstration script wiring collectors and analyzers together.

The demo keeps the workload simple and CPU-bound so it produces visible
artifacts for both psutil sampling and cProfile without relying on any
application-specific code.
"""

from __future__ import annotations

import sys
from pathlib import Path

from autoprofiler.analyzers.simple_analyzer import PatternMatchingAnalyzer
from autoprofiler.collectors import CProfileCollector, PsutilCollector
from autoprofiler.models import TargetProgram
from autoprofiler.patterns.loader import load_patterns
from autoprofiler.reporting.reporter import render_findings_json, render_markdown
from autoprofiler.runner import Runner


def _cpu_bound_command() -> TargetProgram:
    workload = """
import math
import time


def busy_work(duration: float = 3.5) -> float:
    end = time.perf_counter() + duration
    total = 0.0
    while time.perf_counter() < end:
        for value in range(8000):
            total += math.sqrt(value % 128)
    return total


if __name__ == "__main__":
    print(busy_work())
"""
    return TargetProgram(command=[sys.executable, "-c", workload], timeout=20)


def main() -> None:
    target = _cpu_bound_command()
    collectors = [PsutilCollector(sample_interval=0.25), CProfileCollector()]

    session = Runner().run(target, collectors=collectors)

    patterns_path = Path(__file__).resolve().parent / "patterns" / "performance.yaml"
    patterns = load_patterns(patterns_path)
    analyzer = PatternMatchingAnalyzer(patterns)
    session.findings = analyzer.analyze(session.artifacts)

    print(render_markdown(session))
    print("\nJSON Findings:\n")
    print(render_findings_json(session))


if __name__ == "__main__":
    main()
