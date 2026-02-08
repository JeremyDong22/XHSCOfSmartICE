# 查看帖子表现 — 抓取数据看板、评论区洞察、内容复盘
# v1.1: 迁移至 .claude/skills/，shared 路径更新为绝对项目路径

---
name: xhs-check
description: >
  This skill should be used when the user asks to "看看帖子表现", "帖子数据怎么样",
  "检查小红书数据", "帖子火了吗", "评论区有什么", "xhs check", "追踪帖子",
  "内容表现分析", or mentions 小红书数据看板、帖子互动、评论洞察、内容复盘。
  Tracks post performance via DevTools MCP on Xiaohongshu Creator Platform.
user-invocable: true
argument-hint: "[可选:帖子编号或标题关键词]"
---

# 小红书帖子表现追踪

## 概述

通过 DevTools MCP 访问小红书创作服务平台数据看板，抓取帖子表现数据（阅读、点赞、收藏、评论、转发），分析内容策略效果，识别高表现内容模式。

## 参数

`/xhs-check [帖子编号或关键词]`
- 无参数：检查所有帖子的整体表现
- 指定帖子：只检查特定帖子的详细数据
- 示例：`/xhs-check` 或 `/xhs-check 桌访AI`

## 执行流程

### 1. 读取历史数据

读取 **`.claude/plugins/xhs-automation/shared/performance-history.md`** 获取上次检查的数据基线，用于对比增长。

### 2. 抓取数据看板

通过 DevTools MCP 执行：
1. navigate_page → "https://creator.xiaohongshu.com/statistics"
2. take_snapshot → 抓取整体数据概览（总阅读、总互动、粉丝变化）
3. 导航到笔记管理页面，逐篇抓取每篇笔记的详细数据
4. 对每篇笔记记录：阅读量、点赞数、收藏数、评论数、转发数

### 3. 评论区洞察（可选）

如果用户要求或某篇帖子互动量显著，进入评论区：
1. 点击进入帖子详情
2. take_snapshot 抓取评论内容
3. 识别以下信号：
   - **潜在客户**：问价格、问方案、问合作的评论
   - **高频问题**：多人问同一个问题
   - **负面反馈**：投诉、质疑、不满
   - **互动机会**：可以回复增加互动的评论

### 4. 数据分析

对比历史数据，生成分析报告：

**整体趋势**：
- 总阅读/互动的增长趋势
- 粉丝增长情况
- 最近一周 vs 上一周的对比

**单篇分析**：
- 哪篇帖子表现最好？为什么？（类型、标题风格、发布时间）
- 哪篇帖子表现最差？可能原因？
- 互动率（互动/阅读）排名

**内容策略洞察**：
- 哪种帖子类型（焦虑/噱头/干货/故事）表现最好？
- 哪种标题风格点击率最高？
- 哪些标签带来最多曝光？
- 最佳发布时间段

### 5. 更新记录

将最新数据写入 **`.claude/plugins/xhs-automation/shared/performance-history.md`**：
- 更新表现数据汇总表
- 更新内容策略洞察
- 更新评论区洞察（如有）
- 追加检查日志（时间戳 + 关键发现）

### 6. 输出报告

向用户展示简洁的分析报告，包含：
- 数据变化摘要（对比上次检查）
- Top 3 表现最好的帖子
- 需要关注的评论（潜在客户、负面反馈）
- 下一步建议（发什么类型的帖子、是否需要优化某篇）

## 共享资源

所有共享文件位于 `.claude/plugins/xhs-automation/shared/`：

| 文件 | 用途 | 读/写 |
|------|------|-------|
| `performance-history.md` | 历史数据和洞察 | 读+写 |
| `brand-context.md` | 已发布笔记清单 | 读 |
| `devtools-workflow.md` | 数据看板导航流程 | 读 |
