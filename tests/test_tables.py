#!/usr/bin/env python3
"""반복형 기준 → 비교표 변환 회귀 테스트 (명세서 3절).

실행: python tests/test_tables.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import normalize_text, verify_compression
from pipeline.protect import Protector
from pipeline.tables import build_table


def _protector() -> Protector:
    terms = json.loads((ROOT / "config" / "terms.json").read_text(encoding="utf-8"))
    return Protector(terms=terms)


def main() -> int:
    failures = []
    protector = _protector()

    # 1) 반복형: 표로 변환되고 모든 토큰·괄호·한정어 보존
    repetitive = (
        "[05] 내화구조의 부재별 두께 기준은?\n"
        "① 벽은 두께 10㎝ 이상이어야 한다.\n"
        "② 바닥은 두께 10㎝ 이상이어야 한다.\n"
        "③ 보는 두께 5㎝ 이상이어야 한다.\n"
        "④ 기둥은 두께 25㎝ 이상이어야 한다."
    )
    norm = normalize_text(repetitive)
    masked, mapping = protector.mask(norm, namespace="Q05")
    table = build_table(masked, mapping)
    if table is None:
        failures.append("반복형이 표로 변환되지 않음")
    else:
        if "| 항목 | 기준 |" not in table:
            failures.append("표 헤더가 생성되지 않음")
        v = verify_compression(norm, table, mapping)
        if not v["passed"]:
            failures.append(f"표 검증 실패: {v['checks']}")
        # 라벨이 공통 측정어 없이 부재명만 남았는지
        if "벽 |" not in v["restored"] or "기둥 |" not in v["restored"]:
            failures.append("라벨 정리(벽/기둥) 실패")

    # 2) 조건절(다만/한정) 포함 → 표로 변환되면 안 됨
    conditional = (
        "[01] 방화구획 기준은?\n"
        "1. 10층 이하의 층은 1천㎡ 이내마다 구획한다. 다만, 스프링클러설비 설치 시 3천㎡ 이내.\n"
        "2. 11층 이상의 층은 200㎡ 이내마다 구획한다. 다만, 불연재료 마감 시 1천500㎡ 이내로 한정한다.\n"
        "3. 매 층마다 구획한다."
    )
    norm2 = normalize_text(conditional)
    masked2, mapping2 = protector.mask(norm2, namespace="Q01")
    if build_table(masked2, mapping2) is not None:
        failures.append("조건절(다만/한정) 카드가 잘못 표로 변환됨")

    if table:
        print("변환된 비교표:")
        print(verify_compression(norm, table, mapping)["restored"])

    if failures:
        print("\n❌ FAIL")
        for f in failures:
            print("  -", f)
        return 1
    print("\n✅ ALL PASS — 비교표 변환/가드 검증 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
