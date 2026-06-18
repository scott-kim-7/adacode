from __future__ import annotations

import os

import pytest

from ada.eval.harness.stack_check import is_agent_reachable

os.environ.setdefault("ADA_EVAL_MODEL", "eval-offline")


def pytest_configure(config: pytest.Config) -> None:
	config.addinivalue_line("markers", "eval_smoke: Agent eval smoke gates (requires :9082 for live runs)")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
	for item in items:
		if "/regression/eval/" in str(item.fspath).replace("\\", "/"):
			item.add_marker(pytest.mark.eval_smoke)


@pytest.fixture
def require_agent_stack():
	if not is_agent_reachable():
		pytest.skip("Agent API :9082 not reachable — start ./scripts/ada.sh start")


@pytest.fixture
def require_live_eval(require_agent_stack):
	if os.environ.get("ADA_EVAL_RUN_LIVE") != "1":
		pytest.skip("Live eval smoke skipped — set ADA_EVAL_RUN_LIVE=1 to run against MLX")
	del require_agent_stack
