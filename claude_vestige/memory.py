"""Guardado de memorias en la colección sessions."""

from __future__ import annotations

import hashlib
import time

from claude_vestige.config import ProjectConfig
from claude_vestige.embeddings import EmbeddingProvider
from claude_vestige.ingester import Chunk
from claude_vestige.store import VectorStore

VALID_MEMORY_TYPES = {"decision", "bug_fix", "change", "note"}


def save_memory(
    content: str,
    memory_type: str,
    tags: list[str],
    config: ProjectConfig,
    provider: EmbeddingProvider,
    store: VectorStore,
) -> dict:
    """Guarda una memoria en la colección sessions."""
    if memory_type not in VALID_MEMORY_TYPES:
        return {
            "error": f"Tipo inválido: {memory_type}. Válidos: {', '.join(sorted(VALID_MEMORY_TYPES))}"
        }

    if not content.strip():
        return {"error": "El contenido no puede estar vacío."}

    timestamp = time.time()
    raw_id = f"memory::{timestamp}::{hashlib.sha256(content.encode()).hexdigest()[:8]}"
    memory_id = hashlib.sha256(raw_id.encode()).hexdigest()[:16]

    chunk = Chunk(
        id=memory_id,
        content=content,
        metadata={
            "file": "memory",
            "section": memory_type,
            "type": memory_type,
            "tags": ",".join(tags),
            "last_modified": timestamp,
            "source": "session",
        },
    )

    embedding = provider.embed_query(content)
    store.upsert_sessions([(chunk, embedding)])

    return {"id": memory_id, "type": memory_type, "status": "saved"}


def count_observations(store: VectorStore) -> int:
    """Retorna cuántas observaciones hay en la colección sessions."""
    return store.get_stats()["sessions_chunks"]
