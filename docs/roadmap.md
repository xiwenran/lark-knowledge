# lark-knowledge 路线图

> 全项目规划文件,所有版本期都在此文件中。按 Echo「跨阶段项目规划必须物理化」规则维护。

**结构说明（2026-07-21 改造）**：本文件只保留「当前主线状态（按专项分组）+ 待确认区 + 未排期 + 已关闭索引」；判断项目现在走到哪一步只看本文件，不需要通读全文。每个专项的详细背景、决策过程、验收清单下沉到 `docs/roadmap/`（已关闭）与 `docs/roadmap/pending/`（待确认）子文件。**子文件不写新状态、不写新进度、不写下一步**——文中残留的 已完成/进行中/待启动 等状态记号只是下沉时的原文快照，判断当前状态只认本文件。

---

## 当前主线状态

### [P1] lark-knowledge-lint × research 联动闭环（P1-E）  [详情 →](roadmap/lark-knowledge-p1-lint-research-close.md)
- 当前阶段: P1-A~D（补链算法/聚类识别/research骨架/Tavily接入）均已完成；P1-E「lint扫空白→research批量补→用户确认写入正式库」完整闭环仍在打通
- 一句话现状: 来源计划层（source_planner）已落地，完整编排（巡检→来源计划→研究→待确认草稿）尚未跑通
- 阻塞: 原文未提及具体阻塞项
- 最近验证: 原文未给出具体验证记录，仅说明"来源计划层已落地"
- commit hash: 原文未提供（P1-A~D 各自有 hash，P1-E 本身未给出）

---

## 待确认区（等用户裁决：还在做 / 已关闭 / 废弃归档）

### P11.4~P11.6 — 微信公众号/音视频转写/登录态社交平台抓取器  [原文快照 →](roadmap/pending/lark-knowledge-p11-4-5-6-unverified.md)
- 缺什么: 三项均标注"✅ 已完成（骨架，commit `47e249c`）"，但原文各自明确写"真实扫码+抓取验收待后续会话""Get 笔记 API key 真调用验收待后续会话""Browser Bridge 扩展 + OpenCLI CLI 真调用验收待后续会话"，无法确认真机验收是否已发生
- 待裁决: 这三项此后是否已经真实验收过？若已验收需补验证证据；若未验收，应转回「当前主线」或「未排期」
- 建议: 回看后按实际情况二选一：已验收则补记录转已关闭；未验收则明确当前是否还打算推进

### P2-F — 端到端验收（3 测试链接跑完整流程）  [原文快照 →](roadmap/pending/lark-knowledge-p2f-e2e-acceptance.md)
- 缺什么: 2026-07-21 主会话核对：git 历史无 P2-F 执行记录，判定未执行过
- 待裁决: 是否还要补跑 3 测试链接端到端验收？还是随 P2-B 日常使用已实质覆盖、直接放弃该单独验收项？
- 建议: 若 xhs_product 抓取近期有真实使用且无问题，建议放弃单独验收直接归档

### P3-F — 精选 Top20 自动维护脚本  [原文快照 →](roadmap/pending/lark-knowledge-p3f-top20-updater.md)
- 缺什么: 2026-07-21 主会话核对：脚本 `5a67396` 后另有公式修正 `d200716`（说明至少实跑过一次），但「≥10 期数据后首跑验收」是否满足需查飞书表期数，静态核不出
- 待裁决: 当前收件表期数是否已 ≥10？若是可安排首跑验收后关闭
- 建议: allin 全量批次跑完后期数大概率已够，届时跑一次验收即可关闭

---

## 未排期

- P2-B2 — 小红书商品免登录抓取方案（待升级） ⏸ 待启动：把商品页免登录能力固化为 intake 主路径，替换当前误走 OpenCLI 登录态骨架的行为
- P2-E — 赛道分析自动汇总 ⏸ 待规划（P3 考虑）：积累到一定数量的商品调研记录后，自动汇总生成赛道分析页

---

## 已关闭

- P2-A/C/D 小红书虚拟产品配置三项（专题/资产形态/source_type 配置、intake 5维框架全库化、upgrade 5维章节结构） ✅ `9c218b2` — 验证: 2026-07-21 主会话核对，提交信息逐项列明 intake/upgrade SKILL.md 与 config.json（独立配置仓）改动；P2-A 飞书 wiki 三节点 token 已记录在原文快照 [详情 →](roadmap/lark-knowledge-p2-acd-missing-hash.md)
- P3-E Kami PDF 排版模板 + 自动化脚本 ✅ `427683a`（模板）+`66ed87f`（generate_pdf.py 脚本） — 验证: 2026-07-21 主会话核对定位到脚本提交，其后 f94f081/86bbce2/e74649e 等十余次排版迭代与自动上传飞书功能均基于该脚本实跑演进 [详情 →](roadmap/lark-knowledge-p3e-kami-pdf.md)
- P3-G 逐字稿流水线重构（多模型分工 + 质量合同） ✅ `3fd9128` — 验证: 2026-07-21 主会话核对，重构后提交链证明真实运行（`2bd28f5` 修复真实响应字段名、`e89a230` 收件后自动接续逐字稿、`8c02bc0` 专项排版规则），当前 allin-fullrun-phase3 分支正以该流水线全量批跑 [详情 →](roadmap/lark-knowledge-p3g-pipeline-rewrite.md)
- lark-knowledge-lint 四信号补链 + Louvain 聚类识别 + research skill 骨架 + Tavily API 接入（P1-A/B/C/D） ✅ `2073f44`/`6408931`/`01a96d7`/`ee2d23e` — 验证: 现有飞书知识库实跑，Top 20 补链建议人工判合理；松散聚类清单可用；research skill 骨架可触发并输出结构化任务清单；针对真实空白主题产出可读草稿写入飞书待确认区 [详情 →](roadmap/lark-knowledge-p1-lint-research-close.md)
- P11 多源抓取器基础设施 + 无状态网页 + 文档附件 + 对抗性审查修复 ✅ `47e249c`/`37d4339` — 验证: dispatcher 对 10 URL+3 文件正确分发；10 个公开网页全部拿到正文，3 个 paywall 站至少 2 个正文入库；PDF/DOCX/PPTX/XLSX/EPUB/arxiv 各扩展名样本转换成功；对抗性审查发现 3 处安全/逻辑问题（2 高 1 中）修复后新增 3 条回归测试，41/41 通过 [详情 →](roadmap/lark-knowledge-p11-fetchers-core.md)
- P2-B xhs_product Fetcher + dispatcher 顶层扩展 ✅ `9c218b2` — 验证: 识别 xhslink 短链，公开分享页/H5 API/无登录 Playwright 抓商品与店铺页面，账号主页不走登录态（原文未给出具体测试用例数量，仅标记完成） [详情 →](roadmap/lark-knowledge-p2b-xhs-fetcher.md)
- All In Podcast 飞书基础设施 + 收件 Skill + 逐字稿双语排版 + 内联注释（P3-A/B/C/D） ✅ `57e06f1`/`6ea0e2d`/`4f51a00` — 验证: 飞书多维表格 17 字段齐全、6 大主题+2024/2025 子节点全部可访问；1 期真实 YouTube 链接跑通收件表新增记录；1 期逐字稿完整写入飞书页面，格式符合方案文档规范，注释与独立五维分析章节已覆盖 [详情 →](roadmap/lark-knowledge-p3-allin-core-pipeline.md)
- All In 商品拆解图（P3-H）+ 小红书笔记撰写 Skill（P3-I）+ gen_image.py 修复（P3-J） ✅ `2f0a525`/`cfdbaac`→`71bb01d` — 验证: 4 张手绘拆解图（封面/商业模式/流量/机会）完成；小红书笔记撰写 skill 完成，触发词 `/小红书笔记` 可用；冷眼审查发现的 import time 位置与配置路径两处瑕疵已修复 [详情 →](roadmap/lark-knowledge-p3-xhs-note-skill.md)
- All In 视觉系统 V2（P3-K1~K6：PDF 手机字号优化 / 手绘概念海报双模板 / Codex 优先生图链路 / 5 张并发生成 / 商品拆解图同步 V2 / 提示词参数化模板固化） ✅ `c605835` — 验证: K1~K6 全部交付；E270 重生 5 张图，封面符合 cover_v2 要素、4 张内页符合 inner_v2 要素、配色属于同一色组；`poster_template.py` 模板参数化后同一期数据二次调用输出完全一致（幂等） [详情 →](roadmap/lark-knowledge-p3k-visual-v2.md)
