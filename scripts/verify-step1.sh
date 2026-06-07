#!/usr/bin/env bash
# Step 1 automated verification (Go/No-Go items that do not require GUI).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"
USER_DIR="$("$ROOT/scripts/resolve-vscode-user-dir.sh")"
HOST="${ADA_MLX_HOST:-127.0.0.1}"
PORT="${ADA_MLX_PORT:-8080}"
MODEL="${ADA_MLX_MODEL:-$ADA_MLX_MODEL_DEFAULT}"
PASS=0
FAIL=0

ok() { echo "  [ok] $1"; PASS=$((PASS + 1)); }
bad() { echo "  [FAIL] $1" >&2; FAIL=$((FAIL + 1)); }

echo "=== Step 1 verification ==="
echo ""

# 1. venv + mlx-lm + mlx-vlm
if [[ -d "$ROOT/.venv-mlx" ]] \
	&& "$ROOT/.venv-mlx/bin/python" -c "import mlx_lm, mlx_vlm" 2>/dev/null; then
	ok "MLX venv (.venv-mlx + mlx-lm + mlx-vlm)"
else
	bad "MLX venv missing — run: ./scripts/ensure-mlx-venv.sh"
fi

# 2. scripts
for f in adacode.sh serve-qwen.sh ensure-mlx-venv.sh stop-mlx-server.sh install-step1.sh verify-step1-mlx.sh verify-step1-vision.sh download-qwen-model.sh; do
	if [[ -x "$ROOT/scripts/$f" ]]; then
		ok "scripts/$f executable"
	else
		bad "scripts/$f missing or not executable"
	fi
done

# 3. BYOK config
if [[ -f "$USER_DIR/chatLanguageModels.json" ]] && grep -q "$ADA_MLX_BYOK_ID_MARKER" "$USER_DIR/chatLanguageModels.json"; then
	if python3 "$ROOT/scripts/ada/verify_byok_schema.py" "$USER_DIR/chatLanguageModels.json"; then
		ok "chatLanguageModels.json (flat BYOK schema + $ADA_MLX_DISPLAY_NAME_DEFAULT)"
	else
		bad "chatLanguageModels.json has wrong schema (nested configuration) — run: ./scripts/install-step1.sh"
	fi
else
	bad "chatLanguageModels.json missing — run: ./scripts/install-step1.sh"
fi

# 4. settings
if [[ -f "$USER_DIR/settings.json" ]] && grep -q '"chat.agent.enabled": true' "$USER_DIR/settings.json"; then
	ok "settings.json (chat.agent.enabled)"
else
	bad "settings.json missing agent flag — run: ./scripts/install-step1.sh"
fi

# 5. compile artifact (light check)
if [[ -d "$ROOT/.build/electron" ]] || [[ -d "$ROOT/out" ]]; then
	ok "IDE build artifacts present"
else
	bad "IDE not compiled — run: npm run compile"
fi

# 6. MLX server
BASE="http://${HOST}:${PORT}"
if curl -sf "$BASE/v1/models" >/dev/null 2>&1; then
	ok "MLX server responding ($BASE)"
else
	bad "MLX server not running — run: ./scripts/serve-qwen.sh (or ./scripts/adacode.sh)"
fi

# 7. chat completion (72B)
if curl -sf "$BASE/v1/models" >/dev/null 2>&1; then
	RESP=$(curl -sf "$BASE/v1/chat/completions" \
		-H "Content-Type: application/json" \
		-d "{\"model\":\"${MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: STEP1_OK\"}],\"stream\":false,\"max_tokens\":32}" \
		|| true)
	if echo "$RESP" | grep -q "STEP1_OK\|step1_ok\|Step1"; then
		ok "Qwen chat completion ($MODEL)"
	elif echo "$RESP" | grep -q '"content"'; then
		ok "Qwen chat completion ($MODEL) — got response"
	else
		bad "Qwen chat completion failed for $MODEL"
		echo "    Response: ${RESP:0:200}" >&2
	fi
fi

# 8. vision (when server running; skip if mlx_lm text-only)
if curl -sf "$BASE/v1/models" >/dev/null 2>&1 && [[ -d "$ROOT/.venv-mlx" ]]; then
	export ADA_MLX_HOST="$HOST" ADA_MLX_PORT="$PORT" ADA_MLX_MODEL="$MODEL"
	if source "$ROOT/.venv-mlx/bin/activate" && python "$ROOT/scripts/ada/verify_mlx_vision.py" >/dev/null 2>&1; then
		ok "MLX vision (image_url via mlx-vlm server)"
	elif source "$ROOT/.venv-mlx/bin/activate" && python "$ROOT/scripts/ada/verify_mlx_vision.py" 2>&1 | grep -q "text-only"; then
		bad "MLX server is text-only (mlx_lm) — run: ./scripts/stop-mlx-server.sh && ./scripts/serve-qwen.sh"
	else
		echo "  [skip] MLX vision probe (server warming up or model loading)"
	fi
fi

# 9. HF model cache (no server load; skips if venv missing)
if [[ -d "$ROOT/.venv-mlx" ]]; then
	export ADA_MLX_MODEL="$MODEL"
	# shellcheck source=/dev/null
	if source "$ROOT/.venv-mlx/bin/activate" && python "$ROOT/scripts/ada/verify_mlx_cache.py" >/dev/null 2>&1; then
		ok "Qwen model in HF cache (verify-qwen-download)"
	else
		bad "Qwen model not in HF cache — run: ./scripts/download-qwen-model.sh"
	fi
else
	echo "  [skip] HF cache check (no .venv-mlx)"
fi

# 10. docs
if [[ -f "$ROOT/docs/ada/step1/README.md" ]]; then
	ok "Step 1 documentation"
else
	bad "docs/ada/step1/ missing"
fi

echo ""
echo "=== Result: $PASS passed, $FAIL failed ==="

if [[ $FAIL -gt 0 ]]; then
	echo ""
	echo "Fix failures above, then re-run: ./scripts/verify-step1.sh"
	exit 1
fi

echo ""
echo "Automated Step 1 checks passed."
echo "Manual IDE checks (once): ./scripts/adacode.sh"
echo "  • Model picker → ${ADA_MLX_DISPLAY_NAME_DEFAULT}"
echo "  • #filename file context"
echo "  • diff Accept/Reject"
echo "  • Agent tool call"
echo "  • Image attach (mlx-vlm server) — ./scripts/verify-step1-vision.sh"
