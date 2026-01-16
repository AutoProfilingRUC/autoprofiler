#!/usr/bin/env python3
"""Workloads for exercising cProfile vs. child process CPU usage."""

from __future__ import annotations

import argparse
import multiprocessing
import time


def cpu_burn(duration: float) -> int:
    """Burn CPU for approximately ``duration`` seconds."""
    end_time = time.perf_counter() + duration
    total = 0
    while time.perf_counter() < end_time:
        for i in range(10_000):
            total += i * i
    return total


def run_single(duration: float) -> None:
    cpu_burn(duration)


def run_multi(duration: float) -> None:
    worker = multiprocessing.Process(target=cpu_burn, args=(duration,))
    worker.start()
    worker.join()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["single", "multi"], default="single")
    parser.add_argument("--duration", type=float, default=1.0)
    args = parser.parse_args()

    if args.mode == "single":
        run_single(args.duration)
    else:
        run_multi(args.duration)


if __name__ == "__main__":
    main()
