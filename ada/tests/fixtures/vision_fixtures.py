from __future__ import annotations

from typing import Any

# 1x1 red PNG — same as scripts/ada/verify_mlx_vision.py
TINY_PNG_B64 = (
	"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

IMAGE_URL_BLOCK: dict[str, Any] = {
	"type": "image_url",
	"image_url": {"url": f"data:image/png;base64,{TINY_PNG_B64}"},
}


def openai_user_multimodal(text: str = "describe this image") -> dict[str, Any]:
	return {
		"role": "user",
		"content": [
			{"type": "text", "text": text},
			IMAGE_URL_BLOCK,
		],
	}


def openai_user_image_only() -> dict[str, Any]:
	return {"role": "user", "content": [dict(IMAGE_URL_BLOCK)]}


def openai_history_with_prior_image() -> list[dict[str, Any]]:
	return [
		openai_user_multimodal("first image"),
		{"role": "assistant", "content": "I see a red pixel."},
		openai_user_multimodal("second image"),
	]
