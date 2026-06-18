# Ada 패키지 구조 (web-only)

```
ada/
├── config/
│   ├── model_registry.yaml
│   └── agent.yaml               # MainGraph system prompt / routing
├── src/ada/
│   ├── agent/                   # LangGraph MainGraph (CLI ada-agent)
│   │   ├── config.py            # agent.yaml
│   │   ├── state.py
│   │   ├── nodes.py             # prepare → route → plan → respond → verify
│   │   ├── graph.py
│   │   ├── session.py
│   │   ├── llm.py               # profile → LLM callable
│   │   ├── content.py           # multimodal content parse/preserve
│   │   ├── openai_compat.py     # OpenAI messages ↔ MainGraph
│   │   └── server.py            # FastAPI /v1/chat/completions (:9082)
│   ├── llm.py                   # OpenAI-compatible HTTP client
│   ├── registry.py
│   ├── vault.py
│   ├── tri_chat.py
│   └── cli.py
├── tests/
└── vault/                       # secrets.vault.enc (런타임 생성)
```

## Web UI (레포 루트)

| 구성 | 경로 |
|------|------|
| Open WebUI | [`web/docker-compose.yml`](../web/docker-compose.yml) → `:9082` agent API |
| LangGraph agent | [`scripts/ensure-ada-agent-server.sh`](../scripts/ensure-ada-agent-server.sh) |
| MLX 서버 | 외부 프로세스 — `http://127.0.0.1:8080/v1` (Ada가 기동/종료하지 않음) |
| 원스톱 | [`scripts/ada.sh`](../scripts/ada.sh) |

Open WebUI → LangGraph MainGraph (`:9082`) → MLX (`:8080`).  
터미널 REPL: `ada ada-agent` — [docs/ada/agent/README.md](../docs/ada/agent/README.md)
