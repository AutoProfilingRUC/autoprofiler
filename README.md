# AutoProfiler (Python-based Automatic Profiling Tool)

## 1. Project Overview

AutoProfiler is an **automatic performance profiling and diagnosis tool** implemented in **Python**.

The core goal of this project is:

> Given an **unknown target program** (usually Python, but not limited by project structure),
> automatically collect performance data, analyze performance patterns,
> and generate **evidence-based performance diagnostics and optimization suggestions**.

This project **does NOT assume**:

- prior knowledge of the target program  
- access to or modification of the target program’s source code  
- specific frameworks, coding styles, or workloads  

AutoProfiler is designed as a **black-box / semi-black-box profiler**, similar in philosophy to tools like `perf`, `py-spy`, or `valgrind`, but specialized for **Python ecosystems** and **AI-assisted explanation**.

---

## 2. Non-Goals (Very Important)

To avoid ambiguity, AutoProfiler explicitly does **NOT** aim to:

- ❌ Fully understand business logic of the target program  
- ❌ Automatically rewrite or refactor code by default  
- ❌ Guarantee performance improvement after suggestions  
- ❌ Depend on decorators, instrumentation, or source modification  
- ❌ Be a full IDE or debugger  

Instead, the project focuses on a pipeline of **profiling facts → diagnosis → verifiable guidance**.

---

## 3. High-Level Architecture

AutoProfiler follows a **three-stage pipeline**:

```text
[ Runner ]
    ↓
[ Collectors ]  → raw profiling artifacts
    ↓
[ Analyzers ]   → structured findings (pattern-based)
    ↓
[ Reporter ]    → human-readable diagnosis & suggestions
```

Each stage is **strictly decoupled** and communicates through well-defined data structures.

---

## 4. Target Program Model (Critical Assumption)

The target program is treated as an **opaque executable command**:

```text
TargetProgram = {
    command: ["python", "main.py", "--arg1", "value"],
    cwd: "/path/to/workdir",
    env: { ... },
    timeout: optional
}
```

Key implications:

* The profiler **launches and observes**, but does not interfere.
* The program may be:

  * a script
  * a module (`python -m xxx`)
  * a test suite
  * a service (short-lived or long-running)
* The profiler must work **without knowing program internals**.

---

## 5. Installation & Environment Setup

### Requirements

* Python ≥ 3.10
* Linux / WSL recommended (for `py-spy` and future eBPF-based features)

### Option A: One-step bootstrap (recommended)

```bash
python -m venv .venv
python3 tools/bootstrap.py
source .venv/bin/activate
```

This will:

* Create a virtual environment
* Install all dependencies from `requirements.txt`

### Option B: Manual setup

Create an isolated environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Install runtime dependencies:

Core runtime libraries:

* [`psutil`](https://pypi.org/project/psutil/) — used by `PsutilCollector` for CPU and memory sampling
* [`PyYAML`](https://pypi.org/project/PyYAML/) — used to load declarative performance patterns

```bash
python -m pip install psutil pyyaml
```

Optional / future collectors may require additional dependencies (e.g. `py-spy`). Check the corresponding collector module docstring for details.

Web UI dependencies (if you run `web_app.py`):

* [`Flask`](https://pypi.org/project/Flask/)
* [`flask-cors`](https://pypi.org/project/flask-cors/)

To validate the installation, run a lightweight import and bytecode compilation check:

```bash
python -m compileall autoprofiler
```

---

## 6. Minimal Reference Implementation (for contributors)

The repository includes a lightweight Python package scaffold (`autoprofiler/`) that follows the design rules above:

* `autoprofiler.models` defines the immutable schemas (`TargetProgram`, `ProfileArtifact`, `Finding`, etc.)
* `autoprofiler.runner.Runner` launches opaque commands, captures stdout/stderr, and invokes collectors without modifying the target program
* `autoprofiler.collectors.psutil_collector.PsutilCollector` observes CPU and memory usage for an existing PID using periodic sampling (no instrumentation)
* `autoprofiler.patterns.loader` reads declarative YAML pattern definitions (see `autoprofiler/patterns/performance.yaml`)
* `autoprofiler.analyzers.simple_analyzer.PatternMatchingAnalyzer` deterministically matches collector metrics against pattern thresholds to emit structured findings
* `autoprofiler.reporting.reporter` renders `report.md`-style text and `findings.json` payloads from a profiling session

### Python quickstart

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

# Run the target and collect artifacts
session = Runner().run(target, collectors=[collector])

# Load performance patterns and run analysis
patterns = load_patterns(Path("autoprofiler/patterns/performance.yaml"))
analyzer = PatternMatchingAnalyzer(patterns)
session.findings = analyzer.analyze(session.artifacts)

# Render human-readable and machine-readable reports
print(render_markdown(session))
print(render_findings_json(session))
```

This quickstart keeps the **black-box profiling** philosophy intact: it launches the target command, observes metrics externally, matches them against declarative patterns, and produces reproducible reports.

### Demo workload

For a simple CPU-heavy demo workload that exercises the pipeline end-to-end:

```bash
python -m autoprofiler.demo_profile
```

This combines psutil sampling with a cProfile-based collector (if available), loads patterns from `autoprofiler/patterns/performance.yaml`, and prints both markdown and JSON findings.

### Run AutoProfiler via the template test

You can also launch the profiling pipeline directly from the terminal using the template test in `tests/test_autoprofiler_template.py`.

Run the default inline program:

```bash
python -m unittest tests.test_autoprofiler_template
```

Point the profiler at your own program (any executable command works):

```bash
AUTOPROFILER_TARGET="python my_script.py --flag" \
  python -m unittest tests.test_autoprofiler_template
```

---

## 7. CLI-first process profiling (Linux MVP)

AutoProfiler now supports profiling **arbitrary Linux executables** and attaching to
**running processes** from the command line. Existing Python collectors (cProfile/py-spy)
are still available and can be requested explicitly.

### Run mode

```bash
# Run an executable and profile until it exits
python -m autoprofiler run -- ./my_binary --flag value

# Profile for a fixed window (in seconds)
python -m autoprofiler run --duration 10 -- ./my_binary --flag value

# Set working directory + environment variables for the target process
python -m autoprofiler run --cwd /tmp --env FOO=bar --env PATH=/opt/bin:$PATH -- ./my_binary
```

### Attach mode

```bash
# Attach to a running PID for 30s (default)
python -m autoprofiler attach --pid 12345

# Attach to process name (collects all matching PIDs)
python -m autoprofiler attach --name myservice --duration 20

# Include the entire process tree (child processes) in aggregation
python -m autoprofiler attach --pid 12345 --include-children --duration 20
```

### Collector selection

```bash
# Choose collectors explicitly
python -m autoprofiler run --collect psutil,perf -- ./my_binary
python -m autoprofiler run --collect psutil,pyspy -- python my_script.py
```

Defaults:

* Linux: `psutil + perf` (perf is best-effort; it disables itself when unavailable)
* Other platforms: `psutil` only

### Output artifacts

Every CLI run produces:

* `profile_report.json` (machine-readable, JSON)
* terminal summary (human-readable)
* optional artifacts (e.g., `perf_*.data`, `pyspy_*.svg`)

Example JSON snippet:

```json
{
  "schema_version": "1.0",
  "metadata": {
    "mode": "run",
    "command": ["./my_binary", "--flag", "value"],
    "pids": [4242],
    "platform": "linux"
  },
  "timeseries": [
    {"t": 0.0, "cpu_percent": 12.5, "rss_bytes": 10485760.0}
  ],
  "summary": {
    "cpu_percent": {"min": 8.0, "max": 110.0, "p50": 45.0, "p95": 98.0}
  },
  "diagnosis": [
    {"label": "cpu_bound", "confidence": 0.7, "evidence": {"cpu_avg": 91.2}}
  ],
  "warnings": []
}
```

### Perf permissions (Linux)

`perf` may require relaxed kernel settings or elevated privileges. Common fixes:

```bash
sudo sysctl -w kernel.perf_event_paranoid=1
sudo sysctl -w kernel.kptr_restrict=0
```

If you see `perf` permission errors, AutoProfiler will continue and emit a warning in
`profile_report.json` with troubleshooting hints.

### Windows notes (design-ready, partial support)

* `--cwd` and `--env` work for running Windows executables.
* `psutil` data collection works best-effort on Windows.
* ETW profiling is **not** implemented in the MVP; see `EtwCollector` placeholder.

The template test prints the generated markdown report to stdout so you can quickly inspect findings without wiring up additional code.

---

## 7. Runner Responsibilities

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

## 8. Collectors: Data Acquisition Layer

Collectors are **pluggable, independent modules** that observe the running process.

Each collector:

* Attaches to the target PID (or wraps execution)
* Produces a `ProfileArtifact`
* Must be safe for unknown programs

### Available collectors

* **PsutilCollector** (implemented)

  * System-level metrics: CPU usage, RSS memory, I/O activity, thread count
  * Periodic sampling without instrumentation

* **CProfileCollector** (implemented)

  * Uses `python -m cProfile`
  * Collects call counts and cumulative time
  * Wraps the target command via `prepare_command()` method
  * Produces `.pstats` files for detailed analysis

* **PySpyCollector** (implemented)

  * Sampling-based CPU profiler
  * Low overhead, no source modification
  * Gracefully degrades with a warning when the `py-spy` binary is unavailable
  * Can generate flamegraph outputs

Collectors should **never interpret results** — only collect and serialize.

---

## 9. Artifacts and Data Format

All collectors output standardized artifacts.

```python
ProfileArtifact = {
    "collector": "py-spy",
    "type": "cpu-sampling",
    "timestamp": "...",
    "raw_files": [...],
    "metrics": {...},
}
```

Artifacts must be:

* Serializable (JSON-compatible)
* Persisted to disk
* Reusable for offline analysis

---

## 10. Analyzers: Pattern-Based Diagnosis

Analyzers consume artifacts and generate **Findings**.

### Key design principle

> Analyzers do not understand business logic.
> They understand **performance patterns**.

Examples:

* High call count of small functions
* CPU-bound vs IO-bound behavior
* Excessive memory growth
* Hot call paths dominating runtime
* Abnormal variance across runs

### Finding structure

```python
Finding = {
    "id": "high_call_count_small_fn",
    "location": "file.py:function:line",
    "evidence": {
        "call_count": 1_200_000,
        "avg_time_us": 1.2,
        "total_time_s": 1.44,
    },
    "confidence": 0.82,
    "pattern_id": "high_call_count_small_fn",
    "suggestions": [...],
}
```

All findings must:

* Be backed by quantitative evidence
* Be explainable without code context
* Be reproducible

See the next section for the canonical pattern list.

---

## 11. LLM Integration Philosophy

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
* Replace analyzers or pattern logic

---

## 12. Performance Pattern Knowledge Base

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

### Available performance patterns

Patterns are organized by category (see `autoprofiler/patterns/performance.yaml`):

#### CPU-related patterns

* `high_cpu_usage`: Sustained high CPU consumption (> 75%)
* `low_cpu_high_io`: Low CPU usage suggesting IO-bound workload (< 20%)
* `cpu_variance_high`: High CPU variance indicating inconsistent workload

#### Function call patterns (cProfile-based)

* `high_call_count_small_fn`: Excessive small function invocations (> 1M calls, < 5s total)
* `single_function_dominates`: One function consumes > 50% of execution time
* `high_calls_low_time`: Many calls but low total time (overhead-dominated)

#### Memory patterns

* `memory_growth_risk`: RSS memory exceeds threshold (> 500MB)
* `vms_rss_ratio_high`: High virtual-to-physical memory ratio (> 4.0, suggests fragmentation)
* `memory_growth_trend`: Upward memory trend during execution (potential leak)

#### Execution time patterns

* `long_execution_time`: Execution exceeds expected duration (> 10s)

#### Hot function patterns

* `top_functions_concentration`: Top functions consume > 70% of time
* `hot_function_high_call_count`: Hot function has unusually high call count (> 100K)

#### Sampling patterns

* `insufficient_sampling`: Too few samples collected (< 5 samples)

#### Combined patterns (multi-artifact)

* `cpu_intensive_few_calls`: High CPU (> 70%) with few calls (< 10K) — suggests tight loops
* `memory_intensive_low_cpu`: High memory (> 1GB) with low CPU (< 30%) — suggests data-heavy processing

Patterns can be extended without modifying code.

---

## 13. Output and Reports

Primary output formats:

* `report.md` (human-readable)
* `findings.json` (machine-readable)
* raw profiling artifacts (for reproducibility)

Reports include:

* Summary of observed behavior
* Key bottlenecks
* Evidence-backed explanations
* Suggested actions
* How to verify improvements

---

## 14. Design Constraints (for code generation tools)

When generating or modifying code (via AI or templates), always respect:

* Modular architecture
* Explicit data schemas
* No hidden global state
* No assumptions about target code
* Prefer clarity over cleverness
* Profiling correctness > micro-optimizations

---

## 15. Expected Evolution & Open Tasks

Planned future extensions (high-level):

* Multi-run regression detection and trend analysis
* Diff-based performance comparison between runs or branches
* Enhanced memory profiling (e.g. `tracemalloc`, `memray`)
* Cross-language support via eBPF and system-level collectors
* Visualization (HTML views, flamegraph embedding)

Concrete open tasks for contributors:

* Extend `ProfileArtifact` schemas for richer metadata (e.g. per-thread stats)
* Add more declarative patterns (cache behavior, GC activity, I/O patterns)
* Build a simple CLI front-end (`autoprofiler` entry point) for running profiles without Python code changes
* Add multi-run storage and comparison API
* Create sample "bad" workloads with known bottlenecks for regression testing
* Enhance LLM integration for more sophisticated report generation

---

## 16. Testing

The project includes several test files in the `tests/` directory:

* `test_autoprofiler_template.py` - Basic template test for profiling any target program
* `test_new_patterns.py` - Tests for new performance pattern detection
* `test_extended.py` - Extended tests with longer-running workloads
* `test_complete_demo.py` - Complete demonstration of all features

Run tests using:

```bash
# Run all tests
python -m unittest discover tests

# Run specific test
python -m unittest tests.test_autoprofiler_template

# Run demo scripts directly
python tests/test_extended.py
```

---

## 17. Guiding Philosophy

> AutoProfiler is not an optimizer.
> It is an **automated performance analyst**.

The system exists to:

* Reduce human effort
* Increase diagnostic accuracy
* Improve explainability
* Enable reproducible performance engineering
