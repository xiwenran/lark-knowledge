#!/usr/bin/env python3
"""
generate_pdf.py — 生成 All In Podcast 知识库 PDF

从 bilingual.json + analysis.json 填充 HTML 模板，用 Chrome headless 导出 PDF。
默认同时生成「注释版」和「原稿版」两份 PDF。

用法：
  python3 generate_pdf.py bilingual.json --record-id recXXX
  python3 generate_pdf.py bilingual.json --record-id recXXX --annotated-only
  python3 generate_pdf.py bilingual.json --record-id recXXX --html-only  # 只生成HTML，浏览器手动打印

输出：
  /tmp/allin_E270_annotated.pdf   注释版（含内联注释）
  /tmp/allin_E270_original.pdf    原稿版（无注释）
"""

import json
import os
import re
import sys
import argparse
import subprocess
import shutil
import tempfile
from pathlib import Path

# ── 路径配置 ─────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent
TEMPLATE_DIR = REPO_ROOT / "templates" / "allin-kami"
TEMPLATE_HTML = TEMPLATE_DIR / "episode.html"
CONFIG_PATH = Path.home() / ".agents/skills/lark-knowledge-config/config.json"

# macOS Chrome 路径（优先级顺序）
CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "chromium",
    "google-chrome",
]


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))


def get_record(config: dict, record_id: str) -> dict:
    """从飞书收件表读取记录，数组类型字段自动取第一个值"""
    result = subprocess.run([
        "lark-cli", "base", "+record-get",
        "--base-token", config["all_in_podcast"]["base_token"],
        "--table-id", config["all_in_podcast"]["table_id"],
        "--record-id", record_id
    ], capture_output=True, text=True)
    raw = json.loads(result.stdout)["data"]["record"]
    normalized = {}
    for k, v in raw.items():
        normalized[k] = v[0] if isinstance(v, list) and len(v) == 1 else v
    return normalized


def extract_dim(text: str, marker: str) -> str:
    """从五维分析文本提取单个维度内容"""
    pattern = rf'{marker}[^\n]*\n(.*?)(?=①|②|③|④|⑤|$)'
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ''


def parse_quotes(quotes_text: str) -> list:
    """
    解析精华金句 Markdown，返回 [{en, zh, speaker}] 列表
    支持格式：
      > **"英文原句"**
      > 中文译文 — 说话人
    """
    quotes = []
    # 按空行或 > 段落分割
    blocks = re.split(r'\n\s*\n', quotes_text.strip())
    for block in blocks:
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        # 第一行：> **"英文"**
        en_match = re.search(r'[""](.+?)[""]', lines[0])
        en = en_match.group(1).strip() if en_match else lines[0].lstrip('> *').strip()
        # 第二行：> 中文 — 说话人
        second = lines[1].lstrip('> ').strip()
        if ' — ' in second:
            zh, speaker = second.rsplit(' — ', 1)
        elif ' - ' in second:
            zh, speaker = second.rsplit(' - ', 1)
        else:
            zh, speaker = second, ''
        quotes.append({'en': en, 'zh': zh.strip(), 'speaker': speaker.strip()})
    return quotes


def parse_bilingual_segment(text: str) -> list:
    """
    解析 Doubao 输出的双语段落，返回 [{speaker, en, zh}] 列表
    格式：> **Speaker**: EN text\n**Speaker**：CN text
    """
    turns = []
    # 匹配每个说话人单元（> **Speaker**: EN + **Speaker**：CN）
    pattern = r'>\s*\*\*([^*]+)\*\*\s*:\s*(.+?)\n\*\*([^*]+)\*\*[：:]\s*(.+?)(?=\n\s*\n>|\n\s*\n\*\*|\Z)'
    for m in re.finditer(pattern, text, re.DOTALL):
        turns.append({
            'speaker': m.group(3).strip(),
            'en': m.group(2).strip().replace('\n', ' '),
            'zh': m.group(4).strip().replace('\n', ' ')
        })

    # 如果精确匹配失败，退回到按段落分割
    if not turns:
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('>'):
                en_line = line.lstrip('> *').strip()
                en_line = re.sub(r'^\*\*[^*]+\*\*\s*:', '', en_line).strip()
                if i + 1 < len(lines):
                    cn_line = lines[i+1].strip()
                    speaker_m = re.match(r'\*\*([^*]+)\*\*[：:](.+)', cn_line)
                    if speaker_m:
                        turns.append({
                            'speaker': speaker_m.group(1).strip(),
                            'en': en_line,
                            'zh': speaker_m.group(2).strip()
                        })
                        i += 2
                        continue
            i += 1
    return turns


def escape_html(text: str) -> str:
    """转义 HTML 特殊字符"""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def build_transcript_html(segments: list, annotations: dict, include_annotations: bool) -> str:
    """生成逐字稿 HTML"""
    parts = []
    for seg in segments:
        time_label = seg.get('time_label', '')
        translated = seg.get('translated', '')

        parts.append(f'<div class="chapter-heading no-break">[{escape_html(time_label)}]</div>')

        turns = parse_bilingual_segment(translated)
        if turns:
            for turn in turns:
                speaker = escape_html(turn['speaker'])
                zh = escape_html(turn['zh'])
                parts.append(
                    f'<p class="zh-para"><span class="speaker">{speaker}：</span>{zh}</p>'
                )

            # 注释
            if include_annotations:
                seg_annotations = annotations.get(time_label, [])
                for ann in seg_annotations:
                    parts.append(
                        f'<div class="annotation no-break">{escape_html(ann)}</div>'
                    )

            # 英文原文（合并为一块，折叠显示）
            en_texts = [t['en'] for t in turns if t.get('en')]
            if en_texts:
                en_combined = ' '.join(en_texts)
                parts.append(f'<span class="en-text">{escape_html(en_combined)}</span>')
        else:
            # 解析失败时直接显示原文
            parts.append(f'<p class="zh-para">{escape_html(translated[:300])}…</p>')

        parts.append('<hr class="section-rule">')

    return '\n'.join(parts)


def build_quotes_html(quotes: list) -> str:
    """生成精华金句 HTML"""
    if not quotes:
        return '<p>（待补充）</p>'
    parts = []
    for q in quotes:
        en = escape_html(q.get('en', ''))
        zh = escape_html(q.get('zh', ''))
        speaker = escape_html(q.get('speaker', ''))
        parts.append(f'''
<div class="quote-block no-break">
  <div class="quote-en">"{en}"</div>
  <div class="quote-zh">{zh}</div>
  <div class="quote-speaker">— {speaker}</div>
</div>''')
    return '\n'.join(parts)


def build_html(segments: list, record: dict, analysis: dict, include_annotations: bool) -> str:
    """填充 HTML 模板，返回完整 HTML 字符串"""
    template = TEMPLATE_HTML.read_text(encoding='utf-8')

    # 元数据
    episode = record.get('期号', 'E???')
    date = str(record.get('发布日期', ''))[:10]
    duration = record.get('时长（分钟）', '?')
    views = record.get('YouTube播放量', 0)
    views_wan = f"{int(views) // 10000}万" if views else '?万'
    topic = record.get('主题分类', '科技&AI')
    cn_title = record.get('中文标题', '未知标题')

    # 五维分析
    five_dim_raw = (
        analysis.get('five_dim', '')
        or record.get('AI摘要', '')
        or record.get('五维分析', '')
        or ''
    )
    dim1 = extract_dim(five_dim_raw, '①') or '（待补充）'
    dim2 = extract_dim(five_dim_raw, '②') or '（待补充）'
    dim3 = extract_dim(five_dim_raw, '③') or '（待补充）'
    dim4 = extract_dim(five_dim_raw, '④') or '（待补充）'
    dim5 = extract_dim(five_dim_raw, '⑤') or '（待补充）'

    # 精华金句
    quotes_text = analysis.get('quotes', '')
    quotes = parse_quotes(quotes_text)

    # 逐字稿
    annotations = analysis.get('annotations', {})
    transcript_html = build_transcript_html(segments, annotations, include_annotations)
    quotes_html = build_quotes_html(quotes)

    # 概览摘要（从五维提取首句）
    def first_sentence(text):
        if text and text != '（待补充）':
            return text.split('。')[0][:60] + '…'
        return '见五维分析'

    # 简单字符串替换（模板用 {{VAR}} 占位符）
    replacements = {
        '{{EPISODE_NUM}}': episode,
        '{{PUBLISH_DATE}}': date,
        '{{TITLE_ZH}}': cn_title,
        '{{DURATION}}': str(duration),
        '{{VIEWS}}': views_wan,
        '{{TOPIC_TAG}}': topic,
        '{{OVERVIEW_TOPIC}}': first_sentence(dim1),
        '{{OVERVIEW_KEY}}': first_sentence(dim2),
        '{{OVERVIEW_CN}}': first_sentence(dim5),
        '{{ANALYSIS_1}}': escape_html(dim1),
        '{{ANALYSIS_2}}': escape_html(dim2),
        '{{ANALYSIS_3}}': escape_html(dim3),
        '{{ANALYSIS_4}}': escape_html(dim4),
        '{{ANALYSIS_5}}': escape_html(dim5),
    }

    html = template
    for k, v in replacements.items():
        html = html.replace(k, v)

    # 替换精华金句区域（固定3个占位符 → 动态内容）
    quote_section_pattern = r'<!-- 复制以下块 3-5 次 -->.*?<hr class="section-rule page-break">'
    new_quote_section = quotes_html + '\n\n  <hr class="section-rule page-break">'
    html = re.sub(quote_section_pattern, new_quote_section, html, flags=re.DOTALL)

    # 替换逐字稿示例段落
    transcript_placeholder_pattern = r'<!-- 示例段落（生产时替换） -->.*?<hr class="section-rule">'
    html = re.sub(transcript_placeholder_pattern,
                  transcript_html,
                  html, flags=re.DOTALL)

    # 修正 CSS 路径为绝对路径（Chrome headless 需要）
    css_abs = str(TEMPLATE_DIR / "styles.css")
    html = html.replace('href="styles.css"', f'href="file://{css_abs}"')

    return html


def find_chrome() -> str | None:
    """找到系统中可用的 Chrome/Chromium"""
    for path in CHROME_PATHS:
        if Path(path).exists():
            return path
        found = shutil.which(path)
        if found:
            return found
    return None


def html_to_pdf(html_path: str, pdf_path: str) -> bool:
    """用 Chrome headless 将 HTML 转成 PDF，返回是否成功"""
    chrome = find_chrome()
    if not chrome:
        print("⚠️  未找到 Chrome/Chromium，无法自动生成 PDF")
        print("   请在浏览器中打开 HTML 文件，手动「文件→打印→另存为 PDF」")
        return False

    cmd = [
        chrome,
        "--headless=new",
        "--print-to-pdf=" + pdf_path,
        "--print-to-pdf-no-header",
        "--no-sandbox",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        "file://" + html_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"   ⚠️ Chrome 返回错误: {result.stderr[:200]}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description='生成 All In Podcast PDF')
    parser.add_argument('input', help='bilingual.json 路径')
    parser.add_argument('--record-id', required=True, help='飞书收件表 record_id')
    parser.add_argument('--analysis', default=None, help='AI分析结果 JSON 路径（可选）')
    parser.add_argument('--annotated-only', action='store_true', help='只生成注释版')
    parser.add_argument('--original-only', action='store_true', help='只生成原稿版')
    parser.add_argument('--html-only', action='store_true', help='只生成 HTML，不转 PDF（手动打印用）')
    parser.add_argument('--output-dir', default='/tmp', help='输出目录，默认 /tmp')
    args = parser.parse_args()

    config = load_config()

    print(f"[加载] 读取 {args.input}")
    segments = json.loads(Path(args.input).read_text(encoding='utf-8'))
    print(f"       共 {len(segments)} 段")

    print(f"[飞书] 读取收件表记录 {args.record_id}...")
    record = get_record(config, args.record_id)
    episode = record.get('期号', 'E???')
    cn_title = record.get('中文标题', '未知标题')
    print(f"       {episode} · {cn_title}")

    analysis = {}
    analysis_path = args.analysis or f"/tmp/allin_{args.record_id}_analysis.json"
    if Path(analysis_path).exists():
        analysis = json.loads(Path(analysis_path).read_text(encoding='utf-8'))
        print(f"[分析] 加载 AI 分析: {analysis_path}")
    else:
        print(f"[分析] 未找到 {analysis_path}，五维/金句/注释将留空")

    output_dir = Path(args.output_dir)
    episode_slug = episode.replace(' ', '_')

    # 决定要生成哪些版本
    versions = []
    if args.annotated_only:
        versions = [('annotated', True)]
    elif args.original_only:
        versions = [('original', False)]
    else:
        versions = [('annotated', True), ('original', False)]

    for version_name, include_annotations in versions:
        print(f"\n[生成] {version_name} 版本...")

        html = build_html(segments, record, analysis, include_annotations)

        # 写 HTML
        html_path = output_dir / f"allin_{episode_slug}_{version_name}.html"
        html_path.write_text(html, encoding='utf-8')
        print(f"       HTML: {html_path}")

        if args.html_only:
            print(f"   ✅ HTML 已生成，请在浏览器打开后「打印→另存为 PDF」")
            continue

        # 转 PDF
        pdf_path = output_dir / f"allin_{episode_slug}_{version_name}.pdf"
        print(f"[PDF]  正在生成 {pdf_path.name}...")
        success = html_to_pdf(str(html_path.resolve()), str(pdf_path))
        if success:
            size_kb = pdf_path.stat().st_size // 1024
            print(f"       ✅ PDF 已生成: {pdf_path} ({size_kb} KB)")
        else:
            print(f"       ⚠️  PDF 生成失败，HTML 文件保留在: {html_path}")

    print(f"\n✅ 完成！输出目录: {output_dir}")


if __name__ == '__main__':
    main()
