"""
分析任务 - 核心分析流程
"""
import traceback
from pathlib import Path
import json

from analysis.manager import analysis_manager
from analysis.code_analyzer import CodeAnalyzer
from analysis.deepseek_analyzer import DeepSeekAnalyzer
from utils.converters import convert_markdown_to_html, convert_markdown_to_pdf
from utils.helpers import safe_get_artifact_type, simplify_obj

def analyze_python_file(file_path, analysis_id, deepseek_config, upload_folder):
    """分析Python文件（包含DeepSeek分析）"""
    try:
        analysis_manager.update_status(
            analysis_id, 
            'analyzing', 
            progress=10,
            progress_text='正在导入分析模块...'
        )
        
        # 导入AutoProfiler核心模块
        try:
            from autoprofiler.runner import Runner
            from autoprofiler.models import TargetProgram
            from autoprofiler.collectors.psutil_collector import PsutilCollector
            from autoprofiler.collectors.cprofile_collector import CProfileCollector
            from autoprofiler.patterns.loader import load_patterns
            from autoprofiler.analyzers.simple_analyzer import PatternMatchingAnalyzer
            from autoprofiler.reporting.reporter import render_markdown
            autoprofiler_available = True
        except ImportError as e:
            analysis_manager.update_status(
                analysis_id,
                'failed',
                error=f"AutoProfiler模块导入失败: {str(e)}",
                progress_text='缺少AutoProfiler核心模块'
            )
            return
        
        analysis_manager.update_status(
            analysis_id,
            'analyzing',
            progress=20,
            progress_text='正在运行性能分析...'
        )
        
        # 运行性能分析
        file_path_obj = Path(file_path)
        target = TargetProgram(
            command=["python", str(file_path_obj)],
            timeout=60,
            cwd=str(file_path_obj.parent)
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
            patterns_file = Path(__file__).parent.parent / "autoprofiler" / "patterns" / "performance.yaml"
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
        
        # 转换为HTML
        html_report = convert_markdown_to_html(markdown_report)
        
        # 生成PDF
        pdf_path = None
        try:
            pdf_path = convert_markdown_to_pdf(markdown_report, Path(file_path).stem, upload_folder)
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