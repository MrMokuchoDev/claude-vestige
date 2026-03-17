---
name: search
description: Deep semantic search in project memory. Use when the user asks to "search memory", "find context about", "what do we know about", "recall decisions about", or needs to find specific information in the project index.
user-invocable: true
---

# Claude Vestige Search

Search project documentation and session memory using semantic similarity.

## Steps

1. Run a search with the user's query:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/hooks/run.sh -m claude_vestige.cli search --query "the user query here" --cwd "$PWD" --n 10
   ```
   This returns a JSON index with: id, file, section, type (doc/memory), snippet.

2. Evaluate the results — read the snippets to determine which are relevant.

3. For relevant results, get full content:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/hooks/run.sh -m claude_vestige.cli chunks --ids "id1" "id2" --cwd "$PWD"
   ```
   Only fetch 2-4 chunks, not all 10.

4. Present the findings to the user clearly.

## Token Optimization

This 2-layer pattern saves ~70% tokens:
- Layer 1: search → lightweight index (~700 tokens)
- Layer 2: chunks → full content only for relevant IDs (~1500 tokens for 3 chunks)
