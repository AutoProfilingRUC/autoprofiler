"""
Deterministic analyzer that matches collector metrics against declarative patterns.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from ..models import Finding, ProfileArtifact
from .base import Analyzer


class PatternMatchingAnalyzer(Analyzer):
    """Analyzer that evaluates numeric thresholds defined in patterns."""

    def __init__(self, patterns: List[Dict]) -> None:
        self.patterns = patterns

    def analyze(self, artifacts: Iterable[ProfileArtifact]) -> List[Finding]:
        findings: List[Finding] = []
        artifact_list = list(artifacts)
        
        # 首先处理单artifact模式
        for artifact_index, artifact in enumerate(artifact_list):
            for pattern in self.patterns:
                # 跳过需要多artifact的模式
                if pattern.get("requires_multiple_artifacts", False):
                    continue
                    
                matches, evidence = self._matches_pattern(
                    artifact.metrics, pattern, artifact, artifact_list
                )
                if not matches:
                    continue

                finding_id = f"finding_{artifact_index}_{pattern['id']}"
                summary = pattern.get("meaning", "Pattern match detected")
                suggestions = list(pattern.get("suggestions", []))
                confidence = self._confidence(evidence, pattern)
                
                # 尝试从top_functions中提取location
                location = self._extract_location(artifact.metrics, pattern)
                
                findings.append(
                    Finding(
                        finding_id=finding_id,
                        pattern_id=pattern["id"],
                        location=location,
                        evidence=evidence,
                        confidence=confidence,
                        summary=summary,
                        suggestions=suggestions,
                    )
                )
        
        # 然后处理需要多artifact的组合模式
        for pattern in self.patterns:
            if not pattern.get("requires_multiple_artifacts", False):
                continue
            matches, evidence = self._matches_multi_artifact_pattern(
                artifact_list, pattern
            )
            if not matches:
                continue
            
            finding_id = f"finding_multi_{pattern['id']}"
            summary = pattern.get("meaning", "Pattern match detected")
            suggestions = list(pattern.get("suggestions", []))
            confidence = self._confidence(evidence, pattern)
            
            findings.append(
                Finding(
                    finding_id=finding_id,
                    pattern_id=pattern["id"],
                    location=None,
                    evidence=evidence,
                    confidence=confidence,
                    summary=summary,
                    suggestions=suggestions,
                )
            )
        
        return findings

    def _matches_pattern(
        self,
        metrics: Dict[str, Any],
        pattern: Dict,
        artifact: ProfileArtifact,
        all_artifacts: List[ProfileArtifact],
    ) -> Tuple[bool, Dict[str, Any]]:
        """匹配单个artifact的模式。"""
        evidence: Dict[str, Any] = {}
        conditions: Dict[str, Any] = pattern.get("condition", {})
        
        # 处理特殊条件类型
        for condition_key, condition_value in conditions.items():
            if condition_key == "top_function_ratio":
                # 检查top函数时间占比
                if not self._check_top_function_ratio(metrics, condition_value, evidence):
                    return False, evidence
            elif condition_key == "top_function_call_count":
                # 检查top函数调用次数
                if not self._check_top_function_call_count(metrics, condition_value, evidence):
                    return False, evidence
            elif condition_key == "memory_growth_trend":
                # 检查内存增长趋势
                if not self._check_memory_growth_trend(all_artifacts, condition_value, evidence):
                    return False, evidence
            elif condition_key == "vms_rss_ratio":
                # 计算vms/rss比例
                if not self._check_vms_rss_ratio(metrics, condition_value, evidence):
                    return False, evidence
            elif condition_key == "function_time_ratio":
                # 检查函数时间占比
                if not self._check_function_time_ratio(metrics, condition_value, evidence):
                    return False, evidence
            else:
                # 标准数值条件
                if condition_key not in metrics:
                    return False, evidence
                value = self._get_numeric_value(metrics[condition_key])
                if value is None:
                    return False, evidence
                if not self._evaluate_rule(value, condition_value):
                    return False, evidence
                evidence[condition_key] = value
        
        return True, evidence

    def _matches_multi_artifact_pattern(
        self, artifacts: List[ProfileArtifact], pattern: Dict
    ) -> Tuple[bool, Dict[str, Any]]:
        """匹配需要多个artifact的组合模式。"""
        evidence: Dict[str, Any] = {}
        conditions: Dict[str, Any] = pattern.get("condition", {})
        
        # 收集所有artifact的指标
        all_metrics: Dict[str, List[Any]] = {}
        for artifact in artifacts:
            for key, value in artifact.metrics.items():
                if key not in all_metrics:
                    all_metrics[key] = []
                all_metrics[key].append(value)
        
        # 检查组合条件
        for condition_key, condition_value in conditions.items():
            if condition_key == "cpu_from_system":
                # 从system artifact获取CPU
                cpu_avg = self._get_metric_from_category(artifacts, "system", "cpu_percent_avg")
                if cpu_avg is None or not self._evaluate_rule(cpu_avg, condition_value):
                    return False, evidence
                evidence["cpu_percent_avg"] = cpu_avg
            elif condition_key == "calls_from_cpu":
                # 从cpu artifact获取调用次数
                total_calls = self._get_metric_from_category(artifacts, "cpu", "total_calls")
                if total_calls is None or not self._evaluate_rule(total_calls, condition_value):
                    return False, evidence
                evidence["total_calls"] = total_calls
            elif condition_key == "memory_from_system":
                # 从system artifact获取内存
                rss_max = self._get_metric_from_category(artifacts, "system", "rss_bytes_max")
                if rss_max is None or not self._evaluate_rule(rss_max, condition_value):
                    return False, evidence
                evidence["rss_bytes_max"] = rss_max
        
        return True, evidence

    def _check_top_function_ratio(
        self, metrics: Dict[str, Any], rule: str, evidence: Dict[str, Any]
    ) -> bool:
        """检查top函数时间占比。"""
        total_time = self._get_numeric_value(metrics.get("total_time"))
        top_functions = metrics.get("top_functions", [])
        
        if total_time is None or total_time == 0 or not top_functions:
            return False
        
        # 计算top 3函数的总时间占比
        top_time = sum(
            self._get_numeric_value(func.get("cumulative_time", 0))
            for func in top_functions[:3]
        )
        ratio = top_time / total_time if total_time > 0 else 0.0
        
        if not self._evaluate_rule(ratio, rule):
            return False
        
        evidence["top_function_ratio"] = ratio
        evidence["top_functions_count"] = len(top_functions)
        return True

    def _check_top_function_call_count(
        self, metrics: Dict[str, Any], rule: str, evidence: Dict[str, Any]
    ) -> bool:
        """检查top函数调用次数。"""
        top_functions = metrics.get("top_functions", [])
        if not top_functions:
            return False
        
        top_func = top_functions[0]
        call_count = self._get_numeric_value(top_func.get("call_count", 0))
        if call_count is None:
            return False
        
        if not self._evaluate_rule(call_count, rule):
            return False
        
        evidence["top_function_call_count"] = call_count
        evidence["top_function"] = top_func.get("function", "unknown")
        return True

    def _check_memory_growth_trend(
        self, artifacts: List[ProfileArtifact], rule: str, evidence: Dict[str, Any]
    ) -> bool:
        """检查内存增长趋势。"""
        # 收集所有system artifact的rss_bytes采样
        rss_samples: List[float] = []
        for artifact in artifacts:
            if artifact.category == "system" and "rss_bytes_max" in artifact.metrics:
                rss = self._get_numeric_value(artifact.metrics["rss_bytes_max"])
                if rss is not None:
                    rss_samples.append(rss)
        
        if len(rss_samples) < 3:
            return False
        
        # 计算增长趋势（简单线性回归斜率）
        n = len(rss_samples)
        x_mean = (n - 1) / 2
        y_mean = sum(rss_samples) / n
        
        numerator = sum((i - x_mean) * (rss_samples[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return False
        
        slope = numerator / denominator
        growth_rate = slope / y_mean if y_mean > 0 else 0.0
        
        if not self._evaluate_rule(growth_rate, rule):
            return False
        
        evidence["memory_growth_rate"] = growth_rate
        evidence["memory_samples"] = len(rss_samples)
        return True

    def _check_vms_rss_ratio(
        self, metrics: Dict[str, Any], rule: str, evidence: Dict[str, Any]
    ) -> bool:
        """检查vms/rss比例。"""
        vms = self._get_numeric_value(metrics.get("vms_bytes_max"))
        rss = self._get_numeric_value(metrics.get("rss_bytes_max"))
        
        if vms is None or rss is None or rss == 0:
            return False
        
        ratio = vms / rss
        if not self._evaluate_rule(ratio, rule):
            return False
        
        evidence["vms_rss_ratio"] = ratio
        evidence["vms_bytes_max"] = vms
        evidence["rss_bytes_max"] = rss
        return True

    def _check_function_time_ratio(
        self, metrics: Dict[str, Any], rule: str, evidence: Dict[str, Any]
    ) -> bool:
        """检查单个函数时间占比。"""
        total_time = self._get_numeric_value(metrics.get("total_time"))
        top_functions = metrics.get("top_functions", [])
        
        if total_time is None or total_time == 0 or not top_functions:
            return False
        
        top_func_time = self._get_numeric_value(top_functions[0].get("cumulative_time", 0))
        if top_func_time is None:
            return False
        
        ratio = top_func_time / total_time if total_time > 0 else 0.0
        if not self._evaluate_rule(ratio, rule):
            return False
        
        evidence["function_time_ratio"] = ratio
        evidence["top_function"] = top_functions[0].get("function", "unknown")
        return True

    def _get_metric_from_category(
        self, artifacts: List[ProfileArtifact], category: str, metric_name: str
    ) -> float | None:
        """从指定category的artifact中获取指标。"""
        for artifact in artifacts:
            if artifact.category == category and metric_name in artifact.metrics:
                return self._get_numeric_value(artifact.metrics[metric_name])
        return None

    def _get_numeric_value(self, value: Any) -> float | None:
        """将值转换为浮点数。"""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

    def _evaluate_rule(self, value: float, rule: str) -> bool:
        """评估数值规则。"""
        rule = rule.strip()
        if rule.startswith(">="):
            return value >= float(rule[2:])
        if rule.startswith("<="):
            return value <= float(rule[2:])
        if rule.startswith(">"):
            return value > float(rule[1:])
        if rule.startswith("<"):
            return value < float(rule[1:])
        if rule.startswith("=="):
            return abs(value - float(rule[2:])) < 1e-9
        try:
            return abs(value - float(rule)) < 1e-9
        except ValueError:
            return False

    def _extract_location(self, metrics: Dict[str, Any], pattern: Dict) -> str | None:
        """从metrics中提取location信息。"""
        top_functions = metrics.get("top_functions", [])
        if top_functions and pattern.get("id") in [
            "single_function_dominates",
            "top_functions_concentration",
            "hot_function_high_call_count",
        ]:
            return top_functions[0].get("function")
        return None

    def _confidence(self, evidence: Dict[str, Any], pattern: Dict) -> float:
        """计算置信度。"""
        if not evidence:
            return 0.0
        
        base_confidence = 0.5
        evidence_count = len([k for k in evidence.keys() if not k.endswith("_count")])
        
        # 基于证据数量增加置信度
        confidence = min(1.0, base_confidence + 0.1 * evidence_count)
        
        # 特殊模式可能有不同的置信度计算
        pattern_id = pattern.get("id", "")
        if "trend" in pattern_id or "ratio" in pattern_id:
            # 趋势和比例分析需要更多证据
            confidence = min(confidence, 0.9)
        
        return confidence
