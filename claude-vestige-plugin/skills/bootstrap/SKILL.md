---
name: bootstrap
description: Index files into project memory. Use when the user asks to "index files", "add to memory", "bootstrap", or wants to configure which files Claude Vestige tracks.
user-invocable: true
---

# Claude Vestige Bootstrap

Index files into the project's semantic memory.

## Steps

1. Check current status to see what's already indexed:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/hooks/run.sh -m claude_vestige.cli status --cwd "$PWD"
   ```
   This returns `config_include` (what's in config.toml) AND `indexed_files` (what's actually in the database).
   Files in `indexed_files` are ALREADY indexed — do NOT suggest re-indexing them.

2. If the project is not indexed yet, run bootstrap to auto-index README.md/CLAUDE.md:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/hooks/run.sh -m claude_vestige.cli bootstrap --cwd "$PWD"
   ```

3. Show the user which .md files exist that are NOT in `indexed_files`.
   Only suggest files that are genuinely new and not yet indexed.

4. If the user wants to add files, run bootstrap with --include:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/hooks/run.sh -m claude_vestige.cli bootstrap --cwd "$PWD" --include ENDPOINTS.md docs/architecture.md
   ```

5. Confirm the result: how many files indexed, how many chunks created.

## Important

- **Check `indexed_files` from status** before suggesting files to index. Files already in the database should NOT be suggested again.
- The user can also edit `.claude-vestige/config.toml` manually
- Never index `.env`, `*.pem`, `*.key`, or `node_modules/` — always excluded
