---
name: bootstrap
description: Initialize Claude Vestige for a project. Use when the user asks to "set up project memory", "configure context indexing", "bootstrap claude_vestige", or when SessionStart indicates the project is not indexed.
user-invocable: true
---

# Claude Vestige Bootstrap

Initialize semantic memory for the current project.

## Steps

1. First, call the `bootstrap_project` MCP tool with NO arguments to discover the project:
   - It will detect the stack (Python, Node.js, etc.)
   - It will list candidate files for indexing (README.md, docs/, etc.)

2. Present the candidates to the user and ask which files they want to index.
   - Suggest README.md and CLAUDE.md as defaults if they exist
   - The user can add globs like `docs/**/*.md`

3. Call `bootstrap_project` again with `include_files` set to the user's selection.
   - This generates `.claude-vestige/config.toml` and indexes the files

4. Confirm the result: how many files indexed, how many chunks created.

## Notes

- If the project is already indexed, `bootstrap_project` will re-index using the existing config
- The user can edit `.claude-vestige/config.toml` manually to add/remove files later
- Never index `.env`, `*.pem`, `*.key`, or `node_modules/` — these are always excluded
