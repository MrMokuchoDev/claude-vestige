"""CLI commands for Claude Vestige — replaces MCP tools with direct Python scripts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from claude_vestige.bootstrap import bootstrap_project
from claude_vestige.config import find_config_upwards, load_config
from claude_vestige.embeddings import create_provider
from claude_vestige.memory import save_memory
from claude_vestige.store import VectorStore


def _get_config(cwd: str | None = None):
    """Get project config starting from cwd."""
    start = Path(cwd) if cwd else Path.cwd()
    config_root = find_config_upwards(start)
    if not config_root:
        return None
    return load_config(config_root)


def cmd_search():
    """Search project memory: claude-vestige-search --query "..." --cwd /path [--n 10]"""
    parser = argparse.ArgumentParser(description="Search project memory")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--cwd", default=None, help="Project directory")
    parser.add_argument("--n", type=int, default=10, help="Number of results")
    args = parser.parse_args()

    config = _get_config(args.cwd)
    if not config:
        print("Project not indexed. Use /claude_vestige:bootstrap first.")
        return

    provider = create_provider(config.embeddings_provider, config.embeddings_model)
    store = VectorStore(config.db_path)
    query_embedding = provider.embed_query(args.query)

    results = store.search(query_embedding=query_embedding, query_text=args.query, n=args.n)

    if not results:
        print("No results found.")
        return

    index = []
    for r in results:
        index.append({
            "id": r.id,
            "file": r.file,
            "section": r.section,
            "type": r.chunk_type,
            "snippet": r.snippet[:200],
        })

    print(json.dumps(index, indent=2, ensure_ascii=False))


def cmd_get_chunks():
    """Get full content for chunk IDs: claude-vestige-chunks --ids id1 id2 --cwd /path"""
    parser = argparse.ArgumentParser(description="Get full chunks by ID")
    parser.add_argument("--ids", nargs="+", required=True, help="Chunk IDs")
    parser.add_argument("--cwd", default=None, help="Project directory")
    args = parser.parse_args()

    config = _get_config(args.cwd)
    if not config:
        print("Project not indexed.")
        return

    store = VectorStore(config.db_path)
    results = store.get_chunks_by_ids(args.ids)

    if not results:
        print("No chunks found with those IDs.")
        return

    chunks = []
    for r in results:
        chunks.append({
            "id": r.id,
            "file": r.file,
            "section": r.section,
            "type": r.chunk_type,
            "content": r.content,
        })

    print(json.dumps(chunks, indent=2, ensure_ascii=False))


def cmd_bootstrap():
    """Bootstrap project: claude-vestige-bootstrap --cwd /path [--include file1.md file2.md]"""
    parser = argparse.ArgumentParser(description="Bootstrap project indexing")
    parser.add_argument("--cwd", default=None, help="Project directory")
    parser.add_argument("--include", nargs="*", default=None, help="Files/globs to index")
    args = parser.parse_args()

    project_path = Path(args.cwd) if args.cwd else None
    result = bootstrap_project(project_path, args.include)
    print(result)


def cmd_save_memory():
    """Save memory: claude-vestige-save --content "..." --type decision --cwd /path [--tags tag1 tag2]"""
    parser = argparse.ArgumentParser(description="Save a memory entry")
    parser.add_argument("--content", required=True, help="Memory content")
    parser.add_argument("--type", required=True, choices=["decision", "bug_fix", "change", "note"], help="Memory type")
    parser.add_argument("--cwd", default=None, help="Project directory")
    parser.add_argument("--tags", nargs="*", default=[], help="Tags")
    args = parser.parse_args()

    config = _get_config(args.cwd)
    if not config:
        print("Project not indexed. Use /claude_vestige:bootstrap first.")
        return

    provider = create_provider(config.embeddings_provider, config.embeddings_model)
    store = VectorStore(config.db_path)

    result = save_memory(
        content=args.content,
        memory_type=args.type,
        tags=args.tags,
        config=config,
        provider=provider,
        store=store,
    )

    print(json.dumps(result, ensure_ascii=False))


def cmd_status():
    """Get project status: claude-vestige-status --cwd /path"""
    parser = argparse.ArgumentParser(description="Get project indexing status")
    parser.add_argument("--cwd", default=None, help="Project directory")
    args = parser.parse_args()

    config = _get_config(args.cwd)
    if not config:
        print("No indexed project found in current directory.")
        return

    store = VectorStore(config.db_path)
    stats = store.get_stats()
    indexed_files = store.get_indexed_files()

    status = {
        "project": config.name,
        "root": str(config.root),
        "embeddings_provider": config.embeddings_provider,
        "docs_chunks": stats["docs_chunks"],
        "sessions_chunks": stats["sessions_chunks"],
        "total_chunks": stats["total_chunks"],
        "config_include": config.include,
        "indexed_files": indexed_files,
    }

    print(json.dumps(status, indent=2, ensure_ascii=False))


COMMANDS = {
    "search": cmd_search,
    "chunks": cmd_get_chunks,
    "bootstrap": cmd_bootstrap,
    "save": cmd_save_memory,
    "status": cmd_status,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: python -m claude_vestige.cli <command> [args]")
        print(f"Commands: {', '.join(COMMANDS.keys())}")
        sys.exit(1)

    command = sys.argv.pop(1)  # Remove command name so argparse sees the rest
    COMMANDS[command]()


if __name__ == "__main__":
    main()
