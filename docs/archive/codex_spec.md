# AutoProfiler — Codex Implementation Specification

> This document defines **strict implementation constraints** and **design intent**
> for any AI system (Codex / GPT) generating or modifying code in this repository.

Failure to follow this specification is considered **incorrect implementation**.

---

## 1. Core Objective

Implement a **Python-based automatic profiling tool** that:

* Profiles **unknown target programs**
* Requires **no source code modification** of the target
* Collects runtime performance data
* Diagnoses performance issues using **pattern-based analysis**
* Produces **evidence-backed, human-readable reports**

The system prioritizes **correctness, explainability, and reproducibility**.

---

## 2. Target Program Model (Immutable Assumption)

The profiler operates on **opaque executable commands**.

```python
TargetProgram = {
    "command": List[str],     # e.g. ["python", "main.py"]
    "cwd": Optional[str],
    "env": Optional[Dict[str, str]],
    "timeout": Optional[float]
}
```

### Hard Constraints

* ❌ Do NOT assume access to target source code
* ❌ Do NOT inject decorators or instrumentation
* ❌ Do NOT require target program imports
* ❌ Do NOT assume program structure or framework
* ✅ Treat target as black-box process(es)

---

## 3. Execution Model (Runner)

The `Runner` component MUST:

* Launch the target program via `subprocess`
* Record:

  * PID(s)
  * start / end time
  * exit status
  * stdout / stderr
* Provide lifecycle hooks for collectors

### Forbidden Behaviors

* No parsing of business output
* No logic inference from stdout
* No monkey-patching or bytecode injection

---

## 4. Collector Layer (Data Acquisition Only)

Collectors are **pure observers**.

Each collector:

* Attaches to process PID(s)
* Produces raw performance artifacts
* Does NOT perform analysis or interpretation

### Initial Required Collectors

* `CProfileCollector`
* `PySpyCollector`
* `PsutilCollector`

### Collector Output Contract

```python
ProfileArtifact = {
    "collector": str,
    "category": str,        # cpu / memory / io / system
    "timestamp": str,
    "metrics": Dict[str, Any],
    "raw_files": List[str]
}
```

---

## 5. Analyzer Layer (Pattern Recognition)

Analyzers consume artifacts and produce **Findings**.

### Analyzer Responsibilities

* Extract quantitative metrics
* Match metrics against predefined performance patterns
* Generate structured findings with evidence

### Analyzer MUST NOT

* Interpret business logic
* Modify target program
* Guess missing data

---

## 6. Finding Data Model (Mandatory)

```python
Finding = {
    "finding_id": str,
    "pattern_id": str,
    "location": Optional[str],  # file:function:line if available
    "evidence": Dict[str, Any],
    "confidence": float,        # 0.0 - 1.0
    "summary": str,
    "suggestions": List[str]
}
```

### Mandatory Properties

* Evidence must be numeric or factual
* Confidence must be justified by metrics
* Suggestions must be **general and verifiable**

---

## 7. Performance Pattern Knowledge Base

Patterns MUST be defined declaratively (e.g. YAML).

Example:

```yaml
- id: high_call_count_small_fn
  condition:
    call_count: "> 1e6"
    avg_time_us: "< 2"
  meaning: "Interpreter dispatch overhead"
  suggestions:
    - "Inline logic"
    - "Batch operations"
```

### Codex Rules

* Do NOT hardcode patterns in logic
* Always load patterns from external definitions
* Pattern matching must be deterministic

---

## 8. LLM Usage Rules (Strict)

LLMs may ONLY be used for:

* Natural language explanation of findings
* Report generation
* Summarization of evidence

LLMs MUST NOT:

* Invent performance data
* Claim guaranteed improvements
* Modify code unless explicitly enabled
* Replace analyzers or pattern logic

---

## 9. Report Generation Requirements

Generated reports MUST:

* Cite evidence explicitly
* Separate observation from interpretation
* State uncertainty when evidence is insufficient
* Provide steps to verify suggested improvements

Primary formats:

* Markdown (`report.md`)
* JSON (`findings.json`)

---

## 10. Determinism and Reproducibility

All generated code MUST:

* Produce identical results given identical inputs
* Persist raw profiling data
* Record execution environment metadata

---

## 11. Code Style and Engineering Constraints

Codex MUST:

* Use explicit, readable Python
* Avoid metaprogramming
* Avoid global mutable state
* Prefer dataclasses for schemas
* Include docstrings explaining intent

Codex MUST NOT:

* Use clever hacks
* Optimize prematurely
* Collapse modules into monoliths

---

## 12. Extension Policy

New features must:

* Respect existing abstractions
* Introduce new collectors/analyzers as plugins
* Not break existing artifact formats

---

## 13. Guiding Principle

> The profiler does not optimize code.
> It **automates performance diagnosis**.

If a behavior is ambiguous, choose:

* Explainability over aggressiveness
* Evidence over intuition
* Simplicity over completeness