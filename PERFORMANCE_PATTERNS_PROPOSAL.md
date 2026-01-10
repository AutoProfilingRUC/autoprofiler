# 性能模式建议清单

> **状态更新**: 本文档中列出的所有可立即实现的模式已经完成实现并添加到 `autoprofiler/patterns/performance.yaml`。

本文档列出了可以添加到 AutoProfiler 的新性能模式，基于现有采集器提供的指标。

## 当前可用的指标

### PsutilCollector 指标
- `cpu_percent_avg`, `cpu_percent_max` - CPU 使用率
- `rss_bytes_max`, `vms_bytes_max` - 内存使用
- `sample_count` - 采样次数

### CProfileCollector 指标
- `total_calls` - 总函数调用次数
- `total_time` - 总执行时间
- `top_functions` - 热点函数列表（包含 call_count, cumulative_time）

### PySpyCollector 指标
- `duration_sec` - 采样持续时间
- `status` - 采集状态

---

## 建议的新性能模式

### 1. CPU 相关模式

#### 1.1 低 CPU 使用率（可能 IO 阻塞）
```yaml
- id: low_cpu_high_io
  meaning: "Low CPU usage suggests IO-bound workload or blocking operations"
  condition:
    cpu_percent_avg: "< 20"
    sample_count: "> 10"
  suggestions:
    - "Check for blocking I/O operations (file, network, database)."
    - "Consider async/await patterns if using synchronous I/O."
    - "Profile I/O wait time separately."
```

#### 1.2 CPU 使用率波动大
```yaml
- id: cpu_variance_high
  meaning: "High CPU usage variance indicates inconsistent workload distribution"
  condition:
    cpu_percent_max: "> 80"
    cpu_percent_avg: "< 50"
  suggestions:
    - "Investigate bursty workloads or periodic tasks."
    - "Consider workload smoothing or batching strategies."
```

### 2. 函数调用相关模式（基于 CProfile）

#### 2.1 高频小函数调用
```yaml
- id: high_call_count_small_fn
  meaning: "Excessive invocation of small functions causes interpreter overhead"
  condition:
    total_calls: "> 1000000"
    total_time: "< 5"
  suggestions:
    - "Consider inlining frequently called small functions."
    - "Batch operations to reduce call overhead."
    - "Use list comprehensions or vectorized operations."
```

#### 2.2 单函数占用大量时间
```yaml
- id: single_function_dominates
  meaning: "One function consumes disproportionate execution time"
  condition:
    total_time: "> 1"
  # 注意：这需要在分析器中检查 top_functions[0].cumulative_time / total_time
  suggestions:
    - "Focus optimization efforts on the identified hot function."
    - "Consider algorithmic improvements or caching."
    - "Check if the function can be parallelized."
```

#### 2.3 函数调用深度过深
```yaml
- id: deep_call_stack
  meaning: "Deep call stacks may indicate recursive algorithms or excessive delegation"
  # 注意：需要从 cProfile 数据中提取调用深度信息
  suggestions:
    - "Review recursive algorithms for optimization opportunities."
    - "Consider iterative alternatives for deep recursion."
    - "Check for unnecessary function call chains."
```

### 3. 内存相关模式

#### 3.1 虚拟内存远大于物理内存
```yaml
- id: vms_rss_ratio_high
  meaning: "High virtual memory to RSS ratio suggests memory fragmentation or sparse allocations"
  condition:
    vms_bytes_max: "> 2000000000"
    rss_bytes_max: "< 500000000"
  suggestions:
    - "Investigate memory fragmentation issues."
    - "Review large sparse data structures."
    - "Consider memory-mapped files for large datasets."
```

#### 3.2 内存持续增长（需要多采样点）
```yaml
- id: memory_growth_trend
  meaning: "Memory usage shows upward trend during execution"
  # 注意：需要分析器计算 rss_bytes 的增长趋势
  suggestions:
    - "Check for memory leaks or unbounded caches."
    - "Review object lifecycle management."
    - "Use memory profilers (tracemalloc, memray) for detailed analysis."
```

### 4. 执行时间相关模式

#### 4.1 执行时间过长
```yaml
- id: long_execution_time
  meaning: "Program execution exceeds expected duration"
  condition:
    total_time: "> 10"
  suggestions:
    - "Profile with py-spy to identify hot paths."
    - "Consider parallelization opportunities."
    - "Review algorithm complexity."
```

#### 4.2 调用次数与时间不匹配
```yaml
- id: high_calls_low_time
  meaning: "Many function calls but low total time suggests overhead-dominated execution"
  condition:
    total_calls: "> 500000"
    total_time: "< 0.5"
  suggestions:
    - "Reduce function call overhead through inlining or batching."
    - "Consider using built-in functions or C extensions."
```

### 5. 热点函数模式（基于 top_functions）

#### 5.1 少数函数占用大部分时间
```yaml
- id: top_functions_concentration
  meaning: "Top N functions consume majority of execution time"
  # 注意：需要分析器计算 top_functions 的 cumulative_time 总和 / total_time
  suggestions:
    - "Focus optimization on the identified hot functions."
    - "Review these functions for algorithmic improvements."
    - "Consider profiling these functions in isolation."
```

#### 5.2 热点函数调用次数异常
```yaml
- id: hot_function_high_call_count
  meaning: "Hot function has unusually high call count"
  # 注意：需要分析器检查 top_functions[0].call_count
  suggestions:
    - "Review if function calls can be reduced through caching."
    - "Check for redundant calls in loops."
    - "Consider memoization or result caching."
```

### 6. 采样相关模式

#### 6.1 采样不足
```yaml
- id: insufficient_sampling
  meaning: "Too few samples collected for reliable analysis"
  condition:
    sample_count: "< 5"
  suggestions:
    - "Increase sample_interval or execution duration."
    - "Ensure program runs long enough for meaningful profiling."
```

### 7. 组合模式（需要多个指标）

#### 7.1 CPU 密集型但调用次数少
```yaml
- id: cpu_intensive_few_calls
  meaning: "High CPU usage with few function calls suggests tight loops or native code"
  condition:
    cpu_percent_avg: "> 70"
    total_calls: "< 10000"
  suggestions:
    - "Profile with py-spy to see native code execution."
    - "Review tight loops for optimization opportunities."
    - "Consider using NumPy or other optimized libraries."
```

#### 7.2 内存高但 CPU 低
```yaml
- id: memory_intensive_low_cpu
  meaning: "High memory usage with low CPU suggests data processing or caching workload"
  condition:
    rss_bytes_max: "> 1000000000"
    cpu_percent_avg: "< 30"
  suggestions:
    - "Review data structure choices and sizes."
    - "Check for unnecessary data copying."
    - "Consider streaming or chunked processing."
```

---

## 需要增强采集器才能检测的模式

以下模式需要扩展采集器功能：

### 8. I/O 相关模式（需要扩展 PsutilCollector）
- 磁盘 I/O 等待时间
- 网络 I/O 活动
- 文件描述符使用情况

### 9. 线程/并发模式（需要扩展 PsutilCollector）
- 线程数量
- 线程切换开销
- GIL 竞争

### 10. 垃圾回收模式（需要 tracemalloc 或 memray）
- GC 频率和耗时
- 对象分配模式
- 内存泄漏检测

### 11. 调用图模式（需要增强 CProfileCollector）
- 调用关系分析
- 递归检测
- 循环依赖检测

---

## 实现优先级建议

### 高优先级（立即可实现）
1. `high_call_count_small_fn` - 高频小函数调用
2. `single_function_dominates` - 单函数占主导
3. `low_cpu_high_io` - 低 CPU 高 IO
4. `vms_rss_ratio_high` - 虚拟内存比例异常
5. `top_functions_concentration` - 热点函数集中

### 中优先级（需要少量分析器增强）
1. `memory_growth_trend` - 内存增长趋势
2. `cpu_intensive_few_calls` - CPU 密集但调用少
3. `high_calls_low_time` - 高调用低时间

### 低优先级（需要采集器扩展）
1. I/O 相关模式
2. 线程/并发模式
3. GC 相关模式

---

## 实现状态

### ✅ 已实现（2024）

所有基于现有指标的模式已经实现：

1. **CPU相关模式** - 全部实现
2. **函数调用相关模式** - 全部实现（需要CProfileCollector）
3. **内存相关模式** - 部分实现
   - ✅ `memory_growth_risk` - 已实现
   - ✅ `vms_rss_ratio_high` - 已实现
   - ⚠️ `memory_growth_trend` - 已实现但需要多个artifact或修改PsutilCollector保存所有采样点
4. **执行时间模式** - 全部实现
5. **热点函数模式** - 全部实现（需要CProfileCollector）
6. **采样模式** - 全部实现
7. **组合模式** - 全部实现（需要多个collector同时运行）

### 实现细节

- **分析器增强**: `PatternMatchingAnalyzer` 已扩展支持：
  - 复杂条件匹配（top_functions分析、比例计算）
  - 多artifact组合模式
  - 趋势分析（内存增长）
  - 派生指标计算（vms/rss比例、函数时间占比）

- **模式文件**: 所有模式已添加到 `autoprofiler/patterns/performance.yaml`

### 使用说明

1. **单collector模式**: 大多数模式只需要单个collector（PsutilCollector或CProfileCollector）
2. **多collector模式**: 组合模式（如`cpu_intensive_few_calls`）需要同时运行多个collector：
   ```python
   collectors = [
       PsutilCollector(sample_interval=0.25),
       CProfileCollector()
   ]
   ```

3. **CProfileCollector使用**: 需要手动调用`prepare_command`包装命令：
   ```python
   collector = CProfileCollector()
   wrapped_command = collector.prepare_command(target.command)
   target = TargetProgram(command=wrapped_command, ...)
   ```

## 注意事项

1. **阈值可配置性**：阈值在YAML文件中定义，可以根据需要调整
2. **模式组合**：某些模式需要多个artifact才能工作（标记为`requires_multiple_artifacts: true`）
3. **上下文感知**：某些模式需要了解程序的执行上下文（如预期运行时间）
4. **误报处理**：置信度计算基于证据数量，复杂模式可能有更保守的置信度
5. **内存增长趋势限制**：当前实现需要多个artifact或修改PsutilCollector来保存所有采样点才能准确检测
