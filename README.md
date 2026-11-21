# PDF 六合一整理器（PdfForExamGenerator）

把 PDF 演示文稿中勾选的页面，按**每页 6 页**（3 列 × 2 行）重新排版到**横版 A4** PDF，适合打印复习。

## 环境与运行

- Python：conda 环境 `env_1`（Python 3.14）
- 依赖：PyMuPDF（已装入 `env_1`；如需重装：`pip install pymupdf`）

```bash
conda activate env_1
python main.py
```

## 使用方法

1. `Ctrl+O` 打开 PDF —— 界面**不渲染预览**，只显示页码列表。
2. 键盘勾选需要的页：

| 按键 | 功能 |
|---|---|
| ↑ / ↓ | 移动光标 |
| Enter / 空格 / 双击 | 勾选 / 取消勾选当前页 |
| PageUp / PageDown | 上下翻 10 页 |
| Home / End | 跳到第一页 / 最后一页 |
| Ctrl+A / Ctrl+D / Ctrl+I | 全选 / 清空 / 反选 |
| Ctrl+G | 跳到"范围勾选"输入框（如 `1-5,8,12-15`，回车应用） |
| Ctrl+O / Ctrl+E | 打开 PDF / 导出 |
| F1 / Esc | 帮助 / 退出 |

3. `Ctrl+E` 导出：默认保存为 `<原文件名>_6up.pdf`（可改位置和名称）。

## 导出规则

- 横版 A4（297 × 210 mm），3 列 × 2 行，阅读顺序从左到右、从上到下；
- 每页**等比缩放居中**放入格子（不变形、不裁切，四周留白）；
- 按**原页码升序**排列（与勾选先后无关）；
- 最后不足 6 页时，剩余格子留白。

## 文件说明

| 文件 | 作用 |
|---|---|
| `main.py` | tkinter 界面、键盘快捷键、勾选状态、会话记忆 |
| `pdf_ops.py` | PDF 读取与"6 合 1"导出逻辑（可独立调用/测试） |
| `requirements.txt` | 依赖清单（pymupdf） |
| `session.json` | 自动生成：记忆上次文件与勾选状态；删除即可重置 |
| `ui_preview.png` | 界面截图 |

## 调整排布参数

打开 `pdf_ops.py` 顶部常量：`COLS` / `ROWS`（每页格数）、`OUTER_MARGIN_MM` / `INNER_MARGIN_MM`（边距，毫米）。

## 常见问题

- **列表里 ☑/☐ 显示为方块**：把 `main.py` 顶部的 `CHECK_MARK` / `UNCHECK_MARK` 换成 `"[x]"` / `"[ ]"`。
- **打开报"已加密"**：请先用其他工具解除 PDF 密码保护。
- **想恢复全新状态**：删除项目目录下的 `session.json`。
