---
status: accepted
---

# Linux 배포에 저장소 고정 체크섬 기반 배포판 중립 Bash 설치기 채택

macOS(Homebrew Cask)와 Windows(Scoop)는 단일 생태계 패키지 매니저로 공식 정식 릴리스 ZIP을 배포하지만, Linux는 배포판별 패키지 생태계가 파편화되어 있다. Linux 1차 배포 수단으로 배포판별 패키지 매니저 대신, 저장소에 버전·URL·SHA256·기대 TTF 목록을 고정한 단일 자기완결 Bash 설치기(`packaging/linux/install.sh`)를 채택하고 정식 릴리스마다 자동 검증 PR로 갱신한다.

## Considered Options

- **배포판별 패키지 매니저 (AUR, APT/deb, RPM/COPR, Nix Flake 등)**: 각 배포판 네이티브 경험은 좋으나 패키징 포맷과 유지보수·검증 표면이 배포판 수만큼 늘어나 1차 범위 대비 비용이 크다.
- **Desktop ZIP 동봉 오프라인 스크립트**: Windows의 수동 ZIP 설치 스크립트와 유사하지만, 사용자가 매번 ZIP을 직접 내려받아 압축을 풀어야 해 한 줄 설치·업데이트 요구를 충족하지 못한다.
- **실행 시 GitHub Releases 동적 조회**: 릴리스마다 저장소 갱신 PR이 필요 없으나, 검증용 `SHA256SUMS.txt`와 ZIP이 같은 출처에 놓여 공급망 분리 검증 효과가 약해지고 비인증 GitHub API 레이트 리밋 위험이 생긴다.

## Consequences

- 정식 릴리스 태그 게시 시 macOS·Windows와 동일하게 Linux 설치기 갱신·검증 워크플로가 자동 PR을 생성하므로, 병합 절차가 한 축 추가된다.
- 공식 지원 범위는 `fontconfig` 기반 주요 데스크톱 Linux의 현재 사용자 영역으로 한정되며, `root`/`sudo` 전역 설치·최소 컨테이너(BusyBox/Alpine)·WSL의 Windows 측 폰트 등록은 제외한다.
- Windows Scoop과 동일한 안전 원칙을 유지해, 관리 설치본만 전용 디렉터리와 마커로 업데이트·제거하고 수동 설치본 충돌이 감지되면 덮어쓰지 않고 중단한다.
