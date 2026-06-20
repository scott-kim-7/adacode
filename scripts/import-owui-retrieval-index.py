#!/usr/bin/env python3
"""Bootstrap Ada local retrieval index from OWUI /ada/retrieval/sources."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from pathlib import Path

# Allow running from repo root without install
_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "ada" / "src"))

from ada.retrieve.local_store import load_index, retrieval_index_path, save_index  # noqa: E402


def _fetch_sources(base_url: str, jwt: str, items: list[dict], queries: list[str]) -> list[dict]:
	url = f"{base_url.rstrip('/')}/api/v1/ada/retrieval/sources"
	body = json.dumps({"items": items, "queries": queries, "full_context": False}).encode("utf-8")
	req = urllib.request.Request(
		url,
		data=body,
		headers={
			"Authorization": f"Bearer {jwt}",
			"Content-Type": "application/json",
			"Accept": "application/json",
		},
		method="POST",
	)
	with urllib.request.urlopen(req, timeout=120) as resp:
		data = json.loads(resp.read().decode("utf-8"))
	sources = data.get("sources") if isinstance(data, dict) else None
	return sources if isinstance(sources, list) else []


def main() -> int:
	parser = argparse.ArgumentParser(description="Import OWUI retrieval sources into Ada local index")
	parser.add_argument("--base-url", default=os.environ.get("ADA_OWUI_BASE_URL", "http://127.0.0.1:3000"))
	parser.add_argument("--jwt", default=os.environ.get("OWUI_JWT", ""))
	parser.add_argument("--items", default="[]", help="JSON array of retrieval items")
	parser.add_argument("--queries", default='["bootstrap"]')
	parser.add_argument("--out", default="")
	args = parser.parse_args()
	if not args.jwt.strip():
		print("OWUI_JWT or --jwt required", file=sys.stderr)
		return 1

	try:
		items = json.loads(args.items)
		queries = json.loads(args.queries)
		if not isinstance(items, list) or not isinstance(queries, list):
			raise ValueError("items and queries must be JSON arrays")
		sources = _fetch_sources(args.base_url, args.jwt.strip(), items, queries)
	except (urllib.error.URLError, ValueError, json.JSONDecodeError) as exc:
		print(f"import failed: {exc}", file=sys.stderr)
		return 1

	out_path = Path(args.out) if args.out else retrieval_index_path()
	existing = load_index(out_path)
	seen = {str(row.get("text")) for row in existing if isinstance(row, dict)}
	added = 0
	for source in sources:
		if not isinstance(source, dict):
			continue
		docs = source.get("document")
		if not isinstance(docs, list) or not docs:
			continue
		text = str(docs[0])
		if not text.strip() or text in seen:
			continue
		seen.add(text)
		meta = source.get("metadata")
		first_meta = meta[0] if isinstance(meta, list) and meta else {}
		existing.append(
			{
				"text": text,
				"metadata": first_meta if isinstance(first_meta, dict) else {},
				"source": source.get("source") or {},
			}
		)
		added += 1

	save_index(existing, out_path)
	print(f"added {added} entries -> {out_path} (total {len(existing)})")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
