"""단계 1 — 보호 토큰 추출 및 마스킹 / 복원.

명세서 1절 절대 원칙:
  "바꾸지 마"라고 부탁하지 말고 아예 안 보이게 한다.
보존 대상을 압축 전에 ⟦Q01-0001⟧ 형태의 마스킹 토큰으로 치환해서 API에 보낸다.
API가 그 내용을 못 보게 해서 변형 자체를 막는다.

문제별 네임스페이스(Q01-)를 붙여 배치 처리 시 토큰 충돌을 막는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ── 우선순위 (숫자가 작을수록 우선; 겹치면 우선순위 높은 쪽을 채택) ──
P_BRACKET_CJK = 1   # 한자·영문 병기 괄호 — 채점관 확인 항목, 최우선
P_LAW = 2           # 법령·조문
P_MEASURE = 3       # 수치 + 단위 + 한정어
P_BRACKET = 4       # 일반 괄호류
P_TERM = 5          # 전문용어(terms.json)
P_MARKER = 6        # 예외·조건 표지어
P_MNEMONIC = 7      # 두음 암기어 원단어(mnemonics.json)

# ── 정규식 ──────────────────────────────────────────────────────
# 수치: 한글수사(천) 혼용 또는 일반 숫자
_NUM = r"(?:\d+천\d*|\d[\d,]*(?:\.\d+)?)"
# 단위 (긴 토큰 우선: 개월 > 개, mm > m)
_UNITS = r"(?:개월|시간|㎡|㎥|MPa|mm|cm|km|kg|층|m|%|회|명|일|년|분|개|L)"
# 한정어 (정답을 가르는 부분 — 수치와 한 덩어리로 보존)
_QUAL = r"(?:\s*(?:이상|이하|초과|미만|이내|이전|이후))?"

RE_MEASURE = re.compile(_NUM + r"\s*" + _UNITS + _QUAL)

RE_LAW = re.compile(
    r"「[^」]*」"                 # 법령명
    r"|제\d+조(?:의\d+)?"        # 제○조 / 제○조의○
    r"|제\d+항"
    r"|제\d+호"
    r"|별표\s*\d+"
    r"|서식\s*\d+"
    r"|부칙"
)

RE_BRACKET = re.compile(
    r"\([^()]*\)"               # ( )
    r"|\[[^\[\]]*\]"            # [ ]
    r"|〔[^〔〕]*〕"             # 〔 〕
    r"|【[^【】]*】"             # 【 】
)

# 괄호 안에 한자(CJK) 또는 영문이 있으면 최우선 태그
RE_CJK = re.compile(r"[一-鿿]|[A-Za-z]")

# 예외·조건 표지어 + 열거 접속사
RE_MARKER = re.compile(r"다만|단,|제외|한정|한하여|및|또는")

# 마스킹 토큰 형식: ⟦Q01-0001⟧
TOKEN_RE = re.compile(r"⟦[A-Za-z0-9]+-\d{4}⟧")


@dataclass
class Span:
    start: int
    end: int
    text: str
    category: str
    priority: int


class Protector:
    """보호 대상을 마스킹 토큰으로 치환하고 복원한다."""

    def __init__(self, terms: list[str] | None = None, mnemonics: list[str] | None = None):
        # 긴 항목부터 매칭되도록 정렬 (부분 매칭 방지)
        self.terms = sorted(set(terms or []), key=len, reverse=True)
        self.mnemonics = sorted(set(mnemonics or []), key=len, reverse=True)

    # ── 후보 수집 ──
    def _candidates(self, text: str) -> list[Span]:
        spans: list[Span] = []

        for m in RE_LAW.finditer(text):
            spans.append(Span(m.start(), m.end(), m.group(), "law", P_LAW))

        for m in RE_MEASURE.finditer(text):
            spans.append(Span(m.start(), m.end(), m.group(), "measure", P_MEASURE))

        for m in RE_BRACKET.finditer(text):
            if RE_CJK.search(m.group()):
                spans.append(Span(m.start(), m.end(), m.group(), "bracket_cjk", P_BRACKET_CJK))
            else:
                spans.append(Span(m.start(), m.end(), m.group(), "bracket", P_BRACKET))

        for m in RE_MARKER.finditer(text):
            spans.append(Span(m.start(), m.end(), m.group(), "marker", P_MARKER))

        for term in self.terms:
            for m in re.finditer(re.escape(term), text):
                spans.append(Span(m.start(), m.end(), m.group(), "term", P_TERM))

        for word in self.mnemonics:
            for m in re.finditer(re.escape(word), text):
                spans.append(Span(m.start(), m.end(), m.group(), "mnemonic", P_MNEMONIC))

        return spans

    # ── 겹침 해소 ──
    @staticmethod
    def _resolve(spans: list[Span]) -> list[Span]:
        # 우선순위(작은 수) → 길이(긴 것) → 위치 순으로 채택, 겹치면 버린다.
        spans.sort(key=lambda s: (s.priority, -(s.end - s.start), s.start))
        chosen: list[Span] = []
        occupied: list[tuple[int, int]] = []
        for s in spans:
            if any(not (s.end <= a or s.start >= b) for a, b in occupied):
                continue  # 이미 채택된 span과 겹침 → 버림
            chosen.append(s)
            occupied.append((s.start, s.end))
        chosen.sort(key=lambda s: s.start)
        return chosen

    # ── 마스킹 ──
    def mask(self, text: str, namespace: str = "Q00") -> tuple[str, dict]:
        """text의 보호 대상을 토큰으로 치환. (masked_text, mapping) 반환."""
        spans = self._resolve(self._candidates(text))

        mapping: dict[str, dict] = {}
        numbered: list[tuple[Span, str]] = []
        for n, s in enumerate(spans, start=1):
            token = f"⟦{namespace}-{n:04d}⟧"
            mapping[token] = {"text": s.text, "category": s.category}
            numbered.append((s, token))

        # 인덱스가 밀리지 않도록 오른쪽(뒤)부터 치환
        out = text
        for s, token in sorted(numbered, key=lambda t: t[0].start, reverse=True):
            out = out[: s.start] + token + out[s.end :]

        return out, mapping


def restore(text: str, mapping: dict) -> str:
    """마스킹 토큰을 원문으로 복원."""
    def repl(m: re.Match) -> str:
        return mapping.get(m.group(), {}).get("text", m.group())

    return TOKEN_RE.sub(repl, text)


def tokens_in(text: str) -> set[str]:
    """text에 존재하는 마스킹 토큰 집합."""
    return set(TOKEN_RE.findall(text))
