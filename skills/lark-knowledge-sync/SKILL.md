---
name: lark-knowledge-sync
version: 1.0.0
description: "同步规范：将 config.json 的最新字段定义推送到飞书规范文档，并追加系统变更记录。触发词：/同步规范"
---

# lark-knowledge-sync (v1.0.0)

**CRITICAL — 开始前 MUST 先用 Read 工具读取 [`../lark-shared/SKILL.md`](../lark-shared/SKILL.md)**

## 功能定位

将 `config.json` 的最新字段定义/选项值推送到飞书规范文档，保持对外展示内容同步。每月自动执行，也可手动触发。

**触发词**：`/同步规范`

**配置来源**：`~/.agents/skills/lark-knowledge-config/config.json`

**规范文档 token**（来自 config.json `spec_docs`）：

| 文档 | Token |
|-----|-------|
| 03_字段与状态机规范 | `ItD3wmSwwii82ykDpKHcqSF8n80` |
| 系统变更记录 | `UKshweoh7i0ML2kPhVGcTh9BnVh` |
| 01_收件入表规范（可选） | `OQfKwXIikijxI9kVjAncoewKnEc` |
| 02_聚合升级规范（可选） | `J82rwf2mTi8RNskCXefcrVtjnAd` |
| 04_知识库页面与排版规范（可选） | `WDdcwRtiAiRNVqkIB3Oc8TeDnDf` |

---

## Step 1: 确认同步范围

**默认同步**（每次必做）：
- `03_字段与状态机规范`：config.json 字段/选项有变更时同步
- `系统变更记录`：追加一条变更记录

**可选追加**（用户确认后执行）：
- `01_收件入表规范`
- `02_聚合升级规范`
- `04_知识库页面与排版规范`

---

## Step 2: 读取 config.json 当前状态

```bash
cat ~/.agents/skills/lark-knowledge-config/config.json
```

提取 `fields` 部分，生成全量字段选项表。

---

## Step 3: 生成并写入 03_字段与状态机规范

基于 config.json `fields` 生成字段选项表（overwrite 模式，全量覆盖）：

```bash
lark-cli docs +update \
  --doc "ItD3wmSwwii82ykDpKHcqSF8n80" \
  --mode overwrite \
  --markdown "<生成的字段规范内容>"
```

生成内容格式示例：
```markdown
## 字段选项表

| 字段名 | 可选值 |
|-------|--------|
| 来源渠道 | 飞书文档 / 公众号 / 网页 / PDF / ... |
| 专题归属 | 小红书 / 虚拟资料产品 / AI编程 |
| 资产形态 | 方法论 / SOP / 模板 / 技巧集 / 案例包 |
| 处理状态 | 待升级 / 待判断 / 仅归档 / 废弃 |
...
```

---

## Step 4: 追加系统变更记录

以 append 模式追加一条变更记录：

```bash
lark-cli docs +update \
  --doc "UKshweoh7i0ML2kPhVGcTh9BnVh" \
  --mode append \
  --markdown "<变更记录条目>"
```

变更记录格式：
```markdown
| <YYYY-MM-DD> | <变更内容简述> | <版本号> |
```

---

## Step 5: 输出同步结果

```
同步完成 ✅

已更新：03_字段与状态机规范
已追加：系统变更记录（<日期>）
```

## 权限

`docx:document`
