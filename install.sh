#!/usr/bin/env bash
set -e

# Claude Vestige — Installer
# Creates venv, installs dependencies, registers marketplace, installs plugin.

VESTIGE_HOME="$HOME/.claude-vestige"
VENV_DIR="$VESTIGE_HOME/.venv"

echo ""
echo "  Claude Vestige — Persistent semantic memory for Claude Code"
echo "  ============================================================"
echo ""

# 1. Check prerequisites
echo "[1/4] Checking prerequisites..."

if ! command -v python3 &>/dev/null; then
    echo "  ✘ python3 not found. Install Python 3.11+ first."
    exit 1
fi
echo "  ✔ python3 found: $(python3 --version)"

if ! python3 -c "import venv" &>/dev/null; then
    echo "  ✘ python3-venv not found. Install it:"
    echo "    sudo apt install python3-venv  (Debian/Ubuntu)"
    echo "    brew install python3            (macOS)"
    exit 1
fi
echo "  ✔ python3-venv available"

if ! command -v claude &>/dev/null; then
    echo "  ✘ claude CLI not found. Install Claude Code first:"
    echo "    npm install -g @anthropic-ai/claude-code"
    exit 1
fi
echo "  ✔ claude CLI found: $(claude --version 2>/dev/null | head -1)"

# 2. Create venv and install dependencies
echo ""
echo "[2/4] Setting up Python environment..."

mkdir -p "$VESTIGE_HOME"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "  ✔ Virtual environment created at $VENV_DIR"
else
    echo "  ✔ Virtual environment already exists"
fi

# Determine install source — if running from cloned repo, install from there
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
    INSTALL_SOURCE="$SCRIPT_DIR"
    echo "  Installing from local source: $INSTALL_SOURCE"
else
    INSTALL_SOURCE="git+https://github.com/MrMokuchoDev/claude-vestige.git"
    echo "  Installing from GitHub..."
fi

"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet "$INSTALL_SOURCE"
"$VENV_DIR/bin/pip" install --quiet fastapi uvicorn
echo "  ✔ Dependencies installed"

# 3. Register marketplace
echo ""
echo "[3/4] Registering plugin marketplace..."

# Determine plugin source path
if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
    MARKETPLACE_SOURCE="$SCRIPT_DIR"
else
    # Clone repo to a known location for marketplace
    REPO_DIR="$VESTIGE_HOME/repo"
    if [ -d "$REPO_DIR" ]; then
        cd "$REPO_DIR" && git pull --quiet 2>/dev/null || true
        cd - >/dev/null
    else
        git clone --quiet https://github.com/MrMokuchoDev/claude-vestige.git "$REPO_DIR"
    fi
    MARKETPLACE_SOURCE="$REPO_DIR"
fi

# Remove old marketplace/plugin if exists
claude plugin uninstall claude-vestige 2>/dev/null || true
claude plugin marketplace remove claude-vestige-tools 2>/dev/null || true

claude plugin marketplace add "$MARKETPLACE_SOURCE" 2>/dev/null
echo "  ✔ Marketplace registered"

# 4. Install plugin
echo ""
echo "[4/4] Installing plugin..."

claude plugin install claude-vestige 2>/dev/null
echo "  ✔ Plugin installed"

# Done
echo ""
echo "  ============================================================"
echo "  ✔ Claude Vestige installed successfully!"
echo ""
echo "  Open Claude Code in any project and it will:"
echo "    • Auto-index README.md and CLAUDE.md"
echo "    • Inject relevant context at session start"
echo "    • Capture observations on file changes"
echo ""
echo "  Dashboard: ~/.claude-vestige/.venv/bin/python -m claude_vestige.api --port 7843"
echo "  ============================================================"
echo ""
