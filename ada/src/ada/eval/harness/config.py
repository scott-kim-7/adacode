from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from ada.paths import ada_root


def repo_root() -> Path:
	return ada_root().parent


def eval_package_root() -> Path:
	return Path(__file__).resolve().parents[1]


def load_eval_config() -> dict[str, Any]:
	config_path = eval_package_root() / "config" / "eval.yaml"
	if not config_path.is_file():
		return {}
	raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
	return raw if isinstance(raw, dict) else {}


def eval_base_url() -> str:
	env = os.environ.get("ADA_EVAL_BASE_URL")
	if env:
		return env.rstrip("/")
	cfg = load_eval_config()
	return str(cfg.get("endpoint") or "http://127.0.0.1:9082/v1").rstrip("/")


def vendor_root() -> Path:
	env = os.environ.get("ADA_EVAL_VENDOR_ROOT")
	if env:
		return Path(env)
	cfg = load_eval_config()
	rel = str(cfg.get("vendor_root") or ".eval/vendor")
	return repo_root() / rel


def results_dir() -> Path:
	path = eval_package_root() / "results"
	path.mkdir(parents=True, exist_ok=True)
	return path


def baseline_path() -> Path:
	cfg = load_eval_config()
	custom = cfg.get("baseline_path")
	if custom:
		path = Path(str(custom))
		if not path.is_absolute():
			return repo_root() / path
		return path
	return results_dir() / "baseline.json"
