# Ada — AI orchestration (web-only)

Python 패키지: Model Registry, vault, Tri-Chat, LangGraph CLI.

**메인 UI는 Open WebUI** — `./scripts/serve-ada.sh` (레포 루트 README 참고).

## 설치

```bash
./scripts/install-step2.sh
# 또는
cd ada && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

## CLI

```bash
ada profiles
ada ada-agent --once "Hello"    # LangGraph pass-through → MLX
ada tri-chat                    # 로컬 + 외부 LLM 3자 대화
```

## Model Registry

설정: [`config/model_registry.yaml`](config/model_registry.yaml)

`chat_profile` → `http://127.0.0.1:8089/v1` (MLX, Open WebUI와 동일 endpoint)

## Vault

```bash
make vault-init
make vault-set KEY=external.openai.api_key
```

## 검증

```bash
./scripts/verify-ada.sh
pytest
```

## 구조

[STRUCTURE.md](STRUCTURE.md)
