from __future__ import annotations

import ipaddress
import os

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

LOCAL_API_KEY_HEADER = "X-Ada-Local-Key"
TRUSTED_PROXY_HEADER = "X-Ada-WebUI-Proxy"
OAUTH_CALLBACK_SUFFIX = "/oauth/gmail/callback"

_api_key_header = APIKeyHeader(name=LOCAL_API_KEY_HEADER, auto_error=False)

_local_api_key: str | None = None


def configure_local_api_key(key: str | None) -> None:
	global _local_api_key
	_local_api_key = (key or "").strip() or None


def _trusted_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
	raw = os.environ.get(
		"ADA_TRUSTED_PROXY_CIDRS",
		"127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
	)
	nets: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
	for part in raw.split(","):
		part = part.strip()
		if part:
			nets.append(ipaddress.ip_network(part, strict=False))
	return nets


def _client_ip(request: Request) -> str | None:
	if request.client is None:
		return None
	return request.client.host


def _is_oauth_callback(request: Request) -> bool:
	return request.url.path.rstrip("/").endswith(OAUTH_CALLBACK_SUFFIX)


def _is_trusted_proxy(request: Request) -> bool:
	if request.headers.get(TRUSTED_PROXY_HEADER) != "1":
		return False
	host = _client_ip(request)
	if not host:
		return False
	try:
		ip = ipaddress.ip_address(host)
	except ValueError:
		return False
	return any(ip in net for net in _trusted_networks())


def require_email_auth(
	request: Request,
	api_key: str | None = Security(_api_key_header),
) -> None:
	if _is_oauth_callback(request):
		return
	if _is_trusted_proxy(request):
		return
	expected = _local_api_key
	if not expected:
		raise HTTPException(status_code=503, detail="Local API key is not configured (vault unlock required)")
	if not api_key or api_key != expected:
		raise HTTPException(status_code=401, detail="Invalid or missing local API key")
