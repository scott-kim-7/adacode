# Step 2 — Model Registry, vault, 외부 LLM, Tri-Chat

Step 1(로컬 Qwen IDE) 완료 후 **ada/** Python으로 3자 대화와 외부 API 연동을 추가합니다.

## 목표

1. **Model Registry** — `chat_profile` / `external_profile` / `regression_profile`
2. **vault** — 외부 API 키 암호화 저장 (`ada/vault/secrets.vault.enc`)
3. **Tri-Chat MVP** — 로컬 MLX · 외부 LLM · 사용자 (CLI)

## 사전 조건

- Step 1: `./scripts/adacode.sh`, `./scripts/verify-step1.sh`
- MLX 서버: `./scripts/serve-qwen.sh` (Tri-Chat 로컬 턴용)

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

정책: [VAULT.md](../VAULT.md) — 평문 settings·`.env` 금지.

개발용 우회 (vault 없이 테스트):

```bash
export ADA_EXTERNAL_API_KEY=sk-...
```

## 3. Model Registry

[`ada/config/model_registry.yaml`](../../ada/config/model_registry.yaml)

| 프로필 | 역할 |
|--------|------|
| `chat_profile` | 로컬 MLX Qwen (`127.0.0.1:8080`) — Step 1 BYOK와 동일 |
| `external_profile` | OpenAI-compatible API — vault `external.openai.api_key` |
| `regression_profile` | Step 4 placeholder — 로컬 MLX 고정 |

```bash
ada profiles chat_profile   # 상세
ada profiles
```

## 4. IDE — 두 번째 BYOK (외부 LLM)

Step 1 JSON에 **두 번째 Custom Endpoint** 그룹을 추가합니다.

```bash
./scripts/install-step2.sh
```

또는 [`chatLanguageModels.external.example.json`](chatLanguageModels.external.example.json) 내용을  
`chatLanguageModels.json` 배열에 **merge** (Local Qwen 그룹 유지).

IDE 재시작: Cmd+Q → `./scripts/adacode.sh`

> BYOK JSON에는 API 키가 들어갑니다. **ada orchestration(Tri-Chat CLI)** 은 vault를 사용하고, IDE BYOK는 사용자가 직접 키를 넣거나 OS keychain에 맡깁니다.

## 5. Tri-Chat CLI (MVP)

```bash
# 터미널 1
./scripts/serve-qwen.sh

# 터미널 2
cd ada && source .venv/bin/activate
export ADA_EXTERNAL_API_KEY=sk-...   # 또는 vault
ada tri-chat
```

한 턴만 (테스트):

```bash
ada tri-chat --once "Summarize what Tri-Chat does in one sentence."
```

흐름: **User** → **Local (Qwen)** → **External (API)** → 반복.

## Step 2 완료 기준

- [x] Model Registry YAML + `ada profiles`
- [x] vault `make vault-init` / `vault-set` / `vault-list`
- [x] Tri-Chat CLI — 로컬 + 외부 최소 1턴 (`--once`)
- [x] 외부 BYOK 예시 JSON + `install-step2.sh`
- [ ] IDE에서 두 모델 동시 선택 (사용자 확인)

## 다음

Step 3 — 자율 Agent. Step 2 후반 — VL 이미지 전용 경로 또는 Tri-Chat 역할 분담.
