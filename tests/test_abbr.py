#!/usr/bin/env python3
"""약어 양면 출력 회귀 테스트 (명세서 3절).

실행: python tests/test_abbr.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import normalize_text, verify_compression
from pipeline.protect import Protector
from pipeline.abbr import load_abbr, full_phrases, to_memo_view


def main() -> int:
    abbr = load_abbr(ROOT / "config" / "abbr.json")
    terms = json.loads((ROOT / "config" / "terms.json").read_text(encoding="utf-8"))

    raw = "거실에는 스프링클러설비 기타 이와 유사한 자동식 소화설비를 30m 이내마다 설치한다."
    norm = normalize_text(raw)
    protector = Protector(terms=terms, abbreviations=full_phrases(abbr))
    masked, mapping = protector.mask(norm, namespace="Q02")

    answer = verify_compression(norm, masked, mapping)["restored"]
    memo = to_memo_view(answer, abbr)

    failures = []

    # 1) 풀어쓴 원문이 abbr 토큰 하나로 통째 보존되어야 함
    abbr_tokens = [v for v in mapping.values() if v["category"] == "abbr"]
    if not any("스프링클러설비 기타 이와 유사한 자동식 소화설비" == t["text"] for t in abbr_tokens):
        failures.append("풀어쓴 원문이 abbr 토큰으로 통째 보존되지 않음")

    # 2) 답안용 뷰에는 풀어쓴 원문이 그대로 살아 있어야 함 (약어 금지)
    if "스프링클러설비 기타 이와 유사한 자동식 소화설비" not in answer:
        failures.append("답안용 뷰에 풀어쓴 원문이 없음")
    if "SP" in answer:
        failures.append("답안용 뷰에 약어 SP가 노출됨 (감점 위험)")

    # 3) 암기용 뷰에는 약어로 축약되어야 함
    if "SP" not in memo:
        failures.append("암기용 뷰가 약어 SP로 축약되지 않음")
    if "스프링클러설비 기타 이와 유사한" in memo:
        failures.append("암기용 뷰에 긴 원문이 남아 있음")

    print("📝 답안용:", answer)
    print("🧠 암기용:", memo)

    if failures:
        print("\n❌ FAIL")
        for f in failures:
            print("  -", f)
        return 1
    print("\n✅ ALL PASS — 약어 양면 출력 검증 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
