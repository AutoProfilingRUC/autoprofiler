"""
Asynchronous task wrapper for proj-analyser.
"""
import traceback

from proj_analyser.manager import project_analysis_manager
from proj_analyser.service import analyze_project_with_api


def analyze_project_task(project_path, analysis_id, deepseek_config, options):
    try:
        project_analysis_manager.update_status(
            analysis_id,
            "analyzing",
            progress=5,
            progress_text="准备开始项目级性能分析...",
        )

        def on_progress(progress, text):
            project_analysis_manager.update_status(
                analysis_id,
                "analyzing",
                progress=progress,
                progress_text=text,
            )

        result = analyze_project_with_api(
            project_path=project_path,
            deepseek_config=deepseek_config or {},
            query_terms=options.get("query_terms", []),
            top_files=options.get("top_files", 12),
            token_budget=options.get("token_budget", 12000),
            bytes_per_token=options.get("bytes_per_token", 4),
            max_rounds=options.get("max_rounds", 6),
            max_file_chars=options.get("max_file_chars", 4000),
            temperature=options.get("temperature", 0.1),
            max_output_tokens=options.get("max_output_tokens", 2200),
            progress_callback=on_progress,
        )

        project_analysis_manager.update_status(
            analysis_id,
            "completed",
            progress=100,
            progress_text="项目分析完成",
            result=result,
            step_completed="proj-analyser 完成",
        )
    except Exception as err:
        print(f"proj-analyser failed: {err}")
        traceback.print_exc()
        project_analysis_manager.update_status(
            analysis_id,
            "failed",
            progress_text="项目分析失败",
            error=str(err),
        )

