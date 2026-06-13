"""약어 양면(兩面) 출력 (명세서 3절).

같은 카드를 두 뷰로 토글한다.
  - 답안용 뷰(answer): 풀어쓴 원문 그대로. (답안에 약어 쓰면 점수 안 나옴)
  - 암기용 뷰(memo):  풀어쓴 원문을 약어로 축약. (암기 부담 감소)

풀어쓴 원문은 보호 단계에서 통째로 마스킹되어 압축 중 변형되지 않으므로,
답안용 뷰에는 항상 원문이 온전히 살아 있고 암기용 뷰만 약어로 바꾼다.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_abbr(path: str | Path) -> dict[str, str]:
    """abbr.json 로드. {약어: 풀어쓴 원문} (주석 키 제외)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if k != "_comment"}


def full_phrases(abbr: dict[str, str]) -> list[str]:
    """보호 대상으로 넘길 풀어쓴 원문 목록."""
    return list(abbr.values())


def to_memo_view(answer_text: str, abbr: dict[str, str]) -> str:
    """답안용 뷰 → 암기용 뷰: 풀어쓴 원문을 약어로 축약 (긴 것부터)."""
    text = answer_text
    for short, full in sorted(abbr.items(), key=lambda kv: len(kv[1]), reverse=True):
        text = text.replace(full, short)
    return text
