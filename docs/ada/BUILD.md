# Phase 0 — adacode 빌드·실행

[microsoft/vscode](https://github.com/microsoft/vscode)를 **`scott-kim-7/adacode` fork**로 clone하여 M4 Max에서 빌드·실행한다.

| 항목 | 값 |
|------|-----|
| GitHub 계정 | `scott-kim-7` |
| Fork repo | **https://github.com/scott-kim-7/adacode** |
| Upstream | `microsoft/vscode` |
| 로컬 경로 | `.../SynologyDrive-playground/adacode/` |

## 목표

- `./scripts/code.sh`로 **로컬 IDE 기동**
- 이후 커스터마이즈·ada 확장·AI 플랫폼은 **동일 repo**에 commit/push

## 사전 요구 (M4 Max, macOS)

| 항목 | 권장 |
|------|------|
| Xcode Command Line Tools | `xcode-select --install` |
| Node.js | **24.15.0+** (`.nvmrc` 기준, nvm 권장) |
| 패키지 매니저 | **npm** (최신 VS Code는 yarn 미지원) |
| Python | 3.11+ (Phase 1~) |
| `gh` 로그인 | `gh auth status` → `scott-kim-7` |
| 디스크 여유 | **≥ 30GB** |
| RAM | 128GB — 충분 |

## Step 0 — GitHub fork (`adacode`)

**아직 fork가 없을 때** (한 번만):

```bash
gh repo fork microsoft/vscode \
  --fork-name adacode \
  --clone=false \
  --remote=false
```

## Step 1 — clone

```bash
cd "/Users/scott/Library/CloudStorage/SynologyDrive-playground"
git clone https://github.com/scott-kim-7/adacode.git
cd adacode
```

## Step 2 — Node 버전

```bash
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh"
nvm install 24.15.0
nvm use 24.15.0
```

> **주의**: v24.7.0 등 minor가 15 미만이면 preinstall에서 거부됩니다.

## Step 3 — 의존성 설치 (최초 1회)

```bash
npm install
```

매번 할 필요 없음 — `package-lock.json` 변경 시에만 재실행.

## Step 4 — 컴파일·실행

```bash
npm run compile
./scripts/code.sh
```

개발 시:

```bash
npm run watch          # 터미널 1
./scripts/code.sh      # 터미널 2
```

## 검증 기록 (2026-06-06)

| 항목 | 값 |
|------|-----|
| commit | `6a4e80f425c2eb9d4c528862efeed9f4743692e8` |
| VS Code 버전 | 1.124.0 |
| Node | v24.15.0 |
| npm | v11.12.1 |
| compile | `npm run compile` 성공 |
| 실행 | `./scripts/code.sh` → Code - OSS 기동 |

## 자주 나는 문제

| 증상 | 조치 |
|------|------|
| Node 버전 오류 | `nvm use 24.15.0` |
| `yarn` 관련 오류 | `npm install` 사용 |
| copilot compile 실패 | `.pnp.cjs`, `.yarn` 삭제 후 `extensions/copilot`에서 `npm install` |

## 참고

- [VS Code How to Contribute](https://github.com/microsoft/vscode/wiki/How-to-Contribute)
- [DESIGN_PLAN.md](DESIGN_PLAN.md)
