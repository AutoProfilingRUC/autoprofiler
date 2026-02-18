"""
Service orchestrator for proj-analyser.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from models.deepseek_config import DeepSeekConfig
from proj_analyser.api_dialogue import run_api_dialogue
from proj_analyser.focus import build_focus_plan
from proj_analyser.scanner import scan_project
from utils.converters import convert_markdown_to_html


def _emit_progress(cb: Optional[Callable], progress: int, text: str) -> None:
    if cb:
        cb(progress, text)


def _infer_local_risks(scan_result: Dict, focus_plan: Dict, limit: int = 8) -> List[Dict]:
    risks = []
    by_path = {f.get("path"): f for f in scan_result.get("files", []) if f.get("path")}
    selected = focus_plan.get("selected_files", [])
    code_languages = {
        "python",
        "javascript",
        "typescript",
        "java",
        "kotlin",
        "go",
        "rust",
        "c",
        "cpp",
        "csharp",
        "php",
        "ruby",
        "swift",
        "scala",
    }

    for item in selected[: max(1, limit)]:
        path = item.get("path")
        file_meta = by_path.get(path, {}) or {}
        language = (file_meta.get("language") or "").lower()
        if language not in code_languages:
            continue

        src = (file_meta.get("preview_text") or "").lower()
        reasons = []
        if "for " in src and "for " in src[src.find("for ") + 1 :]:
            reasons.append("疑似嵌套循环，可能造成 CPU 开销")
        if "requests." in src or "httpx." in src:
            reasons.append("存在网络请求路径，需关注超时/重试/批量化")
        if ".read(" in src or ".write(" in src or "open(" in src:
            reasons.append("存在文件 I/O，需关注频繁小 I/O 与缓冲策略")
        if "select " in src or "execute(" in src or "cursor" in src:
            reasons.append("疑似数据库访问，需检查索引与 N+1 查询")
        if "thread" in src or "asyncio" in src or "lock" in src:
            reasons.append("并发路径，需关注锁竞争/事件循环阻塞")

        if reasons:
            risks.append(
                {
                    "path": path,
                    "priority": "P1" if len(reasons) >= 2 else "P2",
                    "signals": reasons[:3],
                }
            )
    return risks[:limit]


def _render_local_fallback_report(scan_result: Dict, focus_plan: Dict, query_terms: List[str]) -> str:
    summary = scan_result.get("summary", {})
    langs = scan_result.get("language_distribution", [])[:6]
    entrypoints_primary = scan_result.get("entrypoints_primary", [])[:8]
    entrypoints = entrypoints_primary or scan_result.get("entrypoints_top", [])[:8]
    entrypoints_low_signal_count = int(summary.get("entrypoints_low_signal_found", 0))
    selected = focus_plan.get("selected_files", [])[:12]
    risks = _infer_local_risks(scan_result, focus_plan)

    lines = []
    lines.append("# Project Performance Report (Local Fallback Mode)\n")
    lines.append("未检测到可用 API/本地模型配置，已自动降级为本地规则分析。\n")
    lines.append("## 项目摘要")
    lines.append(f"- 扫描文件数: {summary.get('files_scanned', 0)}")
    lines.append(f"- 入口候选数: {summary.get('entrypoints_found', 0)}")
    lines.append(f"- 主入口候选数: {summary.get('entrypoints_primary_found', 0)}")
    lines.append(f"- 低置信入口候选数: {entrypoints_low_signal_count}")
    lines.append(f"- 总体积(bytes): {summary.get('total_size_bytes', 0)}")
    if query_terms:
        lines.append(f"- 查询关键词: {', '.join(query_terms)}")
    lines.append("")

    lines.append("## 语言分布（Top）")
    for lang in langs:
        lines.append(
            f"- {lang.get('language', 'unknown')}: files={lang.get('files', 0)} size={lang.get('size_bytes', 0)}"
        )
    lines.append("")

    lines.append("## 重点文件（预算内）")
    for f in selected:
        lines.append(
            f"- {f.get('path')} (score={f.get('score')}, tokens~{f.get('token_estimate')})"
        )
    lines.append("")

    lines.append("## 主入口候选（Top）")
    for ep in entrypoints:
        lines.append(
            f"- {ep.get('file_path')} (score={ep.get('score')}, reason={ep.get('reason')})"
        )
    lines.append("")

    lines.append("## 本地性能风险研判（启发式）")
    if not risks:
        lines.append("- 暂未从重点文件预览中识别到明显高风险信号。")
    else:
        for r in risks:
            lines.append(f"- [{r['priority']}] {r['path']}")
            for s in r["signals"]:
                lines.append(f"  - {s}")
    lines.append("")

    lines.append("## 下一步建议")
    lines.append("- 为获取更深入的跨文件因果分析，请配置 API key 或本地模型并重新执行项目级分析。")
    lines.append("- 先对 P1 文件执行函数级 profiling（cProfile/py-spy），再验证优化收益。")
    return "\n".join(lines)


def _build_project_code_structure(scan_result: Dict, focus_plan: Dict) -> Dict:
    langs = scan_result.get("language_distribution", [])
    entrypoints = scan_result.get("entrypoints_top", [])
    entrypoints_primary = scan_result.get("entrypoints_primary", [])
    entrypoints_low_signal = scan_result.get("entrypoints_low_signal", [])
    top_levels = scan_result.get("top_level_overview", [])
    directories = scan_result.get("directories_top", [])
    selected = focus_plan.get("selected_files", [])
    summary = scan_result.get("summary", {})

    return {
        "type": "project",
        "basic_info": {
            "repo_root": scan_result.get("repo_root", ""),
            "files_scanned": summary.get("files_scanned", 0),
            "entrypoints_found": summary.get("entrypoints_found", 0),
            "total_size_bytes": summary.get("total_size_bytes", 0),
        },
        "top_level_overview": top_levels[:20],
        "directories_top": directories[:30],
        "language_distribution": langs,
        "entrypoints_primary": entrypoints_primary[:12],
        "entrypoints_low_signal": entrypoints_low_signal[:12],
        "entrypoints_top": entrypoints[:12],
        "focus_files": selected[:20],
    }


def _build_project_deepseek_results(analysis_mode: str, report_markdown: str) -> Dict:
    if analysis_mode.startswith("project_api"):
        return {"project_performance": report_markdown}
    if analysis_mode.startswith("fallback_local"):
        return {"local_fallback": report_markdown}
    return {}


def _render_project_structure_section(scan_result: Dict, focus_plan: Dict) -> str:
    summary = scan_result.get("summary", {}) or {}
    langs = scan_result.get("language_distribution", [])[:6]
    entrypoints_primary = scan_result.get("entrypoints_primary", [])[:8]
    entrypoints = entrypoints_primary or scan_result.get("entrypoints_top", [])[:8]
    top_levels = scan_result.get("top_level_overview", [])[:10]
    directories = scan_result.get("directories_top", [])[:10]
    selected = focus_plan.get("selected_files", [])[:10]

    lines = [
        "## 项目代码结构摘要",
        f"- 扫描文件数: {summary.get('files_scanned', 0)}",
        f"- 入口候选数: {summary.get('entrypoints_found', 0)}",
        f"- 主入口候选数: {summary.get('entrypoints_primary_found', 0)}",
        f"- 低置信入口候选数: {summary.get('entrypoints_low_signal_found', 0)}",
        f"- 总体积(bytes): {summary.get('total_size_bytes', 0)}",
        "",
        "### 语言分布（Top）",
    ]
    if not langs:
        lines.append("- 无可用数据")
    else:
        for item in langs:
            lines.append(
                f"- {item.get('language', 'unknown')}: files={item.get('files', 0)} size={item.get('size_bytes', 0)}"
            )

    lines.append("")
    lines.append("### 主入口候选（Top）")
    if not entrypoints:
        lines.append("- 无可用数据")
    else:
        for ep in entrypoints:
            lines.append(
                f"- {ep.get('file_path', '-')}: score={ep.get('score', 0)} reason={ep.get('reason', [])}"
            )

    lines.append("")
    lines.append("### 顶层目录结构（Top）")
    if not top_levels:
        lines.append("- 无可用数据")
    else:
        for d in top_levels:
            lines.append(
                f"- {d.get('path', '-')}: files={d.get('files', 0)} size={d.get('size_bytes', 0)}"
            )

    lines.append("")
    lines.append("### 目录热点（按文件数）")
    if not directories:
        lines.append("- 无可用数据")
    else:
        for d in directories:
            lines.append(
                f"- {d.get('path', '-')}: files={d.get('files', 0)} size={d.get('size_bytes', 0)}"
            )

    lines.append("")
    lines.append("### 重点文件（预算内）")
    if not selected:
        lines.append("- 无可用数据")
    else:
        for f in selected:
            lines.append(
                f"- {f.get('path', '-')}: score={f.get('score', 0)} tokens~{f.get('token_estimate', 0)}"
            )

    return "\n".join(lines)


def _render_ai_status_section(analysis_mode: str, runtime_mode: str, rounds: int) -> str:
    if analysis_mode.startswith("project_api"):
        status = "已启用模型分析并返回项目级报告。"
    elif analysis_mode.startswith("fallback_local_after_llm_error"):
        status = "模型调用失败，已自动降级为本地规则分析。"
    else:
        status = "未检测到可用 API/本地模型，已使用本地规则分析。"
    return "\n".join(
        [
            "## AI分析状态",
            f"- 分析模式: {analysis_mode}",
            f"- 运行模型模式: {runtime_mode}",
            f"- API对话轮次: {rounds}",
            f"- 状态说明: {status}",
        ]
    )


def _merge_report_sections(
    base_report: str,
    scan_result: Dict,
    focus_plan: Dict,
    analysis_mode: str,
    runtime_mode: str,
    rounds: int,
) -> str:
    report = (base_report or "").strip()
    if not report:
        report = "# Project Performance Report\n\n未生成有效模型报告，已输出结构化摘要。"

    parts = [report]
    if (
        analysis_mode.startswith("project_api")
        and "## 项目代码结构摘要" not in report
        and "## Project Structure Snapshot" not in report
    ):
        parts.append(_render_project_structure_section(scan_result, focus_plan))
    if "## AI分析状态" not in report and "## AI Analysis Status" not in report:
        parts.append(_render_ai_status_section(analysis_mode, runtime_mode, rounds))
    return "\n\n---\n\n".join(parts)


def analyze_project_with_api(
    project_path: str,
    deepseek_config: Dict,
    query_terms: Optional[List[str]] = None,
    top_files: int = 12,
    token_budget: int = 12000,
    bytes_per_token: int = 4,
    max_rounds: int = 6,
    max_file_chars: int = 4000,
    temperature: float = 0.1,
    max_output_tokens: int = 2200,
    progress_callback: Optional[Callable] = None,
) -> Dict:
    root = Path(project_path).resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"项目路径不存在或不是目录: {project_path}")

    terms = [t.strip() for t in (query_terms or []) if t and t.strip()]
    _emit_progress(progress_callback, 10, "正在扫描项目结构...")
    scan_result = scan_project(str(root))

    _emit_progress(progress_callback, 30, "正在构建重点文件计划...")
    focus_plan = build_focus_plan(
        scan_result=scan_result,
        query_terms=terms,
        top_files=top_files,
        token_budget=token_budget,
        bytes_per_token=bytes_per_token,
    )

    runtime = DeepSeekConfig.resolve_runtime(deepseek_config or {})
    analysis_mode = "fallback_local"
    dialogue = {"report_markdown": "", "rounds": 0, "logs": []}

    if runtime.get("enabled"):
        _emit_progress(
            progress_callback,
            55,
            f"正在进行增量项目分析（{runtime.get('mode', 'api')}）...",
        )
        analysis_mode = "project_api"
        try:
            dialogue = run_api_dialogue(
                repo_root=str(root),
                scan_result=scan_result,
                focus_plan=focus_plan,
                runtime_config=runtime,
                query_terms=terms,
                max_rounds=max_rounds,
                max_file_chars=max_file_chars,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        except Exception as llm_err:
            analysis_mode = "fallback_local_after_llm_error"
            dialogue["report_markdown"] = _render_local_fallback_report(
                scan_result=scan_result,
                focus_plan=focus_plan,
                query_terms=terms,
            )
            dialogue["report_markdown"] += (
                "\n\n---\n\n"
                f"LLM调用失败，已自动降级为本地分析：`{llm_err}`\n"
            )
    else:
        _emit_progress(progress_callback, 55, "未检测到模型配置，使用本地降级分析...")
        dialogue["report_markdown"] = _render_local_fallback_report(
            scan_result=scan_result,
            focus_plan=focus_plan,
            query_terms=terms,
        )

    _emit_progress(progress_callback, 85, "正在写入项目级分析产物...")
    out_dir = root / ".autoprofiler_proj_analyser"
    out_dir.mkdir(parents=True, exist_ok=True)

    report_markdown = _merge_report_sections(
        base_report=dialogue.get("report_markdown", ""),
        scan_result=scan_result,
        focus_plan=focus_plan,
        analysis_mode=analysis_mode,
        runtime_mode=runtime.get("mode", "none"),
        rounds=int(dialogue.get("rounds", 0)),
    )
    report_html = convert_markdown_to_html(report_markdown)

    report_path = out_dir / "report_project_api.md"
    report_html_path = out_dir / "report_project_api.html"
    session_path = out_dir / "api_dialogue.json"
    context_path = out_dir / "analysis_context.json"
    focus_path = out_dir / "focus_plan.json"

    report_path.write_text(report_markdown, encoding="utf-8")
    report_html_path.write_text(report_html, encoding="utf-8")
    session_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(),
                "rounds": dialogue.get("rounds", 0),
                "logs": dialogue.get("logs", []),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    context_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(),
                "repo_root": str(root),
                "summary": scan_result.get("summary", {}),
                "top_level_overview": scan_result.get("top_level_overview", []),
                "directories_top": scan_result.get("directories_top", []),
                "language_distribution": scan_result.get("language_distribution", []),
                "entrypoints_primary": scan_result.get("entrypoints_primary", []),
                "entrypoints_low_signal": scan_result.get("entrypoints_low_signal", []),
                "entrypoints_top": scan_result.get("entrypoints_top", []),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    focus_path.write_text(
        json.dumps(focus_plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Also mirror key outputs to docs/generated/project for easier review.
    docs_dir = root / "docs" / "generated" / "project"
    docs_dir.mkdir(parents=True, exist_ok=True)
    docs_report_path = docs_dir / "report_project_api.md"
    docs_report_html_path = docs_dir / "report_project_api.html"
    docs_context_path = docs_dir / "report_project_context.json"
    docs_focus_path = docs_dir / "report_project_focus.json"
    docs_report_path.write_text(report_markdown, encoding="utf-8")
    docs_report_html_path.write_text(report_html, encoding="utf-8")
    docs_context_path.write_text(context_path.read_text(encoding="utf-8"), encoding="utf-8")
    docs_focus_path.write_text(focus_path.read_text(encoding="utf-8"), encoding="utf-8")

    project_code_structure = _build_project_code_structure(scan_result, focus_plan)
    project_deepseek_results = _build_project_deepseek_results(analysis_mode, report_markdown)

    _emit_progress(progress_callback, 100, "项目分析完成")
    return {
        "repo_root": str(root),
        "analysis_mode": analysis_mode,
        "report_markdown": report_markdown,
        "report_html": report_html,
        "markdown": report_markdown,
        "html": report_html,
        "pdf_path": None,
        "session_info": {
            "duration": 0.0,
            "exit_code": 0,
            "findings_count": 0,
        },
        "deepseek_results": project_deepseek_results,
        "code_structure": project_code_structure,
        "outputs": {
            "output_dir": str(out_dir),
            "report_path": str(report_path),
            "report_html_path": str(report_html_path),
            "session_path": str(session_path),
            "context_path": str(context_path),
            "focus_path": str(focus_path),
            "docs_report_path": str(docs_report_path),
            "docs_report_html_path": str(docs_report_html_path),
            "docs_context_path": str(docs_context_path),
            "docs_focus_path": str(docs_focus_path),
        },
        "context_summary": scan_result.get("summary", {}),
        "focus_summary": focus_plan.get("summary", {}),
        "language_distribution": scan_result.get("language_distribution", []),
        "entrypoints_primary": scan_result.get("entrypoints_primary", []),
        "entrypoints_top": scan_result.get("entrypoints_top", []),
        "rounds": dialogue.get("rounds", 0),
    }
