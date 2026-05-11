#!/usr/bin/env python3
"""
封面生成脚本 — 输入标题+期号，输出 1080×1350 PNG。

用法：
  python generate.py allin \
    --title "你花钱订阅的" "SaaS 可能" "正在等死" \
    --subtitle "按席位收费的时代" "可能真的要变了" \
    --info "All In Podcast · E270" \
    --number 270 \
    -o cover_allin.png

  python generate.py breakdown \
    --title "9块9的备课资料" "卖的不是" "PPT" \
    --subtitle "买家花的不是9块9买50页PPT" "是省掉3小时备课时间" \
    --info "教师备课资料包 · 9.9元 · 4000+单" \
    --number 012 \
    -o cover_breakdown.png

标题最后一行自动使用强调色高亮。
"""
import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SVG_NS = "http://www.w3.org/2000/svg"
TAG_TEXT = f"{{{SVG_NS}}}text"
TAG_TSPAN = f"{{{SVG_NS}}}tspan"

TEMPLATES = {
    "breakdown": {
        "svg": os.path.join(SCRIPT_DIR, "breakdown.svg"),
        "brand": "虚拟产品实操手记",
        "footer_prefix": "BREAKDOWN · NO.",
    },
    "allin": {
        "svg": os.path.join(SCRIPT_DIR, "allin.svg"),
        "brand": "ALL IN PODCAST",
        "footer_prefix": "ALL IN · VOL.",
    },
}

INNER_TEMPLATES = {
    "allin": {
        "svg": os.path.join(SCRIPT_DIR, "allin_inner_v2.svg"),
    },
    "allin_dark": {
        "svg": os.path.join(SCRIPT_DIR, "allin_inner_dark.svg"),
    },
}

COVER_TEMPLATES = {
    "allin": {
        "svg": os.path.join(SCRIPT_DIR, "allin_cover_v2.svg"),
        "brand": "ALL IN PODCAST",
        "footer_prefix": "ALL IN · VOL.",
    },
}


def _find_by_id(root, element_id):
    """按 id 查找 SVG 元素（优先路径）。"""
    for elem in root.iter():
        if elem.get("id") == element_id:
            return elem
    return None


def _find_text_by_content(root, keyword):
    """按文本内容查找 <text> 元素（fallback 路径）。"""
    for elem in root.iter(TAG_TEXT):
        if elem.text and keyword in elem.text:
            return elem
        for child in elem:
            if child.text and keyword in child.text:
                return elem
    return None


def _find_title_by_style(root):
    """按 font-weight=900 + 多 tspan 查找标题（兜底路径）。"""
    for text_el in root.iter(TAG_TEXT):
        if text_el.get("font-weight") == "900":
            tspans = list(text_el.iter(TAG_TSPAN))
            if len(tspans) >= 2:
                return text_el
    return None


def _find_subtitle_by_style(root):
    """按 opacity<1 + font-size + tspan 查找副标题（兜底路径）。"""
    for text_el in root.iter(TAG_TEXT):
        op = text_el.get("opacity", "")
        if op:
            try:
                if float(op) < 1.0 and text_el.get("font-size"):
                    tspans = list(text_el.iter(TAG_TSPAN))
                    if tspans:
                        return text_el
            except ValueError:
                pass
    return None


def _replace_title(title_elem, title_lines):
    """替换主标题 tspan，最后一行自动用强调色。"""
    old_tspans = list(title_elem.iter(TAG_TSPAN))
    if not old_tspans:
        return

    first_attribs = dict(old_tspans[0].attrib)
    accent_color = None
    if old_tspans:
        last = old_tspans[-1]
        if last.get("fill") and last.get("fill") != title_elem.get("fill"):
            accent_color = last.get("fill")

    font_size = first_attribs.get("font-size", "128")
    x_val = first_attribs.get("x", "80")
    line_dy = "160"
    if len(old_tspans) >= 2:
        d = old_tspans[1].get("dy", "160")
        if d != "0":
            line_dy = d

    for ts in old_tspans:
        title_elem.remove(ts)
    title_elem.text = None

    for i, line in enumerate(title_lines):
        ts = ET.SubElement(title_elem, TAG_TSPAN)
        ts.set("font-size", font_size)
        ts.set("x", x_val)
        ts.set("dy", "0" if i == 0 else line_dy)
        if i == len(title_lines) - 1 and accent_color:
            ts.set("fill", accent_color)
        ts.text = line


def _replace_subtitle(subtitle_elem, subtitle_lines):
    """替换副标题 tspan。"""
    old_tspans = list(subtitle_elem.iter(TAG_TSPAN))
    first_attribs = dict(old_tspans[0].attrib) if old_tspans else {}
    x_val = first_attribs.get("x", "80")
    line_dy = "72"
    if len(old_tspans) >= 2:
        d = old_tspans[1].get("dy", "72")
        if d != "0":
            line_dy = d

    for ts in old_tspans:
        subtitle_elem.remove(ts)
    subtitle_elem.text = None

    for i, line in enumerate(subtitle_lines):
        ts = ET.SubElement(subtitle_elem, TAG_TSPAN)
        ts.set("x", x_val)
        ts.set("dy", "0" if i == 0 else line_dy)
        ts.text = line


def _replace_body(body_elem, lines):
    """替换正文段落 tspan，保留首行样式。"""
    old_tspans = list(body_elem.iter(TAG_TSPAN))
    if not old_tspans:
        return

    first_attribs = dict(old_tspans[0].attrib)
    x_val = first_attribs.get("x", "80")
    line_dy = "50"
    if len(old_tspans) >= 2:
        d = old_tspans[1].get("dy", "50")
        if d != "0":
            line_dy = d

    # 检测是否有特殊样式行（如加粗首行、红色引用行）
    special_lines = {}
    for ts in old_tspans:
        if ts.get("font-weight") and ts.get("font-weight") != body_elem.get("font-weight", ""):
            special_lines["bold"] = {
                "font-weight": ts.get("font-weight"),
                "fill": ts.get("fill", ""),
                "font-size": ts.get("font-size", ""),
            }
        if ts.get("fill") and ts.get("fill") != body_elem.get("fill", "#333333"):
            if "accent" not in special_lines:
                special_lines["accent"] = ts.get("fill")

    for ts in old_tspans:
        body_elem.remove(ts)
    body_elem.text = None

    base_font_size = first_attribs.get("font-size", "32")

    for i, line in enumerate(lines):
        ts = ET.SubElement(body_elem, TAG_TSPAN)
        ts.set("font-size", base_font_size)
        ts.set("x", x_val)
        ts.set("dy", "0" if i == 0 else line_dy)

        if line.startswith("!"):
            line = line[1:]
            ts.set("font-weight", "700")
            ts.set("fill", "#1A1A1A")
        elif line.startswith(">"):
            line = line[1:]
            accent = special_lines.get("accent", "#C0392B")
            ts.set("fill", accent)
            ts.set("font-size", str(int(base_font_size) + 4) if base_font_size.isdigit() else base_font_size)
        ts.text = line


def generate_inner_page(template_name, page_title, highlight_lines,
                        body_sections, page_number, info_text,
                        output_path):
    """生成内页 PNG。

    Args:
        template_name: 模板类型（如 "allin"）
        page_title: 页面标题
        highlight_lines: 红色核心金句行列表
        body_sections: 正文段落列表，每个元素是一个行列表
                       行首 "!" 表示加粗，">" 表示红色强调
        page_number: 页码
        info_text: 底部信息文本
        output_path: 输出路径
    """
    cfg = INNER_TEMPLATES[template_name]

    with open(cfg["svg"], "r", encoding="utf-8") as f:
        svg_content = f.read()

    ET.register_namespace("", SVG_NS)
    root = ET.fromstring(svg_content)

    # 替换页面标题
    title_el = _find_by_id(root, "page-title")
    if title_el is not None:
        title_el.text = page_title

    # 替换核心金句
    quote_el = _find_by_id(root, "highlight-quote")
    if quote_el is not None and highlight_lines:
        old_tspans = list(quote_el.iter(TAG_TSPAN))
        first_attribs = dict(old_tspans[0].attrib) if old_tspans else {}
        x_val = first_attribs.get("x", "80")
        font_size = first_attribs.get("font-size", "38")
        line_dy = "54"
        if len(old_tspans) >= 2:
            d = old_tspans[1].get("dy", "54")
            if d != "0":
                line_dy = d

        for ts in old_tspans:
            quote_el.remove(ts)
        quote_el.text = None

        for i, line in enumerate(highlight_lines):
            ts = ET.SubElement(quote_el, TAG_TSPAN)
            ts.set("font-size", font_size)
            ts.set("x", x_val)
            ts.set("dy", "0" if i == 0 else line_dy)
            ts.text = line

    # 替换正文段落 body-1 到 body-N
    for idx, section_lines in enumerate(body_sections):
        body_el = _find_by_id(root, f"body-{idx + 1}")
        if body_el is not None:
            _replace_body(body_el, section_lines)

    # 替换底部信息
    if info_text:
        fl = _find_by_id(root, "footer-left")
        if fl is not None:
            fl.text = info_text

    # 替换页码
    fr = _find_by_id(root, "footer-right")
    if fr is not None:
        fr.text = str(page_number)

    # 输出 PNG
    final_svg = ET.tostring(root, encoding="unicode", xml_declaration=False)
    if 'xmlns="http://www.w3.org/2000/svg"' not in final_svg:
        final_svg = final_svg.replace("<svg ", f'<svg xmlns="{SVG_NS}" ', 1)

    try:
        import cairosvg
    except ImportError:
        print("错误：需要 cairosvg，运行 pip install cairosvg")
        raise SystemExit(1)

    scale = 2
    cairosvg.svg2png(
        bytestring=final_svg.encode("utf-8"),
        write_to=output_path,
        output_width=1080 * scale,
        output_height=1350 * scale,
    )
    print(f"内页已生成：{output_path}")


def generate_cover(template_name, title_lines, subtitle_lines, info_text,
                   number, output_path, brand_override=None,
                   image_path=None):
    """生成封面 PNG。"""
    cfg = COVER_TEMPLATES.get(template_name) or TEMPLATES[template_name]

    with open(cfg["svg"], "r", encoding="utf-8") as f:
        svg_content = f.read()

    ET.register_namespace("", SVG_NS)
    root = ET.fromstring(svg_content)

    # --- 替换期号水印（ID → 样式 fallback） ---
    watermark = _find_by_id(root, "episode-watermark")
    if watermark is None:
        for t in root.iter(TAG_TEXT):
            fs = t.get("font-size", "")
            if fs and int(fs) >= 400:
                watermark = t
                break
    if watermark is not None:
        watermark.text = str(number)

    # --- 替换主标题（ID → 样式 fallback） ---
    title_elem = _find_by_id(root, "main-title")
    if title_elem is None:
        title_elem = _find_title_by_style(root)
    if title_elem is not None and title_lines:
        _replace_title(title_elem, title_lines)

    # --- 替换副标题（ID → 样式 fallback） ---
    if subtitle_lines:
        sub_elem = _find_by_id(root, "subtitle")
        if sub_elem is None:
            sub_elem = _find_subtitle_by_style(root)
        if sub_elem is not None:
            _replace_subtitle(sub_elem, subtitle_lines)

    # --- 替换底部左角标（ID → 内容 fallback） ---
    footer_text = f"{cfg['footer_prefix']}{number}"
    fl = _find_by_id(root, "footer-left")
    if fl is None:
        fl = _find_text_by_content(root, cfg["footer_prefix"])
    if fl is not None:
        fl.text = footer_text

    # --- 替换底部右归属（ID → 内容 fallback） ---
    if info_text:
        fr = _find_by_id(root, "footer-right")
        if fr is None:
            fr = _find_text_by_content(root, "Podcast")
        if fr is not None:
            fr.text = info_text

    # --- 替换品牌名 ---
    if brand_override:
        sl = _find_by_id(root, "series-label")
        if sl is not None:
            sl.text = brand_override

    # --- 嵌入配图（base64 data URI） ---
    if image_path:
        img_el = _find_by_id(root, "cover-image")
        if img_el is not None and os.path.isfile(image_path):
            import base64
            import mimetypes
            mime, _ = mimetypes.guess_type(image_path)
            if not mime:
                mime = "image/png"
            with open(image_path, "rb") as img_f:
                b64 = base64.b64encode(img_f.read()).decode("ascii")
            xlink_ns = "http://www.w3.org/1999/xlink"
            img_el.set(f"{{{xlink_ns}}}href", f"data:{mime};base64,{b64}")
            img_el.set("href", f"data:{mime};base64,{b64}")

    # 输出 SVG
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    final_svg = ET.tostring(root, encoding="unicode", xml_declaration=False)
    if 'xmlns="http://www.w3.org/2000/svg"' not in final_svg:
        final_svg = final_svg.replace("<svg ", f'<svg xmlns="{SVG_NS}" ', 1)

    try:
        import cairosvg
    except ImportError:
        print("错误：需要 cairosvg，运行 pip install cairosvg")
        raise SystemExit(1)

    scale = 2
    cairosvg.svg2png(
        bytestring=final_svg.encode("utf-8"),
        write_to=output_path,
        output_width=1080 * scale,
        output_height=1350 * scale,
    )
    print(f"封面已生成：{output_path}")


def main():
    parser = argparse.ArgumentParser(description="生成小红书封面/内页 PNG")
    sub = parser.add_subparsers(dest="command", help="子命令")

    # 封面子命令
    cover_p = sub.add_parser("cover", help="生成封面")
    cover_p.add_argument("template", choices=["breakdown", "allin"])
    cover_p.add_argument("--title", nargs="+", required=True,
                         help="标题行（最后一行自动高亮）")
    cover_p.add_argument("--subtitle", nargs="+", default=None)
    cover_p.add_argument("--info", default=None)
    cover_p.add_argument("--number", required=True)
    cover_p.add_argument("--brand", default=None)
    cover_p.add_argument("--image", default=None,
                         help="右下角配图路径（JPG/PNG）")
    cover_p.add_argument("-o", "--output", default=None)

    # 内页子命令
    inner_p = sub.add_parser("inner", help="生成内页")
    inner_p.add_argument("template", choices=["allin"])
    inner_p.add_argument("--page-title", required=True)
    inner_p.add_argument("--highlight", nargs="+", required=True,
                         help="红色核心金句行")
    inner_p.add_argument("--body", action="append", nargs="+",
                         help="正文段落（可多次指定，每次一个段落的多行）")
    inner_p.add_argument("--page-number", type=int, default=2)
    inner_p.add_argument("--info", default=None)
    inner_p.add_argument("-o", "--output", default=None)

    # 兼容旧用法：直接 `generate.py allin --title ...`
    args = parser.parse_args()

    if args.command == "inner":
        output = args.output or f"inner_{args.template}_p{args.page_number}.png"
        # CLI 模式下 `|` 分隔符展开为多行（方便手动测试）
        body = []
        for section in (args.body or []):
            expanded = []
            for item in section:
                expanded.extend(item.split('|'))
            body.append(expanded)
        generate_inner_page(
            template_name=args.template,
            page_title=args.page_title,
            highlight_lines=args.highlight,
            body_sections=body,
            page_number=args.page_number,
            info_text=args.info,
            output_path=output,
        )
    elif args.command == "cover":
        output = args.output or f"cover_{args.template}.png"
        generate_cover(
            template_name=args.template,
            title_lines=args.title,
            subtitle_lines=args.subtitle,
            info_text=args.info,
            number=args.number,
            output_path=output,
            brand_override=args.brand,
            image_path=args.image,
        )
    else:
        # 兼容旧用法: generate.py allin --title ...
        if len(sys.argv) > 1 and sys.argv[1] in TEMPLATES:
            old_p = argparse.ArgumentParser()
            old_p.add_argument("template", choices=list(TEMPLATES.keys()))
            old_p.add_argument("--title", nargs="+", required=True)
            old_p.add_argument("--subtitle", nargs="+", default=None)
            old_p.add_argument("--info", default=None)
            old_p.add_argument("--number", required=True)
            old_p.add_argument("--brand", default=None)
            old_p.add_argument("-o", "--output", default=None)
            old_args = old_p.parse_args()
            output = old_args.output or f"cover_{old_args.template}.png"
            generate_cover(
                template_name=old_args.template,
                title_lines=old_args.title,
                subtitle_lines=old_args.subtitle,
                info_text=old_args.info,
                number=old_args.number,
                output_path=output,
                brand_override=old_args.brand,
            )
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
