# AutoProfiler

AutoProfiler 是一个本地性能分析工具，提供 Web 界面和 HTTP API。

当前支持：

- 单文件分析。
- 中大型仓库的项目级分析（`proj-analyser`）。
- AI 增强报告（远程 API 或本地 OpenAI 兼容模型）。

## 项目整体框架

核心模块：

- `web.py`：Flask 应用入口与路由注册。
- `api/`：单文件分析、项目分析、模型配置、系统能力查询等 HTTP 接口。
- `analysis/`：单文件分析主流程（运行时采集、静态分析、AI 合并与报告组装）。
- `proj_analyser/`：项目扫描、仓库上下文构建、focus 计划、增量 API 对话。
- `utils/`：Markdown/HTML 转换、运行环境能力探测、通用工具函数。
- `templates/` + `static/` + `gui/`：前端页面与交互逻辑。
- `uploads/`：运行期配置和临时产物（默认 git ignore，避免提交密钥与状态文件）。

执行链路：

- 单文件模式：
  1. 接口接收绝对文件路径。
  2. Python 文件执行运行时采集（`cProfile`、可选 `psutil`）并结合静态分析。
  3. 非 Python 文件执行静态多语言分析。
  4. 若模型配置可用，追加 AI 结果；否则返回本地白盒分析结果。
- 项目模式（`proj-analyser`）：
  1. 扫描仓库结构并生成入口候选。
  2. 依据 token 预算生成重点文件/片段计划。
  3. 按 `need_files -> final_report` 协议增量调用 API，避免一次性发送全仓库。
  4. 生成报告时采用“白盒为主、黑盒为辅”的融合策略。

数据与产物：

- 分析任务异步执行，通过 `analysis_id` 轮询结果。
- 项目分析产物写入 `uploads/runtime_artifacts/project_reports/<project_key>/`，并镜像到 `docs/generated/project/`。
- 单文件结果通过接口直接返回（`markdown`、`html`、可选 `pdf_path`）。

`docs/` 是维护中的文档入口：

- `docs/README.md`
- `docs/reference/`
- `docs/changelog.md`
- `docs/archive/`

## 能分析什么

单文件模式有两条执行路径：

1. Python 运行时性能分析（`.py`、`.pyw`）。
2. 其他语言走静态多语言分析（结构 + 性能信号）。

项目模式（`proj-analyser`）会先扫描仓库结构、构建重点文件计划，再通过增量对话协议（`need_files` / `final_report`）进行分析，以控制 token 开销。

## 单文件支持后缀

`.py .pyw .js .jsx .ts .tsx .java .kt .go .rs .c .h .cpp .cc .hpp .cs .php .rb .swift .scala .sql .yml .yaml .toml .json .md`

说明：

- 只有 Python 文件支持运行时采样分析。
- 其他语言为静态结构/性能信号分析。

## 快速开始

### 1) 初始化环境

Windows：

```powershell
python -m venv .venv
python tools/bootstrap.py
.\.venv\Scripts\activate
```

Linux/macOS：

```bash
python3 -m venv .venv
python3 tools/bootstrap.py
source .venv/bin/activate
```

Linux 依赖建议（Debian/Ubuntu，先执行）：

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip libcairo2 libpango-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info
```

### 2) 启动 Web 服务

```bash
python web.py
```

默认访问地址：

- `http://127.0.0.1:5000`

## 模型配置

相关接口：

- `GET /api/deepseek/config`
- `POST /api/deepseek/config`
- `POST /api/deepseek/test`
- `POST /api/deepseek/clear`

运行时配置文件：

- `uploads/deepseek_config.json`（本地运行文件，默认忽略）
- `uploads/deepseek_config.example.json`（仓库模板）

核心字段：

- `api_key`, `api_url`, `model`
- `use_local_model`, `local_api_url`, `local_model`, `local_api_key`
- `output_language`: `zh` 或 `en`
- `enable_blackbox`, `enable_whitebox`

说明：

- `GET /api/deepseek/config` 返回脱敏后的密钥信息（如 `api_key_masked`）和是否已配置标记（如 `api_key_configured`），不会返回明文密钥。
- 保存配置时若 `api_key`/`local_api_key` 留空，会保留已存密钥，不会被误清空。

## 运行环境能力自动探测

AutoProfiler 会自动探测当前系统能力，并按能力启用/降级功能：

- Python 运行时执行改为 `sys.executable`，不再硬编码 `python`。
- 若 `psutil` 不可用，运行时分析会跳过 psutil 采样，仍尝试 cProfile。
- PDF 导出前会检查 `markdown`、`weasyprint` 及运行库是否可用。
- 前端会展示系统能力摘要，PDF 不可用时自动禁用下载按钮。

能力查询接口：

- `GET /api/system/capabilities`
- 强制刷新：`GET /api/system/capabilities?refresh=1`

## Web 使用流程

1. 打开页面。
2. 选择 `单文件` 或 `整项目`。
3. 输入绝对路径。
   - 支持直接粘贴带引号路径，例如 `"E:\MY_WORK\CS\etrip-profiling\autoprofiler\tests\test_extended.py"`。
4. 可选配置模型。
5. 点击开始分析。

行为说明：

- 项目模式在无模型配置时可自动降级到本地规则分析。
- AI 输出语言由 `output_language` 决定。

## HTTP API

### 单文件分析

启动：

```http
POST /api/analyze-file-path
Content-Type: application/json

{
  "file_path": "/abs/path/to/repo/src/service/handler.ts",
  "output_language": "en"
}
```

轮询：

```http
GET /api/analysis/<analysis_id>
```

### 项目分析（`proj-analyser`）

启动：

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

轮询：

```http
GET /api/proj-analyser/analysis/<analysis_id>
```

项目模式传给模型的上下文包含仓库摘要、目录分布、入口候选和 focus 计划。源码按文件/行范围增量提供，不会一次性全量发送。

## 输出产物

项目模式输出：

- `uploads/runtime_artifacts/project_reports/<project_key>/report_project_api.md`
- `uploads/runtime_artifacts/project_reports/<project_key>/report_project_api.html`
- `uploads/runtime_artifacts/project_reports/<project_key>/api_dialogue.json`
- `uploads/runtime_artifacts/project_reports/<project_key>/analysis_context.json`
- `uploads/runtime_artifacts/project_reports/<project_key>/focus_plan.json`

其中 `api_dialogue.json` 现在包含每轮及汇总 token 用量（`token_usage_rounds`、`token_usage_summary`），API 模式报告会追加“API Token 用量”章节。

文档镜像输出：

- `docs/generated/project/report_project_api.md`
- `docs/generated/project/report_project_api.html`
- `docs/generated/project/report_project_context.json`
- `docs/generated/project/report_project_focus.json`

单文件结果通过 API 返回：`markdown`、`html`、可选 `pdf_path`。
运行时分析生成的 `cProfile .pstats` 统一写入 `uploads/runtime_artifacts/cprofile/`。

## 测试

建议先跑关键测试：

```bash
python -m unittest tests.test_code_analyzer_multilang
python -m unittest tests.test_single_file_multilang_task
python -m unittest tests.test_proj_analyser_scanner
python -m unittest tests.test_proj_analyser_prompt_language
```

全量测试：

```bash
python -m unittest discover tests
```

## 常见问题

`PDF 导出不可用`：

- 先确认 `requirements.txt` 已安装完整。
- Windows 下 WeasyPrint 需要 GTK 运行时。

`模型调用失败`：

- 检查 API key 和 endpoint。
- 本地模型需保证 OpenAI 兼容接口可访问。

`项目报告只有 fallback`：

- 代表当前没有可用模型配置，或 API 调用失败。
- 先用 `/api/deepseek/test` 验证配置连通性。

`bootstrap.py` 在 Linux 执行 `pip install -U pip` 失败：

- 常见原因是 venv/pip 组件不完整，或网络/代理限制导致 pip 失败。
- 建议使用 Python 3 重新执行：
  - `python3 -m venv .venv`
  - `python3 tools/bootstrap.py`
- 必要时可手动恢复：
  - `.venv/bin/python -m ensurepip --upgrade`
  - `.venv/bin/python -m pip install -U pip`
  - `.venv/bin/python -m pip install -r requirements.txt`
