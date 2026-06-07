# Ada — AI coding agents (web-only)

This repository is a **web-only** local AI platform. The main chat UI is **Open WebUI** (Docker) connected to a local **MLX** OpenAI-compatible server.

## Layout

| Path | Purpose |
|------|---------|
| [`ada/`](ada/) | Python package — Model Registry, vault, Tri-Chat, LangGraph CLI |
| [`web/docker-compose.yml`](web/docker-compose.yml) | Open WebUI container |
| [`scripts/`](scripts/) | MLX server, Open WebUI launcher, verify |
| [`docs/ada/`](docs/ada/) | Human documentation |

## Quick commands

```bash
./scripts/install-step2.sh    # ada venv
./scripts/serve-qwen.sh       # MLX :8080
./scripts/serve-ada.sh        # Open WebUI :3000
./scripts/verify-ada.sh       # pytest + compose smoke
```

## Python development

```bash
cd ada
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

See [`ada/README.md`](ada/README.md) and [`.github/copilot-instructions.md`](.github/copilot-instructions.md) if present.
