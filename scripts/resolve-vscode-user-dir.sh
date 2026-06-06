#!/usr/bin/env bash
# Print the Code-OSS dev build User profile directory (matches VSCODE_DEV=1).
set -euo pipefail

if [[ -n "${ADA_VSCODE_USER_DIR:-}" ]]; then
	echo "$ADA_VSCODE_USER_DIR"
	exit 0
fi

case "$(uname -s)" in
	Darwin)
		echo "$HOME/Library/Application Support/code-oss-dev/User"
		;;
	Linux)
		echo "${XDG_CONFIG_HOME:-$HOME/.config}/code-oss-dev/User"
		;;
	*)
		echo "$HOME/.vscode-oss-dev/User"
		;;
esac
