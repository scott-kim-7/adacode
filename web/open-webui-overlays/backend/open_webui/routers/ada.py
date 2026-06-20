import json
import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from open_webui.retrieval.utils import get_sources_from_items
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.misc import get_last_user_message

router = APIRouter()
log = logging.getLogger(__name__)

AGENT_BASE = os.environ.get("ADA_AGENT_BASE_URL", "http://host.docker.internal:9082").rstrip("/")
PROXY_HEADER = "X-Ada-WebUI-Proxy"
PROXY_HEADER_VALUE = "1"


def _agent_url(path: str, query: str) -> str:
	base = f"{AGENT_BASE}/{path.lstrip('/')}"
	if query:
		return f"{base}?{query}"
	return base


class RetrievalSourcesForm(BaseModel):
	items: list[dict] = Field(default_factory=list)
	queries: list[str] = Field(default_factory=list)
	full_context: bool = False


class ToolExecuteForm(BaseModel):
	name: str
	arguments: dict = Field(default_factory=dict)
	tool_ids: list[str] = Field(default_factory=list)


async def _resolve_tools_dict(request: Request, tool_ids: list[str], user) -> dict:
	from open_webui.utils.tools import get_tools

	extra_params = {
		"__request__": request,
		"__user__": user.model_dump() if hasattr(user, "model_dump") else {},
	}
	tools_dict = await get_tools(request, tool_ids, user, extra_params)

	mcp_clients: dict = {}
	for tool_id in tool_ids:
		if not str(tool_id).startswith("server:mcp:"):
			continue
		try:
			from open_webui.utils.mcp.client import MCPClient

			server_id = str(tool_id)[len("server:mcp:") :]
			mcp_server_connection = None
			for server_connection in request.app.state.config.TOOL_SERVER_CONNECTIONS:
				if (
					server_connection.get("type", "") == "mcp"
					and server_connection.get("info", {}).get("id") == server_id
				):
					mcp_server_connection = server_connection
					break
			if not mcp_server_connection:
				log.error("MCP server with id %s not found", server_id)
				continue

			headers: dict[str, str] = {}
			auth_type = mcp_server_connection.get("auth_type", "")
			if auth_type == "bearer":
				headers["Authorization"] = f"Bearer {mcp_server_connection.get('key', '')}"
			elif auth_type == "session":
				headers["Authorization"] = f"Bearer {request.state.token.credentials}"

			connection_headers = mcp_server_connection.get("headers")
			if isinstance(connection_headers, dict):
				headers.update(connection_headers)

			client = MCPClient()
			await client.connect(
				url=mcp_server_connection.get("url", ""),
				headers=headers or None,
			)
			mcp_clients[server_id] = client

			tool_specs = await client.list_tool_specs() or []
			for tool_spec in tool_specs:
				function_name = f"{server_id}_{tool_spec['name']}"

				def make_tool_function(mcp_client, fn_name):
					async def tool_function(**kwargs):
						return await mcp_client.call_tool(fn_name, function_args=kwargs)

					return tool_function

				tools_dict[function_name] = {
					"type": "mcp",
					"callable": make_tool_function(client, tool_spec["name"]),
					"spec": {
						"name": function_name,
						"description": tool_spec.get("description", ""),
						"parameters": tool_spec.get("parameters", {}),
					},
				}
		except Exception as exc:
			log.exception("ada tools/execute MCP resolve failed for %s: %s", tool_id, exc)

	return tools_dict


def _format_tool_result(result) -> str:
	if isinstance(result, (dict, list)):
		return json.dumps(result, ensure_ascii=False)
	return str(result)


@router.post("/tools/execute")
async def ada_tool_execute(
	request: Request,
	body: ToolExecuteForm,
	user=Depends(get_verified_user),
):
	if not body.tool_ids:
		raise HTTPException(status_code=400, detail="tool_ids must be a non-empty list")
	if not (body.name or "").strip():
		raise HTTPException(status_code=400, detail="name is required")

	from open_webui.utils.tools import get_updated_tool_function

	try:
		tools_dict = await _resolve_tools_dict(request, body.tool_ids, user)
	except Exception as exc:
		log.exception("ada tools/execute get_tools failed: %s", exc)
		raise HTTPException(status_code=500, detail="tool resolution failed") from exc

	tool = tools_dict.get(body.name)
	if not tool:
		raise HTTPException(status_code=404, detail=f"unknown tool: {body.name}")

	spec = tool.get("spec", {})
	allowed = spec.get("parameters", {}).get("properties", {}).keys()
	filtered = {k: v for k, v in body.arguments.items() if k in allowed}

	try:
		if tool.get("type") == "mcp":
			result = await tool["callable"](**filtered)
		elif tool.get("direct"):
			raise HTTPException(status_code=400, detail="client-side direct tools are not supported")
		else:
			tool_function = get_updated_tool_function(
				function=tool["callable"],
				extra_params={},
			)
			result = await tool_function(**filtered)
	except HTTPException:
		raise
	except Exception as exc:
		log.exception("ada tools/execute run failed: %s", exc)
		return {"content": str(exc)}

	return {"content": _format_tool_result(result)}


@router.post("/retrieval/sources")
async def ada_retrieval_sources(
	request: Request,
	body: RetrievalSourcesForm,
	user=Depends(get_verified_user),
):
	if not body.queries or not any(str(q).strip() for q in body.queries):
		raise HTTPException(status_code=400, detail="queries must be a non-empty list")

	try:
		sources = await get_sources_from_items(
			request=request,
			items=body.items,
			queries=body.queries,
			embedding_function=lambda query, prefix: request.app.state.EMBEDDING_FUNCTION(
				query, prefix=prefix, user=user
			),
			k=request.app.state.config.TOP_K,
			reranking_function=(
				(
					lambda query, documents: request.app.state.RERANKING_FUNCTION(
						query, documents, user=user
					)
				)
				if request.app.state.RERANKING_FUNCTION
				else None
			),
			k_reranker=request.app.state.config.TOP_K_RERANKER,
			r=request.app.state.config.RELEVANCE_THRESHOLD,
			hybrid_bm25_weight=request.app.state.config.HYBRID_BM25_WEIGHT,
			hybrid_search=request.app.state.config.ENABLE_RAG_HYBRID_SEARCH,
			full_context=body.full_context or request.app.state.config.RAG_FULL_CONTEXT,
			user=user,
		)
	except Exception as exc:
		log.exception("ada retrieval/sources failed: %s", exc)
		raise HTTPException(status_code=500, detail="retrieval failed") from exc

	return {"sources": sources or []}


@router.api_route("/agent/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_ada_agent(
	path: str,
	request: Request,
	_user=Depends(get_admin_user),
):
	url = _agent_url(path, request.url.query)
	body = await request.body()
	headers: dict[str, str] = {PROXY_HEADER: PROXY_HEADER_VALUE}
	content_type = request.headers.get("content-type")
	if content_type:
		headers["Content-Type"] = content_type
	try:
		async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
			upstream = await client.request(
				request.method,
				url,
				content=body if body else None,
				headers=headers,
			)
	except httpx.HTTPError as exc:
		log.warning("Ada agent proxy failed: %s", exc)
		return JSONResponse(
			status_code=502,
			content={"detail": f"Ada agent unreachable at {AGENT_BASE}: {exc}"},
		)
	media_type = upstream.headers.get("content-type", "application/json")
	response_headers: dict[str, str] = {}
	content_disposition = upstream.headers.get("content-disposition")
	if content_disposition:
		response_headers["Content-Disposition"] = content_disposition
	return Response(
		content=upstream.content,
		status_code=upstream.status_code,
		media_type=media_type,
		headers=response_headers,
	)
