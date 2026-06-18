# Open WebUI + 로컬 MLX

메인 채팅 UI입니다. Open WebUI는 [오픈소스 LLM 웹 UI](https://github.com/open-webui/open-webui)를 Docker로 실행합니다.

## 실행

**사전 조건:** mlx_lm / mlx-vlm이 `http://127.0.0.1:8080/v1` 에서 이미 응답해야 합니다 (Ada가 MLX를 기동하지 않음).

```bash
./scripts/ada.sh start           # Agent :9082 + Open WebUI (권장)
./scripts/serve-open-webui.sh    # WebUI만 (MLX + Agent 선행)
./scripts/serve-ada.sh           # MLX 확인 후 WebUI
```

브라우저: http://127.0.0.1:3000 (`ADA_OPEN_WEBUI_PORT`)

## 아키텍처

```
Browser → Open WebUI (Docker :3000)
       → LangGraph agent API (:9082/v1)
       → MainGraph (route / plan / respond)
       → MLX (:8080/v1)
       → (model id from GET /v1/models)
```

구성 파일: [`web/docker-compose.yml`](../../web/docker-compose.yml)

## 최초 설정

1. 브라우저에서 **Sign up** — 로컬 계정 (데이터는 Docker volume `open-webui`)
2. 채팅에서 모델 선택 — Open WebUI가 `GET /v1/models` 목록을 표시합니다. 선택한 모델이 mlx_vlm에 로드됩니다 (`/health` → `loaded_model`).
3. (필요 시) Settings → Connections → OpenAI base URL 확인

## Ada Email UI (v0.6.42 패치)

Open WebUI에 Ada Email 설정·Inbox 패널·Mail Archive 페이지(`/ada/email`)가 통합됩니다 (`./scripts/vendor-open-webui.sh` → 로컬 Docker build).

1. `cd ada && make vault-init` — vault 마스터 비밀번호 설정 (파일만 생성, env 미사용)
2. Gmail OAuth: Google Console redirect URI `http://127.0.0.1:9082/oauth/gmail/callback` → `make vault-set KEY=gmail.oauth.client`
3. `./scripts/ada.sh start` — vault가 있으면 **비밀번호만** 입력 (fd 3으로 Agent에 1회 전달). `ada.local.api_key`는 vault에 자동 생성.
4. Open WebUI **Admin → Settings → Ada Email** — Local API Key 입력 없음 (admin 세션 → WebUI 프록시 → Agent)
5. **Email Archive**는 Admin → Ada Email 설정 화면의 **Open email archive** 링크로만 진입 (`/ada/email`). Navbar Inbox 버튼과 별개입니다.
6. **Inbox UI poll interval**은 채팅 Inbox 패널의 브라우저 폴링 주기이고, **Heartbeat interval**은 Agent 백그라운드 작업(gmail sync, email graph 등) 주기입니다.
7. Summary Skip Rules에서 no-reply, mailing list, custom rule을 저장하면 해당 메일은 요약 생성을 건너뜁니다.

레거시 `ada/.local/ada_local_api_key`가 있으면: `cd ada && ada vault migrate-local-key`

검증: `./scripts/verify-open-webui-ada.sh`

## 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `ADA_OPEN_WEBUI_PORT` | `3000` | 호스트 포트 |
| `ADA_OPEN_WEBUI_CONTAINER` | `adacode-open-webui` | 컨테이너 이름 |
| `ADA_MLX_MODEL` | *(다운로드 시)* | HF repo id — `download-mlx-model.sh` 전용 |
| `OPENAI_API_BASE_URL` | `host.docker.internal:9082/v1` | 컨테이너 → LangGraph agent |
| `ADA_AGENT_PORT` | `9082` | agent API 포트 |
| `ADA_AGENT_BASE_URL` | `host.docker.internal:9082` | WebUI → Agent Email 프록시 |
| `ADA_VAULT_UNLOCK_FD` | *(기동 시)* | vault unlock 비밀번호를 읽을 fd (보통 `3`) |

Open WebUI Docker build가 OOM이면 Docker Desktop **Memory ≥ 10GB** 권장. Dockerfile은 `NODE_OPTIONS=--max-old-space-size=8192` 사용.

**`main` 이미지 → v0.6.42 로컬 빌드로 바꾼 경우** 기존 Docker 볼륨의 DB 스키마가 맞지 않을 수 있습니다 (`Can't locate revision b2c3d4e5f6a7`, `tool.access_control` 없음). 해결:

```bash
ADA_OPEN_WEBUI_RESET_DATA=1 ./scripts/ada.sh start
# 또는
./scripts/reset-open-webui-data.sh && ./scripts/serve-open-webui.sh
```

계정·채팅 기록이 삭제되고 Sign up부터 다시 시작합니다.

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
| **Connect Gmail — Vault not configured** | `curl http://127.0.0.1:9082/health` → `email_vault` 확인. `missing` / `unlock_required`이면 vault-init·vault-set·`ada.sh restart`(vault 비밀번호). |
| **Email UI Agent unreachable** | `./scripts/vendor-open-webui.sh` 후 WebUI 재빌드. Admin 로그인 필요 (프록시는 admin only). |
| 이미지 응답 매우 느림 | VL 모델 — 첫 토큰 30~90초 흔함. **새 채팅(+)** 사용 |

## LangGraph agent

Open WebUI 채팅은 **LangGraph MainGraph**를 거칩니다 (`scripts/ada_agent_server.py`, 포트 `:9082`).

- plan 경로: 긴 질문·키워드 → 내부 계획 후 답변
- direct 경로: 짧은 질문 → 바로 답변
- plan/respond 노드 모두 OpenAI `image_url` multimodal content 전달

**Vision 검증:**

```bash
./scripts/verify-step1-vision.sh    # MLX :8080
./scripts/verify-agent-vision.sh    # Agent :9082
```

터미널 REPL: `ada ada-agent`
