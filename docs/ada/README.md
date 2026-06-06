# Ada — Cursor형 로컬 AI 동료

**Apple Silicon (M4 Max) + MLX 로컬 LLM** 위에서 동작하며, 사용자 지시·승인 하에 **자신의 Agent Spec과 소스코드를 개선**하는 AI 동료 플랫폼.

## 실행 (Step 1)

저장소 루트에서 **한 줄**로 adacode를 실행합니다. MLX Qwen 서버를 백그라운드로 띄운 뒤 IDE를 엽니다.

```bash
cd adacode
./scripts/adacode.sh
```

**최초 1회** (자동 처리되지 않는 항목):

```bash
npm install && npm run compile          # IDE 빌드 (Step 0)
./scripts/install-step1.sh              # BYOK + settings (adacode.sh도 자동 실행)
./scripts/verify-step1.sh               # Step 1 자동 검증
```

IDE가 열리면 채팅 패널 → **Qwen2.5-VL-72B-Instruct (MLX 4-bit)** 선택 → Agent 모드. 파일 참조는 `#파일명` (Cursor `@file`과 동일).

옵션:

| 환경 변수 | 기본값 | 설명 |
|-----------|--------|------|
| `ADA_MLX_MODEL` | `mlx-community/Qwen2.5-VL-72B-Instruct-4bit` | MLX 모델 ID |
| `ADA_MLX_PORT` | `8080` | MLX 포트 |
| `ADA_MLX_WAIT_TRIES` | `120` | 서버 준비 대기 (×2초) |

IDE만 실행 (로컬 LLM 없이): `./scripts/code.sh`

> **단일 저장소**: IDE·AI 엔진·확장·문서는 모두 [scott-kim-7/adacode](https://github.com/scott-kim-7/adacode)에 있습니다.  
> (구 `ada_v1` 저장소는 2026-06-06 이전됨)

## 문서

| 문서 | 설명 |
|------|------|
| [BUILD.md](BUILD.md) | **Phase 0** — adacode fork·빌드·실행 |
| [DESIGN_PLAN.md](DESIGN_PLAN.md) | 전체 설계·Phase 0~7 실행 계획 |
| [SUMMARY.md](SUMMARY.md) | 기획 요약 (의사결정 기록) |
| [VAULT.md](VAULT.md) | 계정·비밀번호 단일 vault 정책 |
| [step1/README.md](step1/README.md) | **Step 1** — 로컬 Qwen 72B + Cursor형 adacode |
| [COMMITS.md](COMMITS.md) | 커밋·스냅샷 규칙 |

## 현재 상태

- **Step 0 완료** — fork·`npm run compile`·`./scripts/code.sh`
- **Step 1 완료** — 로컬 Qwen 72B + BYOK + `./scripts/adacode.sh` ([완료 기록](step1/COMPLETE.md))
- **Step 2 다음** — 외부 LLM + Tri-Chat
- 하드웨어: MacBook Pro M4 Max, 128GB RAM

## 빠른 시작 (Step 1 — 수동)

MLX·IDE를 각각 띄우려면:

```bash
./scripts/adacode.sh    # 권장: 위 「실행」 절 참고

# 또는 수동:
./scripts/serve-qwen.sh
./scripts/install-step1-chat-models.sh   # 최초 1회
./scripts/code.sh
```

자세한 절차: [step1/README.md](step1/README.md)

## 빠른 시작 (Phase 0 — IDE만)

```bash
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 24.15.0
cd adacode
./scripts/code.sh
```

### AI 플랫폼 (Step 2+ — ada/ Python)

```bash
cd adacode/ada
make vault-init && make serve
open http://127.0.0.1:8080/ui
```

## North Star

1. 자체 빌드 Code-OSS + ada 확장에서 **로컬 LLM** 채팅·@file
2. `/improve` → Spec diff → Approve → 동작 개선
3. `/improve-code` → git branch patch → pytest+regression → Approve → merge
4. `make restore`로 특정 commit 복원

## 저장소 구조

```
adacode/
├── extensions/ada-vscode/   # Phase 4: 채팅·Improve UI
├── ada/                     # AI 동료 플랫폼 (Phase 1~)
│   ├── config/
│   ├── vault/
│   ├── specs/agent/
│   ├── src/ada/
│   └── web/
└── docs/ada/                # 본 문서
```
