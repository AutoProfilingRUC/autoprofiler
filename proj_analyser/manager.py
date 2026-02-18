"""
Project analysis manager for proj-analyser.
"""
import uuid
from datetime import datetime
from queue import Queue


class ProjectAnalysisManager:
    """Manage asynchronous project analysis tasks."""

    def __init__(self):
        self.analyses = {}
        self.progress_queues = {}

    def create_analysis(self, project_path, deepseek_config=None, options=None):
        analysis_id = str(uuid.uuid4())
        self.analyses[analysis_id] = {
            "id": analysis_id,
            "project_path": str(project_path),
            "created_at": datetime.now().isoformat(),
            "status": "pending",
            "progress": 0,
            "progress_text": "准备开始项目分析...",
            "result": None,
            "error": None,
            "deepseek_config": deepseek_config or {},
            "options": options or {},
            "analysis_steps": [],
        }
        self.progress_queues[analysis_id] = Queue()
        return analysis_id

    def update_status(
        self,
        analysis_id,
        status,
        progress=0,
        progress_text=None,
        result=None,
        error=None,
        step_completed=None,
    ):
        if analysis_id not in self.analyses:
            return
        current = self.analyses[analysis_id]
        current["status"] = status
        current["progress"] = progress
        if progress_text:
            current["progress_text"] = progress_text
            if step_completed:
                current["analysis_steps"].append(step_completed)
        if result is not None:
            current["result"] = result
        if error:
            current["error"] = error
        if analysis_id in self.progress_queues:
            self.progress_queues[analysis_id].put(
                {
                    "status": status,
                    "progress": progress,
                    "progress_text": progress_text,
                }
            )

    def get_analysis(self, analysis_id):
        return self.analyses.get(analysis_id)

    def get_progress_update(self, analysis_id):
        if analysis_id not in self.progress_queues:
            return None
        try:
            return self.progress_queues[analysis_id].get_nowait()
        except Exception:
            return None


project_analysis_manager = ProjectAnalysisManager()

