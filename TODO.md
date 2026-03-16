# Claude Vestige — Plan de Desarrollo

## Fases

### Fase 1: Plugin skeleton + SessionStart hook ✅
**Objetivo:** Al abrir una conversación, Claude recibe contexto relevante automáticamente.

- [x] Crear `pyproject.toml` y estructura de paquete `claude_vestige/`
- [x] Crear módulos core: `store.py`, `ingester.py`, `embeddings.py`, `config.py`, `memory.py`, `bootstrap.py`
- [x] Crear estructura plugin: `.claude-plugin/plugin.json`, `hooks/hooks.json`
- [x] Implementar `hooks/session_start.py` — inyecta contexto de ChromaDB
- [x] Tests: 37 tests (core + session_start hook)

### Fase 2: Captura automática de observaciones ✅
**Objetivo:** Capturar qué hizo Claude y por qué, automáticamente.

- [x] Implementar `hooks/user_prompt.py` — guarda prompt del usuario en archivo temporal
- [x] Configurar PostToolUse con hook `agent` — analiza tool use + prompt del usuario con LLM
- [x] Implementar `hooks/save_observation.py` — guarda observación en ChromaDB
- [x] Actualizar `hooks/hooks.json` con UserPromptSubmit y PostToolUse
- [x] Tests: 11 tests (user_prompt, save_observation, hooks.json validation)

### Fase 3: Skills + MCP + Dashboard ✅
**Objetivo:** Búsqueda manual, inicialización guiada, y dashboard web.

- [x] Crear `skills/bootstrap/SKILL.md` — workflow guiado para inicializar proyecto
- [x] Crear `skills/search/SKILL.md` — búsqueda semántica 2 capas guiada
- [x] Crear `.mcp.json` apuntando al MCP server
- [x] Implementar `server.py` — 5 tools MCP (retrieve_context, get_chunks, save_memory, bootstrap_project, get_status)
- [x] Implementar `api.py` — 6 endpoints REST (health, projects, search, sessions, stats, dashboard)
- [x] Implementar `dashboard.html` — UI dark theme full-width con sidebar, búsqueda, docs y observaciones
- [x] Crear `CLAUDE.md` del plugin — instrucciones de uso para Claude
- [x] Agregar registro de proyectos en `~/.claude-vestige/projects.json` al hacer bootstrap
- [x] Tests: 22 tests (skills frontmatter, MCP config, plugin.json, API endpoints, dashboard)

### Fase 4: Stop hook + polish ✅
**Objetivo:** Resumen de sesión y limpieza.

- [x] Implementar `hooks/stop.py` — resumen de sesión, limpieza de archivos temporales
- [x] Implementar `hooks/post_tool_use.py` — análisis con Haiku via `claude --print --model haiku`
- [x] Wrapper `hooks/run.sh` para resolver venv dinámicamente
- [x] Actualizar `hooks/hooks.json` con Stop hook y PostToolUse como command
- [x] Tests: 14 tests (stop hook, session log, pipeline end-to-end)
- [x] Probado en real: SessionStart → UserPrompt → PostToolUse (Haiku) → Stop → observaciones en dashboard

---

## Decisiones tomadas

| Fecha | Decisión | Razón |
|---|---|---|
| 2026-03-14 | Plugin con hooks (no MCP puro) | Los hooks se ejecutan automáticamente; los MCP tools dependen de que Claude decida llamarlos |
| 2026-03-14 | Hook `agent` para observaciones en PostToolUse | El agent puede analizar el tool use con LLM Y ejecutar Bash para guardar en ChromaDB. Todo en un solo hook, sin API key externa |
| 2026-03-14 | UserPromptSubmit captura el prompt | PostToolUse no recibe la conversación. Capturando el prompt por separado, el agent puede inferir la intención |
| 2026-03-14 | fastembed como default | Cero setup externo, ONNX en-proceso. Ollama como opción |
| 2026-03-14 | DB por proyecto (no centralizada) | Cada proyecto tiene su ChromaDB en `.claude-vestige/db/`. Aislamiento total por directorio |
| 2026-03-14 | PostToolUse re-indexa archivos del include | Reemplaza al file watcher — no necesita proceso largo corriendo |
| 2026-03-14 | Retrieval 2 capas | retrieve_context (índice liviano) + get_chunks (contenido). Ahorra ~70% tokens |
| 2026-03-14 | Auto-bootstrap con README.md y CLAUDE.md | Primera vez: indexa solo estos archivos si existen. Escaneo básico como fallback |
| 2026-03-14 | Escaneo básico como fallback | Si no hay docs, inyectar stack + estructura como contexto mínimo |
| 2026-03-15 | Paquete pip (`claude_vestige/`) | Instalación estándar, sin hacks de sys.path. hooks importan `from claude_vestige import ...` |
| 2026-03-15 | Instalación: pip + /plugin install | pip para dependencias, /plugin para hooks. Claro y sin magia |
| 2026-03-15 | Dashboard con layout full-width | Sidebar de proyectos + área principal con tabs. Estilo IBM Plex Mono, dark theme profesional |
| 2026-03-15 | Registro global de proyectos | `~/.claude-vestige/projects.json` se actualiza automáticamente al hacer bootstrap. El dashboard lo lee para listar proyectos |
