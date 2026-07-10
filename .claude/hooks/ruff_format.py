#!/usr/bin/env python
"""
PostToolUse formatting hook (Edit/Write/MultiEdit).

After the agent edits a Python file under backend/, auto-run ruff's fixer +
formatter on just that file, so every change lands already matching the repo's
style (line-length 100, py312) without the agent having to remember. Ruff is
already configured in backend/pyproject.toml.

Protocol: read the tool-call JSON on stdin. Always exit 0 — formatting is a
convenience, never a reason to fail the edit. Anything printed to stdout is
surfaced as context to the agent.
"""
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    path = (payload.get("tool_input", {}) or {}).get("file_path", "")
    if not path.endswith(".py"):
        return 0

    p = Path(path)
    if not p.exists():
        return 0

    # ruff lives in the backend venv / project; run from backend/ so it finds pyproject.toml
    cwd = None
    for parent in p.resolve().parents:
        if (parent / "pyproject.toml").exists():
            cwd = parent
            break

    try:
        subprocess.run(["ruff", "check", "--fix", str(p)], cwd=cwd,
                       capture_output=True, text=True, timeout=30)
        fmt = subprocess.run(["ruff", "format", str(p)], cwd=cwd,
                             capture_output=True, text=True, timeout=30)
        if fmt.returncode == 0:
            print(f"[hook] ruff formatted {p.name}")
    except FileNotFoundError:
        pass  # ruff not installed — silently skip
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
