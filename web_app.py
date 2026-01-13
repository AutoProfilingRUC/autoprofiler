#!/usr/bin/env python3
"""
AutoProfiler Web界面 - 通过浏览器上传和分析Python文件
修复版：解决属性访问问题和转义序列警告
"""

import os
import sys
import json
import tempfile
import uuid
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 第三方库导入
try:
    from flask import Flask, request, render_template, jsonify, send_file, send_from_directory
    from flask_cors import CORS
    from werkzeug.utils import secure_filename
    FLASK_AVAILABLE = True
except ImportError:
    print("错误: Flask相关依赖未安装")
    print("请运行: pip install flask flask-cors werkzeug")
    FLASK_AVAILABLE = False
    sys.exit(1)

# 创建Flask应用
app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')
CORS(app)

# 配置
app.config.update(
    MAX_CONTENT_LENGTH=50 * 1024 * 1024,  # 最大50MB
    UPLOAD_FOLDER=tempfile.gettempdir() + '/autoprofiler_uploads',
    SECRET_KEY='autoprofiler-dev-key',
    JSON_AS_ASCII=False,
)

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class AnalysisManager:
    """分析管理器"""
    
    def __init__(self):
        self.analyses = {}
    
    def create_analysis(self, file_path: Path, original_name: str) -> str:
        """创建新的分析会话"""
        analysis_id = str(uuid.uuid4())
        
        self.analyses[analysis_id] = {
            'id': analysis_id,
            'file_path': str(file_path),
            'original_name': original_name,
            'created_at': datetime.now().isoformat(),
            'status': 'pending',
            'progress': 0,
            'result': None,
            'error': None,
        }
        
        return analysis_id
    
    def update_status(self, analysis_id: str, status: str, progress: int = 0, 
                     result: Dict = None, error: str = None):
        """更新分析状态"""
        if analysis_id in self.analyses:
            self.analyses[analysis_id]['status'] = status
            self.analyses[analysis_id]['progress'] = progress
            if result:
                self.analyses[analysis_id]['result'] = result
            if error:
                self.analyses[analysis_id]['error'] = error
            self.analyses[analysis_id]['updated_at'] = datetime.now().isoformat()
    
    def get_analysis(self, analysis_id: str) -> Optional[Dict]:
        """获取分析信息"""
        return self.analyses.get(analysis_id)
    
    def cleanup_old_analyses(self, max_age_hours: int = 24):
        """清理旧的分析数据"""
        current_time = datetime.now()
        to_delete = []
        
        for analysis_id, analysis in self.analyses.items():
            created_at = datetime.fromisoformat(analysis['created_at'])
            age_hours = (current_time - created_at).total_seconds() / 3600
            
            if age_hours > max_age_hours:
                # 清理文件
                try:
                    file_path = Path(analysis.get('file_path', ''))
                    if file_path.exists():
                        file_path.unlink()
                except:
                    pass
                to_delete.append(analysis_id)
        
        for analysis_id in to_delete:
            del self.analyses[analysis_id]

# 创建分析管理器实例
analysis_manager = AnalysisManager()

def safe_import_autoprofiler():
    """安全导入AutoProfiler模块"""
    try:
        # 检查基础依赖
        import psutil
        import yaml
    except ImportError as e:
        return False, f"缺少依赖: {str(e)}"
    
    try:
        # 尝试导入AutoProfiler核心模块
        from autoprofiler.runner import Runner
        from autoprofiler.models import TargetProgram
        from autoprofiler.collectors.psutil_collector import PsutilCollector
        from autoprofiler.collectors.cprofile_collector import CProfileCollector
        
        # 尝试导入其他模块（这些可能不存在）
        try:
            from autoprofiler.patterns.loader import load_patterns
            from autoprofiler.analyzers.simple_analyzer import PatternMatchingAnalyzer
            from autoprofiler.reporting.reporter import render_markdown
            return True, {
                'Runner': Runner,
                'TargetProgram': TargetProgram,
                'PsutilCollector': PsutilCollector,
                'CProfileCollector': CProfileCollector,
                'load_patterns': load_patterns,
                'PatternMatchingAnalyzer': PatternMatchingAnalyzer,
                'render_markdown': render_markdown,
                'has_full_module': True
            }
        except ImportError:
            # 如果缺少某些模块，使用基本功能
            return True, {
                'Runner': Runner,
                'TargetProgram': TargetProgram,
                'PsutilCollector': PsutilCollector,
                'CProfileCollector': CProfileCollector,
                'has_full_module': False
            }
    except ImportError as e:
        return False, f"无法导入AutoProfiler核心模块: {str(e)}"

def analyze_python_file(file_path: Path, analysis_id: str):
    """分析Python文件"""
    import_success, autoprofiler_modules = safe_import_autoprofiler()
    
    if not import_success:
        analysis_manager.update_status(analysis_id, 'failed', error=autoprofiler_modules)
        return
    
    try:
        # 解包模块
        Runner = autoprofiler_modules['Runner']
        TargetProgram = autoprofiler_modules['TargetProgram']
        PsutilCollector = autoprofiler_modules['PsutilCollector']
        CProfileCollector = autoprofiler_modules['CProfileCollector']
        
        # 检查是否有完整模块
        has_full_module = autoprofiler_modules.get('has_full_module', False)
        
        # 更新状态
        analysis_manager.update_status(analysis_id, 'analyzing', progress=20)
        
        # 构建目标程序
        target = TargetProgram(
            command=["python", str(file_path)],
            timeout=60,
            cwd=str(file_path.parent)
        )
        
        # 创建收集器
        collectors = [PsutilCollector(sample_interval=0.1)]
        
        # 尝试添加CProfile收集器
        try:
            collectors.append(CProfileCollector())
        except:
            print("警告: CProfileCollector不可用")
        
        analysis_manager.update_status(analysis_id, 'analyzing', progress=40)
        
        # 运行分析
        runner = Runner()
        session = runner.run(target, collectors=collectors)
        
        analysis_manager.update_status(analysis_id, 'analyzing', progress=70)
        
        # 生成报告
        report = "AutoProfiler 分析报告\n" + "="*50 + "\n\n"
        
        # 添加基本信息
        report += f"目标文件: {file_path.name}\n"
        report += f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # 尝试获取会话信息
        session_info = {}
        
        # 使用安全的属性访问
        for attr_name in ['duration', 'run_time', 'execution_time', 'total_time']:
            if hasattr(session, attr_name):
                session_info['duration'] = getattr(session, attr_name)
                break
        else:
            session_info['duration'] = 0
        
        for attr_name in ['exit_code', 'exitcode', 'returncode']:
            if hasattr(session, attr_name):
                session_info['exit_code'] = getattr(session, attr_name)
                break
        else:
            session_info['exit_code'] = 0
        
        report += f"运行时长: {session_info['duration']:.2f} 秒\n"
        report += f"退出码: {session_info['exit_code']}\n\n"
        
        # 如果有完整模块，尝试生成更详细的报告
        if has_full_module:
            try:
                load_patterns = autoprofiler_modules['load_patterns']
                PatternMatchingAnalyzer = autoprofiler_modules['PatternMatchingAnalyzer']
                render_markdown = autoprofiler_modules['render_markdown']
                
                # 加载性能模式
                patterns_file = project_root / "autoprofiler" / "patterns" / "performance.yaml"
                if patterns_file.exists():
                    patterns = load_patterns(patterns_file)
                    analyzer = PatternMatchingAnalyzer(patterns)
                    session.findings = analyzer.analyze(session.artifacts)
                    session_info['findings_count'] = len(session.findings)
                else:
                    session.findings = []
                    session_info['findings_count'] = 0
                
                # 生成详细报告
                detailed_report = render_markdown(session)
                if detailed_report:
                    report = detailed_report
                    
            except Exception as e:
                report += f"警告: 详细分析失败: {str(e)}\n\n"
                session_info['findings_count'] = 0
        else:
            session_info['findings_count'] = 0
            report += "注: 使用的是基础分析模式，某些高级功能可能不可用。\n"
            report += "要使用完整功能，请确保所有AutoProfiler模块已正确安装。\n\n"
        
        # 添加收集器信息
        report += "\n收集器信息:\n"
        if hasattr(session, 'artifacts') and session.artifacts:
            for artifact in session.artifacts:
                if hasattr(artifact, 'collector'):
                    report += f"- {artifact.collector}\n"
                    if hasattr(artifact, 'metrics'):
                        for key, value in artifact.metrics.items():
                            report += f"  {key}: {value}\n"
        else:
            report += "- 无收集器数据\n"
        
        analysis_manager.update_status(analysis_id, 'analyzing', progress=90)
        
        # 准备结果
        result = {
            'report': report,
            'session_info': session_info,
            'file_info': {
                'name': file_path.name,
                'size': file_path.stat().st_size,
                'created': datetime.fromtimestamp(file_path.stat().st_ctime).isoformat(),
            },
            'findings': []
        }
        
        # 如果有发现，添加详细信息
        if hasattr(session, 'findings') and session.findings:
            for f in session.findings:
                finding_data = {}
                if hasattr(f, 'id'):
                    finding_data['id'] = f.id
                if hasattr(f, 'description'):
                    finding_data['description'] = f.description
                if hasattr(f, 'evidence'):
                    finding_data['evidence'] = f.evidence
                if hasattr(f, 'suggestions'):
                    finding_data['suggestions'] = f.suggestions
                if hasattr(f, 'confidence'):
                    finding_data['confidence'] = f.confidence
                result['findings'].append(finding_data)
        
        analysis_manager.update_status(analysis_id, 'completed', progress=100, result=result)
        
    except Exception as e:
        error_msg = f"分析失败: {str(e)}"
        print(f"分析错误: {error_msg}")
        print(traceback.format_exc())
        analysis_manager.update_status(analysis_id, 'failed', error=error_msg)

def validate_python_file(file_path: Path) -> Dict[str, Any]:
    """验证Python文件"""
    if not file_path.exists():
        return {"valid": False, "error": "文件不存在"}
    
    if file_path.stat().st_size > 50 * 1024 * 1024:  # 50MB
        return {"valid": False, "error": "文件太大（最大50MB）"}
    
    # 检查文件扩展名
    if file_path.suffix.lower() not in ['.py', '.pyw', '.txt']:
        # 检查文件内容是否包含Python代码
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1024)
                if 'import' not in content and 'def ' not in content and 'print' not in content:
                    return {"valid": False, "error": "文件可能不是Python脚本"}
        except:
            return {"valid": False, "error": "无法读取文件内容"}
    
    return {"valid": True, "error": None}

# ============= 路由定义 =============

@app.route('/')
def index():
    """首页 - 返回简单HTML页面"""
    html = '''
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AutoProfiler Web</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                border-bottom: 2px solid #4CAF50;
                padding-bottom: 10px;
            }
            .upload-area {
                border: 3px dashed #ccc;
                padding: 40px;
                text-align: center;
                margin: 20px 0;
                border-radius: 10px;
                cursor: pointer;
                transition: all 0.3s;
                background: #fafafa;
            }
            .upload-area:hover {
                border-color: #4CAF50;
                background: #f9fff9;
            }
            .upload-area.dragover {
                border-color: #2196F3;
                background: #f0f8ff;
            }
            .upload-input {
                display: none;
            }
            .btn {
                background: #4CAF50;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                margin: 10px;
            }
            .btn:hover {
                background: #45a049;
            }
            .progress {
                width: 100%;
                background: #eee;
                border-radius: 10px;
                margin: 20px 0;
                display: none;
            }
            .progress-bar {
                width: 0%;
                height: 20px;
                background: #4CAF50;
                border-radius: 10px;
                transition: width 0.3s;
            }
            .result {
                margin-top: 20px;
                padding: 20px;
                background: #f9f9f9;
                border-radius: 5px;
                display: none;
            }
            pre {
                background: #f8f8f8;
                padding: 15px;
                border-radius: 5px;
                overflow: auto;
                max-height: 400px;
            }
            .error {
                color: #d32f2f;
                background: #ffebee;
                padding: 10px;
                border-radius: 5px;
                margin: 10px 0;
                display: none;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>AutoProfiler - Python性能分析</h1>
            <p>上传Python文件进行性能分析</p>
            
            <div class="upload-area" id="dropArea">
                <p>拖放Python文件到此处 或 点击选择文件</p>
                <input type="file" id="fileInput" class="upload-input" accept=".py,.pyw">
                <button class="btn" onclick="document.getElementById('fileInput').click()">
                    选择文件
                </button>
                <p class="file-info">支持 .py, .pyw 文件，最大50MB</p>
            </div>
            
            <div class="progress" id="progress">
                <div class="progress-bar" id="progressBar"></div>
                <div id="progressText">0%</div>
            </div>
            
            <div class="error" id="errorMessage"></div>
            
            <div class="result" id="result">
                <h2>分析结果</h2>
                <div id="resultContent"></div>
                <button class="btn" onclick="downloadReport()">下载报告</button>
                <button class="btn" onclick="copyReport()">复制报告</button>
            </div>
        </div>
        
        <script>
            let currentAnalysisId = null;
            
            // 拖放功能
            const dropArea = document.getElementById('dropArea');
            const fileInput = document.getElementById('fileInput');
            
            dropArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                dropArea.classList.add('dragover');
            });
            
            dropArea.addEventListener('dragleave', () => {
                dropArea.classList.remove('dragover');
            });
            
            dropArea.addEventListener('drop', (e) => {
                e.preventDefault();
                dropArea.classList.remove('dragover');
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    uploadFile(files[0]);
                }
            });
            
            fileInput.addEventListener('change', (e) => {
                if (fileInput.files.length > 0) {
                    uploadFile(fileInput.files[0]);
                }
            });
            
            function uploadFile(file) {
                if (!file.name.match(/\\.(py|pyw)$/i)) {
                    showError('请选择Python文件 (.py 或 .pyw)');
                    return;
                }
                
                const formData = new FormData();
                formData.append('file', file);
                
                document.getElementById('progress').style.display = 'block';
                document.getElementById('errorMessage').style.display = 'none';
                document.getElementById('result').style.display = 'none';
                updateProgress(10, '上传中...');
                
                fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        currentAnalysisId = data.analysis_id;
                        updateProgress(30, '开始分析...');
                        checkAnalysisStatus();
                    } else {
                        showError(data.error || '上传失败');
                        updateProgress(0, '');
                    }
                })
                .catch(error => {
                    showError('上传失败: ' + error.message);
                    updateProgress(0, '');
                });
            }
            
            function checkAnalysisStatus() {
                if (!currentAnalysisId) return;
                
                fetch('/api/analysis/' + currentAnalysisId)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateProgress(data.progress, '分析中...');
                        
                        if (data.status === 'completed') {
                            showResult(data);
                        } else if (data.status === 'failed') {
                            showError(data.error || '分析失败');
                            updateProgress(0, '');
                        } else {
                            // 继续轮询
                            setTimeout(checkAnalysisStatus, 1000);
                        }
                    } else {
                        showError(data.error || '获取状态失败');
                        updateProgress(0, '');
                    }
                })
                .catch(error => {
                    showError('获取状态失败: ' + error.message);
                    updateProgress(0, '');
                });
            }
            
            function showResult(data) {
                updateProgress(100, '分析完成');
                
                const resultDiv = document.getElementById('result');
                const contentDiv = document.getElementById('resultContent');
                
                let html = '<h3>报告摘要</h3>';
                if (data.result && data.result.session_info) {
                    const info = data.result.session_info;
                    html += `<p>运行时长: ${info.duration.toFixed(2)} 秒</p>`;
                    html += `<p>退出码: ${info.exit_code}</p>`;
                    html += `<p>发现问题: ${info.findings_count} 个</p>`;
                }
                
                html += '<h3>详细报告</h3>';
                if (data.result && data.result.report) {
                    html += `<pre>${escapeHtml(data.result.report)}</pre>`;
                }
                
                contentDiv.innerHTML = html;
                resultDiv.style.display = 'block';
                
                // 保存报告数据
                window.lastReport = data.result ? data.result.report : '';
            }
            
            function downloadReport() {
                if (!window.lastReport) return;
                
                const blob = new Blob([window.lastReport], { type: 'text/markdown' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'autoprofiler_report.md';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            }
            
            function copyReport() {
                if (!window.lastReport) return;
                
                navigator.clipboard.writeText(window.lastReport)
                    .then(() => alert('报告已复制到剪贴板'))
                    .catch(err => showError('复制失败: ' + err));
            }
            
            function updateProgress(percent, text) {
                document.getElementById('progressBar').style.width = percent + '%';
                document.getElementById('progressText').textContent = text + ' (' + percent + '%)';
            }
            
            function showError(message) {
                const errorDiv = document.getElementById('errorMessage');
                errorDiv.textContent = message;
                errorDiv.style.display = 'block';
            }
            
            function escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }
        </script>
    </body>
    </html>
    '''
    return html

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """处理文件上传"""
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "没有文件"})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "没有选择文件"})
        
        # 安全文件名
        original_filename = secure_filename(file.filename)
        file_extension = Path(original_filename).suffix
        
        # 生成唯一文件名
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        file_path = Path(app.config['UPLOAD_FOLDER']) / unique_filename
        
        # 保存文件
        file.save(file_path)
        
        # 验证文件
        validation = validate_python_file(file_path)
        if not validation['valid']:
            try:
                file_path.unlink()
            except:
                pass
            return jsonify({"success": False, "error": validation['error']}), 400
        
        # 创建分析会话
        analysis_id = analysis_manager.create_analysis(file_path, original_filename)
        
        # 在后台线程中运行分析
        import threading
        thread = threading.Thread(
            target=analyze_python_file,
            args=(file_path, analysis_id),
            daemon=True
        )
        thread.start()
        
        return jsonify({
            'success': True,
            'analysis_id': analysis_id,
            'filename': original_filename,
            'message': '文件上传成功'
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": f"上传失败: {str(e)}"}), 500

@app.route('/api/analysis/<analysis_id>')
def get_analysis_status(analysis_id):
    """获取分析状态"""
    analysis = analysis_manager.get_analysis(analysis_id)
    
    if not analysis:
        return jsonify({"success": False, "error": "分析会话不存在"}), 404
    
    response_data = {
        'success': True,
        'analysis_id': analysis_id,
        'status': analysis['status'],
        'progress': analysis['progress'],
    }
    
    if analysis['status'] == 'completed' and analysis['result']:
        response_data['result'] = analysis['result']
    
    if analysis['status'] == 'failed' and analysis['error']:
        response_data['error'] = analysis['error']
    
    return jsonify(response_data)

@app.route('/api/analysis/<analysis_id>/report')
def download_report(analysis_id):
    """下载分析报告"""
    analysis = analysis_manager.get_analysis(analysis_id)
    
    if not analysis or analysis['status'] != 'completed' or not analysis.get('result'):
        return jsonify({"success": False, "error": "报告不可用"}), 404
    
    report_content = analysis['result']['report']
    report_filename = f"autoprofiler_report_{analysis_id[:8]}.md"
    report_path = Path(app.config['UPLOAD_FOLDER']) / report_filename
    
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        return send_file(
            report_path,
            as_attachment=True,
            download_name=f"autoprofiler_report_{analysis['original_name'].replace('.py', '')}.md"
        )
    except Exception as e:
        return jsonify({"success": False, "error": f"生成报告失败: {str(e)}"}), 500

@app.route('/api/health')
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'service': 'AutoProfiler Web',
        'timestamp': datetime.now().isoformat()
    })

# ============= 启动应用 =============

def main():
    """主函数"""
    if not FLASK_AVAILABLE:
        print("错误: Flask相关依赖未安装")
        print("请运行: pip install flask flask-cors werkzeug")
        return
    
    # 创建必要目录
    for directory in ['static', 'templates']:
        dir_path = Path(project_root) / directory
        dir_path.mkdir(exist_ok=True)
    
    print("\n" + "="*60)
    print("AutoProfiler Web 界面")
    print("="*60)
    print(f"访问地址: http://127.0.0.1:5000")
    print(f"上传目录: {app.config['UPLOAD_FOLDER']}")
    print("="*60)
    print("按 Ctrl+C 停止服务")
    print("\n")
    
    # 运行Flask应用
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )

if __name__ == '__main__':
    main()