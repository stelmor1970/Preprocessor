"""클로드 비전 OCR — 스캔 PDF → 충실 전사 텍스트.

요약·해설 없이 한 글자도 바꾸지 않고 그대로 옮긴다.
괄호 안 한자/영문, 수치·단위·한정어, 법령명·조항번호를 정확히 보존한다.
(요약은 단계 2 압축에서 마스킹 보호 하에 수행한다.)
"""

from __future__ import annotations

import base64

import anthropic
import fitz  # PyMuPDF

MAX_PX = 7000

OCR_SYSTEM = """당신은 정밀 OCR 전사기입니다.
이미지의 텍스트를 한 글자도 빠뜨리거나 바꾸지 말고 그대로 옮겨 적으십시오.

규칙:
- 요약·해설·재배열 금지. 보이는 그대로 전사.
- 괄호 안 한자·영문 병기(예: (器機)), 수치·단위(㎡, m, 층, 분 등), 이상/이하/이내 등 한정어를 정확히 보존.
- 법령명 「...」, 제○조·제○항·제○호·별표 번호를 정확히 전사.
- 문제 번호 [01], [02] 등 구조와 항목 번호(1. ①②③ (1))를 유지.
- 표는 마크다운 표로 변환.
- 페이지 머리말·꼬리말·페이지 번호는 생략."""


def _page_images(pdf_path: str, dpi: int, start: int, end: int | None) -> list[dict]:
    doc = fitz.open(pdf_path)
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pages = []
    last = end if end else len(doc)
    for i in range(start - 1, min(last, len(doc))):
        pix = doc[i].get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
        if pix.width > MAX_PX or pix.height > MAX_PX:
            scale = MAX_PX / max(pix.width, pix.height)
            pix = pix.resize(int(pix.width * scale), int(pix.height * scale))
        b64 = base64.standard_b64encode(pix.tobytes("png")).decode()
        pages.append({"page": i + 1, "b64": b64})
    doc.close()
    return pages


def ocr_pdf(
    client: anthropic.Anthropic,
    pdf_path: str,
    model: str = "claude-opus-4-8",
    dpi: int = 120,
    pages_per_chunk: int = 4,
    start: int = 1,
    end: int | None = None,
) -> str:
    """PDF를 충실 전사하여 전체 텍스트를 반환."""
    pages = _page_images(pdf_path, dpi, start, end)
    print(f"OCR 대상: {len(pages)}페이지")

    out = []
    for i in range(0, len(pages), pages_per_chunk):
        chunk = pages[i : i + pages_per_chunk]
        s, e = chunk[0]["page"], chunk[-1]["page"]
        print(f"  전사 중: 페이지 {s}~{e} ...", end="", flush=True)

        content = []
        for p in chunk:
            content.append({"type": "text", "text": f"--- 페이지 {p['page']} ---"})
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": p["b64"]},
            })
        content.append({"type": "text", "text": "위 페이지들을 규칙에 따라 그대로 전사하십시오."})

        msg = client.messages.create(
            model=model,
            max_tokens=8192,
            system=[{"type": "text", "text": OCR_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        out.append(text)
        print(" 완료")

    return "\n\n".join(out)
