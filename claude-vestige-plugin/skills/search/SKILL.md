---
name: search
description: Deep semantic search in project memory. Use when the user asks to "search project memory", "find context about", "what do we know about", "recall decisions", or needs to find specific information in the project index.
user-invocable: true
---

# Claude Vestige Search

Search project documentation and session memory using semantic similarity.

## Steps

1. Call `retrieve_context` with the user's query and `n=10`:
   - Returns a lightweight index (~50 tokens per result)
   - Each result has: id, file, section, type (doc/memory), snippet

2. Evaluate the results — read the snippets to determine which are relevant.
   - Filter by type if the user is looking for decisions (memory) vs documentation (doc)

3. Call `get_chunks` with ONLY the relevant IDs (usually 2-4, not all 10):
   - Returns full content (~500 tokens per chunk)
   - This is the token optimization: only fetch what you need

4. Present the findings to the user in a clear format.

## Token Optimization

This 2-layer pattern saves ~70% tokens vs fetching all chunks:
- Layer 1: `retrieve_context` → lightweight index (~700 tokens total)
- Layer 2: `get_chunks` → full content only for selected IDs (~1500 tokens for 3 chunks)
- Naive approach would use ~2500 tokens for the same 10 results

**Never call `get_chunks` with all IDs from the index — that defeats the purpose.**
