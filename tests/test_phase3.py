"""Tests de Fase 3: Skills, MCP, Dashboard."""

import json
from pathlib import Path

import pytest
import yaml

from claude_vestige.config import load_config
from claude_vestige.store import VectorStore


PLUGIN_DIR = Path(__file__).parent.parent / "claude-vestige-plugin"


class TestSkills:
    def test_bootstrap_skill_exists(self):
        skill_path = PLUGIN_DIR / "skills" / "bootstrap" / "SKILL.md"
        assert skill_path.exists()

    def test_bootstrap_skill_has_valid_frontmatter(self):
        skill_path = PLUGIN_DIR / "skills" / "bootstrap" / "SKILL.md"
        content = skill_path.read_text()
        # Extraer frontmatter entre ---
        parts = content.split("---", 2)
        assert len(parts) >= 3, "SKILL.md debe tener frontmatter YAML entre ---"
        fm = yaml.safe_load(parts[1])
        assert "name" in fm
        assert fm["name"] == "bootstrap"
        assert "description" in fm
        assert fm.get("user-invocable") is True

    def test_search_skill_exists(self):
        skill_path = PLUGIN_DIR / "skills" / "search" / "SKILL.md"
        assert skill_path.exists()

    def test_search_skill_has_valid_frontmatter(self):
        skill_path = PLUGIN_DIR / "skills" / "search" / "SKILL.md"
        content = skill_path.read_text()
        parts = content.split("---", 2)
        assert len(parts) >= 3
        fm = yaml.safe_load(parts[1])
        assert fm["name"] == "search"
        assert "description" in fm
        assert fm.get("user-invocable") is True


class TestMcpJson:
    def test_mcp_json_exists(self):
        mcp_path = PLUGIN_DIR / ".mcp.json"
        assert mcp_path.exists()

    def test_mcp_json_is_valid(self):
        mcp_path = PLUGIN_DIR / ".mcp.json"
        data = json.loads(mcp_path.read_text())
        assert "mcpServers" in data
        assert "claude_vestige" in data["mcpServers"]

    def test_mcp_json_has_stdio_type(self):
        mcp_path = PLUGIN_DIR / ".mcp.json"
        data = json.loads(mcp_path.read_text())
        server = data["mcpServers"]["claude_vestige"]
        assert server["type"] == "stdio"
        assert "python" in server["command"]


class TestPluginJson:
    def test_plugin_json_exists(self):
        plugin_path = PLUGIN_DIR / ".claude-plugin" / "plugin.json"
        assert plugin_path.exists()

    def test_plugin_json_has_required_fields(self):
        plugin_path = PLUGIN_DIR / ".claude-plugin" / "plugin.json"
        data = json.loads(plugin_path.read_text())
        assert "name" in data
        assert "version" in data
        assert "description" in data


class TestPluginClaude:
    def test_plugin_claude_md_exists(self):
        claude_path = PLUGIN_DIR / "CLAUDE.md"
        assert claude_path.exists()

    def test_plugin_claude_md_has_content(self):
        claude_path = PLUGIN_DIR / "CLAUDE.md"
        content = claude_path.read_text()
        assert "retrieve_context" in content
        assert "get_chunks" in content
        assert "save_memory" in content


class TestDashboard:
    def test_dashboard_html_exists(self):
        html_path = PLUGIN_DIR / "dashboard.html"
        assert html_path.exists()

    def test_dashboard_html_has_structure(self):
        html_path = PLUGIN_DIR / "dashboard.html"
        content = html_path.read_text()
        assert "<html" in content
        assert "Claude Vestige" in content
        assert "/api/projects" in content
        assert "/api/search" in content


class TestApiEndpoints:
    """Tests de los endpoints del dashboard API."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from claude_vestige.api import app
        return TestClient(app)

    def test_health(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_projects_empty(self, client):
        response = client.get("/api/projects")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_search_requires_params(self, client):
        response = client.get("/api/search")
        assert response.status_code == 422  # Missing required params

    def test_search_with_invalid_project(self, client):
        response = client.get("/api/search?query=test&project_root=/nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    def test_dashboard_html_served(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "Claude Vestige" in response.text

    def test_sessions_with_invalid_project(self, client):
        response = client.get("/api/sessions//nonexistent")
        assert response.status_code == 200

    def test_stats_with_invalid_project(self, client):
        response = client.get("/api/stats//nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    def test_search_on_indexed_project(self, client, tmp_project_with_config):
        response = client.get(
            f"/api/search?query=test&project_root={tmp_project_with_config}&n=5"
        )
        assert response.status_code == 200
        results = response.json()
        assert isinstance(results, list)
        assert len(results) > 0

    def test_stats_on_indexed_project(self, client, tmp_project_with_config):
        response = client.get(f"/api/stats/{tmp_project_with_config}")
        assert response.status_code == 200
        data = response.json()
        assert "docs_chunks" in data
        assert data["docs_chunks"] > 0
