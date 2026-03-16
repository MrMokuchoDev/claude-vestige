"""Fixtures compartidos para tests."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_registry(tmp_path, monkeypatch):
    """Aísla el registry global para que los tests no contaminen ~/.claude-vestige/projects.json."""
    registry_path = tmp_path / "test_registry.json"
    monkeypatch.setenv("CLAUDE_VESTIGE_REGISTRY", str(registry_path))


@pytest.fixture
def tmp_project(tmp_path):
    """Crea un directorio temporal como proyecto de prueba."""
    return tmp_path


@pytest.fixture
def tmp_project_with_readme(tmp_path):
    """Proyecto con README.md."""
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Test Project\n\n"
        "## Overview\n\n"
        "This is a test project for Claude Vestige.\n\n"
        "## Architecture\n\n"
        "Uses Python with FastAPI.\n\n"
        "## Decisions\n\n"
        "We chose PostgreSQL for the database.\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def tmp_project_with_config(tmp_project_with_readme):
    """Proyecto con config.toml + README.md ya indexados."""
    from claude_vestige.bootstrap import auto_bootstrap

    auto_bootstrap(tmp_project_with_readme)
    return tmp_project_with_readme


@pytest.fixture
def tmp_python_project(tmp_path):
    """Proyecto Python sin docs."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
    (tmp_path / "main.py").write_text("print('hello')\n")
    (tmp_path / "utils.py").write_text("def helper(): pass\n")
    return tmp_path
