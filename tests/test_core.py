"""Tests de los módulos core de Claude Vestige."""

from pathlib import Path

import pytest

from claude_vestige.config import (
    build_exclude_spec,
    find_config_upwards,
    find_markdown_files,
    generate_config_toml,
    load_config,
    resolve_include_files,
)
from claude_vestige.embeddings import create_provider
from claude_vestige.ingester import Chunk, chunk_markdown, ingest_files
from claude_vestige.store import VectorStore
from claude_vestige.memory import save_memory, VALID_MEMORY_TYPES
from claude_vestige.bootstrap import auto_bootstrap, bootstrap_project, detect_stack, count_files_by_extension


class TestEmbeddings:
    def test_create_fastembed_provider(self):
        provider = create_provider("fastembed")
        assert provider is not None

    def test_embed_returns_list_of_floats(self):
        provider = create_provider("fastembed")
        result = provider.embed(["hello world"])
        assert len(result) == 1
        assert isinstance(result[0], list)
        assert isinstance(result[0][0], float)

    def test_embed_query_returns_list_of_floats(self):
        provider = create_provider("fastembed")
        result = provider.embed_query("hello world")
        assert isinstance(result, list)
        assert isinstance(result[0], float)

    def test_invalid_provider_raises(self):
        with pytest.raises(ValueError):
            create_provider("invalid")


class TestConfig:
    def test_load_config_returns_none_without_file(self, tmp_project):
        assert load_config(tmp_project) is None

    def test_generate_and_load_config(self, tmp_project):
        generate_config_toml(tmp_project, "test-project", ["README.md"])
        config = load_config(tmp_project)
        assert config is not None
        assert config.name == "test-project"
        assert config.include == ["README.md"]
        assert config.project_id == "test-project"

    def test_find_config_upwards(self, tmp_project):
        generate_config_toml(tmp_project, "test", ["README.md"])
        subdir = tmp_project / "src" / "deep"
        subdir.mkdir(parents=True)
        result = find_config_upwards(subdir)
        assert result == tmp_project

    def test_find_config_upwards_returns_none(self, tmp_project):
        assert find_config_upwards(tmp_project) is None

    def test_build_exclude_spec_blocks_node_modules(self, tmp_project):
        spec = build_exclude_spec(tmp_project)
        assert spec.match_file("node_modules/foo/README.md")
        assert spec.match_file("apps/node_modules/bar.js")
        assert spec.match_file(".env")
        assert spec.match_file("secrets.pem")

    def test_build_exclude_spec_allows_normal_files(self, tmp_project):
        spec = build_exclude_spec(tmp_project)
        assert not spec.match_file("src/main.py")
        assert not spec.match_file("README.md")

    def test_resolve_include_files(self, tmp_project_with_readme):
        spec = build_exclude_spec(tmp_project_with_readme)
        files = resolve_include_files(tmp_project_with_readme, ["README.md"], spec)
        assert len(files) == 1
        assert files[0].name == "README.md"

    def test_find_markdown_files(self, tmp_project_with_readme):
        spec = build_exclude_spec(tmp_project_with_readme)
        files = find_markdown_files(tmp_project_with_readme, spec)
        assert len(files) == 1


class TestIngester:
    def test_chunk_markdown_splits_by_headers(self, tmp_project_with_readme):
        readme = tmp_project_with_readme / "README.md"
        chunks = chunk_markdown(readme, tmp_project_with_readme)
        assert len(chunks) > 1
        assert all(isinstance(c, Chunk) for c in chunks)
        assert all(c.metadata["file"] == "README.md" for c in chunks)

    def test_chunk_ids_are_deterministic(self, tmp_project_with_readme):
        readme = tmp_project_with_readme / "README.md"
        chunks1 = chunk_markdown(readme, tmp_project_with_readme)
        chunks2 = chunk_markdown(readme, tmp_project_with_readme)
        assert [c.id for c in chunks1] == [c.id for c in chunks2]

    def test_ingest_files_returns_chunks_with_embeddings(self, tmp_project_with_readme):
        provider = create_provider("fastembed")
        readme = tmp_project_with_readme / "README.md"
        results = ingest_files([readme], tmp_project_with_readme, provider)
        assert len(results) > 0
        chunk, embedding = results[0]
        assert isinstance(chunk, Chunk)
        assert isinstance(embedding, list)
        assert isinstance(embedding[0], float)


class TestStore:
    def test_upsert_and_search(self, tmp_project):
        provider = create_provider("fastembed")
        store = VectorStore(tmp_project / ".claude-vestige" / "db")

        chunk = Chunk(id="test1", content="PostgreSQL is our database", metadata={"file": "test.md", "section": "db", "last_modified": 1.0})
        embedding = provider.embed_query("PostgreSQL is our database")
        store.upsert_docs([(chunk, embedding)])

        query_emb = provider.embed_query("what database do we use")
        results = store.search(query_embedding=query_emb, query_text="what database do we use", n=5)
        assert len(results) == 1
        assert results[0].id == "test1"
        assert "PostgreSQL" in results[0].content

    def test_get_chunks_by_ids(self, tmp_project):
        provider = create_provider("fastembed")
        store = VectorStore(tmp_project / ".claude-vestige" / "db")

        chunk = Chunk(id="test2", content="FastAPI for the backend", metadata={"file": "arch.md", "section": "stack", "last_modified": 1.0})
        embedding = provider.embed_query("FastAPI for the backend")
        store.upsert_docs([(chunk, embedding)])

        results = store.get_chunks_by_ids(["test2"])
        assert len(results) == 1
        assert results[0].content == "FastAPI for the backend"

    def test_delete_docs_for_file(self, tmp_project):
        provider = create_provider("fastembed")
        store = VectorStore(tmp_project / ".claude-vestige" / "db")

        chunk = Chunk(id="del1", content="to be deleted", metadata={"file": "old.md", "section": "x", "last_modified": 1.0})
        embedding = provider.embed_query("to be deleted")
        store.upsert_docs([(chunk, embedding)])

        store.delete_docs_for_file("old.md")
        assert store.get_stats()["docs_chunks"] == 0

    def test_get_stats(self, tmp_project):
        store = VectorStore(tmp_project / ".claude-vestige" / "db")
        stats = store.get_stats()
        assert stats["docs_chunks"] == 0
        assert stats["sessions_chunks"] == 0
        assert stats["total_chunks"] == 0

    def test_sessions_collection_separate(self, tmp_project):
        provider = create_provider("fastembed")
        store = VectorStore(tmp_project / ".claude-vestige" / "db")

        doc = Chunk(id="doc1", content="doc content", metadata={"file": "a.md", "section": "x", "last_modified": 1.0})
        session = Chunk(id="ses1", content="session content", metadata={"file": "memory", "section": "note", "last_modified": 1.0})

        doc_emb = provider.embed_query("doc content")
        ses_emb = provider.embed_query("session content")

        store.upsert_docs([(doc, doc_emb)])
        store.upsert_sessions([(session, ses_emb)])

        stats = store.get_stats()
        assert stats["docs_chunks"] == 1
        assert stats["sessions_chunks"] == 1


class TestMemory:
    def test_save_memory_valid(self, tmp_project):
        provider = create_provider("fastembed")
        config = type("C", (), {"db_path": tmp_project / ".claude-vestige" / "db"})()
        store = VectorStore(config.db_path)

        result = save_memory("Decided to use JWT", "decision", ["auth"], config, provider, store)
        assert "id" in result
        assert result["status"] == "saved"
        assert store.get_stats()["sessions_chunks"] == 1

    def test_save_memory_invalid_type(self, tmp_project):
        provider = create_provider("fastembed")
        config = type("C", (), {"db_path": tmp_project / ".claude-vestige" / "db"})()
        store = VectorStore(config.db_path)

        result = save_memory("test", "invalid_type", [], config, provider, store)
        assert "error" in result

    def test_save_memory_empty_content(self, tmp_project):
        provider = create_provider("fastembed")
        config = type("C", (), {"db_path": tmp_project / ".claude-vestige" / "db"})()
        store = VectorStore(config.db_path)

        result = save_memory("", "note", [], config, provider, store)
        assert "error" in result


class TestBootstrap:
    def test_detect_stack_python(self, tmp_python_project):
        stack = detect_stack(tmp_python_project)
        assert "Python" in stack

    def test_detect_stack_empty(self, tmp_project):
        stack = detect_stack(tmp_project)
        assert stack == []

    def test_auto_bootstrap_with_readme(self, tmp_project_with_readme):
        result = auto_bootstrap(tmp_project_with_readme)
        assert result is not None
        assert "indexados" in result
        config = load_config(tmp_project_with_readme)
        assert config is not None
        assert "README.md" in config.include

    def test_auto_bootstrap_without_docs(self, tmp_project):
        result = auto_bootstrap(tmp_project)
        assert result is None

    def test_bootstrap_project_with_include_files(self, tmp_project_with_readme):
        result = bootstrap_project(tmp_project_with_readme, include_files=["README.md"])
        assert "indexados" in result

    def test_bootstrap_project_discover_mode(self, tmp_project_with_readme):
        result = bootstrap_project(tmp_project_with_readme)
        assert "candidatos" in result.lower() or "indexados" in result.lower()

    def test_count_files_by_extension(self, tmp_python_project):
        spec = build_exclude_spec(tmp_python_project)
        counts = count_files_by_extension(tmp_python_project, spec)
        assert ".py" in counts
        assert counts[".py"] == 2
