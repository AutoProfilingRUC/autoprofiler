# proj-analyser Reference

## Purpose

`proj-analyser` extends AutoProfiler from single-file analysis to repository-level performance diagnosis.

## API endpoints

Start analysis:

```http
POST /api/proj-analyser/analyze
Content-Type: application/json

{
  "project_path": "E:/MY_WORK/CS/etrip-profiling/autoprofiler",
  "query": ["performance", "api", "bottleneck"],
  "output_language": "zh",
  "top_files": 12,
  "token_budget": 12000,
  "max_rounds": 6,
  "max_file_chars": 4000
}
```

Poll result:

```http
GET /api/proj-analyser/analysis/<analysis_id>
```

## Output paths

Primary outputs:

- `.autoprofiler_proj_analyser/report_project_api.md`
- `.autoprofiler_proj_analyser/report_project_api.html`
- `.autoprofiler_proj_analyser/api_dialogue.json`
- `.autoprofiler_proj_analyser/analysis_context.json`
- `.autoprofiler_proj_analyser/focus_plan.json`

`api_dialogue.json` includes:

- per-round model actions and provided files (`logs`)
- token usage aggregate (`token_usage_summary`)
- token usage per round (`token_usage_rounds`)

Mirrored docs outputs:

- `docs/generated/project/report_project_api.md`
- `docs/generated/project/report_project_api.html`
- `docs/generated/project/report_project_context.json`
- `docs/generated/project/report_project_focus.json`

## Runtime model selection

Model resolution priority:

1. Local OpenAI-compatible model (`use_local_model=true` and local fields complete).
2. Remote API (`api_key`, `api_url`, `model` complete).
3. Local fallback mode if neither is configured.

Language control:

- `output_language`: `zh` or `en`.
- The value is applied to API system/user prompts and expected report language.

## API input context (what the model receives)

The first turn includes a structured repository snapshot, not raw full-repo code:

- `summary` (files scanned, entrypoints, total size)
- `top_level_overview` (top-level path/file-size distribution)
- `directories_top` (hot directories by file count/size)
- `language_distribution`
- `entrypoints_primary` (preferred runtime entrypoints after low-signal filtering)
- `entrypoints_top`
- `entrypoints_low_signal_count` (tests/demos/examples-style candidates count)
- `focus_plan.selected_files` (budgeted candidate files)
- `focus_plan.selected_plus_agent_tokens_estimate` (selected files + prompt/context overhead estimate)

Source code is then provided incrementally by `need_files` requests (path + line ranges).

## Frontend flow

1. Choose mode: single-file or whole-project.
2. Input absolute path.
3. In project mode, if no model is configured:
   - prompt for API key and save, or
   - skip and continue with local fallback analysis.
