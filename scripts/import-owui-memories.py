#!/usr/bin/env python3
"""Import OWUI memories into Ada Agent local memory store (Phase 6)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request


def _fetch_memories(base_url: str, jwt: str) -> list[dict]:
	url = f"{base_url.rstrip('/')}/api/v1/memories/"
	req = urllib.request.Request(
		url,
		headers={"Authorization": f"Bearer {jwt}", "Accept": "application/json"},
		method="GET",
	)
	with urllib.request.urlopen(req, timeout=30) as resp:
		data = json.loads(resp.read().decode("utf-8"))
	if not isinstance(data, list):
		raise ValueError("unexpected memories response")
	return [item for item in data if isinstance(item, dict)]


def main() -> int:
	parser = argparse.ArgumentParser(description="Import OWUI memories to Ada agent store")
	parser.add_argument("--base-url", default=os.environ.get("ADA_OWUI_BASE_URL", "http://127.0.0.1:3000"))
	parser.add_argument("--jwt", default=os.environ.get("OWUI_JWT", ""))
	parser.add_argument(
		"--out",
		default=os.environ.get(
			"ADA_AGENT_MEMORY_STORE",
			"ada/.local/agent_memory/memories.json",
		),
	)
	args = parser.parse_args()
	if not args.jwt.strip():
		print("OWUI_JWT or --jwt required", file=sys.stderr)
		return 1

	try:
		memories = _fetch_memories(args.base_url, args.jwt.strip())
	except (urllib.error.URLError, ValueError) as exc:
		print(f"import failed: {exc}", file=sys.stderr)
		return 1

	rows: list[dict] = []
	for item in memories:
		content = item.get("content")
		if not content:
			continue
		created = item.get("created_at") or item.get("updated_at") or int(time.time())
		rows.append({"content": str(content), "created_at": int(created)})

	out_path = args.out
	os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
	with open(out_path, "w", encoding="utf-8") as fh:
		json.dump(rows, fh, ensure_ascii=False, indent=2)

	print(f"imported {len(rows)} memories -> {out_path}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
