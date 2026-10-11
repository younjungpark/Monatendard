# macOS 폰트 배포

Homebrew는 공식 릴리스의 Desktop·Desktop Nerd ZIP에 들어 있는 TTF를 설치합니다.
Cask 정의는 저장소 루트의 `Casks/`에 있고, 이 디렉터리에는 Cask 갱신과 검증에 쓰는 스크립트를 둡니다.

## 새 버전을 배포할 때

기존처럼 정식 버전 태그를 게시하면 됩니다. Release workflow가 ZIP을 게시한 뒤
macOS에서 두 Cask를 갱신하고 설치·제거를 검사합니다. 검사가 끝나면 갱신 PR이 생성됩니다.

PR의 변경 내용과 검사 결과를 확인하고 병합하면 Homebrew 사용자도 새 버전을 받을 수 있습니다.
추가 검사가 승인 대기로 표시되면 **Approve workflows to run**을 눌러 실행하세요.
같은 버전으로 다시 실행해도 변경이 없으면 PR을 만들지 않습니다.
사전 릴리스와 Release workflow의 수동 빌드는 자동 갱신 대상에서 제외됩니다.

## 배포에 문제가 생겼을 때

Release의 `update-font-casks` job에서 실패한 단계를 확인합니다.
Cask 갱신에 실패하더라도 이미 게시된 폰트 ZIP은 그대로 사용할 수 있습니다.

- **다운로드·체크섬 오류:** 릴리스에 ZIP 두 개와 `SHA256SUMS.txt`가 모두 있는지 확인합니다.
  파일이 교체됐다면 ZIP과 체크섬이 일치하는지도 확인합니다.
- **TTF 구성 변경:** 글꼴 파일명이나 스타일이 바뀌었는지 확인하고, `Casks/`의 파일 목록과
  [verify_casks.sh](verify_casks.sh)의 검사 목록을 함께 수정합니다.
- **설치·제거 오류:** Homebrew 로그에서 실패한 파일이나 명령을 확인합니다.
- **PR 생성 오류:** Actions 로그에 표시된 저장소 권한이나 브랜치 관련 오류를 확인합니다.
  저장소 **Settings → Actions → General → Workflow permissions**에서
  **Allow GitHub Actions to create and approve pull requests**가 켜져 있어야 PR을 만들 수 있습니다
  (2026-10-11에 켬).

원인을 수정한 뒤 **Actions → Update font casks → Run workflow**에서 다시 실행합니다.
브랜치는 `main`, `tag`에는 다시 배포할 정식 버전 태그를 지정합니다.
`tag`를 비우면 최신 정식 릴리스를 사용하며, `source_repository`는 비워 두면 됩니다.
폰트를 다시 빌드하거나 새 태그를 만들 필요는 없습니다.

## 관련 파일

| 파일 | 역할 |
|---|---|
| [font-monatendard.rb](../../Casks/font-monatendard.rb) | 일반판 다운로드 주소·버전·체크섬·TTF 목록 |
| [font-monatendard-nerd-font.rb](../../Casks/font-monatendard-nerd-font.rb) | Nerd판 다운로드 주소·버전·체크섬·TTF 목록 |
| [update_casks.py](update_casks.py) | 공식 ZIP의 체크섬과 TTF 구성을 확인하고 두 Cask를 갱신 |
| [verify_casks.sh](verify_casks.sh) | 갱신한 Cask의 스타일·설치·제거 검사 |
| [update-font-casks.yml](../../.github/workflows/update-font-casks.yml) | 릴리스 후 Cask 갱신부터 PR 생성까지 실행 |
| [font-casks.yml](../../.github/workflows/font-casks.yml) | Cask 관련 파일을 수정한 PR 검사 |

자동 검사는 이전 버전에서의 실제 업그레이드나 편집기·터미널의 화면 표시까지 확인하지는 않습니다.
글꼴 이름이나 파일 구조가 바뀌는 경우에는 해당 동작도 별도로 확인합니다.
