> 原文快照：下沉自 docs/roadmap.md（2026-07-21 迁移），文中状态记号为历史残留

### P3-E: Kami PDF 排版模板 + 自动化脚本
- 目标：用 Kami（HTML/CSS）生成可打印 PDF，主副式双语，霞鹜文楷，天蓝色 #4DABF7
- 涉及文件：`templates/allin-kami/`、`scripts/allin/generate_pdf.py`
- 验收：1 期 PDF 导出，双语对照排版，可在 Kami 中标注
- 状态：✅ 已完成（模板 commit `427683a`，自动化脚本 2026-04-29）
  - `templates/allin-kami/styles.css`：霞鹜文楷 + #4DABF7 天蓝色全套样式
  - `templates/allin-kami/episode.html`：封面/概览/五维/金句/逐字稿完整模板
  - `scripts/allin/generate_pdf.py`：读 bilingual.json + analysis.json，Chrome headless 生成 PDF
  - 同时输出注释版（annotated）和原稿版（original）两份
