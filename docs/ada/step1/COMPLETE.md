# Step 1 완료 기록

| 항목 | 값 |
|------|-----|
| 완료일 | 2026-06-06 |
| 모델 | `mlx-community/Qwen2.5-VL-72B-Instruct-4bit` |
| MLX endpoint | `http://127.0.0.1:8080/v1` |
| BYOK 프로필 | `~/Library/Application Support/code-oss-dev/User/chatLanguageModels.json` (macOS) |
| 검증 | `./scripts/verify-step1.sh` — **11/11 passed** |

## Go/No-Go

| # | 항목 | 상태 |
|---|------|------|
| 1 | MLX venv + mlx-lm | ✓ |
| 2 | `./scripts/adacode.sh` 통합 실행 | ✓ |
| 3 | BYOK Qwen 72B 등록 | ✓ |
| 4 | `chat.agent.enabled` | ✓ |
| 5 | IDE 빌드 산출물 | ✓ |
| 6 | MLX `/v1/models` | ✓ |
| 7 | Qwen 72B chat completion | ✓ |
| 8 | IDE 채팅·`#파일`·diff·Agent | 사용자 `./scripts/adacode.sh` 로 확인 |

## 실행

```bash
./scripts/adacode.sh
```

재검증:

```bash
./scripts/install-step1.sh   # 설정 재적용
./scripts/verify-step1.sh    # 자동 검증
```
