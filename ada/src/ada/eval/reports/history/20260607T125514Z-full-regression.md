# Ada Full Regression Report

**생성 시각:** 2026-06-07T12:55:14Z  
**시작 시각:** 2026-06-07T12:40:34Z  
**종합 결과:** **FAIL**  
**총 소요 시간:** 880.0s (14.7min)  

## Tier 요약

| Tier | Suite | 결과 |
|------|-------|------|
| 1 | Contract regression | **PASS** |
| 2 | Eval pytest (smoke) | **FAIL** |
| 3 | Benchmarks ×5 (smoke) | **PASS** |

## 실행 단계

| # | 단계 | 결과 | 소요 |
|---|------|------|------|
| 1 | Contract regression | **PASS** | 1.0s |
| 2 | Benchmark: τ²-bench (smoke) | **PASS** | 7.0s |
| 3 | Benchmark: BFCL v4 (smoke) | **PASS** | 241.0s |
| 4 | Benchmark: SWE-bench (smoke) | **PASS** | 6.0s |
| 5 | Benchmark: ToolSandbox (smoke) | **PASS** | 176.0s |
| 6 | Benchmark: MCPAgentBench (smoke) | **PASS** | 94.0s |
| 7 | Eval pytest (live) | **FAIL** | 354.0s |

### 오류

- **Eval pytest (live)**: `exit code 1`

## 스택

| 구성요소 | 상태 |
|----------|------|
| Agent API (`http://127.0.0.1:8082/v1`) | OK |
| MLX upstream | OK |

## 벤치마크 (smoke)

| 벤치마크 | 모드 | 통과 | 전체 | Pass rate | Baseline | 결과 | 소요 |
|----------|------|------|------|-----------|----------|------|------|
| τ²-bench (harness-fallback) | smoke | 5 | 5 | 100.0% | 1.0 | PASS | 4.7s |
| BFCL v4 (harness-fallback) | smoke | 10 | 10 | 100.0% | 1.0 | PASS | 139.6s |
| SWE-bench Verified (harness-fallback) | smoke | 1 | 1 | 100.0% | 1.0 | PASS | 3.1s |
| ToolSandbox (harness-fallback) | smoke | 3 | 3 | 100.0% | 1.0 | PASS | 136.9s |
| MCPAgentBench (harness-fallback) | smoke | 5 | 5 | 100.0% | 1.0 | PASS | 58.3s |


## Contract Pytest

| 항목 | 값 |
|------|-----|
| 결과 | **PASS** |
| 통과 | 22 |
| 실패 | 0 |
| 에러 | 0 |
| 스킵 | 0 |
| 소요 시간 | 0.27s |


## Eval Pytest

| 항목 | 값 |
|------|-----|
| 결과 | **FAIL** |
| 통과 | 14 |
| 실패 | 1 |
| 에러 | 0 |
| 스킵 | 0 |
| 소요 시간 | 353.41s |

### 실패 상세

- `tests.regression.eval.test_swe_smoke.test_swe_smoke_script`
  ```
  require_stack = None

    def test_swe_smoke_script(require_stack):
    	script = _repo_root() / "scripts" / "eval" / "run-swe-smoke.sh"
    	result = subprocess.run([str(script)], capture_output=True, text=True, check=False)
    	assert result.returncode == 0, result.stderr
>   	out = results_dir() / "swe-smoke.json"
           ^^^^^^^^^^^
E    NameError: name 'results_dir' is not defined

ada/tests/regression/eval/test_swe_smoke.py:27: NameError
  ```


## 산출물

- Snapshot: `/Users/scott/Library/CloudStorage/SynologyDrive-playground/adacode/ada/src/ada/eval/results/snapshot-smoke-latest.json`
- Summary: `/Users/scott/Library/CloudStorage/SynologyDrive-playground/adacode/ada/src/ada/eval/reports/summary-latest.md`
- Baseline: `/Users/scott/Library/CloudStorage/SynologyDrive-playground/adacode/ada/src/ada/eval/results/baseline.json`

## 재실행

```bash
./scripts/verify-regression-full.sh
./scripts/verify-regression-full.sh --benchmark-mode full   # 며칠 소요
./scripts/verify-regression-full.sh --start-stack --update-baseline
```
