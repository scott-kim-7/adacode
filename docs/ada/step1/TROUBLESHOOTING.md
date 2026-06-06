# Step 1 트러블슈팅

## 모델 피커에 Other Models / Qwen이 없음

**Other Models** 섹션은 Copilot 클라우드 모델(GPT, Haiku 등) 중 **Promoted에 안 들어간 모델**이 있거나, **Custom Endpoint BYOK**가 등록됐을 때만 나타납니다. Promoted만 있으면 섹션 자체가 사라질 수 있습니다.

**가장 흔한 원인**

1. **`chatLanguageModels.json` 형식 오류** — `models` / `apiKey` 를 `"configuration": { ... }` 안에 넣으면 VS Code가 **완전히 무시**합니다 (Other Models에 GPT만 보이고 Qwen은 절대 안 뜸).
2. IDE 재시작/Reload 없음
3. Copilot 확장 미재컴파일

**올바른 JSON (flat)**

```json
{
  "vendor": "customendpoint",
  "name": "Local Qwen",
  "apiKey": "local",
  "apiType": "chat-completions",
  "models": [
    {
      "id": "mlx-community/Qwen2.5-VL-72B-Instruct-4bit",
      "name": "Qwen2.5-VL-72B-Instruct (MLX 4-bit)",
      "url": "http://127.0.0.1:8080",
      "toolCalling": true
    }
  ]
}
```

**해결 순서**

1. `./scripts/install-step1.sh`  ← flat JSON 재설치
2. IDE **완전 종료**(Cmd+Q) 후 `./scripts/adacode.sh`
3. **Developer: Reload Window**
4. 모델 피커 → **Other Models** → **Qwen2.5-VL-72B-Instruct (MLX 4-bit)**

**Manage Models...** 가 보이면 Other Models 대신 하단/검색창 옆 톱니에서 BYOK 설정을 열 수 있습니다.

## 모델 피커에 Custom Endpoint / Qwen이 없음 (BYOK 미등록)

위 **flat JSON** 절을 확인하세요. `./scripts/install-step1.sh` 로 재설치하면 됩니다.

1. `./scripts/install-step1.sh`
2. `./scripts/adacode.sh` (IDE 재시작)
3. **Developer: Reload Window**
4. macOS 프로필: `~/Library/Application Support/code-oss-dev/User/chatLanguageModels.json`

## Language model unavailable

1. `./scripts/serve-qwen.sh` 가 **먼저** 실행 중인지 확인
2. `curl http://127.0.0.1:8080/v1/models`
3. JSON `url`은 base만: `http://127.0.0.1:8080` (경로 붙이지 않음)

## Agent 도구 호출 실패

`chatLanguageModels.example.json` 에서:

```json
"toolCalling": true,
"editTools": ["apply-patch", "code-rewrite"]
```

## 응답이 매우 느림

Qwen 72B Q4는 M4 Max 128GB에서 **8~15 tok/s** 가 정상입니다.

## OOM / swap

- `ADA_MLX_MODEL=mlx-community/Qwen2.5-VL-72B-Instruct-4bit` (Q4 유지)
- 다른 heavy 앱 종료
- 짧은 컨텍스트 사용

## copilot compile 실패

[BUILD.md](../BUILD.md) — `.pnp.cjs`, `.yarn` 삭제 후 `extensions/copilot` 에서 `npm install`

## BYOK 정책 (`isClientBYOKAllowed`)

adacode fork에서는 **항상 허용** (`return true`). upstream VS Code/Copilot Enterprise 정책은 적용되지 않습니다.

## 채팅 이미지 첨부 실패

**증상:** 이미지를 채팅에 붙이면 `"Only 'text' content type is supported."` 또는 유사 오류.

**원인 (모델 문제 아님):** `mlx_lm` OpenAI-compatible 서버(`serve-qwen.sh` → `mlx_lm.server`)가 **text content만** 처리합니다. BYOK JSON에 `"vision": true` 가 있어도 서버가 `image_url` / multimodal part를 거부합니다.

Copilot BYOK 경로(`CopilotLanguageModelWrapper` → `http://127.0.0.1:8080`)까지는 이미지 전송을 시도하지만, 서버 `process_message_content()` 에서 차단됩니다.

**Step 1 정책 (옵션 A):** 텍스트·Agent·`#파일`·diff는 정상. **이미지는 Step 1 범위 밖** — [COMPLETE.md](COMPLETE.md) Go/No-Go 참고.

**Step 2+ 대안:**

| 방향 | 설명 |
|------|------|
| VL 전용 경로 | mlx_lm 서버 패치 또는 별도 VL inference 스크립트 |
| Tri-Chat 역할 분담 | 로컬=이미지 처리, 외부 LLM=텍스트 요약 (ada orchestration) |
| 텍스트 전용 모델 | Step 1 기본을 `Qwen2.5-72B-Instruct-4bit` 로 두고 VL은 Step 2에서 분리 |

**당장 우회:** 이미지 대신 **텍스트로 설명**하거나, OCR 결과를 붙여 질의하세요.
