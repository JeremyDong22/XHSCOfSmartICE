# 发小红书帖子 — 生成餐饮AI营销内容并通过DevTools自动发布
# v1.1: 迁移至 .claude/skills/，shared 路径更新为绝对项目路径

---
name: xhs-post
description: >
  This skill should be used when the user asks to "发小红书帖子", "写餐饮AI营销内容",
  "发帖", "写一篇小红书", "xhs post", "生成营销帖", "自动发帖", or mentions
  小红书内容创作、餐饮AI推广、社交媒体发布。Generates and publishes food industry
  AI marketing posts to Xiaohongshu Creator Platform via DevTools MCP.
user-invocable: true
argument-hint: "[主题] [类型:焦虑型|噱头型|干货型|故事型]"
---

# 小红书餐饮AI自动发帖

## 概述

生成并发布餐饮AI营销帖子到小红书创作服务平台。完整流程：读取品牌context → 生成内容 → 通过DevTools MCP自动发布。

## 参数

`/xhs-post [主题] [类型]`
- 主题：产品名或痛点关键词（如"桌访AI"、"智能库存"）
- 类型：焦虑型（默认）| 噱头型 | 干货型 | 故事型
- 示例：`/xhs-post 桌访AI 焦虑型`

## 执行流程

### 1. 读取品牌Context

读取以下 shared 文件获取最新品牌状态：
- **`.claude/plugins/xhs-automation/shared/brand-context.md`** — 当前narrative定位、已发布笔记清单、近期素材
- **`.claude/plugins/xhs-automation/shared/brand-knowledge.md`** — 产品矩阵、行业痛点、竞品案例、切入角度池
- **`.claude/plugins/xhs-automation/shared/performance-history.md`** — 帖子表现数据（如有），参考高表现内容策略

### 2. 防重复检查

从 `brand-context.md` 的"已发布笔记清单"中提取所有已发布标题和角度。确保本次生成的内容：
- 标题不与已发布笔记重复
- 切入角度不与最近3篇重复
- 产品聚焦不与最近2篇重复

### 3. 生成内容

参考 **`.claude/plugins/xhs-automation/shared/writing-formulas.md`** 中的写作公式，生成以下四部分：

**封面文字**：最多3行，每行不超过8个字
**标题**：20字以内，必须有情绪钩子，包含目标人群关键词
**正文**：490-600字，段落间空行，引用数据用引号突出，结尾有CTA
**标签**：5-10个，覆盖行业+技术+热点+场景四个维度

核心规则：
- 每次聚焦**一个具体产品**或**一个具体痛点**，不泛泛而谈
- 从 brand-knowledge.md 的切入角度轮换池中选择未用过的角度
- 使用 brand-context.md 中的近期素材增加时效性
- 如果 performance-history.md 有数据，优先使用高表现的内容策略

### 4. 用户确认

将生成的完整内容（封面文字 + 标题 + 正文 + 标签）展示给用户确认。等待用户确认或修改后再执行发布。

### 5. DevTools MCP 自动发布

按照 **`.claude/plugins/xhs-automation/shared/devtools-workflow.md`** 的10步流程执行自动发布：
1. 导航到创作服务平台发布页
2. 检查登录状态
3. 点击"文字配图"
4. 输入封面文字
5. 生成图片并选模板（焦虑型→提问，噱头型→涂写，干货型→备忘，故事型→手写）
6. 进入编辑页
7. 填写标题
8. 填写正文
9. 添加标签（优先使用系统推荐标签）
10. 发布

### 6. 更新记录

发布成功后，将新帖子追加到 `brand-context.md` 的"已发布笔记清单"中。

## 共享资源

所有共享文件位于 `.claude/plugins/xhs-automation/shared/`：

| 文件 | 用途 | 何时读取 |
|------|------|---------|
| `brand-context.md` | 品牌narrative、已发布清单 | 生成前必读 |
| `brand-knowledge.md` | 产品矩阵、痛点、案例 | 生成时参考 |
| `writing-formulas.md` | 标题公式、情绪词、CTA | 生成时参考 |
| `devtools-workflow.md` | DevTools发布流程 | 发布时参考 |
| `performance-history.md` | 帖子表现数据 | 生成前可选读取 |
