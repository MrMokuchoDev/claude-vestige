"""MCP server para Claude Vestige — tools manuales de búsqueda y guardado."""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from claude_vestige.bootstrap import bootstrap_project
from claude_vestige.config import find_config_upwards, load_config
from claude_vestige.embeddings import create_provider
from claude_vestige.memory import save_memory
from claude_vestige.store import VectorStore

server = Server("claude_vestige")


def _get_config():
    """Obtiene la config del proyecto actual."""
    config_root = find_config_upwards(Path.cwd())
    if not config_root:
        return None
    return load_config(config_root)


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="retrieve_context",
            description="Search project docs and session memory. Returns lightweight index with snippets (~50 tokens each). Use for finding relevant context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "n": {"type": "integer", "description": "Number of results (default 10)", "default": 10},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_chunks",
            description="Get full content for specific chunk IDs returned by retrieve_context. Only request IDs you actually need.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ids": {"type": "array", "items": {"type": "string"}, "description": "Chunk IDs to fetch"},
                },
                "required": ["ids"],
            },
        ),
        Tool(
            name="save_memory",
            description="Save an important decision, bug fix, or note to project memory for future sessions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "What to remember (concise, structured)"},
                    "type": {"type": "string", "enum": ["decision", "bug_fix", "change", "note"], "description": "Type of memory"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for categorization", "default": []},
                },
                "required": ["content", "type"],
            },
        ),
        Tool(
            name="bootstrap_project",
            description="Initialize or re-index a project. Without include_files, returns candidates. With include_files, generates config and indexes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {"type": "string", "description": "Project root (default: cwd)"},
                    "include_files": {"type": "array", "items": {"type": "string"}, "description": "Files/globs to index"},
                },
            },
        ),
        Tool(
            name="get_status",
            description="Get indexing status: chunks count, collections, embeddings provider.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == "retrieve_context":
            return _handle_retrieve_context(arguments)
        elif name == "get_chunks":
            return _handle_get_chunks(arguments)
        elif name == "save_memory":
            return _handle_save_memory(arguments)
        elif name == "bootstrap_project":
            return _handle_bootstrap(arguments)
        elif name == "get_status":
            return _handle_get_status()
        else:
            return [TextContent(type="text", text=f"Tool desconocido: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


def _handle_retrieve_context(args: dict):
    config = _get_config()
    if not config:
        return [TextContent(type="text", text="Proyecto no indexado. Usa /claude_vestige:bootstrap primero.")]

    query = args.get("query", "")
    n = args.get("n", 10)

    provider = create_provider(config.embeddings_provider, config.embeddings_model)
    store = VectorStore(config.db_path)
    query_embedding = provider.embed_query(query)

    results = store.search(query_embedding=query_embedding, query_text=query, n=n)

    if not results:
        return [TextContent(type="text", text="No se encontraron resultados.")]

    # Retornar índice liviano
    index = []
    for r in results:
        index.append({
            "id": r.id,
            "file": r.file,
            "section": r.section,
            "type": r.chunk_type,
            "snippet": r.snippet[:200],
        })

    return [TextContent(type="text", text=json.dumps(index, indent=2, ensure_ascii=False))]


def _handle_get_chunks(args: dict):
    config = _get_config()
    if not config:
        return [TextContent(type="text", text="Proyecto no indexado.")]

    ids = args.get("ids", [])
    if not ids:
        return [TextContent(type="text", text="No se proporcionaron IDs.")]

    store = VectorStore(config.db_path)
    results = store.get_chunks_by_ids(ids)

    if not results:
        return [TextContent(type="text", text="No se encontraron chunks con esos IDs.")]

    chunks = []
    for r in results:
        chunks.append({
            "id": r.id,
            "file": r.file,
            "section": r.section,
            "type": r.chunk_type,
            "content": r.content,
        })

    return [TextContent(type="text", text=json.dumps(chunks, indent=2, ensure_ascii=False))]


def _handle_save_memory(args: dict):
    config = _get_config()
    if not config:
        return [TextContent(type="text", text="Proyecto no indexado. Usa /claude_vestige:bootstrap primero.")]

    provider = create_provider(config.embeddings_provider, config.embeddings_model)
    store = VectorStore(config.db_path)

    result = save_memory(
        content=args.get("content", ""),
        memory_type=args.get("type", "note"),
        tags=args.get("tags", []),
        config=config,
        provider=provider,
        store=store,
    )

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


def _handle_bootstrap(args: dict):
    project_path = Path(args["project_path"]) if args.get("project_path") else None
    include_files = args.get("include_files")

    result = bootstrap_project(project_path, include_files)
    return [TextContent(type="text", text=result)]


def _handle_get_status():
    config = _get_config()
    if not config:
        return [TextContent(type="text", text="No hay proyecto indexado en el directorio actual.")]

    store = VectorStore(config.db_path)
    stats = store.get_stats()

    status = {
        "project": config.name,
        "root": str(config.root),
        "embeddings_provider": config.embeddings_provider,
        "docs_chunks": stats["docs_chunks"],
        "sessions_chunks": stats["sessions_chunks"],
        "total_chunks": stats["total_chunks"],
        "include": config.include,
    }

    return [TextContent(type="text", text=json.dumps(status, indent=2, ensure_ascii=False))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
