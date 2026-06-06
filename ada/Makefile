.PHONY: vault-init vault-set vault-list profiles tri-chat test install

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

install:
	python3 -m venv $(VENV)
	$(PIP) install -e ".[dev]"

vault-init:
	$(PYTHON) -m ada vault init

vault-set:
	@test -n "$(KEY)" || (echo "Usage: make vault-set KEY=external.openai.api_key" >&2; exit 1)
	$(PYTHON) -m ada vault set $(KEY)

vault-list:
	$(PYTHON) -m ada vault list

profiles:
	$(PYTHON) -m ada profiles

tri-chat:
	$(PYTHON) -m ada tri-chat

test:
	$(PYTHON) -m pytest tests/ -q
