# Step 1 트러블슈팅

> Step 1은 VS Code fork + BYOK 시절 문서입니다. **현재 web 스택**은 [web/README.md](../web/README.md)를 보세요.

## 모델 피커에 Other Models / 로컬 LLM이 없음

**가장 흔한 원인**

1. **`chatLanguageModels.json` 형식 오류** — `models` / `apiKey` 를 `"configuration": { ... }` 안에 넣으면 무시됩니다.
2. IDE 재시작/Reload 없음
3. `id`가 `GET /v1/models` 응답과 불일치

**올바른 JSON (flat)**

```json
{
  "vendor": "customendpoint",
  "name": "Local LLM",
  "apiKey": "local",
  "apiType": "chat-completions",
  "models": [
    {
      "id": "openapi-resolved",
      "name": "Local LLM (from GET /v1/models)",
      "url": "http://127.0.0.1:8080",
      "toolCalling": true
    }
  ]
}
```

`id` / `name`은 실제 `curl http://127.0.0.1:8080/v1/models` 결과에 맞게 바꿉니다.

**해결 순서**

1. `./scripts/install-step1.sh`
2. IDE **완전 종료**(Cmd+Q) 후 재실행
3. **Developer: Reload Window**
4. 모델 피커 → **Other Models** → 등록한 로컬 LLM

## Language model unavailable

1. LLM 서버가 `:8080`에서 응답하는지 확인: `curl http://127.0.0.1:8080/v1/models`
2. JSON `url`은 base만: `http://127.0.0.1:8080` (경로 붙이지 않음)
3. Ada web 스택: `./scripts/ada.sh status`

## Agent 도구 호출 실패

`chatLanguageModels.example.json` 에서:

```json
"toolCalling": true,
"editTools": ["apply-patch", "code-rewrite"]
```

## 응답이 매우 느림

대형 VL 모델은 Apple Silicon에서 첫 토큰까지 수십 초 걸릴 수 있습니다. 더 작은 HF repo id로 `ADA_MLX_MODEL`을 바꿔 재다운로드할 수 있습니다.

## OOM / swap

- `ADA_MLX_MODEL`을 더 작은 양자화 모델로 변경 후 `./scripts/download-mlx-model.sh`
- 다른 heavy 앱 종료
- 짧은 컨텍스트 사용

## copilot compile 실패

[BUILD.md](../BUILD.md) — `.pnp.cjs`, `.yarn` 삭제 후 `extensions/copilot` 에서 `npm install`

## BYOK 정책 (`isClientBYOKAllowed`)

adacode fork에서는 **항상 허용** (`return true`).

## 채팅 이미지 첨부

**증상:** `"Only 'text' content type is supported."`

**원인:** **`mlx_lm` text-only 서버**가 포트 8080에서 실행 중.

**해결:** vision 지원 `mlx-vlm` 서버로 `:8080`을 교체한 뒤:

```bash
./scripts/verify-step1-vision.sh
```

**Open WebUI (현재):** `./scripts/verify-agent-vision.sh` — agent API(:8082) multimodal smoke test.

## 이미지 첨부 후 응답이 비어 있거나 오래 걸림

1. VL + 이미지 prefill이 느림 — 첫 토큰까지 **30~90초** 흔함
2. 구 BYOK 설정 — `"streaming": true` + `max_tokens` 미전송 시 빈 응답처럼 보일 수 있음
3. Agent 모드 — tool call만 반환하면 채팅에 글이 안 보일 수 있음

**해결**

```bash
./scripts/install-step1.sh
./scripts/ada.sh restart    # web 스택
```

- **이미지 설명만:** Ask 모드 권장
- `./scripts/verify-step1-vision.sh` / `./scripts/verify-agent-vision.sh` 로 단계별 확인
