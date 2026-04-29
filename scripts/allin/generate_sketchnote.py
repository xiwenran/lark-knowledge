#!/usr/bin/env python3
"""
generate_sketchnote.py — 生成 All In Podcast 手绘笔记图片

从 analysis.json 提炼每张图的内容要点，调用图片生成 API 批量生成。
风格：黑线 + 天蓝色 + 米白背景，Sketchnote 手绘速记风。

用法：
  export IMAGE_API_KEY=sk-xxx
  export IMAGE_API_BASE=https://api.vectorengine.cn    # 第三方中转站
  python3 generate_sketchnote.py --record-id recXXX

  # 或直接传参数：
  python3 generate_sketchnote.py --record-id recXXX \
    --api-key sk-xxx \
    --api-base https://api.vectorengine.cn \
    --model gpt-image-1

  # 只看提示词，不调 API：
  python3 generate_sketchnote.py --record-id recXXX --prompts-only

输出：/tmp/allin_<期号>_sketch_01_封面.png … _sketch_0N_国内启示.png
"""

import json
import os
import re
import sys
import time
import base64
import argparse
import subprocess
import urllib.request
from pathlib import Path
from openai import OpenAI

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent
CONFIG_PATH = Path.home() / ".agents/skills/lark-knowledge-config/config.json"

DEFAULT_API_BASE = "https://api.vectorengine.cn"
DEFAULT_MODEL = "gpt-image-1"

# ── 风格基底（所有图共用）────────────────────────────────
STYLE_BASE = (
    "手绘 sketchnote 笔记风格。黑色线条为主，天蓝色（#4DABF7）作为高亮强调色，"
    "米白色背景（#FAFAF7）。手写字体质感，有涂鸦式图标和指示箭头。"
    "竖版 3:4 比例，内容居中，留白充足，最多 4 个主要视觉元素。"
    "底部右下角标注小字：「All In 中文笔记」。不要出现任何英文界面元素，全部用中文。"
)


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))


def get_record(config: dict, record_id: str) -> dict:
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
    pattern = rf'{marker}[^\n]*\n(.*?)(?=①|②|③|④|⑤|$)'
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ''


def extract_bullets(text: str, max_points: int = 3) -> list:
    """从段落文本提取 2-4 个核心要点"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    sentences = []
    for line in lines:
        for part in re.split(r'[。；;]', line):
            part = part.strip()
            if len(part) > 6:
                sentences.append(part[:32] + ('…' if len(part) > 32 else ''))
    return sentences[:max_points] if sentences else ([text[:40] + '…'] if text else ['（待补充）'])


def parse_first_quote(quotes_text: str) -> dict:
    if not quotes_text:
        return {'en': '', 'zh': '', 'speaker': ''}
    for block in re.split(r'\n\s*\n', quotes_text.strip()):
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        en_m = re.search(r'[""](.+?)[""]', lines[0])
        en = en_m.group(1)[:60] if en_m else ''
        second = lines[1].lstrip('> ').strip()
        zh, speaker = (second.rsplit(' — ', 1) if ' — ' in second else (second, ''))
        return {'en': en, 'zh': zh.strip()[:40], 'speaker': speaker.strip()}
    return {'en': '', 'zh': '', 'speaker': ''}


def build_page_prompts(record: dict, analysis: dict) -> list:
    """根据方案文档第八节，生成每张图的提示词列表"""
    episode  = record.get('期号', 'E???')
    cn_title = record.get('中文标题', '未知标题')
    date     = str(record.get('发布日期', ''))[:10]
    duration = record.get('时长（分钟）', '?')
    views    = record.get('YouTube播放量', 0)
    views_wan = f"{int(views) // 10000}万" if views else '?万'

    five_dim_raw = analysis.get('five_dim', '')
    quotes_text  = analysis.get('quotes', '')

    dim1 = extract_dim(five_dim_raw, '①')
    dim2 = extract_dim(five_dim_raw, '②')
    dim3 = extract_dim(five_dim_raw, '③')
    dim4 = extract_dim(five_dim_raw, '④')
    dim5 = extract_dim(five_dim_raw, '⑤')

    # 从五维内容提取封面关键词
    kw_raw = re.findall(r'[一-鿿]{2,6}(?:领域|趋势|模式|判断|机会|风险|债务|收购|估值|破产|监管|改革)', dim1 + dim2)
    keywords = list(dict.fromkeys(kw_raw))[:3] or ['科技', 'AI', '投资']

    pages = []

    # 第 1 页：封面（固定）
    pages.append({
        'page_num': 1, 'title': '封面',
        'prompt': (
            f"{STYLE_BASE}\n\n"
            f"内容（封面页）：\n"
            f"大标题（手写大字）：{cn_title}\n"
            f"副标题小字：{episode} · {date} · {duration}分钟 · 播放量{views_wan}\n"
            f"中央区域：四位主持人简笔画卡通头像，从左到右依次标注名字：Jason、Chamath、Sacks、Friedberg\n"
            f"底部关键词标签（天蓝色气泡）：{'  ·  '.join(keywords)}\n"
            f"整体构图：标题在上，人物在中，关键词在下，有手绘边框装饰"
        )
    })

    # 第 2 页：核心议题（五维① + ②）
    pts = extract_bullets(dim1 + '。' + dim2, 3)
    bullet_str = '\n'.join(f'  · {p}' for p in pts)
    pages.append({
        'page_num': 2, 'title': '核心议题',
        'prompt': (
            f"{STYLE_BASE}\n\n"
            f"内容（第2页 — 核心议题）：\n"
            f"章节大标题（天蓝色手写）：本期核心议题\n"
            f"要点（每条配手绘图标和箭头）：\n{bullet_str}\n"
            f"版式：从上到下流程式排列，箭头连接，有涂鸦式分割线"
        )
    })

    # 第 3 页：市场判断（五维③）—— 有内容才生成
    if dim3:
        pts3 = extract_bullets(dim3, 3)
        bullet_str3 = '\n'.join(f'  · {p}' for p in pts3)
        pages.append({
            'page_num': 3, 'title': '市场判断',
            'prompt': (
                f"{STYLE_BASE}\n\n"
                f"内容（第3页 — 市场与行业判断）：\n"
                f"章节大标题（天蓝色手写）：市场判断\n"
                f"要点（每条配天蓝色数据高亮框）：\n{bullet_str3}\n"
                f"版式：要点卡片式排列，重要数字用天蓝色方框圈出"
            )
        })

    # 第 4 页：四人立场图谱（五维④）—— 有内容才生成
    if dim4:
        stances = {}
        for name in ['Chamath', 'Jason', 'Sacks', 'Friedberg']:
            m = re.search(rf'{name}[：:]\s*([^。\n]{{1,30}})', dim4)
            stances[name] = m.group(1) if m else '见正文'
        pages.append({
            'page_num': len(pages) + 1, 'title': '四人立场',
            'prompt': (
                f"{STYLE_BASE}\n\n"
                f"内容（第{len(pages)+1}页 — 四人立场图谱）：\n"
                f"章节大标题（天蓝色手写）：四人怎么看\n"
                f"四个对话气泡，各写一位主播的核心观点：\n"
                f"  · Jason 气泡：{stances['Jason']}\n"
                f"  · Chamath 气泡：{stances['Chamath']}\n"
                f"  · Sacks 气泡：{stances['Sacks']}\n"
                f"  · Friedberg 气泡：{stances['Friedberg']}\n"
                f"版式：四个气泡分布在画面四角，中间是话题词，像对话现场"
            )
        })

    # 最后页：国内启示 + 金句（固定）
    pts5 = extract_bullets(dim5, 4)
    bullet_str5 = '\n'.join(f'  · {p}' for p in pts5)
    quote = parse_first_quote(quotes_text)
    quote_line = f"底部金句（手写斜体，天蓝色）：「{quote['zh']}」 — {quote['speaker']}" if quote.get('zh') else ''

    pages.append({
        'page_num': len(pages) + 1, 'title': '国内启示',
        'prompt': (
            f"{STYLE_BASE}\n\n"
            f"内容（最后页 — 国内启示）：\n"
            f"章节大标题（天蓝色手写）：对我们的启示\n"
            f"可迁移判断（每条配灯泡或箭头图标）：\n{bullet_str5}\n"
            f"{quote_line}\n"
            f"系列标识（底部居中小字）：All In 中文知识库\n"
            f"版式：要点从上到下，金句在最底，有装饰性手绘边框"
        )
    })

    return pages


def generate_image(client: OpenAI, prompt: str, page_num: int,
                   model: str = DEFAULT_MODEL, retry: int = 2) -> bytes | None:
    """调用图片 API，返回图片字节"""
    for attempt in range(retry):
        try:
            response = client.images.generate(
                model=model,
                prompt=prompt,
                n=1,
                size="1024x1536",        # 3:4 竖版
                response_format="b64_json",
            )
            item = response.data[0]
            if getattr(item, 'b64_json', None):
                return base64.b64decode(item.b64_json)
            elif getattr(item, 'url', None):
                with urllib.request.urlopen(item.url) as r:
                    return r.read()
        except Exception as e:
            if attempt < retry - 1:
                print(f"  ⚠️  第 {page_num} 张失败（{e}），3s 后重试...")
                time.sleep(3)
            else:
                print(f"  ❌  第 {page_num} 张放弃: {e}")
    return None


def main():
    parser = argparse.ArgumentParser(description='生成 All In Podcast 手绘笔记')
    parser.add_argument('--record-id', required=True)
    parser.add_argument('--analysis', default=None)
    parser.add_argument('--api-key', default=None,
                        help='也可用 IMAGE_API_KEY 环境变量')
    parser.add_argument('--api-base', default=None,
                        help=f'中转站地址，默认 {DEFAULT_API_BASE}，也可用 IMAGE_API_BASE 环境变量')
    parser.add_argument('--model', default=None,
                        help=f'模型名，默认 {DEFAULT_MODEL}')
    parser.add_argument('--output-dir', default='/tmp')
    parser.add_argument('--prompts-only', action='store_true',
                        help='只打印提示词，不调 API')
    args = parser.parse_args()

    api_key  = args.api_key  or os.environ.get('IMAGE_API_KEY')
    api_base = args.api_base or os.environ.get('IMAGE_API_BASE') or DEFAULT_API_BASE
    model    = args.model    or DEFAULT_MODEL

    if not args.prompts_only and not api_key:
        print("❌ 缺少 API Key\n   export IMAGE_API_KEY=your_key  或  --api-key your_key")
        sys.exit(1)

    config = load_config()
    print(f"[飞书] 读取收件表记录 {args.record_id}...")
    record  = get_record(config, args.record_id)
    episode = record.get('期号', 'E???')
    print(f"       {episode} · {record.get('中文标题','')}")

    analysis = {}
    ap = args.analysis or f"/tmp/allin_{args.record_id}_analysis.json"
    if Path(ap).exists():
        analysis = json.loads(Path(ap).read_text(encoding='utf-8'))
        print(f"[分析] 加载: {ap}")
    else:
        print(f"[分析] 未找到 {ap}，将用占位内容")

    pages = build_page_prompts(record, analysis)
    print(f"[规划] 共 {len(pages)} 张：{', '.join(p['title'] for p in pages)}")

    if args.prompts_only:
        print("\n" + "="*60)
        for p in pages:
            print(f"\n── 第 {p['page_num']} 张：{p['title']} ──\n{p['prompt']}")
        return

    client = OpenAI(api_key=api_key, base_url=api_base)
    print(f"[API]  {api_base}  model={model}")

    output_dir = Path(args.output_dir)
    slug = episode.replace(' ', '_')
    generated = []

    for p in pages:
        print(f"\n[生成] {p['page_num']}/{len(pages)} — {p['title']}...")
        img = generate_image(client, p['prompt'], p['page_num'], model)
        if img:
            out = output_dir / f"allin_{slug}_sketch_{p['page_num']:02d}_{p['title']}.png"
            out.write_bytes(img)
            print(f"       ✅ {out.name} ({len(img)//1024} KB)")
            generated.append(str(out))
        time.sleep(1)

    print(f"\n✅ 完成！{len(generated)}/{len(pages)} 张 → {output_dir}")
    for f in generated:
        print(f"   {Path(f).name}")


if __name__ == '__main__':
    main()
