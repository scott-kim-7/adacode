#!/usr/bin/env python3
"""Simulate Open WebUI aiohttp streaming against MLX / Ada Agent."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import aiohttp

PLAN_PROMPT = (
	"이 시스템의 아키텍처를 단계별로 계획해 주세요. "
	"설계 관점에서 모듈, 데이터 흐름, 배포를 bullet로 정리하세요."
)


async def test(
	url: str,
	label: str,
	*,
	user_content: str,
) -> tuple[str, str, str, str | None]:
	import urllib.request

	models_url = url.rsplit("/chat/completions", 1)[0] + "/models"
	with urllib.request.urlopen(
		urllib.request.Request(models_url, headers={"Authorization": "Bearer local"}),
		timeout=30,
	) as resp:
		data = json.loads(resp.read().decode("utf-8"))
	model = data["data"][0]["id"]
	payload = {
		"model": model,
		"messages": [{"role": "user", "content": user_content}],
		"max_tokens": 80,
		"stream": True,
		"stream_options": {"include_usage": True},
	}
	content_parts: list[str] = []
	reasoning_parts: list[str] = []
	error: str | None = None
	try:
		async with aiohttp.ClientSession() as session:
			async with session.post(
				url,
				json=payload,
				headers={"Authorization": "Bearer local"},
				timeout=aiohttp.ClientTimeout(total=180),
			) as resp:
				print(f"{label} status={resp.status} ctype={resp.headers.get('Content-Type')}")
				if resp.status != 200:
					body = await resp.text()
					return label, "", "", f"HTTP {resp.status}: {body[:200]}"
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
							return (
								label,
								"".join(content_parts),
								"".join(reasoning_parts),
								error,
							)
						try:
							data = json.loads(payload_txt)
							delta = data.get("choices", [{}])[0].get("delta", {})
							content = delta.get("content")
							if content:
								content_parts.append(content)
							reasoning = delta.get("reasoning_content") or delta.get("reasoning")
							if reasoning:
								reasoning_parts.append(str(reasoning))
						except json.JSONDecodeError as exc:
							print(f"{label} parse_err={exc} line={payload_txt[:120]!r}")
	except Exception as exc:  # noqa: BLE001
		error = repr(exc)
	return label, "".join(content_parts), "".join(reasoning_parts), error


def default_targets() -> list[tuple[str, str]]:
	agent_port = os.environ.get("ADA_AGENT_PORT", "9082")
	mlx_port = os.environ.get("ADA_MLX_PORT", "8089")
	host = os.environ.get("ADA_MLX_HOST", "127.0.0.1")
	return [
		(f"http://{host}:{agent_port}/v1/chat/completions", f"agent{agent_port}"),
		(f"http://{host}:{mlx_port}/v1/chat/completions", f"mlx{mlx_port}"),
	]


async def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"--require-sse",
		action="store_true",
		help="Exit 1 unless at least one target returns non-empty streamed text",
	)
	parser.add_argument(
		"--agent-only",
		action="store_true",
		help="Only test Ada Agent (:9082 by default)",
	)
	parser.add_argument(
		"--plan-smoke",
		action="store_true",
		help="Use a long plan-route prompt (Agent LangGraph plan + respond)",
	)
	args = parser.parse_args()

	user_content = PLAN_PROMPT if args.plan_smoke else "안녕"
	targets = default_targets()
	if args.agent_only:
		targets = [targets[0]]

	ok = False
	for url, label in targets:
		name, content, reasoning, err = await test(url, label, user_content=user_content)
		print(
			f"RESULT {name} err={err} content={content[:120]!r} "
			f"reasoning={reasoning[:80]!r}"
		)
		if args.plan_smoke and label.startswith("agent"):
			if err:
				continue
			if "<think>" not in content:
				print(f"{name}: expected inline thinking tags in content", file=sys.stderr)
				continue
			if "[route] plan" not in content:
				print(f"{name}: expected [route] plan trace in content", file=sys.stderr)
				continue
		if (content or reasoning) and not err:
			ok = True

	if args.require_sse and not ok:
		print("No target produced streamed assistant text.", file=sys.stderr)
		return 1
	return 0


if __name__ == "__main__":
	raise SystemExit(asyncio.run(main()))
