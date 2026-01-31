"""
辅助函数
"""

def simplify_obj(obj):
    """将复杂的对象转换为简单格式用于JSON序列化"""
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    elif isinstance(obj, dict):
        return {k: simplify_obj(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [simplify_obj(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        return simplify_obj(obj.__dict__)
    else:
        return str(obj)


def safe_get_artifact_type(artifact):
    """安全获取artifact的类型"""
    try:
        # 尝试多种方式获取类型
        if hasattr(artifact, 'type'):
            return artifact.type
        elif hasattr(artifact, '__dict__'):
            return getattr(artifact, 'type', type(artifact).__name__)
        elif isinstance(artifact, dict):
            return artifact.get('type', 'unknown')
        else:
            return type(artifact).__name__
    except:
        return 'unknown'