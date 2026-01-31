"""
DeepSeek分析器
"""
import json
import requests
from typing import Optional, Callable

class DeepSeekAnalyzer:
    """DeepSeek API分析器"""
    
    @staticmethod
    def analyze_with_deepseek(config: dict, analysis_type: str, content: dict, 
                             progress_callback: Optional[Callable] = None) -> Optional[str]:
        """使用DeepSeek API进行分析"""
        if not config.get('api_key'):
            return None
        
        # 准备提示词
        if analysis_type == 'blackbox':
            prompt = DeepSeekAnalyzer._create_blackbox_prompt(content)
        elif analysis_type == 'whitebox':
            prompt = DeepSeekAnalyzer._create_whitebox_prompt(content)
        else:
            return None
        
        # 调用API
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {config["api_key"]}'
            }
            
            data = {
                'model': config.get('model', 'deepseek-chat'),
                'messages': [
                    {
                        'role': 'system',
                        'content': '你是一个专业的Python性能分析专家，请分析提供的性能数据或代码，给出具体的优化建议。'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'temperature': config.get('temperature', 0.3),
                'max_tokens': config.get('max_tokens', 2000),
                'stream': False
            }
            
            if progress_callback:
                progress_callback(f'正在调用DeepSeek API进行{analysis_type}分析...')
            
            response = requests.post(
                config.get('api_url', 'https://api.deepseek.com/v1/chat/completions'),
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('choices', [{}])[0].get('message', {}).get('content', '')
            else:
                return f"API调用失败: {response.status_code} - {response.text}"
                
        except Exception as e:
            return f"DeepSeek分析失败: {str(e)}"
    
    @staticmethod
    def _create_blackbox_prompt(performance_data: dict) -> str:
        """创建黑盒分析提示词"""
        prompt = f"""请分析以下Python程序的性能数据，找出性能瓶颈并提供具体的优化建议：

性能数据：
{json.dumps(performance_data, indent=2, ensure_ascii=False)}

请按照以下格式提供分析结果：

## DeepSeek AI 黑盒分析报告

### 性能瓶颈分析
1. **主要瓶颈**：（指出最严重的性能问题）
2. **问题原因**：（分析问题产生的原因）

### 优化建议
1. **短期优化**：（立即可以实施的改进）
2. **长期优化**：（需要重构的改进）
3. **架构建议**：（系统架构层面的建议）

### 预期收益
- 性能提升预估：
- 资源消耗降低：
- 代码可维护性提升：

请用中文回复，建议要具体、可操作。"""
        
        return prompt
    
    @staticmethod
    def _create_whitebox_prompt(code_structure: dict) -> str:
        """创建白盒分析提示词"""
        prompt = f"""请分析以下Python代码的结构，找出潜在的问题并提供具体的优化建议：

代码结构分析结果：
{json.dumps(code_structure, indent=2, ensure_ascii=False)}

请按照以下格式提供分析结果：

## DeepSeek AI 白盒分析报告

### 代码结构评估
1. **代码质量评分**：（1-10分）
2. **主要优点**：
3. **主要问题**：

### 具体改进建议
1. **架构优化**：
2. **函数重构**：
3. **类设计改进**：
4. **异常处理优化**：
5. **代码规范问题**：

### 性能优化建议
1. **算法优化**：
2. **内存使用优化**：
3. **I/O优化**：

### 安全与可维护性
1. **安全问题**：
2. **可维护性建议**：
3. **测试建议**：

请用中文回复，建议要具体、可操作。"""
        
        return prompt