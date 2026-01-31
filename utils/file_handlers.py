"""
文件处理器
"""
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename

def save_uploaded_file(file, upload_folder: Path) -> tuple:
    """保存上传的文件"""
    filename = secure_filename(file.filename)
    file_extension = Path(filename).suffix
    unique_filename = f"{uuid.uuid4().hex}{file_extension}"
    file_path = Path(upload_folder) / unique_filename
    
    file.save(file_path)
    
    return str(file_path), filename

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