# Ada — AI orchestration (Step 2+)

Python 패키지: Model Registry, vault, Tri-Chat CLI.

## 설치

```bash
cd ada
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Vault

```bash
make vault-init          # ada/vault/secrets.vault.enc 생성
make vault-set KEY=external.openai.api_key
make vault-list
```

## Model Registry

```bash
ada profiles             # chat_profile, external_profile, regression_profile
ada profile chat_profile
```

설정: [`config/model_registry.yaml`](config/model_registry.yaml)

## Tri-Chat MVP

로컬 MLX → 외부 LLM → 사용자 순환 (CLI):

```bash
# MLX 서버 필요: ./scripts/serve-qwen.sh
ada tri-chat

# 비대화 1회 (테스트)
ada tri-chat --once "Hello tri-chat"
```

외부 LLM 키: vault `external.openai.api_key` 또는 개발용 `ADA_EXTERNAL_API_KEY`.

문서: [docs/ada/step2/README.md](../docs/ada/step2/README.md)
