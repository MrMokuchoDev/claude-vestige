"""Tests del hook session_start.py."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_SCRIPT = Path(__file__).parent.parent / "claude-vestige-plugin" / "hooks" / "session_start.py"
PYTHON = sys.executable


def run_hook(cwd: str) -> subprocess.CompletedProcess:
    """Ejecuta el hook como subproceso, simulando cómo lo llama Claude Code."""
    input_json = json.dumps({"cwd": cwd, "session_id": "test-session"})
    return subprocess.run(
        [PYTHON, str(HOOK_SCRIPT)],
        input=input_json,
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestSessionStartHook:
    def test_configured_project_injects_context(self, tmp_project_with_config):
        """Proyecto ya indexado → output contiene chunks."""
        result = run_hook(str(tmp_project_with_config))
        assert result.returncode == 0
        assert "[Claude Vestige]" in result.stdout
        assert "Memoria semántica activa" in result.stdout
        assert "doc chunks" in result.stdout

    def test_unconfigured_project_with_readme_auto_bootstraps(self, tmp_project_with_readme):
        """Proyecto sin config pero con README → auto-bootstrap."""
        result = run_hook(str(tmp_project_with_readme))
        assert result.returncode == 0
        assert "Auto-indexado" in result.stdout
        assert "Memoria semántica activa" in result.stdout

    def test_empty_project_shows_basic_scan(self, tmp_python_project):
        """Proyecto sin docs → escaneo básico."""
        result = run_hook(str(tmp_python_project))
        assert result.returncode == 0
        assert "Stack:" in result.stdout
        assert "Python" in result.stdout
        assert "bootstrap" in result.stdout

    def test_completely_empty_project(self, tmp_project):
        """Proyecto vacío → no crashea."""
        result = run_hook(str(tmp_project))
        assert result.returncode == 0
        assert "[Claude Vestige]" in result.stdout

    def test_empty_stdin_does_not_crash(self):
        """Sin stdin → usa cwd, no crashea."""
        result = subprocess.run(
            [PYTHON, str(HOOK_SCRIPT)],
            input="",
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0

    def test_invalid_json_stdin_does_not_crash(self):
        """JSON inválido → no crashea."""
        result = subprocess.run(
            [PYTHON, str(HOOK_SCRIPT)],
            input="not json",
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0

    def test_second_run_uses_existing_index(self, tmp_project_with_readme):
        """Segunda ejecución usa índice existente, no re-bootstrapea."""
        # Primera ejecución: auto-bootstrap
        result1 = run_hook(str(tmp_project_with_readme))
        assert "Auto-indexado" in result1.stdout

        # Segunda ejecución: usa índice existente
        result2 = run_hook(str(tmp_project_with_readme))
        assert "Auto-indexado" not in result2.stdout
        assert "Memoria semántica activa" in result2.stdout
