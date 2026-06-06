from __future__ import annotations

from pathlib import Path


def ada_root() -> Path:
	"""Return the ada/ package root (contains config/, vault/)."""
	return Path(__file__).resolve().parents[2]


def registry_path() -> Path:
	return ada_root() / "config" / "model_registry.yaml"


def vault_path() -> Path:
	return ada_root() / "vault" / "secrets.vault.enc"
