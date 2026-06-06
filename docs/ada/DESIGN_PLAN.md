# Ada: Cursor형 AI 동료 + 자기 소스코드 개선 — 실행 계획

> 저장소: `scott-kim-7/adacode`

## 최종 목표 (North Star)

**Cursor처럼 쓰는 로컬 AI 동료**가 있고, 사용자가 지시·승인하면 **그 AI 동료가 adacode 내 `ada/`·`extensions/ada-vscode/`의 Spec과 소스코드를 개선**한다.

### 성공 기준

1. **자체 빌드 Code-OSS** + ada 확장에서 **로컬 LLM** 채팅·@file
2. `/improve` → Agent Spec diff → eval → **Approve** → 동작 개선
3. `/improve-code ada/src/ada/...` → git branch patch → pytest+regression → **Approve** → merge
4. `make restore`로 특정 commit 복원
5. credential은 `ada/vault/secrets.vault.enc` **단일 파일**만

## 설계 원칙

1. **2단계 자기개선**: Agent Spec YAML → 소스코드
2. **사용자 지시·4단계 승인**
3. **운영 중 자동 수정 금지**
4. **회귀·자기개선 = 로컬 MLX 필수**
5. **단일 vault**
6. **Git + commits.db**
7. **IDE = Code-OSS 빌드 + ada 확장**
8. **Model Registry** — chat_profile / regression_profile 분리
9. **3자 Tri-Chat** (Phase 6)

## Phase 로드맵

| Phase | 기간 | 산출 | 4단계 Step |
|-------|------|------|------------|
| **Pre** | ✓ | 설계 문서 (ada_v1 → adacode 이전) | — |
| **0** | ✓ | adacode fork · clone · build · 실행 | Step 0 |
| **1** | 1주 | vault, MLX serve, `ada/` scaffold | **Step 2** |
| **2** | 2~3주 | Spec 자기개선 + web 4탭 | Step 4 |
| **3** | 2주 | Cursor형 web (@file, diff) | Step 2~3 |
| **4** | 3~4주 | ada-vscode → 빌드 IDE에 탑재 | Step 1 (BYOK) |
| **5** | 3~4주 | 소스코드 자기개선 | Step 4 |
| **6** | 2~3주 | @codebase RAG + Tri-Chat | **Step 2** |
| **7** | 선택 | product.json 브랜딩 | — |

> **4단계 vs Phase:** Step 1(로컬 LLM IDE)은 Phase 4 BYOK로 달성. Step 2(Tri-Chat)는 Phase 1 scaffold + Phase 6. 상세: [SUMMARY.md](SUMMARY.md)

## 저장소 구조

```
adacode/
├── extensions/ada-vscode/
├── ada/
│   ├── config/
│   ├── vault/
│   ├── specs/agent/
│   ├── src/ada/
│   └── web/
└── docs/ada/
```

## 3그래프

| 그래프 | 역할 |
|--------|------|
| **MainGraph** | route → plan → respond → verify |
| **ImprovementGraph** | sample → RCA → patch → candidate_spec |
| **EvalGraph** | golden 케이스 + hybrid evaluator |

자동 promote 없음 — 사용자 **4단계 승인**.

---

[SUMMARY.md](SUMMARY.md) | [BUILD.md](BUILD.md)
