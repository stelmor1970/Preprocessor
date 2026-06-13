#!/usr/bin/env python3
"""압축 파이프라인 오케스트레이터.

흐름: (OCR) → 분해 → 정규화 → 보호마스킹 → 압축 → 검증 → 복원 → 카드 출력

검증을 통과하지 못한 카드는 압축본을 버리고 원문(정규화본)을 유지한다.

사용:
  # 이미 전사된 텍스트로 (OCR 생략)
  python run_pipeline.py --text-file tests/golden/Q01_raw.txt

  # 압축 없이 보호/검증만 (API 불필요, Phase 1 동작 확인)
  python run_pipeline.py --text-file tests/golden/Q01_raw.txt --no-compress

  # 스캔 PDF부터 끝까지
  python run_pipeline.py --pdf 수험서.pdf
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pipeline import normalize_text, restore, verify_compression
from pipeline.protect import Protector
from pipeline.segment import segment
from pipeline.cards import Card, save_json, save_markdown, save_report

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"


def load_config() -> dict:
    cfg = json.loads((CONFIG / "config.json").read_text(encoding="utf-8"))
    terms = json.loads((CONFIG / "terms.json").read_text(encoding="utf-8"))
    mnem = json.loads((CONFIG / "mnemonics.json").read_text(encoding="utf-8"))
    cfg["terms"] = terms
    cfg["mnemonics"] = mnem
    cfg["mnemonic_words"] = [w for k, v in mnem.items() if k != "_comment" for w in v]
    return cfg


def mnemonic_for(card_id: str, normalized: str, mnemonics: dict) -> str:
    """정규화 본문에 등장하는 두음 암기어를 찾아 반환 (간단 매칭)."""
    for key, words in mnemonics.items():
        if key == "_comment":
            continue
        if sum(1 for w in words if w in normalized) >= max(1, len(words) // 2):
            return key
    return ""


def get_text(args) -> str:
    if args.text_file:
        return Path(args.text_file).read_text(encoding="utf-8")
    if args.pdf:
        import anthropic
        from pipeline.ocr import ocr_pdf
        client = anthropic.Anthropic()
        return ocr_pdf(
            client, args.pdf, model=args.model, dpi=args.dpi,
            start=args.start_page, end=args.end_page,
        )
    raise SystemExit("오류: --text-file 또는 --pdf 중 하나를 지정하세요.")


def main():
    ap = argparse.ArgumentParser(description="수험서 압축 파이프라인")
    src = ap.add_argument_group("입력")
    src.add_argument("--pdf", help="스캔 PDF 경로 (Vision OCR 수행)")
    src.add_argument("--text-file", help="이미 전사된 텍스트 파일 경로")
    ap.add_argument("--no-compress", action="store_true", help="압축 생략 (보호/검증만, API 불필요)")
    ap.add_argument("--output-dir", default="output", help="출력 폴더")
    ap.add_argument("--model", default=None, help="압축/OCR 모델 (기본: config.json)")
    ap.add_argument("--batch-size", type=int, default=None, help="압축 배치 크기")
    ap.add_argument("--dpi", type=int, default=120, help="OCR 해상도")
    ap.add_argument("--start-page", type=int, default=1)
    ap.add_argument("--end-page", type=int, default=None)
    args = ap.parse_args()

    cfg = load_config()
    model = args.model or cfg["model"]
    batch_size = args.batch_size or cfg.get("batch_size", 6)
    ratio_range = (cfg["compression_ratio"]["min"], cfg["compression_ratio"]["max"])

    if not args.no_compress and not os.environ.get("ANTHROPIC_API_KEY"):
        print("오류: 압축에는 ANTHROPIC_API_KEY가 필요합니다. (--no-compress로 보호/검증만 가능)")
        sys.exit(1)

    # ── 입력 텍스트 확보 ──
    text = get_text(args)

    # ── 분해 → 정규화 → 마스킹 ──
    protector = Protector(terms=cfg["terms"], mnemonics=cfg["mnemonic_words"])
    raw_cards = segment(text)
    if not raw_cards:
        print("처리할 문제를 찾지 못했습니다.")
        sys.exit(1)
    print(f"문제 {len(raw_cards)}개 분해 완료")

    prepared = []  # {"id","norm","masked","mapping","mnemonic"}
    for rc in raw_cards:
        norm = normalize_text(rc["raw"])
        masked, mapping = protector.mask(norm, namespace=rc["id"])
        prepared.append({
            "id": rc["id"],
            "norm": norm,
            "masked": masked,
            "mapping": mapping,
            "mnemonic": mnemonic_for(rc["id"], norm, cfg["mnemonics"]),
        })

    # ── 압축 (선택) ──
    compressed_map: dict[str, str] = {}
    if not args.no_compress:
        import anthropic
        from pipeline.compress import compress_batch
        client = anthropic.Anthropic()
        items = [{"id": p["id"], "masked": p["masked"]} for p in prepared]
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            ids = ", ".join(b["id"] for b in batch)
            print(f"압축 중: {ids} ...", end="", flush=True)
            try:
                result = compress_batch(client, batch, model=model)
                compressed_map.update(result)
                print(" 완료")
            except Exception as e:
                print(f" 실패({e}) — 해당 배치 원문 유지")

    # ── 검증 → 채택/복원 → 카드 ──
    cards: list[Card] = []
    for p in prepared:
        comp_masked = compressed_map.get(p["id"])
        if comp_masked is None:
            # 압축 안 함 또는 실패 → 원문 유지
            card = Card(
                id=p["id"], raw=p["norm"], compressed=p["norm"],
                ratio=0.0, mnemonic=p["mnemonic"], adopted=False,
                verify={"checks": [{"name": "compression", "status": "WARN", "detail": "압축 미수행"}]},
            )
        else:
            v = verify_compression(p["norm"], comp_masked, p["mapping"], ratio_range)
            if v["passed"]:
                card = Card(
                    id=p["id"], raw=p["norm"], compressed=v["restored"],
                    ratio=v["ratio"], mnemonic=p["mnemonic"], adopted=True, verify=v,
                )
            else:
                # 검증 실패 → 원문 유지 + 리포트 기록
                card = Card(
                    id=p["id"], raw=p["norm"], compressed=p["norm"],
                    ratio=0.0, mnemonic=p["mnemonic"], adopted=False, verify=v,
                )
        cards.append(card)

    # ── 출력 ──
    out = Path(args.output_dir)
    save_json(cards, out / "cards.json")
    save_markdown(cards, out / "cards.md")
    report = save_report(cards, out / "report.json")

    print("\n" + "=" * 50)
    print(f"총 {report['total']}장 · 채택 {report['adopted']} · 실패 {report['rejected']}")
    if report["rejected_ids"]:
        print(f"검증 실패(원문 유지): {report['rejected_ids']}")
    if report["adopted"]:
        print(f"채택 카드 평균 압축률: {report['avg_ratio_adopted']:.1%}")
    print(f"출력: {out}/cards.json, cards.md, report.json")


if __name__ == "__main__":
    main()
