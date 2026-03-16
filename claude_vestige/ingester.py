"""Chunking de archivos Markdown y generación de embeddings."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter

from claude_vestige.embeddings import EmbeddingProvider

MAX_CHUNK_CHARS = 2000  # ~500 tokens
OVERLAP_CHARS = 200  # ~50 tokens


@dataclass
class Chunk:
    """Un fragmento de texto con su metadata."""

    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _make_chunk_id(file_path: str, section: str, index: int) -> str:
    """Genera ID determinístico basado en archivo + sección + índice."""
    raw = f"{file_path}::{section}::{index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _split_by_headers(text: str) -> list[tuple[str, str]]:
    """Divide texto por headers ## de Markdown. Retorna [(section_name, content)]."""
    sections: list[tuple[str, str]] = []
    current_header = "intro"
    current_lines: list[str] = []

    for line in text.splitlines():
        if line.startswith("## "):
            if current_lines:
                sections.append((current_header, "\n".join(current_lines).strip()))
            current_header = line.lstrip("# ").strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_header, "\n".join(current_lines).strip()))

    return [(h, c) for h, c in sections if c]


def _split_long_section(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Divide una sección larga por párrafos, respetando el límite de caracteres."""
    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current_len + para_len > max_chars and current:
            chunks.append("\n\n".join(current))
            # Overlap: mantener el último párrafo
            if len(current) > 1:
                overlap = current[-1]
                current = [overlap]
                current_len = len(overlap)
            else:
                current = []
                current_len = 0
        current.append(para)
        current_len += para_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def chunk_markdown(file_path: Path, project_root: Path) -> list[Chunk]:
    """Parsea un archivo Markdown y lo divide en chunks."""
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    rel_path = str(file_path.relative_to(project_root))
    last_modified = file_path.stat().st_mtime

    # Extraer frontmatter si existe
    post = frontmatter.loads(text)
    content = post.content

    sections = _split_by_headers(content)
    chunks: list[Chunk] = []

    for section_name, section_content in sections:
        parts = _split_long_section(section_content)
        for i, part in enumerate(parts):
            chunk_id = _make_chunk_id(rel_path, section_name, i)
            chunks.append(
                Chunk(
                    id=chunk_id,
                    content=part,
                    metadata={
                        "file": rel_path,
                        "section": section_name,
                        "last_modified": last_modified,
                        "source": "manual",
                    },
                )
            )

    return chunks


def ingest_files(
    files: list[Path],
    project_root: Path,
    provider: EmbeddingProvider,
) -> list[tuple[Chunk, list[float]]]:
    """Procesa archivos y genera chunks con embeddings."""
    all_chunks: list[Chunk] = []

    for file_path in files:
        try:
            chunks = chunk_markdown(file_path, project_root)
            all_chunks.extend(chunks)
        except Exception:
            continue

    if not all_chunks:
        return []

    # Batch embedding
    texts = [c.content for c in all_chunks]
    embeddings = provider.embed(texts)

    return list(zip(all_chunks, embeddings))
