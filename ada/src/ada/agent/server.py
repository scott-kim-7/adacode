from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from ada.agent.config import load_agent_config
from ada.agent.llm import load_profile_from_env, make_llm_callable
from ada.agent.openai_compat import build_chat_completion_response, run_chat_completion

HOST = os.environ.get("ADA_AGENT_HOST", "127.0.0.1")
PORT = int(os.environ.get("ADA_AGENT_PORT", "8082"))
MLX_UPSTREAM = os.environ.get("MLX_UPSTREAM", "http://127.0.0.1:8080").rstrip("/")
FORCE_NON_STREAM = os.environ.get("ADA_AGENT_FORCE_NON_STREAM", "1") != "0"


def create_app() -> FastAPI:
	cfg = load_agent_config()
	profile = load_profile_from_env()
	llm_callable = make_llm_callable(profile)
	model_id = profile.model

	app = FastAPI(title="Ada LangGraph Agent", version="0.1.0")

	@app.get("/health")
	async def health() -> dict[str, str]:
		return {"status": "ok", "model": model_id}

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
				return resp.json()
		except httpx.HTTPError:
			return {
				"object": "list",
				"data": [{"id": model_id, "object": "model", "owned_by": "ada"}],
			}

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

		model = str(payload.get("model") or model_id)
		stream_requested = bool(payload.get("stream"))
		if stream_requested and FORCE_NON_STREAM:
			stream_requested = False

		try:
			content = await asyncio.to_thread(
				run_chat_completion,
				messages,
				llm_callable,
				cfg,
			)
		except Exception as exc:
			raise HTTPException(status_code=502, detail=f"Agent failed: {exc}") from exc

		body = build_chat_completion_response(model, content)
		return JSONResponse(content=body)

	return app


def main() -> int:
	import uvicorn

	app = create_app()
	profile = load_profile_from_env()
	print(f"Ada LangGraph agent server", flush=True)
	print(f"  listen: http://{HOST}:{PORT}/v1", flush=True)
	print(f"  mlx:    {MLX_UPSTREAM}", flush=True)
	print(f"  model:  {profile.model}", flush=True)
	print(
		f"  mode:   {'buffered JSON (Open WebUI compat)' if FORCE_NON_STREAM else 'JSON only'}",
		flush=True,
	)
	uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
	return 0
