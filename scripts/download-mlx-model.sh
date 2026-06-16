#!/usr/bin/env bash
# Pre-download an MLX model to the Hugging Face cache (no server, no RAM load).
# Requires ADA_MLX_MODEL (Hugging Face repo id).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

if [[ -z "${ADA_MLX_MODEL:-}" ]]; then
	echo "ERROR: Set ADA_MLX_MODEL to the Hugging Face repo id to download." >&2
	echo "Example: ADA_MLX_MODEL=org/repo-name ./scripts/download-mlx-model.sh" >&2
	exit 1
fi

MODEL="$ADA_MLX_MODEL"
DISPLAY_NAME="${ADA_MLX_DISPLAY_NAME:-$MODEL}"

"$ROOT/scripts/ensure-mlx-venv.sh"
# shellcheck source=/dev/null
source "$ROOT/.venv-mlx/bin/activate"

echo "Downloading MLX model to Hugging Face cache"
echo "  label: $DISPLAY_NAME"
echo "  repo:  $MODEL"
echo ""
echo "This only downloads files. It does not start the MLX server or load weights into RAM."
echo "Cache: \$HF_HOME or ~/.cache/huggingface/hub"
echo ""

export ADA_MLX_MODEL="$MODEL"
export ADA_MLX_DISPLAY_NAME="$DISPLAY_NAME"

python "$ROOT/scripts/ada/download_mlx_model.py"
