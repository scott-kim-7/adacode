#!/usr/bin/env python3
"""Simulate Open WebUI aiohttp streaming against MLX / proxy."""

from __future__ import annotations

import asyncio
import json
import sys

import aiohttp


async def test(url: str, label: str) -> tuple[str, str, str | None]:
	payload = {
		"model": "mlx-community/Qwen3-VL-32B-Instruct-8bit",
		"messages": [{"role": "user", "content": "안녕"}],
		"max_tokens": 40,
		"stream": True,
		"stream_options": {"include_usage": True},
	}
	texts: list[str] = []
	error: str | None = None
	try:
		async with aiohttp.ClientSession() as session:
			async with session.post(
				url,
				json=payload,
				headers={"Authorization": "Bearer local"},
				timeout=aiohttp.ClientTimeout(total=120),
			) as resp:
				print(f"{label} status={resp.status} ctype={resp.headers.get('Content-Type')}")
				buffer = ""
				async for raw in resp.content:
					buffer += raw.decode("utf-8", errors="replace")
					while "\n" in buffer:
						line, buffer = buffer.split("\n", 1)
						line = line.strip()
						if not line.startswith("data:"):
							continue
						payload_txt = line[5:].strip()
						if payload_txt == "[DONE]":
							return label, "".join(texts), error
						try:
							data = json.loads(payload_txt)
							delta = data.get("choices", [{}])[0].get("delta", {})
							content = delta.get("content")
							if content:
								texts.append(content)
							reasoning = delta.get("reasoning")
							if reasoning is not None:
								print(f"{label} reasoning={reasoning!r}")
						except json.JSONDecodeError as exc:
							print(f"{label} parse_err={exc} line={payload_txt[:120]!r}")
	except Exception as exc:  # noqa: BLE001
		error = repr(exc)
	return label, "".join(texts), error


async def main() -> int:
	targets = [
		("http://host.docker.internal:8081/v1/chat/completions", "proxy8081"),
		("http://host.docker.internal:8080/v1/chat/completions", "mlx8080"),
	]
	for url, label in targets:
		name, text, err = await test(url, label)
		print(f"RESULT {name} err={err} text={text[:120]!r}")
	return 0


if __name__ == "__main__":
	raise SystemExit(asyncio.run(main()))
