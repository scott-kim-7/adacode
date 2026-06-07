#!/usr/bin/env bash
# Clone external benchmark vendors into .eval/vendor/ (gitignored).
set -euo pipefail

EVAL_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$EVAL_DIR/common.sh"

VENDOR_ROOT="${ADA_EVAL_VENDOR_ROOT:-$ROOT/.eval/vendor}"
mkdir -p "$VENDOR_ROOT"

echo "=== Ada eval vendor install ==="
echo "Vendor root: $VENDOR_ROOT"

clone_repo() {
	local url="$1"
	local dest="$2"
	if [[ -d "$dest/.git" ]]; then
		echo "  skip (exists): $dest"
		return 0
	fi
	echo "  clone: $url -> $dest"
	git clone --depth 1 "$url" "$dest"
}

clone_repo "https://github.com/amazon-agi/tau2-bench-verified" "$VENDOR_ROOT/tau2-bench-verified"
if [[ -d "$VENDOR_ROOT/tau2-bench-verified" ]] && command -v uv >/dev/null 2>&1; then
	( cd "$VENDOR_ROOT/tau2-bench-verified" && uv sync ) || echo "  warn: tau2 uv sync failed"
fi

clone_repo "https://github.com/ShishirPatil/gorilla" "$VENDOR_ROOT/gorilla"
if [[ -d "$VENDOR_ROOT/gorilla/berkeley-function-call-leaderboard" ]]; then
	activate_venv
	pip install -q -e "$VENDOR_ROOT/gorilla/berkeley-function-call-leaderboard" || echo "  warn: BFCL pip install failed"
fi

clone_repo "https://github.com/SWE-bench/SWE-bench" "$VENDOR_ROOT/SWE-bench"
if [[ -d "$VENDOR_ROOT/SWE-bench" ]]; then
	activate_venv
	pip install -q -e "$VENDOR_ROOT/SWE-bench" || echo "  warn: SWE-bench pip install failed"
fi

clone_repo "https://github.com/apple/ToolSandbox" "$VENDOR_ROOT/ToolSandbox"
if [[ -d "$VENDOR_ROOT/ToolSandbox/requirements.txt" ]]; then
	activate_venv
	pip install -q -r "$VENDOR_ROOT/ToolSandbox/requirements.txt" || echo "  warn: ToolSandbox pip install failed"
fi

# MCPAgentBench — pin when official repo URL is stable
MCP_URL="${ADA_MCPAGENTBENCH_REPO:-}"
if [[ -n "$MCP_URL" ]]; then
	clone_repo "$MCP_URL" "$VENDOR_ROOT/MCPAgentBench"
fi

echo "Done."
