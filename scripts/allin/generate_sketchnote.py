#!/usr/bin/env python3
"""
generate_sketchnote.py — 生成 All In Podcast 手绘笔记图片

从 analysis.json 提炼每张图的内容要点，调用 GPT Image 2 API 批量生成。
风格：黑线 + 天蓝色 + 米白背景，Sketchnote 手绘速记风。

用法：
  export IMAGE_API_KEY=your_key
  export IMAGE_API_BASE=https://your-relay.com/v1   # 第三方中转站
  python3 generate_sketchnote.py --record-id recXXX

  # 或直接传参数：
  python3 generate_sketchnote.py --record-id recXXX \
    --api-key sk-xxx \
    --api-base https://your-relay.com/v1

输出：/tmp/allin_<期号>_sketch_<N>.png（5-8 张）
"""

import json
import os
import re
import sys
import time
import argparse
import subprocess
import base64
from pathlib import Path
from openai import OpenAI

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent
CONFIG_PATH = Path.home() / ".agents/skills/lark-knowledge-config/config.json"

# ── 风格基底（所有图共用）────────────────────────────────
STYLE_BASE = """手绘 sketchnote 笔记风格。黑色线条为主，天蓝色（#4DABF7）作为高亮强调色，米白色背景（#FAFAF7）。手写字体质感，有涂鸦式图标和指示箭头。竖版 3:4 比例，内容居中，留白充足，最多 4 个主要视觉元素。底部右下角标注小字：「All In 中文笔记」。不要出现任何英文界面元素，全部用中文。"""


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


def extract_bullet_points(text: str, max_points: int = 3) -> list[str]:
    """从段落文本里提取 2-4 个核心要点（按句子切割）"""
    # 先按换行拆，再按句号拆
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    sentences = []
    for line in lines:
        parts = re.split(r'[。；;]', line)
        sentences.extend([p.strip() for p in parts if len(p.strip()) > 8])
    # 取前 max_points 条，每条截到 30 字
    result = []
    for s in sentences[:max_points]:
        result.append(s[:30] + ('…' if len(s) > 30 else ''))
    return result or [text[:40] + '…']


def parse_first_quote(quotes_text: str) -> dict:
    """提取第一条精华金句"""
    if not quotes_text:
        return {'en': '', 'zh': '', 'speaker': ''}
    blocks = re.split(r'\n\s*\n', quotes_text.strip())
    for block in blocks:
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        en_m = re.search(r'[""](.+?)[""]', lines[0])
        en = en_m.group(1)[:60] if en_m else ''
        second = lines[1].lstrip('> ').strip()
        if ' — ' in second:
            zh, speaker = second.rsplit(' — ', 1)
        else:
            zh, speaker = second, ''
        return {'en': en, 'zh': zh.strip()[:40], 'speaker': speaker.strip()}
    return {'en': '', 'zh': '', 'speaker': ''}


def build_page_prompts(record: dict, analysis: dict) -> list[dict]:
    """
    根据方案文档第八节，生成每张图的提示词
    返回：[{page_num, title, prompt}]
    """
    episode = record.get('期号', 'E???')
    cn_title = record.get('中文标题', '未知标题')
    date = str(record.get('发布日期', ''))[:10]
    duration = record.get('时长（分钟）', '?')
    views = record.get('YouTube播放量', 0)
    views_wan = f"{int(views) // 10000}万" if views else '?万'

    five_dim_raw = analysis.get('five_dim', '')
    quotes_text = analysis.get('quotes', '')

    dim1 = extract_dim(five_dim_raw, '①')
    dim2 = extract_dim(five_dim_raw, '②')
    dim3 = extract_dim(five_dim_raw, '③')
    dim4 = extract_dim(five_dim_raw, '④')
    dim5 = extract_dim(five_dim_raw, '⑤')

    # 从五维提取关键词（用于封面）
    all_text = ' '.join([dim1, dim2, dim3])
    kw_candidates = re.findall(r'[一-鿿]{2,6}(?:(?:领域|趋势|模式|判断|机会|风险|债务|收购|估值|破产|监管|改革))', all_text)
    keywords = list(dict.fromkeys(kw_candidates))[:3] or ['科技', 'AI', '投资']

    pages = []

    # ── 第 1 页：封面（固定） ─────────────────────────────
    pages.append({
        'page_num': 1,
        'title': '封面',
        'prompt': f"""{STYLE_BASE}

内容（封面页）：
大标题（手写大字）：{cn_title}
副标题小字：{episode} · {date} · {duration}分钟 · 播放量{views_wan}
中央区域：四位主持人的简笔画卡通头像，从左到右依次标注名字：Jason、Chamath、Sacks、Friedberg，每人风格各异（Jason活泼、Chamath自信、Sacks严肃、Friedberg理性）
底部关键词标签（天蓝色气泡）：{'  ·  '.join(keywords)}
整体构图：标题在上，人物在中，关键词在下，有手绘边框装饰"""
    })

    # ── 第 2 页：核心议题（五维①②） ─────────────────────
    points_1_2 = extract_bullet_points(dim1 + '。' + dim2, max_points=3)
    pages.append({
        'page_num': 2,
        'title': '核心议题',
        'prompt': f"""{STYLE_BASE}

内容（第2页 — 核心议题）：
章节大标题（天蓝色手写）：本期核心议题
要点（每条配手绘图标和箭头）：
{''.join(f'  · {p}' + chr(10) for p in points_1_2)}
版式：从上到下流程式排列，箭头连接，有涂鸦式分割线"""
    })

    # ── 第 3 页：市场判断（五维③） ────────────────────────
    if dim3:
        points_3 = extract_bullet_points(dim3, max_points=3)
        pages.append({
            'page_num': 3,
            'title': '市场判断',
            'prompt': f"""{STYLE_BASE}

内容（第3页 — 市场与行业判断）：
章节大标题（天蓝色手写）：市场判断
要点（每条配天蓝色数据高亮框）：
{''.join(f'  · {p}' + chr(10) for p in points_3)}
版式：要点卡片式排列，重要数字用天蓝色方框圈出"""
        })

    # ── 第 4 页：四人立场图谱（五维④） ───────────────────
    if dim4:
        # 尝试提取每人立场
        stances = {}
        for name in ['Chamath', 'Jason', 'Sacks', 'Friedberg']:
            m = re.search(rf'{name}[：:：]\s*([^。\n]+)', dim4)
            stances[name] = m.group(1)[:25] if m else '（见正文）'

        pages.append({
            'page_num': 4,
            'title': '四人立场',
            'prompt': f"""{STYLE_BASE}

内容（第4页 — 四人立场图谱）：
章节大标题（天蓝色手写）：四人怎么看
四个对话气泡，每个气泡内写一位主播的核心观点：
  · Jason 气泡：{stances.get('Jason', '见正文')}
  · Chamath 气泡：{stances.get('Chamath', '见正文')}
  · Sacks 气泡：{stances.get('Sacks', '见正文')}
  · Friedberg 气泡：{stances.get('Friedberg', '见正文')}
版式：四个气泡分布在画面四角，中间是话题词，像对话现场"""
        })

    # ── 最后页：国内启示 + 金句（五维⑤，固定） ────────────
    points_5 = extract_bullet_points(dim5, max_points=4)
    quote = parse_first_quote(quotes_text)

    quote_text = ''
    if quote.get('zh'):
        quote_text = f"底部金句（手写斜体，天蓝色）：「{quote['zh']}」 — {quote['speaker']}"

    pages.append({
        'page_num': len(pages) + 1,
        'title': '国内启示',
        'prompt': f"""{STYLE_BASE}

内容（最后页 — 国内启示）：
章节大标题（天蓝色手写）：对我们的启示
可迁移判断（每条配灯泡或箭头图标）：
{''.join(f'  · {p}' + chr(10) for p in points_5)}
{quote_text}
系列标识（底部居中小字）：All In 中文知识库
版式：要点从上到下，金句在最底，有装饰性手绘边框"""
    })

    return pages


def generate_image(client: OpenAI, prompt: str, page_num: int, retry: int = 2) -> bytes | None:
    """调用 GPT Image 2 API 生成单张图，返回图片字节"""
    for attempt in range(retry):
        try:
            response = client.images.generate(
                model="gpt-image-alpha",   # GPT Image 2 的 API model 名，中转站可能不同，见下方说明
                prompt=prompt,
                n=1,
                size="1024x1365",          # 3:4 竖版
                response_format="b64_json",
                quality="standard"
            )
            b64 = response.data[0].b64_json
            return base64.b64decode(b64)
        except Exception as e:
            if attempt < retry - 1:
                print(f"  ⚠️  第 {page_num} 张生成失败（{e}），{3}s 后重试...")
                time.sleep(3)
            else:
                print(f"  ❌  第 {page_num} 张生成失败，已放弃: {e}")
                return None


def main():
    parser = argparse.ArgumentParser(description='生成 All In Podcast 手绘笔记')
    parser.add_argument('--record-id', required=True, help='飞书收件表 record_id')
    parser.add_argument('--analysis', default=None, help='AI分析结果 JSON 路径（可选）')
    parser.add_argument('--api-key', default=None, help='GPT Image API Key（也可用 IMAGE_API_KEY 环境变量）')
    parser.add_argument('--api-base', default=None, help='API Base URL，第三方中转站地址（也可用 IMAGE_API_BASE 环境变量）')
    parser.add_argument('--model', default=None, help='模型名称，默认 gpt-image-alpha（中转站可能不同）')
    parser.add_argument('--output-dir', default='/tmp', help='输出目录，默认 /tmp')
    parser.add_argument('--prompts-only', action='store_true', help='只打印提示词，不调用 API（调试用）')
    args = parser.parse_args()

    # API 配置
    api_key = args.api_key or os.environ.get('IMAGE_API_KEY')
    api_base = args.api_base or os.environ.get('IMAGE_API_BASE')

    if not args.prompts_only and not api_key:
        print("❌ 缺少 API Key")
        print("   方式1：export IMAGE_API_KEY=your_key")
        print("   方式2：--api-key your_key")
        sys.exit(1)

    config = load_config()

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
        print(f"[分析] 未找到 {analysis_path}，将用占位内容生成图片")

    # 生成每张图的提示词
    pages = build_page_prompts(record, analysis)
    print(f"\n[规划] 共 {len(pages)} 张图：{', '.join(p['title'] for p in pages)}")

    if args.prompts_only:
        print("\n" + "="*60)
        for p in pages:
            print(f"\n── 第 {p['page_num']} 张：{p['title']} ──")
            print(p['prompt'])
        return

    # 初始化 OpenAI 客户端
    client_kwargs = {"api_key": api_key}
    if api_base:
        client_kwargs["base_url"] = api_base
        print(f"[API]  使用中转站: {api_base}")
    client = OpenAI(**client_kwargs)

    # 覆盖模型名（中转站可能用不同名称）
    if args.model:
        for p in pages:
            p['model'] = args.model

    output_dir = Path(args.output_dir)
    episode_slug = episode.replace(' ', '_')
    generated = []

    for p in pages:
        print(f"\n[生成] 第 {p['page_num']}/{len(pages)} 张：{p['title']}...")
        img_bytes = generate_image(client, p['prompt'], p['page_num'])
        if img_bytes:
            out_path = output_dir / f"allin_{episode_slug}_sketch_{p['page_num']:02d}_{p['title']}.png"
            out_path.write_bytes(img_bytes)
            size_kb = len(img_bytes) // 1024
            print(f"       ✅ 已保存: {out_path.name} ({size_kb} KB)")
            generated.append(str(out_path))
        time.sleep(1)  # 避免限流

    print(f"\n✅ 完成！共生成 {len(generated)}/{len(pages)} 张")
    print(f"   输出目录: {output_dir}")
    for f in generated:
        print(f"   {Path(f).name}")


if __name__ == '__main__':
    main()
