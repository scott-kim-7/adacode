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


def run_command(
	cmd: list[str],
	*,
	cwd: Path | None = None,
	timeout: float | None = None,
	env: dict[str, str] | None = None,
) -> SubprocessResult:
	import time

	start = time.monotonic()
	proc = subprocess.run(
		cmd,
		cwd=str(cwd) if cwd else None,
		env=env,
		capture_output=True,
		text=True,
		timeout=timeout,
		check=False,
	)
	return SubprocessResult(
		returncode=proc.returncode,
		stdout=proc.stdout,
		stderr=proc.stderr,
		duration_sec=time.monotonic() - start,
	)


def load_json_file(path: Path) -> dict[str, Any]:
	raw = json.loads(path.read_text(encoding="utf-8"))
	if not isinstance(raw, dict):
		raise ValueError(f"expected JSON object in {path}")
	return raw
