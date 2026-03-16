"""Abstracción de providers de embeddings."""

from __future__ import annotations

from typing import Optional, Protocol


class EmbeddingProvider(Protocol):
    """Interfaz que debe cumplir todo provider de embeddings."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings para una lista de textos."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Genera embedding para un solo texto (query de búsqueda)."""
        ...


class FastEmbedProvider:
    """Provider usando fastembed (ONNX, en-proceso, sin servidor externo)."""

    def __init__(self, model: str = "BAAI/bge-small-en-v1.5") -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [e.tolist() for e in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return list(self._model.query_embed(text))[0].tolist()


class OllamaProvider:
    """Provider usando Ollama (requiere servidor externo corriendo)."""

    def __init__(self, model: str = "nomic-embed-text") -> None:
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        import requests

        results = []
        for text in texts:
            resp = requests.post(
                "http://localhost:11434/api/embeddings",
                json={"model": self._model, "prompt": text},
                timeout=30,
            )
            resp.raise_for_status()
            results.append(resp.json()["embedding"])
        return results

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]


def create_provider(
    provider: str = "fastembed", model: Optional[str] = None
) -> EmbeddingProvider:
    """Factory para crear el provider de embeddings."""
    if provider == "fastembed":
        return FastEmbedProvider(model=model or "BAAI/bge-small-en-v1.5")
    elif provider == "ollama":
        return OllamaProvider(model=model or "nomic-embed-text")
    else:
        raise ValueError(f"Provider desconocido: {provider}. Usa 'fastembed' o 'ollama'.")
