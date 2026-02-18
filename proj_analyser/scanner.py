"""
Project scanner used by proj-analyser.

Design adapted from the indexing/focus pre-step in `Your proj sucks`:
keep a lightweight project summary and entrypoint candidates for targeted reading.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List


LANGUAGE_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".kt": "kotlin",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
    ".scala": "scala",
    ".sql": "sql",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".md": "markdown",
}

SKIP_DIRS = {
    ".git",
    ".svn",
    ".hg",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "target",
    ".mypy_cache",
    ".pytest_cache",
    "uploads",
    ".autoprofiler_proj_analyser",
}

ENTRYPOINT_NAMES = {
    "main.py",
    "app.py",
    "server.py",
    "manage.py",
    "__main__.py",
    "index.js",
    "index.ts",
    "main.go",
    "main.rs",
    "program.cs",
}

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
}


LOW_SIGNAL_ENTRYPOINT_HINTS = (
    "/tests/",
    "/test/",
    "/fixtures/",
    "/demo/",
    "/demos/",
    "/example/",
    "/examples/",
    "/sample/",
    "/samples/",
    "/benchmark/",
    "/benchmarks/",
)


def _is_probably_text(path: Path) -> bool:
    ext = path.suffix.lower()
    if ext in LANGUAGE_BY_EXT:
        return True
    return path.name.lower() in BUILD_OR_CONFIG


def _detect_language(path: Path) -> str:
    return LANGUAGE_BY_EXT.get(path.suffix.lower(), "unknown")


def _read_preview(path: Path, max_chars: int = 2000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    if len(text) > max_chars:
        return text[:max_chars]
    return text


def _is_low_signal_entrypoint_path(path_str: str) -> bool:
    normalized = "/" + (path_str or "").replace("\\", "/").strip("/").lower() + "/"
    for hint in LOW_SIGNAL_ENTRYPOINT_HINTS:
        if hint in normalized:
            return True
    file_name = normalized.strip("/").split("/")[-1]
    return file_name.startswith("test_")


def _entrypoint_score(path_str: str, preview_text: str) -> Dict:
    score = 0
    reasons: List[str] = []
    normalized = (path_str or "").replace("\\", "/")
    name = normalized.split("/")[-1].lower()
    path_low = normalized.lower()

    if name in ENTRYPOINT_NAMES:
        score += 70
        reasons.append(f"entrypoint_filename:{name}")

    if "/cmd/" in path_low or "/bin/" in path_low:
        score += 24
        reasons.append("entrypoint_directory")

    text_low = preview_text.lower()
    if "if __name__ == '__main__'" in text_low or 'if __name__ == "__main__"' in text_low:
        score += 40
        reasons.append("python_main_guard")
    if "flask(" in text_low or "app.run(" in text_low:
        score += 20
        reasons.append("web_bootstrap")
    if "fastapi(" in text_low or "uvicorn.run(" in text_low:
        score += 20
        reasons.append("asgi_bootstrap")
    if "def main(" in text_low or "fn main(" in text_low:
        score += 20
        reasons.append("main_symbol")

    # De-prioritize tests/demos/examples as primary runtime entrypoints.
    if _is_low_signal_entrypoint_path(path_low):
        score = max(0, score - 60)
        reasons.append("low_signal_entrypoint_path_penalty")

    return {"score": score, "reasons": reasons}


def scan_project(
    repo_root: str,
    max_file_mb: int = 4,
    max_files: int = 3000,
) -> Dict:
    """Lightweight recursive project scan with language and entrypoint metadata."""
    root = Path(repo_root).resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"项目路径不存在或不是目录: {repo_root}")

    max_bytes = max(1, int(max_file_mb)) * 1024 * 1024
    files = []
    language_stats: Dict[str, Dict[str, int]] = {}
    entrypoints = []
    top_level_stats: Dict[str, Dict[str, int]] = {}
    directory_stats: Dict[str, Dict[str, int]] = {}
    scanned_count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        if scanned_count >= max_files:
            break
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for filename in filenames:
            if scanned_count >= max_files:
                break
            path = Path(dirpath) / filename
            if not _is_probably_text(path):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > max_bytes:
                continue

            rel = path.relative_to(root).as_posix()
            language = _detect_language(path)
            preview = _read_preview(path)
            ep = _entrypoint_score(rel, preview)

            file_item = {
                "path": rel,
                "size_bytes": size,
                "language": language,
                "preview_text": preview,
                "is_entrypoint": ep["score"] > 0,
                "entrypoint_score": ep["score"],
                "entrypoint_reasons": ep["reasons"],
            }
            files.append(file_item)
            scanned_count += 1

            parts = rel.split("/")
            top_key = parts[0] if len(parts) > 1 else "."
            top_stat = top_level_stats.setdefault(top_key, {"files": 0, "bytes": 0})
            top_stat["files"] += 1
            top_stat["bytes"] += size

            dir_key = "/".join(parts[:-1]) if len(parts) > 1 else "."
            dir_stat = directory_stats.setdefault(dir_key, {"files": 0, "bytes": 0})
            dir_stat["files"] += 1
            dir_stat["bytes"] += size

            if ep["score"] > 0:
                low_signal_ep = _is_low_signal_entrypoint_path(rel)
                entrypoints.append(
                    {
                        "file_path": rel,
                        "score": ep["score"],
                        "reason": ep["reasons"],
                        "low_signal_path": low_signal_ep,
                    }
                )

            st = language_stats.setdefault(language, {"files": 0, "bytes": 0})
            st["files"] += 1
            st["bytes"] += size

    language_distribution = [
        {"language": k, "files": v["files"], "size_bytes": v["bytes"]}
        for k, v in language_stats.items()
    ]
    language_distribution.sort(key=lambda x: (x["files"], x["size_bytes"]), reverse=True)

    top_level_overview = [
        {"path": k, "files": v["files"], "size_bytes": v["bytes"]}
        for k, v in top_level_stats.items()
    ]
    top_level_overview.sort(key=lambda x: (x["files"], x["size_bytes"]), reverse=True)

    directories_top = [
        {"path": k, "files": v["files"], "size_bytes": v["bytes"]}
        for k, v in directory_stats.items()
    ]
    directories_top.sort(key=lambda x: (x["files"], x["size_bytes"]), reverse=True)

    entrypoints.sort(key=lambda x: x["score"], reverse=True)
    entrypoints_primary = [x for x in entrypoints if not x.get("low_signal_path")]
    entrypoints_low_signal = [x for x in entrypoints if x.get("low_signal_path")]

    return {
        "repo_root": str(root),
        "summary": {
            "files_scanned": len(files),
            "entrypoints_found": len(entrypoints),
            "entrypoints_primary_found": len(entrypoints_primary),
            "entrypoints_low_signal_found": len(entrypoints_low_signal),
            "total_size_bytes": sum(i["size_bytes"] for i in files),
        },
        "top_level_overview": top_level_overview[:20],
        "directories_top": directories_top[:30],
        "language_distribution": language_distribution,
        "entrypoints_primary": entrypoints_primary[:20],
        "entrypoints_low_signal": entrypoints_low_signal[:20],
        "entrypoints_top": entrypoints[:20],
        "files": files,
    }
