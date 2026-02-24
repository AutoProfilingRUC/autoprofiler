"""
proj-analyser API routes.
"""
import threading
from pathlib import Path

from flask import jsonify, request

from models.deepseek_config import DeepSeekConfig
from proj_analyser.manager import project_analysis_manager
from proj_analyser.task import analyze_project_task


def _normalize_query_terms(raw_query):
    if raw_query is None:
        return []
    if isinstance(raw_query, str):
        items = [s.strip() for s in raw_query.split(",")]
        return [s for s in items if s]
    if isinstance(raw_query, list):
        return [str(s).strip() for s in raw_query if str(s).strip()]
    return []


def register_proj_analyser_routes(app):
    @app.route("/api/proj-analyser/analyze", methods=["POST"])
    def start_project_analysis():
        payload = request.get_json(silent=True) or {}
        project_path = str(payload.get("project_path", "")).strip()
        if not project_path:
            return jsonify({"success": False, "error": "project_path 不能为空"}), 400

        raw_project_dir = Path(project_path)
        if not raw_project_dir.is_absolute():
            return jsonify({"success": False, "error": "project_path 必须是绝对路径"}), 400

        project_dir = raw_project_dir.resolve()
        if not project_dir.exists() or not project_dir.is_dir():
            return jsonify({"success": False, "error": f"项目路径无效: {project_dir}"}), 400

        deepseek_config = payload.get("deepseek_config") or DeepSeekConfig.load()
        if "output_language" in payload:
            deepseek_config = dict(deepseek_config or {})
            deepseek_config["output_language"] = payload.get("output_language")
        deepseek_config = DeepSeekConfig.normalize_config(deepseek_config)
        try:
            options = {
                "query_terms": _normalize_query_terms(payload.get("query")),
                "top_files": int(payload.get("top_files", 12)),
                "token_budget": int(payload.get("token_budget", 12000)),
                "bytes_per_token": int(payload.get("bytes_per_token", 4)),
                "max_rounds": int(payload.get("max_rounds", 6)),
                "max_file_chars": int(payload.get("max_file_chars", 4000)),
                "temperature": float(payload.get("temperature", 0.1)),
                "max_output_tokens": int(payload.get("max_output_tokens", 2200)),
            }
        except Exception as err:
            return jsonify({"success": False, "error": f"参数格式错误: {err}"}), 400

        analysis_id = project_analysis_manager.create_analysis(
            project_path=str(project_dir),
            deepseek_config=deepseek_config,
            options=options,
        )

        thread = threading.Thread(
            target=analyze_project_task,
            args=(str(project_dir), analysis_id, deepseek_config, options),
            daemon=True,
        )
        thread.start()

        return jsonify(
            {
                "success": True,
                "analysis_id": analysis_id,
                "project_path": str(project_dir),
                "message": "proj-analyser 已启动",
            }
        )

    @app.route("/api/proj-analyser/analysis/<analysis_id>", methods=["GET"])
    def get_project_analysis_status(analysis_id):
        analysis = project_analysis_manager.get_analysis(analysis_id)
        if not analysis:
            return jsonify({"success": False, "error": "分析会话不存在"}), 404

        response = {
            "success": True,
            "analysis_id": analysis_id,
            "status": analysis.get("status"),
            "progress": analysis.get("progress"),
            "progress_text": analysis.get("progress_text", "分析中..."),
            "analysis_steps": analysis.get("analysis_steps", []),
            "project_path": analysis.get("project_path"),
        }

        progress_update = project_analysis_manager.get_progress_update(analysis_id)
        if progress_update:
            response.update(progress_update)

        if analysis.get("status") == "completed":
            response["result"] = analysis.get("result")
        if analysis.get("status") == "failed":
            response["error"] = analysis.get("error")
        return jsonify(response)
