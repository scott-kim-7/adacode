from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ada.eval.harness.config import baseline_path, load_eval_config


def _now_iso() -> str:
	return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_result(path: Path, payload: dict[str, Any]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def make_result(
	benchmark: str,
	mode: str,
	*,
	endpoint: str,
	model: str,
	tasks_total: int,
	tasks_passed: int,
	duration_sec: float,
	task_ids: list[str] | None = None,
	extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
	payload: dict[str, Any] = {
		"benchmark": benchmark,
		"mode": mode,
		"timestamp": _now_iso(),
		"endpoint": endpoint,
		"model": model,
		"tasks_total": tasks_total,
		"tasks_passed": tasks_passed,
		"pass_rate": (tasks_passed / tasks_total) if tasks_total else 0.0,
		"duration_sec": round(duration_sec, 2),
		"task_ids": task_ids or [],
	}
	if extra:
		payload.update(extra)
	return payload


def load_baseline() -> dict[str, Any]:
	path = baseline_path()
	if not path.is_file():
		return {}
	raw = json.loads(path.read_text(encoding="utf-8"))
	return raw if isinstance(raw, dict) else {}


def compare_baseline(
	benchmark: str,
	pass_rate: float,
	*,
	delta: float | None = None,
) -> tuple[bool, str]:
	cfg = load_eval_config()
	threshold_delta = delta if delta is not None else float(cfg.get("baseline_delta") or 0.05)
	baseline = load_baseline()
	entry = baseline.get(benchmark)
	if not isinstance(entry, dict):
		return True, "no baseline — accept current result"
	base_rate = float(entry.get("pass_rate") or 0.0)
	min_rate = max(0.0, base_rate - threshold_delta)
	if pass_rate + 1e-9 >= min_rate:
		return True, f"pass_rate {pass_rate:.3f} >= baseline {base_rate:.3f} - {threshold_delta:.3f}"
	return False, f"pass_rate {pass_rate:.3f} < baseline {base_rate:.3f} - {threshold_delta:.3f}"


def validate_result_schema(payload: dict[str, Any]) -> None:
	required = [
		"benchmark",
		"mode",
		"timestamp",
		"endpoint",
		"model",
		"tasks_total",
		"tasks_passed",
		"pass_rate",
		"duration_sec",
	]
	for key in required:
		if key not in payload:
			raise ValueError(f"missing result field: {key}")
