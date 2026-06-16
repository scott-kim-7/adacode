from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from ada.agent.config import load_agent_config
from ada.agent.llm import load_profile_from_env, make_llm_callable, make_tool_llm_callable
from ada.agent.openai_compat import (
	build_chat_completion_response,
	build_tool_chat_completion_response,
	iter_sse_chat_completion,
	run_chat_completion,
	run_chat_completion_streaming,
	run_tool_chat_completion,
)
from ada.agent.stream_sink import StreamSink
from ada.openai_models import (
	NoLoadedModelError,
	effective_model_id,
	loaded_model_from_health,
	resolve_model_id,
)

HOST = os.environ.get("ADA_AGENT_HOST", "127.0.0.1")
PORT = int(os.environ.get("ADA_AGENT_PORT", "8082"))
MLX_UPSTREAM = os.environ.get("MLX_UPSTREAM", "http://127.0.0.1:8080").rstrip("/")
FORCE_NON_STREAM = os.environ.get("ADA_AGENT_FORCE_NON_STREAM", "0") != "0"


def create_app() -> FastAPI:
	cfg = load_agent_config()
	profile = load_profile_from_env()
	llm_callable = make_llm_callable(profile)
	tool_llm_callable = make_tool_llm_callable(profile)

	app = FastAPI(title="Ada LangGraph Agent", version="0.1.0")

	@app.get("/health")
	async def health() -> dict[str, str]:
		payload: dict[str, str] = {"status": "ok", "endpoint": MLX_UPSTREAM}
		try:
			timeout = httpx.Timeout(5.0, connect=2.0)
			async with httpx.AsyncClient(timeout=timeout) as client:
				resp = await client.get(f"{MLX_UPSTREAM}/health")
				resp.raise_for_status()
				upstream = resp.json()
				if isinstance(upstream, dict) and upstream.get("loaded_model"):
					payload["loaded_model"] = str(upstream["loaded_model"])
		except httpx.HTTPError:
			pass
		return payload

	@app.get("/v1/models")
	async def list_models() -> dict[str, Any]:
		timeout = httpx.Timeout(30.0, connect=10.0)
		try:
			async with httpx.AsyncClient(timeout=timeout) as client:
				resp = await client.get(
					f"{MLX_UPSTREAM}/v1/models",
					headers={"Authorization": "Bearer local"},
				)
				resp.raise_for_status()
				payload = resp.json()
		except httpx.HTTPError as exc:
			raise HTTPException(
				status_code=503,
				detail=f"LLM server unreachable at {MLX_UPSTREAM}: {exc}",
			) from exc
		if not isinstance(payload, dict):
			return payload
		items = payload.get("data")
		if not isinstance(items, list) or not items:
			return payload
		ids = [str(item["id"]) for item in items if isinstance(item, dict) and item.get("id")]
		if not ids:
			return payload
		by_id = {str(item["id"]): item for item in items if isinstance(item, dict) and item.get("id")}
		preferred = loaded_model_from_health(f"{MLX_UPSTREAM}/v1", api_key="local")
		if preferred:
			if preferred in by_id:
				return {"object": "list", "data": [by_id[preferred]]}
			return {
				"object": "list",
				"data": [{"id": preferred, "object": "model", "created": int(time.time())}],
			}
		return payload

	@app.post("/v1/chat/completions")
	async def chat_completions(request: Request) -> Response:
		try:
			payload = await request.json()
		except Exception as exc:
			raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

		if not isinstance(payload, dict):
			raise HTTPException(status_code=400, detail="Expected JSON object")

		messages = payload.get("messages")
		if not isinstance(messages, list) or not messages:
			raise HTTPException(status_code=400, detail="messages must be a non-empty array")

		try:
			model = effective_model_id(
				f"{MLX_UPSTREAM}/v1",
				str(payload.get("model") or ""),
				api_key="local",
			)
		except NoLoadedModelError as exc:
			raise HTTPException(status_code=400, detail=str(exc)) from exc
		stream_requested = bool(payload.get("stream"))
		if stream_requested and FORCE_NON_STREAM:
			stream_requested = False

		tools = payload.get("tools")
		has_tools = isinstance(tools, list) and len(tools) > 0

		try:
			if has_tools:
				assistant, finish_reason = await asyncio.to_thread(
					run_tool_chat_completion,
					messages,
					tools,
					tool_llm_callable,
					cfg,
					tool_choice=payload.get("tool_choice"),
				)
				body = build_tool_chat_completion_response(model, assistant, finish_reason)
			elif stream_requested:
				from ada.agent.stream_sink import StreamContext

				sink = StreamSink()
				stream_ctx = StreamContext(
					sink=sink,
					inline_thinking=cfg.stream.inline_thinking,
					expose_graph_trace=cfg.stream.expose_graph_trace,
					trace_direct_route=cfg.stream.trace_direct_route,
				)
				streaming_llm = make_llm_callable(profile, stream_context=stream_ctx)

				stream_options = payload.get("stream_options")
				include_usage = (
					isinstance(stream_options, dict)
					and bool(stream_options.get("include_usage"))
				)

				async def sse_body() -> Any:
					async for chunk in iter_sse_chat_completion(
						sink,
						model,
						run_turn=lambda: run_chat_completion_streaming(
							messages,
							streaming_llm,
							sink,
							cfg,
							stream_context=stream_ctx,
						),
						include_usage=include_usage,
					):
						yield chunk

				return StreamingResponse(
					sse_body(),
					media_type="text/event-stream",
					headers={
						"Cache-Control": "no-cache",
						"Connection": "keep-alive",
						"X-Accel-Buffering": "no",
					},
				)
			else:
				content = await asyncio.to_thread(
					run_chat_completion,
					messages,
					llm_callable,
					cfg,
				)
				body = build_chat_completion_response(model, content)
		except Exception as exc:
			raise HTTPException(status_code=502, detail=f"Agent failed: {exc}") from exc

		return JSONResponse(content=body)

	return app


def main() -> int:
	import sys

	import uvicorn

	from ada.eval.harness.stack_check import is_mlx_upstream_reachable

	if not is_mlx_upstream_reachable():
		upstream = os.environ.get("MLX_UPSTREAM", "http://127.0.0.1:8080").rstrip("/")
		print(
			f"WARNING: LLM server is not reachable at {upstream} — agent will start; "
			"chat works once mlx_vlm.server is up.",
			file=sys.stderr,
			flush=True,
		)

	app = create_app()
	print(f"Ada LangGraph agent server", flush=True)
	print(f"  listen: http://{HOST}:{PORT}/v1", flush=True)
	print(f"  mlx:    {MLX_UPSTREAM}", flush=True)
	print(f"  models: GET {MLX_UPSTREAM}/v1/models (OpenAPI)", flush=True)
	print(
		f"  mode:   {'buffered JSON (set ADA_AGENT_FORCE_NON_STREAM=1)' if FORCE_NON_STREAM else 'SSE stream (plan thinking + respond)'}",
		flush=True,
	)
	uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
	return 0
