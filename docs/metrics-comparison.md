# 글꼴 수치 비교: v0.2.3 · Proto A · Proto C · Jetendard

2026-10-05 측정 · Regular TTF · fontTools

## 처리 방식

| 항목 | v0.2.3 | Proto A | Proto C | Jetendard |
| --- | --- | --- | --- | --- |
| 영문 기반 | Monaspace Neon Frozen 1.400 | 같음 | 같음 | JetBrains Mono 2.304 |
| 영문 처리 | 가로 92.5% 압축 후 다시 그림 | 원본 그대로 | 가로 92.5% 압축 후 다시 그림 | 원본 그대로 |
| 영문 힌팅 | 없음 | 있음 (원본) | 없음 | 있음 (ttfautohint) |
| 한글 기반 | Pretendard 1.3.9 | 같음 | 같음 | Pretendard |
| 한글 배율 | 가로 1.13, 세로 1.11 | 균등 1.15 | 균등 1.15 | 균등 1.15 |
| 한글 힌팅 | 없음 | 없음 | 없음 | 없음 |

## 수치 (em 대비)

| 항목 | v0.2.3 | Proto A | Proto C | Jetendard |
| --- | --- | --- | --- | --- |
| 영문 셀 폭 | 0.600 | 0.620 | 0.600 | 0.600 |
| 한글 셀 폭 | 1.200 | 1.240 | 1.200 | 1.200 |
| x-height | 0.5135 | 0.5135 | 0.5135 | 0.550 |
| 영문 o 폭 × 높이 | 0.463 × 0.537 | 0.501 × 0.537 | 0.463 × 0.537 | 0.432 × 0.566 |
| 기본 줄 높이 | 1.245 | 1.245 | 1.245 | 1.320 |
| 한글 평균 크기 | 0.864 × 0.955 | 0.880 × 0.989 | 0.880 × 0.989 | 0.880 × 0.989 |
| 한글 높이 ÷ x-height | 1.86 | 1.93 | 1.93 | 1.80 |
| 한글 글자 사이 여백 (셀 대비) | 28% | 29% | 27% | 27% |
| 한글 세로÷가로 비 (원본 = 1) | 0.9825 | 1.0000 | 1.0000 | 0.9996 |

측정 방법:

- 한글 평균 크기는 U+AC00–D7A3 11,172자 외곽 상자의 평균이다.
- 한글 세로÷가로 비는 각 글자의 세로 배율을 가로 배율로 나눈 값의 평균이다. Pretendard 원본 비율이면 1이다.
- 한글 글자 사이 여백은 `1 − 한글 평균 폭 ÷ 한글 셀 폭`이다.
- 기본 줄 높이는 `hhea` ascent − descent + lineGap이다. Windows Terminal에서 `cellHeight`를 지정하면 이 값 대신 그 값을 쓴다.

## 읽는 법

- **한글 글자는 Proto A, Proto C, Jetendard가 같다.** 크기와 비율이 모두 같고, 글자별 차이는 0.001em 이하다(upm 1000과 2000의 반올림 차이).
- **v0.2.3만 한글이 1.8% 납작하다.** 가로 1.13, 세로 1.11의 비균등 배율 때문이며, 11,172자 모두에 같은 방향으로 걸린다.
- **남은 차이는 영문이다.** Monaspace의 x-height(0.5135)가 JetBrains Mono(0.550)보다 낮아서, 같은 한글이 Monatendard 계열에서 영문 대비 조금 커 보인다(1.93 대 1.80).
- **Proto A와 C의 차이는 영문 처리와 셀 폭뿐이다.** 2026-10-05 Windows Terminal 15pt Light에서 둘은 거의 같아 보였다. 15pt(20px)에서는 0.620em(12.4px)과 0.600em(12px) 셀이 모두 12px로 반올림되는 것으로 보인다.

## 시험판 설치 패키지

`tools/package_proto.py`로 만든다. 먼저 `--all`로 14개 스타일을 빌드해야 한다.

```sh
uv run monatendard build --profile proto-a --all
uv run monatendard build-nerd --profile proto-a --all
uv run python tools/package_proto.py proto-a proto-c
```

결과는 `dist/Monatendard-Proto-{A,C}-0.3.0-proto-Nerd.zip`이다. 압축을 풀고 `install.cmd`를 실행하면 관리자 권한 없이 현재 사용자에게 설치된다.
