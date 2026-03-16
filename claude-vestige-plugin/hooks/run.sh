#!/usr/bin/env bash
# Wrapper que ejecuta scripts Python con el venv correcto de claude_vestige.
# Busca el venv relativo a la raíz del paquete (dos niveles arriba de hooks/).
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"
PKG_ROOT="$(dirname "$PLUGIN_ROOT")"
VENV_PYTHON="$PKG_ROOT/.venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "[Claude Vestige] Error: venv not found at $VENV_PYTHON" >&2
    exit 0  # No fallar — hooks deben ser resilientes
fi

exec "$VENV_PYTHON" "$@"
