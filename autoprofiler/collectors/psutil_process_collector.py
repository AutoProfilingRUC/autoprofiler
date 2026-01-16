"""
Cross-language process sampling collector using psutil.

This collector can aggregate metrics across a process tree and emit
time series + summary statistics for downstream diagnostics.
"""

from __future__ import annotations

import importlib.util
import statistics
import threading
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from ..models import ProfileArtifact
from .base import Collector


def _ensure_psutil_available() -> None:
    if importlib.util.find_spec("psutil") is None:
        raise RuntimeError(
            "psutil is required for PsutilProcessCollector but is not installed."
        )


@dataclass
class _ProcessSample:
    t: float
    cpu_percent: float
    rss_bytes: float
    vms_bytes: float
    read_bytes: float
    write_bytes: float
    num_threads: float
    ctx_switches_voluntary: float
    ctx_switches_involuntary: float
    open_files: float
    fd_count: float
    process_count: float


class PsutilProcessCollector(Collector):
    """Sample per-process metrics and aggregate across a process tree."""

    def __init__(self, sample_interval: float = 0.1, include_children: bool = False) -> None:
        super().__init__(category="system")
        self.sample_interval = sample_interval
        self.include_children = include_children
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._samples: List[_ProcessSample] = []
        self._root_pids: List[int] = []
        self._warnings: List[str] = []
        self._start_time: Optional[float] = None

    def start(self, pid: int | List[int]) -> None:
        _ensure_psutil_available()
        if isinstance(pid, int):
            self._root_pids = [pid]
        else:
            self._root_pids = list(pid)
        self._stop_event.clear()
        self._start_time = time.monotonic()
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
        import psutil  # noqa: WPS433 - lazy import for optional dependency

        # Prime CPU percent calculations.
        for process in self._iter_processes(psutil):
            try:
                process.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        while not self._stop_event.is_set():
            start_tick = time.monotonic()
            sample = self._collect_sample(psutil)
            if sample:
                self._samples.append(sample)
            elapsed = time.monotonic() - start_tick
            time.sleep(max(0.0, self.sample_interval - elapsed))

    def _collect_sample(self, psutil_module) -> Optional[_ProcessSample]:
        if self._start_time is None:
            return None

        cpu_total = 0.0
        rss_total = 0.0
        vms_total = 0.0
        read_total = 0.0
        write_total = 0.0
        thread_total = 0.0
        ctx_voluntary_total = 0.0
        ctx_involuntary_total = 0.0
        open_files_total = 0.0
        fd_total = 0.0
        process_count = 0.0

        for process in self._iter_processes(psutil_module):
            try:
                process_count += 1.0
                cpu_total += float(process.cpu_percent(interval=None))
                mem_info = process.memory_info()
                rss_total += float(mem_info.rss)
                vms_total += float(mem_info.vms)
                thread_total += float(process.num_threads())

                io_counters = None
                if hasattr(process, "io_counters"):
                    try:
                        io_counters = process.io_counters()
                    except (psutil_module.AccessDenied, OSError):
                        self._warnings.append("io_counters unavailable for some processes")
                if io_counters:
                    read_total += float(getattr(io_counters, "read_bytes", 0.0))
                    write_total += float(getattr(io_counters, "write_bytes", 0.0))

                if hasattr(process, "num_ctx_switches"):
                    try:
                        ctx = process.num_ctx_switches()
                        ctx_voluntary_total += float(getattr(ctx, "voluntary", 0.0))
                        ctx_involuntary_total += float(getattr(ctx, "involuntary", 0.0))
                    except (psutil_module.AccessDenied, OSError):
                        self._warnings.append("ctx_switches unavailable for some processes")

                if hasattr(process, "open_files"):
                    try:
                        open_files_total += float(len(process.open_files()))
                    except (psutil_module.AccessDenied, OSError):
                        self._warnings.append("open_files unavailable for some processes")

                if hasattr(process, "num_fds"):
                    try:
                        fd_total += float(process.num_fds())
                    except (psutil_module.AccessDenied, OSError):
                        self._warnings.append("fd_count unavailable for some processes")
            except (psutil_module.NoSuchProcess, psutil_module.AccessDenied):
                continue

        t = time.monotonic() - self._start_time
        return _ProcessSample(
            t=t,
            cpu_percent=cpu_total,
            rss_bytes=rss_total,
            vms_bytes=vms_total,
            read_bytes=read_total,
            write_bytes=write_total,
            num_threads=thread_total,
            ctx_switches_voluntary=ctx_voluntary_total,
            ctx_switches_involuntary=ctx_involuntary_total,
            open_files=open_files_total,
            fd_count=fd_total,
            process_count=process_count,
        )

    def _iter_processes(self, psutil_module) -> Iterable:
        processes = []
        seen_pids = set()
        for pid in list(self._root_pids):
            try:
                root = psutil_module.Process(pid)
                candidates = [root]
                if self.include_children:
                    candidates.extend(root.children(recursive=True))
                for candidate in candidates:
                    if candidate.pid in seen_pids:
                        continue
                    seen_pids.add(candidate.pid)
                    processes.append(candidate)
            except (psutil_module.NoSuchProcess, psutil_module.AccessDenied):
                continue
        return processes

    def _summarize(self) -> Dict[str, object]:
        timeseries = [self._sample_to_dict(sample) for sample in self._samples]
        summary: Dict[str, Dict[str, float]] = {}
        numeric_keys = [
            "cpu_percent",
            "rss_bytes",
            "vms_bytes",
            "read_bytes",
            "write_bytes",
            "num_threads",
            "ctx_switches_voluntary",
            "ctx_switches_involuntary",
            "open_files",
            "fd_count",
            "process_count",
        ]
        for key in numeric_keys:
            values = [sample[key] for sample in timeseries if key in sample]
            if not values:
                continue
            summary[key] = self._summary_stats(values)

        return {
            "sample_interval_ms": float(self.sample_interval * 1000),
            "include_children": self.include_children,
            "root_pids": list(self._root_pids),
            "sample_count": float(len(timeseries)),
            "timeseries": timeseries,
            "summary": summary,
            "warnings": sorted(set(self._warnings)),
        }

    @staticmethod
    def _sample_to_dict(sample: _ProcessSample) -> Dict[str, float]:
        return {
            "t": float(sample.t),
            "cpu_percent": float(sample.cpu_percent),
            "rss_bytes": float(sample.rss_bytes),
            "vms_bytes": float(sample.vms_bytes),
            "read_bytes": float(sample.read_bytes),
            "write_bytes": float(sample.write_bytes),
            "num_threads": float(sample.num_threads),
            "ctx_switches_voluntary": float(sample.ctx_switches_voluntary),
            "ctx_switches_involuntary": float(sample.ctx_switches_involuntary),
            "open_files": float(sample.open_files),
            "fd_count": float(sample.fd_count),
            "process_count": float(sample.process_count),
        }

    @staticmethod
    def _summary_stats(values: List[float]) -> Dict[str, float]:
        sorted_values = sorted(values)
        return {
            "min": float(sorted_values[0]),
            "max": float(sorted_values[-1]),
            "p50": float(statistics.median(sorted_values)),
            "p95": float(
                sorted_values[int(round(0.95 * (len(sorted_values) - 1)))]
            ),
        }
