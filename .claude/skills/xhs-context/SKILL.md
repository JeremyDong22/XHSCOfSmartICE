# 更新品牌Context — 记录narrative变化、新产品、新事件、新素材
# v1.1: 迁移至 .claude/skills/，shared 路径更新为绝对项目路径

---
name: xhs-context
description: >
  This skill should be used when the user mentions brand changes, narrative updates,
  new products, new stores, company positioning shifts, or says things like
  "我们最近开了新店", "narrative要改", "公司定位调整了", "我们做了新产品",
  "更新品牌信息", "加个新素材", "我们跟XX合作了", "品牌context",
  or any update to SmartICE/宁桂杏/野百灵 brand information that should influence
  future content generation. Manages and updates brand context to keep content aligned with latest brand information.
user-invocable: true
argument-hint: "[品牌变化描述]"
---

# 品牌Context动态管理

## 概述

维护品牌的动态context库，确保所有内容生成skill使用最新的品牌信息。当品牌发生变化（新产品、新店、narrative调整、合作、里程碑）时，结构化地更新共享知识库。

## 参数

`/xhs-context [变化描述]`
- 也可以在对话中自然提及品牌变化，自动触发
- 示例：用户说"我们最近跟一个连锁品牌签了合作"

## 执行流程

### 1. 理解变化

分析用户描述的品牌变化，归类为以下类型：
- **Narrative变化**：品牌定位、核心身份、差异化表述的调整
- **实体变化**：新店开业、店铺关闭、品牌更名
- **产品变化**：新产品上线、产品升级、产品下线
- **里程碑事件**：合作签约、获奖、媒体报道、数据突破
- **素材更新**：新的客户故事、新的数据点、新的案例

### 2. 确认变更

向用户确认理解是否正确，展示将要更新的内容：
- 哪个文件会被更新
- 具体更新什么内容
- 对未来内容生成的影响

### 3. 执行更新

根据变化类型，更新对应的 shared 文件（位于 `.claude/plugins/xhs-automation/shared/`）：

**Narrative变化** → 更新 `brand-context.md` 的"当前Narrative定位"部分：
- 修改核心身份、品牌故事、差异化、阶段描述
- 在"品牌大事记"追加记录：日期 - narrative从X变为Y - 原因

**实体变化** → 更新 `brand-context.md` 的"品牌实体"部分：
- 新增/修改/删除品牌实体信息
- 在"品牌大事记"追加记录

**产品变化** → 更新 `brand-knowledge.md` 的"产品矩阵"部分：
- 新增产品：按现有格式添加（老板说法、痛点、数据钩子、故事素材）
- 产品升级：更新对应产品的描述
- 同时更新"切入角度轮换池"，添加新产品相关的角度

**里程碑事件** → 更新 `brand-context.md` 的"品牌大事记"和"近期可用素材"：
- 大事记追加：日期 - 事件描述 - 对内容策略的影响
- 近期素材追加：可以在帖子中使用的具体素材

**素材更新** → 更新 `brand-context.md` 的"近期可用素材"或 `brand-knowledge.md` 的对应产品部分

### 4. 影响评估

更新完成后，向用户说明：
- 更新了哪些文件的哪些部分
- 这些变化会如何影响未来的帖子生成
- 是否建议立即发一篇新帖子来体现这些变化
- 是否需要优化已发布的帖子（如果narrative大幅变化）

## 共享资源

所有共享文件位于 `.claude/plugins/xhs-automation/shared/`：

| 文件 | 用途 | 读/写 |
|------|------|-------|
| `brand-context.md` | narrative、实体、大事记、素材 | 读+写 |
| `brand-knowledge.md` | 产品矩阵、痛点、角度池 | 读+写 |
| `performance-history.md` | 参考表现数据决定是否需要优化 | 读 |
