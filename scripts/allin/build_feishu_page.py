#!/usr/bin/env python3
"""
build_feishu_page.py — 组装飞书 Wiki 页面（纯自动化部分）

职责：接收翻译好的双语 JSON + AI 分析结果（注释/金句/五维），
      组装完整 Markdown，写入飞书 Wiki，回填收件表。

AI 分析（Haiku核查/Sonnet注释/Opus异常检测）由 Claude Code 主会话负责，
输出写入 /tmp/allin_<ID>_analysis.json 后交给本脚本使用。

用法：
  # 完整流程（需要 analysis.json）
  python3 build_feishu_page.py bilingual.json --record-id recXXX

  # 跳过分析（直接组装，注释留空）
  python3 build_feishu_page.py bilingual.json --record-id recXXX --skip-analysis

  # 只预览，不写飞书
  python3 build_feishu_page.py bilingual.json --record-id recXXX --dry-run
"""

import json
import os
import sys
import re
import argparse
import subprocess
from pathlib import Path

CONFIG_PATH = Path.home() / ".agents/skills/lark-knowledge-config/config.json"


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
    """从五维分析文本提取单个维度内容（兼容同行格式和下一行格式）"""
    # 格式1：内容在下一行（多行段落）
    m = re.search(rf'{marker}[^\n]*\n(.*?)(?=①|②|③|④|⑤|\Z)', text, re.DOTALL)
    if m and m.group(1).strip():
        return m.group(1).strip()
    # 格式2：内容在 ：/: 后的同一行
    m = re.search(rf'{marker}[^：:\n]*[：:]\s*(.+?)(?=\s*[①②③④⑤]|\Z)', text, re.DOTALL)
    return m.group(1).strip() if m else ''


def parse_bilingual_turns(text: str) -> list:
    """
    解析双语发言，返回 [{speaker, en, zh}]
    支持：多行英文、空行间隔、多种冒号格式
    """
    turns = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        en_m = re.match(r'>\s*\*\*([^*]+)\*\*\s*[：:]\s*(.*)', line)
        if en_m:
            speaker_en = en_m.group(1).strip()
            en_text = en_m.group(2).strip()
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if not nxt or nxt.startswith('>') or nxt.startswith('**'):
                    break
                en_text += ' ' + nxt
                j += 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            zh_text = ''
            speaker = speaker_en
            if j < len(lines):
                zh_m = re.match(r'\*\*([^*]+)\*\*[：:]\s*(.*)', lines[j].strip())
                if zh_m:
                    speaker = zh_m.group(1).strip()
                    zh_text = zh_m.group(2).strip()
                    k = j + 1
                    while k < len(lines):
                        nxt = lines[k].strip()
                        if not nxt or nxt.startswith('>') or nxt.startswith('**'):
                            break
                        zh_text += ' ' + nxt
                        k += 1
                    j = k
            speaker = re.sub(r'[：:]\s*$', '', speaker).strip()
            turns.append({'speaker': speaker, 'en': en_text.strip(), 'zh': zh_text.strip()})
            i = j
        else:
            i += 1
    return turns


def build_transcript_section(segments: list, annotations: dict) -> str:
    """组装逐字稿 Markdown，每条发言单独分段，确保飞书正确渲染"""
    parts = []
    for seg in segments:
        time_label = seg.get('time_label', '')
        translated = seg.get('translated', '')

        # 章节标题
        parts.append(f"\n**[{time_label}]**\n")

        # 解析双语发言，每条之间加空行确保飞书不合并引用块
        turns = parse_bilingual_turns(translated)
        if turns:
            for turn in turns:
                speaker = turn['speaker']
                en = turn['en']
                zh = turn['zh']
                # 英文用引用块，中文用普通段落，空行分隔防合并
                parts.append(f"\n> **{speaker}**: {en}\n")
                parts.append(f"**{speaker}**：{zh}\n")
        else:
            # 解析失败退路：直接输出原始内容
            parts.append(translated)

        # 章节注释
        for ann in annotations.get(time_label, []):
            parts.append(f"\n<callout background-color=\"light-blue\">{ann}</callout>")

        parts.append("\n---\n")

    return '\n'.join(parts)


def build_page_markdown(
    segments: list,
    record: dict,
    analysis: dict
) -> str:
    """组装完整飞书页面 Markdown"""

    # 元数据
    episode = record.get('期号', 'E???')
    date = str(record.get('发布日期', ''))[:10]
    duration = record.get('时长（分钟）', '?')
    views = record.get('YouTube播放量', 0)
    views_wan = f"{int(views) // 10000}万" if views else '?万'
    topic = record.get('主题分类', '科技&AI')
    cn_title = record.get('中文标题', '')

    # 五维分析（优先用 analysis.json，其次用收件表，最后用占位）
    five_dim_raw = (
        analysis.get('five_dim', '')
        or record.get('AI摘要', '')
        or record.get('五维分析', '')
    )

    dim1 = extract_dim(five_dim_raw, '①') or analysis.get('dim1', '（待补充）')
    dim2 = extract_dim(five_dim_raw, '②') or analysis.get('dim2', '（待补充）')
    dim3 = extract_dim(five_dim_raw, '③') or analysis.get('dim3', '（待补充）')
    dim4 = extract_dim(five_dim_raw, '④') or analysis.get('dim4', '（待补充）')
    dim5 = extract_dim(five_dim_raw, '⑤') or analysis.get('dim5', '（待补充）')

    # 精华金句
    quotes = analysis.get('quotes', '（待补充）')

    # 逐字稿
    annotations_by_seg = analysis.get('annotations', {})
    transcript_md = build_transcript_section(segments, annotations_by_seg)

    page = f"""{episode} · {date} · {duration}分钟 · 播放量 {views_wan} · {topic}

---

📌 {cn_title}

<callout background-color="light-yellow">
· 议题：{dim1[:80] if dim1 != '（待补充）' else '见五维分析'}
· 关键判断：{dim2[:80] if dim2 != '（待补充）' else '见五维分析'}
· 国内启示：{dim5[:80] if dim5 != '（待补充）' else '见五维分析'}
</callout>

---

## <text color="blue">手绘笔记速览</text>

（待补充）

---

## <text color="blue">📥 下载资源</text>

（待补充）

---

## <text color="blue">五维分析</text>

### <text color="blue">一、本期议题</text>

{dim1}

### <text color="blue">二、核心论点链</text>

{dim2}

### <text color="blue">三、市场与行业判断</text>

{dim3}

### <text color="blue">四、四人立场图谱</text>

{dim4}

### <text color="blue">五、国内启示</text>

{dim5}

---

## <text color="blue">精华金句</text>

{quotes}

---

## <text color="blue">中英对照逐字稿</text>

{transcript_md}
"""
    return page


def write_to_feishu(config: dict, wiki_node: str, title: str, page_md: str, record_id: str) -> str:
    """分批写入飞书 Wiki，返回 wiki URL"""

    split_marker = '## <text color="blue">中英对照逐字稿</text>'
    if split_marker in page_md:
        idx = page_md.index(split_marker)
        header_part = page_md[:idx + len(split_marker)]
        transcript_part = page_md[idx + len(split_marker):]
    else:
        header_part = page_md
        transcript_part = ""

    print("[飞书] 创建页面（头部 + 五维 + 金句）...")
    result = subprocess.run([
        "lark-cli", "docs", "+create",
        "--wiki-node", wiki_node,
        "--title", title,
        "--markdown", header_part
    ], capture_output=True, text=True)

    data = json.loads(result.stdout)
    if not data.get("ok"):
        raise RuntimeError(f"页面创建失败: {result.stdout}")

    doc_token = data["data"]["doc_id"]
    wiki_url = data["data"].get("doc_url") or f"https://www.feishu.cn/wiki/{doc_token}"
    print(f"       页面已创建: {wiki_url}")

    # 逐字稿按段分批 append
    if transcript_part.strip():
        seg_blocks = re.split(r'\n(?=\*\*\[)', transcript_part)
        batch_size = 4
        total_batches = (len(seg_blocks) + batch_size - 1) // batch_size
        for i in range(0, len(seg_blocks), batch_size):
            batch = '\n'.join(seg_blocks[i:i+batch_size])
            batch_num = i // batch_size + 1
            print(f"[飞书] 追加逐字稿 {batch_num}/{total_batches}...")
            r = subprocess.run([
                "lark-cli", "docs", "+update",
                "--doc", wiki_url,
                "--mode", "append",
                "--markdown", batch
            ], capture_output=True, text=True)
            if not json.loads(r.stdout).get("ok"):
                print(f"       ⚠️ 批次 {batch_num} 写入失败: {r.stdout[:100]}")

    # 回填收件表
    print("[飞书] 回填收件表...")
    subprocess.run([
        "lark-cli", "base", "+record-upsert",
        "--base-token", config["all_in_podcast"]["base_token"],
        "--table-id", config["all_in_podcast"]["table_id"],
        "--record-id", record_id,
        "--json", json.dumps({
            "飞书页面URL": wiki_url,
            "翻译状态": "已完成",
            "注释状态": "已完成"
        })
    ], capture_output=True, text=True)

    return wiki_url


def main():
    parser = argparse.ArgumentParser(description='组装 All In Podcast 飞书页面')
    parser.add_argument('input', help='bilingual.json 路径')
    parser.add_argument('--record-id', required=True, help='飞书收件表 record_id')
    parser.add_argument('--analysis', default=None,
                        help='AI分析结果 JSON（含 quotes/annotations/five_dim），可选')
    parser.add_argument('--skip-analysis', action='store_true',
                        help='不使用 AI 分析，直接组装（注释/金句留空）')
    parser.add_argument('--dry-run', action='store_true',
                        help='只生成预览 /tmp/allin_preview.md，不写飞书')
    args = parser.parse_args()

    config = load_config()

    print(f"[加载] 读取 {args.input}")
    segments = json.loads(Path(args.input).read_text(encoding='utf-8'))
    print(f"       共 {len(segments)} 段，{sum(len(s.get('translated','')) for s in segments)} 字符")

    print(f"[飞书] 读取收件表记录 {args.record_id}...")
    record = get_record(config, args.record_id)
    episode = record.get('期号', 'E???')
    cn_title = record.get('中文标题', '未知标题')
    topic = record.get('主题分类', '科技&AI')
    date_str = str(record.get('发布日期', ''))
    year = date_str[:4] if date_str else '2026'
    print(f"       {episode} · {cn_title}")

    # 加载 AI 分析结果
    analysis = {}
    if not args.skip_analysis:
        analysis_path = args.analysis or f"/tmp/allin_{args.record_id}_analysis.json"
        if Path(analysis_path).exists():
            analysis = json.loads(Path(analysis_path).read_text(encoding='utf-8'))
            print(f"[分析] 加载 AI 分析: {analysis_path}")
        else:
            print(f"[分析] 未找到 {analysis_path}，注释/金句将留空")
            print(f"       提示：先在 Claude Code 中运行 AI 分析步骤，输出到该文件")

    # 组装页面
    print("[组装] 生成页面 Markdown...")
    page_md = build_page_markdown(segments, record, analysis)

    if args.dry_run:
        preview_path = '/tmp/allin_preview.md'
        Path(preview_path).write_text(page_md, encoding='utf-8')
        print(f"\n✅ 预览文件: {preview_path}")
        print(f"   大小: {len(page_md):,} 字符 ({len(page_md.encode())//1024} KB)")

        # 打印页面结构概览
        sections = [l for l in page_md.splitlines() if l.startswith('##')]
        print(f"\n页面结构：")
        for s in sections:
            print(f"   {s[:60]}")
        return

    # 写入飞书
    wiki_dirs = config["all_in_podcast"]["wiki"]["directories"]
    topic_dirs = wiki_dirs.get(topic, wiki_dirs["科技&AI"])
    wiki_node = (
        topic_dirs.get(year)
        or topic_dirs.get("2026")
        or topic_dirs.get("2025")
        or topic_dirs.get("root")
        or wiki_dirs["科技&AI"]["2026"]
    ) if isinstance(topic_dirs, dict) else wiki_dirs["科技&AI"]["2026"]

    title = f"{episode} · {cn_title}"
    wiki_url = write_to_feishu(config, wiki_node, title, page_md, args.record_id)

    print(f"\n✅ 完成！")
    print(f"   页面：{wiki_url}")
    print(f"   {episode} | {cn_title}")


if __name__ == '__main__':
    main()
