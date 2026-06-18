from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
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
from ada.email.api import build_email_router
from ada.email.platform import EmailPlatform
from ada.heartbeat.runner import HeartbeatLifecycle
from ada.openai_models import (
	NoLoadedModelError,
	effective_model_id,
	loaded_model_from_health,
	resolve_model_id,
)
from ada.vault import VaultError

from ada.ports import agent_host, agent_port, mlx_upstream_url

HOST = agent_host()
PORT = agent_port()
MLX_UPSTREAM = mlx_upstream_url()
FORCE_NON_STREAM = False
CORS_ORIGINS = [
	origin.strip()
	for origin in os.environ.get(
		"ADA_CORS_ORIGINS",
		"http://localhost:3000,http://127.0.0.1:3000",
	).split(",")
	if origin.strip()
]


def create_app(email_platform: EmailPlatform | None = None) -> FastAPI:
	cfg = load_agent_config()
	profile = load_profile_from_env()
	llm_callable = make_llm_callable(profile)
	tool_llm_callable = make_tool_llm_callable(profile)
	if email_platform is not None:
		platform = email_platform
	else:
		try:
			platform = EmailPlatform.from_env()
		except VaultError:
			# Test/runtime fallback: keep email features available without forcing vault unlock.
			platform = EmailPlatform.from_session(None)
	heartbeat_cm = HeartbeatLifecycle(platform.heartbeat)

	@asynccontextmanager
	async def lifespan(app: FastAPI):
		heartbeat_cm.__enter__()
		yield
		heartbeat_cm.__exit__(None, None, None)

	app = FastAPI(title="Ada LangGraph Agent", version="0.1.0", lifespan=lifespan)
	if CORS_ORIGINS:
		app.add_middleware(
			CORSMiddleware,
			allow_origins=CORS_ORIGINS,
			allow_credentials=True,
			allow_methods=["*"],
			allow_headers=["*"],
		)
	app.include_router(build_email_router(platform))

	@app.get("/health")
	async def health() -> dict[str, str]:
		payload: dict[str, str] = {"status": "ok", "endpoint": MLX_UPSTREAM}
		readiness = platform.vault_tokens.oauth_readiness()
		if readiness.ready:
			payload["email_vault"] = "ready"
		elif not readiness.vault_file:
			payload["email_vault"] = "missing"
		elif not readiness.vault_unlocked:
			payload["email_vault"] = "unlock_required"
		elif not readiness.gmail_client:
			payload["email_vault"] = "client_credentials_required"
		else:
			payload["email_vault"] = "locked"
		try:
			timeout = httpx.Timeout(5.0, connect=2.0)
			async with httpx.AsyncClient(timeout=timeout) as client:
				resp = await client.get(f"{MLX_UPSTREAM}/health")
				resp.raise_for_status()
				upstream = resp.json()
				if isinstance(upstream, dict):
					from ada.openai_models import parse_health_model

					loaded = parse_health_model(upstream)
					if loaded:
						payload["loaded_model"] = loaded
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
		force_non_stream = FORCE_NON_STREAM or (os.environ.get("ADA_AGENT_FORCE_NON_STREAM", "0") != "0")
		if stream_requested and force_non_stream:
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
		upstream = mlx_upstream_url()
		print(
			f"WARNING: LLM server is not reachable at {upstream} — agent will start; "
			"chat works once mlx_vlm.server is up.",
			file=sys.stderr,
			flush=True,
		)

	from ada.email.auth import configure_local_api_key
	from ada.vault_secrets import scrub_forbidden_secret_env
	from ada.vault_unlock import bootstrap_vault_session, ensure_local_api_key

	scrub_forbidden_secret_env()
	session = bootstrap_vault_session()
	if session is not None:
		configure_local_api_key(ensure_local_api_key(session))
	else:
		configure_local_api_key(None)

	platform = EmailPlatform.from_session(session)
	app = create_app(email_platform=platform)
	print(f"Ada LangGraph agent server", flush=True)
	print(f"  listen: http://{HOST}:{PORT}/v1", flush=True)
	print(f"  mlx:    {MLX_UPSTREAM}", flush=True)
	print(f"  models: GET {MLX_UPSTREAM}/v1/models (OpenAPI)", flush=True)
	force_non_stream = FORCE_NON_STREAM or (os.environ.get("ADA_AGENT_FORCE_NON_STREAM", "0") != "0")
	print(
		f"  mode:   {'buffered JSON (set ADA_AGENT_FORCE_NON_STREAM=1)' if force_non_stream else 'SSE stream (plan thinking + respond)'}",
		flush=True,
	)
	uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
	return 0
