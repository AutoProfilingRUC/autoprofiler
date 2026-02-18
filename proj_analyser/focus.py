"""
Focus planner for proj-analyser.

Heuristics are adapted from `Your proj sucks` focus strategy:
entrypoint-biased scoring + query-biased ranking + token-budget selection.
"""
from __future__ import annotations

from typing import Dict, List


BUILD_OR_CONFIG = {
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "package.json",
    "go.mod",
    "cargo.toml",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "pom.xml",
    "build.gradle",
    "makefile",
    ".env",
}

CORE_CODE_PREFIXES = (
    "autoprofiler/",
    "analysis/",
    "api/",
    "proj_analyser/",
    "models/",
    "utils/",
)

LOW_SIGNAL_PREFIXES = (
    "tests/",
    "docs/",
    "uploads/",
    "static/",
    "templates/",
)

LOW_SIGNAL_LANGUAGES = {"markdown", "json"}


def estimate_file_tokens(size_bytes: int, bytes_per_token: int) -> int:
    bpt = max(1, int(bytes_per_token))
    size = max(0, int(size_bytes))
    return max(1, (size + bpt - 1) // bpt)


def _add_score(score_map: Dict[str, Dict], path: str, delta: float, reason: str) -> None:
    if not path:
        return
    item = score_map.setdefault(path, {"score": 0.0, "reasons": []})
    item["score"] += float(delta)
    if len(item["reasons"]) < 8 and reason not in item["reasons"]:
        item["reasons"].append(reason)


def _path_quality_adjustment(path: str) -> tuple[float, str]:
    p = (path or "").lower()
    if not p:
        return 0.0, ""

    for prefix in CORE_CODE_PREFIXES:
        if p.startswith(prefix):
            return 22.0, "core_code_priority"

    for prefix in LOW_SIGNAL_PREFIXES:
        if p.startswith(prefix):
            return -30.0, "low_signal_path_penalty"

    if "/fixtures/" in p:
        return -18.0, "fixture_path_penalty"

    return 0.0, ""


def _is_low_signal_path(path: str) -> bool:
    p = (path or "").lower()
    for prefix in LOW_SIGNAL_PREFIXES:
        if p.startswith(prefix):
            return True
    return False


def build_focus_plan(
    scan_result: Dict,
    query_terms: List[str],
    top_files: int = 12,
    token_budget: int = 12000,
    bytes_per_token: int = 4,
) -> Dict:
    files = scan_result.get("files", [])
    top_files = max(1, int(top_files))
    token_budget = max(1, int(token_budget))
    bytes_per_token = max(1, int(bytes_per_token))

    file_by_path = {f.get("path"): f for f in files if f.get("path")}
    score_map: Dict[str, Dict] = {}

    entrypoints_seed = scan_result.get("entrypoints_primary") or scan_result.get("entrypoints_top", [])
    for ep in entrypoints_seed:
        path = ep.get("file_path")
        score = ep.get("score", 0)
        base = 80.0 + float(score)
        if _is_low_signal_path(path):
            base = max(5.0, base * 0.15)
            _add_score(score_map, path, base, "entrypoint_low_signal_scaled")
        else:
            _add_score(score_map, path, base, f"entrypoint:score={score}")

    for item in files:
        path = item.get("path", "")
        if not path:
            continue
        adj, reason = _path_quality_adjustment(path)
        if adj != 0 and reason:
            _add_score(score_map, path, adj, reason)

        language = (item.get("language") or "").lower()
        if language in LOW_SIGNAL_LANGUAGES:
            _add_score(score_map, path, -18.0, "low_signal_language_penalty")

        lower_name = path.lower().split("/")[-1]
        if lower_name in BUILD_OR_CONFIG:
            _add_score(score_map, path, 14.0, "build_or_config_file")

    cleaned_terms = [t.strip().lower() for t in (query_terms or []) if t and t.strip()]
    for term in cleaned_terms:
        hits = []
        for item in files:
            path = item.get("path", "")
            if not path:
                continue
            score = 0.0
            path_low = path.lower()
            preview = (item.get("preview_text") or "").lower()
            language = (item.get("language") or "").lower()
            if term in path_low:
                score += 40.0
            if term in preview:
                score += 28.0
            if language in LOW_SIGNAL_LANGUAGES:
                score *= 0.25
            if score > 0:
                hits.append((path, score))
        hits.sort(key=lambda x: x[1], reverse=True)
        for idx, (path, hit_score) in enumerate(hits[: top_files * 8]):
            boost = max(4.0, hit_score / (idx + 1))
            _add_score(score_map, path, boost, f"query:{term}#{idx + 1}")

    ranked = []
    for path, meta in score_map.items():
        f = file_by_path.get(path, {})
        size = int(f.get("size_bytes", 0))
        token_estimate = estimate_file_tokens(size, bytes_per_token)
        ranked.append(
            {
                "path": path,
                "score": round(float(meta["score"]), 2),
                "size_bytes": size,
                "token_estimate": token_estimate,
                "reasons": meta["reasons"],
            }
        )

    if not ranked:
        for item in files[:top_files]:
            size = int(item.get("size_bytes", 0))
            ranked.append(
                {
                    "path": item.get("path", ""),
                    "score": 1.0,
                    "size_bytes": size,
                    "token_estimate": estimate_file_tokens(size, bytes_per_token),
                    "reasons": ["fallback:first_files"],
                }
            )

    ranked.sort(key=lambda x: (-x["score"], x["path"]))
    ranked_head = ranked[:top_files]

    selected = []
    selected_tokens = 0
    for item in ranked:
        if len(selected) >= top_files:
            break
        next_tokens = selected_tokens + item["token_estimate"]
        if next_tokens > token_budget:
            if not selected:
                selected.append(item)
                selected_tokens = next_tokens
            continue
        selected.append(item)
        selected_tokens = next_tokens

    if not selected and ranked:
        selected = [ranked[0]]
        selected_tokens = ranked[0]["token_estimate"]

    # Approximate non-file prompt/context overhead to keep budgeting conservative.
    context_tokens_estimate = (
        450
        + len(cleaned_terms) * 12
        + len(scan_result.get("language_distribution", [])) * 18
        + len(scan_result.get("entrypoints_top", [])) * 24
        + len(scan_result.get("top_level_overview", [])) * 20
        + len(scan_result.get("directories_top", [])) * 16
    )
    selected_plus_agent_tokens_estimate = selected_tokens + int(context_tokens_estimate)

    return {
        "strategy": "entrypoint_query_budgeted_selection",
        "inputs": {
            "top_files": top_files,
            "token_budget": token_budget,
            "bytes_per_token": bytes_per_token,
            "query_terms": cleaned_terms,
        },
        "ranked_files": ranked_head,
        "selected_files": selected,
        "summary": {
            "candidate_files": len(ranked),
            "ranked_count": len(ranked_head),
            "selected_count": len(selected),
            "selected_tokens_estimate": selected_tokens,
            "selected_plus_agent_tokens_estimate": selected_plus_agent_tokens_estimate,
        },
    }
