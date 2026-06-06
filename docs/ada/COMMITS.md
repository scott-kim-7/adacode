# 커밋·스냅샷

## 메시지 형식

```
<type>(<scope>): <subject>
```

- type: `feat`, `fix`, `spec`, `regression`, `docs`, `chore`
- scope: `ada`, `ada-vscode`, `docs`

## 규칙

- 작업 세션마다 commit
- `cd ada && make snapshot LABEL=...`
- `cd ada && make restore HASH=...`
- `ada/commits.db` (Phase 1)

## 금지

- `ada/vault/secrets.vault.enc` commit
- API key, token 평문 commit
