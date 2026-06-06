from __future__ import annotations

import base64
import json
import os
import unicodedata
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from ada.paths import vault_path

VAULT_VERSION = 1
PBKDF2_ITERATIONS = 600_000
SALT_BYTES = 16
NONCE_BYTES = 12


class VaultError(Exception):
	pass


def _normalize_password(password: str) -> bytes:
	return unicodedata.normalize("NFKC", password.strip()).encode("utf-8")


def _derive_key(password: str, salt: bytes) -> bytes:
	kdf = PBKDF2HMAC(
		algorithm=hashes.SHA256(),
		length=32,
		salt=salt,
		iterations=PBKDF2_ITERATIONS,
	)
	return kdf.derive(_normalize_password(password))


def _encrypt_payload(secrets: dict[str, str], password: str) -> bytes:
	salt = os.urandom(SALT_BYTES)
	key = _derive_key(password, salt)
	nonce = os.urandom(NONCE_BYTES)
	plaintext = json.dumps(secrets, ensure_ascii=False, sort_keys=True).encode("utf-8")
	ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
	envelope = {
		"version": VAULT_VERSION,
		"salt": base64.b64encode(salt).decode("ascii"),
		"nonce": base64.b64encode(nonce).decode("ascii"),
		"ciphertext": base64.b64encode(ciphertext).decode("ascii"),
	}
	return json.dumps(envelope, indent=2).encode("utf-8")


def _decrypt_payload(blob: bytes, password: str) -> dict[str, str]:
	try:
		envelope = json.loads(blob.decode("utf-8"))
		salt = base64.b64decode(envelope["salt"])
		nonce = base64.b64decode(envelope["nonce"])
		ciphertext = base64.b64decode(envelope["ciphertext"])
		key = _derive_key(password, salt)
		plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
		data = json.loads(plaintext.decode("utf-8"))
		return {str(k): str(v) for k, v in data.items()}
	except Exception as exc:
		raise VaultError("Vault unlock failed (wrong password or corrupt file)") from exc


class Vault:
	def __init__(self, path: Path | None = None) -> None:
		self.path = path or vault_path()

	def exists(self) -> bool:
		return self.path.is_file()

	def init(self, password: str) -> None:
		self.path.parent.mkdir(parents=True, exist_ok=True)
		self.path.write_bytes(_encrypt_payload({}, password))

	def unlock(self, password: str) -> dict[str, str]:
		if not self.exists():
			raise VaultError(f"Vault not found: {self.path}. Run: make vault-init")
		return _decrypt_payload(self.path.read_bytes(), password)

	def save(self, secrets: dict[str, str], password: str) -> None:
		self.path.parent.mkdir(parents=True, exist_ok=True)
		self.path.write_bytes(_encrypt_payload(secrets, password))

	def set_key(self, key: str, value: str, password: str) -> None:
		secrets = self.unlock(password) if self.exists() else {}
		secrets[key] = value
		self.save(secrets, password)

	def list_keys(self, password: str) -> list[str]:
		return sorted(self.unlock(password).keys())

	def get(self, key: str, password: str) -> str | None:
		return self.unlock(password).get(key)


def prompt_password(action: str) -> str:
	import getpass

	print(f"[VAULT ACTION REQUIRED: {action}]")
	print(f"  파일: {vault_path()}")
	return getpass.getpass("Vault password: ")
