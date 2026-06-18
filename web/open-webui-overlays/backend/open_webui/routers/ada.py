import logging
import os

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from open_webui.utils.auth import get_admin_user

router = APIRouter()
log = logging.getLogger(__name__)

AGENT_BASE = os.environ.get("ADA_AGENT_BASE_URL", "http://host.docker.internal:8082").rstrip("/")
PROXY_HEADER = "X-Ada-WebUI-Proxy"
PROXY_HEADER_VALUE = "1"


def _agent_url(path: str, query: str) -> str:
	base = f"{AGENT_BASE}/{path.lstrip('/')}"
	if query:
		return f"{base}?{query}"
	return base


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
