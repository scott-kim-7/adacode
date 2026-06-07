#!/usr/bin/env python3
"""OpenAI-compatible API: Open WebUI → LangGraph MainGraph → MLX."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ada" / "src"))

from ada.agent.server import main

if __name__ == "__main__":
	raise SystemExit(main())
