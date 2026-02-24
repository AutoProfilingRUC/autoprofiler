"""
DeepSeek相关API路由
"""
from flask import jsonify, request
import requests

from models.deepseek_config import DeepSeekConfig


def _resolve_chat_endpoint(api_url: str) -> str:
    base = (api_url or "").strip().rstrip("/")
    if not base:
        return "https://api.deepseek.com/v1/chat/completions"
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _mask_secret(value: str) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    if len(token) <= 4:
        return "*" * len(token)
    return "*" * (len(token) - 4) + token[-4:]


def _sanitize_config_for_response(config: dict) -> dict:
    cfg = DeepSeekConfig.normalize_config(config or {})
    api_key = str(cfg.get("api_key", "") or "")
    local_api_key = str(cfg.get("local_api_key", "") or "")
    cfg["api_key"] = ""
    cfg["local_api_key"] = ""
    cfg["api_key_configured"] = bool(api_key.strip())
    cfg["local_api_key_configured"] = bool(local_api_key.strip())
    cfg["api_key_masked"] = _mask_secret(api_key)
    cfg["local_api_key_masked"] = _mask_secret(local_api_key)
    return cfg


def _merge_secret_fields(existing: dict, incoming: dict) -> dict:
    prev = DeepSeekConfig.normalize_config(existing or {})
    merged = DeepSeekConfig.normalize_config({**prev, **(incoming or {})})

    if merged.get("clear_api_key"):
        merged["api_key"] = ""
    elif not str(merged.get("api_key", "")).strip() and str(prev.get("api_key", "")).strip():
        merged["api_key"] = prev.get("api_key", "")

    if merged.get("clear_local_api_key"):
        merged["local_api_key"] = ""
    elif not str(merged.get("local_api_key", "")).strip() and str(prev.get("local_api_key", "")).strip():
        merged["local_api_key"] = prev.get("local_api_key", "")

    merged.pop("clear_api_key", None)
    merged.pop("clear_local_api_key", None)
    return merged


def register_deepseek_routes(app):
    """注册DeepSeek相关路由"""
    
    @app.route('/api/deepseek/config', methods=['GET'])
    def get_deepseek_config():
        """获取DeepSeek配置"""
        try:
            config = _sanitize_config_for_response(DeepSeekConfig.load())
            return jsonify({
                "success": True, 
                "config": config
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/deepseek/config', methods=['POST'])
    def save_deepseek_config():
        """保存DeepSeek配置"""
        try:
            existing_config = DeepSeekConfig.load()
            config = _merge_secret_fields(existing_config, request.get_json() or {})
            DeepSeekConfig.save(config)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/deepseek/clear', methods=['POST'])
    def clear_deepseek_config():
        """清除DeepSeek配置"""
        try:
            DeepSeekConfig.clear()
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/deepseek/test', methods=['POST'])
    def test_deepseek_connection():
        """测试DeepSeek连接"""
        try:
            incoming = request.get_json() or {}
            existing_config = DeepSeekConfig.load()
            config = _merge_secret_fields(existing_config, incoming)
            runtime = DeepSeekConfig.resolve_runtime(config)
            if not runtime.get("enabled"):
                return jsonify(
                    {"success": False, "error": "未配置可用模型（远程API或本地模型）"}
                ), 400
            lang = runtime.get("output_language", "zh")
            system_text = "连接测试" if lang == "zh" else "Connection check"
            user_text = "你好" if lang == "zh" else "Hello"

            headers = {'Content-Type': 'application/json'}
            if runtime.get("api_key"):
                headers['Authorization'] = f'Bearer {runtime["api_key"]}'
            
            data = {
                'model': runtime.get("model", "deepseek-chat"),
                'messages': [
                    {
                        'role': 'system',
                        'content': system_text
                    },
                    {
                        'role': 'user',
                        'content': user_text
                    }
                ],
                'max_tokens': 5
            }
            
            response = requests.post(
                _resolve_chat_endpoint(runtime.get("api_url")),
                headers=headers,
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                return jsonify({"success": True})
            else:
                return jsonify({
                    "success": False, 
                    "error": f"API返回错误: {response.status_code} - {response.text[:100]}"
                }), 400
                
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
