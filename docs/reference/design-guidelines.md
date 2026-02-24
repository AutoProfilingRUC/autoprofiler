# AutoProfiler Design Guidelines

## Scope

AutoProfiler focuses on performance diagnosis with reproducible evidence. It does not guarantee automatic optimization.

## Pipeline

Use the pipeline `Runner -> Collectors -> Analyzers -> Reporter`.

- Runner launches target commands and captures execution metadata.
- Collectors gather metrics without modifying target business code.
- Analyzers produce structured findings from explicit rules/patterns.
- Reporter renders markdown/json/html outputs from structured findings.

## Project-level analysis (`proj-analyser`)

- `proj-analyser` is for medium/large repositories where single-file analysis is insufficient.
- Prefer incremental API dialogue with strict JSON actions:
  - `need_files`
  - `final_report`
- Keep token usage bounded via focus planning and range-based file reads.
- If API/local model config is unavailable, fallback to local rule-based report.

## Data and output conventions

- Persist project-level outputs in `.autoprofiler_proj_analyser/`.
- Mirror review copies into `docs/generated/project/`.
- Treat `docs/generated/` as runtime outputs, not source documentation.
- Keep user secrets and machine-local config out of git.

## Reliability requirements

- Every finding should include evidence (file/path/metric).
- On model failures, produce a deterministic fallback report instead of empty output.
- Keep API errors observable in output status and logs.

## Environment capability gating

- Detect runtime capabilities before using optional features (`/api/system/capabilities`).
- Prefer graceful downgrade over hard failure (e.g., PDF export disabled when dependencies are missing).
- Avoid platform-specific command hardcoding for runtime execution (`sys.executable`).
