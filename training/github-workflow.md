---
title: GitHub工作流
topicId: github-workflow
author: PRAM Team
version: 1.0
---

# 🌿 GitHub协作工作流

本课介绍ERP项目的GitHub协作规范，包括**Issue管理**、**分支策略**、**TDD开发**和**代码审核**流程。

---

<!-- quiz -->
**题目**：GitHub工作流的核心原则不包括以下哪项？

- A. 测试驱动开发
- B. 两层代码审核
- C. 代码注释强制英文规范
- D. 每日强制提交

**答案**：D

**解析**：核心原则是TDD、两层审核和纯英文规范，没有"每日强制提交"的要求。
<!-- /quiz -->

---

# 📝 Issue管理

**谁创建**：Mitchell和Gloria负责创建Issue

**Issue包含**：
- 清晰的标题和描述
- 优先级（P0/P1/P2）和模块标签
- 关键需求和验收标准
- 测试用例（如有）

**领取方式**：
1. 被分配后开发
2. 主动阅读Issue后认领

---

<!-- quiz -->
**题目**：Issue的优先级标签不包括？

- A. P0
- B. P1
- C. P2
- D. P3

**答案**：D

**解析**：优先级标签为P0、P1、P2三个级别，没有P3。
<!-- /quiz -->

---

# 🌿 分支管理

**命名规范**：
```
feature/<模块>/<功能>  — 新功能
bugfix/<模块>/<bug>    — Bug修复
```

**示例**：
- `feature/inventory/add-sku-management`
- `bugfix/procurement/fix-order-calculation`

**创建流程**：
```bash
git checkout main
git pull origin main
git checkout -b feature/inventory/add-sku-management
```

---

<!-- quiz -->
**题目**：修复采购模块订单计算Bug，分支名应该是？

- A. `fix/order-calculation`
- B. `bugfix/procurement/fix-order-calculation`
- C. `feature/procurement/order-calculation`
- D. `hotfix/order`

**答案**：B

**解析**：Bug修复分支格式为`bugfix/<模块>/<bug描述>`。
<!-- /quiz -->

---

# 🧪 TDD开发流程

**非前端模块**必须遵循**测试驱动开发**：

1. **查看Issue中的测试用例**（如有则直接用）
2. **编写测试**（覆盖正常、边界、异常场景）
3. **运行测试**（预期失败❌，因为代码未实现）
4. **编写实现代码**使测试通过
5. **代码审视**并补充双语注释

**前端模块**：按需求开发，无需写测试。

---

<!-- quiz -->
**题目**：TDD开发流程的正确顺序是？

- A. 写代码→写测试→运行测试
- B. 写测试→运行测试→写代码
- C. 运行测试→写测试→写代码
- D. 写代码→运行测试→写测试

**答案**：B

**解析**：TDD流程是先写测试，运行（预期失败），再写代码使测试通过。
<!-- /quiz -->

---

# 🔀 Pull Request流程

**提交规范**：
```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型**：feat(新功能)、fix(修复)、docs(文档)、test(测试)

**PR审核条件**：
- ✅ CI/CD检查通过
- ✅ Gloria审核通过（功能审核）
- ✅ Mitchell审核通过（质量审核）
- ✅ 无代码冲突

---

<!-- quiz -->
**题目**：以下哪个不是PR合并的必要条件？

- A. CI/CD检查通过
- B. Gloria审核通过
- C. 完成10个功能点
- D. 无代码冲突

**答案**：C

**解析**：合并需要CI通过、两层审核通过、无冲突，与功能点数量无关。
<!-- /quiz -->

---

# 📝 纯英文规范

**必须英文的内容**：
- 代码注释和文档字符串
- API文档和接口说明
- Commit Message
- PR描述

**变量和函数名**：使用英文

```python
# 正确 ✅
def calculate_cost():
    """Calculate total cost. """

# 错误 ❌
def 计算成本():
    """计算总成本"""
```

---

<!-- quiz -->
**题目**：以下哪项符合纯英文规范？

- A. 函数名用中文
- B. 注释只有英文
- C. 文档字符串纯英文
- D. Commit只有中文

**答案**：C

**解析**：规范要求文档字符串、注释、Commit、PR都需纯英文，函数名用英文。
<!-- /quiz -->

---

# 📚 本课小结

## 核心知识点

1. **Issue**：Mitchell/Gloria创建，含优先级和模块标签
2. **分支**：`feature/模块/功能`或`bugfix/模块/bug`
3. **TDD**：非前端模块先写测试再写代码
4. **PR**：需Gloria功能审核+Mitchell质量审核
5. **纯英文**：注释、文档、Commit、PR都纯英文

---

<!-- quiz -->
**题目**：关于代码审核流程，描述正确的是？

- A. 只需Mitchell审核即可合并
- B. Gloria负责功能审核，Mitchell负责质量审核
- C. 前端模块也需要TDD测试
- D. 可以直接在main分支提交

**答案**：B

**解析**：Gloria负责功能审核，Mitchell负责质量审核。A错误需两层审核；C错误前端无需TDD；D错误禁止直接在main提交。
<!-- /quiz -->
