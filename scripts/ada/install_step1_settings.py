#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def main() -> int:
	target = Path(sys.argv[1])
	snippet = Path(sys.argv[2])
	updates = json.loads(snippet.read_text())

	settings: dict = {}
	if target.exists():
		try:
			settings = json.loads(target.read_text() or "{}")
		except json.JSONDecodeError:
			print(f"Warning: {target} is not valid JSON; replacing with snippet.", file=sys.stderr)
			settings = {}

	changed = False
	for key, value in updates.items():
		if settings.get(key) != value:
			settings[key] = value
			changed = True

	if changed or not target.exists():
		target.write_text(json.dumps(settings, indent=4, ensure_ascii=False) + "\n")
		print(f"Updated {target}")
	else:
		print(f"Settings already up to date: {target}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
