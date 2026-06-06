#!/usr/bin/env bash
# Pre-download the Step 1 MLX model to the Hugging Face cache (no server, no RAM load).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv-mlx"
MODEL="${ADA_MLX_MODEL:-mlx-community/Qwen2.5-VL-72B-Instruct-4bit}"
DISPLAY_NAME="${ADA_MLX_DISPLAY_NAME:-Qwen2.5-VL-72B-Instruct (MLX 4-bit)}"

ensure_venv() {
	if [[ ! -d "$VENV" ]]; then
		echo "Creating .venv-mlx and installing mlx-lm ..."
		python3 -m venv "$VENV"
		# shellcheck source=/dev/null
		source "$VENV/bin/activate"
		pip install -U pip mlx-lm
	else
		# shellcheck source=/dev/null
		source "$VENV/bin/activate"
	fi
}

ensure_venv

echo "Downloading MLX model to Hugging Face cache"
echo "  name:  $DISPLAY_NAME"
echo "  repo:  $MODEL"
echo ""
echo "This only downloads files (~40GB+). It does not start the MLX server or load weights into RAM."
echo "Cache: \$HF_HOME or ~/.cache/huggingface/hub"
echo ""

export ADA_MLX_MODEL="$MODEL"
export ADA_MLX_DISPLAY_NAME="$DISPLAY_NAME"

python "$ROOT/scripts/ada/download_mlx_model.py"
