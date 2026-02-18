"""
DeepSeek配置模型
"""
import json
from pathlib import Path


class DeepSeekConfig:
    """DeepSeek API配置管理器"""

    @staticmethod
    def default_config():
        return {
            'api_key': '',
            'api_url': 'https://api.deepseek.com/v1/chat/completions',
            'model': 'deepseek-chat',
            'enable_blackbox': True,
            'enable_whitebox': True,
            'output_language': 'zh',
            'temperature': 0.3,
            'max_tokens': 2000,
            # Local model (OpenAI-compatible endpoint) options
            'use_local_model': False,
            'local_api_url': 'http://127.0.0.1:11434/v1/chat/completions',
            'local_model': '',
            'local_api_key': ''
        }

    @staticmethod
    def normalize_output_language(value: str) -> str:
        """标准化输出语言，仅允许 zh/en"""
        lang = str(value or "").strip().lower()
        if lang in ("en", "english"):
            return "en"
        if lang in ("zh", "zh-cn", "cn", "chinese"):
            return "zh"
        return "zh"

    @staticmethod
    def normalize_config(config: dict) -> dict:
        cfg = DeepSeekConfig.default_config()
        cfg.update(config or {})
        cfg["output_language"] = DeepSeekConfig.normalize_output_language(
            cfg.get("output_language")
        )
        return cfg
    
    @staticmethod
    def load(config_file: Path = None):
        """加载配置"""
        if config_file is None:
            from config import Config
            config_file = Config.DEEPSEEK_CONFIG_FILE
        
        merged = DeepSeekConfig.default_config()
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    merged.update(user_config)
            except:
                pass
        
        return DeepSeekConfig.normalize_config(merged)

    @staticmethod
    def has_remote_api(config: dict) -> bool:
        cfg = DeepSeekConfig.default_config()
        cfg.update(config or {})
        return bool(cfg.get('api_key') and cfg.get('api_url') and cfg.get('model'))

    @staticmethod
    def has_local_model(config: dict) -> bool:
        cfg = DeepSeekConfig.default_config()
        cfg.update(config or {})
        return bool(
            cfg.get('use_local_model')
            and cfg.get('local_api_url')
            and cfg.get('local_model')
        )

    @staticmethod
    def has_any_model(config: dict) -> bool:
        return DeepSeekConfig.has_remote_api(config) or DeepSeekConfig.has_local_model(config)

    @staticmethod
    def resolve_runtime(config: dict) -> dict:
        """
        Resolve runtime endpoint/model with priority:
        1) local model (if enabled and configured)
        2) remote API config
        """
        cfg = DeepSeekConfig.normalize_config(config)
        output_language = cfg.get("output_language", "zh")

        if DeepSeekConfig.has_local_model(cfg):
            return {
                "enabled": True,
                "mode": "local",
                "api_url": cfg.get("local_api_url"),
                "model": cfg.get("local_model"),
                "api_key": cfg.get("local_api_key", ""),
                "output_language": output_language,
            }

        if DeepSeekConfig.has_remote_api(cfg):
            return {
                "enabled": True,
                "mode": "remote",
                "api_url": cfg.get("api_url"),
                "model": cfg.get("model"),
                "api_key": cfg.get("api_key", ""),
                "output_language": output_language,
            }

        return {
            "enabled": False,
            "mode": "none",
            "api_url": "",
            "model": "",
            "api_key": "",
            "output_language": output_language,
        }
    
    @staticmethod
    def save(config: dict, config_file: Path = None):
        """保存配置"""
        if config_file is None:
            from config import Config
            config_file = Config.DEEPSEEK_CONFIG_FILE

        merged = DeepSeekConfig.normalize_config(config)
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def clear(config_file: Path = None):
        """清除配置"""
        if config_file is None:
            from config import Config
            config_file = Config.DEEPSEEK_CONFIG_FILE
        
        if config_file.exists():
            config_file.unlink()
