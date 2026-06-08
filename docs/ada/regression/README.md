# Ada Regression Tests

릴리스·리팩터링 후 **반드시 유지되어야 하는 계약(contract)** 을 검증합니다.

## 실행

```bash
# regression만 (빠름, ~22 tests)
./scripts/verify-regression.sh

# regression + 전체 unit + compose smoke
./scripts/verify-ada.sh

# pytest 직접
cd ada && pytest tests/regression/ -m regression -q
```

런타임 스택(MLX/Agent) E2E는 regression **unit**과 별도:

```bash
./scripts/verify-step1-vision.sh   # MLX :8080 vision
./scripts/verify-agent-vision.sh   # Agent :8082 vision
```

## 구조

```
ada/tests/regression/
├── conftest.py                      # @pytest.mark.regression, 공통 config
├── test_main_graph_regression.py    # LangGraph direct/plan/retry/vision
├── test_agent_api_regression.py     # FastAPI Open WebUI contract
└── test_stack_config_regression.py  # agent.yaml, registry, docker-compose, multimodal
```

## 커버하는 계약

| 영역 | 검증 |
|------|------|
| **MainGraph** | direct 1회 LLM, plan 2회, empty retry, multi-turn session |
| **Vision** | plan/respond LLM 입력에 `image_url` 포함, compat에서 strip 없음 |
| **Agent API** | `stream:true` → buffered JSON, OpenAI response shape, health/models |
| **Stack config** | docker-compose → `:8082`, agent.yaml vision, chat_profile MLX |

## CI

GitHub Actions `ada-pytest.yml`:

1. `pytest ada/tests/regression/ -m regression`
2. `pytest ada/tests/` (전체)

## Tier 2 — Eval smoke

Agent API `:8082` + MLX `:8080` 기동 후:

```bash
./scripts/verify-regression-eval-smoke.sh
```

## Tier 3 — Full regression (한방)

Contract + 벤치 5개 + eval pytest + 통합 리포트:

```bash
./scripts/ada.sh start
./scripts/verify-regression-full.sh
./scripts/verify-regression-full.sh --update-baseline   # baseline 갱신
```

벤치별 단독 실행: [REGRESSION_BENCHMARKS.md](../eval/REGRESSION_BENCHMARKS.md) · [README.md](../eval/README.md)

## 새 regression 추가 기준

- Open WebUI·LangGraph·MLX 연동에서 **한 번 깨졌던 버그** 또는 **North Star 경로**
- 외부 API 형식(OpenAI JSON, multimodal content) 변경 시 깨지기 쉬운 지점
- 단순 unit test duplication은 피하고 **end-to-end contract** 위주
