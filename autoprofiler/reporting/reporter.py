"""
Reporter utilities for producing human-readable and machine-readable outputs.
"""

from __future__ import annotations
import json
from typing import List
from ..models import ProfilingSession

def render_markdown(session: ProfilingSession) -> str:
    lines: List[str] = []
    
    # 标题双语化
    lines.append(f"# AutoProfiler Report for `{ ' '.join(session.target.command) }` / 分析报告")
    lines.append("")
    
    # 执行摘要
    lines.append("## Execution Summary / 执行摘要")
    lines.append(f"- PID: {session.execution.pid}")
    lines.append(f"- Return Code / 返回码: {session.execution.returncode}")
    lines.append(f"- Started At / 开始时间: {session.execution.started_at.isoformat()}")
    lines.append(f"- Finished At / 结束时间: {session.execution.finished_at.isoformat()}")
    duration = (session.execution.finished_at - session.execution.started_at).total_seconds()
    lines.append(f"- Duration (s) / 耗时 (秒): {duration:.3f}")
    lines.append("")

    # 产物/指标
    lines.append("## Artifacts / 收集产物")
    for artifact in session.artifacts:
        lines.append(f"- {artifact.collector} ({artifact.category}): {artifact.metrics}")
    lines.append("")

    # 核心发现
    lines.append("## Findings / 发现")
    if not session.findings:
        lines.append("- No patterns matched; consider running with additional collectors. / 未匹配到任何性能模式；建议增加采集器。")
    else:
        for finding in session.findings:
            # 模式名称与摘要
            lines.append(f"- **{finding.pattern_id}** (confidence/置信度 {finding.confidence:.2f}): {finding.summary}")
            lines.append(f"  - Evidence / 证据: {finding.evidence}")
            
            # 建议部分：处理换行逻辑
            for suggestion in finding.suggestions:
                if " / " in suggestion:
                    # 拆分中英文
                    eng_part, chn_part = suggestion.split(" / ", 1)
                    lines.append(f"  - Suggestion: {eng_part}")
                    lines.append(f"    /建议: {chn_part}") # 换行并对齐缩进
                else:
                    lines.append(f"  - Suggestion / 建议: {suggestion}")
            # 每个发现之间留一个空行，提升可读性
            lines.append("")

    # 验证步骤
    lines.append("## Verification Steps / 验证步骤")
    lines.append("- Re-run the profiler to confirm reproducibility. / 重新运行分析器以确认可复现性。")
    lines.append("- Compare metrics across runs to track improvement. / 比较多次运行的指标以追踪改进情况。")
    
    return "\n".join(lines)

def render_findings_json(session: ProfilingSession) -> str:
    # JSON 保持原始数据结构，通常不需要双语化 UI 文本
    payload = {
        "target": {
            "command": session.target.command,
            "cwd": session.target.cwd,
            "timeout": session.target.timeout,
        },
        "execution": {
            "pid": session.execution.pid,
            "returncode": session.execution.returncode,
            "started_at": session.execution.started_at.isoformat(),
            "finished_at": session.execution.finished_at.isoformat(),
        },
        "artifacts": [
            {"collector": a.collector, "category": a.category, "metrics": a.metrics}
            for a in session.artifacts
        ],
        "findings": [
            {
                "pattern_id": f.pattern_id,
                "confidence": f.confidence,
                "summary": f.summary,
                "evidence": f.evidence,
                "suggestions": f.suggestions,
            }
            for f in session.findings
        ]
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)