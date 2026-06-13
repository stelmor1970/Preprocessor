"""점검실무행정 수험서 압축 파이프라인.

명세서 2절 단계 구성:
  단계 0  normalize  — OCR 텍스트 정규화
  단계 1  protect    — 보호 토큰 추출 및 마스킹 / 복원
  단계 2  compress   — 클로드 API 개조식 압축 (Phase 2)
  단계 3  verify     — 보호 토큰·압축률·괄호·한정어 검증
"""

from .normalize import normalize_text
from .protect import Protector, restore, tokens_in, TOKEN_RE
from .verify import verify_roundtrip, verify_compression

__all__ = [
    "normalize_text",
    "Protector",
    "restore",
    "tokens_in",
    "TOKEN_RE",
    "verify_roundtrip",
    "verify_compression",
]
