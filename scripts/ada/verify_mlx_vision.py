#!/usr/bin/env python3
"""Probe whether the local MLX OpenAI server accepts multimodal (image) input."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

# 1x1 PNG (red pixel)
TINY_PNG_B64 = (
	"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def main() -> int:
	host = os.environ.get("ADA_MLX_HOST", "127.0.0.1")
	port = os.environ.get("ADA_MLX_PORT", "8080")
	base = f"http://{host}:{port}/v1"

	sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "ada" / "src"))
	from ada.openai_models import resolve_model_id

	model = resolve_model_id(base)

	body = {
		"model": model,
		"messages": [
			{
				"role": "user",
				"content": [
					{"type": "text", "text": "What color is this image? One word only."},
					{
						"type": "image_url",
						"image_url": {"url": f"data:image/png;base64,{TINY_PNG_B64}"},
					},
				],
			}
		],
		"stream": False,
		"max_tokens": 32,
	}

	req = urllib.request.Request(
		f"{base}/chat/completions",
		data=json.dumps(body).encode("utf-8"),
		headers={"Content-Type": "application/json"},
		method="POST",
	)

	try:
		with urllib.request.urlopen(req, timeout=300) as resp:
			payload = json.loads(resp.read().decode("utf-8"))
	except urllib.error.HTTPError as exc:
		text = exc.read().decode("utf-8", errors="replace")
		if "Only 'text' content type is supported" in text:
			print(
				"RESULT: mlx_lm text-only server detected — use a vision-capable mlx-vlm server on :8080",
				file=sys.stderr,
			)
			return 2
		print(f"RESULT: HTTP {exc.code}: {text[:400]}", file=sys.stderr)
		return 1
	except OSError as exc:
		print(f"RESULT: server unreachable at {base}: {exc}", file=sys.stderr)
		return 1

	content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
	if not content:
		print(f"RESULT: empty response: {json.dumps(payload)[:400]}", file=sys.stderr)
		return 1

	print(f"RESULT: vision OK — reply: {str(content)[:120]}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
