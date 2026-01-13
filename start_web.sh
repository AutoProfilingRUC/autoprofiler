#!/bin/bash
# AutoProfiler Web界面启动脚本

echo "启动 AutoProfiler Web界面..."
echo ""

# 检查Python环境
python_cmd="python3"
if ! command -v python3 &> /dev/null; then
    python_cmd="python"
    if ! command -v python &> /dev/null; then
        echo "错误: 未找到Python，请安装Python 3.8或更高版本"
        exit 1
    fi
fi

# 检查Python版本
python_version=$($python_cmd -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ $python_version < "3.8" ]]; then
    echo "警告: 建议使用 Python 3.8 或更高版本 (当前: $python_version)"
fi

# 检查依赖
echo "检查依赖..."
if ! $python_cmd -c "import flask" 2>/dev/null; then
    echo "安装Flask和相关依赖..."
    $python_cmd -m pip install flask flask-cors werkzeug psutil PyYAML
fi

# 检查AutoProfiler核心模块
echo "检查AutoProfiler核心模块..."
if [ ! -d "autoprofiler" ]; then
    echo "错误: 未找到autoprofiler目录，请在项目根目录运行此脚本"
    exit 1
fi

# 创建必要的目录
mkdir -p static/css static/js static/images templates

# 运行Web应用
echo "启动Web服务器..."
echo "访问地址: http://127.0.0.1:5000"
echo "按 Ctrl+C 停止服务"
echo ""

$python_cmd web_app.py