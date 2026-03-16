#!/usr/bin/env python3
"""
PostToolUse hook — captura observaciones con análisis de Haiku.

1. Recibe tool use por stdin
2. Lee el prompt del usuario de ~/.claude-vestige/current_prompt.txt
3. Llama a Haiku via `claude --print --model haiku` para analizar
4. Guarda la observación en ChromaDB
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

PROMPT_FILE = Path.home() / ".claude-vestige" / "current_prompt.txt"


def main() -> None:
    try:
        hook_input = json.loads(sys.stdin.read())
    except Exception:
        return

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    tool_response = hook_input.get("tool_response", "")
    cwd = hook_input.get("cwd", "")

    if not cwd or not tool_name:
        return

    # Leer el prompt del usuario
    user_prompt = ""
    try:
        if PROMPT_FILE.exists():
            user_prompt = PROMPT_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        pass

    # Preparar contexto para Haiku
    tool_summary = _summarize_tool_input(tool_name, tool_input, tool_response)
    if not tool_summary:
        return

    # Llamar a Haiku para análisis
    observation = _analyze_with_haiku(tool_summary, user_prompt)
    if not observation:
        return

    # Extraer tipo del prefijo que Haiku devuelve
    obs_type, observation = _extract_type(observation)

    # Registrar en session log
    _log_observation(observation)

    # Guardar en ChromaDB
    try:
        from claude_vestige.config import find_config_upwards, load_config
        from claude_vestige.embeddings import create_provider
        from claude_vestige.memory import save_memory
        from claude_vestige.store import VectorStore

        project_root = Path(cwd).resolve()
        config_root = find_config_upwards(project_root)
        if not config_root:
            return

        config = load_config(config_root)
        if not config:
            return

        provider = create_provider(config.embeddings_provider, config.embeddings_model)
        store = VectorStore(config.db_path)

        save_memory(
            content=observation,
            memory_type=obs_type,
            tags=["auto-captured"],
            config=config,
            provider=provider,
            store=store,
        )

        # Auto-indexar archivos .md creados/editados
        _auto_index_file(tool_name, tool_input, config, provider, store, config_root)
    except Exception:
        pass


def _summarize_tool_input(tool_name: str, tool_input: dict, tool_response: str) -> str:
    """Resume el tool input para no enviar demasiado a Haiku."""
    if tool_name in ("Write", "Edit", "MultiEdit"):
        file_path = tool_input.get("file_path", "unknown")
        if tool_name == "Write":
            content = tool_input.get("content", "")
            # Truncar contenido largo
            if len(content) > 500:
                content = content[:500] + "\n... (truncated)"
            return f"Tool: {tool_name}\nFile: {file_path}\nContent:\n{content}"
        else:
            old = tool_input.get("old_string", "")[:200]
            new = tool_input.get("new_string", "")[:200]
            return f"Tool: {tool_name}\nFile: {file_path}\nOld: {old}\nNew: {new}"

    return ""


def _analyze_with_haiku(tool_summary: str, user_prompt: str) -> str:
    """Llama a Haiku via claude CLI para analizar el tool use."""
    claude_path = shutil.which("claude")
    if not claude_path:
        return ""

    prompt_context = f"User asked: {user_prompt}\n\n" if user_prompt else ""

    analysis_prompt = (
        "You are a concise observation logger for a software project. "
        "Your job: capture what was done and why, to provide context for future sessions.\n\n"
        "RESPOND WITH ONLY 'SKIP' if the change is purely whitespace, formatting, or an empty file.\n\n"
        "For everything else, write 1-2 sentences: WHAT was done and WHY (infer from user context).\n"
        "Prefix with type: [change], [decision], [bug_fix], or [note]\n\n"
        "Examples:\n"
        "- [decision] Switched from SQLite to ChromaDB because hybrid search requires embedding support.\n"
        "- [change] Created considerations.md with deployment and development guidelines per user request.\n"
        "- [bug_fix] Fixed HNSW corruption by wrapping ChromaDB queries in try/except to handle concurrent access.\n\n"
        f"{prompt_context}"
        f"{tool_summary}\n\n"
        "Response:"
    )

    try:
        result = subprocess.run(
            [claude_path, "--print", "--model", "haiku"],
            input=analysis_prompt,
            capture_output=True,
            text=True,
            timeout=20,
        )

        if result.returncode != 0:
            return ""

        observation = result.stdout.strip()
        if not observation:
            return ""
        # SKIP puede venir solo o con explicación después
        first_line = observation.split("\n")[0].strip()
        if first_line.upper().startswith("SKIP"):
            return ""

        return observation

    except Exception:
        return ""


def _extract_type(observation: str) -> tuple[str, str]:
    """Extrae el tipo del prefijo [type] que Haiku devuelve."""
    import re

    valid_types = {"change", "decision", "bug_fix", "note"}
    match = re.match(r"\[(\w+)\]\s*(.*)", observation, re.DOTALL)
    if match:
        candidate = match.group(1).lower()
        if candidate in valid_types:
            return candidate, match.group(2).strip()

    # Fallback: inferir del contenido
    text = observation.lower()
    if any(w in text for w in ("fix", "bug", "error", "corrig", "arregl")):
        return "bug_fix", observation
    if any(w in text for w in ("decid", "decision", "architect", "switch")):
        return "decision", observation
    return "change", observation


def _log_observation(observation: str) -> None:
    """Registra la observación en el log de sesión para el Stop hook."""
    session_log = Path.home() / ".claude-vestige" / "session_observations.jsonl"
    try:
        session_log.parent.mkdir(parents=True, exist_ok=True)
        with session_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"observation": observation}) + "\n")
    except Exception:
        pass


def _auto_index_file(tool_name, tool_input, config, provider, store, project_root):
    """Auto-indexa archivos .md que Claude crea o edita."""
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        return

    file_path = tool_input.get("file_path", "")
    if not file_path or not file_path.endswith(".md"):
        return

    from claude_vestige.config import MAX_FILE_SIZE
    from claude_vestige.ingester import chunk_markdown

    target = Path(file_path)
    if not target.exists() or not target.is_file():
        return
    if target.stat().st_size > MAX_FILE_SIZE:
        return

    chunks = chunk_markdown(target, project_root)
    if not chunks:
        return

    embeddings = provider.embed([c.content for c in chunks])
    store.upsert_docs(list(zip(chunks, embeddings)))


if __name__ == "__main__":
    main()
