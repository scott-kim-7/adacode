from __future__ import annotations

import os

from ada.eval.harness.config import eval_base_url
from ada.openai_models import NoLoadedModelError, resolve_model_id


def resolved_eval_model() -> str:
	# Offline/CI fixtures only — not used for live MLX routing.
	offline = os.environ.get("ADA_EVAL_MODEL", "").strip()
	if offline:
		return offline
	base = eval_base_url().rstrip("/")
	api_key = os.environ.get("OPENAI_API_KEY", "local")
	try:
		return resolve_model_id(base, api_key=api_key)
	except NoLoadedModelError:
		return "openapi-unloaded"
