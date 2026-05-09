---
title: PRAM 简介
topicId: pram-intro
author: PRAM Team
version: 1.0
---

# 🎮 欢迎来到 PRAM 世界

PRAM 是 **Project Resource And Management** 的缩写，是专为高效团队打造的资源管理平台。

> 💡 核心理念：**轻松、有趣、严谨**

---

## 为什么选择 PRAM？

在快节奏的开发环境中，团队常常面临这些挑战：

- 📋 任务分散在不同工具中，难以统一管理
- 👥 团队成员之间的信息同步不及时
- 📊 项目进度缺乏可视化追踪
- 🎯 知识沉淀和传承困难

PRAM 将这些能力整合在一个平台中，让团队协作像玩游戏一样简单有趣。

---

<!-- quiz -->
**题目**：PRAM 的全称是什么？

- A. Process Resource And Management
- B. Project Resource And Management
- C. Product Resource And Management
- D. Program Resource And Management

**答案**：B

**解析**：PRAM = Project Resource And Management，这是我们项目组名字的由来。
<!-- /quiz -->

---

# 🏗️ PRAM 的三大支柱

PRAM 的设计围绕三个核心支柱展开：

## 1. 轻松（Easy）

降低使用门槛，让每个人都能快速上手：

```typescript
// 只需一行代码即可初始化
const pram = new PRAM({
  team: '我的团队',
  project: ' awesome-app'
})
```

## 2. 有趣（Fun）

融入游戏化机制，让工作不再枯燥：

| 机制 | 说明 |
|------|------|
| 经验值 | 完成任务获得 XP，升级解锁新功能 |
| 成就系统 | 「连续7天全勤」「BUG 终结者」等徽章 |
| 团队排行榜 | 良性竞争，激发团队活力 |

## 3. 严谨（Rigorous）

规范化的流程保障项目质量：

- ✅ 代码审查强制流程
- ✅ 自动化测试覆盖要求
- ✅ 文档同步检查
- ✅ 发布审批机制

---

<!-- quiz -->
**题目**：PRAM 的三大支柱不包括以下哪项？

- A. 轻松（Easy）
- B. 有趣（Fun）
- C. 快速（Fast）
- D. 严谨（Rigorous）

**答案**：C

**解析**：PRAM 的三大支柱是 **轻松、有趣、严谨**，没有「快速」。
<!-- /quiz -->

---

# 🚀 快速开始

## 安装

```bash
npm install @pram/core
```

## 初始化项目

```typescript
import { PRAM } from '@pram/core'

const app = new PRAM({
  name: '我的项目',
  team: [
    { id: 'user1', role: 'admin' },
    { id: 'user2', role: 'developer' },
  ]
})

// 创建第一个任务
app.tasks.create({
  title: '搭建项目脚手架',
  assignee: 'user2',
  priority: 'high'
})
```

---

<!-- quiz -->
**题目**：以下哪个命令用于安装 PRAM 核心库？

- A. `npm install pram`
- B. `npm install @pram/core`
- C. `npm install pram-core`
- D. `yarn add pram`

**答案**：B

**解析**：PRAM 核心库的包名是 `@pram/core`，使用 npm 安装。
<!-- /quiz -->

---

# 📚 本课小结

恭喜你完成了 PRAM 简介的学习！

## 核心知识点

1. **PRAM** = Project Resource And Management
2. **三大支柱**：轻松、有趣、严谨
3. **安装方式**：`npm install @pram/core`
4. **游戏化机制**：经验值、成就、排行榜

## 下一课预告

下一课我们将深入学习 **PRAM 核心架构**，了解平台的技术架构设计和模块划分。

---

<!-- quiz -->
**题目**：PRAM 的核心理念包含以下哪些？（多选）

- A. 轻松
- B. 有趣
- C. 严谨
- D. 便宜

**答案**：A,B,C

**解析**：PRAM 的核心理念是 **轻松、有趣、严谨**。
<!-- /quiz -->
