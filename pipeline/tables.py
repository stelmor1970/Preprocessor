"""반복형 기준 → 비교표 자동 변환 (명세서 3절).

내화구조 두께 기준처럼 ①②③ 구조가 거의 동일한 반복형은 서술형 압축 대상에서
빼고 비교표(항목 × 수치)로 변환한다. 압축률·암기효율 둘 다 우수하다.

변환은 '마스킹된 텍스트' 위에서 수행하므로 모든 보호 토큰이 보존된다.
반복되는 서술 군더더기(평문)만 제거되고, 토큰(수치·법령·괄호 등)은 표 셀에
그대로 남는다. 따라서 단계 3 검증(토큰 집합·괄호·한정어)을 그대로 통과한다.
"""

from __future__ import annotations

import re

from .protect import TOKEN_RE

# 항목 번호 마커: ①~⑮ / (1) / 1. / 가.
_ITEM_RE = re.compile(
    r"^\s*(?:[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]|\(\d+\)|\d+\.|[가-힣]\.)\s*"
)

# 라벨 끝의 조사·연결어 제거용
_TRAIL_JOSA = re.compile(r"(?:은|는|이|가|의|을|를|:|·|,|\s)+$")
# 라벨 끝의 공통 측정어 제거용 (모든 행이 공유 → 항목명에서 제외)
_TRAIL_DIM = re.compile(r"(?:두께|높이|길이|면적|너비|폭|간격|거리|지름|반지름|용량|수량)$")

_MIN_ROWS = 3            # 표로 만들 최소 반복 항목 수
_MAX_LABEL_LEN = 20      # 라벨(항목명) 최대 길이 — 길면 서술형으로 간주


def _category(token: str, mapping: dict) -> str:
    return mapping.get(token, {}).get("category", "")


def _tokens_with_pos(line: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group()) for m in TOKEN_RE.finditer(line)]


def _clean_label(text: str) -> str:
    text = _ITEM_RE.sub("", text).strip()
    prev = None
    while prev != text:  # 조사·공통 측정어를 번갈아 제거 (예: "벽은 두께" → "벽")
        prev = text
        text = _TRAIL_JOSA.sub("", text).strip()
        text = _TRAIL_DIM.sub("", text).strip()
    return text


def build_table(masked: str, mapping: dict) -> str | None:
    """반복형이면 비교표(마스킹 상태) 문자열을 반환, 아니면 None."""
    lines = masked.splitlines()
    item_lines = [i for i, l in enumerate(lines) if _ITEM_RE.match(l)]
    if len(item_lines) < _MIN_ROWS:
        return None

    def measures(line: str) -> list[tuple[int, str]]:
        return [(p, t) for p, t in _tokens_with_pos(line) if _category(t, mapping) == "measure"]

    def has_marker(line: str) -> bool:
        return any(_category(t, mapping) == "marker" for _, t in _tokens_with_pos(line))

    # 자격 검사: 수치 있고, 조건절 마커(다만/한정/제외) 없고, 라벨이 짧은 항목
    rows: list[tuple[str, str]] = []
    qualified = 0
    for i in item_lines:
        line = lines[i]
        ms = measures(line)
        if not ms or has_marker(line):
            continue
        first_pos = ms[0][0]
        label = _clean_label(line[:first_pos])
        if not label or len(label) > _MAX_LABEL_LEN:
            continue
        # 기준 = 첫 수치 위치 이후의 토큰들만 (서술 평문은 버림, 토큰은 보존)
        value_tokens = [t for p, t in _tokens_with_pos(line) if p >= first_pos]
        value = " ".join(value_tokens)
        rows.append((label, value))
        qualified += 1

    # 반복형 판정: 자격 항목이 충분하고, 전체 항목의 과반을 차지
    if qualified < _MIN_ROWS or qualified < len(item_lines) * 0.6:
        return None

    # 표 앞 머리글(문제 헤더 등) 보존
    header = "\n".join(lines[: item_lines[0]]).strip()

    table = ["| 항목 | 기준 |", "|---|---|"]
    table += [f"| {label} | {value} |" for label, value in rows]

    out = []
    if header:
        out.append(header)
    out.append("\n".join(table))
    return "\n\n".join(out)
