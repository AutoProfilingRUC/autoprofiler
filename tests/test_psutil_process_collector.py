from __future__ import annotations

import sys
import time
import types
import unittest
from unittest.mock import patch

from autoprofiler.collectors.psutil_process_collector import PsutilProcessCollector


class PsutilProcessCollectorTest(unittest.TestCase):
    def test_aggregates_process_tree(self) -> None:
        class FakeCounters:
            def __init__(self, read_bytes: float, write_bytes: float) -> None:
                self.read_bytes = read_bytes
                self.write_bytes = write_bytes

        class FakeCtxSwitches:
            def __init__(self, voluntary: float, involuntary: float) -> None:
                self.voluntary = voluntary
                self.involuntary = involuntary

        class FakeMemInfo:
            def __init__(self, rss: float, vms: float) -> None:
                self.rss = rss
                self.vms = vms

        class FakeProcess:
            def __init__(self, pid: int, children: list[int]) -> None:
                self.pid = pid
                self._children = children

            def cpu_percent(self, interval=None):  # noqa: ARG002
                return 5.0 if self.pid == 100 else 7.5

            def memory_info(self):
                return FakeMemInfo(rss=100.0 if self.pid == 100 else 200.0, vms=300.0)

            def io_counters(self):
                return FakeCounters(read_bytes=1000.0, write_bytes=2000.0)

            def num_threads(self):
                return 2 if self.pid == 100 else 3

            def num_ctx_switches(self):
                return FakeCtxSwitches(voluntary=10.0, involuntary=5.0)

            def open_files(self):
                return ["a", "b"]

            def num_fds(self):
                return 4

            def children(self, recursive=True):  # noqa: ARG002
                return [FakeProcess(pid, []) for pid in self._children]

        fake_psutil = types.SimpleNamespace(
            Process=lambda pid: FakeProcess(pid, [200] if pid == 100 else []),
            NoSuchProcess=RuntimeError,
            AccessDenied=RuntimeError,
        )

        with patch.dict(sys.modules, {"psutil": fake_psutil}):
            with patch(
                "autoprofiler.collectors.psutil_process_collector.importlib.util.find_spec",
                return_value=True,
            ):
                collector = PsutilProcessCollector(sample_interval=0.01, include_children=True)
                collector.start(100)
                time.sleep(0.05)
                artifact = collector.stop()

        metrics = artifact.metrics
        self.assertGreater(metrics["sample_count"], 0)
        summary = metrics["summary"]
        self.assertAlmostEqual(summary["cpu_percent"]["max"], 12.5)
        self.assertAlmostEqual(summary["rss_bytes"]["max"], 300.0)


if __name__ == "__main__":
    unittest.main()
