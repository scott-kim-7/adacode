#!/usr/bin/env bash
# Create/update .venv-mlx with mlx-lm (text) + mlx-vlm (vision server).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv-mlx"

if [[ ! -d "$VENV" ]]; then
	echo "Creating .venv-mlx ..."
	python3 -m venv "$VENV"
fi

# shellcheck source=/dev/null
source "$VENV/bin/activate"
pip install -U pip mlx-lm mlx-vlm >/dev/null

if ! python -c "import mlx_lm, mlx_vlm" 2>/dev/null; then
	echo "Failed to install mlx-lm / mlx-vlm in $VENV" >&2
	exit 1
fi
