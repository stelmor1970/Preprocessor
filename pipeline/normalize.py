"""단계 0 — OCR 텍스트 정규화.

클로드 비전이 뽑은 텍스트는 표기가 섞여 있다. 보호 정규식(단계 1)이
`1천500㎡` 같은 한글 수사+숫자 혼용 표기를 놓치지 않도록 먼저 정규화한다.
"""

import re

# 한글 수사(천) + 숫자 혼용 + 면적 단위. 내부 공백을 제거하고 단위를 통일한다.
#   "1천 500㎡" / "1천500 ㎡" / "1천㎡"  →  "1천500㎡" / "1천㎡"
_KORNUM_AREA = re.compile(r"(\d+)\s*천\s*(\d*)\s*(㎡|m²|m2|㎥|m3)")

# 한글 수사(천) + 숫자 혼용 + 일반 단위(m 등). 면적 외 단위도 공백만 정리.
_KORNUM_ETC = re.compile(r"(\d+)\s*천\s*(\d+)\s*(m|km|개|명|회)")

_AREA_UNIT = {"㎡": "㎡", "m²": "㎡", "m2": "㎡", "㎥": "㎥", "m3": "㎥"}


def _join_area(m: re.Match) -> str:
    head, tail, unit = m.group(1), m.group(2), m.group(3)
    return f"{head}천{tail}{_AREA_UNIT.get(unit, unit)}"


def _join_etc(m: re.Match) -> str:
    return f"{m.group(1)}천{m.group(2)}{m.group(3)}"


def normalize_text(text: str) -> str:
    """OCR 원문을 보호 단계가 잘 인식할 수 있는 형태로 정규화."""
    # 1) 한글 수사 + 숫자 혼용 표기의 내부 공백 제거 + 면적 단위 통일
    text = _KORNUM_AREA.sub(_join_area, text)
    text = _KORNUM_ETC.sub(_join_etc, text)

    # 2) 남은 면적 단위 표기 통일 (숫자 뒤 m²/m2 → ㎡)
    text = text.replace("m²", "㎡")
    text = re.sub(r"(?<=\d)\s*m2(?![0-9])", "㎡", text)
    text = re.sub(r"(?<=\d)\s*m3(?![0-9])", "㎥", text)

    # 3) 공백/줄바꿈 정리 (항목 번호 ①②③ (1) 1. 구조는 그대로 보존)
    text = text.replace("　", " ")          # 전각 공백 → 반각
    text = re.sub(r"[ \t]+", " ", text)          # 연속 공백 축약
    text = re.sub(r" *\n *", "\n", text)         # 줄 끝/앞 공백 제거
    text = re.sub(r"\n{3,}", "\n\n", text)       # 빈 줄 3개+ → 2개

    return text.strip()
