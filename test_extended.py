#!/usr/bin/env python3
"""
扩展测试 - 运行时间更长的工作负载，以便检测更多性能模式
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from autoprofiler.runner import Runner
from autoprofiler.models import TargetProgram
from autoprofiler.collectors.psutil_collector import PsutilCollector
from autoprofiler.collectors.cprofile_collector import CProfileCollector
from autoprofiler.patterns.loader import load_patterns
from autoprofiler.analyzers.simple_analyzer import PatternMatchingAnalyzer
from autoprofiler.reporting.reporter import render_markdown


def test_high_cpu_workload():
    """测试高CPU使用率模式"""
    print("=" * 80)
    print("测试: 高CPU使用率工作负载")
    print("=" * 80)
    
    # 创建一个运行2秒的CPU密集型任务
    cpu_code = """
import time
start = time.time()
total = 0
while time.time() - start < 2.0:
    for i in range(10000):
        total += i * i
print(f"Total: {total}")
"""
    
    target = TargetProgram(
        command=["python", "-c", cpu_code],
        timeout=10
    )
    
    collector = PsutilCollector(sample_interval=0.2)
    session = Runner().run(target, collectors=[collector])
    
    patterns = load_patterns(Path("autoprofiler/patterns/performance.yaml"))
    analyzer = PatternMatchingAnalyzer(patterns)
    session.findings = analyzer.analyze(session.artifacts)
    
    print(f"\n执行时间: {(session.execution.finished_at - session.execution.started_at).total_seconds():.3f}秒")
    print(f"\n采集的指标:")
    for artifact in session.artifacts:
        print(f"  {artifact.collector}:")
        for key, value in artifact.metrics.items():
            if isinstance(value, (int, float)):
                print(f"    {key}: {value}")
    
    print(f"\n检测到的模式 ({len(session.findings)} 个):")
    for finding in session.findings:
        print(f"\n  [{finding.pattern_id}] (置信度: {finding.confidence:.2f})")
        print(f"  摘要: {finding.summary}")
        print(f"  证据: {finding.evidence}")
        if finding.suggestions:
            print(f"  建议:")
            for suggestion in finding.suggestions[:2]:  # 只显示前2个
                print(f"    - {suggestion}")
    
    return session


def test_many_function_calls():
    """测试高频函数调用模式"""
    print("\n" + "=" * 80)
    print("测试: 高频函数调用工作负载")
    print("=" * 80)
    
    # 创建大量小函数调用
    many_calls_code = """
def small_func(x):
    return x * 2 + 1

def process_data(n):
    total = 0
    for i in range(n):
        total += small_func(i)
    return total

result = process_data(2000000)  # 200万次调用
print(f"Result: {result}")
"""
    
    cprofile_collector = CProfileCollector(top_n=5)
    wrapped_command = cprofile_collector.prepare_command(["python", "-c", many_calls_code])
    
    target = TargetProgram(
        command=wrapped_command,
        timeout=30
    )
    
    collectors = [
        PsutilCollector(sample_interval=0.1),
        cprofile_collector
    ]
    
    session = Runner().run(target, collectors=collectors)
    
    patterns = load_patterns(Path("autoprofiler/patterns/performance.yaml"))
    analyzer = PatternMatchingAnalyzer(patterns)
    session.findings = analyzer.analyze(session.artifacts)
    
    print(f"\n执行时间: {(session.execution.finished_at - session.execution.started_at).total_seconds():.3f}秒")
    
    print(f"\n采集的指标:")
    for artifact in session.artifacts:
        print(f"\n  {artifact.collector} ({artifact.category}):")
        if artifact.category == "cpu":
            metrics = artifact.metrics
            print(f"    总调用次数: {metrics.get('total_calls', 0):,.0f}")
            print(f"    总时间: {metrics.get('total_time', 0):.3f}秒")
            top_funcs = metrics.get('top_functions', [])[:3]
            if top_funcs:
                print(f"    Top 3 函数:")
                for func in top_funcs:
                    print(f"      - {func.get('function', 'unknown')}")
                    print(f"        调用: {func.get('call_count', 0):,.0f}次, "
                          f"累计时间: {func.get('cumulative_time', 0):.3f}秒")
        else:
            for key, value in artifact.metrics.items():
                if isinstance(value, (int, float)):
                    print(f"    {key}: {value}")
    
    print(f"\n检测到的模式 ({len(session.findings)} 个):")
    for finding in session.findings:
        print(f"\n  [{finding.pattern_id}] (置信度: {finding.confidence:.2f})")
        print(f"  摘要: {finding.summary}")
        if finding.location:
            print(f"  位置: {finding.location}")
        print(f"  证据: {finding.evidence}")
        if finding.suggestions:
            print(f"  建议:")
            for suggestion in finding.suggestions[:2]:
                print(f"    - {suggestion}")
    
    return session


def test_memory_intensive():
    """测试内存密集型工作负载"""
    print("\n" + "=" * 80)
    print("测试: 内存密集型工作负载")
    print("=" * 80)
    
    # 创建大量数据但处理简单（低CPU高内存）
    memory_code = """
import time
data = []
# 创建大量数据
for i in range(500000):
    data.append([j for j in range(50)])
    
# 简单处理（低CPU）
time.sleep(0.5)
total = sum(len(item) for item in data)
print(f"Total items: {len(data)}, Total elements: {total}")
"""
    
    target = TargetProgram(
        command=["python", "-c", memory_code],
        timeout=30
    )
    
    collector = PsutilCollector(sample_interval=0.15)
    session = Runner().run(target, collectors=[collector])
    
    patterns = load_patterns(Path("autoprofiler/patterns/performance.yaml"))
    analyzer = PatternMatchingAnalyzer(patterns)
    session.findings = analyzer.analyze(session.artifacts)
    
    print(f"\n执行时间: {(session.execution.finished_at - session.execution.started_at).total_seconds():.3f}秒")
    
    print(f"\n采集的指标:")
    for artifact in session.artifacts:
        print(f"  {artifact.collector}:")
        for key, value in artifact.metrics.items():
            if isinstance(value, (int, float)):
                if 'bytes' in key:
                    print(f"    {key}: {value / 1024 / 1024:.2f} MB")
                else:
                    print(f"    {key}: {value}")
    
    print(f"\n检测到的模式 ({len(session.findings)} 个):")
    for finding in session.findings:
        print(f"\n  [{finding.pattern_id}] (置信度: {finding.confidence:.2f})")
        print(f"  摘要: {finding.summary}")
        print(f"  证据: {finding.evidence}")
        if finding.suggestions:
            print(f"  建议:")
            for suggestion in finding.suggestions[:2]:
                print(f"    - {suggestion}")
    
    return session


def main():
    print("\n" + "=" * 80)
    print("AutoProfiler 扩展测试 - 检测更多性能模式")
    print("=" * 80)
    
    try:
        # 测试1: 高CPU
        session1 = test_high_cpu_workload()
        
        # 测试2: 高频函数调用
        session2 = test_many_function_calls()
        
        # 测试3: 内存密集型
        session3 = test_memory_intensive()
        
        print("\n" + "=" * 80)
        print("测试总结")
        print("=" * 80)
        print(f"测试1 (高CPU): {len(session1.findings)} 个模式")
        print(f"测试2 (高频调用): {len(session2.findings)} 个模式")
        print(f"测试3 (内存密集): {len(session3.findings)} 个模式")
        print("\n✅ 所有测试完成！")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
