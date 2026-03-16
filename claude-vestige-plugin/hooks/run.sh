#!/usr/bin/env bash
# Wrapper que ejecuta scripts Python con el entorno correcto de claude-vestige.
# Busca Python en este orden:
#   1. Venv instalado por install.sh (~/.claude-vestige/.venv/)
#   2. Venv local del repo (desarrollo con --plugin-dir)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"
PKG_ROOT="$(dirname "$PLUGIN_ROOT")"

# 1. Venv global (instalado por install.sh)
GLOBAL_PYTHON="$HOME/.claude-vestige/.venv/bin/python"
if [ -f "$GLOBAL_PYTHON" ]; then
    exec "$GLOBAL_PYTHON" "$@"
fi

# 2. Venv local (desarrollo)
LOCAL_PYTHON="$PKG_ROOT/.venv/bin/python"
if [ -f "$LOCAL_PYTHON" ]; then
    exec "$LOCAL_PYTHON" "$@"
fi

echo "[Claude Vestige] Error: Python environment not found. Run install.sh first." >&2
exit 0
