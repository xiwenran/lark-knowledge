#!/usr/bin/env python3
"""小红书登录态保存脚本。运行后在弹出浏览器中完成登录，回到终端按回车。"""

import sys
sys.path.insert(0, "skills/lark-knowledge-intake")
from fetchers.opencli_bridge import login

if __name__ == "__main__":
    raise SystemExit(login("xhs"))
