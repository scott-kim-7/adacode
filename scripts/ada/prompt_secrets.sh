#!/usr/bin/env bash
# Prompt for vault unlock password (non-exported shell var, passed to Agent via fd 3).
# Sets (non-exported): _ADA_PROMPT_VAULT_PASSWORD
set -euo pipefail

_ada_vault_exists() {
	[[ -f "${1}/ada/vault/secrets.vault.enc" ]]
}

ada_prompt_secrets() {
	local root="${1:?root required}"
	_ADA_PROMPT_VAULT_PASSWORD=""

	if [[ ! -t 0 ]]; then
		if [[ "${ADA_NON_INTERACTIVE:-0}" == "1" ]]; then
			if _ada_vault_exists "$root" && [[ -z "${ADA_VAULT_UNLOCK_FD:-}" ]]; then
				echo "ADA_NON_INTERACTIVE=1 with vault: pipe password on fd 3, e.g.:" >&2
				echo "  printf '%s' \"\$VAULT_PASS\" | ADA_NON_INTERACTIVE=1 ADA_VAULT_UNLOCK_FD=3 ./scripts/ada.sh start 3<&0" >&2
				return 1
			fi
			return 0
		fi
		echo "Ada vault unlock: run ./scripts/ada.sh from a terminal for interactive prompts." >&2
		echo "Automation: ADA_NON_INTERACTIVE=1 ADA_VAULT_UNLOCK_FD=3 ./scripts/ada.sh start 3<&0" >&2
		return 1
	fi

	if _ada_vault_exists "$root"; then
		legacy_key="${root}/ada/.local/ada_local_api_key"
		if [[ -f "$legacy_key" ]]; then
			echo "WARNING: legacy plaintext key at ada/.local/ada_local_api_key — run: cd ada && ada vault migrate-local-key" >&2
		fi
		read -r -s -p "Vault password: " _ADA_PROMPT_VAULT_PASSWORD </dev/tty
		echo >&2
		if [[ -z "$_ADA_PROMPT_VAULT_PASSWORD" ]]; then
			echo "Vault password is required (ada/vault/secrets.vault.enc exists)." >&2
			return 1
		fi
	fi
}

ada_clear_prompt_secrets() {
	unset _ADA_PROMPT_VAULT_PASSWORD
}
