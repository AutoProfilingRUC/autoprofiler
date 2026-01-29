from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from autoprofiler.analyzers.simple_analyzer import PatternMatchingAnalyzer
from autoprofiler.collectors.cprofile_collector import CProfileCollector
from autoprofiler.collectors.psutil_process_collector import PsutilProcessCollector
from autoprofiler.models import TargetProgram
from autoprofiler.patterns.loader import load_patterns
from autoprofiler.reporting.session_reporter import build_session_report
from autoprofiler.runner import Runner

FIXTURE = Path(__file__).parent / "fixtures" / "cprofile_workload.py"


class CProfileChildProcessTest(unittest.TestCase):
    def test_single_process_cprofile_has_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = CProfileCollector(output_dir=Path(tmpdir))
            command = [
                sys.executable,
                str(FIXTURE),
                "--mode",
                "single",
                "--duration",
                "0.6",
            ]
            target = TargetProgram(
                command=collector.prepare_command(command),
                timeout=5,
            )
            session = Runner().run(target, collectors=[collector])

        artifact = next(
            a for a in session.artifacts if a.collector == "CProfileCollector"
        )
        self.assertGreater(artifact.metrics.get("total_calls", 0), 0)
        self.assertTrue(
            any(
                "cpu_burn" in entry.get("function", "")
                for entry in artifact.metrics.get("top_functions", [])
            )
        )

    def test_multi_process_warns_and_skips_few_calls_inference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cprofile = CProfileCollector(output_dir=Path(tmpdir))
            psutil_collector = PsutilProcessCollector(
                sample_interval=0.1,
                include_children=True,
            )
            command = [
                sys.executable,
                str(FIXTURE),
                "--mode",
                "multi",
                "--duration",
                "0.8",
            ]
            target = TargetProgram(
                command=cprofile.prepare_command(command),
                timeout=5,
            )
            session = Runner().run(target, collectors=[psutil_collector, cprofile])

        patterns = load_patterns(
            Path(__file__).parent.parent / "autoprofiler" / "patterns" / "performance.yaml"
        )
        analyzer = PatternMatchingAnalyzer(patterns)
        findings = analyzer.analyze(session.artifacts)
        finding_ids = {finding.pattern_id for finding in findings}

        report = build_session_report(
            session,
            mode="run",
            platform="test",
            command=command,
            pids=None,
        )
        warnings = report.get("warnings", [])

        self.assertNotIn("cpu_intensive_few_calls", finding_ids)
        self.assertTrue(
            any(
                "child process" in warning or "child" in warning for warning in warnings
            )
        )


if __name__ == "__main__":
    unittest.main()
