"""단계 2 — 클로드 API 압축.

마스킹된 텍스트를 보내 개조식으로 압축한다.
⟦...⟧ 토큰은 API가 내용을 볼 수 없으므로 변형 자체가 불가능하다.
한 문제씩 보내지 않고 배치로 묶되 토큰 네임스페이스로 구분한다.
"""

from __future__ import annotations

import json
import re

import anthropic

COMPRESS_SYSTEM = """당신은 소방시설관리사 2차 실기 수험서를 개조식으로 압축하는 편집기입니다.
입력 텍스트에는 ⟦Q01-0001⟧ 형태의 마스킹 토큰이 섞여 있습니다.

--- 절대 규칙 ---
1. ⟦...⟧ 토큰은 절대 수정·삭제·번역·재배열·분할하지 않습니다. 위치만 자연스럽게 유지합니다.
2. 토큰 사이의 평문만 압축합니다:
   - 명사형 종결(~함 / ~임 / ~할 것)로 변환
   - 도입부·중복 수식어·군더더기 제거
   - 의미가 바뀌지 않는 선에서 최대한 간결하게
3. '다만' / '단,'으로 시작하는 절(토큰일 수 있음)은 독립 단위로 유지하고 앞 절과 병합하지 않습니다.
   예외 관계(제외/한정)의 논리 연결을 끊지 않습니다.
4. 항목 번호(1. 2. 3. / ①②③ / (1)(2))는 그대로 유지합니다.
5. 새로운 토큰을 만들지 않으며, 입력에 없던 ⟦⟧ 기호를 생성하지 않습니다.

--- 출력 형식 ---
입력의 각 문제(헤더 토큰으로 시작)를 압축한 결과를 아래 JSON 배열로만 출력합니다.
설명 문장 없이 JSON만 출력하십시오.
[
  {"id": "Q01", "compressed": "압축된 본문 (토큰 포함)"},
  {"id": "Q02", "compressed": "..."}
]"""


def _build_batch_prompt(items: list[dict]) -> str:
    """배치 입력: 각 item = {"id": "Q01", "masked": "..."}"""
    blocks = []
    for it in items:
        blocks.append(f"=== {it['id']} ===\n{it['masked']}")
    return (
        "다음 문제들을 각각 개조식으로 압축하십시오. "
        "토큰(⟦...⟧)은 그대로 두고 평문만 압축합니다.\n\n"
        + "\n\n".join(blocks)
    )


_JSON_RE = re.compile(r"\[.*\]", re.DOTALL)


def _parse_response(text: str) -> dict[str, str]:
    """모델 응답에서 JSON 배열을 추출해 {id: compressed} 로 반환."""
    m = _JSON_RE.search(text)
    if not m:
        raise ValueError("응답에서 JSON 배열을 찾지 못했습니다.")
    data = json.loads(m.group())
    return {row["id"]: row["compressed"] for row in data}


def compress_batch(
    client: anthropic.Anthropic,
    items: list[dict],
    model: str = "claude-opus-4-8",
    max_tokens: int = 4096,
) -> dict[str, str]:
    """마스킹된 문제 배치를 압축. {id: compressed_masked} 반환.

    items: [{"id": "Q01", "masked": "..."}, ...]
    """
    prompt = _build_batch_prompt(items)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": COMPRESS_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    return _parse_response(text)
