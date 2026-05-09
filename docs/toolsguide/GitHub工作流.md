# GitHub 工作流指南

> 本文档描述团队采用的 GitHub 协作工作流，包括 Issue 管理、分支策略、代码审核等规范。

---

## 📖 文档说明

### 适用人员

本文档适用于 **ERP 项目的所有开发人员**，包括：

- 开发工程师
- 代码审核者（Gloria）
- 终审者（Mitchell）
- 项目管理者
- 全体团队成员

### 文档核心原则

本工作流遵循以下核心原则：

1. ✅ **测试驱动开发（TDD）** — 非前端模块必须先写测试，再编码
2. ✅ **两层代码审核** — 确保功能正确和代码质量
3. ✅ **中英双语规范** — 所有代码注释和文档必须为中英双语
4. ✅ **自动化检查** — CI/CD 流程自动验证测试和代码质量

---

## 🌍 全局特殊要求

### 中英双语规范

为了提升代码国际化和可读性，**团队成员在编写代码时必须遵循纯英文双语规范**：

#### 代码注释必须双语

```python
# 正确示例 ✅
def calculate_inventory_cost():
    """
    Calculate the total cost of current inventory.
    计算当前库存的总成本。
    
    Returns:
        float: Total inventory cost in currency units
               以货币单位表示的库存总成本
    """
    pass

# 错误示例 ❌（仅中文）
def calculate_inventory_cost():
    """计算库存总成本"""
    pass

# 错误示例 ❌（仅英文）
def calculate_inventory_cost():
    """Calculate inventory total cost"""
    pass
```

#### 变量和函数名称使用英文

```python
# 正确示例 ✅
inventory_quantity = 100  # 库存数量
order_status = "pending"  # 订单状态

# 错误示例 ❌
库存数量 = 100
订单状态 = "pending"
```

#### API 文档和接口说明双语

```markdown
# 正确示例 ✅
### Create Order / 创建订单

**Request Body:**
```json
{
  "customer_id": "C001",  // 客户ID
  "items": []            // 订单项目列表
}
```

# 错误示例 ❌
### 创建订单

Request: {...}
```

#### 提交信息（Commit Message）双语

```bash
# 正确示例 ✅
git commit -m "feat(inventory): add SKU management

- Add SKU creation and deletion functionality
  添加 SKU 创建和删除功能
- Implement batch CSV import
  实现批量 CSV 导入
- Add SKU validation and error handling
  添加 SKU 验证和错误处理"

# 错误示例 ❌（仅中文）
git commit -m "添加库存管理功能"

# 错误示例 ❌（仅英文）
git commit -m "feat(inventory): add SKU management"
```

#### PR 描述双语

```markdown
# 正确示例 ✅
## Description / 改动说明
Adds SKU management feature for inventory module.
为库存模块添加 SKU 管理功能。

## Changes / 改动内容
- SKU creation and deletion
  SKU 的创建和删除
- Batch CSV import
  批量 CSV 导入
```

### 审核检查清单

代码审核时，审核者应检查双语规范的合规性：

- ⚠️ 所有函数/类的文档字符串必须双语
- ⚠️ 复杂逻辑的代码注释必须双语
- ⚠️ API 文档必须双语
- ⚠️ 如不符合，**请求更改**，直到符合要求

---

## 1. 工作流总览

```mermaid
flowchart LR
    A[创建 Issue] --> B[任务分配]
    B --> C[创建分支]
    C --> D[本地开发]
    D --> E[编写测试]
    E --> F[提交代码]
    F --> G[Pull Request]
    G --> H[Gloria 审核]
    H --> I[Mitchell 审核]
    I --> J[合并到主分支]
    
    style A fill:#e1f5ff
    style J fill:#c8e6c9
```

---

## 2. Issue 管理

### 2.1 Issue 创建

**由谁创建**：mitchell 和 gloria 负责创建 Issue

**Issue 应包含的内容**：
- 清晰的标题和描述
- 任务的优先级和模块分类
- 关键需求和验收标准
- **（如有）测试用例或测试方案**

### 2.2 Issue 分配与领取

**分配方式**：
1. Mitchell 或 Gloria 主动分配任务给开发者
2. 开发者可在阅读 Issue 后主动认领任务

**分配时标记**：
- 添加 `Assignee` 标签，指定负责开发者
- 添加优先级标签（P0、P1、P2）
- 添加模块标签（库存、采购、销售等）

---

## 3. 分支管理

### 3.1 分支命名规范

```
feature/<模块>/<功能描述>  — 新功能分支
bugfix/<模块>/<bug描述>    — bug修复分支
```

**示例**：
- `feature/inventory/add-sku-management`
- `bugfix/procurement/fix-order-calculation`

### 3.2 创建和切换分支

```bash
# 更新主分支
git checkout main
git pull origin main

# 创建新分支（基于最新的 main）
git checkout -b feature/inventory/add-sku-management
```

### 3.3 分支生命周期

- **创建**：基于 `main` 分支创建个人工作分支
- **开发**：在分支上进行代码修改和测试
- **推送**：完成工作后推送到远程仓库
- **合并**：通过 Pull Request 合并回 `main` 分支
- **清理**：PR 合并后，删除本地和远程分支

---

## 4. 本地开发环境

### 4.1 GitHub Codespaces 环境设置

**为什么用 Codespaces**：
- 一致的开发环境，避免"在我机器上能跑"的问题
- 自动配置项目依赖
- 云端开发，随处可工作

**创建 Codespaces**：

1. 在 GitHub 仓库页面，点击 `Code` → `Codespaces` → `Create codespace on <分支名>`
2. VS Code 将在浏览器中打开
3. 等待容器启动并自动安装依赖

**本地开发替代方案**：
- 可直接在本地开发环境工作
- 需自行配置和管理依赖版本
- 提交前务必在本地测试验证

---

## 5. 开发流程

### 5.1 非前端模块开发流程

#### 第一步：查看 Issue 中的测试用例

如果 Issue 已包含测试用例：
- 直接复用提供的测试用例
- 跳转到「第三步：编写代码」

#### 第二步：编写测试用例（仅当 Issue 未提供）

如果 Issue 没有提供测试用例：

```bash
# 在项目的测试目录创建测试文件
tests/
  └── test_inventory_management.py  # 测试文件

# 编写测试用例，按照 TDD（测试驱动开发）原则
# 测试用例应覆盖：
#   1. 正常场景
#   2. 边界场景
#   3. 异常处理
```

**测试编写规范**：
- 使用项目既定的测试框架（如 pytest、unittest 等）
- 测试命名清晰易懂：`test_<功能>_<场景>`
- 每个测试应该独立，不依赖执行顺序

**TDD 示例：库存创建功能**

假设 Issue 要求实现"创建库存记录"功能，但没有提供测试用例，则按以下步骤进行：

```python
# tests/test_inventory_management.py
# 文件：测试库存管理功能
# File: Test inventory management features

import pytest
from inventory.models import Inventory
from inventory.exceptions import InvalidInventoryError

class TestInventoryCreation:
    """
    Test suite for inventory creation functionality.
    库存创建功能的测试套件。
    """
    
    def test_create_inventory_with_valid_data(self):
        """
        Test creating inventory with valid data.
        使用有效数据创建库存。
        """
        inventory = Inventory(
            sku="SKU-001",          # SKU 编码
            name="Product A",       # 产品名称
            quantity=100,           # 数量
            unit_price=50.0         # 单价
        )
        
        assert inventory.sku == "SKU-001"
        assert inventory.quantity == 100
        assert inventory.total_value == 5000.0  # 100 * 50
    
    def test_create_inventory_with_zero_quantity(self):
        """
        Test creating inventory with zero quantity (boundary case).
        使用零数量创建库存（边界情况）。
        """
        inventory = Inventory(
            sku="SKU-002",
            name="Product B",
            quantity=0,
            unit_price=100.0
        )
        
        assert inventory.quantity == 0
        assert inventory.total_value == 0.0
    
    def test_create_inventory_with_negative_quantity_raises_error(self):
        """
        Test that negative quantity raises error (exception handling).
        负数数量应抛出异常（异常处理）。
        """
        with pytest.raises(InvalidInventoryError) as exc_info:
            Inventory(
                sku="SKU-003",
                name="Product C",
                quantity=-10,           # 负数 - 不合法
                unit_price=50.0
            )
        
        assert "Quantity cannot be negative" in str(exc_info.value)
        # 错误信息：数量不能为负
    
    def test_create_inventory_with_empty_sku_raises_error(self):
        """
        Test that empty SKU raises error.
        空 SKU 应抛出异常。
        """
        with pytest.raises(InvalidInventoryError) as exc_info:
            Inventory(
                sku="",                 # 空 SKU - 不合法
                name="Product D",
                quantity=50,
                unit_price=25.0
            )
        
        assert "SKU cannot be empty" in str(exc_info.value)
```

#### 第三步：运行测试（测试先行）

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_inventory_management.py

# 运行指定测试函数
pytest tests/test_inventory_management.py::test_create_inventory_with_valid_data

# 运行测试并显示详细输出
pytest -v

# 运行测试并显示打印输出
pytest -s
```

**预期结果**：**第一次运行应该失败** ❌（因为 `Inventory` 类还未实现）

```
FAILED tests/test_inventory_management.py::TestInventoryCreation::test_create_inventory_with_valid_data
    ModuleNotFoundError: No module named 'inventory.models'
```

#### 第四步：编写实现代码

根据测试用例的需求，编写业务逻辑代码，使所有测试都能通过：

```python
# src/inventory/models.py
# 库存模型定义
# Inventory model definition

from decimal import Decimal
from inventory.exceptions import InvalidInventoryError


class Inventory:
    """
    Represents an inventory record.
    表示一个库存记录。
    
    Attributes:
        sku: Stock Keeping Unit (unique identifier)
             库存单位（唯一标识符）
        name: Product name
              产品名称
        quantity: Current stock quantity
                  当前库存数量
        unit_price: Price per unit
                    单位价格
    """
    
    def __init__(self, sku: str, name: str, quantity: int, unit_price: float):
        """
        Initialize inventory with validation.
        使用验证初始化库存。
        
        Args:
            sku: SKU code (must not be empty)
                 SKU 代码（不能为空）
            name: Product name
                  产品名称
            quantity: Stock quantity (must be non-negative)
                      库存数量（必须非负）
            unit_price: Price per unit
                        单位价格
        
        Raises:
            InvalidInventoryError: If validation fails
                                   如果验证失败
        """
        # Validate SKU
        # 验证 SKU
        if not sku or not sku.strip():
            raise InvalidInventoryError("SKU cannot be empty")
        
        # Validate quantity
        # 验证数量
        if quantity < 0:
            raise InvalidInventoryError("Quantity cannot be negative")
        
        self.sku = sku
        self.name = name
        self.quantity = quantity
        self.unit_price = unit_price
    
    @property
    def total_value(self) -> float:
        """
        Calculate total inventory value.
        计算库存总价值。
        
        Returns:
            Total value (quantity * unit_price)
            总价值（数量 × 单价）
        """
        return self.quantity * self.unit_price


class InvalidInventoryError(Exception):
    """
    Exception raised for invalid inventory data.
    为无效的库存数据抛出的异常。
    """
    pass
```

运行测试验证实现：

```bash
# 运行所有测试
pytest

# 预期输出：
# tests/test_inventory_management.py::TestInventoryCreation::test_create_inventory_with_valid_data PASSED
# tests/test_inventory_management.py::TestInventoryCreation::test_create_inventory_with_zero_quantity PASSED
# tests/test_inventory_management.py::TestInventoryCreation::test_create_inventory_with_negative_quantity_raises_error PASSED
# tests/test_inventory_management.py::TestInventoryCreation::test_create_inventory_with_empty_sku_raises_error PASSED
#
# ======================== 4 passed in 0.15s ========================
```

**现在所有测试都通过了** ✅

#### 第五步：代码审视

- 检查代码质量和可读性
- 补充必要的注释和文档（中英双语）✅
- 优化性能（如有必要）
- 确保所有测试通过 ✅

```bash
# 最终验证：运行完整的测试套件
pytest tests/test_inventory_management.py -v
```

### 5.2 前端模块开发流程

前端开发按照 Issue 需求进行，通常不需要写测试用例，但需要：
- 测试 UI 界面的交互逻辑
- 验证与后端 API 的集成
- 浏览器兼容性检查

---

## 6. 提交与 Pull Request

### 6.1 本地提交

```bash
# 查看修改状态
git status

# 暂存修改（全部）
git add .

# 暂存特定文件
git add src/inventory/models.py

# 提交代码
git commit -m "feat(inventory): add SKU management feature"
```

**Commit Message 规范**：
```
<type>(<scope>): <subject>

<body>

<footer>
```

- `type`：feat(新功能)、fix(修复)、docs(文档)、style(格式)、test(测试)等
- `scope`：模块名称（inventory、procurement 等）
- `subject`：简短描述（不超过 50 字）
- `body`（可选）：详细说明
- `footer`（可选）：关闭的 Issue 编号，如 `Closes #123`

**示例**：
```
feat(inventory): add SKU management feature

- Add SKU creation and deletion functionality
- Implement batch SKU import from CSV
- Add SKU validation and error handling

Closes #42
```

### 6.2 推送到远程仓库

```bash
# 首次推送
git push -u origin feature/inventory/add-sku-management

# 后续推送
git push
```

### 6.3 创建 Pull Request（PR）

在 GitHub 仓库页面：

1. 推送分支后，GitHub 会自动提示创建 PR
2. 点击 `Create Pull Request` 按钮
3. 填写 PR 信息：
   - **标题**：清晰的功能描述
   - **描述**：说明改动内容、关联的 Issue、测试情况
   - **关联 Issue**：使用 `Closes #<Issue编号>` 自动关闭相关 Issue

**PR 描述模板**：
```markdown
## 关联 Issue
Closes #42

## 改动说明
- 添加 SKU 管理功能
- 实现批量导入 CSV
- 完成单元测试

## 测试验证
- [x] 所有单元测试通过
- [x] 集成测试通过
- [x] 手工测试验证

## 截图或演示
<!-- 如有 UI 改动，附上截图 -->
```

### 6.4 PR 状态检查

PR 创建后，自动触发 CI/CD 流程：
- ✅ **代码检查**（Linting、类型检查）
- ✅ **单元测试**（Test Suite）
- ✅ **集成测试**（如有）
- ✅ **代码覆盖率**（如设置了阈值）

**需要解决的情况**：
- 如果任何检查失败，需要修复代码并重新推送
- PR 会自动更新，不需要重新创建

---

## 7. 代码审核流程

### 7.1 首轮审核（Gloria）

Gloria 负责**功能审核**和**业务逻辑审核**：

- ✓ 功能实现是否符合 Issue 需求
- ✓ 业务逻辑是否正确
- ✓ 测试用例是否完整
- ✓ 文档是否完善

**审核方式**：
- 在 PR 页面添加 Comment 提出意见
- 使用"Request Changes"拒绝 PR（需要修改）
- 使用"Approve"批准进入下一轮审核

### 7.2 二轮审核（Mitchell）

Mitchell 负责**代码质量审核**和**最终把关**：

- ✓ 代码质量（可读性、可维护性）
- ✓ 性能问题
- ✓ 安全隐患
- ✓ 与其他模块的兼容性
- ✓ 是否符合团队规范

**审核方式**：
- 逐行代码审查
- 提出优化建议
- 批准后进行合并

### 7.3 处理审核意见

如果被要求修改：

```bash
# 修改代码
# 保存修改后
git add .
git commit -m "refactor: address review comments"
git push

# PR 会自动更新，显示最新提交
# 重新标记为"Ready for review"
```

---

## 8. 合并与发布

### 8.1 合并条件

PR 只有同时满足以下条件才能合并：

- ✅ 所有 CI/CD 检查通过
- ✅ Gloria 审核通过
- ✅ Mitchell 审核通过
- ✅ 没有代码冲突

### 8.2 执行合并

1. 所有审核通过后，点击 `Merge pull request` 按钮
2. 选择合并策略：
   - **Create a merge commit**：保留完整的分支历史（推荐）
   - **Squash and merge**：将所有提交压缩成一个
   - **Rebase and merge**：线性历史（高级）

3. 点击 `Confirm merge`

### 8.3 分支清理

合并后，GitHub 会提示删除远程分支。同时清理本地分支：

```bash
# 删除本地分支
git branch -d feature/inventory/add-sku-management

# 删除远程分支（如未自动删除）
git push origin --delete feature/inventory/add-sku-management

# 更新本地 main 分支
git checkout main
git pull origin main
```

---

## 9. 常见问题

### Q1：分支中的代码落后于 main 怎么办？

```bash
# 更新本地 main
git checkout main
git pull origin main

# 回到工作分支
git checkout feature/inventory/add-sku-management

# 合并最新的 main 代码
git merge main

# 解决冲突（如有），然后推送
git push
```

### Q2：我不小心在 main 分支上提交了代码？

```bash
# 查看提交历史
git log --oneline -5

# 取消最后一次提交（代码保留）
git reset --soft HEAD~1

# 创建新分支并提交
git checkout -b feature/new-branch
git commit -m "your message"
git push -u origin feature/new-branch
```

### Q3：PR 有冲突无法合并？

```bash
# 在本地解决冲突
git fetch origin
git merge origin/main

# 手动编辑有冲突的文件，解决冲突标记
# 然后提交和推送
git add .
git commit -m "resolve merge conflicts"
git push
```

### Q4：怎样撤销已经 Push 的提交？

```bash
# 创建一个反向提交（推荐）
git revert <commit-hash>
git push

# 或强制回退（仅在分支未合并到 main 时使用）
git reset --hard <commit-hash>
git push -f
```

---

## 10. 最佳实践

### ✅ DO（应该做）

- ✓ 频繁提交小改动，而非一次性大改动
- ✓ 编写清晰的 Commit Message 和 PR 描述
- ✓ 在提交前本地测试
- ✓ 及时处理审核意见
- ✓ 在 Issue 关闭前验证功能
- ✓ 定期拉取 main 分支的最新代码

### ❌ DON'T（不应该做）

- ✗ 直接在 main 分支上提交代码
- ✗ 长期不更新的分支（容易产生冲突）
- ✗ Commit Message 不清楚（如"fix"、"update"）
- ✗ 跳过测试直接提交
- ✗ 在 PR 中修改不相关的代码
- ✗ 代码审核后仍不修改

---

## 11. 参考链接

- [GitHub Flow Guide](https://guides.github.com/introduction/flow/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [GitHub Codespaces Documentation](https://docs.github.com/en/codespaces)
- [Git Documentation](https://git-scm.com/doc)
