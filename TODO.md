# ContextFlow — Plan de Desarrollo

## Fases

### Fase 1: Plugin skeleton + SessionStart hook
**Objetivo:** Al abrir una conversación, Claude recibe contexto relevante automáticamente.

- [ ] Crear `pyproject.toml` y estructura de paquete `contextflow/`
- [ ] Crear módulos core: `store.py`, `ingester.py`, `embeddings.py`, `config.py`, `memory.py`, `bootstrap.py`
- [ ] Crear estructura plugin: `.claude-plugin/plugin.json`, `hooks/hooks.json`
- [ ] Implementar `hooks/session_start.py` — inyecta contexto de ChromaDB
- [ ] Tests: session_start con proyecto configurado, sin configurar, índice vacío
- [ ] Verificación: `claude --plugin-dir ./contextflow-plugin` → recibe contexto

### Fase 2: Captura automática de observaciones (UserPromptSubmit + PostToolUse)
**Objetivo:** Capturar qué hizo Claude y por qué, automáticamente.

- [ ] Implementar `hooks/user_prompt.py` — guarda prompt del usuario en archivo temporal
- [ ] Configurar PostToolUse con hook `prompt` (Haiku) — analiza tool use + prompt del usuario
- [ ] Implementar `hooks/post_tool_use.py` (command) — guarda observación de Haiku en ChromaDB
- [ ] Implementar deduplicación (ventana 60s por archivo)
- [ ] Implementar re-indexación incremental de archivos en `include`
- [ ] Actualizar `hooks/hooks.json` con UserPromptSubmit y PostToolUse
- [ ] Tests: captura de observaciones, deduplicación, re-indexación

### Fase 3: Skills + MCP + Dashboard
**Objetivo:** Búsqueda manual, inicialización guiada, y dashboard web.

- [ ] Crear `skills/bootstrap/SKILL.md`
- [ ] Crear `skills/search/SKILL.md`
- [ ] Crear `.mcp.json` apuntando al MCP server
- [ ] Implementar `server.py` (solo tools MCP: retrieve_context, get_chunks, save_memory)
- [ ] Implementar `api.py` + `dashboard.html` — UI web para ver proyectos, buscar, ver observaciones
- [ ] Crear `CLAUDE.md` del plugin
- [ ] Tests: validar frontmatter de skills, MCP config, endpoints API

### Fase 4: Stop hook + polish
**Objetivo:** Resumen de sesión y limpieza.

- [ ] Implementar `hooks/stop.py` — resumen de sesión, limpieza de archivo temporal
- [ ] Actualizar `hooks/hooks.json` con Stop hook
- [ ] Tests: resumen guardado, limpieza
- [ ] Test end-to-end: SessionStart → UserPrompt → PostToolUse x3 → Stop → verificar ChromaDB

---

## Decisiones tomadas

| Fecha | Decisión | Razón |
|---|---|---|
| 2026-03-14 | Plugin con hooks (no MCP puro) | Los hooks se ejecutan automáticamente; los MCP tools dependen de que Claude decida llamarlos |
| 2026-03-14 | Hook `prompt` (Haiku) para observaciones | Genera contexto con el "qué" y el "por qué" sin API key externa. Corre dentro de Claude Code |
| 2026-03-14 | UserPromptSubmit captura el prompt | PostToolUse no recibe la conversación. Capturando el prompt por separado, Haiku puede inferir la intención |
| 2026-03-14 | fastembed como default | Cero setup externo, ONNX en-proceso. Ollama como opción |
| 2026-03-14 | DB por proyecto (no centralizada) | Cada proyecto tiene su ChromaDB en `.contextflow/db/`. Aislamiento total por directorio |
| 2026-03-14 | PostToolUse re-indexa archivos del include | Reemplaza al file watcher — no necesita proceso largo corriendo |
| 2026-03-14 | Retrieval 2 capas | retrieve_context (índice liviano) + get_chunks (contenido). Ahorra ~70% tokens |
| 2026-03-14 | Auto-bootstrap con README.md y CLAUDE.md | Primera vez: indexa solo estos archivos si existen. Escaneo básico como fallback |
| 2026-03-14 | Escaneo básico como fallback | Si no hay docs, inyectar stack + estructura como contexto mínimo |
| 2026-03-15 | Paquete pip (`contextflow/`) | Instalación estándar, sin hacks de sys.path. hooks importan `from contextflow import ...` |
| 2026-03-15 | Instalación: pip + /plugin install | pip para dependencias, /plugin para hooks. Claro y sin magia |
