#!/usr/bin/env python3
"""
AutoProfiler Web界面增强版 - 主应用入口
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from flask import Flask
from flask_cors import CORS
import os

from config import Config
from api.routes import register_routes
from api.deepseek_routes import register_deepseek_routes
from api.proj_analyser_routes import register_proj_analyser_routes

def create_app(config_class=Config):
    """创建Flask应用"""
    app = Flask(__name__, 
                static_folder='static',
                template_folder='templates')
    
    # 加载配置
    app.config.from_object(config_class)
    
    # 启用CORS
    CORS(app)
    
    # 确保上传目录存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # 注册蓝图/路由
    register_routes(app)
    register_deepseek_routes(app)
    register_proj_analyser_routes(app)
    
    return app

if __name__ == '__main__':
    app = create_app()
    
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
    print(f"🌐 访问地址: http://127.0.0.1:{app.config.get('PORT', 5000)}")
    print("="*70)
    print("按 Ctrl+C 停止服务\n")
    
    app.run(
        host=app.config.get('HOST', '0.0.0.0'),
        port=app.config.get('PORT', 5000),
        debug=app.config.get('DEBUG', True)
    )
