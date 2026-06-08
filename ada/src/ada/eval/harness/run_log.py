from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ada.eval.harness.subprocess_runner import SubprocessResult


def logs_dir() -> Path:
	root = Path(__file__).resolve().parents[1] / "logs"
	root.mkdir(parents=True, exist_ok=True)
	(root / "sessions").mkdir(parents=True, exist_ok=True)
	(root / "benchmarks").mkdir(parents=True, exist_ok=True)
	(root / "subprocess").mkdir(parents=True, exist_ok=True)
	return root


def _slug() -> str:
	return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _write_lines(path: Path, lines: list[str]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("a", encoding="utf-8") as handle:
		for line in lines:
			handle.write(line)
			if not line.endswith("\n"):
				handle.write("\n")


def current_log_path() -> Path | None:
	raw = os.environ.get("ADA_EVAL_LOG")
	return Path(raw) if raw else None


def set_current_log(path: Path) -> None:
	os.environ["ADA_EVAL_LOG"] = str(path)


def create_session_log(suite: str, mode: str = "") -> Path:
	suffix = f"-{mode}" if mode else ""
	path = logs_dir() / "sessions" / f"{_slug()}-{suite}{suffix}.log"
	path.write_text(
		f"# Ada eval session log\n# suite={suite} mode={mode or 'n/a'}\n# started={_now()}\n\n",
		encoding="utf-8",
	)
	set_current_log(path)
	latest = logs_dir() / f"latest-{suite}{suffix}.log"
	if latest.exists() or latest.is_symlink():
		latest.unlink()
	try:
		latest.symlink_to(path.resolve())
	except OSError:
		latest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
	return path


def create_benchmark_log(benchmark: str, mode: str) -> Path:
	path = logs_dir() / "benchmarks" / f"{_slug()}-{benchmark}-{mode}.log"
	path.write_text(
		f"# benchmark={benchmark} mode={mode}\n# started={_now()}\n\n",
		encoding="utf-8",
	)
	set_current_log(path)
	return path


def log_line(message: str, *, level: str = "INFO") -> None:
	line = f"[{_now()}] [{level}] {message}"
	print(line, flush=True)
	path = current_log_path()
	if path:
		_write_lines(path, [line])


def log_event(event: str, **fields: Any) -> None:
	parts = " ".join(f"{key}={value!r}" for key, value in fields.items())
	log_line(f"{event} {parts}".strip())


def write_subprocess_log(name: str, cmd: list[str], result: SubprocessResult, *, cwd: Path | None = None) -> Path:
	path = logs_dir() / "subprocess" / f"{_slug()}-{name.replace(' ', '_')}.log"
	lines = [
		f"# subprocess: {name}",
		f"# started={_now()}",
		f"# cwd={cwd or '.'}",
		f"# cmd={' '.join(cmd)}",
		f"# returncode={result.returncode}",
		f"# duration_sec={result.duration_sec:.2f}",
		"",
		"=== STDOUT ===",
		result.stdout or "(empty)",
		"",
		"=== STDERR ===",
		result.stderr or "(empty)",
		"",
	]
	path.write_text("\n".join(lines), encoding="utf-8")
	log_event("subprocess_complete", name=name, log=str(path), returncode=result.returncode)
	session = current_log_path()
	if session:
		_write_lines(session, [f"[{_now()}] subprocess log: {path}"])
	return path


def _now() -> str:
	return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
