"""Tests de captura de observaciones (Fase 2)."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from claude_vestige.config import load_config
from claude_vestige.store import VectorStore

HOOK_USER_PROMPT = Path(__file__).parent.parent / "claude-vestige-plugin" / "hooks" / "user_prompt.py"
HOOK_SAVE_OBS = Path(__file__).parent.parent / "claude-vestige-plugin" / "hooks" / "save_observation.py"
PYTHON = sys.executable


class TestUserPromptHook:
    def test_saves_prompt_to_file(self, tmp_path, monkeypatch):
        """UserPromptSubmit guarda el prompt en archivo temporal."""
        prompt_file = tmp_path / "current_prompt.txt"
        monkeypatch.setattr(
            "claude_vestige_plugin_hooks_user_prompt.PROMPT_FILE", prompt_file
        ) if False else None  # No podemos monkeypatch un script externo

        # Ejecutar como subproceso
        input_json = json.dumps({"prompt": "Implementa autenticación con JWT"})
        result = subprocess.run(
            [PYTHON, str(HOOK_USER_PROMPT)],
            input=input_json,
            capture_output=True,
            text=True,
            timeout=10,
            env={**__import__("os").environ, "HOME": str(tmp_path)},
        )
        assert result.returncode == 0

        saved_file = tmp_path / ".claude-vestige" / "current_prompt.txt"
        assert saved_file.exists()
        assert saved_file.read_text() == "Implementa autenticación con JWT"

    def test_empty_prompt_does_nothing(self, tmp_path):
        """Prompt vacío no crea archivo."""
        input_json = json.dumps({"prompt": ""})
        result = subprocess.run(
            [PYTHON, str(HOOK_USER_PROMPT)],
            input=input_json,
            capture_output=True,
            text=True,
            timeout=10,
            env={**__import__("os").environ, "HOME": str(tmp_path)},
        )
        assert result.returncode == 0
        assert not (tmp_path / ".claude-vestige" / "current_prompt.txt").exists()

    def test_invalid_json_does_not_crash(self, tmp_path):
        """JSON inválido no crashea."""
        result = subprocess.run(
            [PYTHON, str(HOOK_USER_PROMPT)],
            input="not json",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0


class TestSaveObservation:
    def test_saves_observation_to_chromadb(self, tmp_project_with_config):
        """save_observation.py guarda en ChromaDB."""
        result = subprocess.run(
            [
                PYTHON, str(HOOK_SAVE_OBS),
                "--cwd", str(tmp_project_with_config),
                "--observation", "Se implementó autenticación JWT porque el frontend es SPA stateless",
                "--type", "decision",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0
        assert "saved" in result.stdout.lower()

        # Verificar que se guardó en ChromaDB
        config = load_config(tmp_project_with_config)
        store = VectorStore(config.db_path)
        stats = store.get_stats()
        assert stats["sessions_chunks"] >= 1

    def test_saves_with_default_type(self, tmp_project_with_config):
        """Sin --type usa 'change' por defecto."""
        result = subprocess.run(
            [
                PYTHON, str(HOOK_SAVE_OBS),
                "--cwd", str(tmp_project_with_config),
                "--observation", "Editado auth.py: agregada validación de tokens",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0
        assert "saved" in result.stdout.lower()

    def test_no_config_does_not_crash(self, tmp_project):
        """Proyecto sin config no crashea."""
        result = subprocess.run(
            [
                PYTHON, str(HOOK_SAVE_OBS),
                "--cwd", str(tmp_project),
                "--observation", "test observation",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0

    def test_multiple_observations_accumulate(self, tmp_project_with_config):
        """Múltiples observaciones se acumulan en sessions."""
        for i in range(3):
            subprocess.run(
                [
                    PYTHON, str(HOOK_SAVE_OBS),
                    "--cwd", str(tmp_project_with_config),
                    "--observation", f"Observación de prueba número {i + 1}",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

        config = load_config(tmp_project_with_config)
        store = VectorStore(config.db_path)
        stats = store.get_stats()
        assert stats["sessions_chunks"] >= 3


class TestHooksJson:
    def test_hooks_json_is_valid(self):
        """hooks.json es JSON válido."""
        hooks_path = Path(__file__).parent.parent / "claude-vestige-plugin" / "hooks" / "hooks.json"
        data = json.loads(hooks_path.read_text())
        assert "hooks" in data

    def test_hooks_json_has_all_events(self):
        """hooks.json define SessionStart, UserPromptSubmit, PostToolUse."""
        hooks_path = Path(__file__).parent.parent / "claude-vestige-plugin" / "hooks" / "hooks.json"
        data = json.loads(hooks_path.read_text())
        hooks = data["hooks"]
        assert "SessionStart" in hooks
        assert "UserPromptSubmit" in hooks
        assert "PostToolUse" in hooks

    def test_post_tool_use_has_correct_matcher(self):
        """PostToolUse tiene matcher solo para Write|Edit|MultiEdit (no Bash)."""
        hooks_path = Path(__file__).parent.parent / "claude-vestige-plugin" / "hooks" / "hooks.json"
        data = json.loads(hooks_path.read_text())
        post_tool = data["hooks"]["PostToolUse"][0]
        assert "Write" in post_tool["matcher"]
        assert "Edit" in post_tool["matcher"]
        assert "Bash" not in post_tool["matcher"]

    def test_post_tool_use_is_command_type(self):
        """PostToolUse usa hook tipo command que llama a Haiku via claude CLI."""
        hooks_path = Path(__file__).parent.parent / "claude-vestige-plugin" / "hooks" / "hooks.json"
        data = json.loads(hooks_path.read_text())
        hook = data["hooks"]["PostToolUse"][0]["hooks"][0]
        assert hook["type"] == "command"
