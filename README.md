# AutoProfiler

AutoProfiler is a local performance analysis tool with a Web UI and HTTP APIs.

It supports:

- Single-file analysis.
- Project-level analysis (`proj-analyser`) for medium/large repositories.
- AI-assisted reporting (remote API or local OpenAI-compatible model).

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
python -m venv .venv
python tools/bootstrap.py
source .venv/bin/activate
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
  "file_path": "E:/repo/src/service/handler.ts",
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
  "project_path": "E:/MY_WORK/CS/etrip-profiling/autoprofiler",
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

- `.autoprofiler_proj_analyser/report_project_api.md`
- `.autoprofiler_proj_analyser/report_project_api.html`
- `.autoprofiler_proj_analyser/api_dialogue.json`
- `.autoprofiler_proj_analyser/analysis_context.json`
- `.autoprofiler_proj_analyser/focus_plan.json`

Mirrored review copies:

- `docs/generated/project/report_project_api.md`
- `docs/generated/project/report_project_api.html`
- `docs/generated/project/report_project_context.json`
- `docs/generated/project/report_project_focus.json`

Single-file outputs are returned in API result payload (`markdown`, `html`, optional `pdf_path`).

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
