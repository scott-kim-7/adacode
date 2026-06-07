# Ada 패키지 구조 (web-only)

```
ada/
├── config/model_registry.yaml   # LLM 프로필 (chat_profile → MLX)
├── src/ada/
│   ├── agent/                   # LangGraph pass-through (CLI ada-agent)
│   │   ├── state.py
│   │   ├── graph.py             # START → llm → END
│   │   ├── session.py
│   │   └── llm.py               # profile → LLM callable
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
| Open WebUI | [`web/docker-compose.yml`](../web/docker-compose.yml) |
| MLX 서버 | [`scripts/serve-qwen.sh`](../scripts/serve-qwen.sh) |
| 원스톱 | [`scripts/serve-ada.sh`](../scripts/serve-ada.sh) |

Open WebUI는 LangGraph를 거치지 않고 MLX에 직접 연결합니다.  
터미널에서 agent를 쓰려면 `ada ada-agent` (LangGraph CLI)를 사용합니다.
