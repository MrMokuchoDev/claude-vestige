# ContextFlow — Requerimientos

## Problema

Claude Code pierde todo el contexto entre sesiones. Cada conversación nueva empieza de cero:
no sabe qué se decidió antes, qué bugs se arreglaron, qué arquitectura tiene el proyecto,
ni qué errores no repetir. El usuario tiene que re-explicar todo cada vez.

Los mecanismos existentes (CLAUDE.md, auto-memory) son manuales y limitados:
- CLAUDE.md es estático y el usuario debe mantenerlo actualizado
- La auto-memory de Claude Code es superficial y no indexa documentación del proyecto
- No hay búsqueda semántica sobre el conocimiento acumulado

## Solución

ContextFlow es un **Plugin de Claude Code** que provee memoria semántica persistente.
Indexa documentación y captura decisiones automáticamente usando embeddings locales
y ChromaDB, recuperándolos como contexto relevante en futuras sesiones.

## Requisitos Funcionales

### RF1: Inyección automática de contexto (SessionStart)
- Al iniciar una sesión, el plugin verifica si el proyecto tiene `.contextflow/db/`
- **Primera vez (no indexado):** busca README.md y CLAUDE.md en el proyecto.
  Si existen, los indexa automáticamente (genera config.toml + ChromaDB) e inyecta su contexto.
  Si no existen, hace un escaneo básico del proyecto (stack, conteo de archivos por extensión)
  e inyecta ese resumen como contexto mínimo. Informa que puede usar `/contextflow:bootstrap` opcionalmente
- **Sesiones posteriores:** busca en ChromaDB los chunks más relevantes y los inyecta directamente
- Claude recibe el contexto sin necesidad de llamar ningún tool
- Debe funcionar también después de un compact (re-inyectar contexto perdido)

### RF2: Captura del prompt del usuario (UserPromptSubmit)
- Cada vez que el usuario envía un mensaje, el hook guarda el prompt en un archivo temporal
- Este prompt se usa en RF3 para que Haiku pueda inferir la intención detrás de cada cambio

### RF3: Captura automática de observaciones (PostToolUse)
- Cada vez que Claude usa Write, Edit, MultiEdit o Bash, se ejecuta un pipeline de 2 pasos:
  1. **Hook prompt (Haiku):** recibe el tool use + el prompt del usuario (de RF2).
     Haiku analiza qué se hizo y por qué, generando una observación estructurada.
     Corre dentro de Claude Code, sin API key externa ni procesos background.
  2. **Hook command (Python):** recibe la observación de Haiku y la guarda en ChromaDB
     (colección `sessions`) con embeddings para búsqueda semántica futura.
- Deduplicación: no guardar si el mismo archivo se guardó hace menos de 60 segundos
- Si el archivo editado está en `include` del config.toml → re-indexar automáticamente

### RF4: Resumen de sesión (Stop)
- Al terminar una respuesta, el plugin genera un resumen ligero de la sesión
- Guarda qué archivos se modificaron y cuántas herramientas se usaron
- Limpia el archivo temporal del prompt

### RF5: Inicialización de proyecto (Skill: /contextflow:bootstrap)
- Skill guiado que detecta el stack del proyecto y presenta archivos candidatos
- El usuario elige qué archivos indexar
- Genera `.contextflow/config.toml` e indexa los archivos seleccionados

### RF6: Búsqueda manual profunda (Skill: /contextflow:search + MCP tools)
- Retrieval en 2 capas: `retrieve_context` (índice liviano) → `get_chunks` (contenido completo)
- Disponible como MCP tools para cuando Claude necesite búsqueda explícita
- Skill `/contextflow:search` guía el flujo de búsqueda

### RF7: Guardado manual de memorias (MCP tool: save_memory)
- Tool MCP para guardar memorias específicas que la captura automática no cubriría
- Tipos: decision, bug_fix, change, note

## Requisitos No Funcionales

### RNF1: Cero intervención del usuario
- El plugin debe funcionar automáticamente después de la instalación
- No debe depender de que el usuario escriba instrucciones en CLAUDE.md
- No debe depender de que Claude decida llamar tools para la funcionalidad core

### RNF2: Instalación simple
- Dos pasos: `pip install contextflow` (dependencias) + `/plugin install contextflow` (hooks/skills)
- En desarrollo: `pip install -e .` + `claude --plugin-dir ./contextflow-plugin`
- Después de instalar, funciona en todos los proyectos sin configuración adicional

### RNF3: Sin dependencias externas pesadas
- fastembed como provider de embeddings por defecto (ONNX, en-proceso)
- ChromaDB local, sin servidor externo
- Hooks `prompt` corren dentro de Claude Code (sin API key, sin procesos externos)
- No requiere Ollama, Docker, ni servicios corriendo

### RNF4: Performance
- SessionStart hook debe completar en menos de 5s (con modelo de embeddings en caché)
- PostToolUse prompt hook: depende de Haiku (típicamente 1-2s)
- PostToolUse command hook: debe completar en menos de 5s
- Primera ejecución puede tomar hasta 30s (descarga del modelo fastembed)

### RNF5: Seguridad
- Nunca indexar: `.env*`, `*.pem`, `*.key`, `*.p12`, `node_modules/`, `.git/`
- Respetar `.gitignore` del proyecto
- El usuario controla qué se indexa via `config.toml`

### RNF6: Aislamiento entre proyectos
- Cada proyecto tiene su propia base de datos ChromaDB en `.contextflow/db/`
- Colecciones simples: `docs` y `sessions` (aislamiento por directorio, sin prefijos)
- Nunca mezclar datos entre proyectos

## Restricciones Técnicas

- Python 3.11+ (por tomllib en stdlib)
- Claude Code 1.0.33+ (soporte de plugins)
- Plugin format: directorio con `.claude-plugin/plugin.json`
- Hooks: `command` (scripts Python, JSON stdin/stdout) + `prompt` (LLM interno, Haiku)
- MCP: servidor stdio para tools manuales opcionales
