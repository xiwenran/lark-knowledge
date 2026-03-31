# 飞书知识库生产线

基于飞书 + Claude Code 的专题知识库自动化生产系统。

## 系统架构

```
外部资料 → AI结构化处理 → 飞书多维表格 → 聚合升级 → 专题知识库成品
```

## 核心功能

| Skill | 触发词 | 功能 |
|-------|--------|------|
| `lark-knowledge-intake` | /收件 | 资料 → 结构化 → 写入多维表格 |
| `lark-knowledge-upgrade` | /升级 | 表格记录 → 聚合 → 知识库页面 |
| `lark-knowledge-format` | /排版 | 文档 → 彩色富文本排版美化 |

## 目录结构

```
.
├── memory/                          # Claude Code 记忆系统
│   ├── MEMORY.md                    # 记忆索引
│   ├── project_knowledge_system.md  # 方案总览
│   ├── project_build_progress.md    # 搭建进度
│   ├── user_language.md            # 用户语言偏好
│   └── user_business.md             # 用户业务背景
├── skills/                          # 自定义 Skill
│   ├── lark-knowledge-intake/      # 收件入表
│   ├── lark-knowledge-upgrade/      # 聚合升级
│   └── lark-knowledge-format/      # 排版美化
└── memory/
    └── reference_feishu_ids_SAMPLE.md  # Token 示例（脱敏）
```

## 三个专题

1. **小红书** — 内容分发、流量获取
2. **虚拟资料产品** — 产品化、售卖、变现
3. **AI编程** — 提效、自动化

## 新电脑配置步骤

1. 克隆仓库到 `~/.agents/skills/` 和 `~/.claude/projects/-Users-xili/memory/`
2. 配置 `~/.agents/skills/lark-knowledge-config/config.json`（参考 `reference_feishu_ids_SAMPLE.md`）
3. 运行 `lark-cli auth login` 完成飞书认证

## 排版规范版本

当前版本：**v6.4.2**

核心规则：每句话 2-4 个着色词、Callout 替代列表、标题用 `<text color>` 包裹。

详见 `skills/lark-knowledge-format/SKILL.md`
