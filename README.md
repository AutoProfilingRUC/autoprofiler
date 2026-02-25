# AutoProfiler

AutoProfiler is a local performance analysis tool with a Web UI and HTTP APIs.

It supports:

- Single-file analysis.
- Project-level analysis (`proj-analyser`) for medium/large repositories.
- AI-assisted reporting (remote API or local OpenAI-compatible model).

## Project Architecture

Core modules:

- `web.py`: Flask app entrypoint and route registration.
- `api/`: HTTP handlers for single-file analysis, project analysis, model config, and system capability checks.
- `analysis/`: Single-file pipeline (runtime collectors, static analyzer, AI merge/report composition).
- `proj_analyser/`: Project scanner, repository context builder, focus planning, iterative API dialogue.
- `utils/`: Markdown/HTML conversion, environment capability detection, shared helpers.
- `templates/` + `static/` + `gui/`: Frontend pages and interaction logic.
- `uploads/`: Runtime user config and temporary artifacts (git-ignored for secrets/state).

Execution model:

- Single-file mode:
  1. API receives absolute file path.
  2. Python files run runtime collectors (`cProfile`, optional `psutil`) plus static analysis.
  3. Non-Python files use static multi-language analysis.
  4. If model config exists, AI analysis is added; otherwise local whitebox result is returned.
- Project mode (`proj-analyser`):
  1. Scanner builds repository structure summary and candidate entrypoints.
  2. Focus planner chooses high-priority files/ranges under token budget.
  3. API dialogue runs incrementally (`need_files` -> `final_report`) to avoid dumping whole repo in one request.
  4. Final report is assembled with whitebox as primary baseline and blackbox as supporting signal.

Data and artifacts:

- Analysis tasks are async and queried by `analysis_id` via polling APIs.
- Project reports are written under `uploads/runtime_artifacts/project_reports/<project_key>/` and mirrored to `docs/generated/project/`.
- Single-file results are returned directly in response payload (`markdown`, `html`, optional `pdf_path`).

`docs/` is the source of truth for maintained docs:

- `docs/README.md`
- `docs/reference/`
- `docs/changelog.md`
- `docs/archive/`

## What It Can Analyze

Single-file mode has two execution paths:

1. Python runtime profiling (`.py`, `.pyw`).
2. Static multi-language analysis (other supported source extensions).

Project mode (`proj-analyser`) scans repository structure, builds a focus plan, and runs incremental API dialogue (`need_files` / `final_report`) to keep token usage bounded.

## Supported Single-File Extensions

`.py .pyw .js .jsx .ts .tsx .java .kt .go .rs .c .h .cpp .cc .hpp .cs .php .rb .swift .scala .sql .yml .yaml .toml .json .md`

Note:

- Runtime profiling is available only for Python files.
- Other languages use static structure/performance-signal analysis.

## Quick Start

### 1) Setup environment

Windows:

```powershell
python -m venv .venv
python tools/bootstrap.py
.\.venv\Scripts\activate
```

Linux/macOS:

```bash
python3 -m venv .venv
python3 tools/bootstrap.py
source .venv/bin/activate
```

Linux note (recommended before bootstrap, Debian/Ubuntu):

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip libcairo2 libpango-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info
```

### 2) Start Web server

```bash
python web.py
```

Default URL:

- `http://127.0.0.1:5000`

## Model Configuration

Config endpoint:

- `GET /api/deepseek/config`
- `POST /api/deepseek/config`
- `POST /api/deepseek/test`
- `POST /api/deepseek/clear`

Runtime config file:

- `uploads/deepseek_config.json` (local runtime file, git-ignored)
- `uploads/deepseek_config.example.json` (tracked template)

Important fields:

- `api_key`, `api_url`, `model`
- `use_local_model`, `local_api_url`, `local_model`, `local_api_key`
- `output_language`: `zh` or `en`
- `enable_blackbox`, `enable_whitebox`

Notes:

- `GET /api/deepseek/config` returns masked key fields (`api_key_masked`) and configuration flags (`api_key_configured`), not raw secrets.
- When saving config, leaving `api_key`/`local_api_key` empty keeps existing stored values.

## Runtime Capability Auto-Detection

AutoProfiler now checks host capabilities and enables/degrades features automatically:

- Python runtime execution uses `sys.executable` (no hard-coded `python` binary).
- If `psutil` is unavailable, runtime profiling skips psutil sampling and still tries cProfile.
- PDF export checks `markdown` + `weasyprint` + runtime libraries before conversion.
- Frontend shows system capability summary and disables PDF download button when unsupported.

Capability endpoint:

- `GET /api/system/capabilities`
- Optional refresh: `GET /api/system/capabilities?refresh=1`

## Web Workflow

1. Open the UI.
2. Choose `single file` or `project`.
3. Input an absolute path.
4. Configure model (optional).
5. Start analysis.

Behavior:

- If model config is missing, project mode can continue with local fallback analysis.
- AI output language follows `output_language`.

## HTTP API

### Single-file analysis

Start:

```http
POST /api/analyze-file-path
Content-Type: application/json

{
  "file_path": "/abs/path/to/repo/src/service/handler.ts",
  "output_language": "en"
}
```

Poll:

```http
GET /api/analysis/<analysis_id>
```

### Project analysis (`proj-analyser`)

Start:

```http
POST /api/proj-analyser/analyze
Content-Type: application/json

{
  "project_path": "/abs/path/to/repo",
  "query": ["performance", "api", "bottleneck"],
  "output_language": "zh",
  "top_files": 12,
  "token_budget": 12000,
  "max_rounds": 6,
  "max_file_chars": 4000
}
```

Poll:

```http
GET /api/proj-analyser/analysis/<analysis_id>
```

Project mode context sent to model includes repository summary, directory distribution, entrypoint candidates, and focus plan. Source code is sent incrementally by file/range requests.

## Output Artifacts

Project outputs:

- `uploads/runtime_artifacts/project_reports/<project_key>/report_project_api.md`
- `uploads/runtime_artifacts/project_reports/<project_key>/report_project_api.html`
- `uploads/runtime_artifacts/project_reports/<project_key>/api_dialogue.json`
- `uploads/runtime_artifacts/project_reports/<project_key>/analysis_context.json`
- `uploads/runtime_artifacts/project_reports/<project_key>/focus_plan.json`

`api_dialogue.json` includes per-round and aggregated API token usage (`token_usage_rounds`, `token_usage_summary`), and the report appends an `API Token Usage` section in API mode.

Mirrored review copies:

- `docs/generated/project/report_project_api.md`
- `docs/generated/project/report_project_api.html`
- `docs/generated/project/report_project_context.json`
- `docs/generated/project/report_project_focus.json`

Single-file outputs are returned in API result payload (`markdown`, `html`, optional `pdf_path`).
Runtime profiler artifacts (`cProfile .pstats`) are written to `uploads/runtime_artifacts/cprofile/`.

## Testing

Run focused tests:

```bash
python -m unittest tests.test_code_analyzer_multilang
python -m unittest tests.test_single_file_multilang_task
python -m unittest tests.test_proj_analyser_scanner
python -m unittest tests.test_proj_analyser_prompt_language
```

Run all tests:

```bash
python -m unittest discover tests
```

## Troubleshooting

`PDF export unavailable`:

- Ensure dependencies are installed from `requirements.txt`.
- On Windows, install GTK runtime for WeasyPrint.

`Model calls fail`:

- Verify API key and endpoint.
- For local model, ensure OpenAI-compatible endpoint is reachable.

`Project report is fallback-only`:

- This means no usable model config was found or API call failed.
- Check `/api/deepseek/test` and runtime config fields.

`bootstrap.py` fails at `pip install -U pip` on Linux:

- This usually means venv/pip/runtime deps are incomplete, or network/proxy blocks pip.
- Re-run with Python 3 and check prerequisites:
  - `python3 -m venv .venv`
  - `python3 tools/bootstrap.py`
- If needed, run manual recovery:
  - `.venv/bin/python -m ensurepip --upgrade`
  - `.venv/bin/python -m pip install -U pip`
  - `.venv/bin/python -m pip install -r requirements.txt`
