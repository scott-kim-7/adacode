"""Central policy: all credentials enter vault encrypted; plaintext is never persisted."""

from __future__ import annotations

import os
import secrets
from typing import TYPE_CHECKING

from ada.vault import Vault, VaultError, VaultSession, prompt_password, secure_zero

if TYPE_CHECKING:
	pass

# Non-secret placeholders allowed in registry (not stored in vault).
PUBLIC_API_KEY_TOKENS = frozenset({"local"})

# Plaintext secret env vars are forbidden — use vault keys only.
FORBIDDEN_SECRET_ENV_VARS = frozenset(
	{
		"ADA_VAULT_PASSWORD",
		"ADA_LOCAL_API_KEY",
		"ADA_EXTERNAL_API_KEY",
	}
)

FORBIDDEN_SECRET_ENV_PREFIXES = ("ADA_GMAIL_", "ADA_VAULT_")

DEFAULT_AUTO_SECRET_BYTES = 32

# Keys that require user-provided structured secrets (never auto-generate).
MANUAL_INPUT_VAULT_KEYS = frozenset({"gmail.oauth.client"})


class PlaintextSecretError(VaultError):
	"""Raised when a secret would be stored or read outside vault."""


def scrub_forbidden_secret_env() -> list[str]:
	"""Remove known secret env vars from the process environment. Returns removed names."""
	removed: list[str] = []
	for name in FORBIDDEN_SECRET_ENV_VARS:
		if name in os.environ:
			os.environ.pop(name, None)
			removed.append(name)
	for name in list(os.environ):
		upper = name.upper()
		if upper.startswith(FORBIDDEN_SECRET_ENV_PREFIXES) and upper not in FORBIDDEN_SECRET_ENV_VARS:
			if "KEY" in upper or "PASSWORD" in upper or "SECRET" in upper or "TOKEN" in upper:
				os.environ.pop(name, None)
				removed.append(name)
	return removed


def assert_profile_secret_policy(profile_name: str, api_key: str | None, api_key_vault: str | None) -> None:
	if api_key and api_key not in PUBLIC_API_KEY_TOKENS:
		raise PlaintextSecretError(
			f"Profile '{profile_name}' must not store api_key in config. "
			f"Use api_key_vault and: make vault-set KEY=..."
		)


def read_tty_secret_bytes(prompt: str) -> bytearray:
	import getpass

	text = getpass.getpass(prompt)
	buf = bytearray(text.encode("utf-8"))
	del text
	return buf


def unlock_vault_session_from_tty(action: str) -> VaultSession:
	vault = Vault()
	if not vault.exists():
		raise VaultError(f"Vault not found: {vault.path}. Run: make vault-init")
	pw = bytearray(prompt_password(action).encode("utf-8"))
	try:
		return VaultSession.unlock_from_password_bytes(vault, pw)
	finally:
		secure_zero(pw)


def store_secret_in_vault(key: str, value: bytearray, *, unlock_action: str = "VAULT_SET") -> None:
	"""Encrypt value into vault immediately; zero plaintext buffers before return."""
	if not key.strip():
		raise VaultError("vault key is required")
	session = unlock_vault_session_from_tty(unlock_action)
	try:
		session.set(key, value.decode("utf-8"))
		session.save()
	finally:
		secure_zero(value)


def generate_vault_secret(*, nbytes: int = DEFAULT_AUTO_SECRET_BYTES) -> bytearray:
	"""Return a cryptographically strong secret as bytearray (caller must secure_zero)."""
	if nbytes < 16:
		raise VaultError("auto secret length must be at least 16 bytes")
	return bytearray(secrets.token_urlsafe(nbytes).encode("ascii"))


def ensure_vault_secret(
	session: VaultSession,
	key: str,
	*,
	nbytes: int = DEFAULT_AUTO_SECRET_BYTES,
	force: bool = False,
) -> tuple[str, bool]:
	"""Generate a complex secret if missing (or when force); store encrypted. Returns (value, created)."""
	if not key.strip():
		raise VaultError("vault key is required")
	if key in MANUAL_INPUT_VAULT_KEYS:
		raise VaultError(
			f"Vault key {key!r} cannot be auto-generated. "
			f"Run: cd ada && make vault-set KEY={key}"
		)
	existing = session.get(key)
	if existing and not force:
		return existing, False
	raw = generate_vault_secret(nbytes=nbytes)
	try:
		value = raw.decode("ascii")
		session.set(key, value)
		session.save()
		return value, True
	finally:
		secure_zero(raw)


def ensure_secret_in_vault(
	key: str,
	*,
	nbytes: int = DEFAULT_AUTO_SECRET_BYTES,
	force: bool = False,
	unlock_action: str = "VAULT_ENSURE",
) -> tuple[str, bool]:
	session = unlock_vault_session_from_tty(unlock_action)
	return ensure_vault_secret(session, key, nbytes=nbytes, force=force)


def resolve_vault_secret(
	key: str,
	session: VaultSession | None,
	*,
	unlock_action: str = "VAULT_UNLOCK",
) -> str:
	if session is not None and session.is_unlocked:
		value = session.get(key)
		if not value:
			raise VaultError(f"Vault key not found: {key}")
		return value

	vault = Vault()
	if not vault.exists():
		raise VaultError(f"Vault not found: {vault.path}. Run: make vault-init")
	pw = bytearray(prompt_password(unlock_action).encode("utf-8"))
	try:
		ephemeral = VaultSession.unlock_from_password_bytes(vault, pw)
		value = ephemeral.get(key)
		if not value:
			raise VaultError(f"Vault key not found: {key}")
		return value
	finally:
		secure_zero(pw)
