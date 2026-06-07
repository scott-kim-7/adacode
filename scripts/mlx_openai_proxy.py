#!/usr/bin/env python3
"""OpenAI-compatible proxy: mlx_vlm → Open WebUI.

mlx-vlm emits ``reasoning: null`` on every stream delta. Open WebUI 0.8.x also fails
to persist streamed assistant text (content/output stay empty) even when MLX returns
tokens. This proxy strips reasoning fields and, by default, converts streaming chat
requests into buffered JSON completions that Open WebUI handles correctly.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse

UPSTREAM = os.environ.get("MLX_UPSTREAM", "http://127.0.0.1:8080").rstrip("/")
HOST = os.environ.get("ADA_MLX_PROXY_HOST", "127.0.0.1")
PORT = int(os.environ.get("ADA_MLX_PROXY_PORT", "8081"))
FORCE_NON_STREAM = os.environ.get("ADA_MLX_PROXY_FORCE_NON_STREAM", "1") != "0"

REASONING_KEYS = frozenset({"reasoning", "reasoning_content", "thinking"})


def _clean_delta(delta: dict[str, Any], *, include_role: bool) -> dict[str, Any]:
	clean: dict[str, Any] = {}
	if include_role and delta.get("role"):
		clean["role"] = delta["role"]
	content = delta.get("content")
	if content is not None and content != "":
		clean["content"] = content
	for key, value in delta.items():
		if key in REASONING_KEYS or value is None:
			continue
		if key in {"role", "content"}:
			continue
		clean[key] = value
	return clean


def _strip_reasoning(data: dict[str, Any]) -> dict[str, Any]:
	for choice in data.get("choices") or []:
		if not isinstance(choice, dict):
			continue
		delta = choice.get("delta")
		if isinstance(delta, dict):
			include_role = bool(delta.get("role")) and not delta.get("content")
			choice["delta"] = _clean_delta(delta, include_role=include_role)
		message = choice.get("message")
		if isinstance(message, dict):
			for key in REASONING_KEYS:
				message.pop(key, None)
	return data


def _forward_headers(request: Request) -> dict[str, str]:
	skip = {"host", "content-length", "transfer-encoding", "connection"}
	return {key: value for key, value in request.headers.items() if key.lower() not in skip}


app = FastAPI(title="Ada MLX OpenAI Proxy")


async def _stream_chat(
	method: str,
	url: str,
	body: bytes,
	headers: dict[str, str],
) -> AsyncIterator[str]:
	timeout = httpx.Timeout(600.0, connect=30.0)
	saw_content = False
	async with httpx.AsyncClient(timeout=timeout) as client:
		async with client.stream(method, url, content=body, headers=headers) as upstream:
			async for line in upstream.aiter_lines():
				if not line:
					continue
				if not line.startswith("data:"):
					yield f"{line}\n"
					continue
				payload = line[5:].strip()
				if payload == "[DONE]":
					yield "data: [DONE]\n\n"
					return
				try:
					data = _strip_reasoning(json.loads(payload))
					for choice in data.get("choices") or []:
						delta = choice.get("delta")
						if isinstance(delta, dict) and delta.get("content"):
							saw_content = True
						elif saw_content and isinstance(delta, dict):
							delta.pop("role", None)
					yield f"data: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"
				except json.JSONDecodeError:
					yield f"{line}\n\n"


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy(full_path: str, request: Request) -> Response:
	path = full_path.lstrip("/")
	url = f"{UPSTREAM}/{path}" if path else UPSTREAM
	body = await request.body()
	headers = _forward_headers(request)

	stream = False
	payload_obj: dict[str, Any] | None = None
	if body and path.endswith("chat/completions"):
		try:
			payload_obj = json.loads(body)
			stream = bool(payload_obj.get("stream"))
		except json.JSONDecodeError:
			payload_obj = None

	# Open WebUI 0.8.x loses streamed assistant text; buffered JSON works reliably.
	if stream and FORCE_NON_STREAM and payload_obj is not None:
		payload_obj["stream"] = False
		body = json.dumps(payload_obj).encode()
		stream = False

	if stream:
		return StreamingResponse(
			_stream_chat(request.method, url, body, headers),
			media_type="text/event-stream",
			headers={
				"Cache-Control": "no-cache",
				"Connection": "keep-alive",
				"X-Accel-Buffering": "no",
			},
		)

	timeout = httpx.Timeout(600.0, connect=30.0)
	async with httpx.AsyncClient(timeout=timeout) as client:
		upstream = await client.request(request.method, url, content=body or None, headers=headers)
		content = upstream.content
		media_type = upstream.headers.get("content-type", "application/json")
		if "application/json" in media_type and content and path.endswith("chat/completions"):
			try:
				payload = _strip_reasoning(json.loads(content))
				content = json.dumps(payload, ensure_ascii=False).encode()
			except json.JSONDecodeError:
				pass
		return Response(content=content, status_code=upstream.status_code, media_type=media_type)


def main() -> int:
	print(f"MLX OpenAI proxy → {UPSTREAM}", flush=True)
	print(f"  listen: http://{HOST}:{PORT}/v1", flush=True)
	print(
		f"  mode: {'buffered JSON (Open WebUI compat)' if FORCE_NON_STREAM else 'pass-through stream'}",
		flush=True,
	)
	uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
