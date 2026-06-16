#!/usr/bin/env bash
# Start Open WebUI — MLX (:8080) must already be running.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

ada_require_mlx_up
exec "$ROOT/scripts/serve-open-webui.sh"
