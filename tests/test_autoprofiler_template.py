"""Template test case for running AutoProfiler against a target program.

This file is intentionally simple so you can plug in your own program
without needing to understand the entire codebase. By default it profiles a
short inline Python command, but you can override the command at runtime
using the ``AUTOPROFILER_TARGET`` environment variable.

Example usage:
    python -m unittest tests.test_autoprofiler_template
    AUTOPROFILER_TARGET="python my_script.py --flag" python -m unittest tests.test_autoprofiler_template
"""
from __future__ import annotations

import os
import shlex
from pathlib import Path
import unittest

from autoprofiler.analyzers.simple_analyzer import PatternMatchingAnalyzer
from autoprofiler.collectors.psutil_collector import PsutilCollector
from autoprofiler.models import TargetProgram
from autoprofiler.patterns.loader import load_patterns
from autoprofiler.reporting.reporter import render_markdown
from autoprofiler.runner import Runner

DEFAULT_COMMAND = ["python", "-c", "print('hello from AutoProfiler template')"]


def _resolve_target_command() -> list[str]:
    """Return the target command, preferring AUTOPROFILER_TARGET if set."""
    env_value = os.getenv("AUTOPROFILER_TARGET")
    if env_value:
        # shlex.split lets users provide a single string such as
        # "python my_app.py --flag" and have it parsed into args.
        return shlex.split(env_value)
    return DEFAULT_COMMAND


class AutoProfilerTemplateTest(unittest.TestCase):
    def test_profile_target_command(self) -> None:
        """Run the full profiling pipeline against a simple target command."""

        command = _resolve_target_command()
        target = TargetProgram(command=command, timeout=10)

        collectors = [PsutilCollector(sample_interval=0.2)]
        patterns = load_patterns(Path("autoprofiler/patterns/performance.yaml"))

        session = Runner().run(target, collectors=collectors)

        analyzer = PatternMatchingAnalyzer(patterns)
        session.findings = analyzer.analyze(session.artifacts)

        report = render_markdown(session)

        # Basic assertions to make sure the pipeline ran end-to-end.
        self.assertTrue(session.artifacts, "Collectors should produce artifacts")
        self.assertIsInstance(report, str)

        # Print the report so users can see the output when running the test.
        print("\n=== AutoProfiler report (template) ===\n")
        print(report)


if __name__ == "__main__":
    unittest.main()
