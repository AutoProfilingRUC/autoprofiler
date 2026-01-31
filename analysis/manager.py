"""
分析管理器
"""
import uuid
from datetime import datetime
from queue import Queue

class AnalysisManager:
    """分析管理器"""
    
    def __init__(self):
        self.analyses = {}
        self.progress_queues = {}  # 进度队列
    
    def create_analysis(self, file_path, original_name, deepseek_config=None):
        """创建新的分析任务"""
        analysis_id = str(uuid.uuid4())
        self.analyses[analysis_id] = {
            'id': analysis_id,
            'file_path': str(file_path),
            'original_name': original_name,
            'created_at': datetime.now().isoformat(),
            'status': 'pending',
            'progress': 0,
            'progress_text': '准备开始分析...',
            'result': None,
            'error': None,
            'deepseek_config': deepseek_config or {},
            'deepseek_results': {},
            'analysis_steps': []
        }
        self.progress_queues[analysis_id] = Queue()
        return analysis_id
    
    def update_status(self, analysis_id, status, progress=0, progress_text=None, 
                     result=None, error=None, step_completed=None):
        """更新分析状态"""
        if analysis_id in self.analyses:
            self.analyses[analysis_id]['status'] = status
            self.analyses[analysis_id]['progress'] = progress
            
            if progress_text:
                self.analyses[analysis_id]['progress_text'] = progress_text
                if step_completed:
                    self.analyses[analysis_id]['analysis_steps'].append(step_completed)
            
            if result:
                self.analyses[analysis_id]['result'] = result
            
            if error:
                self.analyses[analysis_id]['error'] = error
            
            # 将进度更新放入队列
            if analysis_id in self.progress_queues:
                self.progress_queues[analysis_id].put({
                    'progress': progress,
                    'progress_text': progress_text,
                    'status': status
                })
    
    def add_deepseek_result(self, analysis_id, analysis_type, result):
        """添加DeepSeek分析结果"""
        if analysis_id in self.analyses:
            if 'deepseek_results' not in self.analyses[analysis_id]:
                self.analyses[analysis_id]['deepseek_results'] = {}
            self.analyses[analysis_id]['deepseek_results'][analysis_type] = result
    
    def get_analysis(self, analysis_id):
        """获取分析任务"""
        return self.analyses.get(analysis_id)
    
    def get_progress_update(self, analysis_id, timeout=1):
        """获取进度更新（非阻塞）"""
        if analysis_id in self.progress_queues:
            try:
                return self.progress_queues[analysis_id].get_nowait()
            except:
                return None
        return None

# 全局分析管理器实例
analysis_manager = AnalysisManager()