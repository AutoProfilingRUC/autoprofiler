"""
Deterministic analyzer that matches collector metrics against declarative patterns.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from ..models import Finding, ProfileArtifact
from .base import Analyzer


class PatternMatchingAnalyzer(Analyzer):
    """Analyzer that evaluates numeric thresholds defined in patterns."""

    def __init__(self, patterns: List[Dict]) -> None:
        self.patterns = patterns

    def analyze(self, artifacts: Iterable[ProfileArtifact]) -> List[Finding]:
        findings: List[Finding] = []
        artifact_list = list(artifacts)
        for artifact_index, artifact in enumerate(artifact_list):
            merged_metrics = self._merge_metrics(artifact)
            for pattern in self.patterns:
                if not self._category_matches(artifact, pattern):
                    continue

                matches, evidence = self._matches_pattern(merged_metrics, pattern)
                if not matches:
                    continue

                finding_id = f"finding_{artifact_index}_{pattern['id']}"
                summary = pattern.get("meaning", "Pattern match detected")
                suggestions = list(pattern.get("suggestions", []))
                confidence = self._confidence(evidence)
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

    def _merge_metrics(self, artifact: ProfileArtifact) -> Dict[str, float]:
        merged: Dict[str, float] = {}
        for key, value in artifact.metrics.items():
            try:
                merged[key] = float(value)
            except (TypeError, ValueError):
                continue
            namespaced = f"{artifact.category}.{key}"
            merged[namespaced] = merged[key]
        return merged

    def _category_matches(self, artifact: ProfileArtifact, pattern: Dict) -> bool:
        pattern_category = pattern.get("category")
        return pattern_category is None or pattern_category == artifact.category

    def _matches_pattern(
        self, metrics: Dict[str, float], pattern: Dict
    ) -> Tuple[bool, Dict[str, float]]:
        evidence: Dict[str, float] = {}
        conditions: Dict[str, str] = pattern.get("condition", {})
        for metric_name, rule in conditions.items():
            if metric_name not in metrics:
                return False, evidence
            value = float(metrics[metric_name])
            if not self._evaluate_rule(value, rule):
                return False, evidence
            evidence[metric_name] = value
        return True, evidence

    def _evaluate_rule(self, value: float, rule: str) -> bool:
        rule = rule.strip()
        if rule.startswith(">="):
            return value >= float(rule[2:])
        if rule.startswith("<="):
            return value <= float(rule[2:])
        if rule.startswith(">"):
            return value > float(rule[1:])
        if rule.startswith("<"):
            return value < float(rule[1:])
        return value == float(rule)

    def _confidence(self, evidence: Dict[str, float]) -> float:
        # 中英文注释: 简单的置信度估计基于证据数量 (confidence derives from evidence breadth)
        if not evidence:
            return 0.0
        count = len(evidence)
        return min(1.0, 0.5 + 0.1 * count)
