#!/usr/bin/env python3
"""
完整演示 - 展示AutoProfiler的所有新功能
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from autoprofiler.runner import Runner
from autoprofiler.models import TargetProgram
from autoprofiler.collectors.psutil_collector import PsutilCollector
from autoprofiler.collectors.cprofile_collector import CProfileCollector
from autoprofiler.patterns.loader import load_patterns
from autoprofiler.analyzers.simple_analyzer import PatternMatchingAnalyzer
from autoprofiler.reporting.reporter import render_markdown


def demo_complete_profiling():
    """完整演示：CPU密集型 + 函数调用分析"""
    print("=" * 80)
    print("AutoProfiler 完整功能演示")
    print("=" * 80)
    
    # 创建一个既有CPU密集计算又有大量函数调用的工作负载
    workload_code = """
def compute_square(x):
    return x * x

def process_batch(start, end):
    total = 0
    for i in range(start, end):
        total += compute_square(i)
    return total

# CPU密集型计算
result = 0
for batch in range(100):
    result += process_batch(batch * 1000, (batch + 1) * 1000)
    
print(f"Final result: {result}")
"""
    
    # 使用CProfileCollector包装命令
    cprofile_collector = CProfileCollector(top_n=5)
    wrapped_command = cprofile_collector.prepare_command(["python", "-c", workload_code])
    
    target = TargetProgram(
        command=wrapped_command,
        timeout=30
    )
    
    # 同时使用多个collector
    collectors = [
        PsutilCollector(sample_interval=0.2),
        cprofile_collector
    ]
    
    print("\n正在运行分析...")
    session = Runner().run(target, collectors=collectors)
    
    # 加载模式并分析
    patterns = load_patterns(Path("autoprofiler/patterns/performance.yaml"))
    analyzer = PatternMatchingAnalyzer(patterns)
    session.findings = analyzer.analyze(session.artifacts)
    
    # 生成完整报告
    report = render_markdown(session)
    
    print("\n" + "=" * 80)
    print("完整分析报告")
    print("=" * 80)
    print(report)
    
    # 统计信息
    print("\n" + "=" * 80)
    print("统计信息")
    print("=" * 80)
    print(f"总采集器数量: {len(session.artifacts)}")
    print(f"检测到的模式数量: {len(session.findings)}")
    
    if session.findings:
        print("\n检测到的模式列表:")
        for i, finding in enumerate(session.findings, 1):
            print(f"  {i}. {finding.pattern_id}")
            print(f"     置信度: {finding.confidence:.2f}")
            print(f"     摘要: {finding.summary}")
            if finding.location:
                print(f"     位置: {finding.location}")
    
    # 按类别统计
    cpu_patterns = [f for f in session.findings if 'cpu' in f.pattern_id.lower()]
    memory_patterns = [f for f in session.findings if 'memory' in f.pattern_id.lower()]
    call_patterns = [f for f in session.findings if 'call' in f.pattern_id.lower() or 'function' in f.pattern_id.lower()]
    
    print("\n按类别统计:")
    print(f"  CPU相关: {len(cpu_patterns)} 个")
    print(f"  内存相关: {len(memory_patterns)} 个")
    print(f"  函数调用相关: {len(call_patterns)} 个")
    print(f"  其他: {len(session.findings) - len(cpu_patterns) - len(memory_patterns) - len(call_patterns)} 个")
    
    return session


def main():
    try:
        session = demo_complete_profiling()
        print("\n✅ 演示完成！")
        return 0
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
