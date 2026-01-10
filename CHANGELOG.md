# AutoProfiler 更新日志

## 2026-01-10 - 性能模式扩展

### 新增功能

#### 1. 扩展的分析器功能
- **复杂模式匹配**: `PatternMatchingAnalyzer` 现在支持：
  - Top函数分析（时间占比、调用次数）
  - 多artifact组合模式匹配
  - 内存增长趋势分析
  - 派生指标计算（vms/rss比例、函数时间占比等）

#### 2. 新增性能模式（共15个）

**CPU相关模式** (3个):
- `high_cpu_usage` - 高CPU使用率检测
- `low_cpu_high_io` - 低CPU高IO（IO阻塞检测）
- `cpu_variance_high` - CPU使用率波动大

**函数调用模式** (3个):
- `high_call_count_small_fn` - 高频小函数调用
- `single_function_dominates` - 单函数占主导
- `high_calls_low_time` - 高调用次数低总时间

**内存模式** (3个):
- `memory_growth_risk` - 内存增长风险（已存在，保留）
- `vms_rss_ratio_high` - 虚拟内存/物理内存比例异常
- `memory_growth_trend` - 内存增长趋势

**执行时间模式** (1个):
- `long_execution_time` - 执行时间过长

**热点函数模式** (2个):
- `top_functions_concentration` - 热点函数集中
- `hot_function_high_call_count` - 热点函数高调用次数

**采样模式** (1个):
- `insufficient_sampling` - 采样不足

**组合模式** (2个):
- `cpu_intensive_few_calls` - CPU密集但调用少（紧循环检测）
- `memory_intensive_low_cpu` - 内存密集但CPU低（数据处理检测）

### 技术改进

1. **代码质量**:
   - 修复了 `datetime.utcnow()` 弃用警告，改用 `datetime.now(timezone.utc)`
   - 改进了类型提示和错误处理

2. **分析器增强**:
   - 支持从 `top_functions` 数组中提取函数信息
   - 支持跨artifact的模式匹配
   - 支持趋势分析和比例计算

3. **文档更新**:
   - 更新了 `README.md`，添加了所有新模式的说明
   - 更新了 `PERFORMANCE_PATTERNS_PROPOSAL.md`，标记实现状态
   - 创建了 `CHANGELOG.md` 记录变更

### 使用示例

#### 单Collector模式
```python
from autoprofiler.runner import Runner
from autoprofiler.models import TargetProgram
from autoprofiler.collectors.psutil_collector import PsutilCollector
from autoprofiler.patterns.loader import load_patterns
from autoprofiler.analyzers.simple_analyzer import PatternMatchingAnalyzer

target = TargetProgram(command=["python", "my_script.py"], timeout=30)
collector = PsutilCollector(sample_interval=0.25)
session = Runner().run(target, collectors=[collector])

patterns = load_patterns(Path("autoprofiler/patterns/performance.yaml"))
analyzer = PatternMatchingAnalyzer(patterns)
session.findings = analyzer.analyze(session.artifacts)
```

#### 多Collector组合模式
```python
from autoprofiler.collectors.cprofile_collector import CProfileCollector

# 使用CProfileCollector需要先包装命令
cprofile_collector = CProfileCollector()
wrapped_command = cprofile_collector.prepare_command(target.command)
target = TargetProgram(command=wrapped_command, timeout=30)

# 同时使用多个collector
collectors = [
    PsutilCollector(sample_interval=0.25),
    cprofile_collector
]
session = Runner().run(target, collectors=collectors)
```

### 已知限制

1. **内存增长趋势**: 当前实现需要多个artifact或修改PsutilCollector保存所有采样点才能准确检测
2. **CProfileCollector**: 需要手动调用 `prepare_command` 包装命令
3. **组合模式**: 需要同时运行多个collector才能工作

### 测试状态

✅ 所有测试通过
✅ 新模式正常工作
✅ 向后兼容性保持

### 文件变更

**修改的文件**:
- `autoprofiler/analyzers/simple_analyzer.py` - 扩展模式匹配功能
- `autoprofiler/patterns/performance.yaml` - 添加15个新模式
- `autoprofiler/runner.py` - 修复datetime弃用警告
- `autoprofiler/collectors/base.py` - 修复datetime弃用警告
- `autoprofiler/collectors/cprofile_collector.py` - 修复datetime弃用警告
- `autoprofiler/collectors/pyspy_collector.py` - 修复datetime弃用警告
- `README.md` - 添加新模式说明

**新增的文件**:
- `PERFORMANCE_PATTERNS_PROPOSAL.md` - 性能模式建议文档
- `CHANGELOG.md` - 更新日志
