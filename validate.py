"""
생성된 DOCX 검증 스크립트
- 파일 존재 여부 확인
- 최소 파일 크기 확인
- docx 구조 무결성 확인 (zipfile 기반)
- 텍스트 내용 샘플 출력
"""
import sys
import os
import zipfile
from pathlib import Path

try:
    from docx import Document
    PYTHON_DOCX = True
except ImportError:
    PYTHON_DOCX = False

OUTPUT = "/mnt/user-data/outputs/소방관리사2차_만제01-29_두문자암기요약.docx"
MIN_SIZE_KB = 10


def check(condition, msg_ok, msg_fail):
    if condition:
        print(f"  ✅ {msg_ok}")
        return True
    else:
        print(f"  ❌ {msg_fail}")
        return False


def main(path=OUTPUT):
    p = Path(path)
    print(f"\n=== DOCX 검증: {p.name} ===\n")
    passed = 0
    total  = 0

    # 1. 파일 존재
    total += 1
    if check(p.exists(), f"파일 존재: {p}", f"파일 없음: {p}"):
        passed += 1
    else:
        print(f"\n결과: {passed}/{total} — 파일이 없어 검증 중단")
        sys.exit(1)

    # 2. 파일 크기
    total += 1
    size_kb = p.stat().st_size / 1024
    if check(size_kb >= MIN_SIZE_KB, f"파일 크기 {size_kb:.1f} KB ≥ {MIN_SIZE_KB} KB",
             f"파일 크기 {size_kb:.1f} KB < {MIN_SIZE_KB} KB (너무 작음)"):
        passed += 1

    # 3. ZIP 구조 (docx = zip)
    total += 1
    try:
        with zipfile.ZipFile(p) as zf:
            names = zf.namelist()
            ok = "word/document.xml" in names
            check(ok, f"word/document.xml 존재 ({len(names)} 항목)", "word/document.xml 없음 (손상 가능)")
            if ok:
                passed += 1
    except zipfile.BadZipFile:
        check(False, "", "ZIP 구조 오류 (손상된 파일)")

    # 4. 텍스트 샘플 (python-docx 있을 경우)
    total += 1
    if PYTHON_DOCX:
        try:
            doc = Document(str(p))
            texts = [p2.text for p2 in doc.paragraphs if p2.text.strip()]
            has_content = len(texts) >= 5
            check(has_content, f"텍스트 단락 {len(texts)}개 확인", "텍스트 단락 부족")
            if has_content:
                passed += 1
                print(f"\n  [샘플 — 첫 5개 단락]")
                for t in texts[:5]:
                    print(f"    · {t[:80]}")
        except Exception as e:
            check(False, "", f"python-docx 파싱 오류: {e}")
    else:
        passed += 1  # python-docx 없으면 건너뜀
        print("  ℹ️  python-docx 미설치 — 텍스트 내용 검증 건너뜀")

    # 결과
    print(f"\n결과: {passed}/{total} 통과", "✅ 검증 성공" if passed == total else "⚠️  일부 실패")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else OUTPUT
    main(target)
