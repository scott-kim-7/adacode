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
