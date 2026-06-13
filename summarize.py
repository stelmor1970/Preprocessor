#!/usr/bin/env python3
"""
소방시설관리사 2차 실기 수험서 PDF 요약 프로그램
Claude Vision 기반 - 스캔 이미지 PDF 전용
"""

import sys
import os
import base64
import argparse
from pathlib import Path

import fitz  # PyMuPDF
import anthropic

MODEL = "claude-opus-4-8"
PAGES_PER_CHUNK = 5   # Vision은 이미지당 토큰이 크므로 소규모 청크 권장
DPI = 150             # 해상도: 낮을수록 빠르고 저렴, 높을수록 정확 (권장 120~200)
OUTPUT_DIR = Path("summaries")

SYSTEM_PROMPT = """당신은 소방시설관리사 2차 실기 시험 전문 강사입니다.

이 수험서는 【문제】→【답안】→【보충정보】 구조로 이루어져 있습니다.
원문의 내용을 빠짐없이 보존하면서, 두문자 암기전략을 추가하는 방식으로 정리해 주세요.
절대로 내용을 임의로 삭제하거나 압축하지 마십시오.

--- 출력 양식 (반드시 준수) ---

문제 단위로 아래 5단계 구조로 작성합니다.

─────────────────────────────────────
### [문제 번호] 문제 제목
─────────────────────────────────────

**【문제】**
원문 문제를 간략화합니다. 법령명·주제어는 그대로 유지하되, 문말 서술형 지시어만 의문형으로 바꿉니다.
변환 규칙:
- "~을 쓰시오" / "~을 서술하시오" / "~에 대해 설명하시오" → "~은?"
- "~를 나열하시오" → "~는?"
- 서브문제(1), 2) 등)도 동일하게 의문형으로 변환
예) 원문: "건축물의 피난 방화구조 등의 기준에 관한 규칙에서 방화구획의 구획기준을 쓰시오"
    변환: "건축물의 피난 방화구조 등의 기준에 관한 규칙에서 방화구획의 구획기준은?"

**【핵심요약】**
이 문제의 출제 포인트를 한 문장으로 요약합니다.
어떤 수치·조건이 핵심인지, 어디서 자주 틀리는지 명시합니다.

**【모범답안】**
원문의 답안을 그대로 옮겨 적습니다.
- 번호·항목 구조가 있으면 그대로 유지
- 수치·법령 기준 한 줄도 생략하지 않음
- 단서·예외 조건은 들여쓰기로 표현
- 비교 항목이 2개 이상이면 마크다운 표로 변환

**【보충정보】**
원문의 보충 설명·추가 해설을 그대로 옮겨 적습니다.
생략 없이 전부 포함합니다.

**【두문자 암기전략】**
형식: 암기전략: '두문자어'
- 답안의 핵심 항목들을 두문자로 묶어 제시
- 각 글자 뒤에 해당 내용 요약 (수치 포함)
- 단서·예외는 들여쓰기 sub-항목으로 추가
예)
암기전략: '십일매직'
**십**: 10층 이하 → 바닥면적 1,000㎡마다 구획 (스프링클러 설치 시 3,000㎡)
**일**: 11층 이상 → 바닥면적 200㎡마다 구획 (스프링클러 시 600㎡)
   ↳ 불연재료 마감 시: 500㎡ (스프링클러 시 1,500㎡)
**매**: 매 층마다 구획 (지하 1층 직결 경사로 제외)
**직**: 직통계단 통하는 부분은 별도 구획

**【Strategist's Tip】**
시험에서 자주 바꿔치는 수치, 혼동하기 쉬운 조건, 출제 패턴 경고를 1~2문장으로 기술.
예) [Tip] '3,000㎡'를 '1,000㎡'로, '600㎡'를 '200㎡'로 바꾸는 함정이 단골 출제됩니다.

--- 절대 규칙 ---
1. 【문제】·【모범답안】·【보충정보】의 내용은 원문에서 한 글자도 삭제하지 않습니다
2. 수치(㎡, m, 층, 분, 개 등)는 반드시 원문과 동일하게 유지합니다
3. 두문자 암기전략은 내용을 '대체'하는 것이 아니라 '추가'하는 것입니다
4. 이미지에서 표가 보이면 반드시 마크다운 표로 변환합니다
5. 필기 메모·밑줄·강조 표시도 중요 정보로 포함합니다
6. 법령·규정·기준 관련 내용은 절대 누락하지 않습니다:
   - 법률명, 시행령, 시행규칙, 고시 등 근거 법령 명칭을 원문 그대로 표기
   - 조·항·호·목 번호(제X조 제X항 제X호 등)를 빠짐없이 포함
   - "~이상", "~이하", "~미만", "~초과" 등 기준 표현은 원문과 동일하게 유지
   - 적용 예외·면제·완화 조건도 반드시 포함
   - 법령에서 정의하는 용어의 정의 규정도 생략하지 않음
7. 괄호 안 내용은 절대 생략하지 않습니다:
   - ( ) 소괄호: 조건, 예외, 단서, 부연 설명 등 핵심 정보가 담겨 있음
   - 예) "바닥면적 1,000㎡(스프링클러 설치 시 3,000㎡)" → 괄호 포함 필수
   - 예) "60분(이상)" "3m(이하)" 등 기준값 괄호도 생략 금지
   - 괄호가 여러 겹인 경우도 모두 원문 그대로 유지
8. 핵심요약을 반드시 작성합니다:
   - 위치: 【문제】 바로 아래, 【모범답안】 위
   - 형식: **【핵심요약】** 이 문제의 출제 포인트와 수험생이 반드시 알아야 할 한 문장
   - 내용: 이 문제가 왜 중요한지, 어떤 수치·조건이 핵심인지 명시"""


# ── PDF → 이미지 변환 ──────────────────────────────────────────

MAX_PX = 7000  # Claude API 최대 허용 픽셀 (8000px 제한, 안전 마진 포함)


def pdf_to_images_base64(pdf_path: str, dpi: int = DPI) -> list[dict]:
    """PDF 각 페이지를 base64 PNG로 변환 (Claude API 8000px 제한 자동 처리)"""
    doc = fitz.open(pdf_path)
    pages = []
    mat = fitz.Matrix(dpi / 72, dpi / 72)

    print(f"PDF 로드 완료: {len(doc)}페이지, {dpi}DPI로 변환 중...")
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)

        # 8000px 초과 시 자동 축소
        if pix.width > MAX_PX or pix.height > MAX_PX:
            scale = MAX_PX / max(pix.width, pix.height)
            new_w = int(pix.width * scale)
            new_h = int(pix.height * scale)
            pix = pix.resize(new_w, new_h)
            if i == 0:
                print(f"  ※ 이미지 크기 초과 → {new_w}×{new_h}px로 자동 축소")

        img_bytes = pix.tobytes("png")
        b64 = base64.standard_b64encode(img_bytes).decode()
        pages.append({
            "page": i + 1,
            "b64": b64,
            "size_kb": len(img_bytes) // 1024,
        })
        if (i + 1) % 50 == 0:
            print(f"  변환 중: {i+1}/{len(doc)}페이지")

    doc.close()
    total_kb = sum(p["size_kb"] for p in pages)
    print(f"변환 완료: {len(pages)}페이지, 총 {total_kb:,}KB")
    return pages


# ── 청크 분할 ──────────────────────────────────────────────────

def chunk_pages(pages: list[dict], chunk_size: int) -> list[list[dict]]:
    return [pages[i:i + chunk_size] for i in range(0, len(pages), chunk_size)]


# ── Vision API 호출 ────────────────────────────────────────────

def build_image_blocks(chunk: list[dict]) -> list[dict]:
    """청크의 이미지를 API content 블록으로 변환"""
    blocks = []
    for p in chunk:
        blocks.append({
            "type": "text",
            "text": f"--- 페이지 {p['page']} ---",
        })
        blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": p["b64"],
            },
        })
    return blocks


def summarize_chunk(
    client: anthropic.Anthropic,
    chunk: list[dict],
    chunk_num: int,
    total_chunks: int,
) -> str:
    """청크(이미지 묶음)를 Vision으로 요약"""
    start_page = chunk[0]["page"]
    end_page = chunk[-1]["page"]

    print(f"\n[{chunk_num}/{total_chunks}] 페이지 {start_page}~{end_page} Vision 요약 중...", end="", flush=True)

    image_blocks = build_image_blocks(chunk)
    image_blocks.append({
        "type": "text",
        "text": (
            f"위 이미지는 소방시설관리사 2차 실기 수험서의 페이지 {start_page}~{end_page}입니다.\n\n"
            "【절대 규칙】\n"
            "- 문제·답안·보충정보의 원문 내용을 한 글자도 생략하지 마십시오\n"
            "- 두문자 암기전략은 원문 내용을 '대체'하는 것이 아니라 맨 마지막에 '추가'하는 것입니다\n"
            "- 수치(㎡, m, 층, 분, 개 등)는 반드시 원문과 동일하게 표기합니다\n"
            "- 법률·시행령·시행규칙·고시·기준 등 법령 명칭과 조·항·호 번호를 빠짐없이 포함합니다\n"
            "- 이상/이하/미만/초과 등 기준 표현, 예외·완화·면제 조건을 원문 그대로 유지합니다\n"
            "- 법령에서 정의하는 용어 정의도 생략하지 않습니다\n"
            "- ( ) 괄호 안 내용은 예외 없이 원문 그대로 포함합니다 (조건·단서·수치 모두)\n"
            "- 【핵심요약】을 반드시 작성합니다: 출제 포인트와 핵심 수치·조건을 한 문장으로\n\n"
            "각 문제를 system prompt 양식에 따라:\n"
            "【문제】→【모범답안】→【보충정보】→【두문자 암기전략】→【Strategist's Tip】 순서로 작성하십시오.\n\n"
            "이미지에 표가 있으면 마크다운 표로 변환하고, 필기 메모·강조 표시도 포함하십시오."
        ),
    })

    parts = []
    with client.messages.stream(
        model=MODEL,
        max_tokens=8192,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": image_blocks}],
    ) as stream:
        for text in stream.text_stream:
            parts.append(text)
            print(".", end="", flush=True)

    msg = stream.get_final_message()
    u = msg.usage
    cache_hit = getattr(u, "cache_read_input_tokens", 0)
    cache_write = getattr(u, "cache_creation_input_tokens", 0)
    print(
        f" 완료 | 입력 {u.input_tokens:,}tok  "
        f"캐시생성 {cache_write:,}tok  캐시적중 {cache_hit:,}tok  "
        f"출력 {u.output_tokens:,}tok"
    )
    return "".join(parts)


# ── 최종 통합 요약 ─────────────────────────────────────────────

def create_final_summary(client: anthropic.Anthropic, chunk_summaries: list[str]) -> str:
    """섹션별 요약 → 최종 통합 요약본"""
    print("\n\n전체 통합 요약 생성 중...")
    combined = "\n\n---\n\n".join(
        f"[섹션 {i+1}]\n{s}" for i, s in enumerate(chunk_summaries)
    )

    parts = []
    with client.messages.stream(
        model=MODEL,
        max_tokens=8192,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[
            {
                "role": "user",
                "content": (
                    "다음은 소방시설관리사 2차 실기 수험서 전체를 섹션별로 요약한 내용입니다.\n"
                    "이를 바탕으로 시험 합격을 위한 최종 통합 요약본을 작성해 주세요.\n\n"
                    "요구사항:\n"
                    "1. 각 문제마다 [번호] 제목 / 핵심요약 / 암기전략 / 항목 설명(두문자 bold) / 표(해당 시) / Strategist's Tip 순서 적용\n"
                    "2. 중복 문제는 통합하되 번호는 원문 기준 유지\n"
                    "3. 수치·법령 기준 누락 없이 포함, 단서·예외는 sub-항목 들여쓰기\n"
                    "4. 출제 빈도 높은 함정·패턴은 Strategist's Tip에 반드시 경고\n"
                    "5. 수험생이 최종 점검용으로 바로 활용할 수 있는 형태로 정리\n\n"
                    f"섹션별 요약:\n{combined}"
                ),
            }
        ],
    ) as stream:
        for text in stream.text_stream:
            parts.append(text)
            print(".", end="", flush=True)

    msg = stream.get_final_message()
    u = msg.usage
    cache_hit = getattr(u, "cache_read_input_tokens", 0)
    cache_write = getattr(u, "cache_creation_input_tokens", 0)
    print(
        f" 완료 | 입력 {u.input_tokens:,}tok  "
        f"캐시생성 {cache_write:,}tok  캐시적중 {cache_hit:,}tok  "
        f"출력 {u.output_tokens:,}tok"
    )
    return "".join(parts)


# ── 파일 저장 ──────────────────────────────────────────────────

def save_chunks(output_dir: Path, base_name: str, chunk_summaries: list[str]):
    """섹션별 요약 중간 저장"""
    chunks_file = output_dir / f"{base_name}_chunks.md"
    with open(chunks_file, "w", encoding="utf-8") as f:
        f.write(f"# {base_name} - 섹션별 요약\n\n")
        for i, s in enumerate(chunk_summaries):
            f.write(f"## 섹션 {i+1}\n\n{s}\n\n---\n\n")
    return chunks_file


def save_final(output_dir: Path, base_name: str, final_summary: str) -> Path:
    final_file = output_dir / f"{base_name}_final_summary.md"
    with open(final_file, "w", encoding="utf-8") as f:
        f.write(f"# {base_name} - 최종 통합 요약\n\n{final_summary}\n")
    return final_file


# ── 진행 상황 복원 (이어서 실행) ───────────────────────────────

def load_existing_chunks(chunks_file: Path) -> list[str]:
    """중간 저장된 청크 요약 복원"""
    if not chunks_file.exists():
        return []
    with open(chunks_file, encoding="utf-8") as f:
        content = f.read()
    sections = content.split("\n---\n\n")
    summaries = []
    for sec in sections[1:]:            # 첫 번째는 파일 헤더
        lines = sec.split("\n")
        body = "\n".join(lines[2:]).strip()   # "## 섹션 N" 헤더 제거
        if body:
            summaries.append(body)
    return summaries


# ── main ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="소방시설관리사 PDF Vision 요약 프로그램",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("pdf_path", help="스캔 PDF 파일 경로")
    parser.add_argument("--pages-per-chunk", type=int, default=PAGES_PER_CHUNK,
                        help="청크당 페이지 수 (Vision 비용 vs 문맥 트레이드오프)")
    parser.add_argument("--dpi", type=int, default=DPI,
                        help="이미지 해상도 (120=저화질/저비용, 200=고화질/고비용)")
    parser.add_argument("--start-page", type=int, default=1,
                        help="처리 시작 페이지 (이어서 실행 시)")
    parser.add_argument("--end-page", type=int, default=None,
                        help="처리 종료 페이지 (테스트 시 일부만 처리)")
    parser.add_argument("--no-final", action="store_true",
                        help="최종 통합 요약 생략 (섹션별 요약만 저장)")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR),
                        help="출력 디렉토리")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("오류: ANTHROPIC_API_KEY 환경변수를 설정해 주세요.")
        print("  export ANTHROPIC_API_KEY='your-api-key'")
        sys.exit(1)

    if not Path(args.pdf_path).exists():
        print(f"오류: PDF 파일을 찾을 수 없습니다: {args.pdf_path}")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    base_name = Path(args.pdf_path).stem
    chunks_file = output_dir / f"{base_name}_chunks.md"

    client = anthropic.Anthropic(api_key=api_key)

    # PDF → 이미지 변환
    all_pages = pdf_to_images_base64(args.pdf_path, dpi=args.dpi)

    # 페이지 범위 적용
    start_idx = args.start_page - 1
    end_idx = args.end_page if args.end_page else len(all_pages)
    pages = all_pages[start_idx:end_idx]
    print(f"처리 대상: 페이지 {args.start_page}~{end_idx} ({len(pages)}페이지)")

    chunks = chunk_pages(pages, args.pages_per_chunk)
    total_chunks = len(chunks)
    print(f"총 {total_chunks}개 청크 (청크당 최대 {args.pages_per_chunk}페이지)")

    # 이어서 실행: 기존 저장된 청크 복원
    chunk_summaries = load_existing_chunks(chunks_file)
    resume_from = len(chunk_summaries)
    if resume_from > 0:
        print(f"기존 요약 {resume_from}개 청크 복원 완료. 청크 {resume_from+1}부터 이어서 시작합니다.")

    # 청크별 요약
    for i, chunk in enumerate(chunks[resume_from:], start=resume_from + 1):
        summary = summarize_chunk(client, chunk, i, total_chunks)
        chunk_summaries.append(summary)
        save_chunks(output_dir, base_name, chunk_summaries)  # 매 청크마다 중간 저장

    print(f"\n섹션별 요약 저장 완료: {chunks_file}")

    # 최종 통합 요약
    if not args.no_final:
        final_summary = create_final_summary(client, chunk_summaries)
        final_file = save_final(output_dir, base_name, final_summary)
        print(f"최종 요약 저장 완료: {final_file}")
    else:
        print("최종 통합 요약 생략 (--no-final 옵션)")

    print("\n모든 작업 완료!")


if __name__ == "__main__":
    main()
