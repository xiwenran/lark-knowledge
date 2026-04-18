---
name: 知识生产线搭建进度
description: 飞书知识库目录结构和多维表格的搭建进度跟踪
type: project
---

## 搭建开始时间
2026-03-29

## 已完成

### 1. 知识库目录结构 ✅
在知识空间中创建了完整的一级和二级目录：
- 00_收件说明、01_小红书（含5个子目录）、02_虚拟资料产品（含5个子目录）、03_AI编程（含5个子目录）、90_方法论与规则、99_待整理与归档说明

### 2. 多维表格字段配置 ✅
- base_token: <BASE_TOKEN>
- table_id: <TABLE_ID>（表名：收件记录）
- 24 个字段全部创建完成

### 3. 自定义 Skill 创建 ✅
创建了 5 个自定义 Skill：
- `lark-knowledge-intake`（/收件）：AI 结构化处理 → 写入多维表格 → 评分≥4自动调用 upgrade
- `lark-knowledge-upgrade`（/升级）：升级流程唯一实现；intake 和手动触发都走此 Skill；支持 Karpathy 风格交叉引用和洞察归档
- `lark-knowledge-format`（/排版）：读取文档 → 按飞书富文本规范美化排版（v6.5.0：字色+背景色双管齐下）
- `lark-knowledge-sync`（/同步规范）：config.json 字段定义 → 飞书规范文档，每月1日自动执行
- `lark-knowledge-lint`（巡检）：扫描积压预警、孤岛词条、关键词缺口，输出巡检报告
- 位置：~/.agents/skills/lark-knowledge-*（软链接指向 /Users/xili/lark-knowledge/skills/，改仓库即生效）

### 4. 方案文档重构为总控+子文档模式 ✅
- 总控主文档只做索引，不维护执行细节
- 5个执行规范子文档：收件规范/升级规范/字段规范/排版规范/变更记录
- 所有子文档字段名已与实际表格24字段对齐

### 5. 引入统一配置文件 + 精简 Skill ✅
- 创建 `~/.agents/skills/lark-knowledge-config/config.json`（唯一数据源）
  - 包含：base_token、table_id、所有 wiki 目录 token、所有字段选项值、规范文档 token
- 四个 Skill 全部精简，硬编码值改为读取 config.json
- intake Step 4 改为引用 upgrade SKILL.md，消除重复逻辑

### 6. 已知 Bug 修复 ✅
- intake line 162 P0 Bug（minimax 乱码）已修复
- upgrade Step 5 回填字段格式：select 字段必须用数组格式 `["已升级"]`，字符串格式静默失败
- format + upgrade 禁止在正文写 `# 标题`（H1），防止与飞书文档元数据标题重复
- intake Step 1 加入微信文章降级链：Jina → Chrome MCP → 提示 PDF

### 7. 自动化运维 ✅
- Skills 目录改为软链接（~/.agents/skills/ → 仓库），改仓库即生效无需手动同步
- cron 月度定时任务：每月1日 09:00 CST 自动执行 /同步规范
- 日志写入 /Users/xili/lark-knowledge/logs/sync.log

## 当前状态

**全流程已在运行。第一段（收件入表）和第二段（升级建页）均已打通，已有3条入库记录。**

## 下一步
1. 搭结构 ✅ 完成
2. 第一段（资料→表格）✅ 已打通，持续收件
3. 第二段（表格→知识库）✅ 已打通，upgrade 正常运行
4. 先半自动，再逐步增加自动化 ⏳ 持续优化中
