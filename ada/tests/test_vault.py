import json

from ada.vault import Vault, _decrypt_payload, _encrypt_payload


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
