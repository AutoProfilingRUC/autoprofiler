import os
import platform
import subprocess
import sys
from pathlib import Path


def run(cmd, cwd=None):
    print(f"[cmd] {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=cwd)


def _is_linux() -> bool:
    return platform.system().lower().startswith("linux")


def print_linux_prerequisites() -> None:
    print("[hint] Linux prerequisite packages (Debian/Ubuntu):")
    print("       sudo apt update")
    print(
        "       sudo apt install -y python3-venv python3-pip "
        "libcairo2 libpango-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info"
    )


def ensure_pip_in_venv(venv_python: Path) -> None:
    try:
        run([str(venv_python), "-m", "pip", "--version"])
        return
    except subprocess.CalledProcessError:
        print("[warn] pip is unavailable in the virtual environment, trying ensurepip...")

    try:
        run([str(venv_python), "-m", "ensurepip", "--upgrade"])
        run([str(venv_python), "-m", "pip", "--version"])
    except subprocess.CalledProcessError:
        print("[error] Failed to bootstrap pip inside virtual environment.")
        if _is_linux():
            print_linux_prerequisites()
        sys.exit(1)


def check_weasyprint_runtime(venv_python: Path) -> None:
    """Best-effort check for WeasyPrint runtime availability."""
    check_cmd = [str(venv_python), "-c", "import weasyprint; print('weasyprint-runtime-ok')"]
    try:
        run(check_cmd)
    except subprocess.CalledProcessError:
        print("[warn] WeasyPrint is installed, but runtime libraries are missing.")
        if platform.system().lower().startswith("win"):
            print("[warn] On Windows, install GTK3 runtime for PDF export support.")
            print("[warn] Expected default path: C:\\Program Files\\GTK3-Runtime Win64\\bin")
        elif _is_linux():
            print("[warn] On Linux, ensure cairo/pango related runtime libs are installed.")
            print_linux_prerequisites()


def main():
    project_root = Path(__file__).resolve().parents[1]
    venv_dir = project_root / ".venv"
    req_file = project_root / "requirements.txt"

    if not req_file.exists():
        print(f"[error] requirements.txt not found at: {req_file}")
        sys.exit(1)

    python = sys.executable

    # 1) create venv if not exists
    if not venv_dir.exists():
        print(f"[info] Creating venv at {venv_dir}")
        try:
            run([python, "-m", "venv", str(venv_dir)])
        except subprocess.CalledProcessError:
            print("[error] Failed to create virtual environment.")
            if _is_linux():
                print("[hint] `python3-venv` may be missing.")
                print_linux_prerequisites()
            sys.exit(1)
    else:
        print(f"[info] venv already exists at {venv_dir}")

    # 2) locate venv python
    if platform.system().lower().startswith("win"):
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    if not venv_python.exists():
        print(f"[error] venv python not found at: {venv_python}")
        sys.exit(1)

    ensure_pip_in_venv(venv_python)

    # 3) upgrade pip + install requirements
    try:
        run([str(venv_python), "-m", "pip", "install", "-U", "pip"])
    except subprocess.CalledProcessError:
        print("[warn] Failed to upgrade pip. Will continue with current pip version.")
        if _is_linux():
            print("[hint] If this keeps failing, check network/proxy or internal mirror settings.")

    try:
        run([str(venv_python), "-m", "pip", "install", "-r", str(req_file)])
    except subprocess.CalledProcessError:
        print("[error] Failed to install required packages from requirements.txt.")
        if _is_linux():
            print_linux_prerequisites()
            print("[hint] You can retry manually:")
            print(f"       {venv_python} -m pip install -r {req_file}")
        sys.exit(1)

    # 4) optional runtime check
    check_weasyprint_runtime(venv_python)

    print("\n[ok] Environment ready.")
    if platform.system().lower().startswith("win"):
        print(f"Activate: {venv_dir}\\Scripts\\activate")
    else:
        print(f"Activate: source {venv_dir}/bin/activate")

    print("\nNext:")
    print(f"  cd {project_root}")
    if platform.system().lower().startswith("win"):
        print("  .\\.venv\\Scripts\\activate")
    else:
        print("  source .venv/bin/activate")
    print("  python -m unittest tests.test_autoprofiler_template")


if __name__ == "__main__":
    main()
