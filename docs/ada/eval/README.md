# Ada Agent Eval Benchmarks

LangGraph Agent API (`:8082`) 대상 업계 벤치마크 smoke/full 실행 가이드.

## Tier 구조

| Tier | 명령 | CI | 전제 |
|------|------|-----|------|
| Contract | `./scripts/verify-regression.sh` | 항상 | 없음 |
| Eval smoke | `./scripts/verify-regression-eval-smoke.sh` | `ada-eval-smoke.yml` (dispatch) | Agent + MLX |
| Eval full | `./scripts/eval/run-*-full.sh` | 없음 | 로컬/nightly |

## 사전 준비

```bash
./scripts/ada.sh start
./scripts/eval/install-vendors.sh   # 선택 — .eval/vendor/ 에 외부 repo clone
```

환경 변수:

```bash
export ADA_EVAL_BASE_URL=http://127.0.0.1:8082/v1
export ADA_EVAL_VENDOR_ROOT=$PWD/.eval/vendor
export ADA_AGENT_PROFILE=chat_profile
```

## 벤치별 실행

| 벤치 | Smoke | Full | Smoke 예상 시간 (로컬 MLX 32B) |
|------|-------|------|-------------------------------|
| τ²-bench | `./scripts/eval/run-tau2-smoke.sh` | `./scripts/eval/run-tau2-full.sh` | 30~90분 |
| BFCL v4 | `./scripts/eval/run-bfcl-smoke.sh` | `./scripts/eval/run-bfcl-full.sh` | 5~30분 |
| SWE-bench | `./scripts/eval/run-swe-smoke.sh` | `./scripts/eval/run-swe-full.sh` | 15~60분 |
| ToolSandbox | `./scripts/eval/run-toolsandbox-smoke.sh` | `./scripts/eval/run-toolsandbox-full.sh` | 20~45분 |
| MCPAgentBench | `./scripts/eval/run-mcpagent-smoke.sh` | `./scripts/eval/run-mcpagent-full.sh` | 30~90분 |

결과 JSON: `ada/src/ada/eval/results/{bench}-smoke.json` (gitignore)

## Baseline

[`ada/src/ada/eval/results/baseline.json`](../../ada/src/ada/eval/results/baseline.json) — smoke `pass_rate` 기준. PR regression은 `baseline - 0.05` 이상.

## pytest

```bash
pytest ada/tests/regression/eval/ -m eval_smoke -q
pytest ada/tests/regression/eval/test_tau2_smoke.py -m eval_smoke -q
```

Agent `:8082` 미기동 시 live smoke 테스트는 skip. Live 실행: `ADA_EVAL_RUN_LIVE=1 pytest ...`

## 리포트

테스트 실행 후 Markdown 리포트가 자동 생성됩니다.

| 스크립트 | 리포트 |
|----------|--------|
| `./scripts/verify-regression.sh` | `ada/src/ada/eval/reports/contract-latest.md` |
| `./scripts/verify-regression-eval-smoke.sh` | `ada/src/ada/eval/reports/eval-smoke-latest.md` |
| `./scripts/eval/run-*-smoke.sh` | `ada/src/ada/eval/reports/benchmark-<name>-smoke-latest.md` |
| (벤치 실행 후 자동 갱신) | `ada/src/ada/eval/reports/summary-latest.md` |

이력: `ada/src/ada/eval/reports/history/` (gitignore)

## 디렉터리

```
ada/src/ada/eval/
├── config/eval.yaml
├── harness/          # agent_client, stack_check, results
├── adapters/         # 벤치별 runner (vendor 또는 harness fallback)
└── results/          # baseline.json + run outputs (smoke/full gitignored)

scripts/eval/
├── install-vendors.sh
├── common.sh
└── run-*-smoke.sh / run-*-full.sh
```
