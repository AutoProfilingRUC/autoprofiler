"""
配置文件
"""
import os
from pathlib import Path

class Config:
    """基础配置类"""
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'autoprofiler-enhanced-deepseek'
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    JSON_AS_ASCII = False
    PERMANENT_SESSION_LIFETIME = 3600  # 1小时
    
    # 路径配置
    BASE_DIR = Path(__file__).parent
    UPLOAD_FOLDER = BASE_DIR / 'uploads'
    STATIC_FOLDER = BASE_DIR / 'static'
    TEMPLATE_FOLDER = BASE_DIR / 'templates'
    
    # DeepSeek配置
    DEEPSEEK_CONFIG_FILE = UPLOAD_FOLDER / 'deepseek_config.json'
    
    # 服务器配置
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5000))
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    @classmethod
    def init_app(cls):
        """初始化应用"""
        # 确保目录存在
        cls.UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        cls.STATIC_FOLDER.mkdir(parents=True, exist_ok=True)
        cls.TEMPLATE_FOLDER.mkdir(parents=True, exist_ok=True)