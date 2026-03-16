#!/usr/bin/env python3
"""
Stop hook — resumen de sesión y limpieza.

Se ejecuta cuando Claude termina la conversación.
1. Lee las observaciones capturadas durante la sesión
2. Genera un resumen compacto de la sesión
3. Lo guarda como memoria tipo 'note' con tag 'session-summary'
4. Limpia el archivo temporal del prompt
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROMPT_FILE = Path.home() / ".claude-vestige" / "current_prompt.txt"
SESSION_LOG = Path.home() / ".claude-vestige" / "session_observations.jsonl"


def main() -> None:
    try:
        hook_input = json.loads(sys.stdin.read())
    except Exception:
        hook_input = {}

    cwd = hook_input.get("cwd", "")
    if not cwd:
        _cleanup()
        return

    project_root = Path(cwd).resolve()

    try:
        from claude_vestige.config import find_config_upwards, load_config
        from claude_vestige.embeddings import create_provider
        from claude_vestige.memory import save_memory
        from claude_vestige.store import VectorStore

        config_root = find_config_upwards(project_root)
        if not config_root:
            _cleanup()
            return

        config = load_config(config_root)
        if not config:
            _cleanup()
            return

        # Leer observaciones de la sesión
        observations = _read_session_observations()
        if not observations:
            _cleanup()
            return

        # Generar resumen
        summary = _build_summary(observations)
        if not summary:
            _cleanup()
            return

        # Guardar resumen en ChromaDB
        provider = create_provider(config.embeddings_provider, config.embeddings_model)
        store = VectorStore(config.db_path)

        save_memory(
            content=summary,
            memory_type="note",
            tags=["session-summary", f"session-{int(time.time())}"],
            config=config,
            provider=provider,
            store=store,
        )

        print(f"[Claude Vestige] Session summary saved ({len(observations)} observations).")

    except Exception as e:
        print(f"[Claude Vestige] Error saving session summary: {e}", file=sys.stderr)
    finally:
        _cleanup()


def _read_session_observations() -> list[str]:
    """Lee las observaciones acumuladas durante la sesión."""
    if not SESSION_LOG.exists():
        return []

    observations = []
    try:
        for line in SESSION_LOG.read_text(encoding="utf-8").strip().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                observations.append(entry.get("observation", ""))
            except json.JSONDecodeError:
                observations.append(line.strip())
    except Exception:
        pass

    return [o for o in observations if o]


def _build_summary(observations: list[str]) -> str:
    """Construye un resumen compacto de las observaciones de la sesión."""
    if not observations:
        return ""

    if len(observations) == 1:
        return f"Session summary: {observations[0]}"

    # Combinar observaciones en un resumen estructurado
    lines = ["Session summary:"]
    for i, obs in enumerate(observations, 1):
        # Truncar observaciones muy largas
        if len(obs) > 200:
            obs = obs[:197] + "..."
        lines.append(f"  {i}. {obs}")

    return "\n".join(lines)


def _cleanup() -> None:
    """Limpia archivos temporales de la sesión."""
    try:
        if PROMPT_FILE.exists():
            PROMPT_FILE.unlink()
    except Exception:
        pass

    try:
        if SESSION_LOG.exists():
            SESSION_LOG.unlink()
    except Exception:
        pass


if __name__ == "__main__":
    main()
