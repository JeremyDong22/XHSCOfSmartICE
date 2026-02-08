# 优化帖子 — 基于表现数据诊断问题并生成优化方案
# v1.1: 迁移至 .claude/skills/，shared 路径更新为绝对项目路径

---
name: xhs-optimize
description: >
  This skill should be used when the user asks to "优化帖子", "改一下那篇帖子",
  "帖子表现不好怎么办", "优化标题", "优化内容", "xhs optimize",
  "提升帖子数据", "内容迭代", or mentions 帖子优化、内容改进、标题优化、
  A/B测试、内容迭代。 Optimizes published XHS posts based on performance data
  and content strategy insights.
user-invocable: true
argument-hint: "[帖子编号或标题] [优化方向:标题|正文|标签|全部]"
---

# 小红书内容优化

## 概述

基于帖子表现数据和内容策略洞察，优化已发布的帖子或生成同主题的优化版本。支持修改已发布笔记（通过DevTools MCP）或生成全新的优化版帖子。

## 参数

`/xhs-optimize [帖子编号] [优化方向]`
- 帖子编号：对应 performance-history 中的编号
- 优化方向：标题 | 正文 | 标签 | 封面 | 全部（默认）
- 示例：`/xhs-optimize 3 标题`

## 执行流程

### 1. 诊断分析

读取 **`.claude/plugins/xhs-automation/shared/performance-history.md`** 获取目标帖子的表现数据。
如果没有数据，建议先执行 xhs-check 抓取最新数据。

分析帖子表现不佳的可能原因：
- **阅读低、互动低** → 标题/封面不够吸引，曝光不足
- **阅读高、互动低** → 内容质量问题，CTA不够强
- **阅读低、互动率高** → 内容好但曝光不足，标签/时间问题
- **评论多但负面** → 内容方向需要调整

### 2. 对比高表现帖子

从 performance-history 中找到表现最好的帖子，分析差异：
- 标题风格对比
- 帖子类型对比
- 标签使用对比
- 发布时间对比

### 3. 生成优化方案

参考 **`.claude/plugins/xhs-automation/shared/writing-formulas.md`** 和 **`.claude/plugins/xhs-automation/shared/brand-knowledge.md`**，针对诊断结果生成优化方案：

**标题优化**：
- 使用不同的标题公式重写
- 增加情绪钩子强度
- 优化关键词覆盖

**正文优化**：
- 调整开头钩子（前2句决定留存）
- 增加数据钩子和故事素材
- 强化CTA（参考高互动帖子的CTA风格）

**标签优化**：
- 替换低效标签
- 增加热门标签
- 调整标签维度覆盖

**封面优化**：
- 更换模板风格
- 调整封面文字（更强的钩子）

### 4. 用户确认

展示优化前后的对比，让用户选择：
- **修改原帖**：通过DevTools MCP编辑已发布笔记
- **发新帖**：用优化后的内容发一篇新帖子
- **仅记录**：记录优化建议，下次发帖时参考

### 5. 执行优化

如果用户选择修改原帖，按照 **`.claude/plugins/xhs-automation/shared/devtools-workflow.md`** 的"编辑已发布笔记流程"执行。
如果用户选择发新帖，调用 xhs-post skill 的发布流程。

### 6. 更新记录

在 **`.claude/plugins/xhs-automation/shared/performance-history.md`** 的检查日志中记录优化操作：
- 优化了哪篇帖子
- 优化了什么内容
- 优化前的数据基线（用于后续对比优化效果）

## 共享资源

所有共享文件位于 `.claude/plugins/xhs-automation/shared/`：

| 文件 | 用途 | 读/写 |
|------|------|-------|
| `performance-history.md` | 表现数据、优化记录 | 读+写 |
| `writing-formulas.md` | 优化时参考写作公式 | 读 |
| `brand-knowledge.md` | 优化时参考产品素材 | 读 |
| `brand-context.md` | 优化时参考品牌context | 读 |
| `devtools-workflow.md` | 编辑已发布笔记流程 | 读 |
