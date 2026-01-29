#!/usr/bin/env python3
"""
AutoProfiler Web界面增强版 - 支持Markdown渲染、PDF导出和DeepSeek AI分析
修复版：解决ProfileArtifact对象访问问题
"""

from flask import Flask, request, render_template, jsonify, send_file, send_from_directory, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import sys
import json
import tempfile
import uuid
import traceback
import requests
from pathlib import Path
from datetime import datetime
import subprocess
import time
import threading
from queue import Queue
import re
import ast
import asyncio
import concurrent.futures

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
    SECRET_KEY='autoprofiler-enhanced-deepseek',
    JSON_AS_ASCII=False,
    PERMANENT_SESSION_LIFETIME=3600,  # 1小时
)

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# DeepSeek API配置存储文件
DEEPSEEK_CONFIG_FILE = Path(app.config['UPLOAD_FOLDER']) / 'deepseek_config.json'

class DeepSeekConfig:
    """DeepSeek API配置管理器"""
    
    @staticmethod
    def load():
        """加载配置"""
        default_config = {
            'api_key': '',
            'api_url': 'https://api.deepseek.com/v1/chat/completions',
            'model': 'deepseek-chat',
            'enable_blackbox': True,
            'enable_whitebox': True,
            'temperature': 0.3,
            'max_tokens': 2000
        }
        
        if DEEPSEEK_CONFIG_FILE.exists():
            try:
                with open(DEEPSEEK_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except:
                pass
        
        return default_config
    
    @staticmethod
    def save(config):
        """保存配置"""
        with open(DEEPSEEK_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

class AnalysisManager:
    """分析管理器"""
    def __init__(self):
        self.analyses = {}
        self.progress_queues = {}  # 进度队列
    
    def create_analysis(self, file_path, original_name, deepseek_config=None):
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
        if analysis_id in self.analyses:
            if 'deepseek_results' not in self.analyses[analysis_id]:
                self.analyses[analysis_id]['deepseek_results'] = {}
            self.analyses[analysis_id]['deepseek_results'][analysis_type] = result
    
    def get_analysis(self, analysis_id):
        return self.analyses.get(analysis_id)
    
    def get_progress_update(self, analysis_id, timeout=1):
        """获取进度更新（非阻塞）"""
        if analysis_id in self.progress_queues:
            try:
                return self.progress_queues[analysis_id].get_nowait()
            except:
                return None
        return None

analysis_manager = AnalysisManager()

class CodeAnalyzer:
    """白盒代码分析器"""
    
    @staticmethod
    def analyze_code_structure(file_path):
        """分析代码结构"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code_content = f.read()
            
            # 使用AST分析代码结构
            tree = ast.parse(code_content)
            
            analysis = {
                'basic_info': CodeAnalyzer._get_basic_info(tree, file_path),
                'functions': CodeAnalyzer._analyze_functions(tree),
                'classes': CodeAnalyzer._analyze_classes(tree),
                'imports': CodeAnalyzer._analyze_imports(tree),
                'complexity': CodeAnalyzer._analyze_complexity(tree),
                'issues': CodeAnalyzer._detect_issues(tree),
                'suggestions': []
            }
            
            # 生成代码结构摘要
            analysis['summary'] = CodeAnalyzer._generate_summary(analysis)
            
            return analysis
        except Exception as e:
            return {'error': f'代码分析失败: {str(e)}'}
    
    @staticmethod
    def _get_basic_info(tree, file_path):
        """获取基本信息"""
        return {
            'filename': Path(file_path).name,
            'file_size': os.path.getsize(file_path),
            'total_lines': len(Path(file_path).read_text().splitlines()),
            'code_lines': sum(1 for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Expr))),
            'analysis_time': datetime.now().isoformat()
        }
    
    @staticmethod
    def _analyze_functions(tree):
        """分析函数"""
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func = {
                    'name': node.name,
                    'lineno': node.lineno,
                    'args': len(node.args.args),
                    'has_docstring': ast.get_docstring(node) is not None,
                    'has_decorators': len(node.decorator_list) > 0,
                    'calls': []
                }
                
                # 分析函数内部调用
                for subnode in ast.walk(node):
                    if isinstance(subnode, ast.Call):
                        if isinstance(subnode.func, ast.Name):
                            func['calls'].append(subnode.func.id)
                
                functions.append(func)
        return functions
    
    @staticmethod
    def _analyze_classes(tree):
        """分析类"""
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                cls = {
                    'name': node.name,
                    'lineno': node.lineno,
                    'methods': [],
                    'bases': [base.id if isinstance(base, ast.Name) else str(base) 
                             for base in node.bases],
                    'has_docstring': ast.get_docstring(node) is not None
                }
                
                # 分析类方法
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        cls['methods'].append(item.name)
                
                classes.append(cls)
        return classes
    
    @staticmethod
    def _analyze_imports(tree):
        """分析导入语句"""
        imports = {'simple': [], 'from_import': []}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports['simple'].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    imports['from_import'].append(f"{module}.{alias.name}")
        return imports
    
    @staticmethod
    def _analyze_complexity(tree):
        """分析复杂度"""
        # 简单复杂度分析
        functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        
        total_statements = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Expr))
        
        return {
            'function_count': len(functions),
            'class_count': len(classes),
            'avg_function_length': total_statements / len(functions) if functions else 0,
            'max_nested_depth': CodeAnalyzer._get_max_nested_depth(tree)
        }
    
    @staticmethod
    def _get_max_nested_depth(tree):
        """获取最大嵌套深度"""
        max_depth = 0
        
        def visit_node(node, depth):
            nonlocal max_depth
            max_depth = max(max_depth, depth)
            
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.Try, 
                                     ast.FunctionDef, ast.ClassDef)):
                    visit_node(child, depth + 1)
                else:
                    visit_node(child, depth)
        
        visit_node(tree, 0)
        return max_depth
    
    @staticmethod
    def _detect_issues(tree):
        """检测常见问题"""
        issues = []
        
        # 检测过长的函数
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_lines = node.end_lineno - node.lineno if node.end_lineno else 0
                if func_lines > 50:
                    issues.append({
                        'type': 'long_function',
                        'message': f'函数 {node.name} 过长 ({func_lines} 行)',
                        'lineno': node.lineno,
                        'severity': 'warning'
                    })
        
        return issues
    
    @staticmethod
    def _generate_summary(analysis):
        """生成摘要"""
        func_count = len(analysis['functions'])
        class_count = len(analysis['classes'])
        issue_count = len(analysis['issues'])
        
        return f"代码分析完成: {func_count} 个函数, {class_count} 个类, 发现 {issue_count} 个潜在问题"

class DeepSeekAnalyzer:
    """DeepSeek API分析器"""
    
    @staticmethod
    def analyze_with_deepseek(config, analysis_type, content, progress_callback=None):
        """使用DeepSeek API进行分析"""
        if not config.get('api_key'):
            return None
        
        # 准备提示词
        if analysis_type == 'blackbox':
            prompt = DeepSeekAnalyzer._create_blackbox_prompt(content)
        elif analysis_type == 'whitebox':
            prompt = DeepSeekAnalyzer._create_whitebox_prompt(content)
        else:
            return None
        
        # 调用API
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {config["api_key"]}'
            }
            
            data = {
                'model': config.get('model', 'deepseek-chat'),
                'messages': [
                    {
                        'role': 'system',
                        'content': '你是一个专业的Python性能分析专家，请分析提供的性能数据或代码，给出具体的优化建议。'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'temperature': config.get('temperature', 0.3),
                'max_tokens': config.get('max_tokens', 2000),
                'stream': False
            }
            
            if progress_callback:
                progress_callback(f'正在调用DeepSeek API进行{analysis_type}分析...')
            
            response = requests.post(
                config.get('api_url', 'https://api.deepseek.com/v1/chat/completions'),
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('choices', [{}])[0].get('message', {}).get('content', '')
            else:
                return f"API调用失败: {response.status_code} - {response.text}"
                
        except Exception as e:
            return f"DeepSeek分析失败: {str(e)}"
    
    @staticmethod
    def _create_blackbox_prompt(performance_data):
        """创建黑盒分析提示词"""
        prompt = f"""请分析以下Python程序的性能数据，找出性能瓶颈并提供具体的优化建议：

性能数据：
{json.dumps(performance_data, indent=2, ensure_ascii=False)}

请按照以下格式提供分析结果：

## DeepSeek AI 黑盒分析报告

### 性能瓶颈分析
1. **主要瓶颈**：（指出最严重的性能问题）
2. **问题原因**：（分析问题产生的原因）

### 优化建议
1. **短期优化**：（立即可以实施的改进）
2. **长期优化**：（需要重构的改进）
3. **架构建议**：（系统架构层面的建议）

### 预期收益
- 性能提升预估：
- 资源消耗降低：
- 代码可维护性提升：

请用中文回复，建议要具体、可操作。"""
        
        return prompt
    
    @staticmethod
    def _create_whitebox_prompt(code_structure):
        """创建白盒分析提示词"""
        prompt = f"""请分析以下Python代码的结构，找出潜在的问题并提供具体的优化建议：

代码结构分析结果：
{json.dumps(code_structure, indent=2, ensure_ascii=False)}

请按照以下格式提供分析结果：

## DeepSeek AI 白盒分析报告

### 代码结构评估
1. **代码质量评分**：（1-10分）
2. **主要优点**：
3. **主要问题**：

### 具体改进建议
1. **架构优化**：
2. **函数重构**：
3. **类设计改进**：
4. **异常处理优化**：
5. **代码规范问题**：

### 性能优化建议
1. **算法优化**：
2. **内存使用优化**：
3. **I/O优化**：

### 安全与可维护性
1. **安全问题**：
2. **可维护性建议**：
3. **测试建议**：

请用中文回复，建议要具体、可操作。"""
        
        return prompt

def safe_get_artifact_type(artifact):
    """安全获取artifact的类型"""
    try:
        # 尝试多种方式获取类型
        if hasattr(artifact, 'type'):
            return artifact.type
        elif hasattr(artifact, '__dict__'):
            return getattr(artifact, 'type', type(artifact).__name__)
        elif isinstance(artifact, dict):
            return artifact.get('type', 'unknown')
        else:
            return type(artifact).__name__
    except:
        return 'unknown'

def analyze_python_file(file_path, analysis_id, deepseek_config):
    """分析Python文件（包含DeepSeek分析）"""
    try:
        analysis_manager.update_status(
            analysis_id, 
            'analyzing', 
            progress=10,
            progress_text='正在导入分析模块...'
        )
        
        # 导入AutoProfiler核心模块
        from autoprofiler.runner import Runner
        from autoprofiler.models import TargetProgram
        from autoprofiler.collectors.psutil_collector import PsutilCollector
        from autoprofiler.collectors.cprofile_collector import CProfileCollector
        from autoprofiler.patterns.loader import load_patterns
        from autoprofiler.analyzers.simple_analyzer import PatternMatchingAnalyzer
        from autoprofiler.reporting.reporter import render_markdown
        
        analysis_manager.update_status(
            analysis_id,
            'analyzing',
            progress=20,
            progress_text='正在运行性能分析...'
        )
        
        # 运行性能分析
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
        
        analysis_manager.update_status(
            analysis_id,
            'analyzing',
            progress=40,
            progress_text='正在收集性能数据...'
        )
        
        runner = Runner()
        session = runner.run(target, collectors=collectors)
        
        analysis_manager.update_status(
            analysis_id,
            'analyzing',
            progress=60,
            progress_text='正在分析性能模式...'
        )
        
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
        
        analysis_manager.update_status(
            analysis_id,
            'analyzing',
            progress=70,
            progress_text='准备性能数据摘要...'
        )
        
        # 准备性能数据摘要（用于黑盒分析）
        performance_summary = {
            'duration': getattr(session, 'duration', 0),
            'exit_code': getattr(session, 'exit_code', 0),
            'findings_count': len(getattr(session, 'findings', [])),
            'findings': getattr(session, 'findings', []),
            'artifacts_summary': {}
        }
        
        # 汇总性能数据 - 使用安全的方法
        artifacts = getattr(session, 'artifacts', [])
        for artifact in artifacts:
            artifact_type = safe_get_artifact_type(artifact)
            if artifact_type not in performance_summary['artifacts_summary']:
                performance_summary['artifacts_summary'][artifact_type] = []
            
            # 尝试将artifact转换为可序列化的格式
            try:
                if hasattr(artifact, '__dict__'):
                    artifact_data = artifact.__dict__.copy()
                elif isinstance(artifact, dict):
                    artifact_data = artifact.copy()
                else:
                    artifact_data = str(artifact)
            except:
                artifact_data = str(artifact)
            
            performance_summary['artifacts_summary'][artifact_type].append(artifact_data)
        
        # 将复杂的对象转换为简单格式用于JSON序列化
        def simplify_obj(obj):
            if isinstance(obj, (int, float, str, bool, type(None))):
                return obj
            elif isinstance(obj, dict):
                return {k: simplify_obj(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [simplify_obj(item) for item in obj]
            elif hasattr(obj, '__dict__'):
                return simplify_obj(obj.__dict__)
            else:
                return str(obj)
        
        # 简化性能摘要用于DeepSeek分析
        performance_summary_simple = simplify_obj(performance_summary)
        
        # DeepSeek黑盒分析
        deepseek_results = {}
        if deepseek_config.get('enable_blackbox', True) and deepseek_config.get('api_key'):
            analysis_manager.update_status(
                analysis_id,
                'deepseek_blackbox',
                progress=75,
                progress_text='正在进行DeepSeek黑盒分析...'
            )
            
            def blackbox_progress(text):
                analysis_manager.update_status(
                    analysis_id,
                    'deepseek_blackbox',
                    progress=analysis_manager.get_analysis(analysis_id)['progress'] + 1,
                    progress_text=text
                )
            
            blackbox_result = DeepSeekAnalyzer.analyze_with_deepseek(
                deepseek_config,
                'blackbox',
                performance_summary_simple,
                blackbox_progress
            )
            
            if blackbox_result:
                deepseek_results['blackbox'] = blackbox_result
                analysis_manager.add_deepseek_result(analysis_id, 'blackbox', blackbox_result)
            
            analysis_manager.update_status(
                analysis_id,
                'analyzing',
                progress=80,
                progress_text='黑盒分析完成'
            )
        
        # 白盒代码结构分析
        code_structure = None
        if deepseek_config.get('enable_whitebox', True):
            analysis_manager.update_status(
                analysis_id,
                'whitebox_analysis',
                progress=85,
                progress_text='正在进行代码结构分析...'
            )
            
            code_structure = CodeAnalyzer.analyze_code_structure(file_path)
            
            if deepseek_config.get('api_key'):
                analysis_manager.update_status(
                    analysis_id,
                    'deepseek_whitebox',
                    progress=90,
                    progress_text='正在进行DeepSeek白盒分析...'
                )
                
                def whitebox_progress(text):
                    analysis_manager.update_status(
                        analysis_id,
                        'deepseek_whitebox',
                        progress=analysis_manager.get_analysis(analysis_id)['progress'] + 1,
                        progress_text=text
                    )
                
                whitebox_result = DeepSeekAnalyzer.analyze_with_deepseek(
                    deepseek_config,
                    'whitebox',
                    code_structure,
                    whitebox_progress
                )
                
                if whitebox_result:
                    deepseek_results['whitebox'] = whitebox_result
                    analysis_manager.add_deepseek_result(analysis_id, 'whitebox', whitebox_result)
            
            analysis_manager.update_status(
                analysis_id,
                'analyzing',
                progress=95,
                progress_text='白盒分析完成'
            )
        
        # 生成Markdown报告（包含DeepSeek分析结果）
        analysis_manager.update_status(
            analysis_id,
            'generating_report',
            progress=97,
            progress_text='正在生成最终报告...'
        )
        
        markdown_report = render_markdown(session)
        
        # 添加DeepSeek分析结果到报告
        if deepseek_results:
            markdown_report += "\n\n" + "="*60 + "\n"
            markdown_report += "# DeepSeek AI 分析结果\n\n"
            
            if 'blackbox' in deepseek_results:
                markdown_report += f"## 黑盒性能分析\n\n{deepseek_results['blackbox']}\n\n"
            
            if 'whitebox' in deepseek_results:
                markdown_report += f"## 白盒代码分析\n\n{deepseek_results['whitebox']}\n\n"
        
        # 添加代码结构分析结果（如果没有DeepSeek分析）
        if code_structure and not deepseek_results.get('whitebox'):
            markdown_report += "\n\n" + "="*60 + "\n"
            markdown_report += "## 代码结构分析\n\n"
            
            if 'error' in code_structure:
                markdown_report += f"代码结构分析失败: {code_structure['error']}\n\n"
            else:
                markdown_report += f"**摘要**: {code_structure.get('summary', 'N/A')}\n\n"
                
                if code_structure.get('basic_info'):
                    info = code_structure['basic_info']
                    markdown_report += f"**文件名**: {info.get('filename', 'N/A')}\n"
                    markdown_report += f"**文件大小**: {(info.get('file_size', 0) / 1024):.2f} KB\n"
                    markdown_report += f"**总行数**: {info.get('total_lines', 0)}\n"
                    markdown_report += f"**代码行数**: {info.get('code_lines', 0)}\n\n"
                
                if code_structure.get('functions'):
                    markdown_report += f"**函数数量**: {len(code_structure['functions'])}\n"
                    if code_structure['functions']:
                        markdown_report += "**前5个函数**:\n"
                        for func in code_structure['functions'][:5]:
                            markdown_report += f"- {func['name']} (第{func['lineno']}行, {func['args']}个参数)\n"
                        markdown_report += "\n"
                
                if code_structure.get('classes'):
                    markdown_report += f"**类数量**: {len(code_structure['classes'])}\n"
                
                if code_structure.get('issues'):
                    markdown_report += f"**发现问题**: {len(code_structure['issues'])}个\n"
                    for issue in code_structure['issues'][:3]:
                        markdown_report += f"- 第{issue['lineno']}行: {issue['message']}\n"
        
        # 转换为HTML（用于Web显示）
        html_report = convert_markdown_to_html(markdown_report)
        
        # 生成PDF（可选）
        pdf_path = None
        try:
            pdf_path = convert_markdown_to_pdf(markdown_report, file_path.stem)
        except Exception as e:
            print(f"PDF生成失败: {e}")
        
        # 准备最终结果
        result = {
            'markdown': markdown_report,
            'html': html_report,
            'pdf_path': pdf_path,
            'session_info': {
                'duration': getattr(session, 'duration', 0),
                'exit_code': getattr(session, 'exit_code', 0),
                'findings_count': len(getattr(session, 'findings', []))
            },
            'deepseek_results': deepseek_results,
            'code_structure': code_structure,
            'performance_summary': performance_summary_simple
        }
        
        analysis_manager.update_status(
            analysis_id,
            'completed',
            progress=100,
            progress_text='分析完成！',
            result=result,
            step_completed='所有分析完成'
        )
        
    except Exception as e:
        error_msg = f"分析失败: {str(e)}"
        print(f"分析错误: {error_msg}")
        traceback.print_exc()
        analysis_manager.update_status(
            analysis_id,
            'failed',
            error=error_msg,
            progress_text='分析过程出错'
        )

def convert_markdown_to_html(markdown_text):
    """将Markdown转换为HTML（增强版）"""
    # 简单的Markdown到HTML转换
    import re
    
    html = markdown_text
    
    # 标题转换
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    
    # 粗体和斜体
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    
    # 代码块
    def replace_code_block(match):
        code = match.group(1)
        lang = ''
        if code.startswith('python') or code.startswith('python\n'):
            lang = 'python'
            code = code[7:] if code.startswith('python\n') else code[6:]
        elif code.startswith('json') or code.startswith('json\n'):
            lang = 'json'
            code = code[5:] if code.startswith('json\n') else code[4:]
        
        code = code.strip()
        return f'<pre class="language-{lang}"><code>{code}</code></pre>'
    
    html = re.sub(r'```(\w*)\n?(.+?)```', replace_code_block, html, flags=re.DOTALL)
    html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)
    
    # 列表
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'(<li>.+</li>\n)+', r'<ul>\g<0></ul>', html)
    
    # 有序列表
    html = re.sub(r'^\d+\. (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'(<li>.+</li>\n)+', r'<ol>\g<0></ol>', html)
    
    # 链接
    html = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', html)
    
    # 水平线
    html = re.sub(r'^---\s*$', r'<hr>', html, flags=re.MULTILINE)
    
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
                max-width: 1000px;
                margin: 0 auto;
                padding: 20px;
                color: #333;
                background: #f8f9fa;
            }}
            .report-container {{
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 15px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 15px;
                margin-bottom: 25px;
            }}
            h2 {{
                color: #34495e;
                margin-top: 30px;
                border-left: 4px solid #3498db;
                padding-left: 15px;
                background: #f8f9fa;
                padding: 10px 15px;
                border-radius: 0 5px 5px 0;
            }}
            h3 {{
                color: #2c3e50;
                margin-top: 25px;
                padding-bottom: 5px;
                border-bottom: 1px solid #eee;
            }}
            h4 {{
                color: #7f8c8d;
                margin-top: 20px;
            }}
            pre {{
                background: #2d3748;
                color: #e2e8f0;
                padding: 20px;
                border-radius: 8px;
                border-left: 4px solid #3498db;
                overflow: auto;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 14px;
                line-height: 1.5;
                margin: 15px 0;
            }}
            code {{
                background: #f1f2f3;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Consolas', 'Monaco', monospace;
                color: #e53e3e;
            }}
            ul, ol {{
                padding-left: 25px;
                margin: 15px 0;
            }}
            li {{
                margin: 8px 0;
            }}
            .finding {{
                background: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px 20px;
                margin: 15px 0;
                border-radius: 0 5px 5px 0;
            }}
            .metric {{
                background: #e8f4fd;
                padding: 15px;
                margin: 15px 0;
                border-radius: 8px;
                border: 1px solid #b8daff;
            }}
            .deepseek-section {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 10px;
                margin: 25px 0;
            }}
            .deepseek-section h2 {{
                color: white;
                border-left: none;
                background: transparent;
                padding: 0;
            }}
            .deepseek-content {{
                background: rgba(255, 255, 255, 0.1);
                padding: 20px;
                border-radius: 8px;
                margin-top: 15px;
                backdrop-filter: blur(10px);
            }}
            .progress-step {{
                background: #28a745;
                color: white;
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 12px;
                margin-right: 10px;
                display: inline-block;
            }}
            .ai-suggestion {{
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                color: white;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
            }}
            .ai-suggestion h3 {{
                color: white;
                border-bottom: 1px solid rgba(255,255,255,0.3);
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            th {{
                background: #3498db;
                color: white;
                padding: 15px;
                text-align: left;
            }}
            td {{
                padding: 12px 15px;
                border-bottom: 1px solid #eee;
            }}
            tr:hover {{
                background: #f8f9fa;
            }}
            hr {{
                border: none;
                border-top: 2px solid #eee;
                margin: 30px 0;
            }}
            .timestamp {{
                color: #6c757d;
                font-size: 12px;
                text-align: right;
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #eee;
            }}
        </style>
    </head>
    <body>
        <div class="report-container">
            {html}
            <div class="timestamp">
                报告生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            </div>
        </div>
    </body>
    </html>
    '''
    
    return styled_html

def convert_markdown_to_pdf(markdown_text, filename):
    """将Markdown转换为PDF"""
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
                    @top-left {{
                        content: "AutoProfiler 性能分析报告";
                        font-size: 10pt;
                        color: #666;
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
                    page-break-after: avoid;
                }}
                h2 {{
                    color: #34495e;
                    margin-top: 25px;
                    page-break-after: avoid;
                }}
                h3 {{
                    color: #2c3e50;
                    margin-top: 20px;
                    page-break-after: avoid;
                }}
                pre {{
                    background: #f5f5f5;
                    padding: 15px;
                    border-radius: 5px;
                    font-family: 'Courier New', monospace;
                    font-size: 12px;
                    overflow: auto;
                    page-break-inside: avoid;
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
                .deepseek-section {{
                    background: #f8f9fa;
                    padding: 15px;
                    border-left: 4px solid #667eea;
                    margin: 20px 0;
                    border-radius: 5px;
                    page-break-inside: avoid;
                }}
                .ai-suggestion {{
                    background: #fff3e0;
                    padding: 15px;
                    border-left: 4px solid #ff9800;
                    margin: 15px 0;
                    border-radius: 5px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 15px 0;
                    page-break-inside: avoid;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 10px;
                    text-align: left;
                }}
                th {{
                    background: #f2f2f2;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>AutoProfiler 性能分析报告</h1>
                <h2>{filename}.py</h2>
                <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            </div>
            
            {html_content}
            
            <div class="footer">
                <p>本报告由 AutoProfiler 生成 - 自动化Python性能分析工具</p>
                <p>包含DeepSeek AI分析结果</p>
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
        # 备用方案
        return None
    except Exception as e:
        print(f"PDF转换失败: {e}")
        return None

# ============= 路由定义 =============

@app.route('/')
def index():
    """首页"""
    # 加载DeepSeek配置
    deepseek_config = DeepSeekConfig.load()
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AutoProfiler - Python性能分析工具</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                position: relative;
                overflow: hidden;
            }}
            .container::before {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 5px;
                background: linear-gradient(90deg, #667eea, #764ba2);
            }}
            h1 {{
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 15px;
                margin-bottom: 30px;
                display: flex;
                align-items: center;
                gap: 15px;
            }}
            h1 i {{
                color: #667eea;
                font-size: 1.2em;
            }}
            .subtitle {{
                color: #7f8c8d;
                font-size: 1.1em;
                margin-bottom: 30px;
                line-height: 1.6;
            }}
            .upload-area {{
                border: 3px dashed #667eea;
                padding: 60px 40px;
                text-align: center;
                margin: 30px 0;
                border-radius: 15px;
                cursor: pointer;
                background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                transition: all 0.3s ease;
                position: relative;
                overflow: hidden;
            }}
            .upload-area:hover {{
                border-color: #764ba2;
                background: linear-gradient(135deg, #f0f8ff 0%, #e6f2ff 100%);
                transform: translateY(-5px);
                box-shadow: 0 15px 30px rgba(102, 126, 234, 0.2);
            }}
            .upload-area.dragover {{
                border-color: #28a745;
                background: linear-gradient(135deg, #e8f5e9 0%, #d4edda 100%);
            }}
            .upload-icon {{
                font-size: 60px;
                color: #667eea;
                margin-bottom: 20px;
            }}
            .upload-text {{
                font-size: 18px;
                font-weight: 600;
                color: #2c3e50;
                margin-bottom: 10px;
            }}
            .upload-hint {{
                color: #6c757d;
                font-size: 14px;
                margin-top: 10px;
            }}
            .btn {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 14px 28px;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-size: 16px;
                font-weight: 600;
                margin: 5px;
                transition: all 0.3s ease;
                display: inline-flex;
                align-items: center;
                gap: 10px;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
            }}
            .btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
            }}
            .btn-secondary {{
                background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
            }}
            .btn-success {{
                background: linear-gradient(135deg, #28a745 0%, #218838 100%);
            }}
            .btn-danger {{
                background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            }}
            .btn-warning {{
                background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%);
                color: #212529;
            }}
            .btn-info {{
                background: linear-gradient(135deg, #17a2b8 0%, #138496 100%);
            }}
            .btn-small {{
                padding: 8px 16px;
                font-size: 14px;
            }}
            .progress-container {{
                width: 100%;
                background: #e9ecef;
                border-radius: 10px;
                margin: 30px 0;
                display: none;
                overflow: hidden;
                box-shadow: inset 0 2px 10px rgba(0,0,0,0.1);
            }}
            .progress-bar {{
                width: 0%;
                height: 25px;
                background: linear-gradient(90deg, #28a745, #20c997);
                border-radius: 10px;
                transition: width 0.5s ease;
                position: relative;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 600;
                color: white;
                text-shadow: 0 1px 2px rgba(0,0,0,0.2);
            }}
            .progress-text {{
                position: absolute;
                width: 100%;
                text-align: center;
                font-size: 14px;
                font-weight: 600;
                color: #2c3e50;
                margin-top: 30px;
                padding: 10px;
                background: #f8f9fa;
                border-radius: 8px;
                border: 1px solid #dee2e6;
            }}
            .progress-steps {{
                display: flex;
                justify-content: space-between;
                margin-top: 10px;
                font-size: 12px;
                color: #6c757d;
            }}
            .progress-step {{
                flex: 1;
                text-align: center;
                padding: 5px;
                border-top: 2px solid #dee2e6;
                position: relative;
            }}
            .progress-step.active {{
                border-color: #28a745;
                color: #28a745;
                font-weight: 600;
            }}
            .progress-step.completed {{
                border-color: #28a745;
                color: #28a745;
            }}
            .progress-step.completed::before {{
                content: "✓";
                position: absolute;
                top: -10px;
                left: 50%;
                transform: translateX(-50%);
                background: #28a745;
                color: white;
                width: 20px;
                height: 20px;
                border-radius: 50%;
                font-size: 12px;
                line-height: 20px;
            }}
            .result-container {{
                margin-top: 40px;
                display: none;
            }}
            .result-tabs {{
                display: flex;
                border-bottom: 2px solid #667eea;
                margin-bottom: 25px;
                overflow-x: auto;
            }}
            .tab {{
                padding: 12px 24px;
                cursor: pointer;
                border: 1px solid #dee2e6;
                border-bottom: none;
                border-radius: 8px 8px 0 0;
                background: #f8f9fa;
                margin-right: 5px;
                white-space: nowrap;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            .tab:hover {{
                background: #e9ecef;
            }}
            .tab.active {{
                background: #667eea;
                color: white;
                border-color: #667eea;
            }}
            .tab-content {{
                display: none;
                padding: 25px;
                border: 1px solid #dee2e6;
                border-top: none;
                border-radius: 0 0 8px 8px;
                background: white;
                max-height: 600px;
                overflow: auto;
                box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            }}
            .tab-content.active {{
                display: block;
            }}
            .html-preview {{
                border: 1px solid #dee2e6;
                padding: 20px;
                border-radius: 8px;
                background: white;
                max-height: 600px;
                overflow: auto;
            }}
            .actions {{
                margin: 25px 0;
                text-align: center;
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                justify-content: center;
            }}
            .ai-analysis-badge {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 6px 15px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 600;
                display: inline-flex;
                align-items: center;
                gap: 6px;
                margin: 5px;
            }}
            .deepseek-enabled {{
                background: #28a745;
                color: white;
                padding: 5px 10px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
                margin-left: 10px;
            }}
            .deepseek-disabled {{
                background: #6c757d;
                color: white;
                padding: 5px 10px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
                margin-left: 10px;
            }}
            .modal {{
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                z-index: 1000;
                justify-content: center;
                align-items: center;
            }}
            .modal-content {{
                background: white;
                padding: 30px;
                border-radius: 15px;
                max-width: 500px;
                width: 90%;
                max-height: 80vh;
                overflow-y: auto;
                box-shadow: 0 20px 40px rgba(0,0,0,0.2);
            }}
            .modal-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                border-bottom: 2px solid #667eea;
                padding-bottom: 15px;
            }}
            .modal-header h2 {{
                color: #2c3e50;
                margin: 0;
                display: flex;
                align-items: center;
                gap: 10px;
            }}
            .close-modal {{
                background: none;
                border: none;
                font-size: 24px;
                cursor: pointer;
                color: #6c757d;
                transition: color 0.2s;
            }}
            .close-modal:hover {{
                color: #e74c3c;
            }}
            .form-group {{
                margin-bottom: 20px;
            }}
            .form-group label {{
                display: block;
                margin-bottom: 8px;
                font-weight: 600;
                color: #2c3e50;
            }}
            .form-control {{
                width: 100%;
                padding: 12px;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                font-size: 16px;
                transition: border-color 0.3s;
            }}
            .form-control:focus {{
                border-color: #667eea;
                outline: none;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }}
            .form-control.password {{
                font-family: monospace;
                letter-spacing: 1px;
            }}
            .form-check {{
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 15px;
            }}
            .form-check-input {{
                width: 20px;
                height: 20px;
            }}
            .form-check-label {{
                font-weight: 600;
                color: #2c3e50;
            }}
            .help-text {{
                font-size: 12px;
                color: #6c757d;
                margin-top: 5px;
            }}
            .config-actions {{
                display: flex;
                justify-content: space-between;
                margin-top: 30px;
                gap: 10px;
            }}
            .config-actions .btn {{
                flex: 1;
            }}
            .notification {{
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px 25px;
                border-radius: 8px;
                color: white;
                font-weight: 600;
                z-index: 1001;
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                transform: translateX(100%);
                transition: transform 0.3s ease;
                max-width: 300px;
            }}
            .notification.show {{
                transform: translateX(0);
            }}
            .notification.success {{
                background: linear-gradient(135deg, #28a745 0%, #218838 100%);
            }}
            .notification.error {{
                background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            }}
            .notification.warning {{
                background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%);
                color: #212529;
            }}
            .stats-container {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin: 20px 0;
            }}
            .stat-card {{
                background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                padding: 20px;
                border-radius: 10px;
                border-left: 4px solid #667eea;
                text-align: center;
            }}
            .stat-value {{
                font-size: 24px;
                font-weight: 700;
                color: #2c3e50;
            }}
            .stat-label {{
                font-size: 12px;
                color: #6c757d;
                margin-top: 5px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .deepseek-status {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 15px;
                border-radius: 10px;
                margin: 20px 0;
                display: flex;
                align-items: center;
                gap: 15px;
            }}
            .status-indicator {{
                width: 10px;
                height: 10px;
                border-radius: 50%;
                background: {'#28a745' if deepseek_config['api_key'] else '#e74c3c'};
                animation: {'pulse 2s infinite' if deepseek_config['api_key'] else 'none'};
            }}
            @keyframes pulse {{
                0% {{ opacity: 1; }}
                50% {{ opacity: 0.5; }}
                100% {{ opacity: 1; }}
            }}
            .header-actions {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
            }}
            @media (max-width: 768px) {{
                .container {{
                    padding: 20px;
                }}
                .header-actions {{
                    flex-direction: column;
                    gap: 15px;
                }}
                .actions {{
                    flex-direction: column;
                }}
                .btn {{
                    width: 100%;
                    justify-content: center;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-actions">
                <h1>
                    <i class="fas fa-chart-line"></i>
                    AutoProfiler - Python性能分析
                </h1>
                <div>
                    <button class="btn btn-info" onclick="openDeepSeekConfig()">
                        <i class="fas fa-robot"></i>
                        DeepSeek配置
                    </button>
                    <button class="btn btn-secondary" onclick="showHelp()">
                        <i class="fas fa-question-circle"></i>
                        帮助
                    </button>
                </div>
            </div>
            
            <div class="deepseek-status">
                <div class="status-indicator"></div>
                <div>
                    <strong>DeepSeek AI分析</strong>
                    <div>状态: {'<span style="color:#28a745">已配置 ✓</span>' if deepseek_config['api_key'] else '<span style="color:#e74c3c">未配置 ✗</span>'}</div>
                </div>
                <div style="flex: 1"></div>
                <div>
                    <div><small>黑盒分析: {'✓ 启用' if deepseek_config['enable_blackbox'] else '✗ 禁用'}</small></div>
                    <div><small>白盒分析: {'✓ 启用' if deepseek_config['enable_whitebox'] else '✗ 禁用'}</small></div>
                </div>
            </div>
            
            <div class="subtitle">
                上传Python文件进行全面的性能分析，包括性能指标收集、代码结构分析，并结合DeepSeek AI提供智能优化建议。
            </div>
            
            <div class="upload-area" id="dropArea">
                <div class="upload-icon">
                    <i class="fas fa-cloud-upload-alt"></i>
                </div>
                <div class="upload-text">拖放Python文件到此处 或 点击选择文件</div>
                <input type="file" id="fileInput" accept=".py,.pyw" style="display: none;">
                <button class="btn" onclick="document.getElementById('fileInput').click()">
                    <i class="fas fa-file-code"></i>
                    选择文件
                </button>
                <div class="upload-hint">支持 .py, .pyw 文件，最大50MB</div>
            </div>
            
            <div class="progress-container" id="progress">
                <div class="progress-bar" id="progressBar"></div>
                <div class="progress-text" id="progressText">0% - 准备开始分析...</div>
                <div class="progress-steps" id="progressSteps">
                    <div class="progress-step" id="step1">准备</div>
                    <div class="progress-step" id="step2">性能分析</div>
                    <div class="progress-step" id="step3">黑盒分析</div>
                    <div class="progress-step" id="step4">白盒分析</div>
                    <div class="progress-step" id="step5">报告生成</div>
                </div>
            </div>
            
            <div class="result-container" id="resultContainer">
                <h2><i class="fas fa-chart-bar"></i> 分析结果</h2>
                
                <div class="stats-container" id="statsContainer">
                    <!-- 统计信息将通过JS动态填充 -->
                </div>
                
                <div class="result-tabs">
                    <div class="tab active" onclick="showTab('preview')">
                        <i class="fas fa-eye"></i> HTML预览
                    </div>
                    <div class="tab" onclick="showTab('markdown')">
                        <i class="fas fa-code"></i> Markdown源码
                    </div>
                    <div class="tab" onclick="showTab('structure')">
                        <i class="fas fa-sitemap"></i> 代码结构
                    </div>
                    <div class="tab" onclick="showTab('deepseek')">
                        <i class="fas fa-robot"></i> AI分析
                    </div>
                    <div class="tab" onclick="showTab('raw')">
                        <i class="fas fa-database"></i> 原始数据
                    </div>
                </div>
                
                <div class="tab-content active" id="previewTab">
                    <div class="html-preview" id="htmlPreview"></div>
                </div>
                
                <div class="tab-content" id="markdownTab">
                    <pre id="markdownContent"></pre>
                </div>
                
                <div class="tab-content" id="structureTab">
                    <div id="codeStructure"></div>
                </div>
                
                <div class="tab-content" id="deepseekTab">
                    <div id="deepseekResults"></div>
                </div>
                
                <div class="tab-content" id="rawTab">
                    <pre id="rawData"></pre>
                </div>
                
                <div class="actions">
                    <button class="btn btn-success" onclick="downloadReport('html')">
                        <i class="fas fa-download"></i> 下载HTML报告
                    </button>
                    <button class="btn" onclick="downloadReport('markdown')">
                        <i class="fas fa-file-alt"></i> 下载Markdown
                    </button>
                    <button class="btn btn-secondary" onclick="downloadReport('pdf')">
                        <i class="fas fa-file-pdf"></i> 下载PDF
                    </button>
                    <button class="btn btn-info" onclick="copyToClipboard('html')">
                        <i class="fas fa-copy"></i> 复制HTML
                    </button>
                    <button class="btn btn-danger" onclick="resetAnalysis()">
                        <i class="fas fa-redo"></i> 新的分析
                    </button>
                </div>
            </div>
        </div>
        
        <!-- DeepSeek配置模态框 -->
        <div class="modal" id="deepseekModal">
            <div class="modal-content">
                <div class="modal-header">
                    <h2><i class="fas fa-robot"></i> DeepSeek API配置</h2>
                    <button class="close-modal" onclick="closeDeepSeekConfig()">×</button>
                </div>
                <form id="deepseekConfigForm">
                    <div class="form-group">
                        <label for="apiKey">API密钥</label>
                        <input type="password" id="apiKey" class="form-control password" 
                               value="{deepseek_config['api_key']}"
                               placeholder="输入您的DeepSeek API密钥">
                        <div class="help-text">
                            可在 <a href="https://platform.deepseek.com/api_keys" target="_blank">DeepSeek平台</a> 获取API密钥
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label for="apiUrl">API地址</label>
                        <input type="text" id="apiUrl" class="form-control" 
                               value="{deepseek_config['api_url']}"
                               placeholder="https://api.deepseek.com/v1/chat/completions">
                        <div class="help-text">通常无需修改，除非使用自定义API端点</div>
                    </div>
                    
                    <div class="form-group">
                        <label for="model">模型</label>
                        <input type="text" id="model" class="form-control" 
                               value="{deepseek_config['model']}"
                               placeholder="deepseek-chat">
                        <div class="help-text">可选的DeepSeek模型名称</div>
                    </div>
                    
                    <div class="form-group">
                        <label>分析选项</label>
                        <div class="form-check">
                            <input type="checkbox" id="enableBlackbox" class="form-check-input" 
                                   {'checked' if deepseek_config['enable_blackbox'] else ''}>
                            <label for="enableBlackbox" class="form-check-label">启用黑盒分析</label>
                        </div>
                        <div class="help-text">基于性能数据的AI分析</div>
                        
                        <div class="form-check">
                            <input type="checkbox" id="enableWhitebox" class="form-check-input" 
                                   {'checked' if deepseek_config['enable_whitebox'] else ''}>
                            <label for="enableWhitebox" class="form-check-label">启用白盒分析</label>
                        </div>
                        <div class="help-text">基于代码结构的AI分析</div>
                    </div>
                    
                    <div class="form-group">
                        <label for="temperature">温度参数</label>
                        <input type="range" id="temperature" class="form-control" min="0" max="1" step="0.1" 
                               value="{deepseek_config['temperature']}">
                        <div class="help-text" id="temperatureValue">{deepseek_config['temperature']} (0=确定性高, 1=创造性高)</div>
                    </div>
                    
                    <div class="config-actions">
                        <button type="button" class="btn btn-success" onclick="saveDeepSeekConfig()">
                            <i class="fas fa-save"></i> 保存配置
                        </button>
                        <button type="button" class="btn btn-secondary" onclick="testDeepSeekConnection()">
                            <i class="fas fa-plug"></i> 测试连接
                        </button>
                        <button type="button" class="btn btn-danger" onclick="clearDeepSeekConfig()">
                            <i class="fas fa-trash"></i> 清除配置
                        </button>
                    </div>
                </form>
            </div>
        </div>
        
        <!-- 通知框 -->
        <div class="notification" id="notification"></div>
        
        <script>
            let currentAnalysisId = null;
            let currentReport = null;
            let progressInterval = null;
            let lastProgress = 0;
            
            // 加载DeepSeek配置
            let deepseekConfig = {json.dumps(deepseek_config, ensure_ascii=False)};
            
            // 拖放功能
            const dropArea = document.getElementById('dropArea');
            const fileInput = document.getElementById('fileInput');
            
            dropArea.addEventListener('dragover', (e) => {{
                e.preventDefault();
                dropArea.classList.add('dragover');
            }});
            
            dropArea.addEventListener('dragleave', () => {{
                dropArea.classList.remove('dragover');
            }});
            
            dropArea.addEventListener('drop', (e) => {{
                e.preventDefault();
                dropArea.classList.remove('dragover');
                
                if (e.dataTransfer.files.length > 0) {{
                    uploadFile(e.dataTransfer.files[0]);
                }}
            }});
            
            fileInput.addEventListener('change', (e) => {{
                if (fileInput.files.length > 0) {{
                    uploadFile(fileInput.files[0]);
                }}
            }});
            
            // 温度滑块显示
            document.getElementById('temperature').addEventListener('input', function() {{
                document.getElementById('temperatureValue').textContent = 
                    this.value + ' (0=确定性高, 1=创造性高)';
            }});
            
            function showNotification(message, type = 'success', duration = 3000) {{
                const notification = document.getElementById('notification');
                notification.textContent = message;
                notification.className = `notification ${{type}}`;
                notification.classList.add('show');
                
                setTimeout(() => {{
                    notification.classList.remove('show');
                }}, duration);
            }}
            
            function openDeepSeekConfig() {{
                document.getElementById('deepseekModal').style.display = 'flex';
            }}
            
            function closeDeepSeekConfig() {{
                document.getElementById('deepseekModal').style.display = 'none';
            }}
            
            function saveDeepSeekConfig() {{
                const config = {{
                    api_key: document.getElementById('apiKey').value.trim(),
                    api_url: document.getElementById('apiUrl').value.trim() || 'https://api.deepseek.com/v1/chat/completions',
                    model: document.getElementById('model').value.trim() || 'deepseek-chat',
                    enable_blackbox: document.getElementById('enableBlackbox').checked,
                    enable_whitebox: document.getElementById('enableWhitebox').checked,
                    temperature: parseFloat(document.getElementById('temperature').value)
                }};
                
                fetch('/api/deepseek/config', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify(config)
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        deepseekConfig = config;
                        showNotification('DeepSeek配置保存成功！', 'success');
                        closeDeepSeekConfig();
                        // 刷新页面以更新状态显示
                        setTimeout(() => location.reload(), 1000);
                    }} else {{
                        showNotification('保存失败: ' + data.error, 'error');
                    }}
                }})
                .catch(error => {{
                    showNotification('保存失败: ' + error.message, 'error');
                }});
            }}
            
            function clearDeepSeekConfig() {{
                if (confirm('确定要清除DeepSeek配置吗？')) {{
                    fetch('/api/deepseek/clear', {{
                        method: 'POST'
                    }})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            showNotification('DeepSeek配置已清除', 'success');
                            closeDeepSeekConfig();
                            setTimeout(() => location.reload(), 1000);
                        }}
                    }});
                }}
            }}
            
            async function testDeepSeekConnection() {{
                const apiKey = document.getElementById('apiKey').value.trim();
                if (!apiKey) {{
                    showNotification('请输入API密钥', 'warning');
                    return;
                }}
                
                showNotification('正在测试DeepSeek连接...', 'warning', 5000);
                
                try {{
                    const response = await fetch('/api/deepseek/test', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                        }},
                        body: JSON.stringify({{
                            api_key: apiKey,
                            api_url: document.getElementById('apiUrl').value.trim()
                        }})
                    }});
                    
                    const data = await response.json();
                    if (data.success) {{
                        showNotification('DeepSeek连接测试成功！', 'success');
                    }} else {{
                        showNotification('连接测试失败: ' + data.error, 'error');
                    }}
                }} catch (error) {{
                    showNotification('连接测试失败: ' + error.message, 'error');
                }}
            }}
            
            function showHelp() {{
                alert(`AutoProfiler 使用帮助

1. 基本使用：
   - 拖放或选择Python文件上传
   - 等待分析完成
   - 查看不同格式的报告

2. DeepSeek AI分析：
   - 点击"DeepSeek配置"按钮设置API密钥
   - 支持黑盒分析（基于性能数据）
   - 支持白盒分析（基于代码结构）
   - 配置后分析报告将包含AI建议

3. 报告格式：
   - HTML预览：格式化的完整报告
   - Markdown源码：原始Markdown内容
   - 代码结构：详细的代码分析
   - AI分析：DeepSeek的优化建议
   - 原始数据：完整分析数据

4. 下载选项：
   - HTML：适合网页查看
   - PDF：适合打印和分享
   - Markdown：适合编辑和存档

注意：DeepSeek API需要有效的API密钥，您可以在DeepSeek官网申请。`);
            }}
            
            function uploadFile(file) {{
                if (!file.name.match(/\\.(py|pyw)$/i)) {{
                    showNotification('请选择Python文件 (.py 或 .pyw)', 'error');
                    return;
                }}
                
                const formData = new FormData();
                formData.append('file', file);
                formData.append('deepseek_config', JSON.stringify(deepseekConfig));
                
                document.getElementById('progress').style.display = 'block';
                resetProgress();
                updateProgress(5, '正在上传文件...');
                
                fetch('/api/upload', {{
                    method: 'POST',
                    body: formData
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        currentAnalysisId = data.analysis_id;
                        updateProgress(10, '文件上传完成，开始分析...');
                        startProgressMonitoring();
                    }} else {{
                        showNotification('上传失败: ' + (data.error || '未知错误'), 'error');
                        resetProgress();
                    }}
                }})
                .catch(error => {{
                    showNotification('上传失败: ' + error.message, 'error');
                    resetProgress();
                }});
            }}
            
            function startProgressMonitoring() {{
                if (progressInterval) clearInterval(progressInterval);
                
                progressInterval = setInterval(() => {{
                    if (!currentAnalysisId) return;
                    
                    fetch('/api/analysis/' + currentAnalysisId)
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            updateProgress(data.progress, data.progress_text || '分析中...');
                            
                            // 更新步骤状态
                            updateStepStatus(data.status);
                            
                            if (data.status === 'completed') {{
                                currentReport = data.result;
                                showResults(data.result);
                                updateProgress(100, '分析完成！');
                                clearInterval(progressInterval);
                                
                                setTimeout(() => {{
                                    document.getElementById('progress').style.display = 'none';
                                }}, 3000);
                            }} else if (data.status === 'failed') {{
                                showNotification('分析失败: ' + (data.error || '未知错误'), 'error');
                                resetProgress();
                                clearInterval(progressInterval);
                            }}
                        }} else {{
                            showNotification('获取状态失败: ' + (data.error || '未知错误'), 'error');
                        }}
                    }})
                    .catch(error => {{
                        showNotification('获取状态失败: ' + error.message, 'error');
                    }});
                }}, 1000); // 每秒轮询一次
            }}
            
            function updateStepStatus(status) {{
                const steps = ['step1', 'step2', 'step3', 'step4', 'step5'];
                const stepElements = steps.map(id => document.getElementById(id));
                
                // 根据状态确定当前步骤
                let currentStep = 0;
                if (status.includes('analyzing')) currentStep = 1;
                if (status.includes('deepseek_blackbox')) currentStep = 2;
                if (status.includes('whitebox_analysis') || status.includes('deepseek_whitebox')) currentStep = 3;
                if (status.includes('generating_report')) currentStep = 4;
                if (status === 'completed') currentStep = 5;
                
                stepElements.forEach((step, index) => {{
                    step.classList.remove('active', 'completed');
                    if (index < currentStep) {{
                        step.classList.add('completed');
                    }} else if (index === currentStep) {{
                        step.classList.add('active');
                    }}
                }});
            }}
            
            function showResults(result) {{
                // 显示HTML预览
                document.getElementById('htmlPreview').innerHTML = result.html;
                
                // 显示Markdown源码
                document.getElementById('markdownContent').textContent = result.markdown;
                
                // 显示代码结构
                if (result.code_structure) {{
                    displayCodeStructure(result.code_structure);
                }}
                
                // 显示DeepSeek分析结果
                if (result.deepseek_results) {{
                    displayDeepSeekResults(result.deepseek_results);
                }}
                
                // 显示原始数据
                document.getElementById('rawData').textContent = JSON.stringify(result, null, 2);
                
                // 显示统计信息
                displayStats(result);
                
                // 显示结果容器
                document.getElementById('resultContainer').style.display = 'block';
                
                // 滚动到结果
                document.getElementById('resultContainer').scrollIntoView({{ behavior: 'smooth' }});
                
                showNotification('分析完成！', 'success');
            }}
            
            function displayStats(result) {{
                const statsContainer = document.getElementById('statsContainer');
                let statsHTML = '';
                
                const sessionInfo = result.session_info || {{}};
                const deepseekResults = result.deepseek_results || {{}};
                const codeStructure = result.code_structure || {{}};
                
                // 基本统计
                statsHTML += `
                    <div class="stat-card">
                        <div class="stat-value">${{sessionInfo.duration ? sessionInfo.duration.toFixed(2) : '0.00'}}</div>
                        <div class="stat-label">运行时间(秒)</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${{sessionInfo.findings_count || 0}}</div>
                        <div class="stat-label">发现问题</div>
                    </div>
                `;
                
                // DeepSeek统计
                if (Object.keys(deepseekResults).length > 0) {{
                    statsHTML += `
                        <div class="stat-card">
                            <div class="stat-value">${{Object.keys(deepseekResults).length}}</div>
                            <div class="stat-label">AI分析项</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">
                                <i class="fas fa-robot" style="color:#667eea"></i>
                            </div>
                            <div class="stat-label">AI分析完成</div>
                        </div>
                    `;
                }}
                
                // 代码结构统计
                if (codeStructure.basic_info) {{
                    statsHTML += `
                        <div class="stat-card">
                            <div class="stat-value">${{codeStructure.functions ? codeStructure.functions.length : 0}}</div>
                            <div class="stat-label">函数数量</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${{codeStructure.classes ? codeStructure.classes.length : 0}}</div>
                            <div class="stat-label">类数量</div>
                        </div>
                    `;
                }}
                
                statsContainer.innerHTML = statsHTML;
            }}
            
            function displayCodeStructure(structure) {{
                const container = document.getElementById('codeStructure');
                let html = '<div class="html-preview">';
                
                html += '<h3>代码结构分析</h3>';
                
                // 基本信息
                if (structure.basic_info) {{
                    html += '<div class="metric">';
                    html += '<h4>基本信息</h4>';
                    html += `<p><strong>文件:</strong> ${{structure.basic_info.filename}}</p>`;
                    html += `<p><strong>大小:</strong> ${{(structure.basic_info.file_size / 1024).toFixed(2)}} KB</p>`;
                    html += `<p><strong>总行数:</strong> ${{structure.basic_info.total_lines}}</p>`;
                    html += `<p><strong>代码行数:</strong> ${{structure.basic_info.code_lines}}</p>`;
                    html += '</div>';
                }}
                
                // 函数信息
                if (structure.functions && structure.functions.length > 0) {{
                    html += '<div class="metric">';
                    html += '<h4>函数分析</h4>';
                    html += `<p>共 ${{structure.functions.length}} 个函数</p>`;
                    html += '<table>';
                    html += '<tr><th>函数名</th><th>行号</th><th>参数</th><th>文档</th><th>调用</th></tr>';
                    structure.functions.slice(0, 10).forEach(func => {{
                        html += `<tr>
                            <td>${{func.name}}</td>
                            <td>${{func.lineno}}</td>
                            <td>${{func.args}}</td>
                            <td>${{func.has_docstring ? '✓' : '✗'}}</td>
                            <td>${{func.calls.length}}</td>
                        </tr>`;
                    }});
                    html += '</table>';
                    if (structure.functions.length > 10) {{
                        html += `<p>... 还有 ${{structure.functions.length - 10}} 个函数</p>`;
                    }}
                    html += '</div>';
                }}
                
                // 类信息
                if (structure.classes && structure.classes.length > 0) {{
                    html += '<div class="metric">';
                    html += '<h4>类分析</h4>';
                    html += `<p>共 ${{structure.classes.length}} 个类</p>`;
                    html += '<table>';
                    html += '<tr><th>类名</th><th>行号</th><th>方法数</th><th>继承</th><th>文档</th></tr>';
                    structure.classes.forEach(cls => {{
                        html += `<tr>
                            <td>${{cls.name}}</td>
                            <td>${{cls.lineno}}</td>
                            <td>${{cls.methods.length}}</td>
                            <td>${{cls.bases.join(', ') || '-'}}</td>
                            <td>${{cls.has_docstring ? '✓' : '✗'}}</td>
                        </tr>`;
                    }});
                    html += '</table>';
                    html += '</div>';
                }}
                
                // 导入信息
                if (structure.imports) {{
                    html += '<div class="metric">';
                    html += '<h4>导入分析</h4>';
                    const totalImports = (structure.imports.simple?.length || 0) + 
                                       (structure.imports.from_import?.length || 0);
                    html += `<p>共 ${{totalImports}} 个导入</p>`;
                    if (structure.imports.simple?.length > 0) {{
                        html += '<p><strong>直接导入:</strong> ' + structure.imports.simple.join(', ') + '</p>';
                    }}
                    if (structure.imports.from_import?.length > 0) {{
                        html += '<p><strong>从模块导入:</strong> ' + structure.imports.from_import.join(', ') + '</p>';
                    }}
                    html += '</div>';
                }}
                
                // 复杂度信息
                if (structure.complexity) {{
                    html += '<div class="metric">';
                    html += '<h4>复杂度分析</h4>';
                    html += `<p><strong>函数数量:</strong> ${{structure.complexity.function_count}}</p>`;
                    html += `<p><strong>类数量:</strong> ${{structure.complexity.class_count}}</p>`;
                    html += `<p><strong>平均函数长度:</strong> ${{structure.complexity.avg_function_length.toFixed(1)}} 语句</p>`;
                    html += `<p><strong>最大嵌套深度:</strong> ${{structure.complexity.max_nested_depth}}</p>`;
                    html += '</div>';
                }}
                
                // 问题
                if (structure.issues && structure.issues.length > 0) {{
                    html += '<div class="finding">';
                    html += '<h4>发现的问题</h4>';
                    structure.issues.forEach(issue => {{
                        html += `<p><strong>${{issue.severity === 'warning' ? '⚠️' : '❌'}} 第${{issue.lineno}}行:</strong> ${{issue.message}}</p>`;
                    }});
                    html += '</div>';
                }}
                
                html += '</div>';
                container.innerHTML = html;
            }}
            
            function displayDeepSeekResults(results) {{
                const container = document.getElementById('deepseekResults');
                let html = '<div class="html-preview">';
                
                html += '<div class="deepseek-section">';
                html += '<h3><i class="fas fa-robot"></i> DeepSeek AI分析结果</h3>';
                
                if (results.blackbox) {{
                    html += '<div class="deepseek-content">';
                    html += '<h4><i class="fas fa-chart-bar"></i> 黑盒性能分析</h4>';
                    // 将Markdown转换为HTML
                    html += results.blackbox.replace(/\\n/g, '<br>')
                                           .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')
                                           .replace(/\\*(.*?)\\*/g, '<em>$1</em>')
                                           .replace(/^### (.*)$/gm, '<h3>$1</h3>')
                                           .replace(/^## (.*)$/gm, '<h2>$1</h2>')
                                           .replace(/^# (.*)$/gm, '<h1>$1</h1>');
                    html += '</div>';
                }}
                
                if (results.whitebox) {{
                    html += '<div class="deepseek-content">';
                    html += '<h4><i class="fas fa-code"></i> 白盒代码分析</h4>';
                    // 将Markdown转换为HTML
                    html += results.whitebox.replace(/\\n/g, '<br>')
                                           .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')
                                           .replace(/\\*(.*?)\\*/g, '<em>$1</em>')
                                           .replace(/^### (.*)$/gm, '<h3>$1</h3>')
                                           .replace(/^## (.*)$/gm, '<h2>$1</h2>')
                                           .replace(/^# (.*)$/gm, '<h1>$1</h1>');
                    html += '</div>';
                }}
                
                if (!results.blackbox && !results.whitebox) {{
                    html += '<div class="deepseek-content">';
                    html += '<p>未启用DeepSeek分析或分析失败。请检查DeepSeek配置。</p>';
                    html += '</div>';
                }}
                
                html += '</div>';
                html += '</div>';
                container.innerHTML = html;
            }}
            
            function showTab(tabName) {{
                // 更新标签页
                document.querySelectorAll('.tab').forEach(tab => {{
                    tab.classList.remove('active');
                }});
                document.querySelectorAll('.tab-content').forEach(content => {{
                    content.classList.remove('active');
                }});
                
                // 激活选中的标签页
                event.target.classList.add('active');
                document.getElementById(tabName + 'Tab').classList.add('active');
            }}
            
            function downloadReport(format) {{
                if (!currentAnalysisId || !currentReport) {{
                    showNotification('没有可下载的报告', 'warning');
                    return;
                }}
                
                let url, filename;
                
                switch(format) {{
                    case 'html':
                        const htmlBlob = new Blob([currentReport.html], {{ type: 'text/html' }});
                        url = URL.createObjectURL(htmlBlob);
                        filename = 'autoprofiler_report.html';
                        break;
                    case 'markdown':
                        const mdBlob = new Blob([currentReport.markdown], {{ type: 'text/markdown' }});
                        url = URL.createObjectURL(mdBlob);
                        filename = 'autoprofiler_report.md';
                        break;
                    case 'pdf':
                        if (!currentReport.pdf_path) {{
                            showNotification('PDF生成失败或不可用', 'warning');
                            return;
                        }}
                        url = `/api/download/pdf/${{currentAnalysisId}}`;
                        filename = 'autoprofiler_report.pdf';
                        break;
                }}
                
                if (format !== 'pdf') {{
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                    showNotification(`${{format.toUpperCase()}}报告下载开始`, 'success');
                }} else {{
                    // PDF直接打开下载
                    window.open(url, '_blank');
                }}
            }}
            
            function copyToClipboard(format) {{
                if (!currentReport) {{
                    showNotification('没有可复制的内容', 'warning');
                    return;
                }}
                
                let textToCopy;
                if (format === 'html') {{
                    textToCopy = currentReport.html;
                }} else {{
                    textToCopy = currentReport.markdown;
                }}
                
                navigator.clipboard.writeText(textToCopy)
                    .then(() => showNotification('已复制到剪贴板', 'success'))
                    .catch(err => showNotification('复制失败: ' + err, 'error'));
            }}
            
            function resetAnalysis() {{
                currentAnalysisId = null;
                currentReport = null;
                document.getElementById('resultContainer').style.display = 'none';
                document.getElementById('progress').style.display = 'none';
                fileInput.value = '';
                
                // 重置预览
                document.getElementById('htmlPreview').innerHTML = '';
                document.getElementById('markdownContent').textContent = '';
                document.getElementById('codeStructure').innerHTML = '';
                document.getElementById('deepseekResults').innerHTML = '';
                document.getElementById('rawData').textContent = '';
                document.getElementById('statsContainer').innerHTML = '';
                
                resetProgress();
                
                if (progressInterval) {{
                    clearInterval(progressInterval);
                    progressInterval = null;
                }}
            }}
            
            function updateProgress(percent, text) {{
                const progressBar = document.getElementById('progressBar');
                const progressText = document.getElementById('progressText');
                
                // 平滑动画
                const start = lastProgress;
                const end = percent;
                const duration = 500; // 动画持续时间
                const startTime = performance.now();
                
                function animate(currentTime) {{
                    const elapsed = currentTime - startTime;
                    const progress = Math.min(elapsed / duration, 1);
                    const currentPercent = start + (end - start) * progress;
                    
                    progressBar.style.width = currentPercent + '%';
                    progressBar.textContent = Math.round(currentPercent) + '%';
                    progressText.textContent = Math.round(currentPercent) + '% - ' + text;
                    
                    if (progress < 1) {{
                        requestAnimationFrame(animate);
                    }} else {{
                        lastProgress = end;
                    }}
                }}
                
                requestAnimationFrame(animate);
            }}
            
            function resetProgress() {{
                lastProgress = 0;
                const progressBar = document.getElementById('progressBar');
                const progressText = document.getElementById('progressText');
                const steps = document.querySelectorAll('.progress-step');
                
                progressBar.style.width = '0%';
                progressBar.textContent = '';
                progressText.textContent = '0% - 准备开始分析...';
                
                steps.forEach(step => {{
                    step.classList.remove('active', 'completed');
                }});
                steps[0].classList.add('active');
            }}
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
        
        # 获取DeepSeek配置
        deepseek_config = request.form.get('deepseek_config')
        if deepseek_config:
            try:
                deepseek_config = json.loads(deepseek_config)
            except:
                deepseek_config = DeepSeekConfig.load()
        else:
            deepseek_config = DeepSeekConfig.load()
        
        analysis_id = analysis_manager.create_analysis(file_path, filename, deepseek_config)
        
        # 启动分析线程
        import threading
        thread = threading.Thread(
            target=analyze_python_file,
            args=(file_path, analysis_id, deepseek_config),
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

@app.route('/api/deepseek/config', methods=['POST'])
def save_deepseek_config():
    """保存DeepSeek配置"""
    try:
        config = request.get_json()
        DeepSeekConfig.save(config)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/deepseek/clear', methods=['POST'])
def clear_deepseek_config():
    """清除DeepSeek配置"""
    try:
        if DEEPSEEK_CONFIG_FILE.exists():
            DEEPSEEK_CONFIG_FILE.unlink()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/deepseek/test', methods=['POST'])
def test_deepseek_connection():
    """测试DeepSeek连接"""
    try:
        config = request.get_json()
        api_key = config.get('api_key')
        api_url = config.get('api_url', 'https://api.deepseek.com/v1/chat/completions')
        
        if not api_key:
            return jsonify({"success": False, "error": "API密钥不能为空"})
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        data = {
            'model': 'deepseek-chat',
            'messages': [
                {
                    'role': 'system',
                    'content': '测试连接'
                },
                {
                    'role': 'user',
                    'content': 'Hello'
                }
            ],
            'max_tokens': 5
        }
        
        response = requests.post(api_url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            return jsonify({"success": True})
        else:
            return jsonify({
                "success": False, 
                "error": f"API返回错误: {response.status_code} - {response.text[:100]}"
            })
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

def main():
    """主函数"""
    print("\n" + "="*70)
    print("🚀 AutoProfiler Web 界面增强版 (支持DeepSeek AI分析)")
    print("="*70)
    print("✨ 功能特性:")
    print("  ✓ HTML格式报告预览 (增强样式)")
    print("  ✓ DeepSeek AI黑盒性能分析")
    print("  ✓ DeepSeek AI白盒代码分析")
    print("  ✓ 实时进度显示 (步骤跟踪)")
    print("  ✓ 代码结构分析 (AST解析)")
    print("  ✓ PDF报告导出")
    print("  ✓ 多格式下载支持")
    print("="*70)
    
    # 检查DeepSeek配置
    deepseek_config = DeepSeekConfig.load()
    if deepseek_config['api_key']:
        print(f"🔑 DeepSeek: 已配置 (模型: {deepseek_config['model']})")
    else:
        print("⚠️  DeepSeek: 未配置 - 请在Web界面中配置API密钥")
    
    print(f"🌐 访问地址: http://127.0.0.1:5000")
    print("="*70)
    print("按 Ctrl+C 停止服务\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)

if __name__ == '__main__':
    main()