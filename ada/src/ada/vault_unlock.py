from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from ada.vault import Vault, VaultError, VaultSession, secure_zero
from ada.vault_secrets import ensure_vault_secret, scrub_forbidden_secret_env

if TYPE_CHECKING:
	pass

LOCAL_API_KEY_VAULT_KEY = "ada.local.api_key"


def _scrub_legacy_env() -> None:
	os.environ.pop("ADA_VAULT_PASSWORD", None)
	os.environ.pop("ADA_LOCAL_API_KEY", None)


def read_password_from_fd(fd: int) -> bytearray:
	try:
		raw = os.read(fd, 4096)
	finally:
		try:
			os.close(fd)
		except OSError:
			pass
	buf = bytearray(raw)
	if buf.endswith(b"\n"):
		del buf[-1]
	return buf


def _password_bytes_to_str(password: bytearray) -> str:
	return password.decode("utf-8")


def bootstrap_vault_session(*, vault: Vault | None = None) -> VaultSession | None:
	"""Unlock vault for long-running processes. Returns None if vault file missing."""
	_scrub_legacy_env()
	scrub_forbidden_secret_env()
	v = vault or Vault()
	if not v.exists():
		return None

	fd_env = os.environ.pop("ADA_VAULT_UNLOCK_FD", "").strip()
	if fd_env:
		try:
			fd = int(fd_env)
		except ValueError as exc:
			raise VaultError(f"Invalid ADA_VAULT_UNLOCK_FD: {fd_env}") from exc
		password = read_password_from_fd(fd)
		try:
			return VaultSession.unlock_from_password_bytes(v, password)
		finally:
			secure_zero(password)

	if sys.stdin.isatty():
		from ada.vault import prompt_password

		pw_str = prompt_password("VAULT_UNLOCK")
		pw = bytearray(pw_str.encode("utf-8"))
		del pw_str
		try:
			return VaultSession.unlock_from_password_bytes(v, pw)
		finally:
			secure_zero(pw)

	raise VaultError(
		"Vault exists but no unlock source. "
		"Use ADA_VAULT_UNLOCK_FD or run from a TTY."
	)


def ensure_local_api_key(session: VaultSession) -> str:
	value, _created = ensure_vault_secret(session, LOCAL_API_KEY_VAULT_KEY)
	return value
