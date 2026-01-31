"""
DeepSeek相关API路由
"""
from flask import jsonify, request
import requests

from models.deepseek_config import DeepSeekConfig

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
            config = request.get_json()
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
            config = request.get_json()
            api_key = config.get('api_key')
            api_url = config.get('api_url', 'https://api.deepseek.com/v1/chat/completions')
            
            if not api_key:
                return jsonify({"success": False, "error": "API密钥不能为空"}), 400
            
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
                }), 400
                
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500