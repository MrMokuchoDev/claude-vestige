# Claude Vestige — Arquitectura

## Visión general

Claude Vestige es un Plugin de Claude Code compuesto por dos capas:

1. **Capa automática (hooks):** se ejecuta sin intervención del usuario en cada sesión
2. **Capa manual (MCP + skills):** disponible cuando Claude o el usuario necesitan búsqueda explícita

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Code                            │
│                                                             │
│  ┌───────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │ SessionStart  │  │ UserPrompt     │  │     Stop      │  │
│  │ Hook (command)│  │ Submit (cmd)   │  │ Hook (command)│  │
│  └──────┬────────┘  └──────┬─────────┘  └──────┬────────┘  │
│         │                  │                    │            │
│         │           ┌──────▼─────────┐          │            │
│         │           │ PostToolUse    │          │            │
│         │           │ Hook (prompt)  │          │            │
│         │           │ Haiku analiza  │          │            │
│         │           └──────┬─────────┘          │            │
│         │                  │                    │            │
│  ┌──────▼──────────────────▼────────────────────▼────────┐  │
│  │              Core Python Modules                       │  │
│  │  ┌─────────┐ ┌──────────┐ ┌───────────────────┐       │  │
│  │  │store.py │ │ingester  │ │  embeddings.py    │       │  │
│  │  │ChromaDB │ │chunking  │ │  fastembed/ollama │       │  │
│  │  └────┬────┘ └──────────┘ └───────────────────┘       │  │
│  │       │                                                │  │
│  │  ┌────▼─────────────────┐                              │  │
│  │  │  .claude-vestige/db/    │                              │  │
│  │  │  (por proyecto)      │                              │  │
│  │  └──────────────────────┘                              │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────┐  ┌──────────────────────────────────┐  │
│  │  MCP Server     │  │  Skills                          │  │
│  │  (manual)       │  │  /claude_vestige:bootstrap          │  │
│  │  retrieve_ctx   │  │  /claude_vestige:search             │  │
│  │  get_chunks     │  │                                  │  │
│  │  save_memory    │  │                                  │  │
│  └─────────────────┘  └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Estructura de archivos

```
claude-vestige/
├── claude_vestige/                     # Paquete Python (pip install -e .)
│   ├── __init__.py
│   ├── store.py                     # ChromaDB: upsert, search, delete
│   ├── ingester.py                  # Chunking markdown por ## headers
│   ├── embeddings.py                # Providers: fastembed (default), ollama
│   ├── config.py                    # Carga config.toml, gitignore, excludes
│   ├── memory.py                    # save_memory con validación de tipos
│   ├── bootstrap.py                 # Detección de stack, generación de config
│   ├── server.py                    # MCP server (solo tools manuales)
│   └── api.py                       # Dashboard FastAPI (python -m claude_vestige.api)
│
├── claude-vestige-plugin/              # Plugin de Claude Code
│   ├── .claude-plugin/
│   │   └── plugin.json              # Manifiesto del plugin
│   ├── .mcp.json                    # MCP server para tools manuales
│   ├── hooks/
│   │   ├── hooks.json               # Registro de hooks
│   │   ├── session_start.py         # Inyecta contexto (command)
│   │   ├── user_prompt.py           # Captura prompt del usuario (command)
│   │   ├── post_tool_use.py         # Guarda observación en ChromaDB (command)
│   │   └── stop.py                  # Resumen de sesión (command)
│   ├── skills/
│   │   ├── bootstrap/SKILL.md       # Inicializar proyecto
│   │   └── search/SKILL.md          # Búsqueda manual guiada
│   └── CLAUDE.md                    # Instrucciones del plugin
│
├── pyproject.toml                   # Definición del paquete + dependencias
├── tests/                           # Tests de integración
└── CLAUDE.md                        # Contexto del proyecto (excluido de git)
```

**Por proyecto indexado (no va en este repo):**
```
{proyecto}/
└── .claude-vestige/
    ├── config.toml                  # Qué archivos indexar
    └── db/                          # ChromaDB persistido (en .gitignore)
```

## Hooks — diseño detallado

### Tipos de hook usados

Los hooks de Claude Code soportan distintos tipos. Claude Vestige usa dos:

- **`command`** — ejecuta un script Python. Recibe JSON por stdin, retorna texto/JSON por stdout.
  Usado en: SessionStart, UserPromptSubmit, Stop (y el command de PostToolUse que guarda en ChromaDB)
- **`prompt`** — hace una llamada LLM interna (Haiku por defecto) dentro de Claude Code.
  No requiere API key ni procesos externos. Retorna `{"ok": true/false, "reason": "..."}`.
  Usado en: PostToolUse para analizar qué hizo Claude y por qué.

### Pipeline de captura de observaciones

El mecanismo central para capturar contexto valioso combina 3 hooks:

```
1. UserPromptSubmit (command)
   → Captura lo que el usuario pidió
   → Guarda en archivo temporal: ~/.claude-vestige/current_prompt.txt

2. PostToolUse (prompt) — Haiku
   → Recibe: tool_name, tool_input, tool_response
   → El prompt incluye el contenido de current_prompt.txt
   → Haiku analiza: qué se hizo + por qué (infiere del prompt del usuario)
   → Retorna {"ok": true, "reason": "observación estructurada"}

3. PostToolUse (command) — Python
   → Recibe la observación del prompt hook
   → Guarda en ChromaDB (colección sessions)
   → Deduplicación: no guardar si mismo archivo hace menos de 60s
   → Si archivo editado está en include → re-indexar

4. Stop (command)
   → Limpia current_prompt.txt
   → Guarda resumen de sesión
```

Este diseño permite que Haiku tenga **ambos contextos**: lo que el usuario pidió (el "por qué")
y lo que Claude ejecutó (el "qué"). Así las observaciones son útiles como contexto futuro.

### SessionStart → `session_start.py` (command)
- **Trigger:** cada vez que se inicia/resume/compacta una sesión
- **Input:** JSON con `cwd`, `session_id`, `source` (startup|resume|compact)
- **Lógica:**
  1. Buscar `.claude-vestige/config.toml` subiendo en el árbol de directorios
  3. **Si existe config + índice:** buscar top 5 chunks con query genérica, imprimir contenido
  4. **Si NO existe config (primera vez):** buscar README.md y CLAUDE.md en el proyecto.
     Si existen → auto-bootstrap (generar config.toml, indexar, inyectar contexto).
     Si no existen → escaneo básico del proyecto
     (detect_stack + conteo de archivos por extensión), inyectar resumen mínimo.
     Informa sobre `/claude_vestige:bootstrap` opcionalmente.
- **Output:** texto impreso a stdout → inyectado directamente en el contexto de Claude

### UserPromptSubmit → `user_prompt.py` (command)
- **Trigger:** cada vez que el usuario envía un mensaje
- **Input:** JSON con `prompt` (el mensaje del usuario)
- **Lógica:** guardar el prompt en `~/.claude-vestige/current_prompt.txt`
- **Output:** vacío (no inyecta nada en la conversación)

### PostToolUse — pipeline de 2 pasos
**Paso 1: prompt hook (Haiku)**
- **Trigger:** después de Write, Edit, MultiEdit, Bash
- **Matcher:** `Write|Edit|MultiEdit|Bash`
- **Tipo:** `prompt` (LLM interno, Haiku por defecto)
- **Prompt:** incluye el tool use + el prompt del usuario (de current_prompt.txt)
- **Retorna:** `{"ok": true, "reason": "observación: qué se hizo y por qué"}`

**Paso 2: command hook (Python)**
- **Trigger:** después del prompt hook
- **Tipo:** `command`
- **Lógica:**
  - Lee la observación generada por Haiku
  - Guarda en ChromaDB (colección `sessions`) con embeddings
  - Deduplicación por archivo (ventana de 60s)
  - Si archivo editado está en `include` del config.toml → re-indexar

### Stop → `stop.py` (command)
- **Trigger:** cuando Claude termina de responder
- **Input:** JSON con `session_id`, `stop_reason`
- **Lógica:** limpia `current_prompt.txt`, guarda resumen de sesión
- **Output:** vacío

## MCP Server (manual)

Tools disponibles para búsqueda explícita:

| Tool | Propósito |
|---|---|
| `retrieve_context(query, n)` | Índice liviano (~50 tokens/resultado) |
| `get_chunks(ids[])` | Contenido completo de chunks seleccionados |
| `save_memory(content, type, tags[])` | Guardar memoria explícita |
| `bootstrap_project(project_path, include_files)` | Inicializar proyecto |
| `get_status()` | Estado del índice |

## Skills (slash commands)

| Skill | Cuándo se usa |
|---|---|
| `/claude_vestige:bootstrap` | Inicializar un proyecto nuevo |
| `/claude_vestige:search` | Búsqueda profunda guiada |

## Módulos core Python

| Módulo | Responsabilidad | Dependencias |
|---|---|---|
| `store.py` | CRUD ChromaDB, búsqueda híbrida BM25+vectorial, RRF | chromadb, rank_bm25 |
| `ingester.py` | Chunking markdown (## headers, párrafos), batch embedding | embeddings.py |
| `embeddings.py` | Abstracción providers (fastembed default, ollama opcional) | fastembed |
| `config.py` | Cargar config.toml, build exclude spec, resolver includes | tomllib, pathspec |
| `memory.py` | Validar y guardar memorias en sessions collection | store.py, embeddings.py |
| `bootstrap.py` | Detectar stack, generar config.toml, indexar | config.py, ingester.py, store.py |

## Flujo de datos

### Primera vez en un proyecto
```
SessionStart hook (command)
  → No hay .claude-vestige/config.toml
  → Busca README.md, CLAUDE.md
  → Si existen: auto-bootstrap
    → config.py genera config.toml con esos archivos
    → ingester.py chunking + embeddings
    → store.py upsert en colección docs
    → stdout: contexto inyectado
  → Si no existen: escaneo básico del proyecto
    → detect_stack() + conteo de archivos por extensión
    → stdout: resumen mínimo del proyecto como contexto
    → Informa sobre /claude_vestige:bootstrap (opcional)
```

### Sesión típica (proyecto ya indexado)
```
1. SessionStart hook (command)
   → store.py.search() con query genérica
   → stdout: chunks relevantes inyectados en contexto

2. Usuario escribe un mensaje
   → UserPromptSubmit hook (command)
   → Guarda prompt en ~/.claude-vestige/current_prompt.txt

3. Claude trabaja, usa Write/Edit/Bash
   → PostToolUse hook (prompt): Haiku analiza tool use + prompt del usuario
   → PostToolUse hook (command): guarda observación en ChromaDB
   → Si archivo en include: re-indexa automáticamente

4. Claude termina de responder
   → Stop hook (command)
   → Guarda resumen de sesión, limpia prompt temporal
```

## ChromaDB

- Cada proyecto tiene su propia DB aislada en `{proyecto}/.claude-vestige/db/`
- Dos colecciones simples: `docs` (documentación indexada) y `sessions` (observaciones capturadas)
- Sin prefijos por project_id — el aislamiento es por directorio
- No existe DB centralizada

## Stack técnico

| Componente | Librería | Notas |
|---|---|---|
| Vector DB | `chromadb` | Local, sin servidor, persiste en disco |
| Embeddings | `fastembed` (default) | ONNX en-proceso, sin servidor externo |
| Embeddings alt | `ollama` (opcional) | Para quien prefiera modelo propio |
| Chunking | `python-frontmatter` + lógica propia | Split por `##` headers |
| Búsqueda híbrida | `rank_bm25` | BM25 sobre chunks, fusión con RRF |
| Config | `tomllib` (stdlib) | Sin dependencia externa |
| Gitignore | `pathspec` | Respetar .gitignore del proyecto |
| Dashboard | `fastapi` + `uvicorn` | Opcional, standalone |
| Plugin hooks | `command` (Python) + `prompt` (Haiku) | Sin procesos externos |
| MCP protocol | `mcp` (Anthropic SDK) | Solo para tools manuales opcionales |

## Decisiones de diseño

| Decisión | Razón |
|---|---|
| Plugin con hooks, no MCP puro | Los hooks se ejecutan automáticamente; los MCP tools dependen de que Claude decida llamarlos |
| Hook `prompt` (Haiku) para observaciones | Genera contexto con el "qué" y el "por qué" sin requerir API key externa ni procesos background. Corre dentro de Claude Code |
| UserPromptSubmit captura el prompt | PostToolUse no recibe la conversación. Capturando el prompt del usuario por separado, Haiku puede inferir la intención detrás de cada cambio |
| fastembed como default | Cero setup externo, ONNX en-proceso. Ollama como opción para quien lo prefiera |
| ChromaDB local por proyecto | Sin servidor, persistencia en archivo, aislamiento total por directorio |
| DB por proyecto (no centralizada) | Cada carpeta donde se use Claude Code tiene su propia base de datos |
| PostToolUse re-indexa archivos del include | Reemplaza al file watcher — no necesita proceso largo corriendo |
| Retrieval 2 capas (retrieve_context + get_chunks) | Ahorra ~70% tokens vs retornar chunks completos |
| config.toml explícito | El usuario controla qué se indexa. Auto-bootstrap solo con README.md y CLAUDE.md |
| Escaneo básico como fallback | Si no hay docs, al menos inyectar stack + estructura como contexto mínimo |
| Paquete pip (`claude_vestige/`) | Los hooks importan `from claude_vestige.store import ...` sin hacks de sys.path. Instalación estándar con `pip install -e .` |
| Instalación: pip + /plugin install | pip instala dependencias Python; /plugin install registra hooks y skills en Claude Code |
