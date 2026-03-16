#!/usr/bin/env python3
"""
save_observation.py — guardado de observaciones en ChromaDB.

Llamado por el hook agent de PostToolUse vía Bash.
Recibe la observación como argumento y la guarda en la colección sessions.

Uso:
  python3 save_observation.py --cwd /path/to/project --observation "texto de la observación"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SESSION_LOG = Path.home() / ".claude-vestige" / "session_observations.jsonl"


def _log_observation(observation: str) -> None:
    """Registra la observación en el log de sesión para el Stop hook."""
    try:
        SESSION_LOG.parent.mkdir(parents=True, exist_ok=True)
        with SESSION_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"observation": observation}) + "\n")
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", required=True, help="Directorio del proyecto")
    parser.add_argument("--observation", required=True, help="Texto de la observación")
    parser.add_argument("--type", default="change", help="Tipo: change, decision, bug_fix, note")
    args = parser.parse_args()

    project_root = Path(args.cwd).resolve()

    # Registrar en session log (para el resumen del Stop hook)
    _log_observation(args.observation)

    try:
        from claude_vestige.config import find_config_upwards, load_config
        from claude_vestige.embeddings import create_provider
        from claude_vestige.memory import save_memory
        from claude_vestige.store import VectorStore

        config_root = find_config_upwards(project_root)
        if not config_root:
            print("No Claude Vestige config found.", file=sys.stderr)
            return

        config = load_config(config_root)
        if not config:
            print("Could not load config.", file=sys.stderr)
            return

        provider = create_provider(config.embeddings_provider, config.embeddings_model)
        store = VectorStore(config.db_path)

        result = save_memory(
            content=args.observation,
            memory_type=args.type,
            tags=["auto-captured"],
            config=config,
            provider=provider,
            store=store,
        )

        if "error" in result:
            print(f"Error: {result['error']}", file=sys.stderr)
        else:
            print(f"Observation saved: {result['id']}")

    except Exception as e:
        print(f"Error saving observation: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
