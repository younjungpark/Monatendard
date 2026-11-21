# 제3자 글꼴 및 구현 고지

## Monaspace Neon 1.400

- 원본: https://github.com/githubnext/monaspace
- 저작권: Copyright (c) 2023, GitHub
- 라이선스: SIL Open Font License 1.1
- Reserved Font Names: Monaspace, Argon, Neon, Xenon, Radon, Krypton

Monatendard는 위 Reserved Font Name을 최종 패밀리 이름으로 사용하지 않습니다.

## Pretendard 1.3.9

- 원본: https://github.com/orioncactus/pretendard
- 저작권: Copyright (c) 2021, Kil Hyung-jin
- 라이선스: SIL Open Font License 1.1
- Reserved Font Name: Pretendard

Monatendard는 위 Reserved Font Name을 최종 패밀리 이름으로 사용하지 않습니다.

## Nerd Fonts Symbols Only 3.5.1

- 원본: https://github.com/ryanoasis/nerd-fonts
- 저작권: Copyright (c) 2014 Ryan L McIntyre
- 라이선스: MIT License

`Monatendard Nerd Font Mono` 변형에만 Symbols Only 글리프를 포함합니다. 전체 MIT
라이선스는 `NERD_FONTS_LICENSE.txt`를 확인해 주세요.

## 구현 참고

글리프 병합, 두 영문 칸 advance, 고정폭 메타데이터 처리 방식은
[Jetendard](https://github.com/kuskhan/jetendard) 및 그 저장소가 고지한
Yeomil Mono의 접근을 참고했습니다. Monatendard의 구현은 Monaspace Neon 영문 전체를
가로 92.5%로 조정하는 별도 요구에 맞게 작성되었습니다.

전체 SIL Open Font License 1.1은 배포 패키지의 `LICENSE` 파일을 확인해 주세요.
