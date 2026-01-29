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
    root_cpu_percent: float
    child_cpu_percent: float
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
    child_process_count: float


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
        self._process_cache: Dict[int, object] = {}

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
        for process in self._iter_processes(psutil, include_children=True):
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

        root_processes, child_processes = self._iter_root_and_children(psutil_module)
        root_pids = {process.pid for process in root_processes}
        child_pids = {process.pid for process in child_processes}
        all_processes = {process.pid: process for process in root_processes + child_processes}

        cpu_total = 0.0
        root_cpu_total = 0.0
        child_cpu_total = 0.0
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
        child_process_count = 0.0

        for pid, process in all_processes.items():
            try:
                cpu_value = float(process.cpu_percent(interval=None))
                if pid in root_pids:
                    root_cpu_total += cpu_value
                if pid in child_pids:
                    child_cpu_total += cpu_value
                    child_process_count += 1.0

                if self.include_children or pid in root_pids:
                    process_count += 1.0
                    cpu_total += cpu_value
                    mem_info = process.memory_info()
                    rss_total += float(mem_info.rss)
                    vms_total += float(mem_info.vms)
                    thread_total += float(process.num_threads())

                    io_counters = None
                    if hasattr(process, "io_counters"):
                        try:
                            io_counters = process.io_counters()
                        except (psutil_module.AccessDenied, OSError):
                            self._warnings.append(
                                "io_counters unavailable for some processes"
                            )
                    if io_counters:
                        read_total += float(getattr(io_counters, "read_bytes", 0.0))
                        write_total += float(getattr(io_counters, "write_bytes", 0.0))

                    if hasattr(process, "num_ctx_switches"):
                        try:
                            ctx = process.num_ctx_switches()
                            ctx_voluntary_total += float(getattr(ctx, "voluntary", 0.0))
                            ctx_involuntary_total += float(
                                getattr(ctx, "involuntary", 0.0)
                            )
                        except (psutil_module.AccessDenied, OSError):
                            self._warnings.append(
                                "ctx_switches unavailable for some processes"
                            )

                    if hasattr(process, "open_files"):
                        try:
                            open_files_total += float(len(process.open_files()))
                        except (psutil_module.AccessDenied, OSError):
                            self._warnings.append(
                                "open_files unavailable for some processes"
                            )

                    if hasattr(process, "num_fds"):
                        try:
                            fd_total += float(process.num_fds())
                        except (psutil_module.AccessDenied, OSError):
                            self._warnings.append("fd_count unavailable for some processes")
            except (psutil_module.NoSuchProcess, psutil_module.AccessDenied):
                self._process_cache.pop(pid, None)
                continue

        t = time.monotonic() - self._start_time
        return _ProcessSample(
            t=t,
            cpu_percent=cpu_total,
            root_cpu_percent=root_cpu_total,
            child_cpu_percent=child_cpu_total,
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
            child_process_count=child_process_count,
        )

    def _iter_processes(
        self, psutil_module, include_children: Optional[bool] = None
    ) -> Iterable:
        include_children = self.include_children if include_children is None else include_children
        processes = []
        seen_pids = set()
        for pid in list(self._root_pids):
            try:
                root = self._get_process(pid, psutil_module)
                if root is None:
                    continue
                candidates = [root]
                if include_children:
                    candidates.extend(root.children(recursive=True))
                for candidate in candidates:
                    if candidate.pid in seen_pids:
                        continue
                    seen_pids.add(candidate.pid)
                    cached = self._get_process(candidate.pid, psutil_module)
                    if cached is None:
                        continue
                    processes.append(cached)
            except (psutil_module.NoSuchProcess, psutil_module.AccessDenied):
                continue
        return processes

    def _iter_root_and_children(self, psutil_module) -> tuple[list, list]:
        root_processes = []
        child_processes = []
        seen_pids = set()
        for pid in list(self._root_pids):
            try:
                root = self._get_process(pid, psutil_module)
                if root is None:
                    continue
                if root.pid not in seen_pids:
                    root_processes.append(root)
                    seen_pids.add(root.pid)
                for child in root.children(recursive=True):
                    if child.pid in seen_pids:
                        continue
                    cached_child = self._get_process(child.pid, psutil_module)
                    if cached_child is None:
                        continue
                    child_processes.append(cached_child)
                    seen_pids.add(cached_child.pid)
            except (psutil_module.NoSuchProcess, psutil_module.AccessDenied):
                continue
        return root_processes, child_processes

    def _get_process(self, pid: int, psutil_module):
        process = self._process_cache.get(pid)
        if process is not None:
            return process
        try:
            process = psutil_module.Process(pid)
        except (psutil_module.NoSuchProcess, psutil_module.AccessDenied):
            return None
        self._process_cache[pid] = process
        return process

    def _summarize(self) -> Dict[str, object]:
        timeseries = [self._sample_to_dict(sample) for sample in self._samples]
        summary: Dict[str, Dict[str, float]] = {}
        numeric_keys = [
            "cpu_percent",
            "root_cpu_percent",
            "child_cpu_percent",
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
            "child_process_count",
        ]
        for key in numeric_keys:
            values = [sample[key] for sample in timeseries if key in sample]
            if not values:
                continue
            summary[key] = self._summary_stats(values)

        self._maybe_warn_child_workload(timeseries)

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
            "root_cpu_percent": float(sample.root_cpu_percent),
            "child_cpu_percent": float(sample.child_cpu_percent),
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
            "child_process_count": float(sample.child_process_count),
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
            "avg": float(sum(sorted_values) / len(sorted_values)),
        }

    def _maybe_warn_child_workload(self, timeseries: List[Dict[str, float]]) -> None:
        if not timeseries:
            return
        child_cpu_values = [sample.get("child_cpu_percent", 0.0) for sample in timeseries]
        root_cpu_values = [sample.get("root_cpu_percent", 0.0) for sample in timeseries]
        child_proc_values = [
            sample.get("child_process_count", 0.0) for sample in timeseries
        ]
        if not child_cpu_values or not child_proc_values:
            return

        child_cpu_avg = sum(child_cpu_values) / len(child_cpu_values)
        root_cpu_avg = sum(root_cpu_values) / len(root_cpu_values)
        child_proc_avg = sum(child_proc_values) / len(child_proc_values)
        if child_proc_avg <= 0 or child_cpu_avg < 10.0:
            return

        if root_cpu_avg <= 0.0 or child_cpu_avg > root_cpu_avg * 1.5:
            self._warnings.append(
                "child_process_workload_detected: child CPU higher than parent; "
                "profilers attached to the parent may miss child work"
            )
