#!/usr/bin/env python3
"""
소방시설관리사 2차 실기 수험서 PDF 요약 프로그램
로컬 실행 기반, Claude API 사용
"""

import sys
import os
import argparse
from pathlib import Path

import fitz  # PyMuPDF
import anthropic

MODEL = "claude-opus-4-8"
CHUNK_PAGES = 20  # 한 번에 처리할 페이지 수
OUTPUT_DIR = Path("summaries")

SYSTEM_PROMPT = """당신은 소방시설관리사 2차 실기 시험 전문 강사입니다.
수험서의 내용을 분석하여 수험생이 시험에 합격할 수 있도록 핵심 내용을 아래 양식에 맞춰 정리해 주세요.

--- 출력 양식 ---

각 문제는 아래 구조로 작성할 것:

1. 제목: [번호] 주제명
   (예: [01] 방화구획의 구획기준 및 완화 적용)

2. 핵심요약: 한 줄로 시험 출제 포인트 요약
   (예: 방화구획은 화재 확산 방지를 위한 구획이며, 면적·층·용도별 기준과 완화 조건이 핵심)

3. 암기전략: 두문자 또는 키워드 나열
   형식 — 암기전략: '두문자-두문자-두문자'
   · 각 두문자 글자 + 설명 (예: 면 — 면적기준 3,000㎡ 이내)
   · 수치·숫자는 괄호로 병기

4. 항목별 상세:
   · 핵심 항목을 bullet(·)으로 나열
   · 수치·기준·예외는 괄호 또는 대시로 명시
   · 서브 조건은 한 단계 들여쓰기

5. 비교 표 (기준이 2개 이상 비교될 때):
   | 구분 | 항목A | 항목B |
   |------|-------|-------|
   | 내용 | 값    | 값    |

6. Strategist's Tip:
   ⚠️ [Strategist's Tip] 시험 함정·출제 패턴 경고
   · 혼동하기 쉬운 수치나 예외사항 명시

---

규칙:
- 각 항목은 간결하고 명확하게 작성
- 수험생이 쉽게 암기할 수 있도록 구조화
- 수치·법령 기준은 반드시 포함"""


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """PDF에서 페이지별 텍스트 추출"""
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            pages.append({"page": i + 1, "text": text})
    doc.close()
    print(f"총 {len(pages)}페이지 텍스트 추출 완료")
    return pages


def chunk_pages(pages: list[dict], chunk_size: int) -> list[list[dict]]:
    """페이지를 청크로 분할"""
    return [pages[i:i + chunk_size] for i in range(0, len(pages), chunk_size)]


def summarize_chunk(client: anthropic.Anthropic, chunk: list[dict], chunk_num: int, total_chunks: int) -> str:
    """청크 단위 요약 생성 (스트리밍)"""
    start_page = chunk[0]["page"]
    end_page = chunk[-1]["page"]
    content = "\n\n".join(f"[페이지 {p['page']}]\n{p['text']}" for p in chunk)

    print(f"\n[{chunk_num}/{total_chunks}] 페이지 {start_page}~{end_page} 요약 중...", end="", flush=True)

    summary_parts = []
    with client.messages.stream(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"다음은 수험서의 페이지 {start_page}~{end_page} 내용입니다. system prompt의 출력 양식에 맞춰 각 문제(주제)별로 요약 정리해 주세요.\n\n{content}"
            }
        ]
    ) as stream:
        for text in stream.text_stream:
            summary_parts.append(text)
            print(".", end="", flush=True)

    print(" 완료")
    return "".join(summary_parts)


def create_final_summary(client: anthropic.Anthropic, chunk_summaries: list[str]) -> str:
    """전체 청크 요약을 통합하여 최종 요약본 생성"""
    print("\n전체 통합 요약 생성 중...")
    combined = "\n\n---\n\n".join(
        f"[섹션 {i+1}]\n{s}" for i, s in enumerate(chunk_summaries)
    )

    result_parts = []
    with client.messages.stream(
        model=MODEL,
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"""다음은 소방시설관리사 2차 실기 수험서 전체를 섹션별로 요약한 내용입니다.
이를 바탕으로 시험 합격을 위한 최종 통합 요약본을 작성해 주세요.

요구사항:
1. system prompt의 출력 양식([번호] 제목 / 핵심요약 / 암기전략 / 항목별 상세 / 비교 표 / Strategist's Tip)을 각 문제마다 적용
2. 중복 문제는 통합하되 번호는 원문 기준 유지
3. 출제 빈도가 높은 항목은 Strategist's Tip에 강조
4. 수험생이 최종 점검용으로 활용할 수 있는 형태로 전체 정리

섹션별 요약:
{combined}"""
            }
        ]
    ) as stream:
        for text in stream.text_stream:
            result_parts.append(text)
            print(".", end="", flush=True)

    print(" 완료")
    return "".join(result_parts)


def save_output(output_dir: Path, pdf_name: str, chunk_summaries: list[str], final_summary: str):
    """결과 파일 저장"""
    output_dir.mkdir(exist_ok=True)
    base_name = Path(pdf_name).stem

    # 청크별 요약 저장
    chunks_file = output_dir / f"{base_name}_chunks.md"
    with open(chunks_file, "w", encoding="utf-8") as f:
        f.write(f"# {base_name} - 섹션별 요약\n\n")
        for i, summary in enumerate(chunk_summaries):
            f.write(f"## 섹션 {i+1}\n\n{summary}\n\n---\n\n")
    print(f"\n섹션별 요약 저장: {chunks_file}")

    # 최종 통합 요약 저장
    final_file = output_dir / f"{base_name}_final_summary.md"
    with open(final_file, "w", encoding="utf-8") as f:
        f.write(f"# {base_name} - 최종 통합 요약\n\n{final_summary}\n")
    print(f"최종 요약 저장: {final_file}")

    return final_file


def main():
    parser = argparse.ArgumentParser(description="소방시설관리사 PDF 요약 프로그램")
    parser.add_argument("pdf_path", help="PDF 파일 경로")
    parser.add_argument("--chunk-pages", type=int, default=CHUNK_PAGES, help=f"청크당 페이지 수 (기본: {CHUNK_PAGES})")
    parser.add_argument("--no-final", action="store_true", help="최종 통합 요약 생략")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="출력 디렉토리")
    parser.add_argument("--start-chunk", type=int, default=1, help="시작 청크 번호 (이어서 실행 시)")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("오류: ANTHROPIC_API_KEY 환경변수를 설정해 주세요.")
        print("  export ANTHROPIC_API_KEY='your-api-key'")
        sys.exit(1)

    if not Path(args.pdf_path).exists():
        print(f"오류: PDF 파일을 찾을 수 없습니다: {args.pdf_path}")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    print(f"PDF 파일 로드 중: {args.pdf_path}")
    pages = extract_text_from_pdf(args.pdf_path)
    chunks = chunk_pages(pages, args.chunk_pages)
    total_chunks = len(chunks)

    print(f"총 {total_chunks}개 청크로 분할 (청크당 최대 {args.chunk_pages}페이지)")

    base_name = Path(args.pdf_path).stem
    chunks_file = output_dir / f"{base_name}_chunks.md"

    # 이어서 실행하는 경우 기존 요약 로드
    chunk_summaries = []
    if args.start_chunk > 1 and chunks_file.exists():
        print(f"기존 요약 파일 로드 중 (청크 1~{args.start_chunk-1})...")
        # 간단히 파일에서 섹션 분리
        with open(chunks_file, encoding="utf-8") as f:
            content = f.read()
        sections = content.split("\n---\n\n")
        for sec in sections[1:args.start_chunk]:  # 헤더 제외
            body = "\n".join(sec.split("\n")[2:]).strip()
            chunk_summaries.append(body)

    # 청크별 요약
    for i, chunk in enumerate(chunks[args.start_chunk - 1:], start=args.start_chunk):
        summary = summarize_chunk(client, chunk, i, total_chunks)
        chunk_summaries.append(summary)

        # 중간 저장 (진행 중 저장)
        with open(chunks_file, "w", encoding="utf-8") as f:
            f.write(f"# {base_name} - 섹션별 요약\n\n")
            for j, s in enumerate(chunk_summaries):
                f.write(f"## 섹션 {j+1}\n\n{s}\n\n---\n\n")

    # 최종 통합 요약
    final_summary = ""
    if not args.no_final:
        final_summary = create_final_summary(client, chunk_summaries)

    final_file = save_output(output_dir, args.pdf_path, chunk_summaries, final_summary)

    print(f"\n완료! 최종 요약본: {final_file}")


if __name__ == "__main__":
    main()
