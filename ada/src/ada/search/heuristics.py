from __future__ import annotations

import re
from typing import Literal

SearchProvider = Literal["exa", "context7", "both"]

_CONTEXT7_RE = re.compile(
	r"\b(framework|library|lib|api|how\s+to|install|documentation|docs?|reference)\b",
	re.IGNORECASE,
)
_EXA_RE = re.compile(r"\b(news|today|stock|weather|\d{4})\b", re.IGNORECASE)


def select_search_providers(user_text: str) -> list[SearchProvider]:
	text = (user_text or "").strip()
	if not text:
		return []
	has_context7 = bool(_CONTEXT7_RE.search(text))
	has_exa = bool(_EXA_RE.search(text))
	if has_context7 and has_exa:
		return ["context7", "exa"]
	if has_context7:
		return ["context7"]
	if has_exa:
		return ["exa"]
	return ["exa"]
