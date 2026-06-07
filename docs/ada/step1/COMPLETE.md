# Step 1 완료 기록

| 항목 | 값 |
|------|-----|
| 완료일 | 2026-06-06 |
| 커밋 | `9fce84bf` — feat(ada): Step 1 local MLX Qwen VL + BYOK integration |
| 모델 | `mlx-community/Qwen3-VL-32B-Instruct-8bit` |
| MLX endpoint | `http://127.0.0.1:8080/v1` |
| BYOK 프로필 | `~/Library/Application Support/code-oss-dev/User/chatLanguageModels.json` (macOS dev) |
| 검증 | `./scripts/verify-step1.sh` — 자동 항목 통과 (HF 캐시 단계 포함) |

## Go/No-Go (자동)

| # | 항목 | 상태 |
|---|------|------|
| 1 | MLX venv + mlx-lm | ✓ |
| 2 | `./scripts/adacode.sh` 통합 실행 | ✓ |
| 3 | BYOK Qwen VL 72B 등록 (flat schema) | ✓ |
| 4 | `chat.agent.enabled` | ✓ |
| 5 | IDE 빌드 산출물 | ✓ |
| 6 | MLX `/v1/models` | ✓ |
| 7 | Qwen 72B chat completion | ✓ |
| 8 | HF 캐시 (`verify-qwen-download.sh`) | ✓ |
| 9 | Step 1 문서 | ✓ |

## Go/No-Go (IDE — Step 1 성공 기준)

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 1 | 모델 피커 → **Other Models** → Qwen3-VL-32B-Instruct (MLX 8-bit) | ✓ | BYOK + adacodeLocalModels 패치 |
| 2 | Agent 모드 + 도구 호출 | ✓ | `toolCalling: true` |
| 3 | `#파일명` 컨텍스트 | ✓ | Cursor `@file` 대응 |
| 4 | diff Accept / Reject | ✓ | ChatEditing |
| 5 | **이미지 첨부** | ✓ | `mlx-vlm` 서버 (`serve-qwen.sh`) |

Step 1은 **텍스트 채팅·Agent·#파일·diff** 기준으로 **완료(Go)**. 이미지 입력은 Step 2 Tri-Chat / 별도 VL 경로에서 다룹니다.

## VL 이미지 — mlx-vlm 서버

- **이전:** `mlx_lm server`는 multimodal 거부 → `"Only 'text' content type is supported."`
- **현재:** `serve-qwen.sh` → **`python -m mlx_vlm.server`** (OpenAI `image_url` 지원)
- 검증: `./scripts/verify-step1-vision.sh`
- 구 서버가 남아 있으면: `./scripts/stop-mlx-server.sh` 후 재시작

상세: [TROUBLESHOOTING.md](TROUBLESHOOTING.md#채팅-이미지-첨부)

## §8 사용자 확인

| 확인 항목 | 결과 |
|-----------|------|
| `./scripts/adacode.sh` 로 IDE + MLX 동시 기동 | ✓ |
| Other Models 에 Qwen VL 표시 | ✓ |
| 텍스트 Agent·#파일·diff | ✓ |
| 이미지 첨부 | ✓ — mlx-vlm 서버 |

**Step 1 마무리: Go** — 2026-06-06

## 실행

```bash
./scripts/adacode.sh
```

재검증:

```bash
./scripts/install-step1.sh   # 설정 재적용
./scripts/verify-step1.sh    # 자동 검증 (HF 캐시 포함)
./scripts/verify-qwen-download.sh --smoke
```

## 다음 단계

Step 2 — `ada/` Model Registry, vault, 외부 LLM, Tri-Chat MVP. [step2/README.md](../step2/README.md)
