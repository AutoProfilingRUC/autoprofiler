"""
Rules-based diagnosis for cross-language process profiling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class DiagnosisFinding:
    label: str
    confidence: float
    evidence: Dict[str, object]


class DiagnosisAnalyzer:
    """Analyze time series metrics and emit bottleneck classifications."""

    def analyze(self, timeseries: List[Dict[str, float]]) -> List[DiagnosisFinding]:
        if not timeseries:
            return []

        cpu_values = [sample.get("cpu_percent", 0.0) for sample in timeseries]
        rss_values = [sample.get("rss_bytes", 0.0) for sample in timeseries]
        thread_values = [sample.get("num_threads", 0.0) for sample in timeseries]

        io_rates = self._rate_series(timeseries, "read_bytes", "t")
        io_rates = [
            read + write
            for read, write in zip(
                io_rates, self._rate_series(timeseries, "write_bytes", "t")
            )
        ]
        ctx_rates = self._rate_series(timeseries, "ctx_switches_voluntary", "t")
        ctx_rates = [
            voluntary + involuntary
            for voluntary, involuntary in zip(
                ctx_rates,
                self._rate_series(timeseries, "ctx_switches_involuntary", "t"),
            )
        ]

        findings: List[DiagnosisFinding] = []
        cpu_avg = _average(cpu_values)
        io_avg = _average(io_rates)
        ctx_avg = _average(ctx_rates)
        thread_avg = _average(thread_values)

        if cpu_avg is not None and io_avg is not None:
            if cpu_avg > 85 and io_avg < 1e6:
                findings.append(
                    DiagnosisFinding(
                        label="cpu_bound",
                        confidence=0.7,
                        evidence={"cpu_avg": cpu_avg, "io_rate_avg": io_avg},
                    )
                )
            if cpu_avg < 40 and io_avg > 5e6:
                findings.append(
                    DiagnosisFinding(
                        label="io_bound",
                        confidence=0.65,
                        evidence={"cpu_avg": cpu_avg, "io_rate_avg": io_avg},
                    )
                )

        rss_growth = self._rss_growth_ratio(rss_values)
        if rss_growth is not None and rss_growth > 0.2:
            findings.append(
                DiagnosisFinding(
                    label="memory_growth",
                    confidence=0.6,
                    evidence={"rss_growth_ratio": rss_growth},
                )
            )

        if cpu_avg is not None and ctx_avg is not None and thread_avg is not None:
            if cpu_avg < 60 and ctx_avg > 1e4 and thread_avg > 16:
                findings.append(
                    DiagnosisFinding(
                        label="scheduling_contention",
                        confidence=0.55,
                        evidence={
                            "cpu_avg": cpu_avg,
                            "ctx_switch_rate_avg": ctx_avg,
                            "threads_avg": thread_avg,
                        },
                    )
                )

        return findings

    @staticmethod
    def _rate_series(
        timeseries: List[Dict[str, float]], value_key: str, time_key: str
    ) -> List[float]:
        rates: List[float] = []
        for prev, cur in zip(timeseries, timeseries[1:]):
            delta_time = cur.get(time_key, 0.0) - prev.get(time_key, 0.0)
            if delta_time <= 0:
                rates.append(0.0)
                continue
            delta_value = cur.get(value_key, 0.0) - prev.get(value_key, 0.0)
            rates.append(delta_value / delta_time)
        return rates

    @staticmethod
    def _rss_growth_ratio(values: List[float]) -> Optional[float]:
        if not values:
            return None
        start = values[0]
        end = values[-1]
        if start <= 0:
            return None
        return (end - start) / start


def _average(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)
