# Claude Vestige

Persistent semantic memory plugin for Claude Code. Automatically captures context from your coding sessions and injects relevant knowledge into future conversations.

## What it does

- **SessionStart**: Auto-indexes `README.md` and `CLAUDE.md`, injects relevant context from ChromaDB
- **PostToolUse**: Haiku analyzes file changes and generates observations (what was done and why)
- **Auto-index**: New `.md` files created by Claude are automatically indexed
- **Stop**: Saves a session summary for future reference

Works with Claude Code CLI, VS Code extension, and Windsurf. Compatible with Linux and macOS.

## Dashboard

Explore indexed documents, observations, and semantic search across all your projects.

### Search
![Search](docs/images/search.png)

### Documents
![Documents](docs/images/documents.png)

### Observations
![Observations](docs/images/observations.png)

## Installation

### Quick install (recommended)

```bash
curl -sSL https://raw.githubusercontent.com/MrMokuchoDev/claude-vestige/main/install.sh | bash
```

### Clone and install

```bash
git clone https://github.com/MrMokuchoDev/claude-vestige.git
cd claude-vestige
./install.sh
```

After installing, **restart Claude Code** completely (close and reopen terminal/IDE).

### Prerequisites

- Python 3.11+
- `python3-venv` (`sudo apt install python3-venv` on Debian/Ubuntu)
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)

## Usage

Open Claude Code in any project:

```bash
cd /path/to/your/project
claude
```

Claude Vestige works automatically — no `--plugin-dir` or extra configuration needed.

### First session in a project

1. The plugin creates `.claude-vestige/` in the project root
2. Indexes `README.md` and `CLAUDE.md` if they exist
3. Injects the indexed content as context for Claude

### Subsequent sessions

1. Previous observations and indexed docs are injected at session start
2. Claude already knows what happened in prior sessions
3. New file changes continue to be captured

### Dashboard

```bash
~/.claude-vestige/.venv/bin/python -m claude_vestige.api --port 7843
```

Open `http://localhost:7843` in your browser.

## For developers

### Local development

```bash
git clone https://github.com/MrMokuchoDev/claude-vestige.git
cd claude-vestige
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,dashboard]"
```

Run with `--plugin-dir` for testing:

```bash
cd /path/to/any/project
claude --plugin-dir /path/to/claude-vestige/claude-vestige-plugin
```

### Running tests

```bash
.venv/bin/python -m pytest tests/ -q
```

### Project structure

```
claude-vestige/
├── claude_vestige/              # Python package (pip install)
│   ├── store.py                 # ChromaDB interface
│   ├── ingester.py              # Markdown chunking
│   ├── embeddings.py            # fastembed provider
│   ├── config.py                # Config loader + gitignore
│   ├── memory.py                # save_memory
│   ├── bootstrap.py             # Stack detection + indexing
│   ├── server.py                # MCP server (optional tools)
│   └── api.py                   # Dashboard FastAPI
│
├── claude-vestige-plugin/       # Claude Code plugin
│   ├── .claude-plugin/plugin.json
│   ├── hooks/
│   │   ├── hooks.json
│   │   ├── session_start.py     # Injects context
│   │   ├── user_prompt.py       # Captures user prompt
│   │   ├── post_tool_use.py     # Haiku analyzes + saves observations
│   │   └── stop.py              # Session summary
│   └── skills/
│       ├── bootstrap/SKILL.md
│       └── search/SKILL.md
│
├── install.sh                   # One-step installer
├── pyproject.toml
└── tests/
```

## Stack

| Component | Library |
|---|---|
| Vector DB | ChromaDB (embedded, per-project) |
| Embeddings | fastembed (ONNX, in-process) |
| Hybrid search | rank_bm25 |
| Observations | Haiku via Claude Code hooks |
| Dashboard | FastAPI + vanilla HTML/JS |

## Uninstall

```bash
claude plugin uninstall claude-vestige
claude plugin marketplace remove claude-vestige-tools
rm -rf ~/.claude-vestige
```

To remove project data, delete `.claude-vestige/` from each project directory.

## License

[MIT](LICENSE)
