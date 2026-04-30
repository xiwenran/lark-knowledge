#!/usr/bin/env python3
"""
generate_pdf.py — 生成 All In Podcast 知识库 PDF

从 bilingual.json + analysis.json 填充 HTML 模板，用 WeasyPrint 导出 PDF。
默认同时生成「注释版」和「原稿版」两份 PDF。

用法：
  python3 generate_pdf.py bilingual.json --record-id recXXX
  python3 generate_pdf.py bilingual.json --record-id recXXX --annotated-only
  python3 generate_pdf.py bilingual.json --record-id recXXX --html-only  # 只生成HTML，浏览器手动打印

依赖：pip3 install weasyprint  /  macOS: brew install pango

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
from pathlib import Path

# macOS Homebrew 库路径（WeasyPrint 依赖 libgobject/libpango）
# DYLD_LIBRARY_PATH 需在进程启动前设置，由 html_to_pdf() 通过 subprocess 传入
_HOMEBREW_LIB = "/opt/homebrew/lib"

# ── 路径配置 ─────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent
TEMPLATE_DIR = REPO_ROOT / "templates" / "allin-kami"
TEMPLATE_HTML = TEMPLATE_DIR / "episode.html"

# 引入共享工具
sys.path.insert(0, str(SCRIPT_DIR))
from utils import load_config, safe_lark_run, get_record, parse_views_wan


def extract_dim(text: str, marker: str) -> str:
    """从五维分析文本提取单个维度内容（兼容同行格式和下一行格式）"""
    # 格式1：内容在下一行（多行段落）
    m = re.search(rf'{marker}[^\n]*\n(.*?)(?=①|②|③|④|⑤|\Z)', text, re.DOTALL)
    if m and m.group(1).strip():
        return m.group(1).strip()
    # 格式2：内容在 ：/: 后的同一行
    m = re.search(rf'{marker}[^：:\n]*[：:]\s*(.+?)(?=\s*[①②③④⑤]|\Z)', text, re.DOTALL)
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
    健壮版：逐行扫描，支持多行英文、空行间隔、多种冒号格式
    支持格式：
      > Speaker: EN text       （无加粗，Doubao-seed 实际输出）
      > **Speaker**: EN text   （有加粗，兼容旧格式）
    中文行：**Speaker**：CN text
    """
    turns = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # 找 EN 行：以 > 开头，说话人有无加粗均可
        en_m = re.match(r'>\s*\*{0,2}([^*:\n>]+?)\*{0,2}\s*[：:]\s*(.*)', line)
        if en_m:
            speaker_en = en_m.group(1).strip()
            en_text = en_m.group(2).strip()
            j = i + 1
            # 收集多行英文（直到空行或 ** 行或 > 行）
            while j < len(lines):
                nxt = lines[j].strip()
                if not nxt or nxt.startswith('>') or nxt.startswith('**'):
                    break
                en_text += ' ' + nxt
                j += 1
            # 跳过空行
            while j < len(lines) and not lines[j].strip():
                j += 1
            # 找 ZH 行：**Speaker**：text
            zh_text = ''
            speaker = speaker_en
            if j < len(lines):
                zh_m = re.match(r'\*\*([^*]+)\*\*[：:]\s*(.*)', lines[j].strip())
                if zh_m:
                    speaker = zh_m.group(1).strip()
                    zh_text = zh_m.group(2).strip()
                    k = j + 1
                    # 收集多行中文
                    while k < len(lines):
                        nxt = lines[k].strip()
                        if not nxt or nxt.startswith('>') or nxt.startswith('**'):
                            break
                        zh_text += ' ' + nxt
                        k += 1
                    j = k
            # 去掉说话人名中残留的 : 或 ：
            speaker = re.sub(r'[：:]\s*$', '', speaker).strip()
            turns.append({
                'speaker': speaker,
                'en': en_text.strip(),
                'zh': zh_text.strip()
            })
            i = j
        else:
            i += 1
    return turns


def escape_html(text: str) -> str:
    """转义 HTML 特殊字符（不转义飞书 <text> 标签）"""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


# 飞书颜色名 → CSS 颜色值
_FEISHU_COLOR_MAP = {
    'red':    '#e03131',
    'blue':   '#1971c2',
    'green':  '#2f9e44',
    'orange': '#e8590c',
    'purple': '#7950f2',
    'grey':   '#868e96',
    'gray':   '#868e96',
}


def feishu_to_html(text: str) -> str:
    """将飞书富文本标签转为 HTML <span>，其余内容 HTML 转义。
    支持：<text color="red/blue/green/orange/purple/grey">…</text>
    支持：**加粗**
    """
    import re as _re

    # 先按 <text color="...">…</text> 分割，交替处理
    parts = _re.split(r'(<text color="[^"]+">.*?</text>)', text, flags=_re.DOTALL)
    result = []
    for part in parts:
        m = _re.match(r'<text color="([^"]+)">(.*?)</text>', part, _re.DOTALL)
        if m:
            color_name = m.group(1)
            content = m.group(2)
            hex_color = _FEISHU_COLOR_MAP.get(color_name, '#333333')
            result.append(f'<span style="color:{hex_color};font-weight:600">{escape_html(content)}</span>')
        else:
            # 普通文本：先转义，再处理 **加粗**
            escaped = escape_html(part)
            escaped = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', escaped)
            result.append(escaped)
    return ''.join(result)


def extract_callouts(text: str):
    """从文本中提取 <callout> 块，返回 (clean_text, [callout_html_list])"""
    callouts = []

    def _collect(m):
        callouts.append(m.group(1).strip())
        return ''

    clean = re.sub(r'<callout[^>]*>(.*?)</callout>', _collect, text, flags=re.DOTALL)
    return clean.strip(), callouts


def build_transcript_html(segments: list, annotations: dict,
                          include_annotations: bool,
                          include_english: bool = True) -> str:
    """生成逐字稿 HTML

    include_english=True（默认）：双语版，英文在上（en-para 主体），中文翻译在下（zh-translation 左边框）
    include_english=False：纯中文版，仅显示中文（zh-para）
    """
    parts = []
    for seg in segments:
        time_label = seg.get('time_label', '')
        translated = seg.get('translated', '')

        parts.append(f'<div class="chapter-heading no-break">[{escape_html(time_label)}]</div>')

        turns = parse_bilingual_segment(translated)
        if turns:
            for turn in turns:
                speaker = escape_html(turn['speaker'])
                # 提取 zh 中的 callout 块
                zh_raw, turn_callouts = extract_callouts(turn.get('zh', ''))
                zh = escape_html(zh_raw)
                en = escape_html(turn.get('en', '').strip())

                # 说话人颜色 class
                spk_lower = turn['speaker'].lower()
                if 'jason' in spk_lower:
                    spk_cls = 'speaker-jason'
                elif 'chamath' in spk_lower:
                    spk_cls = 'speaker-chamath'
                elif 'sacks' in spk_lower:
                    spk_cls = 'speaker-sacks'
                elif 'friedberg' in spk_lower:
                    spk_cls = 'speaker-friedberg'
                else:
                    spk_cls = 'speaker-other'

                if include_english and en:
                    # 双语版：说话人独立成行，英文次行，中文第三行
                    parts.append(
                        f'<p class="speaker-label {spk_cls}">{speaker}</p>'
                    )
                    parts.append(
                        f'<p class="en-para">{en}</p>'
                    )
                    parts.append(
                        f'<span class="zh-translation">{zh}</span>'
                    )
                else:
                    # 纯中文版：说话人独立成行
                    parts.append(
                        f'<p class="speaker-label {spk_cls}">{speaker}</p>'
                    )
                    parts.append(
                        f'<p class="zh-para">{zh}</p>'
                    )

                # 嵌入 callout 注释（附着在该条发言下方）
                if include_annotations and turn_callouts:
                    for callout in turn_callouts:
                        parts.append(
                            f'<div class="annotation no-break">{escape_html(callout)}</div>'
                        )

            # analysis.json 中的段级注释（仍保留）
            if include_annotations:
                seg_annotations = annotations.get(time_label, [])
                for ann in seg_annotations:
                    parts.append(
                        f'<div class="annotation no-break">{escape_html(ann)}</div>'
                    )
        else:
            # 解析失败时直接显示原文（去掉飞书标签）
            clean_text, _ = extract_callouts(translated)
            clean_text = re.sub(r'<text color="[^"]+">|</text>', '', clean_text)
            parts.append(f'<p class="zh-para">{escape_html(clean_text[:400])}…</p>')

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
    views_wan = parse_views_wan(views)
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
    transcript_html = build_transcript_html(segments, annotations, include_annotations,
                                             include_english=True)
    quotes_html = build_quotes_html(quotes)

    # 概览摘要（从五维提取首句，同时处理飞书标签）
    def first_sentence(text):
        if text and text != '（待补充）':
            # 先去掉 <text color> 标签，取纯文字后再截断
            import re as _re
            plain = _re.sub(r'<text color="[^"]+">|</text>', '', text)
            return escape_html(plain.split('。')[0][:60] + '…')
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
        '{{ANALYSIS_1}}': feishu_to_html(dim1),
        '{{ANALYSIS_2}}': feishu_to_html(dim2),
        '{{ANALYSIS_3}}': feishu_to_html(dim3),
        '{{ANALYSIS_4}}': feishu_to_html(dim4),
        '{{ANALYSIS_5}}': feishu_to_html(dim5),
    }

    html = template
    for k, v in replacements.items():
        html = html.replace(k, v)

    # 替换精华金句区域（固定3个占位符 → 动态内容）
    quote_section_pattern = r'<!-- 复制以下块 3-5 次 -->.*?<hr class="section-rule page-break">'
    new_quote_section = quotes_html + '\n\n  <hr class="section-rule page-break">'
    new_html = re.sub(quote_section_pattern, new_quote_section, html, flags=re.DOTALL)
    if new_html == html:
        print("  ⚠️  警告：精华金句模板区块未找到，请检查 episode.html 模板是否被修改")
    html = new_html

    # 替换逐字稿示例段落
    transcript_placeholder_pattern = r'<!-- 示例段落（生产时替换） -->.*?<hr class="section-rule">'
    new_html = re.sub(transcript_placeholder_pattern, transcript_html, html, flags=re.DOTALL)
    if new_html == html:
        print("  ⚠️  警告：逐字稿模板区块未找到，请检查 episode.html 模板是否被修改")
    html = new_html

    # 修正 CSS 路径为绝对路径（WeasyPrint 需要 file:// 路径）
    css_abs = str(TEMPLATE_DIR / "styles.css")
    html = html.replace('href="styles.css"', f'href="file://{css_abs}"')

    return html


def upload_pdf_to_drive(config: dict, pdf_path: Path) -> str:
    """上传 PDF 到飞书云盘，返回文件分享链接（失败返回空字符串）"""
    folder_token = config.get("all_in_podcast", {}).get("pdf_folder_token", "")
    cmd = ["lark-cli", "drive", "+upload", "--file", str(pdf_path)]
    if folder_token:
        cmd += ["--folder-token", folder_token]
    data = safe_lark_run(cmd, action=f"上传 {pdf_path.name}")
    if data:
        file_token = data.get("data", {}).get("file_token", "")
        if file_token:
            return f"https://www.feishu.cn/file/{file_token}"
        print(f"  ⚠️  上传响应中无 file_token: {data}")
    return ""


def update_wiki_downloads(wiki_url: str, annotated_url: str, original_url: str):
    """更新飞书 wiki 页面的「📥 下载资源」区块，替换 PDF 链接占位符"""
    lines = []
    if annotated_url:
        lines.append(f"**注释版 PDF**（含 AI 注释和深度解析）：[点击下载]({annotated_url})")
    if original_url:
        lines.append(f"**原稿版 PDF**（纯净双语逐字稿）：[点击下载]({original_url})")
    if not lines:
        return

    download_md = "\n\n".join(lines)

    # 用唯一占位符做精确替换
    r1 = safe_lark_run([
        "lark-cli", "docs", "+update",
        "--doc", wiki_url,
        "--mode", "replace_range",
        "--selection-with-ellipsis", "（PDF链接待上传）...（PDF链接待上传）",
        "--markdown", download_md
    ], action="更新页面下载链接（replace_range）")

    if r1:
        print(f"       ✅ 下载链接已更新到飞书页面")
        return

    # 备用：在「📥 下载资源」标题后插入
    r2 = safe_lark_run([
        "lark-cli", "docs", "+update",
        "--doc", wiki_url,
        "--mode", "insert_after",
        "--selection-with-ellipsis", "📥 下载资源...📥 下载资源",
        "--markdown", download_md
    ], action="更新页面下载链接（insert_after）")

    if r2:
        print(f"       ✅ 下载链接已插入飞书页面（备用方式）")
    else:
        print(f"       ⚠️  飞书页面自动更新失败，请手动粘贴以下链接到「📥 下载资源」区块：")
        for line in lines:
            print(f"          {line}")


def html_to_pdf(html_path: str, pdf_path: str) -> bool:
    """用 WeasyPrint 将 HTML 转成 PDF，返回是否成功。
    通过 subprocess 传入 DYLD_LIBRARY_PATH 确保 macOS Homebrew 动态库可被 cffi 找到。
    """
    env = os.environ.copy()
    if sys.platform == "darwin":
        existing = env.get("DYLD_LIBRARY_PATH", "")
        if _HOMEBREW_LIB not in existing:
            env["DYLD_LIBRARY_PATH"] = f"{_HOMEBREW_LIB}:{existing}".rstrip(":")

    code = (
        "import sys; from weasyprint import HTML; "
        f"HTML(filename={html_path!r}).write_pdf({pdf_path!r}); "
        "print('ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=120, env=env
    )
    if result.returncode != 0 or "ok" not in result.stdout:
        stderr = result.stderr.strip()
        if "ModuleNotFoundError" in stderr or "ImportError" in stderr:
            print("⚠️  WeasyPrint 未安装，请运行：pip3 install weasyprint")
            print("   macOS 还需要：brew install pango")
        else:
            print(f"⚠️  WeasyPrint 渲染失败：{stderr[:300]}")
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
    parser.add_argument('--skip-upload', action='store_true', help='跳过上传飞书云盘（仅本地生成）')
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

    generated_pdfs = {}  # version_name -> pdf_path

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
            generated_pdfs[version_name] = pdf_path
        else:
            print(f"       ⚠️  PDF 生成失败，HTML 文件保留在: {html_path}")

    # ── 上传到飞书云盘 + 更新页面下载链接 ──────────────────
    if not args.html_only and not args.skip_upload and generated_pdfs:
        upload_links = {}
        for version_name, pdf_path in generated_pdfs.items():
            print(f"\n[上传] 上传 {version_name} 版 PDF 到飞书云盘...")
            url = upload_pdf_to_drive(config, pdf_path)
            if url:
                upload_links[version_name] = url
                print(f"       {url}")

        if upload_links:
            wiki_url = record.get("飞书页面URL", "")
            if wiki_url:
                print(f"\n[飞书] 更新页面下载链接...")
                update_wiki_downloads(
                    wiki_url,
                    upload_links.get("annotated", ""),
                    upload_links.get("original", "")
                )
                # 回填收件表 PDF 状态
                r = safe_lark_run([
                    "lark-cli", "base", "+record-upsert",
                    "--base-token", config["all_in_podcast"]["base_token"],
                    "--table-id", config["all_in_podcast"]["table_id"],
                    "--record-id", args.record_id,
                    "--json", json.dumps({"PDF状态": "已完成"})
                ], action="回填收件表 PDF状态")
                if r:
                    print(f"       ✅ 收件表 PDF状态 已更新")
                else:
                    print(f"       ⚠️  PDF状态 回填失败，请手动在收件表标记")
            else:
                print(f"\n⚠️  收件表中暂无「飞书页面URL」，跳过下载链接更新")
                print(f"   请先运行 build_feishu_page.py 生成飞书页面，再重跑此步骤")
    elif args.skip_upload:
        print(f"\n[跳过] PDF 上传已禁用（--skip-upload）")

    print(f"\n✅ 完成！输出目录: {output_dir}")


if __name__ == '__main__':
    main()
