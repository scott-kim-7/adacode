#!/usr/bin/env bash
# Pre-download the Step 1 MLX model to the Hugging Face cache (no server, no RAM load).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"
MODEL="${ADA_MLX_MODEL:-$ADA_MLX_MODEL_DEFAULT}"
DISPLAY_NAME="${ADA_MLX_DISPLAY_NAME:-$ADA_MLX_DISPLAY_NAME_DEFAULT}"

"$ROOT/scripts/ensure-mlx-venv.sh"
# shellcheck source=/dev/null
source "$ROOT/.venv-mlx/bin/activate"

echo "Downloading MLX model to Hugging Face cache"
echo "  name:  $DISPLAY_NAME"
echo "  repo:  $MODEL"
echo ""
echo "This only downloads files. It does not start the MLX server or load weights into RAM."
echo "Cache: \$HF_HOME or ~/.cache/huggingface/hub"
echo ""

export ADA_MLX_MODEL="$MODEL"
export ADA_MLX_DISPLAY_NAME="$DISPLAY_NAME"

python "$ROOT/scripts/ada/download_mlx_model.py"
