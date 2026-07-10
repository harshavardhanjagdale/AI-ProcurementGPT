#!/usr/bin/env python
"""
PreToolUse guardrail hook (Edit/Write/MultiEdit).

Blocks the agent from writing real secrets into the repo. Two rules:
  1. Never edit a live `.env` file (only `.env.example` is allowed to be touched).
  2. Never write a string that looks like a live API key / SMTP app-password.

Protocol: read the tool-call JSON on stdin. Exit 2 + message on stderr to BLOCK
the tool call (the message is shown back to the agent); exit 0 to allow.

This is the "policy as code" leg of the dev workflow — the model physically
cannot commit a leaked key even if a prompt tells it to.
"""
import json
import re
import sys

# Live-secret signatures. Deliberately narrow to avoid false positives on
# placeholders like "sk-ant-xxxx" or "your-key-here".
SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),      # Anthropic key
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{32,}"),  # OpenAI key
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),         # Google API key
    re.compile(r"AKIA[0-9A-Z]{16}"),               # AWS access key id
    # Gmail app password: four 4-letter groups, but ONLY when near a password
    # keyword — otherwise ordinary English sentences would false-positive.
    re.compile(r"(?i)(?:app[- ]?password|smtp_?password)['\"\s:=]+[a-z]{4}\s[a-z]{4}\s[a-z]{4}\s[a-z]{4}\b"),
]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # never break the tool call on a parsing hiccup

    tool_input = payload.get("tool_input", {}) or {}
    path = (tool_input.get("file_path") or "").replace("\\", "/")

    # Rule 1: protect the live .env
    base = path.rsplit("/", 1)[-1]
    if base == ".env" or (base.startswith(".env") and not base.endswith(".example")):
        sys.stderr.write(
            f"BLOCKED: refusing to edit the live env file '{base}'. "
            "Edit '.env.example' with placeholders instead, and set real values manually.\n"
        )
        return 2

    # Rule 2: scan the content being written for live-looking secrets
    content = " ".join(str(tool_input.get(k, "")) for k in ("content", "new_string", "new_str"))
    for pat in SECRET_PATTERNS:
        if pat.search(content):
            sys.stderr.write(
                "BLOCKED: the content being written contains what looks like a live secret "
                f"(pattern: {pat.pattern}). Use an env var / placeholder, not a hard-coded key.\n"
            )
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
