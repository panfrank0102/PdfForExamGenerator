# -*- coding: utf-8 -*-
"""PDF 读取与"6 合 1"导出逻辑（与 UI 无关，可单独调用/测试）。

依赖: PyMuPDF（import pymupdf，要求 >= 1.24）
"""
import pymupdf as fitz

PT_PER_MM = 72.0 / 25.4

# 横版 A4: 297mm × 210mm
PAGE_W = 297.0 * PT_PER_MM
PAGE_H = 210.0 * PT_PER_MM

# 6 合 1 排布参数（想改成 4 合 1 / 8 合 1 / 调边距时改这里）
COLS = 3
ROWS = 2
OUTER_MARGIN_MM = 8.0   # 页面四周留白
INNER_MARGIN_MM = 4.0   # 格子之间的间距


def get_page_count(path: str) -> int:
    """返回 PDF 页数；加密或无页面的 PDF 抛 ValueError。"""
    doc = fitz.open(path)
    try:
        if doc.needs_pass:
            raise ValueError("该 PDF 已加密，请先解除密码保护")
        if doc.page_count <= 0:
            raise ValueError("该 PDF 没有页面")
        return doc.page_count
    finally:
        doc.close()


def grid_rects(page_w: float, page_h: float, cols: int, rows: int,
               outer_mm: float, inner_mm: float) -> list:
    """计算网格中每个格子的矩形（阅读顺序：从左到右、从上到下）。"""
    ox = outer_mm * PT_PER_MM
    ix = inner_mm * PT_PER_MM
    x0, y0 = ox, ox
    x1, y1 = page_w - ox, page_h - ox
    cell_w = (x1 - x0 - (cols - 1) * ix) / cols
    cell_h = (y1 - y0 - (rows - 1) * ix) / rows
    rects = []
    for r in range(rows):
        for c in range(cols):
            xa = x0 + c * (cell_w + ix)
            ya = y0 + r * (cell_h + ix)
            rects.append(fitz.Rect(xa, ya, xa + cell_w, ya + cell_h))
    return rects


def fit_rect(src_rect: fitz.Rect, cell: fitz.Rect) -> fitz.Rect:
    """等比缩放 src_rect 到 cell 内并居中，返回目标矩形（不变形、不裁切）。"""
    scale = min(cell.width / src_rect.width, cell.height / src_rect.height)
    w, h = src_rect.width * scale, src_rect.height * scale
    x0 = cell.x0 + (cell.width - w) / 2.0
    y0 = cell.y0 + (cell.height - h) / 2.0
    return fitz.Rect(x0, y0, x0 + w, y0 + h)


def export_6up(src_path: str, pages, out_path: str,
               cols: int = COLS, rows: int = ROWS,
               outer_mm: float = OUTER_MARGIN_MM,
               inner_mm: float = INNER_MARGIN_MM) -> int:
    """把 src_path 中指定的页（0-based）按 cols×rows 网格排到横版 A4，
    写出到 out_path。返回实际写入的页数。

    规则：页按原页码升序排列（与传入顺序无关）；最后不足一格的部分留白。
    """
    src = fitz.open(src_path)
    out = None
    try:
        total = src.page_count
        pages = sorted(p for p in set(pages) if 0 <= p < total)
        if not pages:
            raise ValueError("没有可导出的页面（所选页码全部越界）")
        per = cols * rows
        rects = grid_rects(PAGE_W, PAGE_H, cols, rows, outer_mm, inner_mm)
        out = fitz.open()
        for i in range(0, len(pages), per):
            chunk = pages[i:i + per]
            page = out.new_page(width=PAGE_W, height=PAGE_H)
            for pno, cell in zip(chunk, rects):
                dst = fit_rect(src[pno].rect, cell)
                page.show_pdf_page(dst, src, pno)
        out.save(out_path)
        return len(pages)
    finally:
        if out is not None:
            out.close()
        src.close()
