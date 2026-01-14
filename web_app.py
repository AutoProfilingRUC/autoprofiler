#!/usr/bin/env python3
"""
AutoProfiler Web界面增强版 - 支持Markdown渲染和PDF导出
"""

from flask import Flask, request, render_template, jsonify, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import sys
import json
import tempfile
import uuid
import traceback
from pathlib import Path
from datetime import datetime
import subprocess

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')
CORS(app)

# 配置
app.config.update(
    MAX_CONTENT_LENGTH=50 * 1024 * 1024,
    UPLOAD_FOLDER=tempfile.gettempdir() + '/autoprofiler_uploads',
    SECRET_KEY='autoprofiler-enhanced',
    JSON_AS_ASCII=False,
)

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class AnalysisManager:
    """分析管理器"""
    def __init__(self):
        self.analyses = {}
    
    def create_analysis(self, file_path, original_name):
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
    
    def update_status(self, analysis_id, status, progress=0, result=None, error=None):
        if analysis_id in self.analyses:
            self.analyses[analysis_id]['status'] = status
            self.analyses[analysis_id]['progress'] = progress
            if result:
                self.analyses[analysis_id]['result'] = result
            if error:
                self.analyses[analysis_id]['error'] = error
    
    def get_analysis(self, analysis_id):
        return self.analyses.get(analysis_id)

analysis_manager = AnalysisManager()

def analyze_python_file(file_path, analysis_id):
    """分析Python文件"""
    try:
        # 导入AutoProfiler核心模块
        from autoprofiler.runner import Runner
        from autoprofiler.models import TargetProgram
        from autoprofiler.collectors.psutil_collector import PsutilCollector
        from autoprofiler.collectors.cprofile_collector import CProfileCollector
        from autoprofiler.patterns.loader import load_patterns
        from autoprofiler.analyzers.simple_analyzer import PatternMatchingAnalyzer
        from autoprofiler.reporting.reporter import render_markdown
        
        analysis_manager.update_status(analysis_id, 'analyzing', progress=20)
        
        # 运行分析
        target = TargetProgram(
            command=["python", str(file_path)],
            timeout=60,
            cwd=str(file_path.parent)
        )
        
        collectors = [PsutilCollector(sample_interval=0.1)]
        try:
            collectors.append(CProfileCollector())
        except:
            pass
        
        analysis_manager.update_status(analysis_id, 'analyzing', progress=40)
        
        runner = Runner()
        session = runner.run(target, collectors=collectors)
        
        analysis_manager.update_status(analysis_id, 'analyzing', progress=70)
        
        # 加载模式
        try:
            patterns_file = project_root / "autoprofiler" / "patterns" / "performance.yaml"
            if patterns_file.exists():
                patterns = load_patterns(patterns_file)
                analyzer = PatternMatchingAnalyzer(patterns)
                session.findings = analyzer.analyze(session.artifacts)
            else:
                session.findings = []
        except:
            session.findings = []
        
        analysis_manager.update_status(analysis_id, 'analyzing', progress=90)
        
        # 生成Markdown报告
        markdown_report = render_markdown(session)
        
        # 转换为HTML（用于Web显示）
        html_report = convert_markdown_to_html(markdown_report)
        
        # 生成PDF（可选）
        pdf_path = None
        try:
            pdf_path = convert_markdown_to_pdf(markdown_report, file_path.stem)
        except Exception as e:
            print(f"PDF生成失败: {e}")
        
        # 准备结果
        result = {
            'markdown': markdown_report,
            'html': html_report,
            'pdf_path': pdf_path,
            'session_info': {
                'duration': getattr(session, 'duration', 0),
                'exit_code': getattr(session, 'exit_code', 0),
                'findings_count': len(getattr(session, 'findings', []))
            }
        }
        
        analysis_manager.update_status(analysis_id, 'completed', progress=100, result=result)
        
    except Exception as e:
        error_msg = f"分析失败: {str(e)}"
        print(f"分析错误: {error_msg}")
        traceback.print_exc()
        analysis_manager.update_status(analysis_id, 'failed', error=error_msg)

def convert_markdown_to_html(markdown_text):
    """将Markdown转换为HTML"""
    # 简单的Markdown到HTML转换
    import re
    
    html = markdown_text
    
    # 标题转换
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    
    # 粗体和斜体
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    
    # 代码块
    html = re.sub(r'```(.+?)```', r'<pre><code>\1</code></pre>', html, flags=re.DOTALL)
    html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)
    
    # 列表
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'(<li>.+</li>\n)+', r'<ul>\g<0></ul>', html)
    
    # 链接
    html = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', html)
    
    # 段落
    lines = html.split('\n')
    result_lines = []
    current_paragraph = []
    
    for line in lines:
        if line.strip() and not line.startswith('<'):
            current_paragraph.append(line)
        else:
            if current_paragraph:
                result_lines.append(f'<p>{" ".join(current_paragraph)}</p>')
                current_paragraph = []
            result_lines.append(line)
    
    if current_paragraph:
        result_lines.append(f'<p>{" ".join(current_paragraph)}</p>')
    
    html = '\n'.join(result_lines)
    
    # 添加CSS样式
    styled_html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                color: #333;
            }}
            h1 {{
                color: #2c3e50;
                border-bottom: 2px solid #3498db;
                padding-bottom: 10px;
            }}
            h2 {{
                color: #34495e;
                margin-top: 30px;
                border-left: 4px solid #3498db;
                padding-left: 10px;
            }}
            h3 {{
                color: #7f8c8d;
            }}
            pre {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 5px;
                border-left: 4px solid #3498db;
                overflow: auto;
                font-family: 'Consolas', monospace;
            }}
            code {{
                background: #f1f2f3;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Consolas', monospace;
            }}
            ul {{
                padding-left: 20px;
            }}
            li {{
                margin: 5px 0;
            }}
            .finding {{
                background: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 10px 0;
                border-radius: 3px;
            }}
            .metric {{
                background: #e8f4fd;
                padding: 10px;
                margin: 10px 0;
                border-radius: 5px;
                border: 1px solid #b8daff;
            }}
        </style>
    </head>
    <body>
        {html}
    </body>
    </html>
    '''
    
    return styled_html

def convert_markdown_to_pdf(markdown_text, filename):
    """将Markdown转换为PDF"""
    # 需要安装：pip install markdown weasyprint
    
    try:
        import markdown
        from weasyprint import HTML
        
        # 将Markdown转换为HTML
        html_content = markdown.markdown(markdown_text, extensions=['extra', 'codehilite'])
        
        # 添加完整HTML结构
        full_html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{
                    margin: 2cm;
                    @bottom-right {{
                        content: "页码 " counter(page) " / " counter(pages);
                        font-size: 10pt;
                    }}
                }}
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                h1 {{
                    color: #2c3e50;
                    border-bottom: 2px solid #3498db;
                    padding-bottom: 10px;
                }}
                h2 {{
                    color: #34495e;
                    margin-top: 25px;
                }}
                pre {{
                    background: #f5f5f5;
                    padding: 15px;
                    border-radius: 5px;
                    font-family: 'Courier New', monospace;
                    font-size: 12px;
                    overflow: auto;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                    border-bottom: 3px solid #3498db;
                    padding-bottom: 20px;
                }}
                .footer {{
                    margin-top: 50px;
                    padding-top: 20px;
                    border-top: 1px solid #ddd;
                    font-size: 10pt;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>AutoProfiler 性能分析报告</h1>
                <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            </div>
            
            {html_content}
            
            <div class="footer">
                <p>本报告由 AutoProfiler 生成 - 自动化Python性能分析工具</p>
                <p>报告文件: {filename}.py</p>
            </div>
        </body>
        </html>
        '''
        
        # 生成PDF
        pdf_filename = f"{filename}_report.pdf"
        pdf_path = Path(app.config['UPLOAD_FOLDER']) / pdf_filename
        
        HTML(string=full_html).write_pdf(pdf_path)
        
        return str(pdf_path)
        
    except ImportError:
        # 如果weasyprint不可用，尝试使用其他方法
        try:
            # 使用命令行工具：需要安装 pandoc 和 wkhtmltopdf
            md_path = Path(app.config['UPLOAD_FOLDER']) / f"{filename}_temp.md"
            pdf_path = Path(app.config['UPLOAD_FOLDER']) / f"{filename}_report.pdf"
            
            # 保存Markdown文件
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(markdown_text)
            
            # 尝试使用pandoc转换
            try:
                subprocess.run(['pandoc', str(md_path), '-o', str(pdf_path)], 
                             check=True, capture_output=True)
                return str(pdf_path)
            except:
                # 如果pandoc不可用，创建HTML并用浏览器打印
                html_path = Path(app.config['UPLOAD_FOLDER']) / f"{filename}_temp.html"
                html_content = convert_markdown_to_html(markdown_text)
                
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                # 使用weasyprint的替代方案
                return None
                
        except Exception as e:
            print(f"PDF转换失败: {e}")
            return None

# ============= 路由定义 =============

@app.route('/')
def index():
    """首页"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AutoProfiler - Python性能分析</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 1000px;
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
                color: #2c3e50;
                border-bottom: 2px solid #3498db;
                padding-bottom: 10px;
            }
            .upload-area {
                border: 3px dashed #ccc;
                padding: 40px;
                text-align: center;
                margin: 20px 0;
                border-radius: 10px;
                cursor: pointer;
                background: #fafafa;
            }
            .upload-area:hover {
                border-color: #3498db;
                background: #f0f8ff;
            }
            .btn {
                background: #3498db;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                margin: 5px;
                transition: background 0.3s;
            }
            .btn:hover {
                background: #2980b9;
            }
            .btn-secondary {
                background: #95a5a6;
            }
            .btn-success {
                background: #27ae60;
            }
            .btn-danger {
                background: #e74c3c;
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
                background: #3498db;
                border-radius: 10px;
                transition: width 0.3s;
            }
            .result-container {
                margin-top: 30px;
                display: none;
            }
            .result-tabs {
                display: flex;
                border-bottom: 2px solid #3498db;
                margin-bottom: 20px;
            }
            .tab {
                padding: 10px 20px;
                cursor: pointer;
                border: 1px solid #ddd;
                border-bottom: none;
                border-radius: 5px 5px 0 0;
                background: #f8f9fa;
                margin-right: 5px;
            }
            .tab.active {
                background: #3498db;
                color: white;
                border-color: #3498db;
            }
            .tab-content {
                display: none;
                padding: 20px;
                border: 1px solid #ddd;
                border-top: none;
                border-radius: 0 0 5px 5px;
                background: white;
                max-height: 500px;
                overflow: auto;
            }
            .tab-content.active {
                display: block;
            }
            .html-preview {
                border: 1px solid #ddd;
                padding: 20px;
                border-radius: 5px;
                background: white;
                max-height: 500px;
                overflow: auto;
            }
            .actions {
                margin: 20px 0;
                text-align: center;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>AutoProfiler - Python性能分析工具</h1>
            <p>上传Python文件进行性能分析，查看格式化的报告</p>
            
            <div class="upload-area" id="dropArea">
                <p>拖放Python文件到此处 或 点击选择文件</p>
                <input type="file" id="fileInput" accept=".py,.pyw" style="display: none;">
                <button class="btn" onclick="document.getElementById('fileInput').click()">
                    选择文件
                </button>
                <p>支持 .py, .pyw 文件，最大50MB</p>
            </div>
            
            <div class="progress" id="progress">
                <div class="progress-bar" id="progressBar"></div>
                <div id="progressText">0%</div>
            </div>
            
            <div class="result-container" id="resultContainer">
                <h2>分析结果</h2>
                
                <div class="result-tabs">
                    <div class="tab active" onclick="showTab('preview')">HTML预览</div>
                    <div class="tab" onclick="showTab('markdown')">Markdown源码</div>
                    <div class="tab" onclick="showTab('raw')">原始数据</div>
                </div>
                
                <div class="tab-content active" id="previewTab">
                    <div class="html-preview" id="htmlPreview"></div>
                </div>
                
                <div class="tab-content" id="markdownTab">
                    <pre id="markdownContent"></pre>
                </div>
                
                <div class="tab-content" id="rawTab">
                    <pre id="rawData"></pre>
                </div>
                
                <div class="actions">
                    <button class="btn btn-success" onclick="downloadReport('html')">下载HTML报告</button>
                    <button class="btn" onclick="downloadReport('markdown')">下载Markdown</button>
                    <button class="btn btn-secondary" onclick="downloadReport('pdf')">下载PDF</button>
                    <button class="btn" onclick="copyToClipboard('html')">复制HTML</button>
                    <button class="btn btn-danger" onclick="resetAnalysis()">新的分析</button>
                </div>
            </div>
        </div>
        
        <script>
            let currentAnalysisId = null;
            let currentReport = null;
            
            // 拖放功能
            const dropArea = document.getElementById('dropArea');
            const fileInput = document.getElementById('fileInput');
            
            dropArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                dropArea.style.borderColor = '#3498db';
                dropArea.style.background = '#f0f8ff';
            });
            
            dropArea.addEventListener('dragleave', () => {
                dropArea.style.borderColor = '#ccc';
                dropArea.style.background = '#fafafa';
            });
            
            dropArea.addEventListener('drop', (e) => {
                e.preventDefault();
                dropArea.style.borderColor = '#ccc';
                dropArea.style.background = '#fafafa';
                
                if (e.dataTransfer.files.length > 0) {
                    uploadFile(e.dataTransfer.files[0]);
                }
            });
            
            fileInput.addEventListener('change', (e) => {
                if (fileInput.files.length > 0) {
                    uploadFile(fileInput.files[0]);
                }
            });
            
            function uploadFile(file) {
                if (!file.name.match(/\.(py|pyw)$/i)) {
                    alert('请选择Python文件 (.py 或 .pyw)');
                    return;
                }
                
                const formData = new FormData();
                formData.append('file', file);
                
                document.getElementById('progress').style.display = 'block';
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
                        alert('上传失败: ' + (data.error || '未知错误'));
                        updateProgress(0, '');
                    }
                })
                .catch(error => {
                    alert('上传失败: ' + error.message);
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
                            currentReport = data.result;
                            showResults(data.result);
                            updateProgress(100, '分析完成');
                            
                            // 3秒后隐藏进度条
                            setTimeout(() => {
                                document.getElementById('progress').style.display = 'none';
                            }, 3000);
                        } else if (data.status === 'failed') {
                            alert('分析失败: ' + (data.error || '未知错误'));
                            updateProgress(0, '');
                        } else {
                            // 继续轮询
                            setTimeout(checkAnalysisStatus, 1000);
                        }
                    } else {
                        alert('获取状态失败: ' + (data.error || '未知错误'));
                        updateProgress(0, '');
                    }
                })
                .catch(error => {
                    alert('获取状态失败: ' + error.message);
                    updateProgress(0, '');
                });
            }
            
            function showResults(result) {
                // 显示HTML预览
                document.getElementById('htmlPreview').innerHTML = result.html;
                
                // 显示Markdown源码
                document.getElementById('markdownContent').textContent = result.markdown;
                
                // 显示原始数据
                document.getElementById('rawData').textContent = JSON.stringify(result, null, 2);
                
                // 显示结果容器
                document.getElementById('resultContainer').style.display = 'block';
                
                // 滚动到结果
                document.getElementById('resultContainer').scrollIntoView({ behavior: 'smooth' });
            }
            
            function showTab(tabName) {
                // 更新标签页
                document.querySelectorAll('.tab').forEach(tab => {
                    tab.classList.remove('active');
                });
                document.querySelectorAll('.tab-content').forEach(content => {
                    content.classList.remove('active');
                });
                
                // 激活选中的标签页
                event.target.classList.add('active');
                document.getElementById(tabName + 'Tab').classList.add('active');
            }
            
            function downloadReport(format) {
                if (!currentAnalysisId || !currentReport) {
                    alert('没有可下载的报告');
                    return;
                }
                
                let url, filename;
                
                switch(format) {
                    case 'html':
                        const htmlBlob = new Blob([currentReport.html], { type: 'text/html' });
                        url = URL.createObjectURL(htmlBlob);
                        filename = 'report.html';
                        break;
                    case 'markdown':
                        const mdBlob = new Blob([currentReport.markdown], { type: 'text/markdown' });
                        url = URL.createObjectURL(mdBlob);
                        filename = 'report.md';
                        break;
                    case 'pdf':
                        if (!currentReport.pdf_path) {
                            alert('PDF生成失败或不可用');
                            return;
                        }
                        url = `/api/download/pdf/${currentAnalysisId}`;
                        filename = 'report.pdf';
                        break;
                }
                
                if (format !== 'pdf') {
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                } else {
                    // PDF直接打开下载
                    window.open(url, '_blank');
                }
            }
            
            function copyToClipboard(format) {
                if (!currentReport) {
                    alert('没有可复制的内容');
                    return;
                }
                
                let textToCopy;
                if (format === 'html') {
                    textToCopy = currentReport.html;
                } else {
                    textToCopy = currentReport.markdown;
                }
                
                navigator.clipboard.writeText(textToCopy)
                    .then(() => alert('已复制到剪贴板'))
                    .catch(err => alert('复制失败: ' + err));
            }
            
            function resetAnalysis() {
                currentAnalysisId = null;
                currentReport = null;
                document.getElementById('resultContainer').style.display = 'none';
                document.getElementById('progress').style.display = 'none';
                fileInput.value = '';
                
                // 重置预览
                document.getElementById('htmlPreview').innerHTML = '';
                document.getElementById('markdownContent').textContent = '';
                document.getElementById('rawData').textContent = '';
            }
            
            function updateProgress(percent, text) {
                document.getElementById('progressBar').style.width = percent + '%';
                document.getElementById('progressText').textContent = text + ' (' + percent + '%)';
            }
        </script>
    </body>
    </html>
    '''

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """处理文件上传"""
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "没有文件"})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "没有选择文件"})
        
        filename = secure_filename(file.filename)
        file_extension = Path(filename).suffix
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        file_path = Path(app.config['UPLOAD_FOLDER']) / unique_filename
        
        file.save(file_path)
        
        analysis_id = analysis_manager.create_analysis(file_path, filename)
        
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
            'filename': filename
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": f"上传失败: {str(e)}"}), 500

@app.route('/api/analysis/<analysis_id>')
def get_analysis_status(analysis_id):
    """获取分析状态"""
    analysis = analysis_manager.get_analysis(analysis_id)
    
    if not analysis:
        return jsonify({"success": False, "error": "分析会话不存在"}), 404
    
    response = {
        'success': True,
        'analysis_id': analysis_id,
        'status': analysis['status'],
        'progress': analysis['progress']
    }
    
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

def main():
    """主函数"""
    print("\n" + "="*60)
    print("AutoProfiler Web 界面增强版")
    print("="*60)
    print("功能特性:")
    print("  ✓ HTML格式报告预览")
    print("  ✓ Markdown源码查看")
    print("  ✓ PDF报告导出")
    print("  ✓ 多格式下载支持")
    print("="*60)
    print(f"访问地址: http://127.0.0.1:5000")
    print("="*60)
    print("按 Ctrl+C 停止服务\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)

if __name__ == '__main__':
    main()