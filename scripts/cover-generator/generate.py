#!/usr/bin/env python3
"""
封面生成脚本 — 输入标题+期号，输出 1080×1350 PNG。

用法：
  # 商品拆解封面
  python generate.py breakdown \
    --title "9块9的备课资料" "卖的不是" "PPT" \
    --subtitle "买家花的不是9块9买50页PPT" "是省掉3小时备课时间" \
    --info "教师备课资料包 · 9.9元 · 4000+单" \
    --number 012 \
    -o cover_breakdown.png

  # All In Podcast 封面
  python generate.py allin \
    --title "你花钱订阅的" "SaaS 可能" "正在等死" \
    --subtitle "当AI可以直接给你结果" "工具还值钱吗？" \
    --info "All In Podcast · E270" \
    --number 270 \
    -o cover_allin.png

标题最后一行自动使用强调色高亮。
"""
import argparse
import os
import re
import xml.etree.ElementTree as ET

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

TEMPLATES = {
    "breakdown": {
        "svg": os.path.join(SCRIPT_DIR, "breakdown.svg"),
        "brand": "虚拟产品实操手记",
        "footer_prefix": "BREAKDOWN · NO.",
        "accent_attr": "fill",  # 用于检测强调色
    },
    "allin": {
        "svg": os.path.join(SCRIPT_DIR, "allin.svg"),
        "brand": "ALL IN PODCAST",
        "footer_prefix": "ALL IN · VOL.",
        "accent_attr": "fill",
    },
}

NS = {"svg": "http://www.w3.org/2000/svg"}


def _find_text_by_content(root, keyword):
    """在 SVG 中找包含特定文字的 <text> 或 <tspan> 元素。"""
    for elem in root.iter("{http://www.w3.org/2000/svg}text"):
        if elem.text and keyword in elem.text:
            return elem
        for child in elem:
            if child.text and keyword in child.text:
                return elem
    return None


def generate_cover(template_name, title_lines, subtitle_lines, info_text,
                   number, output_path, brand_override=None):
    """生成封面 PNG。"""
    cfg = TEMPLATES[template_name]
    svg_path = cfg["svg"]

    with open(svg_path, "r", encoding="utf-8") as f:
        svg_content = f.read()

    # --- 替换水印期号 ---
    # 水印是那个 font-size="420" 或 "480" 的超大文字
    svg_content = re.sub(
        r'(font-size="4[0-9]{2}"[^>]*>)[^<]*(</text>)',
        rf'\g<1>{number}\2',
        svg_content,
    )

    # --- 替换底部角标 ---
    footer_text = f"{cfg['footer_prefix']}{number}"
    svg_content = re.sub(
        r'(letter-spacing="6">)[^<]*(</text>)',
        rf'\1{footer_text}\2',
        svg_content,
    )

    # --- 解析为 XML 做精确替换 ---
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    root = ET.fromstring(svg_content)

    # 找主标题 <text> 块（font-weight="900" 且包含 tspan）
    title_elem = None
    for text_el in root.iter("{http://www.w3.org/2000/svg}text"):
        if text_el.get("font-weight") == "900":
            tspans = list(text_el.iter("{http://www.w3.org/2000/svg}tspan"))
            if len(tspans) >= 2:
                title_elem = text_el
                break

    if title_elem is not None:
        old_tspans = list(title_elem.iter("{http://www.w3.org/2000/svg}tspan"))
        # 记住第一个 tspan 的属性作为模板
        first_tspan_attribs = dict(old_tspans[0].attrib) if old_tspans else {}
        # 找强调色（最后一个 tspan 如果有不同的 fill）
        accent_color = None
        if old_tspans:
            last = old_tspans[-1]
            if last.get("fill") and last.get("fill") != title_elem.get("fill"):
                accent_color = last.get("fill")

        # 清空旧 tspan
        for ts in old_tspans:
            title_elem.remove(ts)
        title_elem.text = None

        # 生成新 tspan
        font_size = first_tspan_attribs.get("font-size", "96")
        x_val = first_tspan_attribs.get("x", "80")
        dy_val = first_tspan_attribs.get("dy", "0")
        # 计算行间距（从第二个 tspan 的 dy 获取）
        line_dy = "120"
        if len(old_tspans) >= 2:
            d = old_tspans[1].get("dy", "120")
            if d != "0":
                line_dy = d

        for i, line in enumerate(title_lines):
            ts = ET.SubElement(title_elem, "{http://www.w3.org/2000/svg}tspan")
            ts.set("font-size", font_size)
            ts.set("x", x_val)
            ts.set("dy", "0" if i == 0 else line_dy)
            # 最后一行用强调色
            if i == len(title_lines) - 1 and accent_color:
                ts.set("fill", accent_color)
            ts.text = line

    # 找副标题 <text> 块（opacity="0.35" 的文字块）
    subtitle_elem = None
    for text_el in root.iter("{http://www.w3.org/2000/svg}text"):
        if text_el.get("opacity") == "0.35" and text_el.get("font-size"):
            tspans = list(text_el.iter("{http://www.w3.org/2000/svg}tspan"))
            if tspans:
                subtitle_elem = text_el
                break

    if subtitle_elem is not None and subtitle_lines:
        old_tspans = list(subtitle_elem.iter("{http://www.w3.org/2000/svg}tspan"))
        first_attribs = dict(old_tspans[0].attrib) if old_tspans else {}
        x_val = first_attribs.get("x", "80")

        for ts in old_tspans:
            subtitle_elem.remove(ts)
        subtitle_elem.text = None

        for i, line in enumerate(subtitle_lines):
            ts = ET.SubElement(subtitle_elem, "{http://www.w3.org/2000/svg}tspan")
            ts.set("x", x_val)
            ts.set("dy", "0" if i == 0 else "40")
            ts.text = line

    # 替换产品信息行（letter-spacing="2" 的那行）
    if info_text:
        for text_el in root.iter("{http://www.w3.org/2000/svg}text"):
            ls = text_el.get("letter-spacing")
            fs = text_el.get("font-size")
            if ls == "2" and fs in ("24", "22"):
                text_el.text = info_text
                break

    # 替换归属行中的品牌名（如果有 brand_override）
    if brand_override:
        for text_el in root.iter("{http://www.w3.org/2000/svg}text"):
            if text_el.text and "— " in text_el.text:
                text_el.text = f"— {brand_override}"
                break

    # 输出 SVG
    final_svg = ET.tostring(root, encoding="unicode", xml_declaration=False)
    # 补上 xmlns（ET 有时会丢）
    if 'xmlns="http://www.w3.org/2000/svg"' not in final_svg:
        final_svg = final_svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1)

    # 渲染 PNG
    try:
        import cairosvg
    except ImportError:
        print("错误：需要 cairosvg，运行 pip install cairosvg")
        raise SystemExit(1)

    cairosvg.svg2png(
        bytestring=final_svg.encode("utf-8"),
        write_to=output_path,
        output_width=1080,
        output_height=1350,
    )
    print(f"封面已生成：{output_path}")


def main():
    parser = argparse.ArgumentParser(description="生成小红书封面 PNG")
    parser.add_argument("template", choices=["breakdown", "allin"],
                        help="模板类型")
    parser.add_argument("--title", nargs="+", required=True,
                        help="标题行（最后一行自动高亮）")
    parser.add_argument("--subtitle", nargs="+", default=None,
                        help="副标题行")
    parser.add_argument("--info", default=None,
                        help="产品信息（如 '教师备课资料包 · 9.9元'）")
    parser.add_argument("--number", required=True,
                        help="期号（如 012、270）")
    parser.add_argument("--brand", default=None,
                        help="品牌名覆盖")
    parser.add_argument("-o", "--output", default=None,
                        help="输出路径（默认 cover_{template}.png）")
    args = parser.parse_args()

    output = args.output or f"cover_{args.template}.png"

    generate_cover(
        template_name=args.template,
        title_lines=args.title,
        subtitle_lines=args.subtitle,
        info_text=args.info,
        number=args.number,
        output_path=output,
        brand_override=args.brand,
    )


if __name__ == "__main__":
    main()
