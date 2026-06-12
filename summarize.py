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
수험서의 내용을 분석하여 수험생이 시험에 합격할 수 있도록 핵심 내용을 아래 양식에 맞춰 정리해 주세요.

--- 출력 양식 (반드시 준수) ---

각 주제(문제)는 아래 6단계 구조로 작성합니다.

[단계 1] 제목
숫자. [번호] 주제명
예) 1. [01] 방화구획의 구획기준 및 완화 적용

[단계 2] 핵심요약
한 문장으로 시험 출제 포인트 요약. 수험생이 왜 이 주제를 공부해야 하는지 동기를 부여하는 문장.
예) 방화구획은 화재 확산 방지의 최후 보루입니다. 면적 기준과 완화 조건을 수치 중심으로 정확히 정복해야 합니다.

[단계 3] 암기전략
형식: 주제명 암기전략: '두문자그룹1-두문자그룹2'
- 두문자 각 글자를 앞에 배치하고 뒤에 설명 서술
- 수치·숫자는 반드시 포함 (괄호 또는 한글 병기)
- 단서·예외 조건은 줄바꿈 후 들여쓰기로 추가
예)
구획기준 암기전략: '십일매직-필이주'
십: 10층 이하의 층은 바닥면적 1천㎡ 이내마다 구획 (스프링클러 등 자동식 소화설비 설치 시 3천㎡)
일: 11층 이상의 층은 바닥면적 200㎡(스프링클러 설치 시 600㎡) 이내마다 구획
   단, 벽·반자 마감이 불연재료인 경우 500㎡(스프링클러 시 1,500㎡) 이내
매: 매 층마다 구획 (직접 연결하는 지하 1층 경사로 부위는 제외)

[단계 4] 핵심 체크 (해당 시)
주제에서 자주 혼동되거나 추가 설명이 필요한 핵심 정의·조건을 1~3줄로 기술.
예) 핵심 체크: 필로티 구조란 벽면적의 2분의 1 이상이 그 층의 바닥면에서 위층 바닥 아래면까지 공간으로 된 것만 해당함.

[단계 5] 비교 표 (비교 기준이 2개 이상일 때 반드시 작성)
마크다운 표 형식, 3열 이내.
예)
| 구분 | 차염성능(연기·불꽃) | 차열성능(열) |
|------|------------------|------------|
| 60분+ 방화문 | 60분 이상 | 30분 이상 |
| 60분 방화문  | 60분 이상 | - |
| 30분 방화문  | 30분 이상 60분 미만 | - |

[단계 6] Strategist's Tip
형식: [Strategist's Tip] 경고 내용
시험에서 자주 바꿔치는 수치, 혼동하기 쉬운 조건, 출제 패턴 경고를 1~2문장으로 기술.
예) [Strategist's Tip] 자동방화셔터의 설치 거리(3m)는 시험에서 5m로 자주 바꿔치는 단골 함정입니다. 반드시 '삼(3)'을 함께 암기하십시오.

--- 규칙 ---
- 각 단계는 생략하지 말 것 (핵심 체크·표는 해당 없으면 생략 가능)
- 수치·법령 기준은 빠짐없이 포함
- 단서·예외 조건은 반드시 들여쓰기 sub-항목으로 처리
- 비교 가능한 항목이 2개 이상이면 반드시 표로 정리
- 암기전략의 두문자 글자는 설명 맨 앞에 단독 배치 (예: 십: 설명)"""


# ── PDF → 이미지 변환 ──────────────────────────────────────────

def pdf_to_images_base64(pdf_path: str, dpi: int = DPI) -> list[dict]:
    """PDF 각 페이지를 base64 PNG로 변환"""
    doc = fitz.open(pdf_path)
    pages = []
    mat = fitz.Matrix(dpi / 72, dpi / 72)   # 72dpi 기준 배율

    print(f"PDF 로드 완료: {len(doc)}페이지, {dpi}DPI로 변환 중...")
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)  # 그레이스케일로 용량 절감
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
            f"위 이미지는 소방시설관리사 2차 실기 수험서의 페이지 {start_page}~{end_page}입니다.\n"
            "system prompt의 출력 양식에 맞춰 각 문제(주제)별로 정리해 주세요.\n\n"
            "요구사항:\n"
            "- 각 문제마다 [번호] 제목 / 핵심요약 / 암기전략 / 항목 설명 / 표(해당 시) / Strategist's Tip 순서로 작성\n"
            "- 두문자 글자는 **bold** 처리\n"
            "- 수치·기준은 괄호로 명시, 단서·예외는 sub-항목 들여쓰기\n"
            "- 이미지에 표·그림이 있으면 내용을 마크다운 표로 변환\n"
            "- 필기 메모나 강조 표시도 중요 정보로 포함"
        ),
    })

    parts = []
    with client.messages.stream(
        model=MODEL,
        max_tokens=4096,
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
