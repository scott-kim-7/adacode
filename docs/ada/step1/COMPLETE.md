# Step 1 완료 기록 (아카이브)

> VS Code fork + BYOK 시절의 Go/No-Go 기록입니다.  
> 현재는 **web-only** — [docs/ada/README.md](../README.md)

| 항목 | 값 |
|------|-----|
| 완료일 | 2026-06-06 |
| 커밋 | `9fce84bf` — feat(ada): Step 1 local MLX VL + BYOK integration |
| 모델 | OpenAPI `GET /v1/models` (소스에 하드코딩 없음) |
| MLX endpoint | `http://127.0.0.1:8080/v1` (외부 기동) |
| BYOK 프로필 | `~/Library/Application Support/code-oss-dev/User/chatLanguageModels.json` (macOS dev) |
| 검증 | `./scripts/verify-step1.sh` |

## Go/No-Go (자동)

| # | 항목 | 상태 |
|---|------|------|
| 1 | MLX venv + mlx-lm / mlx-vlm | ✓ |
| 2 | MLX `/v1/models` | ✓ |
| 3 | BYOK 로컬 LLM 등록 (flat schema) | ✓ |
| 4 | `chat.agent.enabled` | ✓ |
| 5 | HF 캐시 (`verify-mlx-download.sh`) | ✓ |
| 6 | Step 1 문서 | ✓ |

## Go/No-Go (IDE — 당시 성공 기준)

| # | 항목 | 상태 |
|---|------|------|
| 1 | 모델 피커 → Other Models → 로컬 LLM | ✓ |
| 2 | Agent 모드 + 도구 호출 | ✓ |
| 3 | `#파일명` 컨텍스트 | ✓ |
| 4 | diff Accept / Reject | ✓ |
| 5 | 이미지 첨부 (mlx-vlm) | ✓ |

## VL 이미지

- **text-only `mlx_lm`:** multimodal 거부
- **vision `mlx-vlm`:** OpenAI `image_url` 지원
- 검증: `./scripts/verify-step1-vision.sh`

상세: [TROUBLESHOOTING.md](TROUBLESHOOTING.md#채팅-이미지-첨부)

## 재검증 (현재 스크립트명)

```bash
./scripts/install-step1.sh
./scripts/verify-step1.sh
export ADA_MLX_MODEL=org/repo-name
./scripts/verify-mlx-download.sh --smoke
```

## 다음 단계

Step 2 — Model Registry, vault, Tri-Chat. [step2/README.md](../step2/README.md)
