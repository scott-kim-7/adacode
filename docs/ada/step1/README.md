# Step 1 — 로컬 Qwen 72B + Cursor형 adacode

```bash
./scripts/adacode.sh
```

위 한 줄로 MLX 서버 + IDE를 함께 실행합니다. 상세: [README.md](../README.md#실행-step-1)

---

adacode(VS Code fork)에 **MLX Qwen2.5-VL-72B**를 연결해 Copilot Chat(BYOK Custom Endpoint)으로 Cursor와 같은 채팅·`#파일`·diff·Agent UX를 사용합니다.

## 사전 조건

- Phase 0 완료: `npm run compile`, `./scripts/code.sh`
- M4 Max 128GB 권장 (Qwen 72B Q4)
- Python 3.11+

## 1. MLX 환경 (최초 1회)

```bash
cd adacode
python3 -m venv .venv-mlx
source .venv-mlx/bin/activate
pip install -U mlx-lm
```

## 2. 모델 미리 받기 (선택, 권장)

IDE/서버 실행 전에 Hugging Face 캐시에만 받아 둘 수 있습니다. RAM에 올리지 않고 **다운로드만** 합니다.

```bash
./scripts/download-qwen-model.sh
```

약 **40GB+**, 중단 후 재실행하면 이어받기(resume)됩니다. 캐시 위치: `~/.cache/huggingface/hub`

검증:

```bash
./scripts/verify-qwen-download.sh          # 캐시만 (빠름, RAM 안 씀)
./scripts/verify-qwen-download.sh --smoke  # + MLX 서버에 한 줄 질의
```

## 3. MLX 서버 기동

```bash
./scripts/serve-qwen.sh
```

서버 첫 기동 시 캐시에 없으면 그때 다운로드합니다 (`download-qwen-model.sh` 로 미리 받아 두면 생략).

환경 변수:

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `ADA_MLX_MODEL` | `mlx-community/Qwen2.5-VL-72B-Instruct-4bit` | HF 모델 ID |
| `ADA_MLX_HOST` | `127.0.0.1` | 바인드 주소 |
| `ADA_MLX_PORT` | `8080` | 포트 |

헬스체크:

```bash
./scripts/verify-step1-mlx.sh
# 다른 모델로 테스트: ADA_MLX_MODEL=mlx-community/Qwen2.5-7B-Instruct-4bit ./scripts/verify-step1-mlx.sh
```

## 4. adacode BYOK 설정

### 4.1 GitHub 로그인 주의

BYOK는 **GitHub 미로그인** 상태에서 가장 단순합니다. Enterprise 정책으로 BYOK가 막힐 수 있습니다.

### 4.2 모델 등록

Command Palette → **Chat: Configure Language Models** → **Custom Endpoint** 그룹 추가

또는 예시 JSON을 사용자 프로필에 복사:

```bash
# Code-OSS 기본 프로필
PROFILE="$HOME/.vscode-oss/User"
mkdir -p "$PROFILE"
cp docs/ada/step1/chatLanguageModels.example.json "$PROFILE/chatLanguageModels.json"
```

Dev 빌드(`./scripts/code.sh`, `VSCODE_DEV=1`) 프로필:

- macOS: `~/Library/Application Support/code-oss-dev/User/`
- Linux: `~/.config/code-oss-dev/User/`

설치: `./scripts/install-step1.sh` (경로 자동 해석)

### 4.3 settings.json (권장)

[`settings.example.json`](settings.example.json) 내용을 사용자 `settings.json`에 추가:

```json
{
  "chat.agent.enabled": true
}
```

또는:

```bash
./scripts/install-step1.sh              # chatLanguageModels + settings.json
```

## 5. IDE 실행

```bash
# 터미널 1: MLX (이미 기동 중이면 생략)
./scripts/serve-qwen.sh

# 터미널 2
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 24.15.0
./scripts/code.sh
```

채팅 패널 → 모델 피커 → **Other Models** → **Qwen2.5-VL-72B-Instruct (MLX 4-bit)** → Agent 모드.

### 모델이 목록에 없을 때

BYOK 설정이 **잘못된 폴더**에 있으면 Qwen이 안 보입니다. macOS dev 빌드는:

`~/Library/Application Support/code-oss-dev/User/chatLanguageModels.json`

```bash
./scripts/install-step1.sh
# IDE 완전 종료(Cmd+Q) 후
./scripts/adacode.sh
```

모델 피커에서 **Other Models** 를 펼친 뒤 **Qwen2.5-VL-72B-Instruct (MLX 4-bit)** 를 선택하세요.

## 6. Cursor 대응 기능

| Cursor | adacode Step 1 |
|--------|----------------|
| `@file` | `#파일명` (채팅 입력 `#`) |
| Chat | Copilot Chat 패널 |
| Agent | `agent` participant |
| diff Accept | ChatEditing Accept |

## 7. Go/No-Go 체크리스트

- [x] `./scripts/verify-step1.sh` — 11/11 passed (2026-06-06)
- [x] Qwen 72B chat completion
- [x] BYOK + `chat.agent.enabled` 설치
- [ ] IDE에서 `./scripts/adacode.sh` → 채팅·`#파일`·diff·Agent (사용자 1회 확인)

완료 기록: [COMPLETE.md](COMPLETE.md)

## 트러블슈팅

[TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## 관련 파일

- [`scripts/verify-qwen-download.sh`](../../../scripts/verify-qwen-download.sh)
- [`scripts/download-qwen-model.sh`](../../../scripts/download-qwen-model.sh)
- [`scripts/serve-qwen.sh`](../../../scripts/serve-qwen.sh)
- [`chatLanguageModels.example.json`](chatLanguageModels.example.json)
- [BUILD.md](../BUILD.md)
