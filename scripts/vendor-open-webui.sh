#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${ROOT}/web/open-webui"
TAG="v0.6.42"
OVERLAY="${ROOT}/web/open-webui-overlays"

mkdir -p "${TARGET}"

if [[ -d "${TARGET}/.git" ]]; then
	git -C "${TARGET}" fetch --tags --depth 1 origin "${TAG}" 2>/dev/null || true
	git -C "${TARGET}" checkout -f "${TAG}"
else
	rm -rf "${TARGET}"
	git clone --depth 1 --branch "${TAG}" https://github.com/open-webui/open-webui.git "${TARGET}"
fi

# Ada overlay components + API client
mkdir -p "${TARGET}/src/lib/apis"
mkdir -p "${TARGET}/src/lib/components/admin/Settings"
mkdir -p "${TARGET}/src/lib/components/ada/icons"
mkdir -p "${TARGET}/src/routes/(app)/ada/email"
cp -R "${OVERLAY}/src/lib/." "${TARGET}/src/lib/"
if [[ -d "${OVERLAY}/src/routes" ]]; then
	cp -R "${OVERLAY}/src/routes/." "${TARGET}/src/routes/"
fi
rm -f "${TARGET}/src/routes/(app)/ada/email/+page.server.ts"

mkdir -p "${TARGET}/backend/open_webui/routers"
cp "${OVERLAY}/backend/open_webui/routers/ada.py" "${TARGET}/backend/open_webui/routers/ada.py"

python3 "${OVERLAY}/apply-overrides.py" "${TARGET}" "${OVERLAY}"

touch "${TARGET}/.ada-overlay-stamp"

echo "Open WebUI ${TAG} vendored with Ada Email UI overlays."
git -C "${TARGET}" describe --tags 2>/dev/null || true
