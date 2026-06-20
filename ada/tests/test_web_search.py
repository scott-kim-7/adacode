from __future__ import annotations

from ada.search.heuristics import select_search_providers


def test_select_context7_provider():
	assert "context7" in select_search_providers("How do I install FastAPI framework?")


def test_select_exa_provider():
	assert "exa" in select_search_providers("What is the news today in 2026?")


def test_select_both_providers():
	providers = select_search_providers("FastAPI framework news today 2026")
	assert "context7" in providers
	assert "exa" in providers
