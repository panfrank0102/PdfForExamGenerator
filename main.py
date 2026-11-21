# -*- coding: utf-8 -*-
"""PDF 六合一整理器 —— 主程序（tkinter 界面：无预览、键盘友好）。

用法:
    conda activate env_1
    python main.py
"""
import json
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pdf_ops

APP_NAME = "PDF 六合一整理器（6-up 横版 A4）"
SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session.json")
CHECK_MARK, UNCHECK_MARK = "☑", "☐"

HINTS = ("↑↓ 移动   Enter/空格/双击 勾选   PgUp/PgDn ×10   Home/End\n"
         "Ctrl+A 全选   Ctrl+D 清空   Ctrl+I 反选   Ctrl+G 范围输入\n"
         "Ctrl+E 导出   F1 帮助   Esc 退出")


def parse_range(text, total):
    """解析 '1-5,8,12-15' → 0-based 页号集合；越界页自动忽略。非法片段抛 ValueError。"""
    out, ok = set(), False
    for tok in text.split(","):
        tok = tok.strip()
        if not tok:
            continue
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", tok)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            lo, hi = (a, b) if a <= b else (b, a)
            lo, hi = max(lo, 1), min(hi, total)
            out.update(range(lo - 1, hi))
            ok = True
        elif tok.isdigit():
            p = int(tok)
            if 1 <= p <= total:
                out.add(p - 1)
                ok = True
        else:
            raise ValueError(f"无法识别: “{tok}”")
    if not ok:
        raise ValueError(f"没有落在 1–{total} 范围内的页码")
    return out


class App:
    def __init__(self, root):
        self.root = root
        self.pdf_path = None
        self.page_count = 0
        self.selected = set()   # 0-based 已勾选页
        self.cur = 0            # 光标所在行（0-based）
        root.title(APP_NAME)
        root.geometry("600x790")
        root.minsize(560, 660)
        self._build_ui()
        self._bind_keys()
        self._load_session()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- 界面 ----------------
    def _build_ui(self):
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=8, pady=(8, 2))
        ttk.Button(top, text="打开 PDF…  (Ctrl+O)", command=self.open_dialog).pack(side="left")
        self.lbl_file = ttk.Label(top, text="未打开文件", foreground="#666666", wraplength=400)
        self.lbl_file.pack(side="left", fill="x", expand=True, padx=(10, 0))

        self.lbl_info = ttk.Label(self.root, text="未打开 PDF（Ctrl+O）", anchor="w")
        self.lbl_info.pack(fill="x", padx=8, pady=2)

        mid = ttk.Frame(self.root)
        mid.pack(fill="both", expand=True, padx=8, pady=2)
        self.listbox = tk.Listbox(mid, selectmode="single", activestyle="dotbox",
                                  exportselection=False,
                                  font=("Microsoft YaHei UI", 10))
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        rng = ttk.Frame(self.root)
        rng.pack(fill="x", padx=8, pady=(4, 0))
        ttk.Label(rng, text="范围勾选 (如 1-5,8,12-15):").pack(side="left")
        self.entry_range = ttk.Entry(rng, width=20)
        self.entry_range.pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(rng, text="应用", command=self.apply_range).pack(side="left")

        btns = ttk.Frame(self.root)
        btns.pack(fill="x", padx=8, pady=6)
        ttk.Button(btns, text="全选 (Ctrl+A)", command=self.select_all).pack(side="left")
        ttk.Button(btns, text="清空 (Ctrl+D)", command=self.clear_all).pack(side="left", padx=(6, 0))
        ttk.Button(btns, text="反选 (Ctrl+I)", command=self.invert_selection).pack(side="left", padx=(6, 0))
        ttk.Button(btns, text="导出 6合1 (Ctrl+E)", command=self.export).pack(side="right")

        ttk.Label(self.root, text=HINTS, anchor="w", justify="left",
                  wraplength=568, foreground="#555555").pack(fill="x", padx=8, pady=(0, 8))

    def _bind_keys(self):
        lb = self.listbox
        lb.bind("<Up>", lambda e: self._move(-1))
        lb.bind("<Down>", lambda e: self._move(1))
        lb.bind("<Prior>", lambda e: self._move(-10))
        lb.bind("<Next>", lambda e: self._move(10))
        lb.bind("<Home>", lambda e: self._move(-10 ** 9))
        lb.bind("<End>", lambda e: self._move(10 ** 9))
        lb.bind("<Return>", self._toggle)
        lb.bind("<space>", self._toggle)
        lb.bind("<Button-1>", self._on_click)
        lb.bind("<Double-Button-1>", self._toggle)
        self.entry_range.bind("<Return>", lambda e: self.apply_range())
        r = self.root
        r.bind("<Control-a>", lambda e: self._guard_entry(self.select_all))
        r.bind("<Control-d>", lambda e: self._guard_entry(self.clear_all))
        r.bind("<Control-i>", lambda e: self._guard_entry(self.invert_selection))
        r.bind("<Control-e>", lambda e: self._guard_entry(self.export))
        r.bind("<Control-o>", lambda e: self.open_dialog())
        r.bind("<Control-g>", lambda e: self.entry_range.focus_set())
        r.bind("<F1>", lambda e: self._help())
        r.bind("<Escape>", lambda e: self._on_close())

    def _guard_entry(self, func):
        """焦点在范围输入框时，让 Ctrl+A/D/I/E 保持文本框的默认行为。"""
        if self.root.focus_get() is self.entry_range:
            return None
        return func()

    # ---------------- 列表与勾选 ----------------
    def _item_text(self, i):
        mark = CHECK_MARK if i in self.selected else UNCHECK_MARK
        width = max(1, len(str(self.page_count)))
        return f"{mark} {i + 1:>{width}}"

    def _refresh_item(self, i):
        self.listbox.delete(i)
        self.listbox.insert(i, self._item_text(i))
        self.listbox.selection_set(i)
        self.listbox.see(i)

    def _refresh_all(self):
        lb = self.listbox
        lb.delete(0, "end")
        for i in range(self.page_count):
            lb.insert("end", self._item_text(i))
        if self.page_count:
            self.cur = min(max(self.cur, 0), self.page_count - 1)
            lb.selection_set(self.cur)
            lb.activate(self.cur)
            lb.see(self.cur)
        self._update_info()

    def _update_info(self):
        if self.pdf_path:
            self.lbl_info.config(
                text=f"共 {self.page_count} 页 · 已勾选 {len(self.selected)} 页")
        else:
            self.lbl_info.config(text="未打开 PDF（Ctrl+O）")

    def _move(self, delta):
        if not self.page_count:
            return "break"
        self.cur = max(0, min(self.page_count - 1, self.cur + delta))
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(self.cur)
        self.listbox.activate(self.cur)
        self.listbox.see(self.cur)
        return "break"

    def _on_click(self, event):
        idx = self.listbox.nearest(event.y)
        if idx >= 0:
            self.cur = idx
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(idx)
        return "break"

    def _toggle(self, event=None):
        if not self.page_count:
            return "break"
        i = self.cur
        if i in self.selected:
            self.selected.discard(i)
        else:
            self.selected.add(i)
        self._refresh_item(i)
        self._save_session()
        return "break"

    def select_all(self):
        if not self.page_count:
            return
        self.selected = set(range(self.page_count))
        self._refresh_all()
        self._save_session()

    def clear_all(self):
        if not self.page_count:
            return
        self.selected.clear()
        self._refresh_all()
        self._save_session()

    def invert_selection(self):
        if not self.page_count:
            return
        self.selected = set(range(self.page_count)) - self.selected
        self._refresh_all()
        self._save_session()

    def apply_range(self):
        if not self.page_count:
            return
        text = self.entry_range.get().strip()
        if not text:
            return
        try:
            pages = parse_range(text, self.page_count)
        except ValueError as exc:
            messagebox.showwarning("范围无效", str(exc))
            return
        self.selected |= pages
        self._refresh_all()
        self._save_session()

    # ---------------- 打开 / 导出 ----------------
    def open_dialog(self):
        initial = os.path.dirname(self.pdf_path) if self.pdf_path else os.path.expanduser("~")
        path = filedialog.askopenfilename(
            title="选择 PDF 演示文稿", initialdir=initial,
            filetypes=[("PDF 文件", "*.pdf"), ("所有文件", "*.*")])
        if path:
            self.open_pdf(path)

    def open_pdf(self, path, restore=None):
        try:
            page_count = pdf_ops.get_page_count(path)
        except Exception as exc:
            messagebox.showerror("打开失败", f"无法读取 PDF：\n{path}\n\n{exc}")
            return
        self.pdf_path = path
        self.page_count = page_count
        self.cur = 0
        self.selected = set(restore or []) & set(range(page_count))
        self.lbl_file.config(text=os.path.basename(path))
        self._refresh_all()
        self.listbox.focus_set()
        self._save_session()

    def export(self):
        if not self.pdf_path:
            messagebox.showwarning("提示", "请先打开 PDF（Ctrl+O）")
            return
        pages = sorted(self.selected)
        if not pages:
            messagebox.showwarning("提示", "请先勾选至少 1 页（Enter / 空格）")
            return
        stem = os.path.splitext(os.path.basename(self.pdf_path))[0]
        out_path = filedialog.asksaveasfilename(
            title="导出 6 合 1 PDF", initialdir=os.path.dirname(self.pdf_path),
            initialfile=f"{stem}_6up.pdf", defaultextension=".pdf",
            filetypes=[("PDF 文件", "*.pdf")])
        if not out_path:
            return
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        try:
            used = pdf_ops.export_6up(self.pdf_path, pages, out_path)
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))
        else:
            sheets = (len(pages) + 5) // 6
            messagebox.showinfo(
                "导出完成",
                f"已导出 {used} 页源页面 → {sheets} 张横版 A4\n\n{out_path}")
        finally:
            self.root.config(cursor="")

    # ---------------- 会话记忆 ----------------
    def _save_session(self):
        data = {"pdf": self.pdf_path, "selected": sorted(self.selected)}
        try:
            with open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError:
            pass

    def _load_session(self):
        try:
            with open(SESSION_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        path = data.get("pdf")
        if path and os.path.isfile(path):
            self.open_pdf(path, restore=data.get("selected") or [])
        else:
            self._update_info()

    # ---------------- 其他 ----------------
    def _help(self):
        messagebox.showinfo(
            APP_NAME,
            "快捷键：\n"
            "  ↑ / ↓                  移动光标\n"
            "  Enter / 空格 / 双击     勾选或取消勾选当前页\n"
            "  PageUp / PageDown       上下翻 10 页\n"
            "  Home / End              跳到第一页 / 最后一页\n"
            "  Ctrl+A 全选   Ctrl+D 清空   Ctrl+I 反选\n"
            "  Ctrl+G 跳到范围输入框（如 1-5,8,12-15，回车应用）\n"
            "  Ctrl+O 打开 PDF   Ctrl+E 导出   Esc 退出\n\n"
            "导出规则：横版 A4，3 列 × 2 行，每页等比缩放居中留白，\n"
            "按原页码升序排列，最后不足 6 页留白。")

    def _on_close(self):
        self._save_session()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        ttk.Style(root).theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
