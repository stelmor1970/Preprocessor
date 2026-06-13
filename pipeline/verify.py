"""단계 3 — 검증 (가장 중요).

검증을 통과하지 못한 압축본은 채택하지 않는다.
실패 시 원문 유지 + 리포트에 기록한다.
"""

from __future__ import annotations

import re

from .protect import restore, tokens_in

_BRACKET_CHARS = "()[]〔〕【】「」"
_QUAL_RE = re.compile(r"이상|이하|초과|미만|이내|이전|이후")


def _count_brackets(text: str) -> int:
    return sum(text.count(c) for c in _BRACKET_CHARS)


def _check(name: str, status: str, detail: str = "") -> dict:
    return {"name": name, "status": status, "detail": detail}


def verify_roundtrip(original_norm: str, masked: str, mapping: dict) -> dict:
    """마스킹→복원이 원문과 정확히 일치하는지 검증 (Phase 1 핵심)."""
    restored = restore(masked, mapping)
    checks = []

    ok = restored == original_norm
    checks.append(_check(
        "round_trip",
        "PASS" if ok else "FAIL",
        "" if ok else "복원본이 정규화 원문과 불일치",
    ))

    masked_tokens = tokens_in(masked)
    expected = set(mapping)
    missing = expected - masked_tokens
    checks.append(_check(
        "all_tokens_present",
        "PASS" if not missing else "FAIL",
        "" if not missing else f"마스킹 누락 {len(missing)}개: {sorted(missing)[:5]}",
    ))

    passed = all(c["status"] != "FAIL" for c in checks)
    return {"passed": passed, "checks": checks}


def verify_compression(
    original_norm: str,
    compressed_masked: str,
    mapping: dict,
    ratio_range: tuple[float, float] = (0.4, 0.6),
) -> dict:
    """압축본 검증 (Phase 2).

    - 보호토큰 집합 비교 (누락 시 FAIL)
    - 압축률 검사 (목표 구간 밖이면 WARN)
    - 괄호 개수 검사 (원문 == 복원본, 깨지면 FAIL)
    - 한정어 짝 검사 (개수 불일치 시 FAIL)
    """
    checks = []
    restored = restore(compressed_masked, mapping)

    # 1) 보호토큰 집합 비교
    expected = set(mapping)
    got = tokens_in(compressed_masked)
    missing = expected - got
    extra = got - expected
    if missing or extra:
        detail = []
        if missing:
            detail.append(f"누락 {len(missing)}개: {sorted(missing)[:5]}")
        if extra:
            detail.append(f"미등록 토큰 {len(extra)}개: {sorted(extra)[:5]}")
        checks.append(_check("token_set", "FAIL", "; ".join(detail)))
    else:
        checks.append(_check("token_set", "PASS", f"{len(expected)}개 토큰 보존"))

    # 2) 압축률 검사 (문자 기준 감소율)
    if len(original_norm):
        ratio = 1 - len(restored) / len(original_norm)
    else:
        ratio = 0.0
    lo, hi = ratio_range
    status = "PASS" if lo <= ratio <= hi else "WARN"
    checks.append(_check(
        "compression_ratio",
        status,
        f"압축률 {ratio:.1%} (목표 {lo:.0%}~{hi:.0%})",
    ))

    # 3) 괄호 개수 검사
    o_br, r_br = _count_brackets(original_norm), _count_brackets(restored)
    checks.append(_check(
        "bracket_count",
        "PASS" if o_br == r_br else "FAIL",
        f"원문 {o_br} vs 복원본 {r_br}",
    ))

    # 4) 한정어 짝 검사
    o_q, r_q = len(_QUAL_RE.findall(original_norm)), len(_QUAL_RE.findall(restored))
    checks.append(_check(
        "qualifier_count",
        "PASS" if o_q == r_q else "FAIL",
        f"원문 {o_q} vs 복원본 {r_q}",
    ))

    passed = all(c["status"] != "FAIL" for c in checks)
    return {"passed": passed, "checks": checks, "restored": restored, "ratio": ratio}
