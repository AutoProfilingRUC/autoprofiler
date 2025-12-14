import os
import platform
import subprocess
import sys
from pathlib import Path


def run(cmd, cwd=None):
    print(f"[cmd] {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=cwd)


def main():
    project_root = Path(__file__).resolve().parents[1]  # tests/Autoprof
    venv_dir = project_root / ".venv"
    req_file = project_root / "requirements.txt"

    if not req_file.exists():
        print(f"[error] requirements.txt not found at: {req_file}")
        sys.exit(1)

    python = sys.executable

    # 1) create venv if not exists
    if not venv_dir.exists():
        print(f"[info] Creating venv at {venv_dir}")
        run([python, "-m", "venv", str(venv_dir)])
    else:
        print(f"[info] venv already exists at {venv_dir}")

    # 2) locate venv python
    if platform.system().lower().startswith("win"):
        venv_python = venv_dir / "Scripts" / "python.exe"
        venv_pip = venv_dir / "Scripts" / "pip.exe"
    else:
        venv_python = venv_dir / "bin" / "python"
        venv_pip = venv_dir / "bin" / "pip"

    if not venv_python.exists():
        print(f"[error] venv python not found at: {venv_python}")
        sys.exit(1)

    # 3) upgrade pip + install requirements
    run([str(venv_python), "-m", "pip", "install", "-U", "pip"])
    run([str(venv_pip), "install", "-r", str(req_file)])

    print("\n[ok] Environment ready.")
    if platform.system().lower().startswith("win"):
        print(f"Activate: {venv_dir}\\Scripts\\activate")
    else:
        print(f"Activate: source {venv_dir}/bin/activate")

    print("\nNext:")
    print(f"  cd {project_root}")
    print("  source .venv/bin/activate")
    print("  python -m autoprofiler.demo_profile")


if __name__ == "__main__":
    main()
