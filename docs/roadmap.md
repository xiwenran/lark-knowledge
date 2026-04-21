# lark-knowledge 路线图

> 全项目规划文件,所有版本期都在此文件中。按 Echo「跨阶段项目规划必须物理化」规则维护。

## 第一期 P1 — lint 升级 + Deep Research 接入(进行中)

**触发**:2026-04-21 会话讨论。参考 nashsu/llm_wiki 的四信号关联算法与空白识别思路,决定偷学两样能力进 lark-knowledge:
1. 现有 lark-knowledge-lint 扩展补链/聚类能力
2. 新建 lark-knowledge-research skill,调 Tavily API 自动补空白

**已砍掉**(用户本日拍板):Chrome 剪藏(Claude Code WebFetch 已够用)、lark-knowledge-intake 两步摄入升级(批量摄入一步够)。

### P1-A:lark-knowledge-lint 加四信号补链算法
- 目标:给现有 lint skill 加"未直接互链但内容相关"的补链建议能力
- 涉及文件:`skills/lark-knowledge-lint/SKILL.md`、可能新增 `scripts/lark_lint/signals.py`
- 算法参考:`~/Echo/scripts/obsidian_lint/signals.py`(直接链接 ×3.0、来源重叠 ×4.0、Adamic-Adar ×1.5、类型亲和 ×1.0)
- 验收:在现有飞书知识库实跑,Top 20 补链建议能由用户肉眼判合理
- 状态:✅ 已完成（占位 hash：47e249cdc4cc049bc23ae19348bc31189ce7c24f）

### P1-B:lark-knowledge-lint 加 Louvain 聚类 + 松散聚类识别
- 目标:识别内聚度偏低的社区、孤岛页面
- 涉及文件:`skills/lark-knowledge-lint/SKILL.md`、可能新增 `scripts/lark_lint/community.py`
- 参数调优:Obsidian 端用内聚度 < 0.15 判松散;lark-knowledge 规模更大,阈值和 Top N 可能需要放宽(首跑后调)
- 验收:松散聚类清单能指向真实的"没整理完"区块
- 状态:⏸ 待启动

### P1-C:新建 lark-knowledge-research skill 框架
- 目标:搭骨架——触发词、默认路径、与 lint 的协作契约、草稿写回位置
- 涉及文件:新建 `skills/lark-knowledge-research/SKILL.md`、`scripts/lark_research/` 目录
- 触发词(建议):补空白 / Deep Research / 研究补漏
- 与 lint 的协作:P1-B 产出的空白/松散聚类清单可作为 research 的输入
- 验收:skill 可被触发,输出结构化的研究任务清单(尚未真跑 API)
- 状态:✅ 已完成（commit `01a96d7`）

### P1-D:research skill 接入 Tavily API
- 目标:空白识别 → Tavily 搜索 → LLM 提炼 → 回写飞书草稿
- 涉及文件:`skills/lark-knowledge-research/SKILL.md`、`scripts/lark_research/*.py`
- 前置:用户已有 Tavily API 订阅,密钥走 env 变量不硬编码
- 验收:针对一个真实空白主题,能产出可读的草稿写入飞书"待确认"区
- 状态:⏸ 待启动

### P1-E:两个 skill 联动闭环
- 目标:lint 扫出空白 → research 批量补 → 用户确认后写入正式库
- 涉及文件:两个 skill 的 SKILL.md 互相引用、可能新增调度脚本
- 验收:一次"巡检 → 研究 → 确认"完整跑通,无人工粘合
- 状态:⏸ 待启动(依赖 P1-A/B/C/D 全部落地)

---

## 本期依赖

- 依赖 Obsidian 端 Echo v5.4-C 落地经验(networkx + python-louvain 验证过,可直接迁移)
- 算法参考 `~/Echo/scripts/obsidian_lint/`,不重造轮子
- lark-knowledge 规模大于 Obsidian,算法参数(Top N、聚类阈值)首跑后调优

## 本期不做(用户本日明确砍掉)

- Chrome 剪藏浏览器扩展——Claude Code 的 WebFetch 已经能读网页,不值得自建扩展
- lark-knowledge-intake 两步思维链摄入——商业资产批量场景容错度比个人档案高,一步够用,两步是 Obsidian 端才需要的精度
