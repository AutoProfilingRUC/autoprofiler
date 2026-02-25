"""
格式转换器
"""
import html as html_lib
import re
from datetime import datetime
from pathlib import Path

from utils.runtime_capabilities import configure_windows_gtk_runtime, get_runtime_capabilities


def _normalize_markdown_input(markdown_text: str) -> str:
    text = str(markdown_text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Some model outputs place fenced code inside list items with indentation.
    # Normalize fence markers to left margin so both parsers can recognize them.
    text = re.sub(r"(?m)^[ \t]+(```[a-zA-Z0-9_+\-]*[ \t]*)$", r"\1", text)
    text = re.sub(r"(?m)^[ \t]+(```[ \t]*)$", r"\1", text)
    return text


def _format_inline_markdown(text: str) -> str:
    raw = str(text or "")
    inline_code_tokens = {}

    def _store_inline_code(match):
        key = f"__INLINE_CODE_{len(inline_code_tokens)}__"
        inline_code_tokens[key] = f"<code>{html_lib.escape(match.group(1))}</code>"
        return key

    raw = re.sub(r"`([^`]+)`", _store_inline_code, raw)
    escaped = html_lib.escape(raw)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", escaped)
    escaped = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{html_lib.escape(m.group(2), quote=True)}">{m.group(1)}</a>',
        escaped,
    )
    for key, value in inline_code_tokens.items():
        escaped = escaped.replace(key, value)
    return escaped


def _convert_markdown_fallback(markdown_text: str) -> str:
    text = _normalize_markdown_input(markdown_text)
    code_blocks = {}

    def _store_code_block(match):
        lang = (match.group(1) or "").strip().lower()
        code = (match.group(2) or "").strip("\n")
        safe_code = html_lib.escape(code)
        if lang:
            html = f'<pre class="language-{lang}"><code>{safe_code}</code></pre>'
        else:
            html = f"<pre><code>{safe_code}</code></pre>"
        key = f"__CODE_BLOCK_{len(code_blocks)}__"
        code_blocks[key] = html
        return key

    # Support fenced code blocks with optional leading indentation.
    text = re.sub(
        r"(?ms)^[ \t]*```([a-zA-Z0-9_+\-]*)[ \t]*\n(.*?)^[ \t]*```[ \t]*$",
        _store_code_block,
        text,
    )
    lines = text.splitlines()
    out_lines = []
    paragraph_lines = []
    list_mode = None

    def flush_paragraph():
        nonlocal paragraph_lines
        if not paragraph_lines:
            return
        content = " ".join(s.strip() for s in paragraph_lines if s.strip())
        if content:
            out_lines.append(f"<p>{_format_inline_markdown(content)}</p>")
        paragraph_lines = []

    def close_list():
        nonlocal list_mode
        if list_mode == "ul":
            out_lines.append("</ul>")
        elif list_mode == "ol":
            out_lines.append("</ol>")
        list_mode = None

    for line in lines:
        stripped = line.strip()
        stripped_left = line.lstrip()

        if stripped in code_blocks:
            flush_paragraph()
            close_list()
            out_lines.append(code_blocks[stripped])
            continue

        if not stripped:
            flush_paragraph()
            close_list()
            continue

        heading = re.match(r"^(#{1,4})\s+(.+)$", stripped_left)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            content = _format_inline_markdown(heading.group(2))
            out_lines.append(f"<h{level}>{content}</h{level}>")
            continue

        if re.match(r"^---\s*$", stripped):
            flush_paragraph()
            close_list()
            out_lines.append("<hr>")
            continue

        ul_item = re.match(r"^-\s+(.+)$", stripped_left)
        if ul_item:
            flush_paragraph()
            if list_mode != "ul":
                close_list()
                out_lines.append("<ul>")
                list_mode = "ul"
            out_lines.append(f"<li>{_format_inline_markdown(ul_item.group(1))}</li>")
            continue

        ol_item = re.match(r"^\d+\.\s+(.+)$", stripped_left)
        if ol_item:
            flush_paragraph()
            if list_mode != "ol":
                close_list()
                out_lines.append("<ol>")
                list_mode = "ol"
            out_lines.append(f"<li>{_format_inline_markdown(ol_item.group(1))}</li>")
            continue

        close_list()
        paragraph_lines.append(stripped_left)

    flush_paragraph()
    close_list()
    return "\n".join(out_lines)


def convert_markdown_to_html(markdown_text: str) -> str:
    """将Markdown转换为HTML（增强版）"""
    normalized_text = _normalize_markdown_input(markdown_text)
    html = ""
    try:
        import markdown as markdown_lib

        html = markdown_lib.markdown(
            normalized_text,
            extensions=["extra", "fenced_code", "tables", "sane_lists", "nl2br"],
        )
        # Python-Markdown can leave fenced code untouched in some nested/list cases.
        # If raw fences remain, fallback parser provides a safer rendering result.
        if "```" in html:
            html = _convert_markdown_fallback(normalized_text)
    except Exception:
        # Fallback parser for environments without markdown package.
        html = _convert_markdown_fallback(normalized_text)
    
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
        capabilities = get_runtime_capabilities()
        pdf_feature = (capabilities.get("features") or {}).get("pdf_export", {})
        if not isinstance(pdf_feature, dict) or "available" not in pdf_feature:
            capabilities = get_runtime_capabilities(refresh=True)
            pdf_feature = (capabilities.get("features") or {}).get("pdf_export", {})
        if not pdf_feature.get("available"):
            reason = pdf_feature.get("reason") or "环境未检测到 PDF 导出能力"
            print(f"PDF转换不可用，环境能力检查未通过: {reason}")
            return None

        configure_windows_gtk_runtime()
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
        
    except (ImportError, OSError) as e:
        print(f"PDF转换不可用，缺少依赖或系统库: {e}")
        return None
    except Exception as e:
        print(f"PDF转换失败: {e}")
        return None
