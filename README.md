# AutoProfiler (Python-based Automatic Profiling Tool)

## 1. Project Overview

AutoProfiler is an **automatic performance profiling and diagnosis tool** implemented in **Python**.

The core goal of this project is:

> Given an **unknown target program** (usually Python, but not limited by project structure),
> automatically collect performance data, analyze performance patterns,
> and generate **evidence-based performance diagnostics and optimization suggestions**.

This project **does NOT assume**:

* prior knowledge of the target program
* access to or modification of the target program’s source code
* specific frameworks, coding styles, or workloads

AutoProfiler is designed as a **black-box / semi-black-box profiler**, similar in philosophy to:

* `perf`
* `py-spy`
* `valgrind`

but specialized for **Python ecosystems** and **AI-assisted explanation**.

---

## 2. Non-Goals (Very Important)

To avoid ambiguity, AutoProfiler explicitly does **NOT** aim to:

* ❌ Fully understand business logic of the target program
* ❌ Automatically rewrite or refactor code by default
* ❌ Guarantee performance improvement after suggestions
* ❌ Depend on decorators, instrumentation, or source modification
* ❌ Be a full IDE or debugger

Instead, the project focuses on **profiling facts → diagnosis → verifiable guidance**.

---

## 3. High-Level Architecture

AutoProfiler follows a **three-stage pipeline**:

```
[ Runner ]
    ↓
[ Collectors ]  → raw profiling artifacts
    ↓
[ Analyzers ]   → structured findings (pattern-based)
    ↓
[ LLM Reporter ]→ human-readable diagnosis & suggestions
```

Each stage is **strictly decoupled** and communicates through well-defined data structures.

---

## 4. Target Program Model (Critical Assumption)

The target program is treated as an **opaque executable command**.

```text
TargetProgram = {
    command: ["python", "main.py", "--arg1", "value"],
    cwd: "/path/to/workdir",
    env: { ... },
    timeout: optional
}
```

---

## 5. Runner Responsibilities

The `Runner` module is responsible for:

* Launching the target program via `subprocess`
* Capturing:

  * PID(s)
  * stdout / stderr
  * exit status
  * runtime duration
* Enforcing:

  * time limits
  * environment isolation (best-effort)
* Providing a **stable execution context** for collectors

The Runner **must not**:

* parse or interpret program output
* inject code into the target
* depend on language-specific internals

---

## 6. Collectors: Data Acquisition Layer

Collectors are **pluggable, independent modules** that observe the running process.

Each collector:

* Attaches to the target PID (or wraps execution)
* Produces a `ProfileArtifact`
* Must be safe for unknown programs

### Expected Collectors (Initial MVP)

* **cProfileCollector**

  * Uses `python -m cProfile`
  * Collects call counts and cumulative time
  * Wraps the target command via `Collector.prepare_command`
* **PySpyCollector**

  * Sampling-based CPU profiler
  * Low overhead, no source modification
  * Gracefully degrades with a warning when the `py-spy` binary is unavailable
* **PsutilCollector**

  * System-level metrics:

    * CPU usage
    * RSS memory
    * I/O activity
    * thread count

Collectors should **never interpret results** — only collect and serialize.

---

## 7. Artifacts and Data Format

All collectors output standardized artifacts.

```python
ProfileArtifact = {
    "collector": "py-spy",
    "type": "cpu-sampling",
    "timestamp": "...",
    "raw_files": [...],
    "metrics": {...}
}
```

Artifacts must be:

* Serializable (JSON-compatible)
* Persisted to disk
* Reusable for offline analysis

---

## 8. Analyzers: Pattern-Based Diagnosis

Analyzers consume artifacts and generate **Findings**.

### Key Design Principle

> Analyzers do not understand business logic.
> They understand **performance patterns**.

Examples:

* High call count of small functions
* CPU-bound vs IO-bound behavior
* Excessive memory growth
* Hot call paths dominating runtime
* Abnormal variance across runs

### Finding Structure

```python
Finding = {
    "id": "high_call_count_small_fn",
    "location": "file.py:function:line",
    "evidence": {
        "call_count": 1_200_000,
        "avg_time_us": 1.2,
        "total_time_s": 1.44
    },
    "confidence": 0.82,
    "pattern_id": "high_call_count_small_fn",
    "suggestions": [...]
}
```

All findings must:

* Be backed by quantitative evidence
* Be explainable without code context
* Be reproducible

---

## 9. Performance Pattern Knowledge Base

Performance knowledge is encoded as **explicit patterns**, not hardcoded logic.

Patterns are stored in a declarative format (e.g. YAML):

```yaml
- id: high_call_count_small_fn
  description: >
    Excessive invocation of very small functions causes
    interpreter dispatch overhead.
  condition:
    call_count: "> 1e6"
    avg_time_us: "< 2"
  suggestions:
    - Inline function logic
    - Batch operations
```

This enables:

* Explainability
* Extensibility
* LLM-friendly reasoning

---

## 10. LLM Integration Philosophy

LLMs (Codex / GPT) are used for **explanation and synthesis**, NOT raw inference.

LLMs are provided with:

* Structured Findings
* Performance patterns
* Selected code snippets (optional)
* Explicit instructions to:

  * cite evidence
  * avoid speculation
  * state uncertainty

LLMs must NOT:

* Guess missing data
* Claim guaranteed optimizations
* Modify code unless explicitly enabled

---

## 11. Output and Reports

Primary output formats:

* `report.md` (human-readable)
* `findings.json` (machine-readable)
* raw profiling artifacts (for reproducibility)

Reports must include:

* Summary of observed behavior
* Key bottlenecks
* Evidence-backed explanations
* Suggested actions
* How to verify improvements

---

## 12. Design Constraints (For Codex)

When generating or modifying code, **always respect**:

* Modular architecture
* Explicit data schemas
* No hidden global state
* No assumptions about target code
* Prefer clarity over cleverness
* Profiling correctness > micro-optimizations

---

## 13. Expected Evolution

Planned future extensions:

* Multi-run regression detection
* Diff-based performance comparison
* Memory profiling (tracemalloc / memray)
* Cross-language support via eBPF
* Visualization (HTML / flamegraph embedding)

---

## 14. Guiding Philosophy

> AutoProfiler is not an optimizer.
> It is an **automated performance analyst**.

The system exists to:

* Reduce human effort
* Increase diagnostic accuracy
* Improve explainability
* Enable reproducible performance engineering

---

## 15. Minimal Reference Implementation (for contributors)

The repository includes a lightweight Python package scaffold (`autoprofiler/`) that follows the rules above:

* `autoprofiler.models` defines the immutable schemas (`TargetProgram`, `ProfileArtifact`, `Finding`, etc.).
* `autoprofiler.runner.Runner` launches opaque commands, captures stdout/stderr, and invokes collectors without modifying the target program.
* `autoprofiler.collectors.PsutilCollector` observes CPU and memory usage for an existing PID using periodic sampling (no instrumentation).
* `autoprofiler.patterns.loader` reads declarative YAML pattern definitions (see `autoprofiler/patterns/performance.yaml`).
* `autoprofiler.analyzers.PatternMatchingAnalyzer` deterministically matches collector metrics against pattern thresholds to emit structured findings.
* `autoprofiler.reporting.reporter` renders `report.md`-style text and `findings.json` payloads from a profiling session.

### Quickstart

```python
from pathlib import Path

from autoprofiler.runner import Runner
from autoprofiler.models import TargetProgram
from autoprofiler.collectors.psutil_collector import PsutilCollector
from autoprofiler.patterns.loader import load_patterns
from autoprofiler.analyzers.simple_analyzer import PatternMatchingAnalyzer
from autoprofiler.reporting.reporter import render_findings_json, render_markdown


target = TargetProgram(command=["python", "-c", "print('hello')"], timeout=5)
collector = PsutilCollector(sample_interval=0.25)
session = Runner().run(target, collectors=[collector])

patterns = load_patterns(Path("autoprofiler/patterns/performance.yaml"))
analyzer = PatternMatchingAnalyzer(patterns)
session.findings = analyzer.analyze(session.artifacts)

print(render_markdown(session))
print(render_findings_json(session))
```

For a deeper CPU view, you can wrap the target with `CProfileCollector` and also
add `PySpyCollector` (requires the `py-spy` binary in `PATH`) to capture sampling
data without code changes.

This quickstart keeps the **black-box profiling** philosophy intact: it launches the target command, observes metrics externally, matches them against declarative patterns, and produces reproducible reports.

Key implications:

* The profiler **launches and observes**, but does not interfere.
* The program may be:

  * a script
  * a module (`python -m xxx`)
  * a test suite
  * a service (short-lived or long-running)
* The profiler must work **without knowing program internals**.

### Demo workload

Run `python -m autoprofiler.demo_profile` to see psutil sampling combined with
`CProfileCollector` on a CPU-heavy workload that runs for a few seconds. The
demo loads patterns from `autoprofiler/patterns/performance.yaml` and prints the
resulting markdown and JSON findings so you can validate the pipeline end to
end.

---
