"""
Analysis tasks for single-file mode.

Single-file now supports:
- Python runtime profiling + whitebox
- Multi-language static analysis + AI whitebox/blackbox
"""
import traceback
from pathlib import Path
from time import perf_counter

from analysis.code_analyzer import CodeAnalyzer
from analysis.deepseek_analyzer import DeepSeekAnalyzer
from analysis.manager import analysis_manager
from models.deepseek_config import DeepSeekConfig
from utils.converters import convert_markdown_to_html, convert_markdown_to_pdf
from utils.helpers import safe_get_artifact_type, simplify_obj


PYTHON_SUFFIXES = {".py", ".pyw"}


def _render_static_markdown_report(code_structure: dict, deepseek_results: dict, output_language: str) -> str:
    basic = code_structure.get("basic_info", {}) if isinstance(code_structure, dict) else {}
    complexity = code_structure.get("complexity", {}) if isinstance(code_structure, dict) else {}
    issues = code_structure.get("issues", []) if isinstance(code_structure, dict) else []
    signals = code_structure.get("performance_signals", {}) if isinstance(code_structure, dict) else {}

    if output_language == "en":
        lines = [
            "# AutoProfiler Single-File Report (Static Multi-language Mode)",
            "",
            "## File Summary",
            f"- Filename: {basic.get('filename', 'N/A')}",
            f"- Language: {basic.get('language', 'unknown')}",
            f"- File size (bytes): {basic.get('file_size', 0)}",
            f"- Total lines: {basic.get('total_lines', 0)}",
            f"- Code lines: {basic.get('code_lines', 0)}",
            "",
            "## Structural Metrics",
            f"- Functions: {complexity.get('function_count', len(code_structure.get('functions', [])))}",
            f"- Classes/Types: {complexity.get('class_count', len(code_structure.get('classes', [])))}",
            f"- Branches: {complexity.get('branch_count', 0)}",
            f"- Loops: {complexity.get('loop_count', 0)}",
            f"- Max nested depth: {complexity.get('max_nested_depth', 0)}",
            "",
            "## Performance Signals (Heuristic)",
            f"- Nested loop suspected: {signals.get('nested_loop_suspected', False)}",
            f"- I/O keyword hits: {signals.get('io_keyword_hits', 0)}",
            f"- DB keyword hits: {signals.get('db_keyword_hits', 0)}",
            f"- Network keyword hits: {signals.get('network_keyword_hits', 0)}",
            f"- Concurrency keyword hits: {signals.get('concurrency_keyword_hits', 0)}",
            "",
            "## Potential Issues",
        ]
        if not issues:
            lines.append("- No obvious structural issues detected.")
        else:
            for issue in issues[:12]:
                lines.append(
                    f"- [{issue.get('severity', 'info')}] line {issue.get('lineno', 0)}: {issue.get('message', '')}"
                )
    else:
        lines = [
            "# AutoProfiler 单文件报告（静态多语言模式）",
            "",
            "## 文件摘要",
            f"- 文件名: {basic.get('filename', 'N/A')}",
            f"- 语言: {basic.get('language', 'unknown')}",
            f"- 文件大小(bytes): {basic.get('file_size', 0)}",
            f"- 总行数: {basic.get('total_lines', 0)}",
            f"- 代码行数: {basic.get('code_lines', 0)}",
            "",
            "## 结构指标",
            f"- 函数数: {complexity.get('function_count', len(code_structure.get('functions', [])))}",
            f"- 类/类型数: {complexity.get('class_count', len(code_structure.get('classes', [])))}",
            f"- 分支数: {complexity.get('branch_count', 0)}",
            f"- 循环数: {complexity.get('loop_count', 0)}",
            f"- 最大嵌套深度: {complexity.get('max_nested_depth', 0)}",
            "",
            "## 性能信号（启发式）",
            f"- 疑似嵌套循环: {signals.get('nested_loop_suspected', False)}",
            f"- I/O 关键词命中: {signals.get('io_keyword_hits', 0)}",
            f"- 数据库关键词命中: {signals.get('db_keyword_hits', 0)}",
            f"- 网络关键词命中: {signals.get('network_keyword_hits', 0)}",
            f"- 并发关键词命中: {signals.get('concurrency_keyword_hits', 0)}",
            "",
            "## 潜在问题",
        ]
        if not issues:
            lines.append("- 暂未发现明显结构性问题。")
        else:
            for issue in issues[:12]:
                lines.append(
                    f"- [{issue.get('severity', 'info')}] 第 {issue.get('lineno', 0)} 行: {issue.get('message', '')}"
                )

    if deepseek_results:
        lines.append("")
        lines.append("=" * 60)
        lines.append(
            "# DeepSeek AI Analysis Results" if output_language == "en" else "# DeepSeek AI 分析结果"
        )
        lines.append("")
        if deepseek_results.get("blackbox"):
            lines.append(
                "## Blackbox Performance Analysis" if output_language == "en" else "## 黑盒性能分析"
            )
            lines.append("")
            lines.append(str(deepseek_results["blackbox"]))
            lines.append("")
        if deepseek_results.get("whitebox"):
            lines.append("## Whitebox Code Analysis" if output_language == "en" else "## 白盒代码分析")
            lines.append("")
            lines.append(str(deepseek_results["whitebox"]))
            lines.append("")

    return "\n".join(lines)


def _run_static_multilang_analysis(file_path, analysis_id, deepseek_config, upload_folder):
    output_language = DeepSeekConfig.normalize_output_language(
        (deepseek_config or {}).get("output_language", "zh")
    )
    lang = CodeAnalyzer.detect_language(file_path)

    analysis_manager.update_status(
        analysis_id,
        "analyzing",
        progress=20,
        progress_text="正在进行静态多语言分析...",
    )
    code_structure = CodeAnalyzer.analyze_code_structure(file_path)
    if "error" in (code_structure or {}):
        analysis_manager.update_status(
            analysis_id,
            "failed",
            error=f"静态分析失败: {code_structure.get('error')}",
            progress_text="静态分析过程出错",
        )
        return

    analysis_manager.update_status(
        analysis_id,
        "analyzing",
        progress=55,
        progress_text="正在整理性能信号...",
    )
    performance_summary = {
        "analysis_mode": "static_single_file",
        "language": lang,
        "file_path": str(file_path),
        "summary": code_structure.get("summary", ""),
        "basic_info": code_structure.get("basic_info", {}),
        "complexity": code_structure.get("complexity", {}),
        "issues": code_structure.get("issues", []),
        "performance_signals": code_structure.get("performance_signals", {}),
    }
    performance_summary_simple = simplify_obj(performance_summary)

    deepseek_results = {}
    if deepseek_config.get("enable_blackbox", True) and DeepSeekConfig.has_any_model(deepseek_config):
        analysis_manager.update_status(
            analysis_id,
            "deepseek_blackbox",
            progress=65,
            progress_text="正在进行DeepSeek黑盒分析...",
        )
        blackbox_result = DeepSeekAnalyzer.analyze_with_deepseek(
            deepseek_config,
            "blackbox",
            performance_summary_simple,
        )
        if blackbox_result:
            deepseek_results["blackbox"] = blackbox_result
            analysis_manager.add_deepseek_result(analysis_id, "blackbox", blackbox_result)

    if deepseek_config.get("enable_whitebox", True) and DeepSeekConfig.has_any_model(deepseek_config):
        analysis_manager.update_status(
            analysis_id,
            "deepseek_whitebox",
            progress=80,
            progress_text="正在进行DeepSeek白盒分析...",
        )
        whitebox_payload = dict(code_structure)
        whitebox_payload["analysis_mode"] = "static_single_file"
        whitebox_payload["language"] = lang
        whitebox_result = DeepSeekAnalyzer.analyze_with_deepseek(
            deepseek_config,
            "whitebox",
            simplify_obj(whitebox_payload),
        )
        if whitebox_result:
            deepseek_results["whitebox"] = whitebox_result
            analysis_manager.add_deepseek_result(analysis_id, "whitebox", whitebox_result)

    analysis_manager.update_status(
        analysis_id,
        "generating_report",
        progress=92,
        progress_text="正在生成静态分析报告...",
    )
    markdown_report = _render_static_markdown_report(code_structure, deepseek_results, output_language)
    html_report = convert_markdown_to_html(markdown_report)

    pdf_path = None
    try:
        pdf_path = convert_markdown_to_pdf(markdown_report, Path(file_path).stem, upload_folder)
    except Exception:
        pdf_path = None

    result = {
        "markdown": markdown_report,
        "html": html_report,
        "pdf_path": pdf_path,
        "session_info": {
            "duration": 0.0,
            "exit_code": 0,
            "findings_count": len(code_structure.get("issues", [])),
        },
        "analysis_mode": "single_file_static_multilang",
        "deepseek_results": deepseek_results,
        "code_structure": code_structure,
        "performance_summary": performance_summary_simple,
    }
    analysis_manager.update_status(
        analysis_id,
        "completed",
        progress=100,
        progress_text="分析完成！",
        result=result,
        step_completed="单文件静态分析完成",
    )


def _run_python_runtime_analysis(file_path, analysis_id, deepseek_config, upload_folder):
    output_language = DeepSeekConfig.normalize_output_language(
        (deepseek_config or {}).get("output_language", "zh")
    )
    analysis_manager.update_status(
        analysis_id,
        "analyzing",
        progress=10,
        progress_text="正在导入分析模块...",
    )
    try:
        from autoprofiler.runner import Runner
        from autoprofiler.models import TargetProgram
        from autoprofiler.collectors.psutil_collector import PsutilCollector
        from autoprofiler.collectors.cprofile_collector import CProfileCollector
        from autoprofiler.patterns.loader import load_patterns
        from autoprofiler.analyzers.simple_analyzer import PatternMatchingAnalyzer
        from autoprofiler.reporting.reporter import render_markdown
    except ImportError as err:
        analysis_manager.update_status(
            analysis_id,
            "failed",
            error=f"AutoProfiler模块导入失败: {err}",
            progress_text="缺少AutoProfiler核心模块",
        )
        return

    analysis_manager.update_status(
        analysis_id,
        "analyzing",
        progress=20,
        progress_text="正在运行性能分析...",
    )
    file_path_obj = Path(file_path)
    target = TargetProgram(
        command=["python", str(file_path_obj)],
        timeout=60,
        cwd=str(file_path_obj.parent),
    )
    collectors = [PsutilCollector(sample_interval=0.1)]
    try:
        collectors.append(CProfileCollector())
    except Exception:
        pass

    analysis_manager.update_status(
        analysis_id,
        "analyzing",
        progress=40,
        progress_text="正在收集性能数据...",
    )
    runner = Runner()
    session = runner.run(target, collectors=collectors)

    analysis_manager.update_status(
        analysis_id,
        "analyzing",
        progress=60,
        progress_text="正在分析性能模式...",
    )
    try:
        patterns_file = Path(__file__).parent.parent / "autoprofiler" / "patterns" / "performance.yaml"
        if patterns_file.exists():
            patterns = load_patterns(patterns_file)
            analyzer = PatternMatchingAnalyzer(patterns)
            session.findings = analyzer.analyze(session.artifacts)
        else:
            session.findings = []
    except Exception:
        session.findings = []

    analysis_manager.update_status(
        analysis_id,
        "analyzing",
        progress=70,
        progress_text="准备性能数据摘要...",
    )
    performance_summary = {
        "analysis_mode": "python_runtime_profile",
        "language": "python",
        "duration": getattr(session, "duration", 0),
        "exit_code": getattr(session, "exit_code", 0),
        "findings_count": len(getattr(session, "findings", [])),
        "findings": getattr(session, "findings", []),
        "artifacts_summary": {},
    }
    artifacts = getattr(session, "artifacts", [])
    for artifact in artifacts:
        artifact_type = safe_get_artifact_type(artifact)
        performance_summary["artifacts_summary"].setdefault(artifact_type, [])
        try:
            if hasattr(artifact, "__dict__"):
                artifact_data = artifact.__dict__.copy()
            elif isinstance(artifact, dict):
                artifact_data = artifact.copy()
            else:
                artifact_data = str(artifact)
        except Exception:
            artifact_data = str(artifact)
        performance_summary["artifacts_summary"][artifact_type].append(artifact_data)
    performance_summary_simple = simplify_obj(performance_summary)

    deepseek_results = {}
    if deepseek_config.get("enable_blackbox", True) and DeepSeekConfig.has_any_model(deepseek_config):
        analysis_manager.update_status(
            analysis_id,
            "deepseek_blackbox",
            progress=75,
            progress_text="正在进行DeepSeek黑盒分析...",
        )
        blackbox_result = DeepSeekAnalyzer.analyze_with_deepseek(
            deepseek_config,
            "blackbox",
            performance_summary_simple,
        )
        if blackbox_result:
            deepseek_results["blackbox"] = blackbox_result
            analysis_manager.add_deepseek_result(analysis_id, "blackbox", blackbox_result)

    code_structure = None
    if deepseek_config.get("enable_whitebox", True):
        analysis_manager.update_status(
            analysis_id,
            "whitebox_analysis",
            progress=85,
            progress_text="正在进行代码结构分析...",
        )
        code_structure = CodeAnalyzer.analyze_code_structure(file_path)
        if DeepSeekConfig.has_any_model(deepseek_config):
            analysis_manager.update_status(
                analysis_id,
                "deepseek_whitebox",
                progress=90,
                progress_text="正在进行DeepSeek白盒分析...",
            )
            whitebox_result = DeepSeekAnalyzer.analyze_with_deepseek(
                deepseek_config,
                "whitebox",
                simplify_obj(code_structure),
            )
            if whitebox_result:
                deepseek_results["whitebox"] = whitebox_result
                analysis_manager.add_deepseek_result(analysis_id, "whitebox", whitebox_result)

    analysis_manager.update_status(
        analysis_id,
        "generating_report",
        progress=97,
        progress_text="正在生成最终报告...",
    )
    markdown_report = render_markdown(session)
    if deepseek_results:
        markdown_report += "\n\n" + "=" * 60 + "\n"
        markdown_report += (
            "# DeepSeek AI Analysis Results\n\n"
            if output_language == "en"
            else "# DeepSeek AI 分析结果\n\n"
        )
        if deepseek_results.get("blackbox"):
            section_title = (
                "## Blackbox Performance Analysis" if output_language == "en" else "## 黑盒性能分析"
            )
            markdown_report += f"{section_title}\n\n{deepseek_results['blackbox']}\n\n"
        if deepseek_results.get("whitebox"):
            section_title = "## Whitebox Code Analysis" if output_language == "en" else "## 白盒代码分析"
            markdown_report += f"{section_title}\n\n{deepseek_results['whitebox']}\n\n"

    if code_structure and not deepseek_results.get("whitebox"):
        markdown_report += "\n\n" + "=" * 60 + "\n"
        if output_language == "en":
            markdown_report += "## Code Structure Analysis\n\n"
            if "error" in code_structure:
                markdown_report += f"Code structure analysis failed: {code_structure['error']}\n\n"
            else:
                markdown_report += f"**Summary**: {code_structure.get('summary', 'N/A')}\n\n"
        else:
            markdown_report += "## 代码结构分析\n\n"
            if "error" in code_structure:
                markdown_report += f"代码结构分析失败: {code_structure['error']}\n\n"
            else:
                markdown_report += f"**摘要**: {code_structure.get('summary', 'N/A')}\n\n"

    html_report = convert_markdown_to_html(markdown_report)
    pdf_path = None
    try:
        pdf_path = convert_markdown_to_pdf(markdown_report, Path(file_path).stem, upload_folder)
    except Exception:
        pdf_path = None

    result = {
        "markdown": markdown_report,
        "html": html_report,
        "pdf_path": pdf_path,
        "session_info": {
            "duration": getattr(session, "duration", 0),
            "exit_code": getattr(session, "exit_code", 0),
            "findings_count": len(getattr(session, "findings", [])),
        },
        "analysis_mode": "single_file_python_runtime",
        "deepseek_results": deepseek_results,
        "code_structure": code_structure,
        "performance_summary": performance_summary_simple,
    }
    analysis_manager.update_status(
        analysis_id,
        "completed",
        progress=100,
        progress_text="分析完成！",
        result=result,
        step_completed="所有分析完成",
    )


def analyze_python_file(file_path, analysis_id, deepseek_config, upload_folder):
    """
    Backward-compatible single-file entry.

    Dispatches by file type:
    - Python: runtime profile + whitebox
    - Other supported languages: static multi-language analysis
    """
    started = perf_counter()
    try:
        suffix = Path(file_path).suffix.lower()
        if suffix in PYTHON_SUFFIXES:
            _run_python_runtime_analysis(file_path, analysis_id, deepseek_config, upload_folder)
        else:
            _run_static_multilang_analysis(file_path, analysis_id, deepseek_config, upload_folder)
        finished = perf_counter() - started
        analysis = analysis_manager.get_analysis(analysis_id) or {}
        if analysis.get("status") == "completed" and analysis.get("result"):
            result = analysis["result"]
            session_info = result.get("session_info", {})
            if not session_info.get("duration"):
                session_info["duration"] = round(finished, 3)
                result["session_info"] = session_info
    except Exception as err:
        print(f"分析错误: {err}")
        traceback.print_exc()
        analysis_manager.update_status(
            analysis_id,
            "failed",
            error=f"分析失败: {err}",
            progress_text="分析过程出错",
        )
