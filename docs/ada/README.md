# Ada — Cursor형 로컬 AI 동료

**Apple Silicon (M4 Max) + MLX 로컬 LLM** 위에서 동작하며, 사용자 지시·승인 하에 **자신의 Agent Spec과 소스코드를 개선**하는 AI 동료 플랫폼.

> **단일 저장소**: IDE·AI 엔진·확장·문서는 모두 [scott-kim-7/adacode](https://github.com/scott-kim-7/adacode)에 있습니다.  
> (구 `ada_v1` 저장소는 2026-06-06 이전됨)

## 문서

| 문서 | 설명 |
|------|------|
| [BUILD.md](BUILD.md) | **Phase 0** — adacode fork·빌드·실행 |
| [DESIGN_PLAN.md](DESIGN_PLAN.md) | 전체 설계·Phase 0~7 실행 계획 |
| [SUMMARY.md](SUMMARY.md) | 기획 요약 (의사결정 기록) |
| [VAULT.md](VAULT.md) | 계정·비밀번호 단일 vault 정책 |
| [COMMITS.md](COMMITS.md) | 커밋·스냅샷 규칙 |

## 현재 상태

- **Phase 0 완료** — `scott-kim-7/adacode` fork·clone·`npm run compile`·`./scripts/code.sh` 검증
- **Phase 1 다음** — `ada/` Python 스캐폴딩, vault, MLX serve
- 하드웨어: MacBook Pro M4 Max, 128GB RAM

## 빠른 시작

### IDE 실행

```bash
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 24.15.0
cd adacode
./scripts/code.sh
```

### AI 플랫폼 (Phase 1~)

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
