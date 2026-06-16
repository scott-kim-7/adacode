# Open WebUI + 로컬 MLX

메인 채팅 UI입니다. Open WebUI는 [오픈소스 LLM 웹 UI](https://github.com/open-webui/open-webui)를 Docker로 실행합니다.

## 실행

**사전 조건:** mlx_lm / mlx-vlm이 `http://127.0.0.1:8080/v1` 에서 이미 응답해야 합니다 (Ada가 MLX를 기동하지 않음).

```bash
./scripts/ada.sh start           # Agent :8082 + Open WebUI (권장)
./scripts/serve-open-webui.sh    # WebUI만 (MLX + Agent 선행)
./scripts/serve-ada.sh           # MLX 확인 후 WebUI
```

브라우저: http://127.0.0.1:3000 (`ADA_OPEN_WEBUI_PORT`)

## 아키텍처

```
Browser → Open WebUI (Docker :3000)
       → LangGraph agent API (:8082/v1)
       → MainGraph (route / plan / respond)
       → MLX (:8080/v1)
       → (model id from GET /v1/models)
```

구성 파일: [`web/docker-compose.yml`](../../web/docker-compose.yml)

## 최초 설정

1. 브라우저에서 **Sign up** — 로컬 계정 (데이터는 Docker volume `open-webui`)
2. 채팅에서 모델 선택 — Open WebUI가 `GET /v1/models` 목록을 표시합니다. 선택한 모델이 mlx_vlm에 로드됩니다 (`/health` → `loaded_model`).
3. (필요 시) Settings → Connections → OpenAI base URL 확인

## 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `ADA_OPEN_WEBUI_PORT` | `3000` | 호스트 포트 |
| `ADA_OPEN_WEBUI_CONTAINER` | `adacode-open-webui` | 컨테이너 이름 |
| `ADA_MLX_MODEL` | *(다운로드 시)* | HF repo id — `download-mlx-model.sh` 전용 |
| `OPENAI_API_BASE_URL` | `host.docker.internal:8082/v1` | 컨테이너 → LangGraph agent |
| `ADA_AGENT_PORT` | `8082` | agent API 포트 |

Linux에서는 `172.17.0.1` 또는 호스트 IP로 자동 설정됩니다 (`serve-open-webui.sh`).

## 중지

```bash
./scripts/ada.sh stop
# 또는
docker compose -f web/docker-compose.yml down
```

## 트러블슈팅

| 문제 | 해결 |
|------|------|
| Docker 없음 | Docker Desktop 설치 |
| MLX 연결 실패 | `curl http://127.0.0.1:8080/v1/models` 로 LLM 서버 확인 |
| 응답 매우 느림 | 대형 모델 — 첫 토큰까지 수십 초 가능 |
| 모델 목록 비어 있음 | Open WebUI Settings에서 base URL / API key `local` 확인 |
| **이미지 붙여넣기 무시됨** | `./scripts/verify-agent-vision.sh` |
| 이미지 응답 매우 느림 | VL 모델 — 첫 토큰 30~90초 흔함. **새 채팅(+)** 사용 |

## LangGraph agent

Open WebUI 채팅은 **LangGraph MainGraph**를 거칩니다 (`scripts/ada_agent_server.py`, 포트 `:8082`).

- plan 경로: 긴 질문·키워드 → 내부 계획 후 답변
- direct 경로: 짧은 질문 → 바로 답변
- plan/respond 노드 모두 OpenAI `image_url` multimodal content 전달

**Vision 검증:**

```bash
./scripts/verify-step1-vision.sh    # MLX :8080
./scripts/verify-agent-vision.sh    # Agent :8082
```

터미널 REPL: `ada ada-agent`
