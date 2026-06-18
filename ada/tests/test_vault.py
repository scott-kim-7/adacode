import json

from ada.vault import Vault, VaultSession, _decrypt_payload, _encrypt_payload, secure_zero


def test_vault_roundtrip(tmp_path):
	path = tmp_path / "secrets.vault.enc"
	v = Vault(path)
	password = "test-vault-password"
	secrets = {"external.openai.api_key": "sk-test", "github.token": "ghp_test"}
	v.save(secrets, password)
	loaded = v.unlock(password)
	assert loaded == secrets


def test_vault_set_key(tmp_path):
	path = tmp_path / "secrets.vault.enc"
	v = Vault(path)
	v.init("pw1")
	v.set_key("a.b", "value1", "pw1")
	assert v.get("a.b", "pw1") == "value1"


def test_encrypt_format(tmp_path):
	blob = _encrypt_payload({"k": "v"}, "password")
	data = json.loads(blob.decode("utf-8"))
	assert "salt" in data and "nonce" in data and "ciphertext" in data
	assert _decrypt_payload(blob, "password") == {"k": "v"}


def test_vault_session_unlock_and_save_without_password(tmp_path):
	path = tmp_path / "secrets.vault.enc"
	v = Vault(path)
	v.init("pw1")
	session = VaultSession.unlock_from_password(v, "pw1")
	session.set("a.b", "value2")
	session.save()
	reloaded = VaultSession.unlock_from_password(v, "pw1")
	assert reloaded.get("a.b") == "value2"


def test_secure_zero():
	buf = bytearray(b"secret")
	secure_zero(buf)
	assert buf == bytearray(len(buf))

