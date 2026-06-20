# Vault — 계정·비밀번호

## 원칙 (전역)

**시스템이 다루는 모든 계정·비밀번호·API 키·OAuth 토큰**은 입력 즉시 vault에 암호화해 저장한다. 평문은 디스크·env·UI·config·로그 어디에도 남기지 않고, 입력 버퍼는 가능한 한 즉시 폐기한다.

| 구분 | 정책 |
|------|------|
| **영구 저장** | `secrets.vault.enc` **만** |
| **입력 경로** | `make vault-set`, `make vault-ensure` (자동 생성), OAuth callback → vault |
| **금지** | `.env`, `ada/.local/`, Docker env, `localStorage`, registry `api_key: sk-...`, `ADA_EXTERNAL_API_KEY` |
| **런타임** | unlock된 `VaultSession` / 파생 키만 RAM (사용을 위해 불가피) |
| **앱 데이터** | 이메일 SQLite, WebUI 채팅 DB — 비밀번호가 아닌 데이터 |

코드: [`ada/src/ada/vault_secrets.py`](../ada/src/ada/vault_secrets.py) — `store_secret_in_vault()`, `scrub_forbidden_secret_env()`

## 주요 vault 키

| 키 | 용도 |
|----|------|
| `gmail.oauth.client` | Google OAuth client JSON |
| `gmail.oauth.{account_id}` | Gmail refresh/access tokens |
| `ada.local.api_key` | Email API `X-Ada-Local-Key` (curl/webhook; 브라우저는 WebUI 프록시) |
| `external.*.api_key` | 외부 LLM API 키 |
| `exa.api_key` | Agent `search_batch` — Exa web search ([`search/service.py`](../ada/src/ada/search/service.py)) |
| `context7.api_key` | Agent `search_batch` — Context7 lib/docs search (동일) |

### Web search vault 키 (Phase 2)

`features.web_search` ON 채팅 시 Agent UnifiedGraph `search_batch`가 vault에서 읽는다. 키가 없으면 해당 provider만 skip(채팅은 계속).

```bash
cd ada
make vault-set KEY=exa.api_key        # Exa dashboard API key
make vault-set KEY=context7.api_key   # context7.com API key
make vault-list
```

- **금지:** OWUI Admin Exa 키·Docker env·`.env` — vault만 사용 ([`ada-vault-policy`](../../.cursor/rules/ada-vault-policy.mdc))
- **확인:** `pytest tests/test_web_search.py` (mock); live는 `./scripts/verify-phase2-owui.sh` (스택 + 선택 `OWUI_JWT`)

## 암호 → 키

1. Unicode NFKC 정규화 + trim
2. PBKDF2-HMAC-SHA256, 600_000 iterations, file salt, dklen=32
3. AES-256-GCM

## 기동 (Agent)

```bash
./scripts/ada.sh start   # vault 있으면 터미널에서 비밀번호 → fd 3 → Agent
```

자동화:

```bash
printf '%s' "$VAULT_PASS" | ADA_NON_INTERACTIVE=1 ADA_VAULT_UNLOCK_FD=3 ./scripts/ada.sh start 3<&0
unset VAULT_PASS
```

## 레거시 Local API Key 마이그레이션

```bash
cd ada && ada vault migrate-local-key
# 이후 ada/.local/ada_local_api_key 삭제 가능
```

## 자동 생성 모드

사용자가 값을 직접 입력하지 않아도 되는 비밀(웹훅 HMAC, 내부 API 키 등)은 **cryptographically strong** 값을 생성해 지정한 vault 키에 저장한다. 이미 있으면 유지(idempotent).

```bash
cd ada
make vault-ensure KEY=webhook.shared_secret SHOW=1   # 생성 시 값 1회 출력
ada vault set my.service.token --auto --show
ada vault ensure ada.local.api_key          # Agent 기동 시에도 자동 (ensure_local_api_key)
ada vault ensure my.key --force --show      # 기존 값 덮어쓰기
```

- `--bytes N` — `token_urlsafe` 전 랜덤 바이트 수 (기본 32, 최소 16)
- `--show` — **최초 생성 시에만** 평문 1회 출력 (다시 조회 불가)
- `ada.local.api_key` — Agent bootstrap에서 자동 ensure (값 미출력)

## VaultNotice (5항목)

```
[VAULT ACTION REQUIRED: VAULT_ADD]
무엇:   github.token
왜:     GitHub push
어디:   ada/vault/secrets.vault.enc
어떻게: cd ada && make vault-set KEY=github.token
확인:   cd ada && make vault-list
```
