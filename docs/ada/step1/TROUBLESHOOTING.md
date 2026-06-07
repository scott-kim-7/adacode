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
      "id": "mlx-community/Qwen3-VL-32B-Instruct-8bit",
      "name": "Qwen3-VL-32B-Instruct (MLX 8-bit)",
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
4. 모델 피커 → **Other Models** → **Qwen3-VL-32B-Instruct (MLX 8-bit)**

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

Qwen3-VL 32B 8-bit는 M4 Max 128GB에서 **10~20 tok/s** 가 정상입니다.

## OOM / swap

- `ADA_MLX_MODEL=mlx-community/Qwen3-VL-32B-Instruct-8bit` (기본)
- 이전 Thinking: `ADA_MLX_MODEL=mlx-community/Qwen3-VL-32B-Thinking-4bit`
- 이전 72B: `ADA_MLX_MODEL=mlx-community/Qwen2.5-VL-72B-Instruct-4bit`
- 다른 heavy 앱 종료
- 짧은 컨텍스트 사용

## copilot compile 실패

[BUILD.md](../BUILD.md) — `.pnp.cjs`, `.yarn` 삭제 후 `extensions/copilot` 에서 `npm install`

## BYOK 정책 (`isClientBYOKAllowed`)

adacode fork에서는 **항상 허용** (`return true`). upstream VS Code/Copilot Enterprise 정책은 적용되지 않습니다.

## 채팅 이미지 첨부

**2026-06-06 이후:** `serve-qwen.sh` / `adacode.sh`는 **`mlx-vlm` 서버**를 사용합니다. OpenAI `image_url` 형식을 지원합니다.

**증상:** `"Only 'text' content type is supported."`

**원인:** 예전 **`mlx_lm` text-only 서버**가 아직 포트 8080에서 실행 중입니다.

**해결**

```bash
./scripts/stop-mlx-server.sh
./scripts/ensure-mlx-venv.sh    # mlx-vlm 설치
./scripts/serve-qwen.sh         # 또는 ./scripts/adacode.sh
./scripts/verify-step1-vision.sh
```

**수동 확인:** IDE 채팅에 이미지 첨부 → Qwen VL 모델 선택 → 설명 요청.

**참고:** VL 모델 첫 로드는 수 분·수십 GB RAM 사용. 텍스트만 필요하면 `mlx_lm`을 쓸 수 있지만 adacode 기본은 **mlx-vlm**입니다.

## 이미지 첨부 후 응답이 비어 있거나 오래 걸림

**증상:** 에러는 없지만 assistant 버블이 비어 있거나, 1~2분 동안 아무 텍스트가 안 보임.

**원인**

1. **Qwen VL 72B + 이미지 prefill이 매우 느림** — 첫 토큰까지 **30~90초** 흔함 (768px 이미지 기준). 그동안 UI는 로딩만 표시.
2. **구 BYOK 설정** — `"streaming": true` + `max_tokens` 미전송 시 IDE에서 빈 응답처럼 보일 수 있음.
3. **Agent 모드** — 모델이 텍스트 없이 tool call만 반환하면 채팅에 글이 안 보일 수 있음.

**해결**

```bash
./scripts/install-step1.sh          # streaming:false, maxOutputTokens 갱신
./scripts/stop-mlx-server.sh
./scripts/adacode.sh
```

- **이미지 설명만:** **Ask** 모드 (Agent 아님) 권장.
- **1~2분 대기** 후에도 비어 있으면: `.ada-mlx-server.log` 확인, `./scripts/verify-step1-vision.sh` 실행.
- 더 빠른 vision: `ADA_MLX_MODEL=mlx-community/Qwen2.5-VL-7B-Instruct-4bit` (품질↓, 속도↑).
