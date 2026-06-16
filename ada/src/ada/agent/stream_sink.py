from __future__ import annotations

import queue
from dataclasses import dataclass, field
from typing import Literal

StreamChannel = Literal["content", "reasoning"]
StreamPhase = Literal["plan", "respond"]

# Open WebUI / Qwen-style collapsed plan (plan_fallback_tags mode)
THINK_OPEN = "\n\n\u003cthink\u003e\n"
THINK_CLOSE = "\n\u003c/think\u003e\n\n"


@dataclass(frozen=True)
class StreamChunk:
	channel: StreamChannel
	text: str


@dataclass
class StreamSink:
	"""Thread-safe token queue from LangGraph LLM nodes to Agent SSE."""

	_queue: queue.Queue[StreamChunk | BaseException | None] = field(default_factory=queue.Queue)
	_tokens: list[str] = field(default_factory=list)

	def push(self, token: str, *, channel: StreamChannel = "content") -> None:
		if not token:
			return
		self._tokens.append(token)
		self._queue.put(StreamChunk(channel=channel, text=token))

	def finish(self, error: BaseException | None = None) -> None:
		if error is not None:
			self._queue.put(error)
		self._queue.put(None)

	def get(self) -> StreamChunk | BaseException | None:
		return self._queue.get()

	def joined_text(self) -> str:
		return "".join(self._tokens)

	def drain_pending(self) -> list[StreamChunk]:
		pending: list[StreamChunk] = []
		while True:
			try:
				item = self._queue.get_nowait()
			except queue.Empty:
				break
			if isinstance(item, StreamChunk):
				pending.append(item)
		return pending


@dataclass
class StreamContext:
	sink: StreamSink | None = None
	allow_stream: bool = False
	phase: StreamPhase | None = None
	plan_fallback_tags: bool = False
	_plan_tag_open: bool = False

	def stream_channel(self) -> StreamChannel:
		if self.phase == "plan":
			return "content" if self.plan_fallback_tags else "reasoning"
		return "content"

	def begin_plan_stream(self) -> None:
		self.phase = "plan"
		self.allow_stream = True
		if self.plan_fallback_tags and self.sink is not None:
			self.sink.push(THINK_OPEN, channel="content")
			self._plan_tag_open = True

	def begin_respond_stream(self, *, had_plan: bool = False) -> None:
		if had_plan and self.plan_fallback_tags and self._plan_tag_open and self.sink is not None:
			self.sink.push(THINK_CLOSE, channel="content")
			self._plan_tag_open = False
		self.phase = "respond"
		self.allow_stream = True

	def end_llm_stream(self) -> None:
		self.allow_stream = False
		self.phase = None
