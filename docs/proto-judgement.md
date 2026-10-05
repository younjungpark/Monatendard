# Monatendard 시제품 판정 안내

2026-10-05 · `experiment/proto-ab` 브랜치 · [PRD](prd-monatendard-improvement.md) 1단계

## 만든 것

| 항목 | Proto A | Proto B | Proto C |
| --- | --- | --- | --- |
| 패밀리 | `Monatendard Proto A Nerd Font Mono` | `… Proto B …` | `… Proto C …` |
| 영문 | Monaspace Neon 원본 그대로, 힌팅 보존 | 같음 | v0.2.3 그대로 (92.5% 압축, 힌팅 없음) |
| 셀 폭 영문 / 한글 | 0.620em / 1.240em | 같음 | 0.600em / 1.200em |
| 한글 배율 | 균등 1.15 | 균등 1.07 | 균등 1.15 |
| 굵기 | Light, Regular, Bold | 같음 | 같음 |

Proto C는 2026-10-05 Proto A 사용 후 추가했다. A의 개선이 한글 균등 배율에서 오는지, 영문 압축 해제·힌팅에서 오는지 가르기 위한 대조군이다. 한글은 A와 11,172자 모두 같은 크기이고, 영문 글리프는 v0.2.3과 3606개 모두 같다.

### 한글 비율 (Pretendard 원본 대비 세로÷가로)

| | v0.2.3 | Proto A·C |
| --- | --- | --- |
| 평균 | 0.9825 (1.8% 납작) | 1.0000 |
| 비율이 0.5% 넘게 틀어진 글자 | 11,172자 전부 | 0자 |

두 패밀리 모두 현재 사용자 계정에 설치했다(`%LOCALAPPDATA%\Microsoft\Windows\Fonts`, HKCU). 기존 Monatendard와 Jetendard는 건드리지 않았다.

## 실측 (Regular, em 대비)

한글 크기는 U+AC00–D7A3에서 7자 간격으로 뽑은 글자 외곽의 평균이다. PRD 표와는 측정 방식이 달라 절댓값이 조금 다르므로 같은 열끼리만 비교한다.

| 항목 | v0.2.3 | Proto A | Proto B | Jetendard |
| --- | --- | --- | --- | --- |
| 영문 셀 폭 | 0.600 | 0.620 | 0.620 | 0.600 |
| x-height | 0.5135 | 0.5135 | 0.5135 | 0.550 |
| 한글 평균 크기 | 0.856 × 0.946 | 0.871 × 0.980 | 0.810 × 0.912 | 0.871 × 0.980 |
| 한글 높이 ÷ x-height | 1.84 | 1.91 | 1.78 | 1.78 |
| 한글 글자 사이 여백 | 29% | 30% | 35% | 27% |
| 영문 힌팅 | 없음 | 있음 | 있음 | 있음 |
| 원본과 같은 영문 글리프 | — | 3606/3606 | 3606/3606 | — |

- Proto A는 한글 크기가 Jetendard와 같고, Proto B는 한글 대 영문 크기 관계가 Jetendard와 같다. PRD가 의도한 대로다.
- 박스 문자와 Powerline 글리프는 Monaspace 원본 그대로이며 1240 셀 경계에서 맞닿는다(`verify` 통과).

## 1. 래스터 비교

`build/proto/compare/compare-20px.png`를 연다. 20px(15pt), 96 DPI, Light와 Regular를 나란히 놓았다. 대상은 v0.2.3, Proto A, Proto B, Jetendard, Monaspace Neon 원본(영문만)이다.

다시 그리려면 `uv run python tools/render_comparison.py`를 실행한다. `--size`와 `--line-height`로 조건을 바꿀 수 있다.

**렌더러 한계**: Edge(Chromium)는 DirectWrite로 그리지만, Windows Terminal과 달리 가로 방향 힌팅을 거의 적용하지 않는다. 그래서 이 이미지에서는 힌팅 차이가 실제보다 작게 보인다. 힌팅 효과는 2단계의 터미널 실사용으로 판단한다.

## 2. 실사용

[`packaging/windows/proto/windows-terminal-profiles.json`](../packaging/windows/proto/windows-terminal-profiles.json)의 프로필을 Windows Terminal `settings.json`의 `profiles.list`에 붙여 넣는다. 모두 15pt, Light, `cellHeight` 1.5이다. A·B는 `cellWidth`를 뺐고, C는 v0.2.3과 같이 `cellWidth` 0.6을 둔다.

확인할 것:

- [ ] A와 C가 비슷한가 (비슷하면 개선은 한글 균등 배율에서 온 것이고, 셀 폭 0.600을 지킬 수 있다)
- [ ] 영문이 v0.2.3보다 선명한가
- [ ] Regular로 돌아갈 수 있는가 (`"weight": "light"` 줄을 지우고 비교)
- [ ] Proto A의 한글이 영문보다 커 보이는가
- [ ] Proto B의 한글 사이 여백(35%)이 휑하지 않은가
- [ ] Nerd 아이콘, Powerline 구분자, 박스 문자가 끊기지 않는가
- [ ] 한 줄 글자 수가 약 3% 줄어든 것이 불편한가
- [ ] 그래도 Jetendard 프로필로 손이 가는가

## 3. 결정

| 결과 | 다음 단계 |
| --- | --- |
| 통과 | 고른 시제품(A, B 또는 C)으로 Monatendard v0.3.0 범위를 잡는다 |
| 탈락 | Monatendard는 v0.2.3 그대로 두고, 대체 기반 글꼴 측정을 시작한다 |
| 한글만 흐림 | 한글 자동 힌팅을 별도로 실험한 뒤 다시 판정한다 |

## 다시 빌드·제거

```sh
make proto    # 세 시제품 빌드, 검증, 비교 이미지 생성
```

```powershell
# 다시 설치
.\packaging\windows\proto\Install-MonatendardProto.ps1 `
    -FontDirectory build\proto\proto-a\nerd-ttf `
    -FilePrefix MonatendardProtoANFM `
    -FamilyName 'Monatendard Proto A Nerd Font Mono'

# 판정 후 제거
.\packaging\windows\proto\Uninstall-MonatendardProto.ps1 -FilePrefix MonatendardProtoANFM
.\packaging\windows\proto\Uninstall-MonatendardProto.ps1 -FilePrefix MonatendardProtoBNFM
.\packaging\windows\proto\Uninstall-MonatendardProto.ps1 -FilePrefix MonatendardProtoCNFM
```

## 코드 변경 요약

- `sources.lock.toml`: `[prototypes.proto-a]`, `[prototypes.proto-b]`, `[prototypes.proto-c]` 설정을 추가했다. `[project]`는 그대로다.
- `builder.py`: `BuildProfile`과 `load_profile`을 추가했다. 영문 배율이 1이고 셀 폭이 원본과 같으면 글리프를 다시 그리지 않고 힌팅 테이블도 남긴다. 한글 가로·세로 배율이 같으면 균등 경로(`_fit_cjk_transform`)를 쓴다.
- `nerd.py`, `verify.py`, `cli.py`: 모든 명령이 `--profile`을 받는다. 시제품 출력은 `build/proto/<이름>/` 아래에 둔다.
- `verify`: 영문 셀 폭이 설정값과 같은지, 영문을 보존하는 설정이면 힌팅 테이블과 글리프 명령어가 남아 있는지 검사한다.
- 기본 설정 빌드는 v0.2.3 릴리스 TTF와 바이트 단위로 같다(Regular, Italic 확인).
