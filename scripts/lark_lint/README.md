# lark_lint

只读型补链建议脚本。读取 `config.json` 中的飞书 Base 配置，拉取多维表格记录和知识库页面内容，调用 `signals.py` 输出 Top N 补链建议到标准输出，不回写飞书。

## 用法

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python lint_links.py --top-n 50
```

## 配置

- 默认按顺序查找 `config.json`、`~/.agents/skills/lark-knowledge-config/config.json`
- 也可通过 `--config <path>` 或环境变量 `LARK_KNOWLEDGE_CONFIG` 显式指定
- 严禁把飞书 token、AppID 写进脚本

## 说明

- `signals.py` 按要求直接拷贝自 Echo 源文件，未改写算法实现。
- 为了让原样拷贝的 `signals.py` 能运行，本目录补了同名兼容模块 `graph.py` 和 `nx_compat.py`。
- 脚本只读取 Base 记录与文档 markdown，基于 `## 相关词条` 区块构建现有链接关系，再输出补链建议。
