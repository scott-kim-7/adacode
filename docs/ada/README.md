# Ada — Local LLM + Open WebUI

**web-only** 프로젝트입니다. VS Code fork는 제거되었습니다.

## 빠른 시작

```bash
./scripts/install-step2.sh
./scripts/serve-qwen.sh          # 터미널 1: MLX :8080
./scripts/serve-ada.sh           # 터미널 2: Open WebUI :3000
```

브라우저 → http://127.0.0.1:3000 → 로컬 계정 생성 → 채팅

모델은 [`ada/config/model_registry.yaml`](../ada/config/model_registry.yaml)의 `chat_profile`과 동일한 Qwen MLX 모델을 사용합니다.

## 구성

| 레이어 | 설명 |
|--------|------|
| **Open WebUI** | Docker, 채팅 UI |
| **MLX** | `serve-qwen.sh`, OpenAI-compatible `:8080/v1` |
| **ada/** | Python — registry, vault, Tri-Chat, `ada ada-agent` CLI |

## 검증

```bash
./scripts/verify-ada.sh
```

## 문서

| 문서 | 설명 |
|------|------|
| [web/README.md](web/README.md) | Open WebUI 설정·트러블슈팅 |
| [step2/README.md](step2/README.md) | Model Registry, vault, Tri-Chat |
| [VAULT.md](VAULT.md) | vault 정책 |
| [DESIGN_PLAN.md](DESIGN_PLAN.md) | 기획 (일부 IDE 내용은 레거시) |

## North Star (web-only)

1. 로컬 MLX + Open WebUI로 프라이빗 채팅
2. `ada/` Python으로 registry·vault·Tri-Chat·agent CLI
3. (향후) FastAPI shim으로 Open WebUI ↔ LangGraph agent 연동
