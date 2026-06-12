#!/usr/bin/env python3
"""
소방시설관리사 PDF 요약 프로그램 - GUI 실행기
이 파일을 더블클릭하면 바로 실행됩니다.
"""

import sys
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path


# ── 의존성 체크 ────────────────────────────────────────────────
def check_dependencies():
    missing = []
    try:
        import fitz
    except ImportError:
        missing.append("pymupdf")
    try:
        import anthropic
    except ImportError:
        missing.append("anthropic")
    return missing


# ── GUI 앱 ─────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("소방시설관리사 PDF 요약 프로그램")
        self.resizable(False, False)
        self._build_ui()
        self._running = False

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        # ── API 키 ──
        f0 = ttk.LabelFrame(self, text="Anthropic API 키", padding=8)
        f0.grid(row=0, column=0, sticky="ew", **pad)
        self.api_var = tk.StringVar(value=os.environ.get("ANTHROPIC_API_KEY", ""))
        ttk.Entry(f0, textvariable=self.api_var, width=60, show="*").pack(fill="x")

        # ── PDF 선택 ──
        f1 = ttk.LabelFrame(self, text="PDF 파일 선택", padding=8)
        f1.grid(row=1, column=0, sticky="ew", **pad)
        self.pdf_var = tk.StringVar()
        row = ttk.Frame(f1)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.pdf_var, width=50).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="찾아보기", command=self._browse).pack(side="left", padx=(6, 0))

        # ── 옵션 ──
        f2 = ttk.LabelFrame(self, text="옵션", padding=8)
        f2.grid(row=2, column=0, sticky="ew", **pad)

        r1 = ttk.Frame(f2); r1.pack(fill="x", pady=2)
        ttk.Label(r1, text="이미지 해상도(DPI):").pack(side="left")
        self.dpi_var = tk.IntVar(value=150)
        ttk.Spinbox(r1, from_=100, to=250, increment=10, textvariable=self.dpi_var, width=6).pack(side="left", padx=6)
        ttk.Label(r1, text="(낮을수록 빠름·저렴, 높을수록 정확)").pack(side="left")

        r2 = ttk.Frame(f2); r2.pack(fill="x", pady=2)
        ttk.Label(r2, text="청크당 페이지 수:").pack(side="left")
        self.chunk_var = tk.IntVar(value=5)
        ttk.Spinbox(r2, from_=2, to=10, increment=1, textvariable=self.chunk_var, width=6).pack(side="left", padx=6)

        r3 = ttk.Frame(f2); r3.pack(fill="x", pady=2)
        ttk.Label(r3, text="테스트 (일부 페이지만):").pack(side="left")
        self.test_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(r3, variable=self.test_var, command=self._toggle_test).pack(side="left")
        self.end_page_var = tk.IntVar(value=10)
        self.end_spin = ttk.Spinbox(r3, from_=1, to=9999, textvariable=self.end_page_var, width=6, state="disabled")
        self.end_spin.pack(side="left", padx=4)
        ttk.Label(r3, text="페이지까지만").pack(side="left")

        r4 = ttk.Frame(f2); r4.pack(fill="x", pady=2)
        self.final_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(r4, text="최종 통합 요약본 생성 (시간 추가 소요)", variable=self.final_var).pack(side="left")

        # ── 출력 폴더 ──
        r5 = ttk.Frame(f2); r5.pack(fill="x", pady=2)
        ttk.Label(r5, text="출력 폴더:").pack(side="left")
        self.outdir_var = tk.StringVar(value=str(Path.home() / "소방요약"))
        ttk.Entry(r5, textvariable=self.outdir_var, width=40).pack(side="left", padx=6, fill="x", expand=True)
        ttk.Button(r5, text="변경", command=self._browse_outdir).pack(side="left")

        # ── 실행 버튼 ──
        self.run_btn = ttk.Button(self, text="▶  요약 시작", command=self._start)
        self.run_btn.grid(row=3, column=0, pady=6)

        # ── 로그 창 ──
        f3 = ttk.LabelFrame(self, text="진행 로그", padding=8)
        f3.grid(row=4, column=0, sticky="nsew", **pad)
        self.log = scrolledtext.ScrolledText(f3, width=72, height=18, state="disabled",
                                             font=("Consolas", 9))
        self.log.pack(fill="both", expand=True)

    # ── 이벤트 ────────────────────────────────────────────────

    def _browse(self):
        path = filedialog.askopenfilename(filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")])
        if path:
            self.pdf_var.set(path)

    def _browse_outdir(self):
        d = filedialog.askdirectory()
        if d:
            self.outdir_var.set(d)

    def _toggle_test(self):
        self.end_spin.config(state="normal" if self.test_var.get() else "disabled")

    def _log(self, text):
        self.log.config(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.config(state="disabled")

    def _start(self):
        if self._running:
            return

        api_key = self.api_var.get().strip()
        pdf_path = self.pdf_var.get().strip()

        if not api_key:
            messagebox.showerror("오류", "Anthropic API 키를 입력해 주세요.")
            return
        if not pdf_path or not Path(pdf_path).exists():
            messagebox.showerror("오류", "유효한 PDF 파일을 선택해 주세요.")
            return

        os.environ["ANTHROPIC_API_KEY"] = api_key
        self._running = True
        self.run_btn.config(state="disabled", text="실행 중...")
        self.log.config(state="normal"); self.log.delete("1.0", "end"); self.log.config(state="disabled")

        kwargs = dict(
            pdf_path=pdf_path,
            dpi=self.dpi_var.get(),
            pages_per_chunk=self.chunk_var.get(),
            end_page=self.end_page_var.get() if self.test_var.get() else None,
            no_final=not self.final_var.get(),
            output_dir=self.outdir_var.get(),
        )
        threading.Thread(target=self._run_worker, kwargs=kwargs, daemon=True).start()

    def _run_worker(self, **kwargs):
        # stdout/stderr를 로그 창으로 리다이렉트
        import io
        class LogWriter(io.TextIOBase):
            def __init__(self, app):
                self._app = app
            def write(self, s):
                self._app.after(0, self._app._log, s)
                return len(s)
            def flush(self): pass

        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = LogWriter(self)
        try:
            self._run_summarize(**kwargs)
        except Exception as e:
            print(f"\n[오류] {e}")
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
            self.after(0, self._on_done)

    def _on_done(self):
        self._running = False
        self.run_btn.config(state="normal", text="▶  요약 시작")
        outdir = self.outdir_var.get()
        if messagebox.askyesno("완료", f"요약 완료!\n\n출력 폴더를 열까요?\n{outdir}"):
            import subprocess, platform
            if platform.system() == "Windows":
                os.startfile(outdir)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", outdir])
            else:
                subprocess.Popen(["xdg-open", outdir])

    def _run_summarize(self, pdf_path, dpi, pages_per_chunk, end_page, no_final, output_dir):
        """summarize.py의 핵심 로직을 직접 호출"""
        import base64
        import fitz
        import anthropic
        from summarize import (
            SYSTEM_PROMPT, MODEL,
            pdf_to_images_base64, chunk_pages,
            summarize_chunk, create_final_summary,
            save_chunks, save_final, load_existing_chunks,
        )

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        base_name = Path(pdf_path).stem
        chunks_file = output_dir / f"{base_name}_chunks.md"

        client = anthropic.Anthropic()

        all_pages = pdf_to_images_base64(pdf_path, dpi=dpi)
        pages = all_pages[:end_page] if end_page else all_pages
        print(f"처리 대상: {len(pages)}페이지")

        chunks = chunk_pages(pages, pages_per_chunk)
        total_chunks = len(chunks)
        print(f"총 {total_chunks}개 청크\n")

        chunk_summaries = load_existing_chunks(chunks_file)
        resume_from = len(chunk_summaries)

        for i, chunk in enumerate(chunks[resume_from:], start=resume_from + 1):
            summary = summarize_chunk(client, chunk, i, total_chunks)
            chunk_summaries.append(summary)
            save_chunks(output_dir, base_name, chunk_summaries)

        print(f"\n섹션별 요약 저장 완료: {chunks_file}")

        if not no_final:
            final_summary = create_final_summary(client, chunk_summaries)
            final_file = save_final(output_dir, base_name, final_summary)
            print(f"최종 요약 저장 완료: {final_file}")

        print("\n✓ 모든 작업 완료!")


# ── 진입점 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    missing = check_dependencies()
    if missing:
        root = tk.Tk(); root.withdraw()
        pkg = " ".join(missing)
        answer = messagebox.askyesno(
            "패키지 설치 필요",
            f"다음 패키지가 없습니다: {pkg}\n\n지금 자동 설치할까요?\n(인터넷 연결 필요)"
        )
        if answer:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
            messagebox.showinfo("설치 완료", "설치가 완료되었습니다. 프로그램을 다시 실행해 주세요.")
        sys.exit(0)

    app = App()
    app.mainloop()
