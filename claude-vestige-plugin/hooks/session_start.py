#!/usr/bin/env python3
"""
SessionStart hook — inyecta contexto relevante al iniciar sesión.

Flujo:
1. Busca .claude-vestige/config.toml subiendo en el árbol de directorios
2. Si existe config + índice → busca top 5 chunks, imprime contenido
3. Si NO existe config → auto-bootstrap con README.md/CLAUDE.md si existen
4. Si no hay nada → escaneo básico del proyecto (stack + conteo de archivos)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    # Leer input del hook
    try:
        hook_input = json.loads(sys.stdin.read())
    except Exception:
        hook_input = {}

    cwd = hook_input.get("cwd", str(Path.cwd()))
    project_root = Path(cwd).resolve()

    try:
        _handle_session_start(project_root)
    except Exception as e:
        # Nunca fallar — imprimir error como contexto informativo
        print(f"[Claude Vestige] Error: {e}")


def _handle_session_start(project_root: Path) -> None:
    from claude_vestige.config import find_config_upwards, load_config
    from claude_vestige.store import VectorStore

    # Buscar config subiendo en el árbol
    config_root = find_config_upwards(project_root)

    if config_root:
        config = load_config(config_root)
        if config:
            _inject_indexed_context(config)
            return

    # No hay config — intentar auto-bootstrap
    _handle_first_time(project_root)


def _inject_indexed_context(config) -> None:
    """Proyecto ya indexado: buscar e inyectar contexto relevante."""
    from claude_vestige.embeddings import create_provider
    from claude_vestige.store import VectorStore

    store = VectorStore(config.db_path)
    stats = store.get_stats()

    if stats["total_chunks"] == 0:
        print(f"[Claude Vestige] Proyecto '{config.name}' configurado pero sin chunks.")
        print("Ejecuta /claude_vestige:bootstrap para re-indexar.")
        return

    # Buscar con query genérica para obtener contexto amplio
    provider = create_provider(config.embeddings_provider, config.embeddings_model)
    query = "project overview architecture decisions conventions stack"
    query_embedding = provider.embed_query(query)

    results = store.search(query_embedding=query_embedding, query_text=query, n=5)

    if not results:
        print(f"[Claude Vestige] Proyecto '{config.name}': {stats['total_chunks']} chunks indexados.")
        return

    # Imprimir contexto — esto se inyecta directamente en la conversación de Claude
    print(f"[Claude Vestige] Proyecto '{config.name}' — Memoria semántica activa")
    print(f"Indexado: {stats['docs_chunks']} doc chunks, {stats['sessions_chunks']} observaciones.\n")

    for result in results:
        source = f"{result.file} > {result.section}" if result.section != "intro" else result.file
        label = "doc" if result.chunk_type == "doc" else "observación"
        print(f"### [{label}] {source}")
        print(result.content)
        print()

    print("---")
    print("Usa /claude_vestige:search para búsquedas más específicas.")


def _handle_first_time(project_root: Path) -> None:
    """Primera vez en un proyecto: auto-bootstrap o escaneo básico."""
    from claude_vestige.bootstrap import auto_bootstrap

    # Intentar auto-bootstrap con README.md y CLAUDE.md
    result = auto_bootstrap(project_root)

    if result:
        # Auto-bootstrap exitoso — ahora inyectar el contexto
        print(f"[Claude Vestige] Auto-indexado: {result}\n")

        # Cargar y mostrar lo que se acaba de indexar
        from claude_vestige.config import load_config

        config = load_config(project_root)
        if config:
            _inject_indexed_context(config)
        return

    # No hay README.md ni CLAUDE.md — escaneo básico
    _basic_scan(project_root)


def _basic_scan(project_root: Path) -> None:
    """Escaneo básico: stack + conteo de archivos como contexto mínimo."""
    from claude_vestige.bootstrap import count_files_by_extension, detect_stack
    from claude_vestige.config import build_exclude_spec

    stack = detect_stack(project_root)
    stack_str = ", ".join(stack) if stack else "no detectado"

    exclude_spec = build_exclude_spec(project_root)
    file_counts = count_files_by_extension(project_root, exclude_spec)

    print(f"[Claude Vestige] Proyecto: {project_root.name}")
    print(f"Stack: {stack_str}")

    if file_counts:
        counts_str = ", ".join(f"{count} {ext}" for ext, count in file_counts.items())
        print(f"Archivos: {counts_str}")

    print("\nSin documentación indexada. Usa /claude_vestige:bootstrap para agregar archivos.")


if __name__ == "__main__":
    main()
