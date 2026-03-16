"""Tests del Stop hook y pipeline end-to-end (Fase 4)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from claude_vestige.config import load_config
from claude_vestige.store import VectorStore

HOOK_STOP = Path(__file__).parent.parent / "claude-vestige-plugin" / "hooks" / "stop.py"
HOOK_USER_PROMPT = Path(__file__).parent.parent / "claude-vestige-plugin" / "hooks" / "user_prompt.py"
HOOK_SAVE_OBS = Path(__file__).parent.parent / "claude-vestige-plugin" / "hooks" / "save_observation.py"
PYTHON = sys.executable


class TestStopHook:
    def test_cleanup_prompt_file(self, tmp_path):
        """Stop hook limpia current_prompt.txt."""
        cf_dir = tmp_path / ".claude-vestige"
        cf_dir.mkdir()
        prompt_file = cf_dir / "current_prompt.txt"
        prompt_file.write_text("test prompt")

        input_json = json.dumps({"cwd": str(tmp_path)})
        result = subprocess.run(
            [PYTHON, str(HOOK_STOP)],
            input=input_json,
            capture_output=True,
            text=True,
            timeout=10,
            env={**__import__("os").environ, "HOME": str(tmp_path)},
        )
        assert result.returncode == 0
        assert not prompt_file.exists()

    def test_cleanup_session_log(self, tmp_path):
        """Stop hook limpia session_observations.jsonl."""
        cf_dir = tmp_path / ".claude-vestige"
        cf_dir.mkdir()
        session_log = cf_dir / "session_observations.jsonl"
        session_log.write_text('{"observation": "test"}\n')

        input_json = json.dumps({"cwd": str(tmp_path)})
        result = subprocess.run(
            [PYTHON, str(HOOK_STOP)],
            input=input_json,
            capture_output=True,
            text=True,
            timeout=10,
            env={**__import__("os").environ, "HOME": str(tmp_path)},
        )
        assert result.returncode == 0
        assert not session_log.exists()

    def test_no_observations_no_summary(self, tmp_project_with_config, tmp_path):
        """Sin observaciones, no guarda resumen pero sí limpia."""
        input_json = json.dumps({"cwd": str(tmp_project_with_config)})
        result = subprocess.run(
            [PYTHON, str(HOOK_STOP)],
            input=input_json,
            capture_output=True,
            text=True,
            timeout=60,
            env={**__import__("os").environ, "HOME": str(tmp_path)},
        )
        assert result.returncode == 0
        # Sin observaciones, no hay resumen que guardar
        assert "summary saved" not in result.stdout.lower()

    def test_saves_session_summary(self, tmp_project_with_config, tmp_path):
        """Con observaciones, guarda resumen en ChromaDB."""
        # Simular session log con observaciones
        cf_dir = tmp_path / ".claude-vestige"
        cf_dir.mkdir(parents=True, exist_ok=True)
        session_log = cf_dir / "session_observations.jsonl"
        observations = [
            {"observation": "Implementado auth.py con JWT para autenticación stateless"},
            {"observation": "Agregado middleware de validación de tokens en api.py"},
            {"observation": "Creados tests de autenticación con 5 casos de prueba"},
        ]
        session_log.write_text(
            "\n".join(json.dumps(o) for o in observations) + "\n"
        )

        input_json = json.dumps({"cwd": str(tmp_project_with_config)})
        result = subprocess.run(
            [PYTHON, str(HOOK_STOP)],
            input=input_json,
            capture_output=True,
            text=True,
            timeout=60,
            env={**__import__("os").environ, "HOME": str(tmp_path)},
        )
        assert result.returncode == 0
        assert "3 observations" in result.stdout

        # Verificar que el resumen se guardó en ChromaDB
        config = load_config(tmp_project_with_config)
        store = VectorStore(config.db_path)
        stats = store.get_stats()
        assert stats["sessions_chunks"] >= 1

        # Verificar que los temporales se limpiaron
        assert not session_log.exists()

    def test_single_observation_summary(self, tmp_project_with_config, tmp_path):
        """Una sola observación genera resumen simple."""
        cf_dir = tmp_path / ".claude-vestige"
        cf_dir.mkdir(parents=True, exist_ok=True)
        session_log = cf_dir / "session_observations.jsonl"
        session_log.write_text(
            json.dumps({"observation": "Corregido bug en parser de config.toml"}) + "\n"
        )

        input_json = json.dumps({"cwd": str(tmp_project_with_config)})
        result = subprocess.run(
            [PYTHON, str(HOOK_STOP)],
            input=input_json,
            capture_output=True,
            text=True,
            timeout=60,
            env={**__import__("os").environ, "HOME": str(tmp_path)},
        )
        assert result.returncode == 0
        assert "1 observations" in result.stdout

    def test_invalid_json_does_not_crash(self):
        """JSON inválido no crashea."""
        result = subprocess.run(
            [PYTHON, str(HOOK_STOP)],
            input="not json",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_no_cwd_still_cleans_up(self, tmp_path):
        """Sin cwd, limpia temporales pero no guarda resumen."""
        cf_dir = tmp_path / ".claude-vestige"
        cf_dir.mkdir()
        prompt_file = cf_dir / "current_prompt.txt"
        prompt_file.write_text("test")
        session_log = cf_dir / "session_observations.jsonl"
        session_log.write_text('{"observation": "test"}\n')

        result = subprocess.run(
            [PYTHON, str(HOOK_STOP)],
            input="{}",
            capture_output=True,
            text=True,
            timeout=10,
            env={**__import__("os").environ, "HOME": str(tmp_path)},
        )
        assert result.returncode == 0
        assert not prompt_file.exists()
        assert not session_log.exists()


class TestHooksJsonComplete:
    def test_hooks_json_has_stop(self):
        """hooks.json incluye Stop hook."""
        hooks_path = Path(__file__).parent.parent / "claude-vestige-plugin" / "hooks" / "hooks.json"
        data = json.loads(hooks_path.read_text())
        assert "Stop" in data["hooks"]

    def test_stop_hook_is_command_type(self):
        """Stop hook es tipo command."""
        hooks_path = Path(__file__).parent.parent / "claude-vestige-plugin" / "hooks" / "hooks.json"
        data = json.loads(hooks_path.read_text())
        hook = data["hooks"]["Stop"][0]["hooks"][0]
        assert hook["type"] == "command"

    def test_all_hooks_present(self):
        """hooks.json tiene los 4 hooks: SessionStart, UserPromptSubmit, PostToolUse, Stop."""
        hooks_path = Path(__file__).parent.parent / "claude-vestige-plugin" / "hooks" / "hooks.json"
        data = json.loads(hooks_path.read_text())
        hooks = data["hooks"]
        expected = {"SessionStart", "UserPromptSubmit", "PostToolUse", "Stop"}
        assert set(hooks.keys()) == expected


class TestSaveObservationSessionLog:
    def test_observation_logged_to_session_file(self, tmp_project_with_config, tmp_path):
        """save_observation.py registra en session_observations.jsonl."""
        result = subprocess.run(
            [
                PYTHON, str(HOOK_SAVE_OBS),
                "--cwd", str(tmp_project_with_config),
                "--observation", "Test observation for session log",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            env={**__import__("os").environ, "HOME": str(tmp_path)},
        )
        assert result.returncode == 0

        session_log = tmp_path / ".claude-vestige" / "session_observations.jsonl"
        assert session_log.exists()
        entries = [json.loads(line) for line in session_log.read_text().strip().splitlines()]
        assert len(entries) == 1
        assert entries[0]["observation"] == "Test observation for session log"

    def test_multiple_observations_append(self, tmp_project_with_config, tmp_path):
        """Múltiples observaciones se acumulan en el log."""
        for i in range(3):
            subprocess.run(
                [
                    PYTHON, str(HOOK_SAVE_OBS),
                    "--cwd", str(tmp_project_with_config),
                    "--observation", f"Observation {i + 1}",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                env={**__import__("os").environ, "HOME": str(tmp_path)},
            )

        session_log = tmp_path / ".claude-vestige" / "session_observations.jsonl"
        entries = [json.loads(line) for line in session_log.read_text().strip().splitlines()]
        assert len(entries) == 3


class TestEndToEndPipeline:
    """Test del pipeline completo: UserPrompt → SaveObservation x3 → Stop."""

    def test_full_session_lifecycle(self, tmp_project_with_config, tmp_path):
        """Simula una sesión completa: prompt → observaciones → stop con resumen."""
        env = {**__import__("os").environ, "HOME": str(tmp_path)}
        cwd = str(tmp_project_with_config)

        # 1. UserPromptSubmit — captura el prompt
        subprocess.run(
            [PYTHON, str(HOOK_USER_PROMPT)],
            input=json.dumps({"prompt": "Implementa autenticación JWT"}),
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        prompt_file = tmp_path / ".claude-vestige" / "current_prompt.txt"
        assert prompt_file.exists()
        assert "JWT" in prompt_file.read_text()

        # 2. PostToolUse x3 — save_observation (simula lo que haría el agent)
        observations = [
            ("Creado auth.py con implementación JWT", "change"),
            ("Decisión: usar RS256 para firma de tokens", "decision"),
            ("Corregido bug en validación de expiración", "bug_fix"),
        ]
        for obs_text, obs_type in observations:
            subprocess.run(
                [
                    PYTHON, str(HOOK_SAVE_OBS),
                    "--cwd", cwd,
                    "--observation", obs_text,
                    "--type", obs_type,
                ],
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
            )

        # Verificar que se acumularon en ChromaDB
        config = load_config(tmp_project_with_config)
        store = VectorStore(config.db_path)
        stats = store.get_stats()
        assert stats["sessions_chunks"] >= 3

        # Verificar session log
        session_log = tmp_path / ".claude-vestige" / "session_observations.jsonl"
        assert session_log.exists()
        entries = [json.loads(l) for l in session_log.read_text().strip().splitlines()]
        assert len(entries) == 3

        # 3. Stop — resumen + limpieza
        result = subprocess.run(
            [PYTHON, str(HOOK_STOP)],
            input=json.dumps({"cwd": cwd}),
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        assert result.returncode == 0
        assert "3 observations" in result.stdout

        # Verificar que se guardó el resumen (ahora hay 4: 3 obs + 1 resumen)
        store2 = VectorStore(config.db_path)
        stats2 = store2.get_stats()
        assert stats2["sessions_chunks"] >= 4

        # Verificar limpieza
        assert not prompt_file.exists()
        assert not session_log.exists()

    def test_session_with_no_writes(self, tmp_project_with_config, tmp_path):
        """Sesión donde Claude solo lee — sin observaciones, solo limpieza."""
        env = {**__import__("os").environ, "HOME": str(tmp_path)}

        # 1. UserPromptSubmit
        subprocess.run(
            [PYTHON, str(HOOK_USER_PROMPT)],
            input=json.dumps({"prompt": "Explica la arquitectura del proyecto"}),
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

        # 2. No hay PostToolUse (solo lectura)

        # 3. Stop
        result = subprocess.run(
            [PYTHON, str(HOOK_STOP)],
            input=json.dumps({"cwd": str(tmp_project_with_config)}),
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        assert result.returncode == 0

        # Sin observaciones, no hay resumen
        assert "summary saved" not in result.stdout.lower()

        # Pero sí limpió el prompt
        prompt_file = tmp_path / ".claude-vestige" / "current_prompt.txt"
        assert not prompt_file.exists()
