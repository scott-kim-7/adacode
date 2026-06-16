# Step 1 — 로컬 MLX + VS Code fork (아카이브)

> **2026-06:** 메인 UI는 **Open WebUI** (`./scripts/ada.sh`)로 전환되었습니다.  
> Step 1은 adacode(VS Code fork) + Copilot BYOK 시절의 기록입니다.  
> 현재 운영 가이드: [docs/ada/README.md](../README.md), [web/README.md](../web/README.md)

---

adacode(VS Code fork)에 **로컬 MLX OpenAPI 서버**를 연결해 Copilot Chat(BYOK Custom Endpoint)으로 Cursor형 채팅·`#파일`·diff·Agent UX를 사용했습니다.

**모델 ID는 소스에 하드코딩하지 않습니다.** BYOK JSON의 `id`는 `GET http://127.0.0.1:8080/v1/models` 응답의 첫 항목과 일치해야 합니다. 예시는 [`chatLanguageModels.example.json`](chatLanguageModels.example.json) 참고.

## 사전 조건 (당시)

- Phase 0: `npm run compile`, `./scripts/code.sh`
- Apple Silicon + 충분한 RAM
- Python 3.11+

## 1. MLX 환경 (최초 1회)

```bash
cd adacode
python3 -m venv .venv-mlx   # 또는 ./scripts/ensure-mlx-venv.sh
source .venv-mlx/bin/activate
pip install -U mlx-lm mlx-vlm
```

## 2. 모델 미리 받기 (선택)

HF 캐시에만 다운로드 (RAM 로드 없음):

```bash
export ADA_MLX_MODEL=org/repo-name   # Hugging Face repo id
./scripts/download-mlx-model.sh
```

검증:

```bash
./scripts/verify-mlx-download.sh          # 캐시만
./scripts/verify-mlx-download.sh --smoke  # + :8080 OpenAPI 한 줄 질의
```

## 3. LLM 서버 (외부 기동)

Ada는 **MLX 서버를 기동·종료하지 않습니다.** `mlx_lm` 또는 `mlx-vlm`을 별도로 `:8080`에 띄운 뒤:

```bash
curl -sf http://127.0.0.1:8080/v1/models
```

환경 변수:

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `ADA_MLX_MODEL` | *(필수, 다운로드 시)* | HF repo id — `download-mlx-model.sh` |
| `ADA_MLX_DISPLAY_NAME` | `$ADA_MLX_MODEL` | 캐시 검증 표시 이름 |
| `ADA_MLX_HOST` | `127.0.0.1` | 바인드 주소 |
| `ADA_MLX_PORT` | `8080` | OpenAPI 포트 |

헬스체크:

```bash
./scripts/verify-step1-mlx.sh
./scripts/verify-step1-vision.sh
```

## 4. adacode BYOK 설정

Command Palette → **Chat: Configure Language Models** → **Custom Endpoint**

```bash
./scripts/install-step1.sh
```

예시 JSON: [`chatLanguageModels.example.json`](chatLanguageModels.example.json)

## 5. IDE 실행 (아카이브)

```bash
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 24.15.0
./scripts/code.sh
```

모델 피커 → **Other Models** → BYOK에 등록한 로컬 LLM 표시 이름 선택.

## Go/No-Go

완료 기록: [COMPLETE.md](COMPLETE.md)

## 트러블슈팅

[TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## 관련 파일

- [`scripts/download-mlx-model.sh`](../../../scripts/download-mlx-model.sh)
- [`scripts/verify-mlx-download.sh`](../../../scripts/verify-mlx-download.sh)
- [`scripts/ada.sh`](../../../scripts/ada.sh) — 현재 web 스택 (Agent + Open WebUI)
- [`chatLanguageModels.example.json`](chatLanguageModels.example.json)
