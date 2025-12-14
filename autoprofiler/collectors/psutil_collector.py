"""
Process-level CPU and memory sampling using psutil.

This collector observes the target PID at a fixed interval, summarizing
utilization metrics without injecting instrumentation into the process.
"""

from __future__ import annotations

import importlib.util
import threading
import time
from typing import Dict, List, Optional

from ..models import ProfileArtifact
from .base import Collector


def _ensure_psutil_available() -> None:
    if importlib.util.find_spec("psutil") is None:
        raise RuntimeError(
            "psutil is required for PsutilCollector but is not installed in the environment."
        )


class PsutilCollector(Collector):
    """Lightweight sampling collector built on psutil."""

    def __init__(self, sample_interval: float = 0.5) -> None:
        super().__init__(category="system")
        self.sample_interval = sample_interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._samples: List[Dict[str, float]] = []
        self._pid: Optional[int] = None

    def start(self, pid: int) -> None:
        _ensure_psutil_available()
        self._pid = pid
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self) -> ProfileArtifact:
        self._stop_event.set()
        if self._thread:
            self._thread.join()

        metrics = self._summarize()
        return ProfileArtifact(
            collector=self.__class__.__name__,
            category=self.category,
            timestamp=self._stamp(),
            metrics=metrics,
            raw_files=[],
        )

    def _sample_loop(self) -> None:
        import psutil  # noqa: WPS433 - imported here to respect optional dependency resolution

        process = psutil.Process(self._pid)
        while not self._stop_event.is_set():
            try:
                cpu = process.cpu_percent(interval=None)
                mem_info = process.memory_info()
                self._samples.append(
                    {
                        "cpu_percent": cpu,
                        "rss_bytes": float(mem_info.rss),
                        "vms_bytes": float(mem_info.vms),
                    }
                )
            finally:
                time.sleep(self.sample_interval)

    def _summarize(self) -> Dict[str, float]:
        if not self._samples:
            return {"sample_count": 0.0}

        cpu_values = [sample["cpu_percent"] for sample in self._samples]
        rss_values = [sample["rss_bytes"] for sample in self._samples]
        vms_values = [sample["vms_bytes"] for sample in self._samples]
        return {
            "sample_count": float(len(self._samples)),
            "cpu_percent_avg": float(sum(cpu_values) / len(cpu_values)),
            "cpu_percent_max": float(max(cpu_values)),
            "rss_bytes_max": float(max(rss_values)),
            "vms_bytes_max": float(max(vms_values)),
        }
