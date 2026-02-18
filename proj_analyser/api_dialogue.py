"""
Incremental API dialogue runner for proj-analyser.

Core ideas adapted from `Your proj sucks`:
- strict JSON action protocol (`need_files` / `final_report`)
- loose JSON extraction for unstable model outputs
- targeted file segment serving to minimize token usage
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import requests


def _resolve_output_language(runtime_config: Dict) -> str:
    lang = str((runtime_config or {}).get("output_language", "zh")).strip().lower()
    if lang.startswith("en"):
        return "en"
    return "zh"


def extract_loose_json_object(text: str) -> Optional[Dict]:
    if not text:
        return None
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    if "```json" in text:
        body = text.split("```json", 1)[1]
        body = body.split("```", 1)[0].strip()
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    start = None
    depth = 0
    in_str = False
    escaped = False
    for idx, ch in enumerate(text):
        if in_str:
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            if start is None:
                start = idx
            depth += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                candidate = text[start : idx + 1]
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass
    return None


def _extract_chat_content(payload: Dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            text = item.get("text") if isinstance(item, dict) else None
            if text:
                parts.append(text)
        return "\n".join(parts)
    return ""


def _resolve_chat_endpoint(api_url: str) -> str:
    base = (api_url or "").strip().rstrip("/")
    if not base:
        return "https://api.deepseek.com/v1/chat/completions"
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def call_chat_api_openai_compatible(
    runtime_config: Dict,
    messages: List[Dict],
    temperature: float,
    max_output_tokens: int,
) -> str:
    output_language = _resolve_output_language(runtime_config)
    if os.environ.get("PROJ_ANALYSER_FAKE_CHAT") == "1":
        if len(messages) <= 2:
            return json.dumps(
                {
                    "action": "need_files",
                    "reason": "Need entrypoint and one service file first",
                    "files": [
                        {"path": "web.py", "why": "entrypoint", "start_line": 1, "end_line": 180},
                        {"path": "analysis/task.py", "why": "performance flow", "start_line": 1, "end_line": 220},
                    ],
                },
                ensure_ascii=False,
            )
        fake_report = (
            "## 项目性能分析报告\n\n"
            "- 已完成 Fake 模式增量分析。\n"
            "- 请移除 `PROJ_ANALYSER_FAKE_CHAT=1` 并配置真实 API key 以获得真实结果。\n"
        )
        if output_language == "en":
            fake_report = (
                "## Project Performance Report\n\n"
                "- Fake mode incremental analysis completed.\n"
                "- Remove `PROJ_ANALYSER_FAKE_CHAT=1` and configure a real API key for actual results.\n"
            )
        return json.dumps(
            {
                "action": "final_report",
                "title": "Project Performance Report",
                "report_markdown": fake_report,
            },
            ensure_ascii=False,
        )

    endpoint = _resolve_chat_endpoint(
        runtime_config.get("api_url", "https://api.deepseek.com/v1/chat/completions")
    )
    api_key = (runtime_config or {}).get("api_key", "")
    body = {
        "model": runtime_config.get("model", "deepseek-chat"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_output_tokens,
    }
    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    response = requests.post(
        endpoint,
        headers=headers,
        json=body,
        timeout=90,
    )
    payload = {}
    try:
        payload = response.json()
    except Exception:
        payload = {"raw": response.text}

    if response.status_code != 200:
        raise RuntimeError(f"api_http_error: status={response.status_code} body={payload}")

    content = _extract_chat_content(payload).strip()
    if not content:
        raise RuntimeError("api_empty_content")
    return content


def _sanitize_requested_path(requested: str) -> str:
    path = (requested or "").strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    if not path or ".." in path:
        return ""
    return path


def _resolve_requested_file(file_index: Dict[str, Dict], requested_path: str) -> Optional[str]:
    req = _sanitize_requested_path(requested_path)
    if not req:
        return None
    if req in file_index:
        return req
    suffix = "/" + req
    matches = [p for p in file_index if p.endswith(suffix)]
    if matches:
        return sorted(matches, key=len)[0]
    return None


def read_file_segment(
    repo_root: str,
    file_index: Dict[str, Dict],
    requested_path: str,
    start_line: Optional[int],
    end_line: Optional[int],
    max_chars: int,
) -> Dict:
    resolved = _resolve_requested_file(file_index, requested_path)
    if not resolved:
        return {"requested_path": requested_path, "status": "not_found"}

    full = Path(repo_root) / resolved
    try:
        raw = full.read_text(encoding="utf-8", errors="ignore")
    except Exception as err:
        return {"path": resolved, "status": "read_failed", "error": str(err)}

    lines = raw.splitlines()
    if not lines:
        return {
            "path": resolved,
            "status": "ok",
            "start_line": 1,
            "end_line": 0,
            "truncated": False,
            "size_bytes": full.stat().st_size if full.exists() else 0,
            "content": "",
        }

    s = max(1, int(start_line or 1))
    e = max(s, int(end_line or (s + 200)))
    s = min(s, len(lines))
    e = min(e, len(lines))

    content = "\n".join(lines[s - 1 : e])
    truncated = False
    if len(content) > max_chars:
        content = content[:max_chars]
        truncated = True

    return {
        "path": resolved,
        "status": "ok",
        "start_line": s,
        "end_line": e,
        "truncated": truncated,
        "size_bytes": full.stat().st_size if full.exists() else 0,
        "content": content,
    }


def run_api_dialogue(
    repo_root: str,
    scan_result: Dict,
    focus_plan: Dict,
    runtime_config: Dict,
    query_terms: List[str],
    max_rounds: int = 6,
    max_file_chars: int = 4000,
    temperature: float = 0.1,
    max_output_tokens: int = 2200,
) -> Dict:
    max_rounds = max(1, int(max_rounds))
    max_file_chars = max(500, int(max_file_chars))
    output_language = _resolve_output_language(runtime_config)
    file_index = {f["path"]: f for f in scan_result.get("files", []) if f.get("path")}

    system_prompt = (
        "You are a senior performance engineer for complex software projects, working with a local orchestrator. "
        "Return ONLY one valid JSON object each turn.\n"
        "Actions:\n"
        '1) {"action":"need_files","reason":"...","files":[{"path":"...","why":"...","start_line":1,"end_line":200}]}\n'
        '2) {"action":"final_report","title":"...","report_markdown":"..."}\n'
        "Rules:\n"
        "- Focus on performance bottlenecks in medium/large projects.\n"
        "- Minimize token usage. Request only strictly needed files and narrow ranges.\n"
        "- Prefer `entrypoints_primary`; treat tests/demos/examples/fixtures as low-confidence unless evidence requires them.\n"
        "- Final report must include: bottleneck list (priority P0/P1/P2), evidence (file+line), impact, and concrete optimization actions.\n"
        "- Prefer actionable advice for CPU/memory/IO/DB/network/concurrency hotspots.\n"
        "- Write final_report.report_markdown in English.\n"
        "- Do not include markdown fences around JSON."
    )
    task_text = "Analyze this repository for performance bottlenecks and produce a practical optimization report."
    format_reminder = "Respond with JSON action only."
    invalid_json_retry = (
        "Your previous response was invalid/incomplete JSON. Re-send ONE complete JSON object only."
    )
    invalid_report_retry = (
        "final_report must include non-empty report_markdown. Re-send ONE complete JSON object only."
    )
    continue_instruction = (
        "Continue performance analysis. If sufficient evidence exists, return action=final_report."
    )
    timeout_report = "# Project Performance Report\n\nModel did not return `final_report` within max rounds."
    invalid_json_report = (
        "# Project Performance Report\n\nModel returned incomplete JSON in multiple rounds.\n\n"
        "Try increasing `max_output_tokens` and retry."
    )

    if output_language == "zh":
        system_prompt = (
            "你是一名资深性能工程师，正在与本地编排器协作分析复杂软件项目。"
            "每轮仅返回一个合法 JSON 对象。\n"
            "动作：\n"
            '1) {"action":"need_files","reason":"...","files":[{"path":"...","why":"...","start_line":1,"end_line":200}]}\n'
            '2) {"action":"final_report","title":"...","report_markdown":"..."}\n'
            "规则：\n"
            "- 聚焦中大型项目的性能瓶颈。\n"
            "- 严格控制 token，仅读取必要文件和尽量窄的行范围。\n"
            "- 优先参考 `entrypoints_primary`；tests/demos/examples/fixtures 仅作低置信候选，除非证据要求。\n"
            "- 最终报告必须包含：瓶颈清单（P0/P1/P2）、证据（文件+行号）、影响评估、可执行优化动作。\n"
            "- 优先给出 CPU/内存/IO/数据库/网络/并发热点的可落地建议。\n"
            "- final_report.report_markdown 必须使用中文。\n"
            "- 不要输出 Markdown 代码围栏。"
        )
        task_text = "分析该仓库的性能瓶颈，并输出可执行的优化报告。"
        format_reminder = "仅返回 JSON action。"
        invalid_json_retry = "你上一轮返回的 JSON 不完整或不合法。请只返回一个完整 JSON 对象。"
        invalid_report_retry = "final_report 必须包含非空 report_markdown。请只返回一个完整 JSON 对象。"
        continue_instruction = "继续进行性能分析；若证据充分请直接返回 action=final_report。"
        timeout_report = "# 项目性能分析报告\n\n在最大轮次内未收到 `final_report`。"
        invalid_json_report = (
            "# 项目性能分析报告\n\n模型多轮返回了不完整 JSON，未能得到完整最终报告。\n\n"
            "建议提高 `max_output_tokens` 后重试。"
        )

    selected_files = focus_plan.get("selected_files", [])
    bootstrap_payload = {
        "task": task_text,
        "constraints": {
            "token_minimization": True,
            "max_rounds": max_rounds,
            "prefer_targeted_ranges": True,
        },
        "output_language": output_language,
        "query_terms": query_terms,
        "repo_context": {
            "summary": scan_result.get("summary", {}),
            "top_level_overview": scan_result.get("top_level_overview", []),
            "directories_top": scan_result.get("directories_top", []),
            "language_distribution": scan_result.get("language_distribution", []),
            "entrypoints_primary": scan_result.get("entrypoints_primary", []),
            "entrypoints_top": scan_result.get("entrypoints_top", []),
            "entrypoints_low_signal_count": len(scan_result.get("entrypoints_low_signal", [])),
        },
        "focus_plan": {
            "selected_files": selected_files,
            "selected_tokens_estimate": focus_plan.get("summary", {}).get(
                "selected_tokens_estimate", 0
            ),
            "selected_plus_agent_tokens_estimate": focus_plan.get("summary", {}).get(
                "selected_plus_agent_tokens_estimate", 0
            ),
        },
        "format_reminder": format_reminder,
    }

    messages: List[Dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(bootstrap_payload, ensure_ascii=False, indent=2)},
    ]

    logs = []
    invalid_json_turns = 0
    final_report = None

    for round_id in range(1, max_rounds + 1):
        raw = call_chat_api_openai_compatible(
            runtime_config=runtime_config,
            messages=messages,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        action = extract_loose_json_object(raw)
        if not action:
            invalid_json_turns += 1
            logs.append(
                {
                    "round": round_id,
                    "assistant_action": "invalid_json",
                    "raw_preview": raw[:320],
                }
            )
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        invalid_json_retry
                    ),
                }
            )
            continue

        action_name = action.get("action", "final_report")
        if action_name == "final_report":
            markdown = str(action.get("report_markdown") or "").strip()
            if not markdown:
                invalid_json_turns += 1
                logs.append(
                    {
                        "round": round_id,
                        "assistant_action": "invalid_final_report",
                        "reason": "missing report_markdown",
                    }
                )
                messages.append({"role": "assistant", "content": raw})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            invalid_report_retry
                        ),
                    }
                )
                continue
            final_report = markdown
            logs.append(
                {
                    "round": round_id,
                    "assistant_action": "final_report",
                    "title": action.get("title", "Project Performance Report"),
                }
            )
            break

        snippets = []
        sent_chars = 0
        for f in (action.get("files") or [])[:8]:
            requested = f.get("path") if isinstance(f, dict) else None
            if not requested:
                continue
            snippet = read_file_segment(
                repo_root=repo_root,
                file_index=file_index,
                requested_path=requested,
                start_line=f.get("start_line") if isinstance(f, dict) else None,
                end_line=f.get("end_line") if isinstance(f, dict) else None,
                max_chars=max_file_chars,
            )
            sent_chars += len(snippet.get("content", ""))
            snippets.append(snippet)
            if sent_chars >= max_file_chars * 3:
                break

        if not snippets and selected_files:
            fallback = selected_files[0].get("path")
            if fallback:
                snippets.append(
                    read_file_segment(
                        repo_root=repo_root,
                        file_index=file_index,
                        requested_path=fallback,
                        start_line=1,
                        end_line=220,
                        max_chars=max_file_chars,
                    )
                )

        logs.append(
            {
                "round": round_id,
                "assistant_action": "need_files",
                "assistant_reason": action.get("reason", ""),
                "provided_count": len(snippets),
                "provided_paths": [s.get("path") for s in snippets if s.get("path")],
                "sent_chars": sent_chars,
            }
        )
        messages.append({"role": "assistant", "content": raw})
        messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "round": round_id,
                        "provided_files": snippets,
                        "instruction": continue_instruction,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            }
        )

    if not final_report:
        if invalid_json_turns > 0:
            final_report = invalid_json_report
        else:
            final_report = timeout_report

    return {
        "report_markdown": final_report,
        "rounds": len(logs),
        "logs": logs,
    }
