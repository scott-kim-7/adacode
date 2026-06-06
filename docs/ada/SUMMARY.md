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

## Phase 로드맵

| Phase | 내용 |
|-------|------|
| **0** | ✓ adacode fork·빌드·실행 |
| **1** | vault, MLX, `ada/` scaffold |
| **2** | Spec 자기개선 + web UI |
| **3** | Cursor형 web |
| **4** | ada-vscode |
| **5** | 소스코드 자기개선 |
| **6** | RAG + Tri-Chat |

## 정책

- `regression_profile`: 로컬 MLX 고정
- vault: `ada/vault/secrets.vault.enc`
- Node **24.15.0+**, **npm** (yarn 미지원)
