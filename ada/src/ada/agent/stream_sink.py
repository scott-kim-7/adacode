from __future__ import annotations

import queue
from dataclasses import dataclass, field
from typing import Literal

StreamChannel = Literal["content", "reasoning"]
StreamPhase = Literal["plan", "respond"]

# Open WebUI 0.8.x inline collapsible thinking (ChatGPT-style, same message bubble)
THINK_OPEN = "\n\n<think>\n"
THINK_CLOSE = "\n</think>\n\n"


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
	inline_thinking: bool = True
	expose_graph_trace: bool = True
	trace_direct_route: bool = True
	_thinking_open: bool = False

	def stream_channel(self) -> StreamChannel:
		if self.inline_thinking:
			return "content"
		if self.phase == "plan":
			return "reasoning"
		return "content"

	def _push_content(self, text: str) -> None:
		if self.sink is not None and text:
			self.sink.push(text, channel="content")

	def open_thinking(self) -> None:
		if not self.inline_thinking or self.sink is None or self._thinking_open:
			return
		self._push_content(THINK_OPEN)
		self._thinking_open = True

	def close_thinking(self) -> None:
		if not self.inline_thinking or self.sink is None or not self._thinking_open:
			return
		self._push_content(THINK_CLOSE)
		self._thinking_open = False

	def emit_trace(self, text: str) -> None:
		if not self.expose_graph_trace or self.sink is None:
			return
		line = text if text.endswith("\n") else f"{text}\n"
		if self.inline_thinking:
			self.open_thinking()
			self._push_content(line)
		else:
			self.sink.push(line, channel="reasoning")

	def begin_plan_stream(self) -> None:
		self.phase = "plan"
		self.allow_stream = True
		self.open_thinking()

	def begin_respond_stream(self, *, had_plan: bool = False) -> None:
		del had_plan
		if self._thinking_open:
			self.close_thinking()
		self.phase = "respond"
		self.allow_stream = True

	def end_llm_stream(self) -> None:
		self.allow_stream = False
		self.phase = None
