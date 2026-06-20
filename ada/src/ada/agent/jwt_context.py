from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar, Token

from ada.vault import secure_zero

_jwt_buf: ContextVar[bytearray | None] = ContextVar("ada_owui_jwt", default=None)


def parse_owui_auth_header(headers: Mapping[str, str]) -> bytearray | None:
	raw = headers.get("x-ada-owui-authorization") or headers.get("X-Ada-Owui-Authorization")
	if not raw:
		return None
	text = raw.strip()
	if not text:
		return None
	return bytearray(text.encode("utf-8"))


def set_request_jwt(jwt: bytearray | None) -> Token:
	return _jwt_buf.set(jwt)


def get_request_jwt() -> bytearray | None:
	return _jwt_buf.get()


def reset_request_jwt(token: Token) -> None:
	jwt = _jwt_buf.get()
	if jwt is not None:
		secure_zero(jwt)
	_jwt_buf.reset(token)


def jwt_authorization_header(jwt: bytearray | None) -> dict[str, str]:
	if jwt is None:
		return {}
	return {"Authorization": jwt.decode("utf-8")}
