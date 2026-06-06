# Vault — 계정·비밀번호

## 원칙

- **유일한 저장소**: `ada/vault/secrets.vault.enc` (암호화, gitignore)
- **금지**: `.env`, 환경 변수, config, trace, log, commit, `/tmp`, UI 저장
- **unlock**: 사용 직전, **사유 표시** 후 암호 입력; 세션 캐시 없음

## 암호 → 키

1. Unicode NFKC 정규화 + trim
2. PBKDF2-HMAC-SHA256, 600_000 iterations, file salt, dklen=32
3. AES-256-GCM

## VaultNotice (5항목)

```
[VAULT ACTION REQUIRED: VAULT_ADD]
무엇:   github.token
왜:     GitHub push
어디:   ada/vault/secrets.vault.enc
어떻게: cd ada && make vault-set KEY=github.token
확인:   cd ada && make vault-list
```
