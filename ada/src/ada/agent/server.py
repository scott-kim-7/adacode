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

from ada.agent.classify import classify_request, parse_request_metadata
from ada.agent.config import load_agent_config
from ada.agent.jwt_context import parse_owui_auth_header, reset_request_jwt, set_request_jwt
from ada.agent.llm import make_llm_callable
from ada.agent.llm_registry import (
	build_llm_registry,
	models_config_from_api,
	models_config_to_api,
	profile_from_endpoint,
	resolve_effective_chat_model_id,
	resolve_effective_task_model_id,
)
from ada.agent.models_ops import update_agent_models
from ada.agent.openai_compat import (
	build_chat_completion_response,
	build_tool_chat_completion_response,
	iter_sse_chat_completion,
	run_tool_chat_completion,
	run_unified_chat_completion,
	run_unified_chat_completion_streaming,
)
from ada.agent.tool_policy import is_agent_tool_request
from ada.agent.task_graph import run_task_completion
from ada.agent.stream_sink import StreamSink
from ada.email.api import build_email_router
from ada.email.platform import EmailPlatform
from ada.heartbeat.runner import HeartbeatLifecycle
from ada.openai_models import (
	NoLoadedModelError,
	loaded_model_from_health,
)
from ada.vault import VaultError, VaultSession

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
	registry = build_llm_registry(cfg)
	vault_session: VaultSession | None = None
	if email_platform is not None:
		platform = email_platform
		vault_session = platform.vault_tokens._session
	else:
		try:
			platform = EmailPlatform.from_env()
			vault_session = platform.vault_tokens._session
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
	app.state.agent_cfg = cfg
	app.state.llm_registry = registry
	app.state.vault_session = vault_session
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

	@app.get("/ops/agent/models")
	async def get_agent_models() -> dict[str, Any]:
		return models_config_to_api(app.state.agent_cfg.models)

	@app.put("/ops/agent/models")
	async def put_agent_models(body: dict[str, Any]) -> dict[str, Any]:
		if not isinstance(body, dict):
			raise HTTPException(status_code=400, detail="Expected JSON object")
		try:
			models = models_config_from_api(body, app.state.agent_cfg.models)
			cfg = update_agent_models(models)
		except (TypeError, ValueError) as exc:
			raise HTTPException(status_code=400, detail=str(exc)) from exc
		app.state.agent_cfg = cfg
		app.state.llm_registry = build_llm_registry(cfg)
		return models_config_to_api(cfg.models)

	@app.get("/ops/agent/models/test")
	async def test_agent_models(profile: str = "chat") -> dict[str, Any]:
		cfg = app.state.agent_cfg
		endpoint = cfg.models.task if profile == "task" else cfg.models.chat
		url = f"{endpoint.base_url.rstrip('/')}/models"
		timeout = httpx.Timeout(10.0, connect=5.0)
		try:
			async with httpx.AsyncClient(timeout=timeout) as client:
				resp = await client.get(
					url,
					headers={"Authorization": f"Bearer {endpoint.api_key}"},
				)
				resp.raise_for_status()
				data = resp.json()
		except httpx.HTTPError as exc:
			raise HTTPException(
				status_code=502,
				detail=f"Model endpoint unreachable at {url}: {exc}",
			) from exc
		if not isinstance(data, dict):
			return {"profile": profile, "reachable": True, "models": data}
		return {"profile": profile, "reachable": True, "models": data}

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

		cfg = app.state.agent_cfg
		registry = app.state.llm_registry
		kind = classify_request(request.headers, payload)
		metadata = parse_request_metadata(request.headers, payload)

		try:
			model = resolve_effective_chat_model_id(
				cfg, requested=str(payload.get("model") or "")
			)
			task_model_id = resolve_effective_task_model_id(cfg)
		except NoLoadedModelError as exc:
			raise HTTPException(status_code=400, detail=str(exc)) from exc
		stream_requested = bool(payload.get("stream"))
		force_non_stream = FORCE_NON_STREAM or (os.environ.get("ADA_AGENT_FORCE_NON_STREAM", "0") != "0")
		if stream_requested and force_non_stream:
			stream_requested = False

		tools = payload.get("tools")
		has_tools = isinstance(tools, list) and len(tools) > 0
		agent_tools = has_tools and is_agent_tool_request(metadata, tools)
		if stream_requested and agent_tools:
			stream_requested = False

		jwt_buf = parse_owui_auth_header(request.headers)
		jwt_token = set_request_jwt(jwt_buf)
		vault_session = app.state.vault_session

		try:
			if kind == "task":
				if stream_requested:
					raise HTTPException(status_code=400, detail="Task requests must be non-streaming")
				content = await asyncio.to_thread(
					run_task_completion,
					payload,
					metadata,
					registry["task"],
					cfg,
				)
				response_model = task_model_id
				body = build_chat_completion_response(response_model, content)
			elif has_tools and not agent_tools:
				assistant, finish_reason = await asyncio.to_thread(
					run_tool_chat_completion,
					messages,
					tools,
					registry["tool"],
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
				streaming_llm = make_llm_callable(
					profile_from_endpoint("chat", cfg.models.chat, tool_calling=True),
					stream_context=stream_ctx,
				)

				stream_options = payload.get("stream_options")
				include_usage = (
					isinstance(stream_options, dict)
					and bool(stream_options.get("include_usage"))
				)

				async def sse_body() -> Any:
					async for chunk in iter_sse_chat_completion(
						sink,
						model,
						run_turn=lambda: run_unified_chat_completion_streaming(
							messages,
							metadata,
							streaming_llm,
							registry["tool"],
							sink,
							cfg,
							stream_ctx,
							vault_session,
							openai_tools=tools if agent_tools else None,
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
				result = await asyncio.to_thread(
					run_unified_chat_completion,
					messages,
					metadata,
					registry["chat"],
					registry["tool"],
					cfg,
					vault_session=vault_session,
					openai_tools=tools if agent_tools else None,
				)
				if isinstance(result, tuple):
					assistant, finish_reason = result
					body = build_tool_chat_completion_response(model, assistant, finish_reason)
				else:
					body = build_chat_completion_response(model, result)
		except Exception as exc:
			raise HTTPException(status_code=502, detail=f"Agent failed: {exc}") from exc
		finally:
			reset_request_jwt(jwt_token)

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
