> 原文快照：下沉自 docs/roadmap.md（2026-07-21 迁移），文中状态记号为历史残留

## 第三期 P2 — 小红书虚拟产品分析模块（进行中）

**触发**：2026-04-22 会话。新增第4个专题"小红书虚拟产品"，核心是引入**商业洞察5维框架**作为整个知识库的底层分析逻辑。

**架构决策**：5维框架（产品形态/流量转化/赛道竞争/操盘手画像/机会洞察）适用于所有内容——商品链接、文章、精华帖均通过此框架分析。所有知识库成品页和视角提炼页统一使用5维章节结构。

### P2-A: 配置与 wiki 目录
- 目标：新增专题/资产形态/source_type，飞书 wiki 子目录上线
- 涉及文件：`~/.agents/skills/lark-knowledge-config/config.json`
- 变更：新增专题"小红书虚拟产品"、资产形态"商品调研"/"赛道分析"、source_type xhs_product/xhs_shop/xhs_profile
- wiki 节点：04_小红书虚拟产品（`S4kqwctcFiPIlQkHcbUcUjSGnpg`）/ 01_竞品案例（`T86Bw4KpciQFHikwUdncSTpXnv2`）/ 02_赛道分析（`IKTxwoR4HimnV9k3ZBCc4Xv1ned`）
- 状态：✅ 已完成（2026-04-22）

### P2-C: Intake 5维分析框架（全库通用）
- 目标：所有内容 AI摘要 通过5维框架撰写，不限专题
- 涉及文件：`skills/lark-knowledge-intake/SKILL.md`
- 状态：✅ 已完成（2026-04-22）

### P2-D: Upgrade 5维章节结构（全库通用）
- 目标：所有资产形态成品页/视角提炼页统一使用5维章节结构，替换原有按资产形态分列的模板
- 涉及文件：`skills/lark-knowledge-upgrade/SKILL.md`
- 状态：✅ 已完成（2026-04-22）
