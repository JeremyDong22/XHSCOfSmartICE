# DevTools MCP 浏览器自动化流程 v1.1
# xhs-post, xhs-optimize, xhs-check 共享的浏览器自动化流程
# 前提: Chrome DevTools MCP 已连接，用户已登录小红书创作服务平台
# v1.1: 补充笔记管理页数据抓取流程（基于 2026-02-09 实测）

---

## 一、发布笔记流程（xhs-post 使用）

### Step 1: 导航到发布页
navigate_page → url: "https://creator.xiaohongshu.com/publish/publish?source=official"

### Step 2: 检查登录状态
take_snapshot → 检查是否有"发布笔记"文字
如果出现登录/二维码页面 → 提示用户手动登录，等待确认

### Step 3: 点击"文字配图"
take_snapshot → 找到"文字配图"按钮 → click

### Step 4: 输入封面文字
take_snapshot → 找到文本输入框 → fill(封面文字)

### Step 5: 生成图片并选模板
click "生成图片" → take_snapshot → 根据帖子类型选择模板:
- 焦虑型 → "提问"
- 噱头型 → "涂写"
- 干货型 → "备忘"
- 故事型 → "手写"
click 对应模板

### Step 6: 进入编辑页
click "下一步"

### Step 7: 填写标题
take_snapshot → 找到标题输入框(placeholder="填写标题会有更多赞哦") → fill(标题)

### Step 8: 填写正文
找到正文输入框(multiline) → click → 全选(Meta+A) → fill(正文内容)

### Step 9: 添加标签
take_snapshot → 找到系统推荐的标签 → 逐个click添加
每次click后重新take_snapshot获取新推荐标签
添加5-8个相关标签

### Step 10: 发布
take_snapshot → 找到"发布"按钮 → click
等待"发布成功"确认页面

---

## 二、编辑已发布笔记流程（xhs-optimize 使用）

1. navigate_page → "https://creator.xiaohongshu.com/new/note-manager"
2. take_snapshot → 找到目标笔记 → click "编辑"
3. 进入编辑页后，按发布流程 Step 7-10 修改内容
4. 点击"保存"而非"发布"

---

## 三、抓取帖子表现数据流程（xhs-check 使用）

### 重要：不要用数据看板页

~~navigate_page → "https://creator.xiaohongshu.com/statistics"~~

**数据看板页需要单独申请权限**，大部分账号会显示"暂无访问权限 — 暂未开通数据权限"。
改用**笔记管理页**，每篇笔记卡片上直接显示互动数据。

### Step 1: 导航到笔记管理页
```
navigate_page → url: "https://creator.xiaohongshu.com/new/note-manager"
```

### Step 2: 确认页面加载
take_snapshot → 确认看到 "笔记管理" 标题和 "全部笔记(N)" 标签
- 如果显示 "全部笔记(0)" 但实际有帖子 → 等待几秒或点击"笔记管理"菜单项刷新
- 页面有 4 个标签：全部笔记、已发布、审核中、未通过

### Step 3: 截图抓取数据（推荐用截图而非snapshot）
```
take_screenshot → 读取每篇笔记的数据
```
**每篇笔记卡片包含：**
- 封面缩略图（左侧）
- 标题（加粗大字）
- 发布日期："发布于 YYYY年MM月DD日 HH:MM"
- 数据行（图标+数字）：👁阅读 💬评论 ❤点赞 ⭐收藏 ➡转发
- 操作按钮：权限设置、置顶、编辑、删除

**每屏约显示 3-4 篇笔记**，需要滚动查看全部。

### Step 4: 滚动查看更多笔记

**关键：页面的滚动容器是 `.content`，不是 window 也不是 `.main-container`**

```javascript
// 正确的滚动方式
evaluate_script → () => {
  const content = document.querySelector('.content');
  content.scrollBy(0, 600);
  return content.scrollTop;
}
```

错误方式（不会滚动）：
- ❌ `window.scrollBy(0, 800)` — 页面本身不滚动
- ❌ `document.querySelector('.main-container').scrollBy()` — 不是真正的滚动容器

### Step 5: 重复截图+滚动直到看完所有笔记

判断是否到底：
```javascript
evaluate_script → () => {
  const c = document.querySelector('.content');
  return { atBottom: c.scrollTop + c.clientHeight >= c.scrollHeight - 10 };
}
```

### Step 6: 计算日均阅读

**核心指标是日均阅读，不是总阅读量**（消除发布时间差异）：
```
日均阅读 = 总阅读 / (检查日期 - 发布日期 的天数)
互动率 = (点赞 + 收藏 + 评论 + 转发) / 阅读 × 100%
```

注意：发布不足1天的帖子，天数按1计算，但需标注"待观察"。

### Step 7: 记录到 performance-history.md

更新 `.claude/plugins/xhs-automation/shared/performance-history.md`：
- 更新表现数据汇总表（含日均阅读列）
- 更新日均阅读排名
- 更新内容策略洞察
- 追加检查日志（时间戳 + 关键发现）

---

## 四、异常处理（通用）

- 草稿箱弹窗遮挡 → navigate_page reload 清除
- "发布"打开新tab → list_pages + select_page 切换
- 按钮不可点击 → 等待2秒后重试
- 登录过期 → 提示用户手动登录
- snapshot 文字不全 → 改用 take_screenshot 截图读取
- 数据看板无权限 → 改用笔记管理页（见第三节）
