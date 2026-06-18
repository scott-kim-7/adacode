# Step 2 — Model Registry, vault, 외부 LLM, Tri-Chat

**ada/** Python으로 3자 대화와 외부 API 연동을 추가합니다.

## 목표

1. **Model Registry** — `chat_profile` / `external_profile` / `regression_profile`
2. **vault** — 외부 API 키 암호화 저장 (`ada/vault/secrets.vault.enc`)
3. **Tri-Chat MVP** — 로컬 OpenAPI LLM · 외부 LLM · 사용자 (CLI)

## 사전 조건

- `./scripts/install-step2.sh`
- LLM 서버: `mlx_lm` / `mlx-vlm`이 `http://127.0.0.1:8080/v1` 에서 응답 (Ada가 기동하지 않음)
- web 스택 (선택): `./scripts/ada.sh start`

## 1. ada 패키지 설치

```bash
cd ada
make install
ada profiles
```

## 2. vault (외부 API 키)

```bash
cd ada
make vault-init
make vault-set KEY=external.openai.api_key
make vault-list
```

정책: [VAULT.md](../VAULT.md) — 평문 settings·`.env`·`ADA_*_KEY` env 금지. 외부 API 키는 vault만 사용.

## 3. Model Registry

[`ada/config/model_registry.yaml`](../../ada/config/model_registry.yaml)

| 프로필 | 역할 |
|--------|------|
| `chat_profile` | 로컬 OpenAPI (`127.0.0.1:8080`) — 모델 ID는 `GET /v1/models` |
| `external_profile` | OpenAI-compatible API — vault `external.openai.api_key` |
| `regression_profile` | 회귀 테스트용 로컬 OpenAPI |

```bash
ada profiles chat_profile
ada profiles
```

## 4. IDE — 두 번째 BYOK (외부 LLM, 선택)

Step 1 JSON에 **두 번째 Custom Endpoint** 그룹을 추가합니다.

```bash
./scripts/install-step2.sh
```

예시: [`chatLanguageModels.external.example.json`](chatLanguageModels.external.example.json)

> BYOK JSON에는 API 키가 들어갑니다. **Tri-Chat CLI**는 vault를 사용합니다.

## 5. Tri-Chat CLI (MVP)

```bash
# 터미널 1: LLM 서버가 :8080에서 이미 응답해야 함

# 터미널 2
cd ada && source .venv/bin/activate
make vault-set KEY=external.openai.api_key   # vault unlock 후 입력
ada tri-chat
```

한 턴만 (테스트):

```bash
ada tri-chat --once "Summarize what Tri-Chat does in one sentence."
```

흐름: **User** → **Local (OpenAPI)** → **External (API)** → 반복.

## Step 2 완료 기준

- [x] Model Registry YAML + `ada profiles`
- [x] vault `make vault-init` / `vault-set` / `vault-list`
- [x] Tri-Chat CLI — 로컬 + 외부 최소 1턴 (`--once`)
- [x] 외부 BYOK 예시 JSON + `install-step2.sh`
- [ ] IDE에서 두 모델 동시 선택 (사용자 확인, IDE 사용 시)

## 다음

Step 3 — 자율 Agent. LangGraph agent API는 Open WebUI와 `:9082`로 연동됩니다.
