# Ada 기획 요약

## 목표

- **Cursor형 UI** + **로컬 AI 동료** + **자기 Spec/소스코드 개선**
- M4 Max 128GB + MLX 로컬 LLM
- **단일 저장소** `scott-kim-7/adacode`

## 저장소 전략 (2026-06-06)

| 이전 | 현재 |
|------|------|
| ada_v1 + adacode (2 repo) | **adacode 하나** |
| ada_v1/docs/ | adacode/docs/ada/ |
| src/ada/ | adacode/ada/src/ada/ |

## Phase 0 (완료)

- Fork: https://github.com/scott-kim-7/adacode
- commit: `6a4e80f4`
- [BUILD.md](BUILD.md)

## 4단계 로드맵 (사용자-facing)

| Step | 내용 | 상태 |
|------|------|------|
| **0** | adacode fork·빌드·실행 | ✓ |
| **1** | 로컬 Qwen + Cursor형 IDE (채팅·#파일·diff·Agent) | ✓ |
| **1b** | Step 1 마무리 — Go/No-Go, VL 이미지 한계 문서화 | ✓ |
| **2** | Model Registry + 외부 LLM + **3자 Tri-Chat** | 진행 중 |
| **3** | 자율 Agent (계획·실행·검증) | — |
| **4** | adacode 자기개선 (`/improve`, `/improve-code`) | — |

## Phase 로드맵 (DESIGN_PLAN 구현 세부)

| Phase | 내용 | Step 매핑 |
|-------|------|-----------|
| **0** | ✓ adacode fork·빌드·실행 | Step 0 |
| **1** | vault, MLX serve, `ada/` scaffold | Step 2 |
| **2** | Spec 자기개선 + web 4탭 | Step 4 |
| **3** | Cursor형 web (@file, diff) | Step 2~3 |
| **4** | ada-vscode → 빌드 IDE | Step 1 (Copilot BYOK) |
| **5** | 소스코드 자기개선 | Step 4 |
| **6** | RAG + Tri-Chat | Step 2 |
| **7** | product.json 브랜딩 | 선택 |

## 정책

- `chat_profile`: IDE·Tri-Chat 기본 대화 — 로컬 MLX (`127.0.0.1:8080`)
- `external_profile`: 외부 API LLM — vault 키 (`external.*`)
- `regression_profile`: 로컬 MLX 고정 (Step 4 회귀)
- vault: `ada/vault/secrets.vault.enc`
- Node **24.15.0+**, **npm** (yarn 미지원)
