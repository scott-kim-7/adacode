#!/usr/bin/env bash
# Deprecated alias — use download-mlx-model.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "NOTE: download-qwen-model.sh is deprecated. Use ./scripts/download-mlx-model.sh" >&2
exec "$ROOT/scripts/download-mlx-model.sh" "$@"
