# Windows 배포: Scoop

## 범위와 구조

Windows 10 1809 이상에서 현재 사용자에게만 설치한다. 일반 사용자 PowerShell에서 실행하며
`-g` 전체 사용자 설치는 지원하지 않는다. Scoop과 Git은 사전에 설치되어 있어야 한다.

- bucket 위치: 본 저장소 루트의 `bucket/`.
- `monatendard`: 정식 Desktop ZIP의 일반판 TTF 14개.
- `monatendard-nerd`: 정식 Desktop-Nerd ZIP의 Nerd판 TTF 14개.
- Compact, winget, Chocolatey, 원격 `irm | iex` 설치기는 이번 범위에서 제외한다.
- 원격 스크립트 실행이 없는 방식이라는 의미는 아니다. Scoop은 매니페스트의 PowerShell을
  실행한다. 이 방식의 이점은 고정 ZIP 체크섬과 설치·업데이트·제거 관리이다.

## 사용자 명령

최초 한 번:

```powershell
scoop bucket add monatendard https://github.com/younjungpark/Monatendard.git
```

필요한 패밀리만 설치:

```powershell
scoop install monatendard/monatendard
scoop install monatendard/monatendard-nerd
```

업데이트 또는 제거 전 해당 글꼴을 사용하는 앱을 닫고, 다른 글꼴을 쓰는 PowerShell에서 실행한다.

```powershell
scoop update
scoop update monatendard monatendard-nerd
scoop uninstall monatendard monatendard-nerd
```

하나만 설치했다면 해당 이름만 지정한다. 설치 후 앱을 다시 시작해 패밀리를 선택한다.

## 기존 ZIP 설치에서 전환

같은 이름의 사용자 글꼴 파일이 있으면 Scoop 설치를 중단한다. 수동 설치본을 자동으로
인수하거나 덮어쓰지 않는다. 사용 중인 앱을 닫고, 원래 ZIP의 해당 패밀리 제거 스크립트를
실행한 뒤 Scoop으로 설치한다. 일반판과 Nerd판은 별개이므로 다른 패밀리를 지울 필요가 없다.

기존 릴리스 ZIP의 설치 스크립트는 별도 Windows PowerShell 프로세스에서 실행해 이전 ZIP의
`Add-Type` 충돌을 피한다. 제거는 매니페스트에서 관리 파일을 먼저 지우고 정확한 경로의
등록만 정리한다. 과거 ZIP 제거 스크립트는 외부 경로의 같은 파일명 등록까지 지울 수 있어
Scoop에서는 호출하지 않는다. 수정한 소스 스크립트는
다음 릴리스 ZIP부터 배포되며, 이미 게시된 v0.3.0 자산을 바꾸지 않는다.

## 실패 시 복구

- 파일 사용 중: 편집기·터미널 등을 종료하고 같은 명령을 재시도한다. 필요하면 로그아웃 후
  글꼴을 사용하지 않는 PowerShell에서 재시도한다.
- 설치가 중간에 실패한 경우: 먼저 오류 로그와 `scoop list`를 확인한다. `scoop uninstall`
  로 정리한 뒤 다시 설치한다. 수동 설치본이 감지되면 원래 ZIP의 제거 스크립트로 정리한다.
- 잠금 검사는 수정 전에 모든 대상 파일을 확인하지만 검사와 실제 작업 사이의 경쟁 상태나
  OS·보안 프로그램 오류까지 트랜잭션으로 되돌리는 기능은 아니다. 실패 시 메시지를 확인한다.
- 현재 사용자 HKCU 등록과 LOCALAPPDATA 글꼴 디렉터리만 사용한다. 다른 글꼴의 등록은 보존한다.
- GDI 자체 참조를 먼저 해제한 뒤 앱의 파일 잠금을 검사한다. 사전 검사 실패 시 해제한
  참조 수만큼 다시 등록하며, 파일·레지스트리 삭제는 시작하지 않는다.

## 정식 릴리스 자동 갱신

`release.yml`은 정식 릴리스 게시 성공 후 `update-font-scoop.yml`을 호출한다.
사전 릴리스에서는 호출하지 않는다.

1. `update_scoop.py`가 두 공식 ZIP과 `SHA256SUMS.txt`를 내려받는다.
2. 정식 SemVer, 버전 역행, 체크섬, ZIP 무결성, TTF 14개와 포함 스크립트를 검증한다.
3. 두 매니페스트를 모두 사전 검증한 뒤 버전·URL·해시를 함께 갱신한다.
4. Windows 러너에서 `verify_scoop.ps1`을 실행한다.
5. 변경이 있으면 `automation/scoop-<version>` 브랜치의 PR을 생성·갱신한다.

저장소 Settings → Actions → General에서 Actions의 PR 생성 권한을 허용해야 한다.
기존 Homebrew 갱신과 같은 `GITHUB_TOKEN`을 사용하며 별도 저장소 PAT는 필요 없다.
자동 생성 PR은 기본 토큰의 이벤트 제한 때문에 별도 PR CI가 시작되지 않을 수 있으므로,
갱신 job 자체에서 Windows 검증을 완료한 뒤 PR을 만든다.

수동 갱신:

```sh
python packaging/windows/update_scoop.py --repository younjungpark/Monatendard --tag v0.3.0
```

## 검증

Linux에서는 `make test`, `make lint`로 생성기·정적 회귀 테스트를 실행한다.
Windows의 `Windows Scoop` workflow는 실제 공식 ZIP 설치와 사용자 글꼴 등록·제거,
이전 공식 릴리스에서의 업데이트, 두 패밀리의 공존, 잠금·수동 설치 충돌,
소스 스크립트의 동일 세션 재실행을 검사한다.
실제 앱 화면의 렌더링, 모든 Windows 버전, 로그아웃·재부팅 후의 동작은 별도 수동 확인이 필요하다.

`verify_scoop.ps1`은 전용 CI 러너에서만 실행한다. 사용자 글꼴과 Scoop 상태를 변경하므로
일상 작업 PC에서 검증용으로 실행하지 않는다.
