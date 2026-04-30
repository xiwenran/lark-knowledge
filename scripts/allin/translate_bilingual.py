#!/usr/bin/env python3
"""
translate_bilingual.py — 调用火山引擎 Doubao API 翻译 All In Podcast 逐字稿
输入：vtt_clean.py 输出的 segments.json
输出：bilingual.json（每句含 EN 原文 + CN 译文）

用法：
  export ARK_API_KEY=your_key_here
  python3 translate_bilingual.py segments.json bilingual.json

API 配置（兼容 OpenAI 协议）：
  Base URL: https://ark.cn-beijing.volces.com/api/coding/v3
  Model:    doubao-seed-2.0-pro
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path
from openai import OpenAI

# ── 配置 ──────────────────────────────────────────────
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/coding/v3"
ARK_MODEL = "doubao-seed-2.0-pro"

SYSTEM_PROMPT = """你是 All In Podcast 的专业中文翻译，负责将英文对话稿翻译成自然流畅的中文。

All In Podcast 是一档硅谷顶级投资人对谈节目，四位主播是：
- Jason Calacanis（Jason）：连续创业者，天使投资人，语气活跃直接
- Chamath Palihapitiya（Chamath）：前 Facebook VP，Social Capital 创始人，思路犀利
- David Sacks（Sacks）：Craft Ventures 创始人，前 PayPal COO，逻辑严密
- David Friedberg（Friedberg）：The Production Board 创始人，科学背景，专注数据

翻译原则：
1. 保持口语感，像真人在说话，不要文绉绉
2. 公司名、产品名保留英文（如 Salesforce、Cursor、SpaceX），括号内加中文
3. 金融/科技专业术语准确（free cash flow = 自由现金流，NRR = 净收入留存率）
4. 说话人归属（>> 开头的行表示说话人切换）尽量从上下文判断是哪位主播
5. 数字保留英文原始格式（$140B 不要改成"1400亿"）

输出格式（严格按此格式）：
每个说话单元输出两行：
第一行：> [说话人或 >>]: 英文原文
第二行：**[说话人]**：中文翻译

如果无法判断说话人：
第一行：> >>: 英文原文
第二行：**主播**：中文翻译

示例：
> Jason: You're absolutely right, that's the key insight here.
**Jason**：你说得完全对，这就是核心洞察。

> >>: And having free cash flow in a war chest gives massive optionality.
**Chamath**：手握大量自由现金流本身就是巨大的选择权。"""


def translate_segment(client: OpenAI, segment: dict, retry: int = 3) -> dict:
    """翻译单个分段，返回含双语句子的分段"""

    # 检查 sentences 字段（断点续传时已翻译段为 None）
    sentences = segment.get('sentences')
    if not sentences:
        return segment  # 已翻译，直接返回

    # 准备发给模型的文本
    lines = []
    for sent in sentences:
        prefix = ">> " if sent['speaker_change'] else ""
        lines.append(f"{prefix}{sent['text']}")

    batch_text = "\n".join(lines)

    prompt = f"""请翻译以下 All In Podcast 对话片段（时间范围：{segment['time_label']}）。

原文：
{batch_text}

按照系统提示的格式输出每句话的 EN 原文和 CN 翻译。"""

    for attempt in range(retry):
        try:
            resp = client.chat.completions.create(
                model=ARK_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # 翻译任务低温度，保持一致性
                max_tokens=8192   # 从 4096 升到 8192，防止 15 分钟长段输出被截断
            )
            choice = resp.choices[0]
            # 检查是否因 token 耗尽被截断
            if getattr(choice, 'finish_reason', None) == 'length':
                print(f"  ⚠️  段 {segment['index']} 输出被 token 上限截断（finish_reason=length），"
                      f"末尾内容可能丢失！建议缩小 --segment-minutes 到 10")
            translated_text = choice.message.content.strip()
            return {
                **segment,
                'translated': translated_text,
                'sentences': None  # 翻译后不再需要原始句子结构
            }
        except Exception as e:
            if attempt < retry - 1:
                print(f"  ⚠️  段 {segment['index']} 翻译失败（{e}），{2 ** attempt}s 后重试...")
                time.sleep(2 ** attempt)
            else:
                print(f"  ❌  段 {segment['index']} 翻译失败，已放弃: {e}")
                return {
                    **segment,
                    'translated': f"[翻译失败: {e}]",
                    'sentences': None
                }


def main():
    parser = argparse.ArgumentParser(description='用 Doubao API 翻译 All In Podcast 逐字稿')
    parser.add_argument('input', help='segments.json（vtt_clean.py 的输出）')
    parser.add_argument('output', help='输出 bilingual.json 路径')
    parser.add_argument('--start-from', type=int, default=0,
                        help='从第几段开始翻译（断点续传）')
    args = parser.parse_args()

    api_key = os.environ.get('ARK_API_KEY')
    if not api_key:
        # 尝试从 config.json 读取
        try:
            config_path = Path.home() / '.agents/skills/lark-knowledge-config/config.json'
            cfg = json.loads(config_path.read_text(encoding='utf-8'))
            api_key = cfg.get('ark_api_key') or cfg.get('ARK_API_KEY')
        except Exception:
            pass
    if not api_key:
        print("❌ 缺少 ARK_API_KEY")
        print("   方式一：export ARK_API_KEY=your_key_here")
        print("   方式二：在 config.json 中添加 \"ark_api_key\": \"your_key_here\"")
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=ARK_BASE_URL)

    print(f"[加载] 读取 {args.input}")
    segments = json.loads(Path(args.input).read_text(encoding='utf-8'))
    print(f"       共 {len(segments)} 段")

    # 断点续传：如果输出文件已存在，加载已翻译的段
    results = []
    if args.start_from > 0 and Path(args.output).exists():
        existing = json.loads(Path(args.output).read_text(encoding='utf-8'))
        if len(existing) < args.start_from:
            print(f"  ⚠️  警告：已有 {len(existing)} 段，但 --start-from={args.start_from}")
            print(f"       调整为从第 {len(existing)} 段继续，避免数据空洞")
            args.start_from = len(existing)
        results = existing[:args.start_from]
        print(f"[续传] 已加载前 {len(results)} 段")

    for i, segment in enumerate(segments):
        if i < args.start_from:
            continue

        print(f"[{i+1}/{len(segments)}] 翻译 {segment['time_label']} ...")
        result = translate_segment(client, segment)
        results.append(result)

        # 每段完成后立即保存（防止中断丢失）
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"       ✅ 已保存（{len(result.get('translated', ''))} 字符）")

        # 避免 API 限流
        if i < len(segments) - 1:
            time.sleep(0.5)

    print(f"\n✅ 全部完成，输出: {args.output}")
    print(f"   共 {len(results)} 段已翻译")


if __name__ == '__main__':
    main()
