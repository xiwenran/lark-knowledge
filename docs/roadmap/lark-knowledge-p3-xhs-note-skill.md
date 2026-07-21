> 原文快照：下沉自 docs/roadmap.md（2026-07-21 迁移），文中状态记号为历史残留

### P3-H: 产品拆解笔记生成（upgrade Step 7）
- 目标：对产品分析页面生成 4 张手绘拆解图，用于小红书发布引流
- 涉及文件：`skills/lark-knowledge-upgrade/SKILL.md`（新增 Step 7）、`scripts/shared/gen_image.py`（新增共享图片生成工具）
- 4 张图：封面 / 商业模式拆解 / 流量拆解 / 机会拆解
- 复用 All In 手绘笔记视觉风格
- 状态：✅ 已完成（commit `2f0a525`，2026-05-06）

### P3-I: 小红书笔记撰写 Skill
- 目标：新建独立 Skill，根据飞书知识库页面内容自动撰写小红书笔记（无独立标题，首段 ≤30 字即标题预览、正文 ≤300 字、5-10 个话题标签）
- 涉及文件：新建 `skills/lark-knowledge-xhs-note/SKILL.md`
- 触发词：`/小红书笔记`
- 写作风格：口语化、具体数字、简单直接、举例驱动、结果感强
- 三种内容类型自动区分：🔍 商品拆解型 / 💡 行业洞察型 / 📝 经验分享型
- 配图统一输出到 `~/Downloads/AllInPodcast/<期号>_<主题>/` 子文件夹
- 首段与正文之间增加过渡句，避免跳跃感
- 状态：✅ 已完成（commits `cfdbaac` → `71bb01d`，2026-05-06）

### P3-J: gen_image.py 代码修复
- 目标：修复冷眼审查发现的两个瑕疵（import time 位置 + 配置路径统一）
- 涉及文件：`scripts/shared/gen_image.py`
- 状态：✅ 已完成（commit `cfdbaac`，2026-05-06）
