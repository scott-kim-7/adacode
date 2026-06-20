from __future__ import annotations

import logging
import os
from typing import Any, Protocol

log = logging.getLogger(__name__)


class RetrievalBackend(Protocol):
	async def fetch_sources(
		self,
		items: list[dict[str, Any]],
		queries: list[str],
		*,
		full_context: bool = False,
		jwt: bytearray | None,
	) -> list[dict[str, Any]]: ...


def use_agent_backends() -> bool:
	return os.environ.get("ADA_USE_AGENT_BACKENDS", "").strip().lower() in (
		"1",
		"true",
		"yes",
	)


def get_retrieval_backend():
	if use_agent_backends():
		from ada.retrieve.agent_backend import AgentRetrievalBackend

		return AgentRetrievalBackend()
	from ada.retrieve.owui_backend import OwuiRetrievalBackend

	return OwuiRetrievalBackend()
