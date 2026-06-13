"""카드 데이터 구조 및 출력 (명세서 4절).

카드 단위: [문제번호] / 원문 / 압축본 / 압축률 / 두음 암기어 / 검증결과
최종 산출물: 플래시카드용 JSON, 마크다운(검토용).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .protect import TOKEN_RE


@dataclass
class Card:
    id: str
    raw: str                          # 정규화된 원문 (복원 기준)
    compressed: str = ""              # 검증 통과한 최종 압축본 (토큰 복원 완료)
    ratio: float = 0.0                # 압축률
    mnemonic: str = ""                # 두음 암기어
    adopted: bool = False             # 검증 통과해 압축본 채택 여부
    verify: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        # 보존 토큰을 굵게 하이라이트한 뷰(검토용)
        return d


def _highlight_tokens(text: str, mapping: dict) -> str:
    """검토용: 보존된 원문 조각을 **굵게** 표시."""
    def repl(m):
        info = mapping.get(m.group())
        return f"**{info['text']}**" if info else m.group()
    return TOKEN_RE.sub(repl, text)


def save_json(cards: list[Card], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [c.to_dict() for c in cards]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_markdown(cards: list[Card], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# 압축 카드 (검토용)\n"]
    for c in cards:
        status = "✅ 채택" if c.adopted else "⚠️ 원문 유지(검증 실패)"
        lines.append(f"## [{c.id}]  {status}  · 압축률 {c.ratio:.1%}")
        if c.mnemonic:
            lines.append(f"**두음 암기어:** {c.mnemonic}")
        lines.append("\n**압축본**\n")
        lines.append(c.compressed or "(없음)")
        # 검증 리포트
        if c.verify.get("checks"):
            lines.append("\n**검증**")
            for chk in c.verify["checks"]:
                mark = {"PASS": "✓", "WARN": "!", "FAIL": "✗"}.get(chk["status"], "?")
                detail = f" — {chk['detail']}" if chk.get("detail") else ""
                lines.append(f"- {mark} {chk['name']}{detail}")
        lines.append("\n---\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def save_report(cards: list[Card], path: Path) -> None:
    """검증 리포트 요약(채택/실패 통계)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    adopted = sum(1 for c in cards if c.adopted)
    failed = [c.id for c in cards if not c.adopted]
    avg_ratio = sum(c.ratio for c in cards if c.adopted) / adopted if adopted else 0.0
    report = {
        "total": len(cards),
        "adopted": adopted,
        "rejected": len(failed),
        "rejected_ids": failed,
        "avg_ratio_adopted": round(avg_ratio, 4),
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
