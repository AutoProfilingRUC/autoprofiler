"""
主要API路由
"""
from flask import render_template, jsonify, request, send_file
from pathlib import Path
import json
import uuid

from analysis.manager import analysis_manager
from analysis.task import analyze_python_file
from utils.file_handlers import save_uploaded_file

def register_routes(app):
    """注册主要路由"""
    
    @app.route('/')
    def index():
        """首页"""
        return render_template('index.html')
    
    @app.route('/api/upload', methods=['POST'])
    def upload_file():
        """处理文件上传"""
        try:
            if 'file' not in request.files:
                return jsonify({"success": False, "error": "没有文件"}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({"success": False, "error": "没有选择文件"}), 400
            
            # 保存文件
            file_path, original_name = save_uploaded_file(file, app.config['UPLOAD_FOLDER'])
            
            # 获取DeepSeek配置
            deepseek_config = request.form.get('deepseek_config')
            if deepseek_config:
                try:
                    deepseek_config = json.loads(deepseek_config)
                except:
                    from models.deepseek_config import DeepSeekConfig
                    deepseek_config = DeepSeekConfig.load()
            else:
                from models.deepseek_config import DeepSeekConfig
                deepseek_config = DeepSeekConfig.load()
            
            # 创建分析任务
            analysis_id = analysis_manager.create_analysis(
                file_path, 
                original_name, 
                deepseek_config
            )
            
            # 启动分析线程
            import threading
            thread = threading.Thread(
                target=analyze_python_file,
                args=(file_path, analysis_id, deepseek_config, app.config['UPLOAD_FOLDER']),
                daemon=True
            )
            thread.start()
            
            return jsonify({
                'success': True,
                'analysis_id': analysis_id,
                'filename': original_name
            })
            
        except Exception as e:
            return jsonify({"success": False, "error": f"上传失败: {str(e)}"}), 500
    
    @app.route('/api/analysis/<analysis_id>')
    def get_analysis_status(analysis_id):
        """获取分析状态和进度"""
        analysis = analysis_manager.get_analysis(analysis_id)
        
        if not analysis:
            return jsonify({"success": False, "error": "分析会话不存在"}), 404
        
        response = {
            'success': True,
            'analysis_id': analysis_id,
            'status': analysis['status'],
            'progress': analysis['progress'],
            'progress_text': analysis.get('progress_text', '分析中...'),
            'analysis_steps': analysis.get('analysis_steps', [])
        }
        
        # 获取最新的进度更新
        progress_update = analysis_manager.get_progress_update(analysis_id)
        if progress_update:
            response.update(progress_update)
        
        if analysis['status'] == 'completed' and analysis['result']:
            response['result'] = analysis['result']
        
        if analysis['status'] == 'failed' and analysis['error']:
            response['error'] = analysis['error']
        
        return jsonify(response)
    
    @app.route('/api/download/pdf/<analysis_id>')
    def download_pdf(analysis_id):
        """下载PDF报告"""
        analysis = analysis_manager.get_analysis(analysis_id)
        
        if not analysis or not analysis.get('result') or not analysis['result'].get('pdf_path'):
            return "PDF报告不可用", 404
        
        pdf_path = analysis['result']['pdf_path']
        
        if not Path(pdf_path).exists():
            return "PDF文件不存在", 404
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"autoprofiler_report_{analysis['original_name'].replace('.py', '')}.pdf"
        )