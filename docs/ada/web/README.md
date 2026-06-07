# Open WebUI + 로컬 MLX

메인 채팅 UI입니다. Open WebUI는 [오픈소스 LLM 웹 UI](https://github.com/open-webui/open-webui)를 Docker로 실행합니다.

## 실행

```bash
./scripts/serve-qwen.sh          # MLX 필수
./scripts/serve-open-webui.sh    # Open WebUI만
# 또는
./scripts/serve-ada.sh           # MLX 없으면 백그라운드 기동 시도 후 WebUI
```

브라우저: http://127.0.0.1:3000 (`ADA_OPEN_WEBUI_PORT`)

## 아키텍처

```
Browser → Open WebUI (Docker :3000)
       → OPENAI_API_BASE_URL → MLX (:8080/v1)
       → Qwen model
```

구성 파일: [`web/docker-compose.yml`](../../web/docker-compose.yml)

## 최초 설정

1. 브라우저에서 **Sign up** — 로컬 계정 (데이터는 Docker volume `open-webui`)
2. 채팅에서 모델 선택 — 기본값 `ADA_MLX_MODEL` (Qwen3-VL-32B 8bit)
3. (필요 시) Settings → Connections → OpenAI base URL 확인

## 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `ADA_OPEN_WEBUI_PORT` | `3000` | 호스트 포트 |
| `ADA_OPEN_WEBUI_CONTAINER` | `adacode-open-webui` | 컨테이너 이름 |
| `ADA_MLX_MODEL` | (mlx_defaults.sh) | DEFAULT_MODELS |
| `OPENAI_API_BASE_URL` | `host.docker.internal:8080/v1` | 컨테이너 → MLX |

Linux에서는 `172.17.0.1` 또는 호스트 IP로 자동 설정됩니다 (`serve-open-webui.sh`).

## 중지

```bash
docker compose -f web/docker-compose.yml down
```

## 트러블슈팅

| 문제 | 해결 |
|------|------|
| Docker 없음 | Docker Desktop 설치 |
| MLX 연결 실패 | `./scripts/serve-qwen.sh` 실행 후 `curl http://127.0.0.1:8080/v1/models` |
| 응답 매우 느림 | 32B 모델 — 첫 토큰까지 수십 초 가능 |
| 모델 목록 비어 있음 | Open WebUI Settings에서 base URL / API key `local` 확인 |

## LangGraph agent

Open WebUI는 **MLX에 직접** 연결합니다. LangGraph `ada ada-agent` CLI는 터미널용입니다.  
향후 Open WebUI ↔ Ada agent 연동은 FastAPI OpenAI shim으로 추가 가능합니다.
