#!/usr/bin/env python3
import os
from pathlib import Path

from huggingface_hub import try_to_load_from_cache


def main() -> int:
	model = os.environ["ADA_MLX_MODEL"]
	display = os.environ.get("ADA_MLX_DISPLAY_NAME", model)

	required = [
		"config.json",
		"tokenizer_config.json",
		"model.safetensors.index.json",
	]

	print(f"=== Download check: {display} ===")
	print(f"repo: {model}")
	print()

	missing = []
	for name in required:
		path = try_to_load_from_cache(model, name)
		if path:
			print(f"  ok  {name}")
		else:
			print(f"  MISSING  {name}")
			missing.append(name)

	cache_root = Path.home() / ".cache" / "huggingface" / "hub"
	repo_dir = None
	weight_count = 0
	weight_bytes = 0

	if cache_root.is_dir():
		for models_dir in cache_root.glob("models--*"):
			if model.replace("/", "--") in models_dir.name:
				repo_dir = models_dir
				break

	if repo_dir:
		for path in repo_dir.rglob("model-*.safetensors"):
			if path.is_file():
				weight_count += 1
				weight_bytes += path.stat().st_size
		print()
		print(f"  weight shards: {weight_count}")
		print(f"  weight size:   {weight_bytes / (1024 ** 3):.1f} GB")
		print(f"  cache dir:     {repo_dir}")
	else:
		print()
		print("  warn: could not locate repo folder under ~/.cache/huggingface/hub")

	print()
	if missing or weight_count == 0:
		print("RESULT: INCOMPLETE — run: ./scripts/download-qwen-model.sh")
		return 1

	print("RESULT: cache looks complete")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
