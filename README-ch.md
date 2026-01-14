# AutoProfiler (Python 自动性能分析工具)

## 1. 项目概述

AutoProfiler 是一个用 **Python** 实现的**自动性能分析和诊断工具**，支持**Web界面**和**命令行**两种使用方式。

核心目标：
> 自动收集Python代码的性能数据，分析性能瓶颈，生成**格式化的性能诊断报告**（支持HTML、PDF、Markdown多种格式）。

## 2. 主要特性

### ✅ 多格式报告输出
- **HTML预览**：在浏览器中查看格式化的报告（标题、代码块、列表等）
- **PDF导出**：生成可打印的PDF格式报告
- **Markdown导出**：原始Markdown格式报告
- **实时渲染**：使用marked.js或服务器端转换，实时预览格式化报告

### ✅ 多种使用方式
- **Web界面**：拖放上传，可视化分析（推荐）
- **命令行**：通过环境变量或API调用
- **Python API**：集成到自己的项目中

### ✅ 完整的分析功能
- CPU使用率分析
- 内存消耗监控
- 函数调用统计
- 性能模式匹配
- 智能优化建议

## 3. 快速开始

### 方式一：Web界面（推荐，用户友好）

```bash
# 1. 安装依赖
pip install flask flask-cors werkzeug psutil PyYAML markdown weasyprint

# 2. 启动Web服务
python web_app_enhanced.py

# 3. 打开浏览器访问
# http://127.0.0.1:5000
```

**Web界面功能**：
- 拖放上传Python文件
- 实时进度显示
- HTML格式报告预览
- 多格式下载（HTML/PDF/Markdown）
- 响应式设计，支持移动设备

### 方式二：命令行工具（适合开发人员）

```bash
# 安装核心依赖
pip install psutil PyYAML

# 分析Python文件
export AUTOPROFILER_TARGET="python your_script.py"
python -m unittest tests.test_autoprofiler_template
```

### 方式三：Python API（适合集成）

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
- **内存**：≥ 512MB（建议1GB）
- **磁盘空间**：≥ 100MB

## 5. 安装指南

### 完整安装（包含Web界面和PDF导出）

```bash
# 克隆项目
git clone <repository-url>
cd autoprofiler

# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows

# 安装完整依赖
pip install psutil PyYAML flask flask-cors werkzeug markdown weasyprint
```

### 最小安装（仅命令行工具）

```bash
# 仅核心功能
pip install psutil PyYAML
```

### Docker使用

```bash
# 构建镜像
docker build -t autoprofiler .

# 运行容器
docker run -p 5000:5000 autoprofiler

# 访问 Web 界面
# http://localhost:5000
```

## 6. 使用示例

### 示例1：Web界面分析

1. **启动Web服务**：
   ```bash
   python web_app_enhanced.py
   ```

2. **访问界面**：
   打开浏览器访问 http://127.0.0.1:5000

3. **上传文件**：
   - 拖放Python文件到上传区域
   - 或点击"选择文件"按钮
   - 支持.py和.pyw文件

4. **查看报告**：
   - **HTML预览**：格式化的报告，适合阅读
   - **Markdown源码**：原始Markdown内容
   - **下载选项**：HTML、PDF、Markdown格式

### 示例2：分析性能问题脚本

创建测试文件 `performance_test.py`：

```python
import time
import math

def cpu_intensive():
    """CPU密集型计算"""
    result = 0
    for i in range(10**6):
        result += math.sqrt(i) * math.sin(i)
    return result

def memory_intensive():
    """内存密集型操作"""
    data = []
    for i in range(10000):
        data.append([j for j in range(1000)])
    return sum(len(x) for x in data)

def main():
    print("开始性能测试...")
    
    start = time.time()
    result1 = cpu_intensive()
    print(f"CPU计算完成: {result1:.2f}, 耗时: {time.time()-start:.2f}秒")
    
    start = time.time()
    result2 = memory_intensive()
    print(f"内存操作完成: {result2}, 耗时: {time.time()-start:.2f}秒")
    
    print("测试完成!")

if __name__ == "__main__":
    main()
```

上传此文件到Web界面，将获得：
- CPU使用率图表
- 内存消耗分析
- 函数调用热点
- 优化建议

### 示例3：批量分析（命令行）

```bash
# 批量分析当前目录所有Python文件
for file in *.py; do
    echo "分析文件: $file"
    export AUTOPROFILER_TARGET="python $file"
    python -m unittest tests.test_autoprofiler_template 2>&1 | grep -A5 "AutoProfiler"
done
```

## 7. 报告格式说明

### HTML报告预览
```
# AutoProfiler 性能分析报告

## 执行摘要
- 运行时间: 2.45秒
- 退出码: 0
- 发现问题: 3个

## 性能指标
### CPU使用率
- 平均: 85%
- 峰值: 98%

### 内存消耗
- 峰值: 128MB
- 增长: +64MB
```

### Markdown源码
支持标准的Markdown语法：
- 标题（#, ##, ###）
- 代码块（```python）
- 列表（- 项目）
- 表格
- 引用

### PDF报告
- 专业排版，适合打印
- 包含页眉页脚
- 保持格式一致性

## 8. 核心功能详解

### 性能分析引擎

#### PsutilCollector
```python
from autoprofiler.collectors.psutil_collector import PsutilCollector

# 配置采样间隔
collector = PsutilCollector(
    sample_interval=0.1,  # 每100ms采样一次
    metrics=['cpu_percent', 'memory_rss', 'io_counters']
)
```

#### CProfileCollector
```python
from autoprofiler.collectors.cprofile_collector import CProfileCollector

# 函数级性能分析
collector = CProfileCollector(
    sort_by='cumulative',  # 按累积时间排序
    count=20               # 显示前20个最耗时的函数
)
```

### 智能模式匹配

AutoProfiler内置性能模式库，自动识别常见问题：

```yaml
# patterns/performance.yaml
- id: high_cpu_usage
  description: "CPU使用率过高"
  condition: "cpu_percent > 90"
  suggestions:
    - "考虑算法优化"
    - "检查是否有无限循环"
    - "使用异步或并行处理"

- id: memory_leak
  description: "内存持续增长"
  condition: "memory_growth > 50MB"
  suggestions:
    - "检查循环引用"
    - "使用弱引用"
    - "及时释放大对象"
```

## 9. 高级配置

### 自定义分析配置

```python
from autoprofiler.runner import Runner
from autoprofiler.models import TargetProgram

# 详细配置目标程序
target = TargetProgram(
    command=["python", "app.py", "--debug"],
    timeout=120,                    # 2分钟超时
    cwd="/path/to/project",        # 工作目录
    env={                          # 环境变量
        "PYTHONPATH": "/custom/path",
        "OMP_NUM_THREADS": "4"
    },
    stdout="output.log",           # 重定向输出
    stderr="error.log"             # 重定向错误
)
```

### Web界面配置

```python
# 修改web_app_enhanced.py中的配置
app.config.update(
    MAX_CONTENT_LENGTH=100 * 1024 * 1024,  # 增大到100MB
    UPLOAD_FOLDER='/data/uploads',         # 自定义上传目录
    SECRET_KEY='your-secure-key',          # 生产环境密钥
    PDF_EXPORT=True,                       # 启用PDF导出
    HTML_PREVIEW=True                      # 启用HTML预览
)
```

## 10. 故障排除

### 常见问题

#### Q1: Web界面无法启动
```bash
# 检查依赖
pip list | grep -E "flask|werkzeug|cors"

# 检查端口占用
netstat -tulpn | grep :5000

# 使用不同端口
python web_app_enhanced.py --port=8080
```

#### Q2: PDF导出失败
```bash
# 安装weasyprint依赖
# Ubuntu/Debian
sudo apt-get install python3-weasyprint

# macOS
brew install weasyprint

# 或者使用备选方案
pip install pdfkit
# 并安装wkhtmltopdf
```

#### Q3: 导入错误
```bash
# 确保在项目根目录
cd /path/to/autoprofiler

# 检查Python路径
python -c "import sys; print(sys.path)"

# 安装缺失的依赖
pip install psutil PyYAML
```

### 调试模式

```bash
# 启用详细日志
DEBUG=1 python web_app_enhanced.py

# 查看控制台输出
tail -f autoprofiler.log
```

## 11. API参考

### Web API端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/` | GET | Web界面首页 |
| `/api/upload` | POST | 文件上传 |
| `/api/analysis/<id>` | GET | 获取分析状态 |
| `/api/download/pdf/<id>` | GET | 下载PDF报告 |
| `/api/health` | GET | 健康检查 |

### Python API

```python
# 基本使用
from autoprofiler.runner import Runner
from autoprofiler.models import TargetProgram

runner = Runner()
session = runner.run(target, collectors=collectors)

# 访问分析结果
print(f"运行时间: {session.duration:.2f}秒")
print(f"退出码: {session.exit_code}")

# 获取报告
from autoprofiler.reporting.reporter import render_markdown
report = render_markdown(session)
```

## 12. 扩展开发

### 添加新的收集器

```python
from autoprofiler.collectors.base import BaseCollector

class CustomCollector(BaseCollector):
    """自定义收集器示例"""
    
    def __init__(self, custom_param="default"):
        self.custom_param = custom_param
        super().__init__()
    
    def collect(self, pid: int) -> ProfileArtifact:
        # 实现数据收集逻辑
        metrics = {
            "custom_metric": self.measure_custom_metric(pid),
            "timestamp": datetime.now().isoformat()
        }
        
        return ProfileArtifact(
            collector="custom_collector",
            type="custom-metrics",
            metrics=metrics
        )
```

### 自定义报告模板

```python
# 创建自定义模板
from jinja2 import Template

custom_template = """
# {{ filename }} - 性能分析报告

## 执行统计
- **开始时间**: {{ start_time }}
- **运行时长**: {{ duration }}秒
- **内存峰值**: {{ memory_peak }}MB

{% if findings %}
## 发现的问题
{% for finding in findings %}
### {{ finding.id }}
{{ finding.description }}

**建议**:
{% for suggestion in finding.suggestions %}
- {{ suggestion }}
{% endfor %}
{% endfor %}
{% endif %}
"""

# 渲染报告
template = Template(custom_template)
report = template.render(
    filename="test.py",
    duration=session.duration,
    findings=session.findings
)
```

## 13. 性能最佳实践

### 分析大型项目

```python
# 分阶段分析
target = TargetProgram(
    command=["python", "large_app.py"],
    timeout=300,  # 5分钟超时
    env={"PYTHONUNBUFFERED": "1"}  # 实时输出
)

# 使用低采样频率减少开销
collectors = [
    PsutilCollector(sample_interval=1.0),  # 1秒采样
    # 可选：只在需要时启用详细分析
    # CProfileCollector()
]
```

### 优化分析配置

```yaml
# config/analysis_config.yaml
default:
  sample_interval: 0.5
  timeout: 60
  collectors: [psutil]

detailed:
  sample_interval: 0.1
  timeout: 120
  collectors: [psutil, cprofile]

quick:
  sample_interval: 1.0
  timeout: 30
  collectors: [psutil]
```

## 14. 项目结构

```
autoprofiler/
├── autoprofiler/           # 核心库
│   ├── runner.py          # 运行器
│   ├── models.py          # 数据模型
│   ├── collectors/        # 收集器
│   │   ├── psutil_collector.py
│   │   └── cprofile_collector.py
│   ├── analyzers/         # 分析器
│   ├── patterns/          # 性能模式
│   └── reporting/         # 报告生成
├── web_app_enhanced.py    # 增强版Web界面
├── web_app_simple.py      # 简单版Web界面
├── tests/                 # 测试文件
├── examples/              # 示例代码
├── requirements.txt       # 依赖列表
└── README.md             # 本文档
```

## 15. 贡献指南

### 开发流程

```bash
# 1. 克隆项目
git clone https://github.com/yourusername/autoprofiler.git
cd autoprofiler

# 2. 创建开发分支
git checkout -b feature/new-collector

# 3. 安装开发依赖
pip install -r requirements-dev.txt

# 4. 运行测试
python -m pytest tests/ -v

# 5. 提交代码
git add .
git commit -m "添加新的收集器"
git push origin feature/new-collector
```

### 代码规范

- 使用Black格式化代码
- 遵循PEP 8规范
- 添加类型注解
- 编写单元测试
- 更新文档

## 16. 许可证

本项目采用MIT许可证。详见[LICENSE](LICENSE)文件。

## 17. 更新日志

### v1.2.0 
- 新增Web界面HTML预览功能
- 支持PDF报告导出
- 优化Markdown渲染
- 改进用户体验

### v1.1.0 (2024-01-15)
- 添加Web界面支持
- 实时进度显示
- 基础报告生成

### v1.0.0 (2024-01-01)
- 初始版本发布
- 核心分析功能
- 命令行工具
- 基础性能模式

## 18. 获取帮助

- **文档**：查看本README和代码注释
- **问题**：创建GitHub Issue
- **讨论**：加入项目Discussions
- **邮件**：联系维护者

## 19. 致谢

感谢以下开源项目的贡献：
- **Flask** - Web框架
- **psutil** - 系统监控
- **weasyprint** - PDF生成
- **marked.js** - Markdown渲染
- 以及所有贡献者

---

## 快速开始卡片

### 🚀 5分钟快速开始

```bash
# 1. 安装
pip install psutil PyYAML flask

# 2. 启动
python web_app_simple.py

# 3. 访问
# 打开浏览器: http://localhost:5000

# 4. 分析
# 拖放Python文件，查看报告！
```

### 📊 报告格式对比

| 格式 | 适合场景 | 优点 |
|------|----------|------|
| **HTML** | 网页查看 | 格式美观，交互性好 |
| **PDF** | 打印/分享 | 专业排版，格式固定 |
| **Markdown** | 文档编辑 | 轻量，易编辑 |

### 🔧 常用配置

```python
# web_app_enhanced.py中修改
app.config.update(
    MAX_CONTENT_LENGTH=100 * 1024 * 1024,  # 文件大小限制
    UPLOAD_FOLDER='/tmp/uploads',          # 上传目录
    PDF_EXPORT=True,                       # 启用PDF
    HTML_THEME='github'                    # 主题风格
)
```

---

**开始分析您的Python代码性能，发现瓶颈，提升效率！**

如有问题，请查看[故障排除](#10-故障排除)章节或创建Issue。