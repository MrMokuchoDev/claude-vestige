#!/usr/bin/env python3
"""
UserPromptSubmit hook — captura el prompt del usuario.

Guarda el mensaje del usuario en ~/.claude-vestige/current_prompt.txt
para que el hook PostToolUse (agent) pueda leerlo y entender
la intención detrás de cada cambio.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROMPT_FILE = Path.home() / ".claude-vestige" / "current_prompt.txt"


def main() -> None:
    try:
        hook_input = json.loads(sys.stdin.read())
    except Exception:
        return

    prompt = hook_input.get("prompt", "")
    if not prompt:
        return

    try:
        PROMPT_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROMPT_FILE.write_text(prompt, encoding="utf-8")
    except Exception:
        pass


if __name__ == "__main__":
    main()
