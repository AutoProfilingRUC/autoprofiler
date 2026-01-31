"""
格式转换器
"""
import re
from datetime import datetime
from pathlib import Path

def convert_markdown_to_html(markdown_text: str) -> str:
    """将Markdown转换为HTML（增强版）"""
    
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

def convert_markdown_to_pdf(markdown_text: str, filename: str, upload_folder: Path) -> str:
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
        pdf_path = Path(upload_folder) / pdf_filename
        
        HTML(string=full_html).write_pdf(pdf_path)
        
        return str(pdf_path)
        
    except ImportError:
        # 备用方案
        return None
    except Exception as e:
        print(f"PDF转换失败: {e}")
        return None