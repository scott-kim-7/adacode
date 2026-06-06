# Step 1 완료 기록

| 항목 | 값 |
|------|-----|
| 완료일 | 2026-06-06 |
| 커밋 | `9fce84bf` — feat(ada): Step 1 local MLX Qwen VL + BYOK integration |
| 모델 | `mlx-community/Qwen2.5-VL-72B-Instruct-4bit` |
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
| 1 | 모델 피커 → **Other Models** → Qwen2.5-VL-72B-Instruct (MLX 4-bit) | ✓ | BYOK + adacodeLocalModels 패치 |
| 2 | Agent 모드 + 도구 호출 | ✓ | `toolCalling: true` |
| 3 | `#파일명` 컨텍스트 | ✓ | Cursor `@file` 대응 |
| 4 | diff Accept / Reject | ✓ | ChatEditing |
| 5 | **이미지 첨부** | ✗ (예상) | mlx_lm OpenAI 서버 한계 — **Step 2+** |

Step 1은 **텍스트 채팅·Agent·#파일·diff** 기준으로 **완료(Go)**. 이미지 입력은 Step 2 Tri-Chat / 별도 VL 경로에서 다룹니다.

## 알려진 한계 — VL 이미지 (옵션 A)

- 모델 ID에 VL이 포함돼 있고 BYOK에 `"vision": true` 이지만, **mlx_lm `server.py`는 multimodal content를 거부**합니다.
- 증상: `"Only 'text' content type is supported."`
- 원인: Copilot BYOK → `127.0.0.1:8080` 까지 이미지를 보내려 하지만 서버 `process_message_content()` 가 text만 허용.
- 대응: Step 1에서는 문서화만. Step 2+ 에서 VL 전용 inference 또는 Tri-Chat 역할 분담(로컬=이미지, 외부=텍스트) 검토.

상세: [TROUBLESHOOTING.md](TROUBLESHOOTING.md#채팅-이미지-첨부-실패)

## §8 사용자 확인

| 확인 항목 | 결과 |
|-----------|------|
| `./scripts/adacode.sh` 로 IDE + MLX 동시 기동 | ✓ |
| Other Models 에 Qwen VL 표시 | ✓ |
| 텍스트 Agent·#파일·diff | ✓ |
| 이미지 첨부 | ✗ — Step 2+ 로 이관 (문서화 완료) |

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
