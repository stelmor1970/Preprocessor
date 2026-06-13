#!/usr/bin/env python3
"""Phase 1 회귀 테스트 (명세서 7절 골든 샘플).

압축 없이 정규화 + 보호/마스킹 + 검증만 확인한다.
실행: python tests/test_pipeline.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import Protector, normalize_text, restore, tokens_in, verify_roundtrip


def _load_protector() -> Protector:
    cfg = ROOT / "config"
    terms = json.loads((cfg / "terms.json").read_text(encoding="utf-8"))
    mnem = json.loads((cfg / "mnemonics.json").read_text(encoding="utf-8"))
    words = [w for k, v in mnem.items() if k != "_comment" for w in v]
    return Protector(terms=terms, mnemonics=words)


def main() -> int:
    raw = (ROOT / "tests" / "golden" / "Q01_raw.txt").read_text(encoding="utf-8")
    norm = normalize_text(raw)
    protector = _load_protector()
    masked, mapping = protector.mask(norm, namespace="Q01")

    preserved = {v["text"]: v["category"] for v in mapping.values()}
    failures = []

    # 1) 한글+숫자 혼용 1천500㎡ 보존 (정규화 후 공백 제거되어 잡혀야 함)
    if not any("1천500㎡" in t for t in preserved):
        failures.append("1천500㎡(한글+숫자 혼용)가 보호 토큰에 없음")

    # 2) (器機) 한자 병기 → bracket_cjk 최우선 태그
    if preserved.get("(器機)") != "bracket_cjk":
        failures.append("(器機) 한자 병기가 bracket_cjk로 보존되지 않음")

    # 3) 「...」 법령명 보존
    if not any(t.startswith("「") and "방화구조" in t for t in preserved):
        failures.append("법령명 「건축물의 피난·방화구조...」가 보존되지 않음")

    # 4) 다만 / 한정 / 제외 예외 표지어 보존
    for marker in ("다만", "한정", "제외"):
        if marker not in preserved:
            failures.append(f"예외 표지어 '{marker}'가 보존되지 않음")

    # 5) 라운드트립: 복원본 == 정규화 원문
    rt = verify_roundtrip(norm, masked, mapping)
    if not rt["passed"]:
        failures.append(f"라운드트립 실패: {rt['checks']}")

    # 6) 마스킹된 텍스트에는 보호 원문이 노출되지 않아야 함
    if "器機" in masked or "1천500㎡" in masked:
        failures.append("마스킹 후에도 보호 대상이 평문으로 노출됨")

    # ── 결과 출력 ──
    print("=" * 60)
    print(f"보호 토큰 {len(mapping)}개 추출")
    for tok, info in mapping.items():
        print(f"  {tok}  [{info['category']:12}]  {info['text']}")
    print("-" * 60)
    print("마스킹된 텍스트 (API로 전송될 형태):")
    print(masked)
    print("=" * 60)

    if failures:
        print("\n❌ FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\n✅ ALL PASS — 골든 샘플 보호/검증 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
