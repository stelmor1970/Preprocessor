"""OCR 텍스트를 문제(카드) 단위로 분해.

문제 헤더 `[01]`, `[1]` 패턴을 우선 구분자로 사용한다.
헤더가 없으면 전체를 한 장의 카드(Q01)로 취급한다.
"""

from __future__ import annotations

import re

# 줄 시작의 [01] / [1] / 【01】 형태 문제 헤더
_HEADER_RE = re.compile(r"^\s*[\[【]\s*(\d{1,3})\s*[\]】]", re.MULTILINE)


def segment(text: str, prefix: str = "Q") -> list[dict]:
    """text를 문제 단위로 분해. [{"id": "Q01", "raw": "..."}] 반환."""
    matches = list(_HEADER_RE.finditer(text))
    if not matches:
        body = text.strip()
        return [{"id": f"{prefix}01", "raw": body}] if body else []

    cards = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        num = int(m.group(1))
        raw = text[start:end].strip()
        if raw:
            cards.append({"id": f"{prefix}{num:02d}", "raw": raw})
    return cards
