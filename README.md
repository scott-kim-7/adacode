# Ada — Local LLM + Open WebUI

Apple Silicon + MLX 로컬 LLM 위에서 동작하는 **web-only** AI 채팅 플랫폼입니다.

## 빠른 시작

**사전 조건:** Docker Desktop, Python 3.11+

```bash
# 1) ada Python 패키지 (최초 1회)
./scripts/install-step2.sh

# 2) 로컬 LLM (MLX, 터미널 1)
./scripts/serve-qwen.sh

# 3) Open WebUI (터미널 2)
./scripts/serve-ada.sh
# → http://127.0.0.1:3000
```

첫 접속 시 Open WebUI에서 **로컬 계정**을 만들면 됩니다. 데이터는 Docker volume에 저장됩니다.

또는 MLX가 이미 떠 있으면:

```bash
./scripts/serve-open-webui.sh
```

## 아키텍처

```
Browser → Open WebUI (:3000) → MLX OpenAI API (:8080) → Qwen local model
```

Python `ada/` 패키지는 Model Registry, vault, Tri-Chat CLI, LangGraph `ada-agent` CLI를 제공합니다. **메인 채팅 UI는 Open WebUI**입니다.

## 검증

```bash
./scripts/verify-ada.sh
```

## 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `ADA_MLX_MODEL` | `mlx-community/Qwen3-VL-32B-Instruct-8bit` | MLX 모델 ID |
| `ADA_MLX_PORT` | `8080` | MLX API 포트 |
| `ADA_OPEN_WEBUI_PORT` | `3000` | Open WebUI 포트 |

## 문서

- [docs/ada/README.md](docs/ada/README.md) — 전체 개요
- [docs/ada/web/README.md](docs/ada/web/README.md) — Open WebUI 상세
- [ada/README.md](ada/README.md) — Python 패키지

## CLI (선택)

```bash
cd ada && source .venv/bin/activate
ada profiles
ada ada-agent --once "Hello"
ada tri-chat
```

## 저장소 구조

```
adacode/
├── ada/              # Python: registry, vault, agent, tri-chat
├── web/              # docker-compose.yml (Open WebUI)
├── scripts/          # serve-qwen, serve-ada, verify-ada
└── docs/ada/         # 문서
```
