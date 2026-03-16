"""Dashboard FastAPI para Claude Vestige."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from claude_vestige.bootstrap import detect_stack
from claude_vestige.config import build_exclude_spec, find_config_upwards, load_config
from claude_vestige.embeddings import create_provider
from claude_vestige.store import VectorStore

app = FastAPI(title="Claude Vestige Dashboard")

def _find_dashboard_html() -> Path:
    """Busca dashboard.html en múltiples ubicaciones."""
    candidates = [
        # Desarrollo local (repo)
        Path(__file__).parent.parent / "claude-vestige-plugin" / "dashboard.html",
        # Instalado via plugin marketplace
        Path.home() / ".claude-vestige" / "repo" / "claude-vestige-plugin" / "dashboard.html",
        # Plugin cache de Claude Code
        Path.home() / ".claude" / "plugins" / "cache" / "claude-vestige-tools" / "claude-vestige" / "0.1.0" / "dashboard.html",
        # Dentro del paquete Python
        Path(__file__).parent / "dashboard.html",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]  # fallback

DASHBOARD_HTML = _find_dashboard_html()
def _get_registry_path() -> Path:
    """Retorna el path del registry. Configurable via CLAUDE_VESTIGE_REGISTRY para tests."""
    import os
    custom = os.environ.get("CLAUDE_VESTIGE_REGISTRY")
    if custom:
        return Path(custom)
    return Path.home() / ".claude-vestige" / "projects.json"


def _load_registry() -> list[dict]:
    """Carga el registro global de proyectos."""
    registry_path = _get_registry_path()
    if not registry_path.exists():
        return []
    try:
        return json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _scan_for_projects() -> list[dict]:
    """Escanea proyectos conocidos y retorna info."""
    registry = _load_registry()
    projects = []

    for entry in registry:
        root = Path(entry.get("root", ""))
        if not root.exists():
            continue
        config = load_config(root)
        if not config:
            continue

        try:
            store = VectorStore(config.db_path)
            stats = store.get_stats()
        except Exception:
            stats = {"docs_chunks": 0, "sessions_chunks": 0, "total_chunks": 0}

        projects.append({
            "name": config.name,
            "root": str(config.root),
            "stack": detect_stack(config.root),
            "include": config.include,
            "docs_chunks": stats["docs_chunks"],
            "sessions_chunks": stats["sessions_chunks"],
            "total_chunks": stats["total_chunks"],
        })

    return projects


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Sirve el dashboard HTML."""
    if DASHBOARD_HTML.exists():
        return DASHBOARD_HTML.read_text(encoding="utf-8")
    return "<h1>Claude Vestige Dashboard</h1><p>dashboard.html not found.</p>"


@app.get("/api/health")
async def health():
    """Estado del servicio."""
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/projects")
async def list_projects():
    """Lista proyectos indexados."""
    return _scan_for_projects()


@app.get("/api/search")
async def search(
    query: str = Query(..., description="Search query"),
    project_root: str = Query(..., description="Project root path"),
    n: int = Query(10, description="Number of results"),
):
    """Búsqueda semántica en un proyecto."""
    root = Path(project_root)
    config = load_config(root)
    if not config:
        return {"error": "Proyecto no indexado."}

    try:
        provider = create_provider(config.embeddings_provider, config.embeddings_model)
        store = VectorStore(config.db_path)
        query_embedding = provider.embed_query(query)

        results = store.search(query_embedding=query_embedding, query_text=query, n=n)

        return [
            {
                "id": r.id,
                "file": r.file,
                "section": r.section,
                "type": r.chunk_type,
                "snippet": r.snippet[:200],
                "content": r.content,
            }
            for r in results
        ]
    except Exception:
        return []


@app.get("/api/chunks/{project_root:path}")
async def get_chunks(project_root: str):
    """Lista todos los chunks de docs de un proyecto (sin HNSW)."""
    root = Path(project_root)
    config = load_config(root)
    if not config:
        return []

    try:
        store = VectorStore(config.db_path)
        collection = store._get_collection("docs")

        if collection.count() == 0:
            return []

        data = collection.get(include=["documents", "metadatas"])

        chunks = []
        for i, chunk_id in enumerate(data["ids"]):
            meta = data["metadatas"][i]
            doc = data["documents"][i]
            chunks.append({
                "id": chunk_id,
                "file": meta.get("file", ""),
                "section": meta.get("section", ""),
                "type": "doc",
                "snippet": doc[:200] if doc else "",
                "content": doc,
            })

        return chunks
    except Exception:
        return []


@app.get("/api/sessions/{project_root:path}")
async def get_sessions(
    project_root: str,
    memory_type: Optional[str] = Query(None, description="Filter by type"),
):
    """Lista observaciones/memorias de un proyecto."""
    root = Path(project_root)
    config = load_config(root)
    if not config:
        return {"error": "Proyecto no indexado."}

    try:
        store = VectorStore(config.db_path)
        collection = store._get_collection("sessions")

        if collection.count() == 0:
            return []

        data = collection.get(include=["documents", "metadatas"])
    except Exception:
        return []

    sessions = []
    for i, chunk_id in enumerate(data["ids"]):
        meta = data["metadatas"][i]
        if memory_type and meta.get("type") != memory_type:
            continue
        sessions.append({
            "id": chunk_id,
            "content": data["documents"][i],
            "type": meta.get("type", "note"),
            "tags": meta.get("tags", ""),
            "date": meta.get("last_modified", 0),
        })

    sessions.sort(key=lambda s: s["date"], reverse=True)
    return sessions


@app.get("/api/stats/{project_root:path}")
async def get_stats(project_root: str):
    """Estadísticas de un proyecto."""
    root = Path(project_root)
    config = load_config(root)
    if not config:
        return {"error": "Proyecto no indexado."}

    try:
        store = VectorStore(config.db_path)
        stats = store.get_stats()
    except Exception:
        stats = {"docs_chunks": 0, "sessions_chunks": 0, "total_chunks": 0}

    return {
        "name": config.name,
        "root": str(config.root),
        "provider": config.embeddings_provider,
        "include": config.include,
        **stats,
    }


def main():
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Claude Vestige Dashboard")
    parser.add_argument("--port", type=int, default=7842)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
