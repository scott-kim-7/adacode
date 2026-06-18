# Ada — Local LLM + Open WebUI

**web-only** 프로젝트입니다. VS Code fork는 제거되었습니다.

## 빠른 시작

```bash
./scripts/install-step2.sh
# MLX :8080 — 외부에서 기동 (mlx_lm / mlx-vlm)
./scripts/ada.sh start           # Agent :9082 + Open WebUI :3000
```

브라우저 → http://127.0.0.1:3000 → 로컬 계정 생성 → 채팅

모델 ID는 런타임에 `GET /v1/models`로 해석합니다. 설정: [`ada/config/model_registry.yaml`](../ada/config/model_registry.yaml) (`chat_profile`).

## 구성

| 레이어 | 설명 |
|--------|------|
| **Open WebUI** | Docker, 채팅 UI |
| **MLX** | 외부 LLM 서버, OpenAI-compatible `:8080/v1` |
| **ada/** | Python — registry, vault, Tri-Chat, `ada ada-agent` CLI |

## 검증

```bash
./scripts/verify-regression.sh   # regression contract (22 tests)
./scripts/verify-ada.sh          # regression + full unit + compose
./scripts/verify-agent-vision.sh # 런타임 vision E2E (스택 기동 후)
```

## 문서

| 문서 | 설명 |
|------|------|
| [web/README.md](web/README.md) | Open WebUI 설정·트러블슈팅 |
| [step2/README.md](step2/README.md) | Model Registry, vault, Tri-Chat |
| [VAULT.md](VAULT.md) | vault 정책 |
| [agent/README.md](agent/README.md) | LangGraph MainGraph 설계 |
| [regression/README.md](regression/README.md) | Regression test suite |

## North Star (web-only)

1. 로컬 MLX + Open WebUI로 프라이빗 채팅
2. `ada/` Python으로 registry·vault·Tri-Chat·agent CLI
3. LangGraph agent API(:9082)로 Open WebUI ↔ MainGraph 연동
