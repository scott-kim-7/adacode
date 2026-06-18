# Ada Regression Benchmarks — 소개 및 실행 방법

Contract regression(22 tests, mock)과 별도로, **실제 Agent API (`:9082`) + MLX** 를 경유해 5개 업계 벤치마크를 돌리는 **Eval regression** 계층입니다.

| 구분 | 대상 | 시간 |
|------|------|------|
| Contract | API·MainGraph 계약 | ~0.3초 |
| **Eval regression (본 문서)** | 5종 agent benchmark | smoke ~10–30분 |

모든 벤치는 동일 스택을 사용합니다.

```
벤치 스크립트 → adapter → Agent API :9082 → ToolAgentGraph → MLX :8080
```

---

## 공통 사전 준비

```bash
# repo 루트에서
./scripts/ada.sh start          # MLX :8080 + Agent :9082

# (선택) 공식 vendor runner 사용 시
./scripts/eval/install-vendors.sh
```

환경 변수 (기본값으로 보통 설정 불필요):

```bash
export ADA_EVAL_BASE_URL=http://127.0.0.1:9082/v1
export ADA_AGENT_PROFILE=chat_profile
export ADA_EVAL_VENDOR_ROOT=$PWD/.eval/vendor
```

### smoke vs full

| 모드 | 의미 | 예상 시간 (로컬 MLX 32B) |
|------|------|--------------------------|
| **smoke** | 소량 태스크, 회귀·연동 검증 | 벤치당 수초~수분, 전체 ~10–30분 |
| **full** | `eval.yaml` full 설정 (확대 harness) | 벤치당 수분~수십분 |

> vendor 미설치 시 **harness-fallback**으로 동작합니다. 빠르게 끝나면 공식 full이 아닐 수 있습니다.  
> 결과 JSON의 `extra.fallback_reason`과 `ada/src/ada/eval/logs/` 를 확인하세요.

### 5개 한번에 실행

```bash
./scripts/verify-regression-full.sh
./scripts/verify-regression-full.sh --update-baseline   # baseline 갱신
```

---

## 1. τ²-bench (Tau-squared)

### 소개

멀티턴 대화형 에이전트 벤치마크입니다. 고객 서비스 시나리오(항공·리테일·통신 등)에서 **user proxy + 도구 호출**을 평가합니다. BFCL이 단발성 함수 호출에 가깝다면, τ²는 **대화 흐름 전체**를 봅니다.

| 항목 | 값 |
|------|-----|
| **Adapter** | [`ada/src/ada/eval/adapters/tau2_adapter.py`](../../../ada/src/ada/eval/adapters/tau2_adapter.py) |
| **Vendor** | [amazon-agi/tau2-bench-verified](https://github.com/amazon-agi/tau2-bench-verified) |
| **Smoke** | mock 도메인, 5 tasks |
| **Full** | airline/retail/telecom/mock, 50 tasks |

### 실행

```bash
./scripts/eval/run-tau2-smoke.sh
./scripts/eval/run-tau2-full.sh
```

### 산출물

| 파일 | 설명 |
|------|------|
| `ada/src/ada/eval/results/tau2-smoke.json` | 점수·pass_rate |
| `ada/src/ada/eval/reports/benchmark-tau2-smoke-latest.md` | 리포트 |
| `ada/src/ada/eval/logs/benchmarks/*-tau2-*.log` | 실행 로그 |

---

## 2. BFCL v4 (Berkeley Function-Calling Leaderboard)

### 소개

함수/툴 호출 정확도의 de facto 표준 벤치마크입니다. Python/Java/JS 함수 호출, 병렬 호출, AST 매칭·실행 테스트 등을 포함합니다. v4(Agentic)는 멀티스텝 tool-use 시나리오를 강화합니다.

| 항목 | 값 |
|------|-----|
| **Adapter** | [`ada/src/ada/eval/adapters/bfcl_adapter.py`](../../../ada/src/ada/eval/adapters/bfcl_adapter.py) |
| **Vendor** | [ShishirPatil/gorilla](https://github.com/ShishirPatil/gorilla) → `berkeley-function-call-leaderboard` |
| **Smoke** | `simple_python`, 10 entries |
| **Full** | `simple_python`, 100 entries |

### 실행

```bash
./scripts/eval/run-bfcl-smoke.sh
./scripts/eval/run-bfcl-full.sh
```

### 산출물

| 파일 | 설명 |
|------|------|
| `ada/src/ada/eval/results/bfcl-smoke.json` | 점수·pass_rate |
| `ada/src/ada/eval/reports/benchmark-bfcl-smoke-latest.md` | 리포트 |
| `ada/src/ada/eval/logs/subprocess/*-bfcl-*.log` | vendor subprocess 로그 |

> BFCL smoke는 MLX 호출이 많아 **수 분~십 수 분** 걸릴 수 있습니다.

---

## 3. SWE-bench Verified

### 소개

GitHub 이슈를 읽고 **코드 패치를 생성·적용**해 테스트를 통과하는지 보는 코딩 에이전트 벤치마크입니다. Verified subset(500 instances)이 업계 표준입니다. Docker 기반 sandbox가 일반적입니다.

| 항목 | 값 |
|------|-----|
| **Adapter** | [`ada/src/ada/eval/adapters/swe_adapter.py`](../../../ada/src/ada/eval/adapters/swe_adapter.py) |
| **Vendor** | [SWE-bench/SWE-bench](https://github.com/SWE-bench/SWE-bench) |
| **Smoke** | 1 instance (`django__django-11099`) |
| **Full** | 1 instance (Docker harness **미연동**) |
| **전제** | Docker (full 시) |

### 실행

```bash
./scripts/eval/run-swe-smoke.sh
./scripts/eval/run-swe-full.sh
```

### 산출물

| 파일 | 설명 |
|------|------|
| `ada/src/ada/eval/results/swe-smoke.json` | 점수·pass_rate |
| `ada/src/ada/eval/reports/benchmark-swe-smoke-latest.md` | 리포트 |

> 현재는 Docker eval harness **미연동** — Agent API에 fix summary를 요청하는 harness-fallback으로 연동 상태를 검증합니다.

---

## 4. ToolSandbox (Apple)

### 소개

Apple의 stateful 멀티턴 tool-use 벤치마크입니다. BFCL·τ²와 달리 **상태가 유지되는 도구 환경**과 동적 user proxy를 강조합니다. 리마인더·캘endar 등 상태 전이 시나리오를 평가합니다.

| 항목 | 값 |
|------|-----|
| **Adapter** | [`ada/src/ada/eval/adapters/toolsandbox_adapter.py`](../../../ada/src/ada/eval/adapters/toolsandbox_adapter.py) |
| **Vendor** | [apple/ToolSandbox](https://github.com/apple/ToolSandbox) |
| **Smoke** | 3 scenarios |
| **Full** | 30 scenarios |

### 실행

```bash
./scripts/eval/run-toolsandbox-smoke.sh
./scripts/eval/run-toolsandbox-full.sh
```

### 산출물

| 파일 | 설명 |
|------|------|
| `ada/src/ada/eval/results/toolsandbox-smoke.json` | 점수·pass_rate |
| `ada/src/ada/eval/reports/benchmark-toolsandbox-smoke-latest.md` | 리포트 |

> Vendor evaluator **미연동** — `set_reminder` tool 호출 fallback.

---

## 5. MCPAgentBench

### 소개

MCP(Model Context Protocol) 기반 tool 선택 벤치마크입니다. distractor tool이 섞인 환경에서 **올바른 MCP tool을 고르고 호출**하는 능력을 평가합니다. Ada MCP gateway 방향과 정합성이 높습니다.

| 항목 | 값 |
|------|-----|
| **Adapter** | [`ada/src/ada/eval/adapters/mcpagent_adapter.py`](../../../ada/src/ada/eval/adapters/mcpagent_adapter.py) |
| **MCP shim** | [`ada/src/ada/eval/harness/mcp_client.py`](../../../ada/src/ada/eval/harness/mcp_client.py) |
| **Vendor** | `ADA_MCPAGENTBENCH_REPO` 환경 변수로 repo URL 지정 |
| **Smoke** | 5 tasks (distractor 포함) |
| **Full** | 50 tasks |

### 실행

```bash
# vendor repo URL이 있을 때 (install-vendors.sh)
export ADA_MCPAGENTBENCH_REPO=<official-repo-url>
./scripts/eval/install-vendors.sh

./scripts/eval/run-mcpagent-smoke.sh
./scripts/eval/run-mcpagent-full.sh
```

### 산출물

| 파일 | 설명 |
|------|------|
| `ada/src/ada/eval/results/mcpagent-smoke.json` | 점수·pass_rate |
| `ada/src/ada/eval/reports/benchmark-mcpagent-smoke-latest.md` | 리포트 |

> Vendor runner **미연동** — `search_docs` vs distractor fallback.

---

## 실행 방법 요약

### 벤치별 (개별)

```bash
./scripts/ada.sh start

./scripts/eval/run-tau2-smoke.sh
./scripts/eval/run-bfcl-smoke.sh
./scripts/eval/run-swe-smoke.sh
./scripts/eval/run-toolsandbox-smoke.sh
./scripts/eval/run-mcpagent-smoke.sh
```

`-full.sh`로 full 모드 (파일명만 `*-full.json` / 설정 확대).

### 5개 + contract + pytest (한방)

```bash
./scripts/verify-regression-full.sh
```

### pytest gate (live, 스택 필요)

```bash
ADA_EVAL_RUN_LIVE=1 pytest ada/tests/regression/eval/ -m eval_smoke -q
```

### vendor 설치 (공식 runner 시도)

```bash
./scripts/eval/install-vendors.sh
```

---

## 결과 확인

### JSON (벤치별)

```bash
cat ada/src/ada/eval/results/tau2-smoke.json
# pass_rate, tasks_passed, extra.fallback_reason, extra.benchmark_log
```

### 리포트 (Markdown)

| 경로 | 내용 |
|------|------|
| `ada/src/ada/eval/reports/summary-latest.md` | 5종 요약 |
| `ada/src/ada/eval/reports/full-regression-latest.md` | 한방 실행 통합 |
| `ada/src/ada/eval/reports/benchmark-<id>-<mode>-latest.md` | 벤치별 |

### Baseline (회귀 기준)

[`ada/src/ada/eval/results/baseline.json`](../../../ada/src/ada/eval/results/baseline.json) — PR에서 `pass_rate >= baseline - 0.05` 유지.

### 로그 (디버깅)

```bash
# 최근 full regression 세션
cat ada/src/ada/eval/logs/latest-full-regression-smoke.log

# 벤치별
ls ada/src/ada/eval/logs/benchmarks/
```

---

## 관련 문서

- [README.md](./README.md) — Tier 구조, CI, 환경 변수
- [BENCHMARKS.md](./BENCHMARKS.md) — 아키텍처, vendor/fallback 상세, 로드맵
- [../regression/README.md](../regression/README.md) — Contract regression
