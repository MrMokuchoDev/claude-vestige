# Why Claude Vestige?

## The problem

Every time you open Claude Code in a project, it starts from zero. It doesn't know what you did yesterday, what decisions were made, or where things are. You end up repeating context, approving file explorations, and waiting while Claude rediscovers your codebase — again.

## How Claude Vestige helps

### Faster sessions, fewer interruptions

Without Claude Vestige, a typical interaction looks like this:

```
You: "Fix the payment endpoint"
Claude: Glob("**/*.py")              → You: Allow? [Y]  (wait...)
Claude: Read(src/api/payments.py)    → You: Allow? [Y]  (wait...)
Claude: Read(src/api/auth.py)        → You: Allow? [Y]  (wait...)
Claude: Grep("payment", src/)        → You: Allow? [Y]  (wait...)
Claude: Read(src/models/payment.py)  → You: Allow? [Y]  (wait...)
Claude: "Ok, I see. Let me fix it."
```

**5+ tool calls, 2-5 minutes just exploring**, before any real work starts.

With Claude Vestige:

```
You: "Fix the payment endpoint"
Claude: (already knows the project structure, endpoints, and past decisions)
Claude: Read(src/api/payments.py)    → You: Allow? [Y]
Claude: "Here's the fix."
```

**1-2 tool calls, 30 seconds.** Claude goes straight to the right file because it already has the context.

### Time saved per day

| Scenario | Without | With | Saved |
|---|---|---|---|
| First interaction of the session | 2-5 min exploring | 30 sec (context injected) | **~3 min** |
| "What did we do yesterday?" | You explain manually | Auto-injected observations | **~2 min** |
| "Where are the endpoints?" | Grep + Read multiple files | `/search` or already in context | **~3 min** |
| Repeated across 5-10 sessions/day | — | — | **~30-60 min/day** |

### Smarter token usage

Claude Vestige reduces redundant exploration:

- **SessionStart** injects only relevant chunks (~500-700 tokens) instead of Claude reading entire files (~5,000-10,000 tokens)
- **Semantic search** finds answers in one call instead of multiple Glob + Grep + Read cycles
- **Observations** carry forward decisions and context that would otherwise require user re-explanation

Estimated **3,000-10,000 tokens saved per session** from avoided exploration. Over a full workday, that adds up.

### Context that doesn't exist otherwise

The biggest value isn't token savings — it's knowledge Claude simply wouldn't have:

- **Why** a decision was made (not just what code exists)
- **What changed** in previous sessions and the reasoning behind it
- **Project patterns** and conventions discovered over time

Without persistent memory, every session is amnesia. With Claude Vestige, Claude builds understanding over time — like working with a teammate who actually remembers.
