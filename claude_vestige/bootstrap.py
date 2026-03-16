"""Detección de stack, inicialización de proyectos y indexación."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from claude_vestige.config import (
    ProjectConfig,
    build_exclude_spec,
    find_markdown_files,
    generate_config_toml,
    load_config,
    resolve_include_files,
)
from claude_vestige.embeddings import EmbeddingProvider, create_provider
from claude_vestige.ingester import ingest_files
from claude_vestige.store import VectorStore

def _get_registry_path() -> Path:
    """Retorna el path del registry. Configurable via CLAUDE_VESTIGE_REGISTRY para tests."""
    custom = os.environ.get("CLAUDE_VESTIGE_REGISTRY")
    if custom:
        return Path(custom)
    return Path.home() / ".claude-vestige" / "projects.json"

# Indicadores de stack por archivos marcadores
STACK_INDICATORS: dict[str, str] = {
    "package.json": "Node.js",
    "pyproject.toml": "Python",
    "setup.py": "Python",
    "requirements.txt": "Python",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "composer.json": "PHP",
    "Gemfile": "Ruby",
    "pom.xml": "Java",
    "build.gradle": "Java",
    "build.gradle.kts": "Kotlin",
    "mix.exs": "Elixir",
    "pubspec.yaml": "Dart/Flutter",
    "Package.swift": "Swift",
    "CMakeLists.txt": "C/C++",
    "Makefile": "C/C++",
    "*.csproj": "C#/.NET",
    "*.sln": "C#/.NET",
}

# Detección de frameworks por dependencias en package.json
PACKAGE_JSON_DEPS: dict[str, str] = {
    "next": "Next.js",
    "react": "React",
    "vue": "Vue",
    "angular": "Angular",
    "express": "Express",
    "fastify": "Fastify",
    "nestjs": "NestJS",
    "svelte": "Svelte",
    "nuxt": "Nuxt",
}

# Detección de frameworks Python
PYTHON_INDICATORS: dict[str, str] = {
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "sqlalchemy": "SQLAlchemy",
    "prisma": "Prisma",
}


def detect_stack(project_root: Path) -> list[str]:
    """Detecta el stack tecnológico del proyecto."""
    stack: list[str] = []
    seen: set[str] = set()

    for marker, tech in STACK_INDICATORS.items():
        if "*" in marker:
            if list(project_root.glob(marker)):
                if tech not in seen:
                    stack.append(tech)
                    seen.add(tech)
        elif (project_root / marker).exists():
            if tech not in seen:
                stack.append(tech)
                seen.add(tech)

    # Sub-detección para Node.js
    pkg_path = project_root / "package.json"
    if pkg_path.exists():
        try:
            import json

            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
            all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            for dep, framework in PACKAGE_JSON_DEPS.items():
                if dep in all_deps and framework not in seen:
                    stack.append(framework)
                    seen.add(framework)
        except Exception:
            pass

    # Sub-detección para Python
    pyproject_path = project_root / "pyproject.toml"
    if pyproject_path.exists():
        try:
            content = pyproject_path.read_text(encoding="utf-8").lower()
            for dep, framework in PYTHON_INDICATORS.items():
                if dep in content and framework not in seen:
                    stack.append(framework)
                    seen.add(framework)
        except Exception:
            pass

    return stack


def count_files_by_extension(project_root: Path, exclude_spec) -> dict[str, int]:
    """Cuenta archivos por extensión, respetando exclusiones."""
    counts: dict[str, int] = {}
    try:
        for f in project_root.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(project_root)
            if exclude_spec.match_file(str(rel)):
                continue
            ext = f.suffix.lower()
            if ext:
                counts[ext] = counts.get(ext, 0) + 1
    except Exception:
        pass

    # Ordenar por cantidad descendente, top 10
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10])


def bootstrap_project(
    project_path: Optional[Path] = None,
    include_files: Optional[list[str]] = None,
) -> str:
    """Inicializa un proyecto: detecta stack, genera config, indexa archivos."""
    project_root = (project_path or Path.cwd()).resolve()

    if not project_root.is_dir():
        return f"Error: {project_root} no es un directorio válido."

    # Si ya existe config, re-indexar
    config = load_config(project_root)
    if config:
        return _index_existing_config(config)

    # Si se proporcionan archivos específicos, generar config e indexar
    if include_files:
        return _bootstrap_with_files(project_root, include_files)

    # Si no, modo descubrimiento: retornar candidatos
    return _discover_candidates(project_root)


def auto_bootstrap(project_root: Path) -> Optional[str]:
    """Auto-bootstrap: indexa README.md y CLAUDE.md si existen. Retorna None si no hay nada."""
    auto_files: list[str] = []

    for filename in ["README.md", "CLAUDE.md"]:
        if (project_root / filename).exists():
            auto_files.append(filename)

    if not auto_files:
        return None

    return _bootstrap_with_files(project_root, auto_files)


def _register_project(config: ProjectConfig) -> None:
    """Registra el proyecto en ~/.claude-vestige/projects.json."""
    import json

    try:
        _get_registry_path().parent.mkdir(parents=True, exist_ok=True)
        registry = []
        if _get_registry_path().exists():
            registry = json.loads(_get_registry_path().read_text(encoding="utf-8"))

        # Actualizar o agregar
        existing = [p for p in registry if p.get("root") == str(config.root)]
        if existing:
            existing[0]["name"] = config.name
        else:
            registry.append({"name": config.name, "root": str(config.root)})

        _get_registry_path().write_text(json.dumps(registry, indent=2), encoding="utf-8")
    except Exception:
        pass


def _index_existing_config(config: ProjectConfig) -> str:
    """Re-indexa un proyecto con config existente."""
    try:
        provider = create_provider(config.embeddings_provider, config.embeddings_model)
        store = VectorStore(config.db_path)
        exclude_spec = build_exclude_spec(config.root, config.exclude_extra)
        files = resolve_include_files(config.root, config.include, exclude_spec)

        if not files:
            return f"Proyecto '{config.name}': no se encontraron archivos para indexar."

        chunks_with_embeddings = ingest_files(files, config.root, provider)
        count = store.upsert_docs(chunks_with_embeddings)

        _register_project(config)

        return f"Proyecto '{config.name}': indexados {len(files)} archivos, {count} chunks."
    except Exception as e:
        return f"Error al indexar '{config.name}': {e}"


def _bootstrap_with_files(project_root: Path, include_files: list[str]) -> str:
    """Genera config.toml con los archivos dados e indexa."""
    try:
        name = project_root.name
        generate_config_toml(project_root, name, include_files)
        config = load_config(project_root)
        if not config:
            return "Error: no se pudo generar config.toml."
        return _index_existing_config(config)
    except Exception as e:
        return f"Error en bootstrap: {e}"


def _discover_candidates(project_root: Path) -> str:
    """Modo descubrimiento: retorna stack y archivos candidatos."""
    stack = detect_stack(project_root)
    stack_str = ", ".join(stack) if stack else "no detectado"

    exclude_spec = build_exclude_spec(project_root)
    md_files = find_markdown_files(project_root, exclude_spec)
    candidates = [str(f.relative_to(project_root)) for f in md_files]

    result = f"Stack detectado: [{stack_str}]\n"
    result += f"Archivos candidatos para contexto ({len(candidates)}):\n"
    for c in candidates[:20]:
        result += f"  - {c}\n"
    if len(candidates) > 20:
        result += f"  ... y {len(candidates) - 20} más\n"
    result += "\nUsa /claude_vestige:bootstrap para elegir qué archivos indexar."

    return result
