from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SubprocessResult:
	returncode: int
	stdout: str
	stderr: str
	duration_sec: float
	log_path: Path | None = None


def run_command(
	cmd: list[str],
	*,
	cwd: Path | None = None,
	timeout: float | None = None,
	env: dict[str, str] | None = None,
	log_name: str | None = None,
) -> SubprocessResult:
	import time

	from ada.eval.harness.run_log import write_subprocess_log

	start = time.monotonic()
	try:
		proc = subprocess.run(
			cmd,
			cwd=str(cwd) if cwd else None,
			env=env,
			capture_output=True,
			text=True,
			timeout=timeout,
			check=False,
		)
	except subprocess.TimeoutExpired as exc:
		duration = time.monotonic() - start
		result = SubprocessResult(
			returncode=124,
			stdout=str(exc.stdout or ""),
			stderr=f"TIMEOUT after {timeout}s\n{exc.stderr or ''}",
			duration_sec=duration,
		)
	else:
		result = SubprocessResult(
			returncode=proc.returncode,
			stdout=proc.stdout,
			stderr=proc.stderr,
			duration_sec=time.monotonic() - start,
		)

	if log_name:
		log_path = write_subprocess_log(log_name, cmd, result, cwd=cwd)
		return SubprocessResult(
			returncode=result.returncode,
			stdout=result.stdout,
			stderr=result.stderr,
			duration_sec=result.duration_sec,
			log_path=log_path,
		)
	return result


def load_json_file(path: Path) -> dict[str, Any]:
	raw = json.loads(path.read_text(encoding="utf-8"))
	if not isinstance(raw, dict):
		raise ValueError(f"expected JSON object in {path}")
	return raw
