#!/usr/bin/env bash
# Deprecated alias — use verify-mlx-download.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "NOTE: verify-qwen-download.sh is deprecated. Use ./scripts/verify-mlx-download.sh" >&2
exec "$ROOT/scripts/verify-mlx-download.sh" "$@"
