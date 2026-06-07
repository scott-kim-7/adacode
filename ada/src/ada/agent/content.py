from __future__ import annotations

from typing import Any

UserContent = str | list[dict[str, Any]]

DEFAULT_IMAGE_ONLY_PROMPT = "Describe the image."


def _normalize_block(item: dict[str, Any]) -> dict[str, Any] | None:
	block_type = item.get("type")
	if block_type == "text":
		text = str(item.get("text") or "")
		if not text:
			return None
		return {"type": "text", "text": text}
	if block_type == "image_url":
		image_url = item.get("image_url")
		if not isinstance(image_url, dict):
			return None
		url = image_url.get("url")
		if not url:
			return None
		normalized: dict[str, Any] = {"type": "image_url", "image_url": {"url": str(url)}}
		if image_url.get("detail"):
			normalized["image_url"]["detail"] = image_url["detail"]
		return normalized
	if "text" in item:
		text = str(item["text"])
		if text:
			return {"type": "text", "text": text}
	return None


def parse_openai_content(raw: Any) -> UserContent:
	if raw is None:
		return ""
	if isinstance(raw, str):
		return raw
	if isinstance(raw, list):
		blocks: list[dict[str, Any]] = []
		for item in raw:
			if not isinstance(item, dict):
				continue
			block = _normalize_block(item)
			if block is not None:
				blocks.append(block)
		if not blocks:
			return ""
		if len(blocks) == 1 and blocks[0].get("type") == "text":
			return str(blocks[0]["text"])
		return blocks
	return str(raw)


def extract_text_from_content(content: UserContent) -> str:
	if isinstance(content, str):
		return content
	parts: list[str] = []
	for block in content:
		if block.get("type") == "text":
			text = str(block.get("text") or "")
			if text:
				parts.append(text)
	return "\n".join(parts)


def content_has_image(content: UserContent) -> bool:
	if isinstance(content, str):
		return False
	return any(block.get("type") == "image_url" for block in content)


def content_is_empty(content: UserContent) -> bool:
	if isinstance(content, str):
		return not content.strip()
	return not content_has_image(content) and not extract_text_from_content(content).strip()


def ensure_user_prompt(
	content: UserContent,
	prompt: str = DEFAULT_IMAGE_ONLY_PROMPT,
) -> UserContent:
	if not content_has_image(content):
		return content
	if extract_text_from_content(content).strip():
		return content
	if isinstance(content, str):
		return prompt
	return [{"type": "text", "text": prompt}, *content]
