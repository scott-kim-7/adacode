#!/usr/bin/env python3
import os

from huggingface_hub import snapshot_download


def main() -> int:
	model = os.environ["ADA_MLX_MODEL"]
	display = os.environ.get("ADA_MLX_DISPLAY_NAME", model)

	print(f"Fetching {display} ({model}) ...", flush=True)
	path = snapshot_download(
		repo_id=model,
		repo_type="model",
		resume_download=True,
	)
	print("")
	print("Download complete.")
	print(f"  local cache: {path}")
	print("")
	print("Next: ./scripts/adacode.sh")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
