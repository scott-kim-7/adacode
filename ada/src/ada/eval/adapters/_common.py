from __future__ import annotations

from pathlib import Path
from typing import Any

from ada.eval.harness.config import results_dir
from ada.eval.harness.results import write_result
from ada.eval.harness.run_log import create_benchmark_log, current_log_path, log_event, log_line


def begin_benchmark(benchmark: str, mode: str) -> Path:
	log_path = create_benchmark_log(benchmark, mode)
	log_event("benchmark_start", benchmark=benchmark, mode=mode)
	return log_path


def annotate_result(
	payload: dict[str, Any],
	*,
	mode: str,
	vendor_path: Path | None = None,
	vendor_ran: bool = False,
	fallback_reason: str | None = None,
	subprocess_log: Path | None = None,
) -> dict[str, Any]:
	payload = dict(payload)
	payload["mode"] = mode
	extra: dict[str, Any] = dict(payload.get("extra") or {})
	extra["requested_mode"] = mode
	extra["vendor_path"] = str(vendor_path) if vendor_path else None
	extra["vendor_available"] = bool(vendor_path and vendor_path.is_dir())
	extra["vendor_ran"] = vendor_ran
	if fallback_reason:
		extra["fallback_reason"] = fallback_reason
		log_line(f"FALLBACK: {fallback_reason}", level="WARN")
	if subprocess_log:
		extra["subprocess_log"] = str(subprocess_log)
	session_log = current_log_path()
	if session_log:
		payload["session_log"] = str(session_log)
		extra["benchmark_log"] = str(session_log)
	payload["extra"] = extra
	return payload


def save_benchmark_result(
	benchmark: str,
	mode: str,
	payload: dict[str, Any],
	output: Path | None = None,
) -> dict[str, Any]:
	out = output or results_dir() / f"{benchmark}-{mode}.json"
	write_result(out, payload)
	log_event(
		"benchmark_done",
		benchmark=benchmark,
		mode=mode,
		pass_rate=payload.get("pass_rate"),
		source=(payload.get("extra") or {}).get("source"),
		result=str(out),
	)
	return payload
