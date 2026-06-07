from __future__ import annotations

from collections.abc import Callable

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from ada.agent.config import AgentConfig, load_agent_config
from ada.agent.graph import run_user_turn


class AgentSession:
	"""In-memory chat session backed by the LangGraph MainGraph."""

	def __init__(
		self,
		llm_callable: Callable[[list[BaseMessage]], str],
		config: AgentConfig | None = None,
	) -> None:
		self._llm_callable = llm_callable
		self._config = config or load_agent_config()
		self._history: list[BaseMessage] = []

	@property
	def history(self) -> list[BaseMessage]:
		return list(self._history)

	def reset(self) -> None:
		self._history.clear()

	def send(self, user_text: str) -> str:
		user_text = user_text.strip()
		if not user_text:
			return ""
		assistant_text, self._history = run_user_turn(
			user_text,
			self._history,
			self._llm_callable,
			config=self._config,
		)
		return assistant_text

	def load_history(self, pairs: list[tuple[str, str]]) -> None:
		"""Restore session from Gradio-style (user, assistant) tuples."""
		self._history.clear()
		for user_msg, assistant_msg in pairs:
			if user_msg:
				self._history.append(HumanMessage(content=user_msg))
			if assistant_msg:
				self._history.append(AIMessage(content=assistant_msg))
