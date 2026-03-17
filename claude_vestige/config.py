"""Carga de configuración y resolución de archivos."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pathspec

DEFAULT_EXCLUDES: list[str] = [
    ".env*",
    "*.pem",
    "*.key",
    "*.p12",
    "**/node_modules/",
    "**/.git/",
    "**/dist/",
    "**/build/",
    "**/__pycache__/",
    "**/.venv/",
    "**/venv/",
    "**/.claude-vestige/db/",
]

MAX_FILE_SIZE = 1_048_576  # 1 MB


@dataclass
class ProjectConfig:
    """Configuración de un proyecto indexado."""

    name: str
    root: Path
    include: list[str] = field(default_factory=list)
    exclude_extra: list[str] = field(default_factory=list)
    embeddings_provider: str = "fastembed"
    embeddings_model: Optional[str] = None

    @property
    def project_id(self) -> str:
        return self.name.lower().replace(" ", "-").replace("_", "-")

    @property
    def config_dir(self) -> Path:
        return self.root / ".claude-vestige"

    @property
    def db_path(self) -> Path:
        return self.config_dir / "db"

    @property
    def config_path(self) -> Path:
        return self.config_dir / "config.toml"


def load_config(project_root: Path) -> Optional[ProjectConfig]:
    """Carga config.toml de un proyecto. Retorna None si no existe."""
    config_path = project_root / ".claude-vestige" / "config.toml"
    if not config_path.exists():
        return None

    data = tomllib.loads(config_path.read_text(encoding="utf-8"))

    project = data.get("project", {})
    indexing = data.get("indexing", {})
    embeddings = data.get("embeddings", {})

    return ProjectConfig(
        name=project.get("name", project_root.name),
        root=Path(project.get("root", str(project_root))),
        include=indexing.get("include", []),
        exclude_extra=indexing.get("exclude_extra", []),
        embeddings_provider=embeddings.get("provider", "fastembed"),
        embeddings_model=embeddings.get("model"),
    )


def find_config_upwards(start: Path) -> Optional[Path]:
    """Busca .claude-vestige/config.toml subiendo en el árbol de directorios."""
    current = start.resolve()
    while current != current.parent:
        config = current / ".claude-vestige" / "config.toml"
        if config.exists():
            return current
        current = current.parent
    return None


def build_exclude_spec(
    project_root: Path, extra_excludes: list[str] | None = None
) -> pathspec.PathSpec:
    """Construye PathSpec combinando .gitignore + defaults (defaults al final = máxima prioridad)."""
    patterns: list[str] = []

    # .gitignore primero (menor prioridad)
    gitignore_path = project_root / ".gitignore"
    if gitignore_path.exists():
        gitignore_text = gitignore_path.read_text(encoding="utf-8", errors="ignore")
        for line in gitignore_text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)

    if extra_excludes:
        patterns.extend(extra_excludes)

    # Defaults al final — SIEMPRE excluir node_modules, .git, etc.
    patterns.extend(DEFAULT_EXCLUDES)

    return pathspec.PathSpec.from_lines("gitignore", patterns)


def resolve_include_files(
    project_root: Path, include: list[str], exclude_spec: pathspec.PathSpec
) -> list[Path]:
    """Resuelve los globs de include contra el filesystem, aplicando exclusiones.

    Archivos explícitos (sin wildcards) solo se verifican contra DEFAULT_EXCLUDES
    de seguridad (.env, .key, etc.), ignorando .gitignore. Si el usuario pide
    indexar un archivo específico, se respeta.

    Patrones con wildcards sí respetan .gitignore + DEFAULT_EXCLUDES.
    """
    security_spec = pathspec.PathSpec.from_lines("gitignore", DEFAULT_EXCLUDES)
    files: list[Path] = []
    seen: set[Path] = set()

    for pattern in include:
        is_explicit = "*" not in pattern and "?" not in pattern
        for match in project_root.glob(pattern):
            if not match.is_file():
                continue
            if match in seen:
                continue
            if match.stat().st_size > MAX_FILE_SIZE:
                continue
            rel = match.relative_to(project_root)
            if is_explicit:
                if security_spec.match_file(str(rel)):
                    continue
            else:
                if exclude_spec.match_file(str(rel)):
                    continue
            seen.add(match)
            files.append(match)

    return sorted(files)


def find_markdown_files(
    project_root: Path, exclude_spec: pathspec.PathSpec
) -> list[Path]:
    """Encuentra todos los .md en el proyecto, respetando exclusiones."""
    files: list[Path] = []

    for md in project_root.rglob("*.md"):
        if not md.is_file():
            continue
        if md.stat().st_size > MAX_FILE_SIZE:
            continue
        rel = md.relative_to(project_root)
        if exclude_spec.match_file(str(rel)):
            continue
        files.append(md)

    return sorted(files)


def generate_config_toml(
    project_root: Path, name: str, include: list[str], provider: str = "fastembed"
) -> Path:
    """Genera .claude-vestige/config.toml para un proyecto."""
    config_dir = project_root / ".claude-vestige"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Crear .gitignore para que git ignore esta carpeta automáticamente
    gitignore = config_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8")

    include_str = ", ".join(f'"{f}"' for f in include)
    content = f"""[project]
name = "{name}"
root = "{project_root}"

[indexing]
include = [{include_str}]
exclude_extra = []

[embeddings]
provider = "{provider}"
"""
    config_path = config_dir / "config.toml"
    config_path.write_text(content, encoding="utf-8")
    return config_path
