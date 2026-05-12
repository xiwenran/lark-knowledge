#!/usr/bin/env python3
"""
generate_sketchnote.py — 生成 All In Podcast 手绘笔记图片

从 analysis.json 提炼每张图的内容要点，调用图片生成 API 批量生成。
风格：V2 手绘高级概念海报（cover_v2 + inner_v2 双模板）。

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

输出：/tmp/allin_<期号>_sketch_01_封面.png … _sketch_0N_<页面标题>.png

支持两种模式：
  - 动态模式（推荐）：analysis.json 含 story_plan 字段，页数/标题/内容由 AI 决定
  - 固定模式（兼容）：无 story_plan 时回退到固定 4 页结构
"""

import json
import os
import re
import sys
import time
import base64
import argparse
import concurrent.futures
import shutil
import subprocess
import urllib.request
from pathlib import Path
from openai import OpenAI

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent

DEFAULT_API_BASE = "https://api.vectorengine.cn/v1"
DEFAULT_MODEL = "gpt-image-2"
MIN_IMAGE_BYTES = 10 * 1024

# 引入共享工具
import sys as _sys
_sys.path.insert(0, str(REPO_ROOT))
_sys.path.insert(0, str(SCRIPT_DIR))
from scripts.shared import poster_template
from utils import load_config, get_record


def extract_dim(text: str, marker: str) -> str:
    """兼容两种 AI 输出格式：
    格式1（内容在下一行）：① 议题背景\n内容...
    格式2（内容在同行）：① 议题背景：内容...
    """
    # 格式1：内容在下一行
    m = re.search(rf'{marker}[^\n]*\n(.*?)(?=①|②|③|④|⑤|\Z)', text, re.DOTALL)
    if m and m.group(1).strip():
        return m.group(1).strip()
    # 格式2：内容在 ：/: 后的同行
    m = re.search(rf'{marker}[^：:\n]*[：:]\s*(.+?)(?=\s*[①②③④⑤]|\Z)', text, re.DOTALL)
    return m.group(1).strip() if m else ''


def extract_bullets(text: str, max_points: int = 3, max_len: int = 60) -> list:
    """从段落文本提取 2-4 个核心要点。
    先剥离飞书富文本标签，避免 <text color="..."> 等标签被当作内容截入要点。
    要点长度默认 60 字符（之前 32 字偏短，让内页像封面而不是内容页）。"""
    text = strip_feishu_tags(text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    sentences = []
    for line in lines:
        for part in re.split(r'[。；;]', line):
            part = part.strip()
            if len(part) > 6:
                sentences.append(part[:max_len] + ('…' if len(part) > max_len else ''))
    return sentences[:max_points] if sentences else ([text[:max_len + 8] + '…'] if text else ['（待补充）'])


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


def format_views(views) -> str:
    """播放量转「万」格式，兼容数字和带逗号字符串。"""
    try:
        v = int(str(views).replace(',', '').replace('，', ''))
    except (TypeError, ValueError):
        return '?万'
    return f"{v // 10000}万" if v >= 10000 else str(v)


def format_duration(duration) -> str:
    text = str(duration or '?').strip()
    return text if text.endswith('分钟') else f"{text}分钟"


def parse_pages_arg(arg) -> set[int] | None:
    """解析 --pages：None/空值表示全部；否则只允许 1-5 的页码。"""
    if arg is None:
        return None
    text = str(arg).strip()
    if not text:
        return None

    pages = set()
    for item in text.split(','):
        item = item.strip()
        if not item or not item.isdigit():
            raise argparse.ArgumentTypeError('--pages 只接受数字，多个页码用英文逗号分隔')
        page_num = int(item)
        if page_num < 1 or page_num > 20:
            raise argparse.ArgumentTypeError('--pages 页码范围只能是 1-20')
        pages.add(page_num)
    return pages


def strip_feishu_tags(text: str) -> str:
    """剥离飞书富文本标签（<text color="...">...</text> / <callout .../> 等），
    保留内部纯文本。否则 short_phrase 会把标签字符当成普通字符处理，
    导致「textcolorblueSpaceX」这类前缀污染。"""
    text = str(text)
    # 先把 <text color="...">...</text> 内部内容保留，标签去掉
    text = re.sub(r'<text\b[^>]*>', '', text)
    text = re.sub(r'</text>', '', text)
    # 其它飞书富文本标签（callout / view / file / image / grid / column）一并剥
    text = re.sub(r'</?(?:callout|view|file|image|grid|column)\b[^>]*/?>', '', text)
    return text


_TRAILING_PARTICLES = '的了着过吧呢么么呀啊嘛'  # 助词
_TRAILING_PREPOSITIONS = '在对从向到给为让使被由以与和及或者而'  # 介词/连词


def short_phrase(text: str, fallback: str, max_len: int = 14, exclude: set = None) -> str:
    """提取标签短语。优先级：
    1. METAPHOR_LIBRARY 预设词命中（如「算力入口」「债务炸弹」）
    2. 英文名词或大写缩写（如 SpaceX / Cursor / SaaS / AWS）
    3. 中文首句截断 + 虚词尾保护（避免「算力即入口的」「氯吡硫磷在国」这类切割）

    exclude: 已使用的 label 集合，命中已用的会跳到下一个候选（避免同一期多个 point label 重复）。
    """
    exclude = exclude or set()
    text = strip_feishu_tags(text)
    text = re.sub(r'^[①②③④⑤一二三四五六七八九十、：:\s]+', '', text).strip()

    # 优先 1：METAPHOR_LIBRARY 全文命中（找第一个未被使用的）
    for key in poster_template.METAPHOR_LIBRARY:
        if key in text and key not in exclude:
            return key

    # 优先 2a：连续两个大写词组合（如 "App Store"、"Google Cloud"），找第一个未被使用的
    for m in re.finditer(r'(?:^|[^A-Za-z])([A-Z][A-Za-z0-9]+\s+[A-Z][A-Za-z0-9]+)(?=[^A-Za-z]|$)', text):
        if m.group(1) not in exclude:
            return m.group(1)
    # 优先 2b：单个大写词（缩写或名词），至少 4 字符（避开 App/End/Big 等常见短词）
    # 注：不用 \b（Python 3 中文是 \w，"果" 与 "A" 之间无 word boundary，会跳过 App 误匹配 Store）
    for m in re.finditer(r'(?:^|[^A-Za-z])([A-Z][A-Za-z0-9]{3,15})(?=[^A-Za-z]|$)', text):
        if m.group(1) not in exclude:
            return m.group(1)

    # 中文：取首句到第一个标点
    chinese_text = re.sub(r'[，。；;：:、\n].*$', '', text).strip()
    chinese_text = re.sub(r'[^\w一-鿿&+·-]', '', chinese_text)

    if not chinese_text:
        return fallback

    if len(chinese_text) <= max_len:
        truncated = chinese_text
    else:
        truncated = chinese_text[:max_len]

    # 虚词尾保护：先去助词尾（如「的」），再去「介词+单字」尾（如「在国」「向人」）
    while len(truncated) > 2 and truncated[-1] in _TRAILING_PARTICLES:
        truncated = truncated[:-1]
    truncated = re.sub(rf'[{_TRAILING_PREPOSITIONS}][^a-zA-Z]{{1,2}}$', '', truncated)
    while len(truncated) > 2 and truncated[-1] in _TRAILING_PARTICLES:
        truncated = truncated[:-1]

    if truncated and truncated not in exclude:
        return truncated

    # 如果中文 fallback 也重复，再尝试取第二个短句
    rest = re.sub(r'^[^，。；;：:、\n]*[，。；;：:、\n]+', '', text).strip()
    if rest:
        rest_clean = re.sub(r'[，。；;：:、\n].*$', '', rest)
        rest_clean = re.sub(r'[^\w一-鿿&+·-]', '', rest_clean)[:max_len]
        if rest_clean and rest_clean not in exclude:
            return rest_clean

    return truncated or fallback


def pick_core_word(title: str, five_dim_raw: str = '') -> str:
    """从中文标题优先提取 2-4 字核心词，保持确定性。"""
    if '：' in title or ':' in title:
        tail = re.split(r'[：:]', title, maxsplit=1)[1]
        m = re.search(r'[一-鿿]{2,4}', tail)
        if m:
            return m.group(0)

    candidates = []
    source = f"{title} {five_dim_raw}"
    for key in poster_template.METAPHOR_LIBRARY:
        if key in source:
            candidates.append(key)
    candidates.extend(re.findall(r'[一-鿿]{2,4}(?:入口|监管|主权|能源|芯片|关税|开源|算力|债务|云)', source))
    return candidates[0] if candidates else short_phrase(title, '核心议题', 4)


def pick_metaphor_key(text: str) -> str:
    for key in poster_template.METAPHOR_LIBRARY:
        if key in text:
            return key
    keyword_map = {
        '监管': 'AI监管',
        '数据': '数据主权',
        '能源': '能源',
        '芯片': '芯片',
        '关税': '关税',
        '开源': '开源',
        '加密': '加密货币',
        '货币': '加密货币',
        '算力': '算力入口',
    }
    for keyword, key in keyword_map.items():
        if keyword in text:
            return key
    return '算力入口'


def format_metaphor_options(key: str) -> str:
    options = poster_template.METAPHOR_LIBRARY.get(key, [])
    return '\n'.join(options) if options else (
        "A. 以核心词形成巨型水墨剪影\n"
        "B. 用一个微小角色面对巨型结构，制造命运感\n"
        "C. 让主题物件与产业场景交织成统一画面\n"
        "D. 用留白和墨迹路径表达趋势方向"
    )


def build_cover_params(record: dict, analysis: dict) -> dict:
    """提取 cover_v2 模板填空参数。"""
    five_dim_raw = analysis.get('five_dim', '')
    dim1 = extract_dim(five_dim_raw, '①')
    dim2 = extract_dim(five_dim_raw, '②')

    episode = record.get('期号', 'E???')
    title = record.get('中文标题', '未知标题')
    core_word = pick_core_word(title, five_dim_raw)
    context_text = dim1 or dim2 or title
    context = extract_bullets(context_text, 2)
    point_candidates = extract_bullets(f"{dim1}。{dim2}", 3)
    metaphor_key = pick_metaphor_key(f"{core_word} {title} {dim1} {dim2}")

    sub_words = [short_phrase(point, fallback) for point, fallback in zip(
        point_candidates,
        ['核心议题', '论点链', '市场判断'],
    )]
    while len(sub_words) < 3:
        sub_words.append(['核心议题', '论点链', '市场判断'][len(sub_words)])

    return {
        'episode': episode,
        'date': str(record.get('发布日期', ''))[:10] or '未知日期',
        'duration': format_duration(record.get('时长（分钟）', '?')),
        'views': format_views(record.get('YouTube播放量', 0)),
        'topic': record.get('主题分类', '未分类'),
        'title': title,
        'core_word': core_word,
        'sub_words': '·'.join(sub_words[:3]),
        'context': '\n'.join(f"- {item}" for item in context),
        'points': '\n'.join(f"- {item}" for item in point_candidates),
        'core_word_symbolism': (
            f"「{core_word}」象征本期讨论中的关键入口与结构性力量。"
            "请把它拆成可被看见的基础设施、关口、路径或秩序变化，"
            "让观者无需读解释也能感到议题重量。"
        ),
        'metaphor_options': format_metaphor_options(metaphor_key),
        'aux_poetry': '\n'.join(f"- 「{item}」" for item in sub_words[:2]),
        'forbidden': '',
    }


def extract_stance(text: str, name: str) -> str:
    """三层匹配，逐层放宽，确保提取到真实内容而非「见正文」占位符。
    入口先剥离飞书富文本标签，避免 </text> 等标签残留到立场说明里。"""
    text = strip_feishu_tags(text)
    m = re.search(rf'{name}[：:]\s*([^。\n]{{5,35}})', text)
    if m:
        return m.group(1).strip()
    m = re.search(
        rf'{name}[^，。；\n]{{0,12}}(?:认为|表示|指出|则|强调|认定|判断)\s*([^。；\n]{{5,40}})',
        text
    )
    if m:
        return m.group(1).lstrip('，, ').strip()
    for sent in re.split(r'[。；\n]', text):
        if name in sent:
            idx = sent.index(name)
            chunk = sent[idx + len(name):].lstrip('则是而：: ，,').strip()
            if len(chunk) >= 5:
                return (chunk[:35] + '…') if len(chunk) > 35 else chunk
    return ''


def build_points(text: str, fallbacks: list[str], icon_hint: str) -> list[dict]:
    """构造 3 个 point，确保 label 互不重复（避免同一页 SpaceX/SpaceX/Cursor 这种 bug）。"""
    bullets = extract_bullets(text, len(fallbacks))
    points = []
    used_labels = set()
    for idx, fallback in enumerate(fallbacks):
        body = bullets[idx] if idx < len(bullets) else fallback
        label = short_phrase(body, fallback, 14, exclude=used_labels)
        used_labels.add(label)
        points.append({
            'label': label,
            'text': body,
            'icon_hint': icon_hint,
        })
    return points


def format_points(points: list[dict]) -> str:
    return '\n'.join(
        f"  要点{i + 1}「{p['label']}」：{p['text']}\n  视觉建议：{p['icon_hint']}"
        for i, p in enumerate(points)
    )


def build_inner_params(record: dict, analysis: dict, page_index: int) -> dict:
    """提取 inner_v2 模板填空参数（旧版 gpt-image-2 模式，保留兼容）。"""
    five_dim_raw = analysis.get('five_dim', '')
    quotes_text = analysis.get('quotes', '')
    dim1 = extract_dim(five_dim_raw, '①')
    dim2 = extract_dim(five_dim_raw, '②')
    dim3 = extract_dim(five_dim_raw, '③')
    dim4 = extract_dim(five_dim_raw, '④')
    dim5 = extract_dim(five_dim_raw, '⑤')
    title = record.get('中文标题', '未知标题')

    page_specs = [
        {
            'page_title': '核心议题',
            'source': f"{dim1}。{dim2}",
            'subtitle': '议题背景与核心论点链',
            'fallbacks': ['工具是入口', '论点链展开', '结构性变化'],
            'motif': '让核心母题的不同侧面分别承载背景、论点和转折。',
            'icon': '手绘入口 / 路径箭头 / 结构剖面',
        },
        {
            'page_title': '市场判断',
            'source': dim3,
            'subtitle': '行业趋势、估值与风险信号',
            'fallbacks': ['趋势信号', '估值变化', '风险边界'],
            'motif': '让母题像钟摆或天秤一样贯穿三处判断，表现紧迫感和权衡。',
            'icon': '手绘钟摆 / 天秤 / 数据刻度',
        },
        {
            'page_title': '四人立场',
            'source': dim4,
            'subtitle': 'Jason · Chamath · Sacks · Friedberg 的分歧坐标',
            'fallbacks': ['Jason 立场', 'Chamath 立场', 'Sacks 立场', 'Friedberg 立场'],
            'motif': '让母题像四向罗盘或十字路口，四个方向分别承载四位主播。',
            'icon': '手绘罗盘 / 路标 / 对话批注',
        },
        {
            'page_title': '国内启示',
            'source': dim5,
            'subtitle': '可迁移到中国市场的判断',
            'fallbacks': ['中国类比', '可迁移判断', '行动启示'],
            'motif': '让母题像灯塔、种子或航线，三个要点沿光线或路径展开。',
            'icon': '手绘灯塔 / 种子萌芽 / 航线图',
        },
    ]
    spec = page_specs[page_index]

    if page_index == 2 and dim4:
        fallback = extract_bullets(dim4, 1)[0]
        stances = {
            name: extract_stance(dim4, name) or fallback
            for name in ['Jason', 'Chamath', 'Sacks', 'Friedberg']
        }
        points = [
            {'label': name, 'text': stances[name], 'icon_hint': spec['icon']}
            for name in ['Jason', 'Chamath', 'Sacks', 'Friedberg']
        ]
    else:
        points = build_points(spec['source'], spec['fallbacks'], spec['icon'])

    metaphor_key = pick_metaphor_key(f"{title} {spec['source']}")
    metaphor_options = poster_template.METAPHOR_LIBRARY.get(metaphor_key, [])
    metaphor_hint = metaphor_options[page_index % len(metaphor_options)] if metaphor_options else ''
    quote = parse_first_quote(quotes_text)
    aux_poetry = quote['zh'] if page_index == 3 and quote.get('zh') else short_phrase(spec['source'], spec['page_title'], 10)

    return {
        'page_title': spec['page_title'],
        'core_keyword': metaphor_key if page_index == 0 else ['钟摆', '罗盘', '灯塔'][page_index - 1],
        'page_subtitle': spec['subtitle'],
        'points': points,
        'cross_page_motif_hint': f"{spec['motif']} 隐喻方向参考「{metaphor_key}」：{metaphor_hint}",
        'aux_poetry': f"「{aux_poetry}」",
    }


def render_inner_from_params(params: dict) -> str:
    render_params = dict(params)
    render_params['points'] = format_points(params['points'])
    return poster_template.render_inner_prompt(render_params)


# ── SVG 内页参数构建（认知驱动结构）──────────────────────────────

def _strip_tags(text: str) -> str:
    """去除飞书富文本标签 <text color="...">...</text>。"""
    return re.sub(r'</?text[^>]*>', '', text)


def _char_width(ch: str) -> float:
    """估算单个字符在 font-size=30 PingFang SC 下的渲染宽度（SVG px）。
    数值来自 cairosvg 实际渲染测量。
    """
    if ch in '""''':
        return 13.0
    if ch in '，。、；：！？':
        return 28.0
    if ch in '…——–—':
        return 30.0
    if ch in '「」『』【】（）':
        return 28.0
    if '一' <= ch <= '鿿' or '㐀' <= ch <= '䶿':
        return 29.5
    if ch in '()[]{}':
        return 14.0
    if ch.isdigit():
        return 17.5
    if ch.isascii() and ch.isalpha():
        if ch.isupper():
            return 20.0
        return 16.5
    if ch in ' \t':
        return 8.0
    if ch in '.,:;!?':
        return 10.0
    if ch in '%':
        return 28.0
    if ch in '#@&$':
        return 18.0
    return 20.0


def _text_width(text: str) -> float:
    """估算一段文字的总渲染宽度（SVG px）。"""
    return sum(_char_width(c) for c in text)


# 左边距55 + 右边距55 = 可用宽度 970px
_MAX_LINE_PX = 930


def _wrap_lines(text: str, max_chars: int = 20, max_lines: int = 3) -> list[str]:
    """按像素宽度估算折行，不拆断英文单词，限制总行数。
    max_chars 仍保留作为硬上限兜底（防止估算偏差导致溢出）。
    """
    text = _strip_tags(text).strip()
    if not text:
        return []
    lines = []
    while text and len(lines) < max_lines - 1:
        if _text_width(text) <= _MAX_LINE_PX:
            break
        # 逐字累加找到像素断点
        cut = 0
        px = 0.0
        for i, ch in enumerate(text):
            px += _char_width(ch)
            if px > _MAX_LINE_PX:
                cut = i
                break
        else:
            break
        if cut == 0:
            cut = 1
        # 硬上限兜底
        if cut > max_chars:
            cut = max_chars
        # 不在英文单词中间切
        if cut < len(text) and text[cut].isascii() and text[cut].isalpha():
            saved = cut
            while cut > 0 and text[cut - 1].isascii() and text[cut - 1].isalpha():
                cut -= 1
            if cut == 0:
                cut = saved
        # 不在中文标点前切
        if cut < len(text) and text[cut] in '，。、；：）」』】!？…——':
            saved = cut
            while cut > 0 and text[cut] in '，。、；：）」』】!？…——':
                cut -= 1
            if cut == 0:
                cut = saved
        lines.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    if text:
        if _text_width(text) > _MAX_LINE_PX:
            # 截断到像素限制内
            px = 0.0
            for i, ch in enumerate(text):
                px += _char_width(ch)
                if px > _MAX_LINE_PX - 30:
                    text = text[:i] + '…'
                    break
        lines.append(text)
    return lines[:max_lines]


def _first_sentence(text: str, max_len: int = 40, min_len: int = 10) -> str:
    """取第一个足够长的完整句子，不超过 max_len。"""
    for sep in ['。', '；']:
        idx = text.find(sep)
        if min_len <= idx <= max_len:
            return text[:idx + 1]
    # 句号找不到，试逗号但要求更长
    pos = 0
    while True:
        idx = text.find('，', pos)
        if idx < 0 or idx > max_len:
            break
        if idx >= min_len:
            return text[:idx + 1]
        pos = idx + 1
    return (text[:max_len - 1] + '…') if len(text) > max_len else text


def _parse_zh_quotes(quotes_text: str) -> list[str]:
    """从金句 Markdown 中提取所有中文译文行，去除归属（— Speaker）。"""
    results = []
    for line in quotes_text.split('\n'):
        line = line.strip()
        if not line.startswith('>'):
            continue
        clean = re.sub(r'^>\s*\*?\*?', '', line).strip(' "「」*')
        if not clean or not re.search(r'[一-鿿]', clean):
            continue
        # 去掉 "— Speaker Name" 及其后续内容（含括号注释如"（论 Medallia 案例）"）
        clean = re.sub(r'\s*[—–-]+\s*[A-Za-z][\w\s]*(?:[（(].*?[）)])?.*$', '', clean).strip()
        clean = re.sub(r'\s*[—–-]+\s*[一-鿿].*$', '', clean).strip()
        # 去掉行尾残留的括号注释和 Markdown 格式残留
        clean = re.sub(r'\s*[（(][^）)]*[）)]?\s*$', '', clean).strip()
        clean = clean.strip(' "\"「」*')
        if clean:
            results.append(clean)
    return results


def build_svg_inner_params(record: dict, analysis: dict, page_index: int) -> dict:
    """为 SVG 内页模板构建参数。认知驱动结构：
    0=最反直觉的判断, 1=嘉宾最激烈的分歧, 2=说回咱们, 3=完整资料预览。

    每个 body section 严格限制 3 行 × 20字，匹配 SVG 模板固定布局。
    """
    five_dim_raw = analysis.get('five_dim', '')
    quotes_text = analysis.get('quotes', '')
    dim1 = _strip_tags(extract_dim(five_dim_raw, '①'))
    dim2 = _strip_tags(extract_dim(five_dim_raw, '②'))
    dim3 = _strip_tags(extract_dim(five_dim_raw, '③'))
    dim4 = _strip_tags(extract_dim(five_dim_raw, '④'))
    dim5 = _strip_tags(extract_dim(five_dim_raw, '⑤'))
    episode = record.get('期号', '???')
    zh_quotes = _parse_zh_quotes(quotes_text)
    info = f"All In Podcast E{episode} · 中文知识库"

    W = 40  # 字符数硬上限兜底；实际由 _wrap_lines 按像素宽度断行（_MAX_LINE_PX=970）

    if page_index == 0:
        # 本期最反直觉的判断
        highlight = zh_quotes[0] if zh_quotes else _first_sentence(dim2, 40)
        # 段1：背景
        b1 = _wrap_lines(_first_sentence(dim1, 60), W)
        # 段2：关键论点（用第二条金句或 dim2 的第二句，避免和 highlight 重复）
        core = zh_quotes[1] if len(zh_quotes) > 1 else _first_sentence(dim2, 36)
        b2 = ['!但他们说了一句让人重新想的话——'] + ['>' + l for l in _wrap_lines(core, W - 2, 2)]
        # 段3：展开论证
        sentences = [s.strip() for s in dim2.split('。') if s.strip()]
        expand = sentences[1] + '。' if len(sentences) > 1 else _first_sentence(dim3, 60)
        b3 = _wrap_lines(expand, W)
        # 段4：对你意味什么
        insight = _first_sentence(dim5, 50) if dim5 else '值得持续关注这个方向的变化。'
        b4 = ['!对你意味着什么：'] + _wrap_lines(insight, W, 2)

        return {
            'page_title': '本期最反直觉的判断',
            'highlight_lines': _wrap_lines(highlight, W - 2, 2),
            'body_sections': [b1, b2, b3, b4],
            'page_number': 2,
            'info_text': info,
        }

    elif page_index == 1:
        # 嘉宾最激烈的分歧
        stances = {
            name: _strip_tags(extract_stance(dim4, name) or '')
            for name in ['Sacks', 'Chamath', 'Jason', 'Friedberg']
        }
        aggressive_name = 'Sacks' if stances.get('Sacks') else 'Chamath'
        aggressive = stances.get(aggressive_name, '')
        rebuttal_name = 'Jason' if stances.get('Jason') else 'Friedberg'
        rebuttal = stances.get(rebuttal_name, '')

        # 找中文金句作为 highlight（取最长的一条，不用硬编码关键词过滤）
        dispute_quote = ''
        if zh_quotes:
            dispute_quote = max(zh_quotes, key=len)
        if not dispute_quote:
            dispute_quote = aggressive[:36] if aggressive else _first_sentence(dim3, 36)

        b1 = _wrap_lines(_first_sentence(dim3, 60), W)
        b2 = [f'!{aggressive_name}最激进：'] + ['>' + l for l in _wrap_lines(aggressive[:36] if aggressive else dim3[:30], W - 2, 2)]
        b3 = [f'!{rebuttal_name}立刻反驳：'] + _wrap_lines(rebuttal[:40] if rebuttal else '有数据护城河的公司完全不同。', W, 2)
        b4 = ['!对你意味着什么：'] + _wrap_lines(_first_sentence(dim5, 40) if dim5 else '留意你所在行业的替代信号。', W, 2)

        return {
            'page_title': '嘉宾最激烈的分歧',
            'highlight_lines': _wrap_lines(dispute_quote, W - 4, 2),
            'body_sections': [b1, b2, b3, b4],
            'page_number': 3,
            'info_text': info,
        }

    elif page_index == 2:
        # 说回咱们：你现在能做什么
        dim5_sentences = [s.strip() for s in dim5.split('。') if s.strip()]
        # 取 dim5 第一句作为 highlight（不再硬编码固定文字）
        highlight_text = _first_sentence(dim5, 50) if dim5 else '这期的启发值得细想。'

        relevant = [s for s in dim5_sentences if len(s) >= 6]
        if not relevant:
            relevant = dim5_sentences[:3]
        bullets = relevant[:3] if relevant else ['关注行业变化信号', '判断自身定位', '抓住时间窗口']

        def _action_block(label: str, text: str) -> list[str]:
            return [f'!{label}'] + _wrap_lines(text, W, 2)

        b1 = _action_block('第一件事：', _first_sentence(bullets[0], 40) if bullets else '关注成本结构变化。')
        b2 = _action_block('第二件事：', _first_sentence(bullets[1], 40) if len(bullets) > 1 else '判断你的行业是界面层还是基础设施层。')
        b3 = _action_block('第三件事：', _first_sentence(bullets[2], 40) if len(bullets) > 2 else '今天做不起的AI项目，一年半后成本减半。')
        # 国内对标：从 remaining sentences（排除已用的 bullets）中找
        used_texts = set(bullets[:3])
        remaining = [s for s in relevant if s not in used_texts]
        china_part = next((s for s in remaining if any(k in s for k in ['国内', '中国', '字节', '阿里', '华为', '腾讯'])), '')
        if not china_part:
            china_part = remaining[0] if remaining else ''
        b4 = ['!国内对标：'] + _wrap_lines(_first_sentence(china_part, 40) if china_part else '字节豆包正在走AI+SaaS融合路线。', W, 2)

        return {
            'page_title': '说回咱们：你现在能做什么',
            'highlight_lines': _wrap_lines(highlight_text, W - 2, 2),
            'body_sections': [b1, b2, b3, b4],
            'page_number': 4,
            'info_text': info,
        }

    else:
        # 完整资料预览（动态使用当期标题）
        ep_title = record.get('中文标题', '本期内容')
        dim1_brief = _first_sentence(dim1, 30) if dim1 else '深度分析'
        return {
            'page_title': '完整资料预览',
            'highlight_lines': _wrap_lines(f'E{episode} 完整资料已整理好', W - 2, 2),
            'body_sections': [
                ['!本期资料包含：', f'· {ep_title} 完整中英对照逐字稿', f'· {dim1_brief} 深度分析'],
                ['· 精华金句双语对照', '· 嘉宾立场图谱', '· 国内市场对标分析'],
                ['!All In Podcast 中文知识库', '持续更新中，每期从原版英文出发。', ''],
                ['!获取方式：', '评论区置顶 或 私信「All In」', ''],
            ],
            'page_number': 5,
            'info_text': info,
        }


def _split_title_for_cover(title: str, max_chars: int = 8) -> list[str]:
    """将中文标题拆为 2-3 行，尊重英文单词边界，递归处理长段。"""
    if len(title) <= max_chars:
        return [title]
    # 先在逗号/冒号处分割
    for sep in ['，', '：', '、', '——']:
        if sep in title:
            parts = [p.strip() for p in title.split(sep, 1) if p.strip()]
            result = []
            for p in parts:
                result.extend(_split_title_for_cover(p, max_chars))
            return result
    # 在中英文交界处分割（如 "收购Cursor的" vs "不是买工具"）
    m = re.search(r'([a-zA-Z]+[的了是]?)', title)
    if m and m.end() < len(title):
        prefix = title[:m.end()]
        suffix = title[m.end():]
        if len(prefix) <= max_chars + 4 and len(suffix) <= max_chars + 4:
            return [prefix, suffix]
    # 强制在字数处切，但不切断英文单词
    lines, buf = [], ''
    for ch in title:
        buf += ch
        if len(buf) >= max_chars and not ch.isascii():
            lines.append(buf)
            buf = ''
    if buf:
        lines.append(buf)
    return lines or [title]


def _build_dynamic_inner_params(page_spec: dict, info_text: str, page_number: int) -> dict:
    """从 story_plan 的单页规格构建 SVG 内页渲染参数。"""
    W = 40
    highlight = page_spec.get('highlight', '')
    sections = page_spec.get('sections', [])

    body_sections = []
    for sec in sections:
        label = sec.get('label', '')
        content = sec.get('content', '')
        if label:
            lines = [f'!{label}'] + _wrap_lines(content, W, 2)
        else:
            lines = _wrap_lines(content, W)
        body_sections.append(lines)

    while len(body_sections) < 4:
        body_sections.append([''])

    return {
        'page_title': page_spec.get('title', f'第{page_number}页'),
        'highlight_lines': _wrap_lines(highlight, W - 2, 2),
        'body_sections': body_sections[:4],
        'page_number': page_number,
        'info_text': info_text,
    }


def _build_dynamic_svg_pages(record: dict, analysis: dict, story_plan: dict) -> list:
    """story_plan 驱动的动态页面构建：页数和标题由 AI 决定。"""
    episode = record.get('期号', '???')
    info = f"All In Podcast E{episode} · 中文知识库"

    cover_title = story_plan.get('cover_title_lines') or _split_title_for_cover(
        record.get('中文标题', '未知标题'))
    cover_subtitle = story_plan.get('cover_subtitle_lines', [])
    if not cover_subtitle:
        dim2 = _strip_tags(extract_dim(analysis.get('five_dim', ''), '②'))
        sub_sentences = [s.strip() for s in re.split(r'[。；]', dim2) if s.strip() and len(s.strip()) >= 6]
        cover_subtitle = [s[:18] for s in sub_sentences[:2]]

    pages = [{
        'page_num': 1,
        'title': '封面',
        'mode': 'cover',
        'params': {
            'episode': episode,
            'title_lines': cover_title,
            'subtitle_lines': cover_subtitle,
            'info_text': f"All In Podcast · E{episode}",
        },
    }]

    for idx, page_spec in enumerate(story_plan.get('pages', [])):
        params = _build_dynamic_inner_params(page_spec, info, idx + 2)
        pages.append({
            'page_num': idx + 2,
            'title': page_spec.get('title', f'第{idx + 2}页'),
            'mode': 'inner_svg',
            'params': params,
        })

    return pages


def build_svg_pages(record: dict, analysis: dict) -> list:
    """构建 SVG 渲染参数列表。优先用 story_plan 动态模式，否则回退固定结构。"""
    story_plan = analysis.get('story_plan')
    if story_plan and story_plan.get('pages'):
        return _build_dynamic_svg_pages(record, analysis, story_plan)
    cover_raw = build_cover_params(record, analysis)
    episode = record.get('期号', '???')
    title = record.get('中文标题', '未知标题')
    dim1 = _strip_tags(extract_dim(analysis.get('five_dim', ''), '①'))

    # 封面标题：从中文标题衍生 2-3 行
    title_lines = _split_title_for_cover(title)
    # 副标题：从②核心论点提取关键短句（≤18字/行，最多2行）
    dim2 = _strip_tags(extract_dim(analysis.get('five_dim', ''), '②'))
    sub_sentences = [s.strip() for s in re.split(r'[。；]', dim2) if s.strip() and len(s.strip()) >= 6]
    subtitle_lines = []
    for s in sub_sentences[:2]:
        s = _strip_tags(s)
        if len(s) > 18:
            s = s[:17] + '…'
        subtitle_lines.append(s)
    if not subtitle_lines:
        subtitle_lines = [title[:18]]

    pages = [{
        'page_num': 1,
        'title': '封面',
        'mode': 'cover',
        'params': {
            'episode': episode,
            'title_lines': title_lines,
            'subtitle_lines': subtitle_lines,
            'info_text': f"All In Podcast · E{episode}",
        },
    }]

    titles = ['本期最反直觉的判断', '嘉宾最激烈的分歧', '说回咱们', '完整资料预览']
    for idx in range(4):
        inner_params = build_svg_inner_params(record, analysis, idx)
        pages.append({
            'page_num': idx + 2,
            'title': titles[idx],
            'mode': 'inner_svg',
            'params': inner_params,
        })

    return pages


def build_page_prompts(record: dict, analysis: dict) -> list:
    """生成 1 张 cover + 4 张 inner 的参数（SVG 模式优先，兼容旧 gpt-image-2）。"""
    return build_svg_pages(record, analysis)


def find_codex_companion() -> list[str] | None:
    """Return command prefix for codex-companion, including .mjs fallback."""
    companion = shutil.which('codex-companion')
    if companion:
        print(f"codex-companion 路径：{companion}", file=sys.stderr)
        return [companion]

    root = Path.home() / '.claude/plugins/cache/openai-codex'
    candidates = sorted(root.glob('*/*/scripts/codex-companion.mjs'), key=lambda path: path.parent.parent.name)
    if candidates:
        mjs_path = candidates[-1]
        print(f"codex-companion 路径：{mjs_path}", file=sys.stderr)
        return ['node', str(mjs_path)]

    print("codex-companion 未找到，fallback 到 API", file=sys.stderr)
    return None


def generate_via_codex(prompt: str, page_num: int, output_path: Path) -> bool:
    """用 Codex 子代理生图。成功时图片已写到 output_path。"""
    companion_cmd = find_codex_companion()
    if not companion_cmd:
        return False

    prompt_path = Path(f"/tmp/allin_img_prompt_{page_num}.txt")
    prompt_path.write_text(prompt, encoding='utf-8')
    task = (
        f"读取 {prompt_path} 的提示词，用 gpt-image-2 生成一张 1024x1536 竖版图片，"
        f"将图片保存到 {output_path}。只完成生图和保存，不修改其他文件。"
    )
    try:
        result = subprocess.run(
            [*companion_cmd, 'task', task],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except Exception as exc:
        print(f"  ⚠️  第 {page_num} 张 Codex 失败：{exc}")
        return False
    finally:
        prompt_path.unlink(missing_ok=True)

    if result.returncode != 0:
        msg = (result.stderr or result.stdout or '').strip().splitlines()
        print(f"  ⚠️  第 {page_num} 张 Codex 失败：{msg[-1] if msg else 'unknown error'}")
        return False
    if output_path.exists() and output_path.stat().st_size > MIN_IMAGE_BYTES:
        return True

    print(f"  ⚠️  第 {page_num} 张 Codex 未产出有效图片")
    return False


def generate_image(prompt: str, page_num: int, output_path: Path,
                   api_key: str = None, api_base: str = None,
                   model: str = DEFAULT_MODEL, retry: int = 3) -> bytes | None:
    """Codex 优先，失败后调用图片 API，返回图片字节。
    注意：不传 response_format 参数，兼容 VectorEngine 等中转站。
    默认返回 URL，自动下载；若有 b64_json 则直接解码。
    """
    failures = 0
    prefer_api = os.environ.get('IMAGE_GEN_PREFER_API', '').lower() in {'1', 'true', 'yes', 'on'}

    if not prefer_api:
        if generate_via_codex(prompt, page_num, output_path):
            return output_path.read_bytes()
        failures += 1

    if not api_key:
        print(f"  ❌  第 {page_num} 张放弃：Codex 失败且未配置 API Key")
        return None

    client = OpenAI(api_key=api_key, base_url=api_base or DEFAULT_API_BASE)
    while failures < retry:
        attempt = failures
        try:
            response = client.images.generate(
                model=model,
                prompt=prompt,
                n=1,
                size="1024x1536",        # 3:4 竖版
                timeout=300,
                # 不传 response_format，避免中转站不兼容
            )
            # response 可能是 ImagesResponse 对象或 dict
            if hasattr(response, 'data'):
                items = response.data
            elif isinstance(response, dict):
                items = response.get('data', [])
            else:
                raise ValueError(f"意外的响应类型: {type(response)}")

            item = items[0]
            b64 = getattr(item, 'b64_json', None) or (item.get('b64_json') if isinstance(item, dict) else None)
            url = getattr(item, 'url', None) or (item.get('url') if isinstance(item, dict) else None)

            if b64:
                return base64.b64decode(b64)
            elif url:
                with urllib.request.urlopen(url, timeout=60) as r:
                    return r.read()
            else:
                raise ValueError(f"响应中无 b64_json 也无 url: {item}")
        except Exception as e:
            failures += 1
            wait = 60 if attempt == 0 else 90
            if failures < retry:
                print(f"  ⚠️  第 {page_num} 张失败（{e}），{wait}s 后重试...")
                time.sleep(wait)
            else:
                print(f"  ❌  第 {page_num} 张放弃: {e}")
    return None


def generate_svg_page(page: dict, output_dir: Path, slug: str) -> tuple[int, str, str | None, float]:
    """用 SVG 模板渲染一页（封面或内页）。"""
    start = time.time()
    out = output_dir / f"allin_{slug}_sketch_{page['page_num']:02d}_{page['title']}.png"
    cover_gen = REPO_ROOT / 'scripts' / 'cover-generator' / 'generate.py'
    params = page['params']

    env = dict(os.environ)
    env['DYLD_LIBRARY_PATH'] = '/opt/homebrew/lib'

    try:
        if page['mode'] == 'cover':
            cmd = [sys.executable, str(cover_gen), 'cover', 'allin',
                   '--number', str(params.get('episode', '???')),
                   '-o', str(out)]
            if params.get('title_lines'):
                cmd += ['--title'] + params['title_lines']
            if params.get('subtitle_lines'):
                cmd += ['--subtitle'] + params['subtitle_lines']
            if params.get('info_text'):
                cmd += ['--info', params['info_text']]
            subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)

        elif page['mode'] == 'inner_svg':
            cmd = [sys.executable, str(cover_gen), 'inner', 'allin',
                   '--page-title', params['page_title'],
                   '--page-number', str(params['page_number']),
                   '-o', str(out)]
            cmd += ['--highlight'] + params['highlight_lines']
            if params.get('info_text'):
                cmd += ['--info', params['info_text']]
            for section in params.get('body_sections', []):
                cmd += ['--body'] + section
            subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)

    except subprocess.CalledProcessError as exc:
        print(f"  ❌  第 {page['page_num']} 张 SVG 渲染失败：{exc.stderr or exc.stdout}")
        return page['page_num'], page['title'], None, time.time() - start

    elapsed = time.time() - start
    if out.exists() and out.stat().st_size > MIN_IMAGE_BYTES:
        print(f"       ✅ {out.name} ({out.stat().st_size // 1024} KB)")
        return page['page_num'], page['title'], str(out), elapsed
    return page['page_num'], page['title'], None, elapsed


def generate_one_page(page: dict, total: int, output_dir: Path, slug: str,
                      api_key: str, api_base: str, model: str) -> tuple[int, str, str | None, float]:
    """兼容分发：SVG 模式 or gpt-image-2 模式。"""
    if page.get('mode') in ('cover', 'inner_svg'):
        return generate_svg_page(page, output_dir, slug)

    start = time.time()
    out = output_dir / f"allin_{slug}_sketch_{page['page_num']:02d}_{page['title']}.png"
    img = generate_image(page['prompt'], page['page_num'], out, api_key, api_base, model)
    elapsed = time.time() - start
    if img:
        if not out.exists() or out.read_bytes() != img:
            out.write_bytes(img)
        print(f"       ✅ {out.name} ({out.stat().st_size // 1024} KB)")
        return page['page_num'], page['title'], str(out), elapsed
    return page['page_num'], page['title'], None, elapsed


def main():
    parser = argparse.ArgumentParser(description='生成 All In Podcast 手绘笔记')
    parser.add_argument('--record-id', default=None)
    parser.add_argument('--record-json', default=None,
                        help='离线记录 JSON；传入后跳过 lark-cli 读取')
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
    parser.add_argument('--pages', default=None,
                        help='只生成指定页，1-based逗号分隔，如 1 或 1,4，不指定=全部5张')
    args = parser.parse_args()

    if not args.record_id and not args.record_json:
        parser.error('需要 --record-id 或 --record-json')
    try:
        selected = parse_pages_arg(args.pages)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    config = load_config()

    # 优先级：命令行参数 > 环境变量 > config.json image_api 区块
    img_cfg  = config.get('image_api', {})
    api_key  = args.api_key  or os.environ.get('IMAGE_API_KEY')  or img_cfg.get('key', '')
    api_base = args.api_base or os.environ.get('IMAGE_API_BASE') or img_cfg.get('base_url', '') or DEFAULT_API_BASE
    model    = args.model    or img_cfg.get('model', '')          or DEFAULT_MODEL

    if args.record_json:
        print(f"[离线] 加载记录 JSON {args.record_json}...")
        record = json.loads(Path(args.record_json).read_text(encoding='utf-8'))
    else:
        print(f"[飞书] 读取收件表记录 {args.record_id}...")
        record = get_record(config, args.record_id)
    episode = record.get('期号') or args.record_id or Path(args.record_json).stem
    print(f"       {episode} · {record.get('中文标题','')}")

    analysis = {}
    analysis_key = args.record_id or Path(args.record_json).stem
    ap = args.analysis or f"/tmp/allin_{analysis_key}_analysis.json"
    if Path(ap).exists():
        analysis = json.loads(Path(ap).read_text(encoding='utf-8'))
        print(f"[分析] 加载: {ap}")
    elif args.prompts_only:
        # --prompts-only 模式允许没有 analysis.json，用占位符预览提示词
        print(f"[分析] 未找到 {ap}，将用占位内容（--prompts-only 模式）")
    else:
        print(f"❌  未找到分析文件: {ap}")
        print(f"   手绘笔记需要五维分析和金句才能生成有意义的内容。")
        print(f"   请先完成 AI 分析步骤（SKILL.md Step 4-6），生成 analysis.json 后再运行。")
        print(f"   若只想预览提示词，可加 --prompts-only 参数。")
        sys.exit(1)

    pages = build_page_prompts(record, analysis)
    if selected:
        pages = [p for p in pages if p['page_num'] in selected]
        if not pages:
            sys.exit(f"❌  --pages 未匹配任何页面: {args.pages}")
        print(f"[过滤] 只生指定页: {', '.join(str(p['page_num']) for p in pages)}")
    print(f"[规划] 共 {len(pages)} 张：{', '.join(p['title'] for p in pages)}")

    if args.prompts_only:
        print("\n" + "="*60)
        for p in pages:
            print(f"\n── 第 {p['page_num']} 张：{p['title']} ──\n{p['prompt']}")
        return

    prefer_api = os.environ.get('IMAGE_GEN_PREFER_API', '').lower() in {'1', 'true', 'yes', 'on'}
    print(f"[生图] Codex优先={'否' if prefer_api else '是'}  API={api_base}  model={model}")
    if not api_key:
        print("[生图] 未配置 API Key；Codex 失败时无法 fallback 到 API")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = episode.replace(' ', '_')
    generated_by_page = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(generate_one_page, p, len(pages), output_dir, slug, api_key, api_base, model): p
            for p in pages
        }
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            page = futures[future]
            completed += 1
            try:
                page_num, title, result, elapsed = future.result()
            except Exception as exc:
                page_num, title, result, elapsed = page['page_num'], page['title'], None, 0.0
                print(f"  ❌  第 {page_num} 张异常: {exc}")
            print(f"[完成] {completed}/{len(pages)} — {title} (耗时 {elapsed:.0f}s)")
            if not result:
                print(f"       ❌ 第 {page_num} 张失败")
                result = None
            if result:
                generated_by_page[page_num] = result

    generated = [generated_by_page[p['page_num']] for p in pages if p['page_num'] in generated_by_page]

    print(f"\n✅ 完成！{len(generated)}/{len(pages)} 张 → {output_dir}")
    for f in generated:
        print(f"   {Path(f).name}")


if __name__ == '__main__':
    main()
