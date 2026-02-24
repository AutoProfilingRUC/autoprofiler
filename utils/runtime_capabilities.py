"""
Runtime capability detection for cross-platform feature gating.
"""
from __future__ import annotations

import copy
import importlib.util
import platform
import shutil
import sys
import os
from pathlib import Path
from typing import Any, Dict, Optional


_CAPABILITY_CACHE: Optional[Dict[str, Any]] = None


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _command_available(command_name: str) -> bool:
    return shutil.which(command_name) is not None


def configure_windows_gtk_runtime() -> Optional[str]:
    """
    Prepare GTK runtime search path for WeasyPrint on Windows.
    Returns the effective GTK bin path if found.
    """
    if sys.platform != "win32":
        return None

    candidates = []
    custom_bin = os.environ.get("GTK_RUNTIME_BIN")
    if custom_bin:
        candidates.append(Path(custom_bin))

    candidates.extend(
        [
            Path(r"C:\Program Files\GTK3-Runtime Win64\bin"),
            Path(r"C:\Program Files\GTK3 Runtime Win64\bin"),
            Path(r"C:\Program Files\GTK3-Runtime\bin"),
            Path(r"C:\Program Files\GTK3 Runtime\bin"),
            Path(r"C:\GTK3-Runtime Win64\bin"),
        ]
    )

    for candidate in candidates:
        if not candidate.exists():
            continue

        candidate_str = str(candidate)
        current_path = os.environ.get("PATH", "")
        if candidate_str not in current_path.split(os.pathsep):
            os.environ["PATH"] = (
                f"{candidate_str}{os.pathsep}{current_path}" if current_path else candidate_str
            )

        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(candidate_str)
            except OSError:
                pass
        return candidate_str

    return None


def _detect_pdf_export_capability() -> Dict[str, Any]:
    if not _module_available("markdown"):
        return {"available": False, "reason": "python package `markdown` not installed"}
    if not _module_available("weasyprint"):
        return {"available": False, "reason": "python package `weasyprint` not installed"}

    if sys.platform == "win32":
        configure_windows_gtk_runtime()

    try:
        from weasyprint import HTML  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"WeasyPrint runtime unavailable: {exc}"}

    _ = HTML
    return {"available": True, "reason": ""}


def detect_runtime_capabilities() -> Dict[str, Any]:
    platform_name = platform.system().lower()
    modules = {
        "flask": _module_available("flask"),
        "requests": _module_available("requests"),
        "psutil": _module_available("psutil"),
        "markdown": _module_available("markdown"),
        "weasyprint": _module_available("weasyprint"),
    }
    commands = {
        "perf": _command_available("perf"),
        "py-spy": _command_available("py-spy"),
    }
    pdf_feature = _detect_pdf_export_capability()

    perf_reason = ""
    perf_available = platform_name == "linux" and commands["perf"]
    if not perf_available:
        if platform_name != "linux":
            perf_reason = "perf collector is Linux-only"
        else:
            perf_reason = "`perf` not found in PATH"

    pyspy_reason = ""
    if not commands["py-spy"]:
        pyspy_reason = "`py-spy` not found in PATH"

    return {
        "environment": {
            "platform": platform_name,
            "platform_release": platform.release(),
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
        },
        "modules": modules,
        "commands": commands,
        "features": {
            "single_file_static_analysis": {"available": True, "reason": ""},
            "single_file_python_runtime": {
                "available": True,
                "reason": "",
                "python_executable": sys.executable,
            },
            "project_api_analysis": {"available": True, "reason": ""},
            "pdf_export": pdf_feature,
            "perf_collector": {"available": perf_available, "reason": perf_reason},
            "pyspy_collector": {"available": commands["py-spy"], "reason": pyspy_reason},
        },
    }


def clear_runtime_capabilities_cache() -> None:
    global _CAPABILITY_CACHE
    _CAPABILITY_CACHE = None


def get_runtime_capabilities(refresh: bool = False) -> Dict[str, Any]:
    global _CAPABILITY_CACHE
    if refresh or _CAPABILITY_CACHE is None:
        _CAPABILITY_CACHE = detect_runtime_capabilities()
    return copy.deepcopy(_CAPABILITY_CACHE)
