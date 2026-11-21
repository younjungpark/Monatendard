# Linux 배포: Linux 설치기

## 범위와 구조

`fontconfig` 기반의 주요 데스크톱 Linux(Ubuntu/Debian, Fedora, Arch 등)에서 현재 사용자 영역에만
설치한다. `root`/`sudo` 실행과 시스템 전역 설치는 지원하지 않는다.

- 설치기 위치: [install.sh](install.sh) (단일 자기완결 Bash 스크립트).
- **일반판**(`Monatendard`): 정식 Desktop ZIP의 TTF 14개 → `${XDG_DATA_HOME:-$HOME/.local/share}/fonts/monatendard`.
- **Nerd판**(`Monatendard Nerd Font Mono`): 정식 Desktop-Nerd ZIP의 TTF 14개 → `${XDG_DATA_HOME:-$HOME/.local/share}/fonts/monatendard-nerd`.
- **Compact**, 사전 릴리스, 배포판별 패키지 매니저(AUR/APT/RPM/Nix 등), ZIP 동봉 스크립트, 최소 컨테이너(Alpine/BusyBox), WSL의 Windows 측 등록은 이번 범위에서 제외한다. 설계 배경은 [ADR-0001](../../docs/adr/0001-linux-bash-installer-with-pinned-checksums.md)을 참고한다.
- 대외 안내는 [README.md](../../README.md)와 [README.ko.md](../../README.ko.md)에서 제공하며, 고정값은 정식 릴리스마다 자동 갱신 PR로 최신 정식 버전에 맞춘다.
- 필수 도구: `bash`, `fc-cache`(`fontconfig`), 설치 시 `curl` 또는 `wget`, `unzip`, `sha256sum`. (`--status`, `--version`, `--help`는 추가 도구 없이 동작한다.)

## 사용자 명령

원격 원라이너 실행 또는 스크립트 직접 다운로드 실행을 모두 지원한다.

```sh
# 일반판 설치 또는 최신 고정 버전으로 업데이트
curl -fsSL https://raw.githubusercontent.com/younjungpark/Monatendard/main/packaging/linux/install.sh | bash

# Nerd판 설치 또는 업데이트
curl -fsSL https://raw.githubusercontent.com/younjungpark/Monatendard/main/packaging/linux/install.sh | bash -s -- --nerd

# 일반판과 Nerd판 모두 설치 또는 업데이트
curl -fsSL https://raw.githubusercontent.com/younjungpark/Monatendard/main/packaging/linux/install.sh | bash -s -- --all
```

스크립트를 먼저 내려받아 내용을 확인한 뒤 실행할 수도 있다.

```sh
curl -fsSLO https://raw.githubusercontent.com/younjungpark/Monatendard/main/packaging/linux/install.sh
bash install.sh --dry-run
bash install.sh
```

상태 확인, 제거와 기타 옵션:

```sh
# 설치 상태·버전·충돌 여부 확인 (기본: 두 패밀리 모두, --nerd 지정 시 Nerd판만)
curl -fsSL https://raw.githubusercontent.com/younjungpark/Monatendard/main/packaging/linux/install.sh | bash -s -- --status

# 일반판 관리 설치본 제거
curl -fsSL https://raw.githubusercontent.com/younjungpark/Monatendard/main/packaging/linux/install.sh | bash -s -- --uninstall

# Nerd판 / 두 패밀리 모두 제거
curl -fsSL https://raw.githubusercontent.com/younjungpark/Monatendard/main/packaging/linux/install.sh | bash -s -- --nerd --uninstall
curl -fsSL https://raw.githubusercontent.com/younjungpark/Monatendard/main/packaging/linux/install.sh | bash -s -- --all --uninstall

# 고정 배포 버전과 도움말 확인
bash install.sh --version
bash install.sh --help
```

설치 또는 제거 후 편집기와 터미널을 다시 시작해 `Monatendard` 또는 `Monatendard Nerd Font Mono`를
선택한다.

## 기존 수동 설치본에서 전환

**Linux 설치기**는 각 전용 폴더의 `.monatendard-managed` 마커로 **관리 설치본**만 추적한다.
전용 폴더에 마커가 없거나 `${XDG_DATA_HOME:-$HOME/.local/share}/fonts` 및 레거시 `~/.fonts`의
다른 위치에 같은 패밀리의 **수동 설치본**이 감지되면 덮어쓰지 않고 중단하며 충돌 경로를 출력한다.

1. 오류 메시지에 표시된 기존 **수동 설치본** TTF 파일을 직접 삭제한다.
2. 필요 시 `fc-cache -f`를 실행한 뒤 **Linux 설치기**를 다시 실행한다.
3. **일반판**과 **Nerd판**은 별도 패밀리이므로, 다른 패밀리의 **수동 설치본**은 지울 필요가 없다.
   단, `--all` 실행 시에는 두 패밀리의 사전 충돌 검사를 모두 통과해야 변경을 시작한다.

## 실패 시 복구

- **필수 도구 누락**: 안내된 도구(`curl`/`wget`, `unzip`, `sha256sum`, `fontconfig`)를 배포판
  패키지 매니저로 설치한 뒤 재시도한다.
- **체크섬·ZIP 검증 실패**: 임시 디렉터리에서 검증에 실패하면 기존 **관리 설치본**을 건드리지 않고
  중단하며 임시 파일을 정리한다. 네트워크 상태를 확인한 뒤 재시도한다.
- **교체 단계 실패**: 기존 **관리 설치본**을 백업으로 이동한 뒤 스테이징 폴더를 원자적으로 교체하며,
  교체 실패 시 백업을 원래 경로로 복원한다. 문제가 계속되면 같은 설치 명령을 다시 실행해 복구하거나
  `--uninstall` 후 재설치한다.
- **제거 시 오류**: **관리 설치본**이 이미 없으면 안내 후 정상 종료한다. **수동 설치본**만 감지된
  경우에는 삭제하지 않고 오류로 종료하므로 표시된 경로를 직접 정리한다.

## 정식 릴리스 자동 갱신

`release.yml`은 정식 릴리스 게시 성공 후 `update-font-linux.yml`을 호출한다. 사전 릴리스와 수동 빌드에서는
호출하지 않는다.

1. [update_linux.py](update_linux.py)가 공식 일반판·Nerd판 ZIP과 `SHA256SUMS.txt`를 내려받는다.
2. 정식 SemVer, 버전 역행, 체크섬, ZIP 무결성(중복 항목·경로 순회·심볼릭 링크·CRC), Cask와
   [install.sh](install.sh)의 TTF 14개 구성을 검증한다.
3. 검증을 통과하면 [install.sh](install.sh)의 버전·URL·SHA256 상수를 원자적으로 갱신한다.
4. `ubuntu-latest`에서 `shellcheck`와 [verify_linux.sh](verify_linux.sh) E2E 검증을 실행한다.
5. 변경이 있으면 `automation/linux-<version>` 브랜치로 PR을 생성·갱신한다.

수동 갱신 및 로컬 검증:

```sh
# 온라인 정식 릴리스 검증 및 갱신
python packaging/linux/update_linux.py --repository younjungpark/Monatendard --tag v0.3.1

# 로컬 아카이브 디렉터리 검증 (--tag 필수)
python packaging/linux/update_linux.py --repository younjungpark/Monatendard --tag v0.3.1 --archive-dir dist
```

GitHub Actions에서 수동 재실행할 때는 **Actions → Update Linux installer → Run workflow**를 사용한다.
`tag`를 비우면 최신 정식 릴리스를 사용한다.

## 검증

- `ci.yml`: `pytest`로 [install.sh](install.sh) CLI 계약(옵션·환경/권한 차단·충돌·보안·롤백)과
  [update_linux.py](update_linux.py) 단위·회귀 테스트를 실행한다.
- `linux-installer.yml`: `ubuntu-latest`에서 `shellcheck`, 커밋된 고정 해시와 공식 릴리스 체크섬 일치
  검증, 그리고 [verify_linux.sh](verify_linux.sh)를 통한 실제 공식 ZIP 설치·업데이트·두 패밀리 공존·
  `fc-list` 폰트 인식·**수동 설치본** 충돌 차단·`--dry-run`·제거 E2E 검증을 실행한다.
- 실제 GUI 편집기·터미널의 렌더링과 Ubuntu 외 배포판별 동작은 자동 검증에 포함되지 않는다.

## 관련 파일

| 파일 | 역할 |
|---|---|
| [install.sh](install.sh) | 고정 메타데이터가 내장된 단일 자기완결 Linux 설치기 |
| [update_linux.py](update_linux.py) | 공식 ZIP·체크섬·TTF 구성을 검증하고 `install.sh` 상수 갱신 |
| [verify_linux.sh](verify_linux.sh) | 격리 환경에서 `install.sh`의 E2E 설치·업데이트·충돌·제거 검사 |
| [linux-installer.yml](../../.github/workflows/linux-installer.yml) | PR·`main`의 `shellcheck`·해시 일치·Linux E2E CI |
| [update-font-linux.yml](../../.github/workflows/update-font-linux.yml) | 정식 릴리스 후 갱신·검증·PR 자동 생성 |
