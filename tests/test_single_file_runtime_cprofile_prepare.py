import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

from analysis.manager import analysis_manager
from analysis.task import analyze_python_file


class TestSingleFileRuntimeCprofilePrepare(unittest.TestCase):
    def test_runtime_mode_calls_prepare_command(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fp = root / "worker.py"
            fp.write_text("print('ok')\n", encoding="utf-8")

            analysis_id = analysis_manager.create_analysis(str(fp), fp.name, deepseek_config={})
            called = {"prepare": 0}

            def fake_prepare(self, command):
                called["prepare"] += 1
                return list(command) + ["--wrapped-for-test"]

            def fake_run(self, target, collectors):
                if "--wrapped-for-test" not in target.command:
                    raise AssertionError("cProfile prepare_command was not applied")
                started = datetime.now(timezone.utc)
                finished = started + timedelta(milliseconds=10)
                return SimpleNamespace(
                    target=SimpleNamespace(command=target.command, cwd=target.cwd, timeout=target.timeout),
                    execution=SimpleNamespace(
                        pid=1234,
                        returncode=0,
                        started_at=started,
                        finished_at=finished,
                    ),
                    duration=0.01,
                    exit_code=0,
                    findings=[],
                    artifacts=[
                        SimpleNamespace(
                            collector="CProfileCollector",
                            category="cpu",
                            metrics={},
                        )
                    ],
                )

            with patch(
                "autoprofiler.collectors.cprofile_collector.CProfileCollector.prepare_command",
                new=fake_prepare,
            ), patch("autoprofiler.runner.Runner.run", new=fake_run):
                analyze_python_file(str(fp), analysis_id, {}, root)

            analysis = analysis_manager.get_analysis(analysis_id) or {}
            self.assertEqual(analysis.get("status"), "completed")
            self.assertGreaterEqual(called["prepare"], 1)


if __name__ == "__main__":
    unittest.main()
