#!/usr/bin/env python3
"""
测试新实现的性能模式功能
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到路径（从tests文件夹运行时）
sys.path.insert(0, str(Path(__file__).parent.parent))

from autoprofiler.runner import Runner
from autoprofiler.models import TargetProgram
from autoprofiler.collectors.psutil_collector import PsutilCollector
from autoprofiler.collectors.cprofile_collector import CProfileCollector
from autoprofiler.patterns.loader import load_patterns
from autoprofiler.analyzers.simple_analyzer import PatternMatchingAnalyzer
from autoprofiler.reporting.reporter import render_markdown, render_findings_json


def test_cpu_intensive_workload():
    """测试CPU密集型工作负载"""
    print("=" * 80)
    print("测试 1: CPU密集型工作负载")
    print("=" * 80)
    
    # 创建一个CPU密集型的Python脚本
    cpu_intensive_code = """
import time
total = 0
for i in range(1000000):
    total += i * i
print(f"Total: {total}")
"""
    
    target = TargetProgram(
        command=[sys.executable, "-c", cpu_intensive_code],
        timeout=30
    )
    
    collector = PsutilCollector(sample_interval=0.1)
    session = Runner().run(target, collectors=[collector])
    
    # 从项目根目录加载模式文件
    patterns = load_patterns(Path(__file__).parent.parent / "autoprofiler/patterns/performance.yaml")
    analyzer = PatternMatchingAnalyzer(patterns)
    session.findings = analyzer.analyze(session.artifacts)
    
    print("\n执行结果:")
    print(f"- PID: {session.execution.pid}")
    print(f"- 返回码: {session.execution.returncode}")
    print(f"- 执行时间: {(session.execution.finished_at - session.execution.started_at).total_seconds():.3f}秒")
    
    print(f"\n采集的指标:")
    for artifact in session.artifacts:
        print(f"  - {artifact.collector}: {artifact.metrics}")
    
    print(f"\n检测到的模式 ({len(session.findings)} 个):")
    for finding in session.findings:
        print(f"  - {finding.pattern_id} (置信度: {finding.confidence:.2f})")
        print(f"    摘要: {finding.summary}")
        print(f"    证据: {finding.evidence}")
    
    return session


def test_with_cprofile():
    """测试使用CProfileCollector"""
    print("\n" + "=" * 80)
    print("测试 2: 使用CProfileCollector分析函数调用")
    print("=" * 80)
    
    # 创建一个有大量函数调用的脚本
    many_calls_code = """
def small_func(x):
    return x * 2

total = 0
for i in range(500000):
    total += small_func(i)
print(f"Total: {total}")
"""
    
    # 使用CProfileCollector需要先包装命令
    cprofile_collector = CProfileCollector()
    wrapped_command = cprofile_collector.prepare_command([sys.executable, "-c", many_calls_code])
    
    target = TargetProgram(
        command=wrapped_command,
        timeout=30
    )
    
    # 同时使用多个collector
    collectors = [
        PsutilCollector(sample_interval=0.1),
        cprofile_collector
    ]
    
    session = Runner().run(target, collectors=collectors)
    
    patterns = load_patterns(Path(__file__).parent.parent / "autoprofiler/patterns/performance.yaml")
    analyzer = PatternMatchingAnalyzer(patterns)
    session.findings = analyzer.analyze(session.artifacts)
    
    print("\n执行结果:")
    print(f"- PID: {session.execution.pid}")
    print(f"- 返回码: {session.execution.returncode}")
    print(f"- 执行时间: {(session.execution.finished_at - session.execution.started_at).total_seconds():.3f}秒")
    
    print(f"\n采集的指标:")
    for artifact in session.artifacts:
        print(f"  - {artifact.collector} ({artifact.category}):")
        if artifact.category == "cpu" and "top_functions" in artifact.metrics:
            print(f"    总调用次数: {artifact.metrics.get('total_calls', 0):.0f}")
            print(f"    总时间: {artifact.metrics.get('total_time', 0):.3f}秒")
            top_funcs = artifact.metrics.get('top_functions', [])[:3]
            if top_funcs:
                print(f"    Top函数:")
                for func in top_funcs:
                    print(f"      - {func.get('function', 'unknown')}: {func.get('call_count', 0):.0f}次调用, {func.get('cumulative_time', 0):.3f}秒")
        else:
            for key, value in artifact.metrics.items():
                if isinstance(value, (int, float)):
                    print(f"    {key}: {value}")
    
    print(f"\n检测到的模式 ({len(session.findings)} 个):")
    for finding in session.findings:
        print(f"  - {finding.pattern_id} (置信度: {finding.confidence:.2f})")
        print(f"    摘要: {finding.summary}")
        if finding.location:
            print(f"    位置: {finding.location}")
        print(f"    证据: {finding.evidence}")
        if finding.suggestions:
            print(f"    建议:")
            for suggestion in finding.suggestions:
                print(f"      - {suggestion}")
    
    return session


def test_memory_usage():
    """测试内存使用模式"""
    print("\n" + "=" * 80)
    print("测试 3: 内存使用模式检测")
    print("=" * 80)
    
    # 创建一个使用较多内存的脚本
    memory_code = """
data = []
for i in range(100000):
    data.append([j for j in range(100)])
print(f"Created {len(data)} lists")
"""
    
    target = TargetProgram(
        command=[sys.executable, "-c", memory_code],
        timeout=30
    )
    
    collector = PsutilCollector(sample_interval=0.1)
    session = Runner().run(target, collectors=[collector])
    
    patterns = load_patterns(Path(__file__).parent.parent / "autoprofiler/patterns/performance.yaml")
    analyzer = PatternMatchingAnalyzer(patterns)
    session.findings = analyzer.analyze(session.artifacts)
    
    print("\n执行结果:")
    print(f"- PID: {session.execution.pid}")
    print(f"- 返回码: {session.execution.returncode}")
    
    print(f"\n采集的指标:")
    for artifact in session.artifacts:
        print(f"  - {artifact.collector}:")
        for key, value in artifact.metrics.items():
            if isinstance(value, (int, float)):
                if 'bytes' in key:
                    print(f"    {key}: {value / 1024 / 1024:.2f} MB")
                else:
                    print(f"    {key}: {value}")
    
    print(f"\n检测到的模式 ({len(session.findings)} 个):")
    for finding in session.findings:
        print(f"  - {finding.pattern_id} (置信度: {finding.confidence:.2f})")
        print(f"    摘要: {finding.summary}")
        print(f"    证据: {finding.evidence}")
    
    return session


def main():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("AutoProfiler 新模式测试套件")
    print("=" * 80)
    
    try:
        # 测试1: CPU密集型
        session1 = test_cpu_intensive_workload()
        
        # 测试2: CProfile分析
        session2 = test_with_cprofile()
        
        # 测试3: 内存使用
        session3 = test_memory_usage()
        
        print("\n" + "=" * 80)
        print("测试总结")
        print("=" * 80)
        print(f"测试1检测到 {len(session1.findings)} 个模式")
        print(f"测试2检测到 {len(session2.findings)} 个模式")
        print(f"测试3检测到 {len(session3.findings)} 个模式")
        print("\n所有测试完成！")
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
