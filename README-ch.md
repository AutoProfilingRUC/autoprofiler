# AutoProfiler (Python 自动性能分析工具)

## 1. 项目概述

AutoProfiler 是一个用 **Python** 实现的**自动性能分析和诊断工具**。

本项目的核心目标是：

> 给定一个**未知的目标程序**（通常是Python程序，但不仅限于项目结构），自动收集性能数据，分析性能模式，并生成**基于证据的性能诊断和优化建议**。

现在，AutoProfiler 还提供了**Web界面**，用户可以通过浏览器上传和分析Python文件，无需本地命令行操作。

## 2. 新功能：Web界面

AutoProfiler 现在提供了一个完整的Web界面，支持：

- ✅ **拖放上传**：将Python文件拖放到浏览器中即可分析
- ✅ **多种上传方式**：本地文件、URL链接、直接输入代码
- ✅ **实时进度显示**：分析进度条和状态更新
- ✅ **完整报告**：详细的性能分析报告
- ✅ **结果导出**：下载Markdown格式报告

## 3. 快速开始

### 方式一：Web界面（推荐）

1. **安装依赖**：
   ```bash
   pip install flask flask-cors werkzeug psutil PyYAML
   ```

2. **启动Web服务**：
   ```bash
   python web_app.py
   ```

3. **打开浏览器**：
   访问 http://127.0.0.1:5000

4. **上传Python文件**：
   - 拖放文件到网页区域
   - 或点击"选择文件"按钮
   - 或从URL上传Python文件

### 方式二：命令行工具

1. **安装核心依赖**：
   ```bash
   pip install psutil PyYAML
   ```

2. **分析单个Python文件**：
   ```bash
   # 使用内置测试
   python -m unittest tests.test_autoprofiler_template
   
   # 或设置环境变量指向你的文件
   export AUTOPROFILER_TARGET="python your_script.py"
   python -m unittest tests.test_autoprofiler_template
   ```

3. **使用Python API**：
   ```python
   from autoprofiler.runner import Runner
   from autoprofiler.models import TargetProgram
   from autoprofiler.collectors.psutil_collector import PsutilCollector
   
   target = TargetProgram(command=["python", "your_script.py"])
   collector = PsutilCollector(sample_interval=0.1)
   session = Runner().run(target, collectors=[collector])
   ```

## 4. 系统要求

- **Python版本**：≥ 3.8
- **操作系统**：Windows / Linux / macOS
- **内存**：≥ 512MB
- **磁盘空间**：≥ 100MB

## 5. 安装详细步骤

### 完整安装（包含Web界面）

```bash
# 克隆或下载项目
git clone <repository-url>
cd autoprofiler

# 创建虚拟环境（可选）
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows

# 安装所有依赖
pip install psutil PyYAML flask flask-cors werkzeug
```

### 最小安装（仅核心功能）

```bash
# 仅安装核心依赖
pip install psutil PyYAML
```

## 6. 使用示例

### Web界面使用示例

1. **访问Web界面**：http://127.0.0.1:5000
2. **上传示例文件**：
   ```python
   # 创建测试文件 test_performance.py
   import time
   
   def slow_function():
       result = 0
       for i in range(1000000):
           result += i * i
       return result
   
   if __name__ == "__main__":
       start = time.time()
       result = slow_function()
       print(f"结果: {result}, 耗时: {time.time()-start:.2f}秒")
   ```
3. **查看分析结果**：
   - CPU使用率
   - 内存消耗
   - 函数调用分析
   - 性能优化建议

### 命令行示例

```bash
# 创建测试文件
echo "import time; time.sleep(2); print('Done')" > test.py

# 使用AutoProfiler分析
export AUTOPROFILER_TARGET="python test.py"
python -m unittest tests.test_autoprofiler_template
```

## 7. 核心功能

### 性能分析功能

- **CPU分析**：使用psutil监控CPU使用率
- **内存分析**：监控内存使用和增长
- **函数分析**：使用cProfile分析函数调用
- **模式匹配**：基于规则检测性能问题

### 收集器

- **PsutilCollector**：系统级资源监控
- **CProfileCollector**：Python函数级分析
- **PySpyCollector**：采样分析（需要额外安装py-spy）

### 输出格式

- **Markdown报告**：详细的人类可读报告
- **JSON数据**：结构化的机器可读数据
- **HTML报告**：Web界面的格式化报告

## 8. 高级用法

### 自定义分析配置

```python
from autoprofiler.runner import Runner
from autoprofiler.models import TargetProgram
from autoprofiler.collectors import PsutilCollector, CProfileCollector

# 配置目标程序
target = TargetProgram(
    command=["python", "app.py", "--arg", "value"],
    timeout=60,  # 60秒超时
    cwd="/path/to/project",  # 工作目录
    env={"PYTHONPATH": "/custom/path"}  # 环境变量
)

# 配置收集器
collectors = [
    PsutilCollector(sample_interval=0.05),  # 每50ms采样
    CProfileCollector(sort_by="cumulative"),  # 按累积时间排序
]

# 运行分析
runner = Runner()
session = runner.run(target, collectors=collectors)
```

### 批量分析

```python
# 批量分析多个文件
import concurrent.futures
from pathlib import Path

def analyze_file(file_path):
    target = TargetProgram(command=["python", str(file_path)])
    collector = PsutilCollector(sample_interval=0.1)
    session = Runner().run(target, collectors=[collector])
    return file_path.name, session.duration

# 并行分析
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    py_files = list(Path(".").glob("*.py"))
    results = executor.map(analyze_file, py_files)
```

## 9. 故障排除

### 常见问题

1. **导入错误**：
   ```bash
   # 确保安装了所有依赖
   pip install psutil PyYAML
   ```

2. **Web界面无法启动**：
   ```bash
   # 检查Flask是否安装
   pip install flask flask-cors werkzeug
   
   # 检查端口是否被占用
   python web_app.py --port=8080
   ```

3. **文件上传失败**：
   - 检查文件大小（最大50MB）
   - 检查文件格式（支持.py, .pyw）
   - 检查磁盘空间

### 调试模式

```bash
# 启用调试输出
DEBUG=1 python web_app.py

# 查看详细日志
python web_app.py --debug
```

## 10. API参考

### Web API端点

- `GET /` - Web界面首页
- `GET /api/health` - 健康检查
- `POST /api/upload` - 文件上传
- `GET /api/analysis/<id>` - 获取分析状态
- `GET /api/analysis/<id>/report` - 下载分析报告

### Python API

```python
# 主要类
from autoprofiler.runner import Runner
from autoprofiler.models import TargetProgram
from autoprofiler.collectors.psutil_collector import PsutilCollector

# 创建分析会话
target = TargetProgram(command=["python", "script.py"])
collector = PsutilCollector(sample_interval=0.1)
session = Runner().run(target, collectors=[collector])
```

## 11. 贡献指南

### 开发环境设置

```bash
# 克隆项目
git clone <repository-url>
cd autoprofiler

# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
python -m pytest tests/

# 代码格式化
black autoprofiler/
isort autoprofiler/
```

### 提交代码

1. 创建功能分支
2. 编写测试用例
3. 提交Pull Request
4. 通过CI检查

## 12. 许可证

本项目采用MIT许可证。详见LICENSE文件。

## 13. 联系与支持

- **问题反馈**：创建GitHub Issue
- **功能请求**：提交Feature Request
- **贡献代码**：提交Pull Request

## 14. 更新日志

### v1.0.0 (2024-01-01)
- 初始版本发布
- 核心分析功能
- Web界面支持
- 基本性能模式

## 15. 致谢

感谢以下开源项目的贡献：
- psutil：系统资源监控
- Flask：Web框架
- PyYAML：配置解析
- 以及所有贡献者

---

## 快速参考

### 一句话使用
```bash
# 启动Web界面
python web_app.py

# 然后在浏览器打开 http://127.0.0.1:5000
```

### 一句话分析
```bash
# 命令行分析Python文件
export AUTOPROFILER_TARGET="python your_file.py"
python -m unittest tests.test_autoprofiler_template
```

### 一句话安装
```bash
# 完整安装（包含Web界面）
pip install psutil PyYAML flask flask-cors werkzeug
```

---

**开始分析您的Python代码性能吧！**