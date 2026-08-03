> 原文快照：下沉自 docs/roadmap.md（2026-07-21 迁移），文中状态记号为历史残留

### P3-K: 视觉系统升级（V2 概念海报体系）

**触发**：2026-05-07 会话。用户在 E270 期临时验证后确认方向。原 sketchnote 信息图风格（黑线+天蓝色图标）不够吸引小红书用户；PDF 在 iPhone fit-width 显示时文字偏小。临时脚本散在 /tmp，需规范化进 Skill 体系。

**整体状态**：✅ 已完成（K1–K6 全部交付，2026-05-07，commit `c605835`）

#### P3-K1: PDF 排版手机优化

- 目标：A4 PDF 在 iPhone fit-width 缩放约 36% 后，屏幕显示文字 ≥12px 舒适可读
- 涉及文件：`templates/allin-kami/styles.css`
- 核心改动：body 14px→18px，章节标题 22px，英文/翻译 16px，封面标题 38px，页边距 `@page { margin: 10mm 12mm }`，内容 padding 32px 20px
- 设计原理：A4→iPhone fit-width 缩放约 36%，源 PDF 需 18px 以上才能保证屏幕 ≥12px
- 派发模式：Opus 自做（≤10 行字号值修改，已完成）
- 验收：iPhone Safari fit-width 打开 E270 PDF，正文清晰可读，无需放大
- 状态：✅ 已完成（commit `c605835`，2026-05-07）

#### P3-K2: 手绘笔记 V2 模板系统

- 目标：替换原 sketchnote 风格为「手绘高级概念海报」体系，封面+内页双模板，视觉语言更适合小红书引流
- 涉及文件：`scripts/allin/generate_sketchnote.py`（重写 `build_page_prompts()`）
- 新封面模板（cover_v2）核心要素：
  - 巨型核心词（毛笔/书法/剪纸艺术化处理，占 40–60% 面积）
  - 1–2 个微小角色或物体演绎词义（视觉隐喻）
  - 嵌入式封面信息（不分栏）：系列名、期号日期时长播放量、主题分类、副标题、三个核心议题印章、四主播署名、1–2 句诗性补白
  - 质感：手绘水彩+剪纸拼贴+石版印刷+宣纸颗粒
  - 严禁：分栏拼接、群像、英文界面元素、错字
- 新内页模板（inner_v2）核心要素：
  - 顶部巨型章节标题（毛笔字，占 15–20% 高度）
  - 核心隐喻母题贯穿全页（每个五维章节有专属母题，3 个要点「附着」在母题上，不做分栏卡片）
  - 底部金句或印章注解 + 系列标识
- 配色二元体系：
  - 亮色 A（轻盈派，默认）：粉蓝 #4A90E2 + 暖黄 #F5C842 + 米白 #F8F4ED
  - 亮色 B（清新派）：薄荷青 #5DA68F + 杏粉 #E8B197 + 米白
  - 深色 C（东方庄重派，重型题材备选）：朱红 #C73E2C + 墨黑 #1A1A1A + 米黄宣纸 #F5F2EA + 暖金 #C8A35F
  - 深色 D（藏青现代派）：藏青 #1B365D + 暖金 #C8A35F + 米白 + 朱砂红印章
  - 每期由主会话根据议题气质选定色组（默认亮色 A/B，重型变革/危机题材走深色 C/D）
- 派发模式：🅱️ 施工模式（Opus 已定完整方案，Codex 按方案改写 `build_page_prompts()`）
- 验收：用 E270 重生 5 张图，封面符合 cover_v2 要素，4 张内页符合 inner_v2 要素，配色属于同一色组
- 状态：✅ 已完成（commit `c605835`，2026-05-07）

#### P3-K3: Codex 优先生图链路修复

- 目标：补齐 SKILL.md Step 10 承诺的「Codex 优先生图 → API fallback」链路（当前脚本实际只调 OpenAI API）
- 涉及文件：`scripts/allin/generate_sketchnote.py`、`skills/lark-knowledge-allin-transcript/SKILL.md`
- 关键改动：新增 `generate_via_codex()` 函数，用 codex-companion task 派子代理生图；改 `generate_image()` 为 Codex 优先 + 配置 IMAGE_API_KEY 时 API fallback
- 派发模式：🅰️ 自主模式（Codex 自己读 SKILL.md 设计 fallback 链，不需要 Opus 预读代码）
- 验收：默认走 Codex 子代理生图；配置 IMAGE_API_KEY 环境变量时才走 API；SKILL.md 描述与实际一致
- 状态：✅ 已完成（commit `c605835`，2026-05-07）

#### P3-K4: 子代理并发生成（5 张并行）

- 目标：5 张手绘笔记从当前串行约 7 分钟（每张 80–90s）降到 2–3 分钟
- 涉及文件：`scripts/allin/generate_sketchnote.py`
- 实现思路：asyncio 或 threading.ThreadPoolExecutor，5 任务并发，统一收集结果
- 派发模式：🅰️ 自主模式
- 验收：5 张图并发生成，总耗时 ≤ 单张最长耗时 × 1.5
- 状态：✅ 已完成（commit `c605835`，2026-05-07）

#### P3-K5: 商品拆解图（P3-H）按 V2 规范同步

- 目标：`scripts/shared/gen_image.py` 当前用旧 sketchnote 提示词，需升级到 V2 双模板（4 张图：封面 cover_v2 + 3 张内容图 inner_v2）
- 涉及文件：`scripts/shared/gen_image.py`、`skills/lark-knowledge-upgrade/SKILL.md`（同步 Step 7 描述）
- 关键设计：与 `generate_sketchnote.py` 共享配色矩阵和模板生成逻辑（统一从 `scripts/shared/poster_template.py` 导入，见 K6）
- 派发模式：🅱️ 施工模式（方案已定，Codex 按方案改写）
- 验收：商品拆解 4 张图（封面+商业模式拆解+流量拆解+机会拆解）均符合 V2 规范，与 All In 手绘笔记视觉语言一致
- 状态：✅ 已完成（commit `c605835`，2026-05-07）

#### P3-K6: 提示词宪法（参数化模板固化）

- 目标：把封面 V2（cover_v2）和内页 V2（inner_v2）已验证的 prompt 抽象成参数化模板，存进 `scripts/shared/poster_template.py`，供 K2/K5 import 使用；解决每次新会话重写 prompt 导致风格漂移的问题
- 涉及文件：
  - `scripts/shared/poster_template.py`（新建）：包含 `COVER_V2_TEMPLATE`、`INNER_V2_TEMPLATE` 两个常量，以及 `render_cover_prompt(params)`、`render_inner_prompt(params)` 两个渲染函数
  - `scripts/allin/generate_sketchnote.py`（K2 完成后改造）：从 poster_template import，不再内联定义 prompt
  - `scripts/shared/gen_image.py`（K5 完成后改造）：同上
- 派发模式：🅱️ 施工模式（施工说明书 skill-allin-upgrade.md 第 5 章已完整指定模板内容和参数清单）
- 验收：
  - `scripts/shared/poster_template.py` 文件存在，包含两个模板常量和两个渲染函数
  - 模板字符串保留全部方法论骨架（风格基底 / 版面原则 / 严禁列表）
  - 所有可变参数都以 `{参数名}` 形式提取，覆盖封面 15 个参数、内页 8 个参数
  - E271 新一期套用模板，只填参数，无需任何 prompt 重写
  - 同一期数据二次调用模板，输出 prompt 完全一致（幂等）
- 状态：✅ 已完成（commit `c605835`，2026-05-07）
