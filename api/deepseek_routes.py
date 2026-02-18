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


def register_deepseek_routes(app):
    """注册DeepSeek相关路由"""
    
    @app.route('/api/deepseek/config', methods=['GET'])
    def get_deepseek_config():
        """获取DeepSeek配置"""
        try:
            config = DeepSeekConfig.load()
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
            config = request.get_json() or {}
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
            config = DeepSeekConfig.normalize_config(request.get_json() or {})
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
