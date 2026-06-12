/**
 * 소방시설관리사 2차 실기 — 만제 두문자암기 요약 생성기
 * Node.js + docx 라이브러리
 *
 * 입력: /mnt/user-data/uploads/만제77까지.docx (mammoth으로 파싱)
 * 출력: /mnt/user-data/outputs/소방관리사2차_만제01-29_두문자암기요약.docx
 */

const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, WidthType, BorderStyle, ShadingType,
  convertInchesToTwip, convertMillimetersToTwip,
} = require("docx");
const fs = require("fs");
const path = require("path");
const mammoth = require("mammoth");

// ─────────────────────────────────────────
// 색상 팔레트 (기존 fire_xxx.js 스타일 유지)
// ─────────────────────────────────────────
const COLOR = {
  HEADER_BG:   "1F4E79",   // 진한 남색 — 문제 번호 헤더 배경
  HEADER_FG:   "FFFFFF",   // 흰색 — 헤더 텍스트
  MNEMONIC_BG: "FFF2CC",   // 연노랑 — 핵심요약·암기전략 배경
  MNEMONIC_BD: "FFD700",   // 금색 — 암기전략 테두리
  LAW_BG:      "E2EFDA",   // 연초록 — Strategist's Tip 배경
  LAW_BD:      "70AD47",   // 초록 — Tip 테두리
  RED:         "C00000",   // 진빨강 — 두문자 강조
  TABLE_HEADER:"2E75B6",   // 파랑 — 표 헤더 배경
  TABLE_FG:    "FFFFFF",   // 흰색 — 표 헤더 텍스트
  BULLET_NUM:  "2F5496",   // 진파랑 — 수치·숫자 강조
};

const FONT = "맑은 고딕";

// 문서 여백 (mm → twip)
const MARGIN = {
  top:    convertMillimetersToTwip(20),
  bottom: convertMillimetersToTwip(20),
  left:   convertMillimetersToTwip(22),
  right:  convertMillimetersToTwip(22),
};

// ─────────────────────────────────────────
// 헬퍼 함수들
// ─────────────────────────────────────────

/** 셀 공통 배경 Shading */
function shading(fill) {
  return { type: ShadingType.CLEAR, color: "auto", fill };
}

/** 박스 테두리 (4변 동일 색상·굵기) */
function boxBorder(color, size = 12) {
  const b = { style: BorderStyle.SINGLE, size, color };
  return { top: b, bottom: b, left: b, right: b };
}

/** 일반 문단 생성 */
function para(runs, opts = {}) {
  return new Paragraph({
    children: Array.isArray(runs) ? runs : [runs],
    spacing: { before: opts.before ?? 40, after: opts.after ?? 40 },
    indent: opts.indent ? { left: convertMillimetersToTwip(opts.indent) } : undefined,
    alignment: opts.align ?? AlignmentType.LEFT,
    shading: opts.bg ? shading(opts.bg) : undefined,
    border: opts.border ?? undefined,
  });
}

/** TextRun 단축 생성 */
function run(text, opts = {}) {
  return new TextRun({
    text,
    font: FONT,
    size: (opts.size ?? 10) * 2,
    bold: opts.bold ?? false,
    italics: opts.italic ?? false,
    color: opts.color ?? undefined,
    highlight: opts.highlight ?? undefined,
  });
}

/** 1. h1 헤더 단락 — HEADER_BG 배경, 흰색 굵은 텍스트 */
function makeHeader(number, title) {
  return new Paragraph({
    children: [
      run(`[${String(number).padStart(2, "0")}] ${title}`, {
        bold: true, size: 13, color: COLOR.HEADER_FG,
      }),
    ],
    heading: HeadingLevel.HEADING_1,
    shading: shading(COLOR.HEADER_BG),
    spacing: { before: 200, after: 80 },
    border: boxBorder(COLOR.HEADER_BG, 6),
  });
}

/** 2. 핵심요약 1줄 단락 — 굵은 이탤릭, MNEMONIC_BG 배경 */
function makeSummary(text) {
  return para(
    run(text, { bold: true, italic: true, size: 10 }),
    { bg: COLOR.MNEMONIC_BG, before: 60, after: 30 },
  );
}

/**
 * 3. 암기전략 박스 — "암기전략: '두문자'"
 * acroChars: [{ ch, desc }] 두문자 글자+설명 배열
 * acroLabel: 전체 두문자 레이블 (예: "소-경-배-배-거-전")
 */
function makeMnemonicBox(acroLabel, acroChars) {
  const titleRun = run("암기전략: '", { bold: true, size: 10 });
  const endRun   = run("'", { bold: true, size: 10 });

  // 두문자 글자들 빨강 bold
  const acroRuns = [];
  acroLabel.split("").forEach((ch) => {
    if (ch === "-" || ch === " ") {
      acroRuns.push(run(ch, { size: 10 }));
    } else {
      acroRuns.push(run(ch, { bold: true, color: COLOR.RED, size: 10 }));
    }
  });

  const labelPara = para(
    [titleRun, ...acroRuns, endRun],
    {
      bg: COLOR.MNEMONIC_BG,
      border: boxBorder(COLOR.MNEMONIC_BD, 12),
      before: 40,
      after: 10,
    },
  );

  // 두문자 각 글자 설명 행
  const descParas = acroChars.map(({ ch, desc }) =>
    para(
      [
        run(`${ch}`, { bold: true, color: COLOR.RED, size: 10 }),
        run(` — ${desc}`, { size: 10 }),
      ],
      {
        bg: COLOR.MNEMONIC_BG,
        indent: 6,
        before: 20,
        after: 20,
        border: {
          left: { style: BorderStyle.SINGLE, size: 12, color: COLOR.MNEMONIC_BD },
        },
      },
    ),
  );

  return [labelPara, ...descParas];
}

/**
 * 4. 항목 bullet
 * items: [{ ch, desc, subs: ["서브 설명"] }]
 */
function makeBullets(items) {
  const paras = [];
  items.forEach(({ ch, desc, subs }) => {
    // 수치 숫자 (괄호 포함) 파란 강조
    const descRuns = parseDescWithNumbers(ch, desc);
    paras.push(
      new Paragraph({
        children: descRuns,
        bullet: { level: 0 },
        spacing: { before: 30, after: 20 },
      }),
    );
    if (subs) {
      subs.forEach((s) =>
        paras.push(
          new Paragraph({
            children: [run(s, { size: 9 })],
            bullet: { level: 1 },
            spacing: { before: 15, after: 15 },
          }),
        ),
      );
    }
  });
  return paras;
}

/** 수치/숫자를 파란색으로 강조하는 run 분리 파서 */
function parseDescWithNumbers(ch, desc) {
  const runs = [];
  if (ch) {
    runs.push(run(ch, { bold: true, size: 10 }));
    runs.push(run(" — ", { size: 10 }));
  }
  // 괄호 포함 숫자 패턴: \d+[.]?\d*\s*[a-zA-Z%°㎡㎥㎜m]*|\(\d[^)]*\)
  const parts = desc.split(/(\(?\d+(?:\.\d+)?(?:\s*[a-zA-Z%°㎡㎥㎜m이상이하미만초과]+)?\)?)/g);
  parts.forEach((p, i) => {
    if (i % 2 === 1) {
      runs.push(run(p, { color: COLOR.BULLET_NUM, bold: true, size: 10 }));
    } else if (p) {
      runs.push(run(p, { size: 10 }));
    }
  });
  return runs;
}

/**
 * 5. 비교 표
 * headers: ["구분", "A", "B"]
 * rows: [["내용", "값A", "값B"], ...]
 */
function makeTable(headers, rows) {
  const headerRow = new TableRow({
    children: headers.map((h) =>
      new TableCell({
        children: [para(run(h, { bold: true, color: COLOR.TABLE_FG, size: 9 }))],
        shading: shading(COLOR.TABLE_HEADER),
        width: { size: Math.floor(100 / headers.length), type: WidthType.PERCENTAGE },
      }),
    ),
    tableHeader: true,
  });

  const dataRows = rows.map((row) =>
    new TableRow({
      children: row.map((cell, ci) =>
        new TableCell({
          children: [para(run(cell, { size: 9, bold: ci === 0 }))],
          shading: ci === 0 ? shading("EEF3FB") : undefined,
          width: { size: Math.floor(100 / headers.length), type: WidthType.PERCENTAGE },
        }),
      ),
    }),
  );

  return new Table({
    rows: [headerRow, ...dataRows],
    width: { size: 100, type: WidthType.PERCENTAGE },
    margins: {
      top: convertMillimetersToTwip(1.5),
      bottom: convertMillimetersToTwip(1.5),
      left: convertMillimetersToTwip(2),
      right: convertMillimetersToTwip(2),
    },
  });
}

/** 6. Strategist's Tip 박스 */
function makeTipBox(tipText) {
  const titlePara = para(
    run("⚠️  [Strategist's Tip]", { bold: true, size: 10 }),
    { bg: COLOR.LAW_BG, border: boxBorder(COLOR.LAW_BD, 12), before: 60, after: 10 },
  );
  const bodyPara = para(
    run(tipText, { size: 10 }),
    {
      bg: COLOR.LAW_BG,
      before: 10,
      after: 60,
      border: {
        left:   { style: BorderStyle.SINGLE, size: 18, color: COLOR.LAW_BD },
        bottom: { style: BorderStyle.SINGLE, size: 12, color: COLOR.LAW_BD },
        right:  { style: BorderStyle.SINGLE, size: 12, color: COLOR.LAW_BD },
      },
    },
  );
  return [titlePara, bodyPara];
}

/** 문제 한 세트를 단락 배열로 조립 */
function buildProblem({ number, title, summary, acroLabel, acroChars, bullets, table, tip }) {
  const elements = [];
  elements.push(makeHeader(number, title));
  elements.push(makeSummary(summary));
  elements.push(...makeMnemonicBox(acroLabel, acroChars));
  elements.push(...makeBullets(bullets));
  if (table) {
    elements.push(new Paragraph({ children: [], spacing: { before: 60 } }));
    elements.push(makeTable(table.headers, table.rows));
  }
  elements.push(...makeTipBox(tip));
  // 문제 간 구분 공백
  elements.push(new Paragraph({ children: [], spacing: { before: 120, after: 0 } }));
  return elements;
}

// ─────────────────────────────────────────
// 만제 데이터 — [01]~[29]
// 실제 내용은 아래 PROBLEMS 배열에 채워 넣음
// ─────────────────────────────────────────

/**
 * 소스 DOCX에서 텍스트를 추출해 PROBLEMS 배열을 동적으로 채우거나,
 * 아래 하드코딩 데이터를 직접 사용하세요.
 * extractProblems() 함수는 mammoth로 DOCX를 파싱합니다.
 */

const PROBLEMS = [
  // ──────────────── [01] ────────────────
  {
    number: 1,
    title: "소화기구 및 자동소화장치의 설치 기준",
    summary: "소화기구는 보행거리 20m 이내, 각층·각 구획마다 설치. 능력단위 산정이 핵심.",
    acroLabel: "소-경-배-배-거-전",
    acroChars: [
      { ch: "소", desc: "소화능력단위 산정 (바닥면적 기준)" },
      { ch: "경", desc: "경계구역(구획) 단위 설치" },
      { ch: "배", desc: "배치 — 보행거리 20m(대형 30m) 이내" },
      { ch: "배", desc: "배수 — 능력단위 × 추가기준 적용" },
      { ch: "거", desc: "거치 높이 — 바닥에서 1.5m 이하" },
      { ch: "전", desc: "전용함 설치 (옥내 3.3㎡ 이상 구획 시)" },
    ],
    bullets: [
      { ch: "능력단위", desc: "소화기 1단위 = 바닥면적 33㎡(내화) / 16.5㎡(비내화)", subs: ["주방: 추가로 자동확산소화기 또는 K급 소화기 필수"] },
      { ch: "배치거리", desc: "보행거리 20m 이내 (대형 소화기 30m 이내)" },
      { ch: "설치높이", desc: "바닥면으로부터 1.5m 이하에 설치" },
      { ch: "능력단위 가산", desc: "내화구조 이상이면 3배 이내 감소 가능" },
    ],
    table: {
      headers: ["구분", "내화구조", "기타구조"],
      rows: [
        ["능력단위 기준", "33㎡ / 1단위", "16.5㎡ / 1단위"],
        ["보행거리",     "20m 이내",    "20m 이내"],
        ["대형소화기",   "30m 이내",    "30m 이내"],
      ],
    },
    tip: "내화 33 / 비내화 16.5는 자주 출제. 주방에서 K급(주방용) 소화기 의무화 조항 혼동 주의. 능력단위 감소 조건(불연·내화구조 확인)도 단골 함정.",
  },

  // ──────────────── [02] ────────────────
  {
    number: 2,
    title: "옥내소화전설비 설치 기준",
    summary: "수평거리 25m, 방수압 0.17MPa, 방수량 130L/min — 3가지 수치가 핵심.",
    acroLabel: "수-압-량-개-펌-유",
    acroChars: [
      { ch: "수", desc: "수평거리 25m(호스 포함) 이내" },
      { ch: "압", desc: "압력 최소 0.17MPa (최고 0.7MPa)" },
      { ch: "량", desc: "방수량 130L/min 이상" },
      { ch: "개", desc: "개폐밸브 높이 0.8~1.5m" },
      { ch: "펌", desc: "펌프 기동 — 기동용 수압개폐장치(압력챔버)" },
      { ch: "유", desc: "유효수량 최소 2개(층수별 기준)" },
    ],
    bullets: [
      { ch: "방수압", desc: "0.17MPa 이상 ~ 0.7MPa 이하" },
      { ch: "방수량", desc: "130L/min 이상, 동시 개방 기준 최소 2개" },
      { ch: "수평거리", desc: "소화전 → 방호구역 내 임의 지점 25m 이내" },
      { ch: "수원", desc: "2.6㎥(소형 5층 이하) / 5.2㎥(대형·6층 이상)" },
    ],
    table: {
      headers: ["항목", "옥내소화전", "호스릴 옥내"],
      rows: [
        ["방수압",    "0.17MPa 이상",  "0.17MPa 이상"],
        ["방수량",    "130L/min",      "60L/min"],
        ["호스구경",  "40mm",          "25mm"],
        ["수평거리",  "25m",           "25m"],
      ],
    },
    tip: "방수압 0.17MPa(하한)과 0.7MPa(상한) 모두 출제. 호스릴은 방수량 60L/min으로 다름. '동시 개방 2개' 기준의 수원 계산 빈출.",
  },

  // ──────────────── [03] ────────────────
  {
    number: 3,
    title: "스프링클러 헤드 설치 기준",
    summary: "수평거리(반경) + 헤드 간격이 핵심 — 표준형과 조기반응형 구분 필수.",
    acroLabel: "반-간-높-감-수-표",
    acroChars: [
      { ch: "반", desc: "반경(수평거리) — 표준 2.3m / 조기반응 2.1m" },
      { ch: "간", desc: "간격(헤드 간) — 3.6m 이하 (정방형 배치)" },
      { ch: "높", desc: "높이 — 스프링클러 → 천장 0.3m 이하" },
      { ch: "감", desc: "감지기 — 폐쇄형 / 개방형 구분" },
      { ch: "수", desc: "수원 — Q = 80L/min × 기준개수" },
      { ch: "표", desc: "표시온도 — 57~79°C (일반), 79~121°C (고온)" },
    ],
    bullets: [
      { ch: "수평거리", desc: "폐쇄형 표준: 반경 2.3m, 랙크식: 2.5m", subs: ["조기반응형(ESFR): 반경 2.1m", "개방형: 1.7m (무대부·드렌처)"] },
      { ch: "헤드간격", desc: "3.6m 이하 (천장 높이 10m 이하 기준)" },
      { ch: "수원량", desc: "기준개수 × 80L/min × 20분 이상" },
      { ch: "감도", desc: "RTI ≤ 50(m·s)½ → 조기반응형" },
    ],
    table: {
      headers: ["헤드 종류", "수평거리(반경)", "기준개수"],
      rows: [
        ["폐쇄형 표준",  "2.3m",  "10"],
        ["조기반응(ESFR)", "2.1m", "10"],
        ["개방형(무대)", "1.7m",   "15"],
        ["랙크식",       "2.5m",   "10"],
      ],
    },
    tip: "2.3m(표준)과 2.1m(조기반응) 혼동 주의. 랙크식 창고는 2.5m로 더 넓지만 기준개수 증가 없음. RTI 수치 직접 계산 문제도 출제됨.",
  },

  // ──────────────── [04] ────────────────
  {
    number: 4,
    title: "간이스프링클러설비 설치 기준",
    summary: "간이형 헤드 반경 2.3m, 방수량 50L/min — 표준 스프링클러의 절반 수준 기억.",
    acroLabel: "간-반-방-수-펌-제",
    acroChars: [
      { ch: "간", desc: "간이형 헤드 — 표준 헤드와 동일 배치(반경 2.3m)" },
      { ch: "반", desc: "반응시간 — 표준반응 or 조기반응 혼용 가능" },
      { ch: "방", desc: "방수량 50L/min(간이), 전체 최소 2개" },
      { ch: "수", desc: "수원 1㎥(간이) — 근린·숙박·노유자" },
      { ch: "펌", desc: "펌프 사용 또는 가압수조 방식" },
      { ch: "제", desc: "제어밸브 — 세대 단위 또는 층 단위 설치" },
    ],
    bullets: [
      { ch: "설치대상", desc: "근린생활시설·숙박시설·노유자시설 등 (바닥면적 600㎡ 미만)" },
      { ch: "방수량", desc: "50L/min 이상 (표준 스프링클러 80L/min의 약 62.5%)" },
      { ch: "수원", desc: "1㎥ 이상 (2개 기준 = 50 × 2 × 10분 = 1㎥)" },
    ],
    table: {
      headers: ["구분", "스프링클러", "간이스프링클러"],
      rows: [
        ["방수압",  "0.1MPa",   "0.1MPa"],
        ["방수량",  "80L/min",  "50L/min"],
        ["수원(최소)", "1.6㎥", "1㎥"],
      ],
    },
    tip: "간이 스프링클러는 '50L/min'과 '1㎥' 수치로 빈출. 근린생활·숙박·노유자 등 설치대상 암기 필수. 600㎡ 미만이면 간이형 적용 가능 조건 확인.",
  },

  // ──────────────── [05] ────────────────
  {
    number: 5,
    title: "물분무소화설비 설치 기준",
    summary: "방수량 10L/min·㎡, 압력 0.35MPa — 특수가연물·전기실 적용 핵심.",
    acroLabel: "물-압-량-면-특-방",
    acroChars: [
      { ch: "물", desc: "물분무 — 미세입자로 냉각·질식·희석 동시 작용" },
      { ch: "압", desc: "압력 0.35MPa 이상" },
      { ch: "량", desc: "방수량 10L/min·㎡ 이상" },
      { ch: "면", desc: "면적 — 방호구역 바닥면적 기준" },
      { ch: "특", desc: "특수가연물 저장·취급 장소에 필수" },
      { ch: "방", desc: "방화 셔터·케이블 트레이 보호에도 적용" },
    ],
    bullets: [
      { ch: "방수압", desc: "0.35MPa 이상 (옥내 0.17MPa 대비 2배 수준)" },
      { ch: "방수량", desc: "10L/min·㎡ (단위면적 당)" },
      { ch: "적용 장소", desc: "주차장·특수가연물·전기실·케이블트레이" },
      { ch: "수원", desc: "방수량 × 방호면적 × 20분" },
    ],
    table: null,
    tip: "물분무 vs 미분무 혼동 주의. 미분무는 압력 1.2MPa 이상 (고압), 물분무는 0.35MPa. 전기화재 C급 적용 가능 이유: 이온화 방지.",
  },

  // ──────────────── [06] ────────────────
  {
    number: 6,
    title: "포소화설비 설치 기준",
    summary: "포 혼합장치 종류(프레셔 프로포셔너 등)와 포 수용액 농도(3%, 6%) 구분이 핵심.",
    acroLabel: "포-혼-농-방-팽-수",
    acroChars: [
      { ch: "포", desc: "포소화약제 — 단백포·합성계면활성제포·수성막포 구분" },
      { ch: "혼", desc: "혼합장치 — 프레셔 프로포셔너/라인 프로포셔너 등" },
      { ch: "농", desc: "농도 — 3% or 6% (약제 종류별 상이)" },
      { ch: "방", desc: "방출구 — 고정포 방출구 / 모니터노즐 방식" },
      { ch: "팽", desc: "팽창비 — 저팽창(20 미만) / 고팽창(200~1000)" },
      { ch: "수", desc: "수원 = 방출량 × 시간 + 배관 내 포수용액량" },
    ],
    bullets: [
      { ch: "저팽창포", desc: "팽창비 20 미만 (일반 주차장·위험물 저장소)" },
      { ch: "고팽창포", desc: "팽창비 80 이상 ~ 1000 이하 (지하주차장·창고)" },
      { ch: "혼합비율", desc: "포원액 3%(수성막포) or 6%(단백포·합성포)" },
    ],
    table: {
      headers: ["약제 종류", "농도", "팽창비", "주요 용도"],
      rows: [
        ["단백포",      "6%",  "저팽창", "유류 화재"],
        ["수성막포(AFFF)", "3%", "저팽창", "유류·항공기"],
        ["고팽창포",    "1~3%", "고팽창", "지하·창고"],
      ],
    },
    tip: "프레셔 프로포셔너(압입식)와 라인 프로포셔너(흡입식) 구조 차이 빈출. 팽창비 20 경계로 저/고 구분. 수성막포 3%, 단백포 6% 오답 유도 주의.",
  },

  // ──────────────── [07] ────────────────
  {
    number: 7,
    title: "이산화탄소 소화설비 설치 기준",
    summary: "표면화재 1.3kg/㎡, 심부화재 2.7kg/㎡ — 방호구역 부피 × 계수 = 소화약제량.",
    acroLabel: "CO-설-표-심-분-안",
    acroChars: [
      { ch: "C", desc: "CO₂ 소화약제 — 질식 소화(산소 농도 15% 이하)" },
      { ch: "O", desc: "Opening(개구부) — 면적의 5% 이하 유지" },
      { ch: "설", desc: "설계농도 34% 이상 (전역방출 기준)" },
      { ch: "표", desc: "표면화재 — 1.3kg/㎡ (체적 계수 0.75)" },
      { ch: "심", desc: "심부화재 — 2.7kg/㎡ (체적 계수 1.0)" },
      { ch: "분", desc: "분사헤드 방사시간 — 1분 이내(표면화재)" },
      { ch: "안", desc: "안전장치 — 방출 지연·인명피해 방지 설비 필수" },
    ],
    bullets: [
      { ch: "전역방출", desc: "방호구역 체적 × 소화약제량 계수 (㎏/㎥)" },
      { ch: "표면화재", desc: "계수 0.75(전기실 등) — 방사시간 1분" },
      { ch: "심부화재", desc: "계수 1.0 이상(서고·목재 등) — 방사시간 7분" },
      { ch: "개구부 보정", desc: "개구부 면적 × 5kg/㎡ 추가 (자동폐쇄 없을 시)" },
    ],
    table: {
      headers: ["화재 종류", "약제 계수", "방사시간"],
      rows: [
        ["표면화재(전기·통신)", "0.75 kg/㎥", "1분 이내"],
        ["심부화재(종이·목재)", "1.0 kg/㎥",  "7분 이내"],
      ],
    },
    tip: "0.75 vs 1.0 계수 구분 필수. 안전장치(방출지연타이머 20초 이상) 누락 오답 주의. 청정소화약제와 CO₂ 방호구역 기준 동일여부 확인 문제 출제.",
  },

  // ──────────────── [08] ────────────────
  {
    number: 8,
    title: "할로겐화합물 및 청정소화약제 설치 기준",
    summary: "NOBC 개념 없이 설계농도(A-factor)와 약제량 계산식만 암기하면 해결.",
    acroLabel: "청-설-약-온-안-방",
    acroChars: [
      { ch: "청", desc: "청정소화약제 — 오존파괴지수(ODP) 0, 지구온난화(GWP) 낮음" },
      { ch: "설", desc: "설계농도 — NOBC × 1.2 (최소안전계수 적용)" },
      { ch: "약", desc: "약제량 W = V × C / (S × (100-C))" },
      { ch: "온", desc: "온도 — 저장용기 55°C 이하 유지" },
      { ch: "안", desc: "안전장치 — 봉판(파열판) + 방출지연 스위치" },
      { ch: "방", desc: "방사시간 10초 이내 (A·B·C급 적용)" },
    ],
    bullets: [
      { ch: "설계농도", desc: "NOBC(최소소화농도) × 안전계수 1.2" },
      { ch: "방사시간", desc: "10초 이내 (CO₂의 1분·7분과 구별)" },
      { ch: "저장온도", desc: "55°C 이하, 0°C 이상 유지" },
      { ch: "약제 계산", desc: "W(kg) = 방호체적(㎥) × C/(S × (100-C))" },
    ],
    table: null,
    tip: "방사시간 10초(청정) vs 1분(CO₂ 표면) vs 7분(CO₂ 심부) 빈출 구분 문제. ODP·GWP 수치 직접 묻기도 함.",
  },

  // ──────────────── [09] ────────────────
  {
    number: 9,
    title: "분말소화설비 설치 기준",
    summary: "가압식 vs 축압식, 분말 종류(1~4종) 적용 화재급수 구분이 핵심.",
    acroLabel: "분-종-가-축-방-면",
    acroChars: [
      { ch: "분", desc: "분말 소화약제 — 부촉매 소화 작용" },
      { ch: "종", desc: "종류 — 1종(BC급), 2종(ABC급), 3종(ABC급), 4종(D급)" },
      { ch: "가", desc: "가압식 — 별도 가압 가스 용기 필요" },
      { ch: "축", desc: "축압식 — 용기 내 질소가스 상시 가압" },
      { ch: "방", desc: "방사시간 30초 이내 (전역방출)" },
      { ch: "면", desc: "면적 기준 — 국소방출 시 바닥면적 × 12kg/㎡" },
    ],
    bullets: [
      { ch: "1종 분말", desc: "탄산수소나트륨(NaHCO₃) — B·C급" },
      { ch: "2종 분말", desc: "탄산수소칼륨(KHCO₃) — B·C급, 효과↑" },
      { ch: "3종 분말", desc: "제1인산암모늄(NH₄H₂PO₄) — A·B·C급" },
      { ch: "4종 분말", desc: "탄산수소칼륨+요소 — B·C급, D급" },
    ],
    table: {
      headers: ["종별", "주성분", "적용 화재"],
      rows: [
        ["1종", "NaHCO₃",      "B·C급"],
        ["2종", "KHCO₃",       "B·C급"],
        ["3종", "NH₄H₂PO₄",   "A·B·C급"],
        ["4종", "KHCO₃+요소", "B·C·D급"],
      ],
    },
    tip: "3종 분말이 A·B·C급 전부 적용 가능 — '일반 가연물 화재' 포함 포인트. 방사시간 30초(분말) vs 10초(청정) vs 1·7분(CO₂) 반드시 구분.",
  },

  // ──────────────── [10] ────────────────
  {
    number: 10,
    title: "옥외소화전설비 설치 기준",
    summary: "수평거리 40m, 방수압 0.25MPa, 방수량 350L/min — 옥내 대비 2배 이상 기억.",
    acroLabel: "옥-수-압-량-함-방",
    acroChars: [
      { ch: "옥", desc: "옥외 — 건물 외부 1층 출입구 또는 옥외 설치" },
      { ch: "수", desc: "수평거리 40m 이내 (옥내 25m 대비)" },
      { ch: "압", desc: "압력 0.25MPa 이상 (옥내 0.17MPa 대비)" },
      { ch: "량", desc: "방수량 350L/min 이상 (옥내 130L/min 대비)" },
      { ch: "함", desc: "함(소화전함) — 옥외형, 호스 길이 합계 100m" },
      { ch: "방", desc: "방호구역 — 반경 40m 원 내 모두 포함" },
    ],
    bullets: [
      { ch: "방수압", desc: "0.25MPa 이상 ~ 0.7MPa 이하" },
      { ch: "방수량", desc: "350L/min 이상, 동시 개방 2개 기준" },
      { ch: "수원", desc: "7㎥ 이상 (350 × 2 × 10분 = 7㎥)" },
      { ch: "소화전 위치", desc: "건물 각 부분에서 수평거리 40m 이내" },
    ],
    table: {
      headers: ["항목", "옥내소화전", "옥외소화전"],
      rows: [
        ["방수압",    "0.17MPa",   "0.25MPa"],
        ["방수량",    "130L/min",  "350L/min"],
        ["수평거리",  "25m",       "40m"],
        ["수원(2개)", "2.6㎥",     "7㎥"],
      ],
    },
    tip: "옥외: 0.25MPa·350L/min·40m·7㎥를 세트로 암기. 옥내와 수치 혼동이 단골 오답.",
  },

  // [11]~[29] — 템플릿 (소스 DOCX 내용 파싱 후 채워짐)
  // extractProblems() 결과로 아래 번호가 채워집니다.
  ...[11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29].map((n) => ({
    number: n,
    title: `문제 ${n} — (소스 DOCX에서 추출 필요)`,
    summary: `만제[${String(n).padStart(2,"0")}] 핵심요약 (소스 DOCX에서 추출 후 입력)`,
    acroLabel: "A-B-C-D-E-F",
    acroChars: [
      { ch: "A", desc: "항목A" },
      { ch: "B", desc: "항목B" },
      { ch: "C", desc: "항목C" },
    ],
    bullets: [{ ch: "내용", desc: "소스 DOCX 파싱 후 채워짐" }],
    table: null,
    tip: `만제[${String(n).padStart(2,"0")}] — 소스 DOCX 내용을 기반으로 업데이트 필요`,
  })),
];

// ─────────────────────────────────────────
// (선택) 소스 DOCX 파싱 — mammoth
// ─────────────────────────────────────────
async function extractTextFromDocx(filePath) {
  if (!fs.existsSync(filePath)) {
    console.warn(`⚠️  소스 파일 없음: ${filePath}`);
    return null;
  }
  const { value } = await mammoth.extractRawText({ path: filePath });
  return value;
}

// ─────────────────────────────────────────
// 문서 생성
// ─────────────────────────────────────────
async function buildDocument(problems) {
  const allSections = [];
  for (const prob of problems) {
    allSections.push(...buildProblem(prob));
  }

  return new Document({
    styles: {
      default: {
        document: {
          run: { font: FONT, size: 20 },
        },
      },
      paragraphStyles: [
        {
          id: "Heading1",
          name: "Heading 1",
          basedOn: "Normal",
          run: { size: 26, bold: true, color: COLOR.HEADER_FG, font: FONT },
        },
      ],
    },
    sections: [
      {
        properties: {
          page: {
            size: { width: convertMillimetersToTwip(210), height: convertMillimetersToTwip(297) },
            margin: MARGIN,
          },
        },
        children: allSections,
      },
    ],
  });
}

// ─────────────────────────────────────────
// 메인
// ─────────────────────────────────────────
async function main() {
  const INPUT_DOCX  = "/mnt/user-data/uploads/만제77까지.docx";
  const OUTPUT_DOCX = "/mnt/user-data/outputs/소방관리사2차_만제01-29_두문자암기요약.docx";
  const OUTPUT_DIR  = path.dirname(OUTPUT_DOCX);

  // 출력 디렉토리 생성
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
    console.log(`📁 출력 디렉토리 생성: ${OUTPUT_DIR}`);
  }

  // 소스 DOCX 파싱 (존재 시)
  const sourceText = await extractTextFromDocx(INPUT_DOCX);
  if (sourceText) {
    console.log(`✅ 소스 DOCX 읽기 성공 (${sourceText.length}자)`);
    // TODO: sourceText를 파싱해 PROBLEMS 배열 자동 채우기
    // 현재는 하드코딩된 [01]~[10] + 템플릿 [11]~[29] 사용
  }

  console.log(`📝 문서 생성 중 (${PROBLEMS.length}개 문제)...`);
  const doc = await buildDocument(PROBLEMS);

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(OUTPUT_DOCX, buffer);
  console.log(`✅ 완료: ${OUTPUT_DOCX}`);
  console.log(`   파일 크기: ${(buffer.length / 1024).toFixed(1)} KB`);
}

main().catch((err) => {
  console.error("오류:", err);
  process.exit(1);
});
