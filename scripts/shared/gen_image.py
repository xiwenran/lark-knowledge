#!/usr/bin/env python3
"""
gen_image.py — 通用图片生成 CLI 工具（仅 API 调用，不含业务逻辑）

从 config.json 读取 image_api 配置，调用 OpenAI 兼容接口生成图片。
供各 Skill 和脚本复用。

用法：
  python3 gen_image.py --prompt "手绘风格..." --output /tmp/sketch.png
  python3 gen_image.py --prompt "..." --output /tmp/sketch.png --size 1024x1536
"""

import json
import os
import sys
import base64
import argparse
import time
import urllib.request
from pathlib import Path
from openai import OpenAI

# 复用项目统一的配置路径（与 scripts/allin/utils.py 一致）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "allin"))
try:
    from utils import load_config as _load_project_config
except ImportError:
    _load_project_config = None

CONFIG_PATH = Path.home() / ".agents/skills/lark-knowledge-config/config.json"


def load_image_config() -> dict:
    """从 config.json 读取 image_api 区块（优先走项目统一 load_config）"""
    if _load_project_config:
        cfg = _load_project_config()
    else:
        cfg = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    img = cfg.get('image_api', {})
    return {
        'key': img.get('key') or os.environ.get('IMAGE_API_KEY', ''),
        'base_url': img.get('base_url') or os.environ.get('IMAGE_API_BASE', ''),
        'model': img.get('model') or 'gpt-image-2',
    }


def generate(prompt: str, output: str, size: str = "1024x1536",
             retry: int = 3) -> bool:
    """调用图片 API，保存到 output 路径，返回是否成功"""
    cfg = load_image_config()
    if not cfg['key']:
        print("error: 缺少图片 API Key（config.json image_api.key 或 IMAGE_API_KEY 环境变量）")
        return False

    client = OpenAI(api_key=cfg['key'], base_url=cfg['base_url'])

    for attempt in range(retry):
        try:
            resp = client.images.generate(
                model=cfg['model'], prompt=prompt, n=1, size=size
            )
            items = resp.data if hasattr(resp, 'data') else resp.get('data', [])
            item = items[0]

            b64 = getattr(item, 'b64_json', None) or (
                item.get('b64_json') if isinstance(item, dict) else None)
            url = getattr(item, 'url', None) or (
                item.get('url') if isinstance(item, dict) else None)

            if b64:
                img_bytes = base64.b64decode(b64)
            elif url:
                with urllib.request.urlopen(url, timeout=60) as r:
                    img_bytes = r.read()
            else:
                raise ValueError(f"响应中无 b64_json 也无 url")

            Path(output).write_bytes(img_bytes)
            print(f"ok: {output} ({len(img_bytes) // 1024} KB)")
            return True

        except Exception as e:
            if attempt < retry - 1:
                wait = 30 * (attempt + 1)
                print(f"retry: 第 {attempt+1} 次失败（{e}），{wait}s 后重试...")
                time.sleep(wait)
            else:
                print(f"error: 放弃（{e}）")
    return False


def main():
    p = argparse.ArgumentParser(description='调用图片 API 生成图片')
    p.add_argument('--prompt', required=True, help='图片生成提示词')
    p.add_argument('--output', required=True, help='输出文件路径')
    p.add_argument('--size', default='1024x1536', help='图片尺寸（默认竖版 1024x1536）')
    args = p.parse_args()
    ok = generate(args.prompt, args.output, args.size)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
