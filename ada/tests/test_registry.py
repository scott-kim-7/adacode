from pathlib import Path

import yaml

from ada.registry import get_profile, load_registry


def test_load_registry_has_three_profiles():
	reg = load_registry()
	assert set(reg.profiles) >= {"chat_profile", "external_profile", "regression_profile"}


def test_chat_profile_points_to_local_openapi():
	reg = load_registry()
	p = get_profile(reg, "chat_profile")
	assert "127.0.0.1:8080" in p.base_url
	assert p.base_url.endswith("/v1")


def test_external_profile_uses_vault():
	reg = load_registry()
	p = get_profile(reg, "external_profile")
	assert p.api_key_vault == "external.openai.api_key"


def test_tri_chat_config():
	reg = load_registry()
	assert reg.tri_chat.local_profile == "chat_profile"
	assert reg.tri_chat.external_profile == "external_profile"
	assert "user" in reg.tri_chat.turn_order


def test_registry_yaml_exists():
	path = Path(__file__).resolve().parents[1] / "config" / "model_registry.yaml"
	assert path.is_file()
	with path.open(encoding="utf-8") as f:
		data = yaml.safe_load(f)
	assert "profiles" in data
