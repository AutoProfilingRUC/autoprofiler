"""
DeepSeek配置模型
"""
import json
from pathlib import Path

class DeepSeekConfig:
    """DeepSeek API配置管理器"""
    
    @staticmethod
    def load(config_file: Path = None):
        """加载配置"""
        if config_file is None:
            from config import Config
            config_file = Config.DEEPSEEK_CONFIG_FILE
        
        default_config = {
            'api_key': '',
            'api_url': 'https://api.deepseek.com/v1/chat/completions',
            'model': 'deepseek-chat',
            'enable_blackbox': True,
            'enable_whitebox': True,
            'temperature': 0.3,
            'max_tokens': 2000
        }
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except:
                pass
        
        return default_config
    
    @staticmethod
    def save(config: dict, config_file: Path = None):
        """保存配置"""
        if config_file is None:
            from config import Config
            config_file = Config.DEEPSEEK_CONFIG_FILE
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def clear(config_file: Path = None):
        """清除配置"""
        if config_file is None:
            from config import Config
            config_file = Config.DEEPSEEK_CONFIG_FILE
        
        if config_file.exists():
            config_file.unlink()