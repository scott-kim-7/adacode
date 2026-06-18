from __future__ import annotations

from dataclasses import dataclass, field

from ada.llm import ChatMessage, LLMClient, make_client
from ada.registry import ModelRegistry, get_profile
from ada.vault import VaultSession


@dataclass
class TriChatSession:
	"""Three-party chat: user, local MLX, external API LLM."""

	registry: ModelRegistry
	local_client: LLMClient
	external_client: LLMClient | None = None
	history: list[ChatMessage] = field(default_factory=list)
	local_label: str = "Local"
	external_label: str = "External"
	_vault_session: VaultSession | None = field(default=None, repr=False)

	@classmethod
	def from_registry(
		cls,
		registry: ModelRegistry,
		vault_session: VaultSession | None = None,
	) -> TriChatSession:
		local_name = registry.tri_chat.local_profile
		external_name = registry.tri_chat.external_profile
		local = get_profile(registry, local_name)
		external = get_profile(registry, external_name)
		return cls(
			registry=registry,
			local_client=make_client(local, vault_session),
			external_client=None,
			local_label=local.label,
			external_label=external.label,
			_vault_session=vault_session,
		)

	def _external_client(self) -> LLMClient:
		if self.external_client is None:
			external = get_profile(self.registry, self.registry.tri_chat.external_profile)
			self.external_client = make_client(external, self._vault_session)
		return self.external_client

	def _system_context(self) -> str:
		return (
			"You are one participant in a Tri-Chat with a local MLX model, an external API model, "
			"and a human user. Keep replies concise and build on prior messages."
		)

	def _build_messages_for(self, speaker: str) -> list[ChatMessage]:
		msgs = [ChatMessage(role="system", content=self._system_context(), speaker="system")]
		for m in self.history:
			label = m.speaker or m.role
			msgs.append(ChatMessage(role="user", content=f"[{label}]: {m.content}", speaker=label))
		msgs.append(
			ChatMessage(
				role="user",
				content=f"Respond now as [{speaker}]. Address the user and the other model if relevant.",
				speaker="system",
			)
		)
		return msgs

	def run_turn(self, user_text: str) -> list[ChatMessage]:
		"""User message → local reply → external reply."""
		user_msg = ChatMessage(role="user", content=user_text, speaker="User")
		self.history.append(user_msg)

		local_reply = self.local_client.chat(self._build_messages_for(self.local_label))
		local_msg = ChatMessage(role="assistant", content=local_reply, speaker=self.local_label)
		self.history.append(local_msg)

		external_reply = self._external_client().chat(self._build_messages_for(self.external_label))
		external_msg = ChatMessage(role="assistant", content=external_reply, speaker=self.external_label)
		self.history.append(external_msg)

		return [local_msg, external_msg]

	def close(self) -> None:
		self.local_client.close()
		if self.external_client is not None:
			self.external_client.close()
