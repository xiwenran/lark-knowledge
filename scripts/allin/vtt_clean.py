#!/usr/bin/env python3
"""
vtt_clean.py — YouTube VTT 字幕清洗工具
输入：YouTube 自动生成的 .vtt 文件
输出：JSON 文件，按时间分段的干净文本

YouTube VTT 特点：
- 每行带内联时间码 <00:00:01.040><c>word</c>
- 每句话在多个 block 中重复出现（滚动字幕）
- >> 表示说话人切换
- &gt;&gt; 是 >> 的 HTML 实体

用法：python3 vtt_clean.py input.vtt output.json [--segment-minutes 15]
"""

import re
import json
import sys
import argparse
from pathlib import Path


def parse_timestamp(ts: str) -> float:
    """把 HH:MM:SS.mmm 转成秒数"""
    parts = ts.strip().split(":")
    h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
    return h * 3600 + m * 60 + s


def format_timestamp(seconds: float) -> str:
    """秒数转 HH:MM:SS"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def strip_vtt_markup(text: str) -> str:
    """去掉 VTT 内联时间码和 HTML 标签"""
    # 去掉内联时间码 <00:00:01.040>
    text = re.sub(r'<\d{2}:\d{2}:\d{2}\.\d{3}>', '', text)
    # 去掉 <c> 和 </c> 标签
    text = re.sub(r'</?c>', '', text)
    # 其他 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    # HTML 实体
    text = text.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&').replace('&nbsp;', ' ')
    # 清理多余空格
    text = re.sub(r' +', ' ', text).strip()
    return text


def parse_vtt(vtt_path: str) -> list[dict]:
    """
    解析 VTT 文件，返回去重后的句子列表
    每条：{time_start: float, time_end: float, text: str, speaker_change: bool}
    """
    content = Path(vtt_path).read_text(encoding='utf-8')
    lines = content.splitlines()

    blocks = []
    i = 0

    # 跳过 WEBVTT 头部
    while i < len(lines) and not re.match(r'\d{2}:\d{2}:\d{2}', lines[i]):
        i += 1

    while i < len(lines):
        line = lines[i].strip()

        # 时间戳行
        ts_match = re.match(
            r'(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})',
            line
        )
        if ts_match:
            t_start = parse_timestamp(ts_match.group(1))
            t_end = parse_timestamp(ts_match.group(2))

            # 收集该 block 的文本行
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip() != '' and not re.match(r'\d{2}:\d{2}:\d{2}', lines[i]):
                text_lines.append(lines[i].strip())
                i += 1

            # 取第一行（上一句完成版），去掉内联标记
            if text_lines:
                clean = strip_vtt_markup(text_lines[0])
                if clean:
                    blocks.append({
                        'time_start': t_start,
                        'time_end': t_end,
                        'text': clean
                    })
        else:
            i += 1

    # 去重：相邻相同文本只保留第一次出现
    deduped = []
    seen = None
    for block in blocks:
        text = block['text']
        if text != seen:
            seen = text
            deduped.append(block)

    # 识别说话人切换（>> 开头）
    for block in deduped:
        if block['text'].startswith('>>'):
            block['speaker_change'] = True
            block['text'] = block['text'].lstrip('> ').strip()
        else:
            block['speaker_change'] = False

    return deduped


def merge_into_sentences(blocks: list[dict]) -> list[dict]:
    """
    把细碎的 block 合并成完整句子
    遇到说话人切换或标点句尾时断开
    """
    sentences = []
    current_text = []
    current_start = None
    current_end = None
    current_speaker_change = False

    for block in blocks:
        text = block['text']

        if current_start is None:
            current_start = block['time_start']
            current_speaker_change = block['speaker_change']

        # 说话人切换：保存当前句，开新句
        if block['speaker_change'] and current_text:
            sentences.append({
                'time_start': current_start,
                'time_end': current_end,
                'text': ' '.join(current_text),
                'speaker_change': current_speaker_change
            })
            current_text = []
            current_start = block['time_start']
            current_speaker_change = True

        current_text.append(text)
        current_end = block['time_end']

        # 句子结尾标点时断开（但不在说话人切换处，已处理）
        if re.search(r'[.!?]\s*$', text) and len(current_text) >= 3:
            sentences.append({
                'time_start': current_start,
                'time_end': current_end,
                'text': ' '.join(current_text),
                'speaker_change': current_speaker_change
            })
            current_text = []
            current_start = None
            current_speaker_change = False

    # 剩余
    if current_text:
        sentences.append({
            'time_start': current_start,
            'time_end': current_end,
            'text': ' '.join(current_text),
            'speaker_change': current_speaker_change
        })

    return sentences


def group_into_segments(sentences: list[dict], segment_minutes: int = 15) -> list[dict]:
    """按时间分段，每段约 segment_minutes 分钟"""
    segment_seconds = segment_minutes * 60
    segments = []
    current_sentences = []
    seg_start = None

    for sent in sentences:
        if seg_start is None:
            seg_start = sent['time_start']

        current_sentences.append(sent)

        # 到达分段时间且是句子结尾时切割
        if sent['time_end'] - seg_start >= segment_seconds:
            seg_end = sent['time_end']
            segments.append({
                'index': len(segments),
                'time_start': seg_start,
                'time_end': seg_end,
                'time_label': f"{format_timestamp(seg_start)}–{format_timestamp(seg_end)}",
                'sentences': current_sentences
            })
            current_sentences = []
            seg_start = None

    # 剩余句子
    if current_sentences:
        seg_end = current_sentences[-1]['time_end']
        segments.append({
            'index': len(segments),
            'time_start': seg_start or 0,
            'time_end': seg_end,
            'time_label': f"{format_timestamp(seg_start or 0)}–{format_timestamp(seg_end)}",
            'sentences': current_sentences
        })

    return segments


def main():
    parser = argparse.ArgumentParser(description='清洗 YouTube VTT 字幕文件')
    parser.add_argument('input', help='输入 .vtt 文件路径')
    parser.add_argument('output', help='输出 .json 文件路径')
    parser.add_argument('--segment-minutes', type=int, default=15,
                        help='每段时长（分钟），默认 15')
    args = parser.parse_args()

    print(f"[1/3] 解析 VTT: {args.input}")
    blocks = parse_vtt(args.input)
    print(f"      去重后 {len(blocks)} 个 block")

    print("[2/3] 合并成句子...")
    sentences = merge_into_sentences(blocks)
    print(f"      共 {len(sentences)} 句")

    print(f"[3/3] 按 {args.segment_minutes} 分钟分段...")
    segments = group_into_segments(sentences, args.segment_minutes)
    print(f"      共 {len(segments)} 段")

    for seg in segments:
        word_count = sum(len(s['text'].split()) for s in seg['sentences'])
        print(f"      段 {seg['index']}: {seg['time_label']} — {len(seg['sentences'])} 句, {word_count} 词")

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 输出: {args.output}")


if __name__ == '__main__':
    main()
