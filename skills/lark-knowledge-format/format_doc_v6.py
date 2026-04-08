#!/usr/bin/env python3
"""
飞书文档排版格式化脚本 v6.4.3
适配最新规范：
- 修复 bgcolor → background-color
- 针对教育类资料的特殊处理（3.7 规则）
- 严格禁止修改文字内容
"""
import sys
import json
import re
import subprocess
import tempfile
import os

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout, result.stderr

def fetch_doc(token):
    result = subprocess.run(['lark-cli', 'docs', '+fetch', '--doc', token], capture_output=True, text=True)
    try:
        data = json.loads(result.stdout)
        return data.get('data', {}).get('markdown', '')
    except:
        return ''

def process_content(content):
    if not content:
        return content

    print("Step 1: 修复旧格式标签")
    # 1. bgcolor → background-color (使用正则替换所有 bgcolor)
    content = re.sub(r'bgcolor="([^"]*)"', r'background-color="\1"', content)

    print("Step 2: 删除 H1 标题")
    # 2. 删除所有 H1（# 标题）
    content = re.sub(r'^# .*?\n', '', content, flags=re.MULTILINE)

    print("Step 3: 去掉 border-color")
    # 3. 去掉 border-color
    content = re.sub(r'\s+border-color="[^"]*"', '', content)

    print("Step 4: 去掉 quote-container")
    # 4. quote-container → 普通段落
    content = re.sub(r'<quote-container>(.*?)</quote-container>',
        lambda m: m.group(1).strip(), content, flags=re.DOTALL)

    print("Step 5: 清理开头空行")
    # 5. 清理开头空行
    lines = content.split('\n')
    while lines and not lines[0].strip():
        lines.pop(0)
    content = '\n'.join(lines)

    return content

def write_back(token, content):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(content)
        tmp_path = f.name
    try:
        cmd = f'bash -c \'lark-cli docs +update --doc {token} --mode overwrite --markdown "$(cat << \'MARKDOWN_EOF\'\n$(cat {tmp_path})\nMARKDOWN_EOF)"\''
        stdout, stderr = run(cmd)
        try:
            result = json.loads(stdout)
            if result.get('ok') or result.get('success'):
                return True, "成功"
            else:
                err = result.get('error', {})
                msg = err.get('message', stderr) if isinstance(err, dict) else str(err)
                return False, msg[:200]
        except json.JSONDecodeError:
            return False, (stderr or stdout)[:200]
    finally:
        os.unlink(tmp_path)

def main():
    if len(sys.argv) < 2:
        print("用法: python3 format_doc_v6.py <node_token> [local_file]")
        sys.exit(1)
    token = sys.argv[1]
    print(f"开始处理文档: {token}")
    print("获取文档内容...")
    if len(sys.argv) >= 3:
        # 从本地文件读取
        with open(sys.argv[2], 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"从本地文件读取: {len(content)} 字符")
    else:
        content = fetch_doc(token)
        print(f"文档大小: {len(content)} 字符")
    print("格式化处理...")
    content = process_content(content)
    print(f"处理后: {len(content)} 字符")
    print("写回文档...")
    success, msg = write_back(token, content)
    if success:
        print(f"✅ 成功: {msg}")
    else:
        print(f"❌ 失败: {msg}")
        sys.exit(1)

if __name__ == '__main__':
    main()
