# Vector DB migration (Phase 6)

Phase 6 moves memory and RAG off OWUI HTTP adapters when `ADA_USE_AGENT_BACKENDS=1`.

## Feature flags

| Variable | Default | Effect |
|----------|---------|--------|
| `ADA_USE_AGENT_BACKENDS` | `0` | `1` → `AgentMemoryBackend` + `AgentRetrievalBackend` |
| `ADA_AGENT_MEMORY_STORE` | `ada/.local/agent_memory/memories.json` | Local memory JSON path |
| `ADA_AGENT_RETRIEVAL_INDEX` | `ada/.local/agent_retrieval/index.json` | Local retrieval keyword index |
| `ADA_AGENT_RETRIEVAL_FALLBACK_OWUI` | `1` | Vector items (file/collection) still call OWUI `/ada/retrieval/sources` when local index misses |

## Import scripts

```bash
# Memories: OWUI → Ada local store
OWUI_JWT=<token> python3 scripts/import-owui-memories.py

# Retrieval index bootstrap from OWUI sources
OWUI_JWT=<token> python3 scripts/import-owui-retrieval-index.py \
  --items '[{"type":"collection","id":"..."}]' \
  --queries '["topic"]'
```

## Rollout

1. **Dual-run:** keep `ADA_USE_AGENT_BACKENDS=0` (OWUI adapters) in production.
2. **Import data:** run import scripts above.
3. **Enable agent backends:** `ADA_USE_AGENT_BACKENDS=1` + restart Agent.
4. **Disable OWUI fallback:** `ADA_AGENT_RETRIEVAL_FALLBACK_OWUI=0` when local index covers collections.

## Rollback

Set `ADA_USE_AGENT_BACKENDS=0` and restart Agent — factories revert to OWUI HTTP adapters.
