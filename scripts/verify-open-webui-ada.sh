#!/usr/bin/env bash
# Verify vendored Open WebUI has Ada Email UI integration files.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${ROOT}/web/open-webui"
OVERLAY="${ROOT}/web/open-webui-overlays"

if [[ ! -d "${TARGET}/.git" ]]; then
	echo "Run ./scripts/vendor-open-webui.sh first" >&2
	exit 1
fi

TAG="$(git -C "${TARGET}" describe --tags 2>/dev/null || true)"
if [[ "${TAG}" != "v0.6.42" ]]; then
	echo "Expected tag v0.6.42, got: ${TAG:-unknown}" >&2
	exit 1
fi

grep -q ada-email "${TARGET}/src/lib/components/admin/Settings.svelte"
grep -q showAdaInbox "${TARGET}/src/lib/stores/index.ts"
grep -q AdaInboxPanel "${TARGET}/src/lib/components/chat/ChatControls.svelte"
grep -q showAdaInbox "${TARGET}/src/lib/components/chat/Chat.svelte"
grep -q PUBLIC_ADA_AGENT_BASE_URL "${TARGET}/Dockerfile"
test -f "${OVERLAY}/src/lib/apis/ada.ts"
test -f "${TARGET}/src/lib/components/admin/Settings/AdaEmail.svelte"
test -f "${TARGET}/src/lib/components/admin/Settings/AdaSummarySkipRules.svelte"
test -f "${TARGET}/src/lib/components/ada/AdaEmailArchive.svelte"
test -f "${TARGET}/src/routes/(app)/ada/email/+page.svelte"
test -f "${TARGET}/src/routes/(app)/ada/email/+layout.svelte"
! test -f "${TARGET}/src/routes/(app)/ada/email/+page.server.ts"
test -f "${TARGET}/backend/open_webui/routers/ada.py"
grep -q 'prefix="/api/v1/ada"' "${TARGET}/backend/open_webui/main.py"
grep -q '/agent/{path:path}' "${TARGET}/backend/open_webui/routers/ada.py"
grep -q 'retrieval/sources' "${TARGET}/backend/open_webui/routers/ada.py"
grep -q 'X-Ada-Owui-Authorization' "${TARGET}/backend/open_webui/routers/openai.py"
grep -q 'X-Ada-Request-Kind' "${TARGET}/backend/open_webui/routers/openai.py"
grep -q '_ada_agent_handles_context' "${TARGET}/backend/open_webui/utils/middleware.py"
grep -q 'ADA_AGENT_HANDLES_CONTEXT' "${ROOT}/web/docker-compose.yml"
grep -q '_resolve_tools_dict' "${TARGET}/backend/open_webui/routers/ada.py"
grep -q WEBUI_API_BASE_URL "${TARGET}/src/lib/apis/ada.ts"
grep -q vault_unlocked "${TARGET}/src/lib/apis/ada.ts"
! grep -q syncAdaLocalKeyFromStack "${TARGET}/src/lib/apis/ada.ts"
grep -q "Open email archive" "${TARGET}/src/lib/components/admin/Settings/AdaEmail.svelte"
! grep -q "Ada Mail" "${TARGET}/src/lib/components/chat/Navbar.svelte"

echo "verify-open-webui-ada: OK (${TAG})"
