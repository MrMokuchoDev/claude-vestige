"""Interfaz con ChromaDB: upsert, search, delete."""

from __future__ import annotations

import fcntl
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import chromadb
from rank_bm25 import BM25Okapi

from claude_vestige.ingester import Chunk


@dataclass
class ChunkResult:
    """Resultado de búsqueda — puede ser liviano (sin content) o completo."""

    id: str
    file: str
    section: str
    chunk_type: str  # "doc" o "memory"
    date: float
    snippet: str = ""
    content: str = ""
    distance: float = 0.0


class VectorStore:
    """Interfaz con ChromaDB para un proyecto."""

    def __init__(self, db_path: Path) -> None:
        db_path.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._lock_path = db_path / ".lock"
        self._client = chromadb.PersistentClient(path=str(db_path))

    def _acquire_lock(self):
        """Acquire file lock for safe concurrent access."""
        self._lock_file = open(self._lock_path, "w")
        fcntl.flock(self._lock_file, fcntl.LOCK_EX)

    def _release_lock(self):
        """Release file lock."""
        if hasattr(self, "_lock_file") and self._lock_file:
            fcntl.flock(self._lock_file, fcntl.LOCK_UN)
            self._lock_file.close()

    def _get_collection(self, name: str) -> chromadb.Collection:
        return self._client.get_or_create_collection(name=name)

    def upsert_docs(self, chunks_with_embeddings: list[tuple[Chunk, list[float]]]) -> int:
        """Inserta o actualiza chunks en la colección docs."""
        return self._upsert("docs", chunks_with_embeddings)

    def upsert_sessions(self, chunks_with_embeddings: list[tuple[Chunk, list[float]]]) -> int:
        """Inserta o actualiza chunks en la colección sessions."""
        return self._upsert("sessions", chunks_with_embeddings)

    def _upsert(self, collection_name: str, chunks_with_embeddings: list[tuple[Chunk, list[float]]]) -> int:
        if not chunks_with_embeddings:
            return 0

        self._acquire_lock()
        try:
            collection = self._get_collection(collection_name)
            ids = [c.id for c, _ in chunks_with_embeddings]
            documents = [c.content for c, _ in chunks_with_embeddings]
            embeddings = [e for _, e in chunks_with_embeddings]
            metadatas = [c.metadata for c, _ in chunks_with_embeddings]

            collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
            return len(ids)
        finally:
            self._release_lock()

    def search(
        self,
        query_embedding: list[float],
        query_text: str = "",
        n: int = 10,
        collection_name: Optional[str] = None,
    ) -> list[ChunkResult]:
        """Búsqueda híbrida: vectorial + BM25 con Reciprocal Rank Fusion."""
        collections_to_search = (
            [collection_name] if collection_name else ["docs", "sessions"]
        )

        all_results: list[ChunkResult] = []

        for col_name in collections_to_search:
            collection = self._get_collection(col_name)
            if collection.count() == 0:
                continue

            chunk_type = "doc" if col_name == "docs" else "memory"
            actual_n = min(n * 2, collection.count())

            # Búsqueda vectorial
            try:
                vector_results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=actual_n,
                    include=["documents", "metadatas", "distances"],
                )
            except Exception:
                # HNSW index not ready on disk (empty or corrupted collection)
                continue

            if not vector_results["ids"][0]:
                continue

            # Construir resultados vectoriales
            vector_chunks: list[ChunkResult] = []
            for i, chunk_id in enumerate(vector_results["ids"][0]):
                doc = vector_results["documents"][0][i]
                meta = vector_results["metadatas"][0][i]
                dist = vector_results["distances"][0][i]
                snippet = doc[:200] if doc else ""

                vector_chunks.append(
                    ChunkResult(
                        id=chunk_id,
                        file=meta.get("file", ""),
                        section=meta.get("section", ""),
                        chunk_type=chunk_type,
                        date=meta.get("last_modified", 0),
                        snippet=snippet,
                        content=doc,
                        distance=dist,
                    )
                )

            # BM25 reranking si hay query text
            if query_text and len(vector_chunks) > 1:
                results = self._reciprocal_rank_fusion(vector_chunks, query_text, n)
            else:
                results = vector_chunks[:n]

            all_results.extend(results)

        # Ordenar por distance y limitar
        all_results.sort(key=lambda r: r.distance)
        return all_results[:n]

    def _reciprocal_rank_fusion(
        self, vector_chunks: list[ChunkResult], query_text: str, n: int, k: int = 60
    ) -> list[ChunkResult]:
        """Combina ranking vectorial y BM25 con RRF."""
        # Ranking vectorial (ya ordenado por distance)
        vector_ranking = {c.id: rank for rank, c in enumerate(vector_chunks)}

        # Ranking BM25
        tokenized_docs = [c.content.lower().split() for c in vector_chunks]
        bm25 = BM25Okapi(tokenized_docs)
        scores = bm25.get_scores(query_text.lower().split())

        bm25_order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        bm25_ranking = {vector_chunks[i].id: rank for rank, i in enumerate(bm25_order)}

        # Fusión RRF
        rrf_scores: dict[str, float] = {}
        for chunk in vector_chunks:
            v_rank = vector_ranking.get(chunk.id, len(vector_chunks))
            b_rank = bm25_ranking.get(chunk.id, len(vector_chunks))
            rrf_scores[chunk.id] = 1.0 / (k + v_rank) + 1.0 / (k + b_rank)

        # Ordenar por RRF score (mayor = mejor)
        chunks_by_id = {c.id: c for c in vector_chunks}
        sorted_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)

        return [chunks_by_id[cid] for cid in sorted_ids[:n]]

    def get_chunks_by_ids(self, ids: list[str]) -> list[ChunkResult]:
        """Retorna contenido completo de chunks por sus IDs."""
        results: list[ChunkResult] = []

        for col_name in ["docs", "sessions"]:
            collection = self._get_collection(col_name)
            if collection.count() == 0:
                continue

            chunk_type = "doc" if col_name == "docs" else "memory"

            try:
                data = collection.get(ids=ids, include=["documents", "metadatas"])
            except Exception:
                continue

            for i, chunk_id in enumerate(data["ids"]):
                doc = data["documents"][i]
                meta = data["metadatas"][i]
                results.append(
                    ChunkResult(
                        id=chunk_id,
                        file=meta.get("file", ""),
                        section=meta.get("section", ""),
                        chunk_type=chunk_type,
                        date=meta.get("last_modified", 0),
                        content=doc,
                    )
                )

        return results

    def delete_docs_for_file(self, file_path: str) -> None:
        """Elimina chunks de un archivo específico de la colección docs."""
        collection = self._get_collection("docs")
        if collection.count() == 0:
            return

        results = collection.get(where={"file": file_path}, include=[])
        if results["ids"]:
            collection.delete(ids=results["ids"])

    def delete_all(self) -> None:
        """Elimina todas las colecciones del proyecto."""
        for name in ["docs", "sessions"]:
            try:
                self._client.delete_collection(name)
            except Exception:
                pass

    def get_indexed_files(self) -> list[str]:
        """Retorna lista de archivos únicos indexados en la colección docs."""
        try:
            collection = self._get_collection("docs")
            count = collection.count()
            if count == 0:
                return []
            data = collection.get(include=["metadatas"])
            files = set()
            for meta in data["metadatas"]:
                if meta and "file" in meta:
                    files.add(meta["file"])
            return sorted(files)
        except Exception:
            return []

    def get_stats(self) -> dict:
        """Retorna estadísticas del proyecto."""
        try:
            docs_count = self._get_collection("docs").count()
        except Exception:
            docs_count = 0
        try:
            sessions_count = self._get_collection("sessions").count()
        except Exception:
            sessions_count = 0
        return {
            "docs_chunks": docs_count,
            "sessions_chunks": sessions_count,
            "total_chunks": docs_count + sessions_count,
        }
