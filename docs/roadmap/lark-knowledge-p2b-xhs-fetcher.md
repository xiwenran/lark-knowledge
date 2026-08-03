> 原文快照：下沉自 docs/roadmap.md（2026-07-21 迁移），文中状态记号为历史残留

## 第三期 P2 — 小红书虚拟产品分析模块（进行中）

**触发**：2026-04-22 会话。新增第4个专题"小红书虚拟产品"，核心是引入**商业洞察5维框架**作为整个知识库的底层分析逻辑。

**架构决策**：5维框架（产品形态/流量转化/赛道竞争/操盘手画像/机会洞察）适用于所有内容——商品链接、文章、精华帖均通过此框架分析。所有知识库成品页和视角提炼页统一使用5维章节结构。

### P2-B: xhs_product Fetcher + dispatcher 扩展
- 目标：识别 xhslink 短链 + 调公开分享页 / H5 API / 无登录 Playwright 抓商品与店铺页面；账号主页不走登录态
- 涉及文件：`skills/lark-knowledge-intake/xhs_product.py`（新建）、`skills/lark-knowledge-intake/dispatcher.py`（新建顶层分发器）
- 状态：✅ 已完成（commit `9c218b2`）
