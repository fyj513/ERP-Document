# Scheduler 需求中枢 — 系统设计方案

> 状态：已确认灵活模式（Site Plan可调整顺序并同步Scheduler）
> 默认决策：Transfer不计价 | 排程周期：实时

---

## 一、架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DEMAND 来源层                                │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐  │
│  │   SO    │ │   MTO   │ │Transfer │ │Replenish│ │   Rework    │  │
│  │ (销售)  │ │(计划)   │ │(调拨)   │ │(补货)   │ │ (返工)     │  │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └──────┬──────┘  │
│       └─────────────┴──────────┴───────────┴─────────────┘          │
│                           │                                         │
│                    ┌──────▼──────┐                                  │
│                    │  Demand池   │  ← 所有需求统一汇聚                │
│                    │  (待排程)   │                                  │
│                    └──────┬──────┘                                  │
│                           │                                         │
├───────────────────────────┼─────────────────────────────────────────┤
│                      SCHEDULER 层（公司级大脑）                        │
│                           │                                         │
│              ┌────────────▼────────────┐                           │
│              │    Schedule 页面         │                           │
│              │  ┌─────────────────────┐ │                           │
│              │  │ 合并引擎：自动按规则 │ │                           │
│              │  │ 建议MTS/Replenishment│ │                           │
│              │  │ 合并为Candidate Job  │ │                           │
│              │  └─────────────────────┘ │                           │
│              │  ┌─────────────────────┐ │                           │
│              │  │ 优先级引擎：加权得分 │ │                           │
│              │  │ + Scheduler手动置顶  │ │                           │
│              │  └─────────────────────┘ │                           │
│              │  ┌─────────────────────┐ │                           │
│              │  │ 决策面板：确认/拆分/ │ │                           │
│              │  │ 合并/指派Site/策略   │ │                           │
│              │  └─────────────────────┘ │                           │
│              └────────────┬─────────────┘                           │
│                           │                                         │
│                    ┌──────▼──────┐                                  │
│                    │  Job 池     │  ← 已确认的Job                   │
│                    │  (已排程)   │                                  │
│                    └──────┬──────┘                                  │
│                           │                                         │
├───────────────────────────┼─────────────────────────────────────────┤
│                      SITE 层（工厂级执行）                            │
│                           │                                         │
│              ┌────────────┼────────────┐                           │
│              ▼            ▼            ▼                           │
│         ┌────────┐   ┌────────┐   ┌────────┐                      │
│         │Site A  │   │Site B  │   │Site C  │                      │
│         │Plan页面│   │Plan页面│   │Plan页面│                      │
│         └───┬────┘   └───┬────┘   └───┬────┘                      │
│             │            │            │                            │
│         ┌───▼────┐   ┌───▼────┐   ┌───▼────┐                      │
│         │ 执行Job │   │ 执行Job │   │ 执行Job │                      │
│         │(生产/  │   │(生产/  │   │(生产/  │                      │
│         │采购/   │   │采购/   │   │采购/   │                      │
│         │调拨)   │   │调拨)   │   │调拨)   │                      │
│         └────────┘   └────────┘   └────────┘                      │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

**核心设计原则：**
1. **统一入口**：所有Demand进入同一个Demand池，Scheduler在一个页面看到全局
2. **自动合并**：系统按规则自动建议合并，减少Scheduler手动操作
3. **人工决策**：关键决策（优先级置顶、紧急插单、策略选择）保留给Scheduler
4. **灵活下放**：Site Plan可调整本Site内顺序，同步回Scheduler

---

## 二、Site分配策略（核心决策）

### 2.1 问题：Demand创建时Site可能未确定

| Demand来源 | Site是否预设 | 说明 |
|-----------|-------------|------|
| **SO客户订单** | ⚠️ 可能未指定 | 销售下单时可能只填了客户和交期，Site留空或由Scheduler决定 |
| **MTO** | 跟随SO | SO确定Site后，MTO自动跟随 |
| **Transfer** | ⚠️ 一半确定 | **调入方**确定（缺料的Site），**调出方**由Scheduler决定 |
| **Replenishment** | ⚠️ 可能未指定 | 系统生成时可能只标记了"需要补货的Site"，但由哪个Site生产/采购未定 |
| **Rework** | ✅ 已确定 | 在原Site处理，不需要重新分配 |
| **Sample** | ⚠️ 可能未指定 | 研发申请时可能没指定Site，由Scheduler根据产能分配 |

### 2.2 Scheduler的Site分配职责

**分配时机**：Demand进入Schedule页面后、确认排程（创建Job）之前，必须完成Site分配。

**未分配Site的Demand状态：**
- 显示为 `site_id: null` 或 `site_id: PENDING`
- Schedule页面中以 **⚠️ 未分配Site** 标记高亮
- **不可直接创建Job**——必须先分配Site

### 2.3 Site分配决策引擎（系统建议 + Scheduler确认）

系统根据以下因子计算推荐Site：

```
推荐Site = argmax( Site得分 )

Site得分 = w1×产能匹配 + w2×距离/物流 + w3×工艺匹配 + w4×历史偏好

产能匹配 = 1 - (当前Site负荷率)  # 负荷越低得分越高
距离/物流 = f(客户距离, 调入方距离, 物流成本)  # 越近得分越高
工艺匹配 = 该产品是否需要特殊设备/工艺？该Site是否具备？
历史偏好 = 过去90天内，该产品由哪个Site生产的比例最高
```

| 因子 | 权重 | 说明 |
|------|------|------|
| 产能匹配 | 40% | 优先分配给负荷低的Site，避免超载 |
| 距离/物流 | 25% | 优先分配给离客户/调入方近的Site |
| 工艺匹配 | 25% | 某些产品只能在特定Site生产（特殊设备） |
| 历史偏好 | 10% | 保持生产稳定性，减少换线成本 |

### 2.4 各类Demand的Site分配规则

#### A. SO / MTO → Scheduler决定生产Site

```
SO创建（site_id = null）
    │
    ├── 系统计算推荐Site（A厂/B厂/C厂）
    │   └── 显示：「推荐：A厂（负荷65%，距离120km，有工艺）」
    │
    ├── Scheduler审阅
    │   ├── 接受推荐 → site_id = A厂 → 可排程
    │   ├── 更换Site → site_id = B厂 → 可排程
    │   └── 拆分多Site → SO拆分为多个Demand，分别指派不同Site
    │
    └── 分配完成后，Demand状态：site_confirmed = true
```

#### B. Transfer → Scheduler决定调出Site

```
Site B申请调入 200件 C-003
    │
    ├── 调入方已确定：Site B
    │
    ├── Scheduler检查全公司库存
    │   ├── Site C有可用库存 500件 → 推荐从C调出
    │   ├── Site A有可用库存 100件 → 备选
    │   └── 无Site有足够库存 → Transfer不可行，转为Replenishment/采购
    │
    └── Scheduler确认调出方 → 创建Transfer Job
        └── Transfer Job的site_id = "C→B"（调出→调入）
```

#### C. Replenishment → Scheduler决定生产/采购Site

```
系统生成Replenishment Demand（site_id = null）
    │
    ├── 系统计算：哪个Site生产这批货最合理？
    │   └── 考虑：产能、距离目标仓库、该产品历史生产Site
    │
    ├── Scheduler审阅推荐
    │   └── 通常批量确认（Replenishment数量多，逐条确认效率低）
    │
    └── 分配Site → 创建Job → 自动配置PO/MO
```

### 2.5 Schedule页面中的Site分配交互

#### 未分配Site的Demand展示：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ SO-1020   Global Industries   3 line items   ⚠️ Site未分配   DDL: Jun 15     │
│     [分配Site ▼]  系统推荐: A厂 (负荷65%)  [确认分配] [忽略]                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Site分配操作：

| 操作 | 作用 | 适用场景 |
|------|------|----------|
| **系统推荐** | 自动计算最优Site并高亮 | 大多数Demand |
| **下拉选择Site** | Scheduler手动指定Site | 系统推荐不合理时 |
| **批量分配** | 勾选多个Demand → 统一分配Site | Replenishment批量处理 |
| **拆分多Site** | 一个SO拆分为多个Demand，分别分配不同Site | 大单需要多Site协同 |
| **确认分配** | Site确定后，Demand可进入排程 | 分配是排程的前置条件 |

#### 全局产能视图（辅助分配决策）：

```
A厂: ████████░░░░ 65%  |  距离客户A: 120km  |  擅长: 机加工
B厂: ██████████░░ 82%  |  距离客户A: 300km  |  擅长: 注塑
C厂: ████░░░░░░░░ 35%  |  距离客户A: 80km   |  擅长: 装配
```

### 2.6 数据模型更新

**DEMAND表增加字段：**
```
site_id: string | null       # null = 未分配
site_recommended: string     # 系统推荐的Site
site_confirmed: boolean      # Scheduler是否已确认分配
site_confirmed_by: string    # 确认人
site_confirmed_at: datetime  # 确认时间
```

**TRANSFER类型的特殊处理：**
```
# Transfer Demand有两个Site相关字段
from_site_id: string | null  # 调出方（由Scheduler决定）
to_site_id: string           # 调入方（申请时已确定）
```

---

## 三、核心概念与数据模型

### 2.1 实体关系图（ER）

```mermaid
erDiagram
    DEMAND ||--o{ JOB_LINE : "triggers"
    JOB ||--|{ JOB_LINE : "contains"
    JOB ||--o{ SUB_TASK : "generates"
    JOB ||--o{ JOB_EVENT : "logs"
    SITE ||--o{ JOB : "assigned_to"
    PART ||--o{ DEMAND : "requests"
    PART ||--o{ JOB : "produces"
    SO ||--o{ DEMAND : "creates"
    SO ||--o{ JOB : "linked_via_MTO"

    DEMAND {
        string id PK
        string source_type "SO/MTO/TRANSFER/REPLENISH/REWORK/FORECAST/SAMPLE"
        string source_id "来源单据号"
        string part_id FK
        float qty "需求数量"
        float mts_qty "MTS数量"
        float mto_qty "MTO数量"
        string site_id FK "目标Site"
        date required_date "需求日期"
        int priority "优先级得分0-100"
        string status "OPEN/CONFIRMED/CLOSED"
        string merge_group_id "合并组ID"
    }

    JOB {
        string id PK
        string job_no "Job编号"
        string site_id FK
        string part_id FK
        float total_qty "总数量"
        float mts_qty "MTS部分"
        float mto_qty "MTO部分"
        int priority "Job优先级"
        string status "DRAFT/SCHEDULED/EXECUTING/PARTIAL/COMPLETED/CLOSED"
        string strategy "MAKE/BUY/TRANSFER/SUBCONTRACT"
        date planned_start "计划开工"
        date planned_end "计划完工"
        string scheduler_id "排程人"
    }

    JOB_LINE {
        string id PK
        string job_id FK
        string demand_id FK
        float qty "关联数量"
        string allocation_type "MTS/MTO"
    }

    SUB_TASK {
        string id PK
        string job_id FK
        string task_type "PO/MO/TO/RETURN"
        string ref_doc_id "关联单据号"
        string team "负责团队"
        string status "PENDING/EXECUTING/DONE"
    }

    SITE {
        string id PK
        string code "Site编码"
        string name "Site名称"
        string location "位置"
        boolean has_production "是否有产能"
        boolean has_warehouse "是否有仓库"
    }
```

### 2.2 Job状态机

```mermaid
stateDiagram-v2
    [*] --> DRAFT : 系统创建Candidate
    DRAFT --> SCHEDULED : Scheduler确认排程
    SCHEDULED --> EXECUTING : Site开始执行
    EXECUTING --> PARTIAL : 部分完工/到货
    PARTIAL --> EXECUTING : 继续执行
    PARTIAL --> COMPLETED : 全部完成
    EXECUTING --> COMPLETED : 全部完成
    COMPLETED --> CLOSED : 财务结算/归档
    DRAFT --> CANCELLED : Scheduler取消
    SCHEDULED --> CANCELLED : Scheduler取消
    EXECUTING --> ON_HOLD : 异常暂停
    ON_HOLD --> EXECUTING : 恢复
    ON_HOLD --> CANCELLED : 彻底取消
    CANCELLED --> [*]
    CLOSED --> [*]
```

**状态说明：**
| 状态 | 说明 | 谁可操作 |
|------|------|----------|
| DRAFT | 系统建议的Candidate Job，Scheduler未确认 | Scheduler可确认/修改/取消 |
| SCHEDULED | 已确认，已分配Site和策略，待执行 | Site Plan可见，可调整顺序 |
| EXECUTING | Site已开始执行（开工/已发PO等） | Site标记状态 |
| PARTIAL | 部分完成（部分完工/部分到货） | Site标记状态 |
| COMPLETED | 全部子任务完成 | 系统自动/Scheduler确认 |
| CLOSED | 财务结算完成，归档 | 系统自动 |
| ON_HOLD | 异常暂停（缺料/设备故障等） | Site或Scheduler |
| CANCELLED | 已取消 | Scheduler |

---

## 三、Schedule页面设计（公司级大脑）

### 3.1 页面布局

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Schedule 页面                                   [+新建Job] [批量确认] [刷新]  │
├─────────────────────────────────────────────────────────────────────────────┤
│  【筛选栏】                                                                  │
│  [全部 ▼] [Site: 全部 ▼] [来源: 全部 ▼] [状态: 草稿 ▼] [日期: 本周 ▼] [搜索] │
├─────────────────────────────────────────────────────────────────────────────┤
│  【Demand池 - 待处理】                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ ⚠️ 系统建议合并：SO-2025001(MTS 80) + SO-2025003(MTS 50) +        │    │
│  │    Replenish-R001(30) → Candidate Job #CJ-001 (总160件)            │    │
│  │    [确认合并] [查看详情] [拆分] [忽略]                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 🔴 MTO Job #MTO-001 | SO-2025002 | Part:A-001 | 100件 | VIP客户    │    │
│  │    优先级: 85 | 交期: 2026-05-15 | Site: A厂                        │    │
│  │    [确认排程] [调整优先级] [更换Site]                                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 🟣 样品 Job #SAM-001 | 研发申请 | Part:B-002 | 10件                 │    │
│  │    优先级: 50 | 需求日期: 2026-05-20 | Site: B厂                    │    │
│  │    [确认排程] [调整优先级] [更换Site]                                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────────────────┤
│  【已排程Job列表】                                                           │
│  优先级 │ Job编号 │ 类型 │ Part │ 数量 │ Site │ 状态 │ 交期 │ 操作          │
│  ─────────────────────────────────────────────────────────────────────       │
│  🔴 95  │ JB-001  │ MTO  │ A-001│ 100  │ A厂  │ 执行中│ 5/15 │ [查看] [置顶] │
│  🟡 75  │ CJ-001  │ MTS  │ A-001│ 160  │ A厂  │ 已排程│ 5/18 │ [查看] [置顶] │
│  🟡 70  │ TR-001  │调拨  │ C-003│ 200  │ B→C  │ 已排程│ 5/20 │ [查看] [置顶] │
│  🟢 60  │ RP-001  │补货  │ D-004│ 500  │ C厂  │ 草稿  │ 5/25 │ [确认] [编辑] │
│  🔴 99  │ RW-001  │返工  │ A-001│ 20   │ A厂  │ 执行中│ ASAP │ [查看] [紧急] │
├─────────────────────────────────────────────────────────────────────────────┤
│  【全局产能视图】                                                            │
│  A厂: ████████████░░░░ 80% | B厂: ██████░░░░░░░░░░ 40% | C厂: █████░░░░░░ 35%│
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 颜色与标记规范

| 标记 | 含义 | 颜色 |
|------|------|------|
| 🔴 红色 | MTO / 返工 / 紧急插单 | 最高优先级，必须关注 |
| 🟡 黄色 | 普通MTS / Transfer | 标准优先级 |
| 🟢 绿色 | Replenishment / 补货 | 低优先级，系统驱动 |
| 🟣 紫色 | 样品/试制 | 特殊流程，不参与合并 |
| ⚠️ 橙色 | 系统建议合并 | 需要Scheduler确认 |

### 3.3 核心操作

| 操作 | 作用 | 影响 |
|------|------|------|
| **确认排程** | Demand → Job | 生成正式Job，分配编号，进入Site Plan |
| **确认合并** | 多个Demand → 一个Job | 系统生成合并后的Job，原Demand标记为CONFIRMED |
| **拆分** | 一个Candidate Job → 多个Job | Scheduler认为不应合并时手动拆分 |
| **调整优先级** | 修改Job的priority得分 | 影响Site Plan中的执行顺序 |
| **置顶** | 无视得分，排到最前 | 紧急处理，Site Plan实时同步 |
| **更换Site** | 将Job分配到不同Site | 触发产能重新计算 |
| **更换策略** | MAKE→BUY 或 BUY→TRANSFER | 改变子任务生成逻辑 |

### 3.4 原型 v8 交互设计（最终版，已落地）

> 对应原型文件：`assets/prototypes/scheduler-page-v8.html`

#### 3.4.1 布局：55%/45% 左右分栏

```
┌──────────────────────────────────┬──────────────────────────────┐
│ ◈ SCHEDULER 合并→配置→排序→执行  │                             │
├──────────────────────────────────┼──────────────────────────────┤
│ Normal 10 | On Hold 3            │  A厂 · 深圳                  │
│ ─────────────────────────────────│  [Not Released] [Released]  │
│ 💡 系统建议: 合并 2 Demand       │  ────────────────────────── │
│   同Part可在A厂合并生产 [确认]   │  JOB-111  ▶ 执行中 60%      │
│ ─────────────────────────────────│  JOB-444  ▶ 执行中 35%      │
│ 🔗 MERGED GROUP (500件)         │  PO-201   📦 收货中 50%     │
│   SO-1001:1  RP-001             │                             │
│ [拖拽到右侧]                     │  B厂 · 东莞                  │
│ ─────────────────────────────────│  [Not Released] [Released]  │
│ SO-1001 ▶ ACME Corp   A厂 500件│  ────────────────────────── │
│   ☑ RS1234 Steel Bracket 需600 │  JOB-555  ▶ 执行中 40%      │
│   ☑ RS5678 Aluminum Housing    │  PO-967   📦 收货中 50%     │
│ SO-1003 ▶ TechCorp    A厂 300件│                             │
│   ◻ RS9012 Power Supply 需850  │  C厂 · 苏州                  │
│   ◻ RS7890 Connector Kit       │  [Not Released] [Released]  │
│ SO-1016 ▶ ⚠ 未分配    --  120件│  ────────────────────────── │
│   ◻ RS9991 Motor Housing XL    │  JOB-222  ✓ 已完成 100%     │
│   ◻ RS9993 Bearing Set         │  JOB-888  ▶ 执行中 75%      │
│                                  │  TO-002   🚚 运输中 60%     │
│ [2]项已选择 [🔗合并][✂️拆分][清除]│                             │
└──────────────────────────────────┴──────────────────────────────┘
```

#### 3.4.2 上方 Demand 池（左侧 55%）

**展开/折叠列表（解决成百上千 Demand）：**
- Demand 以可折叠行展示，默认折叠
- 点击 ▶ 展开显示 Line Items（Part / Description / OH / Demand / Qty）
- 每个 Line Item 前有 Checkbox，勾选后底部批量操作栏显示
- 批量操作：**合并为Group**、**拆分**、**清除**

**系统建议卡片：**
- 💡 合并建议：检测到同Part/同Site/同BOM的Demand可合并
- 💡 拆分建议：单Demand数量超过产能阈值，建议拆分
- 用户可「确认合并/拆分」或「忽略」

**Demand Groups：**
- 已合并的 Group 以特殊边框卡片展示（🔗 MERGED GROUP）
- Group 可直接**拖拽**到右侧 Site 列表
- 拖拽单位为 Group（不是单个 Demand）

**Normal / On Hold 标签切换：**
- Normal：常规 Demand（SO/Replenish/MTO/Transfer）
- On Hold：待处理 Demand（缺料/工艺待定/QC判定中）

#### 3.4.3 配置弹窗（拖拽后触发）

```
┌──────────────────────────────────────┐
│ 配置处理类型                         │
├──────────────────────────────────────┤
│ Demand Group: 2个Demand              │
│ Site: A厂 · 数量: 530件              │
│                                      │
│ [💼 Job]  [🛒 PO]  [🚚 TO]          │
│ (推荐)   采购       调拨             │
│ 生产/返工                            │
│                                      │
│ 数量: 530                            │
│ 优先级: [Critical ▼]                 │
│                                      │
│ 预览: 创建 Job（生产/返工）          │
│ Site: A厂 · 数量: 530件 · 优先级: CRITICAL
│ 关联Demand: SO-1001, RP-001          │
│                                      │
│              [取消]  [确认创建]      │
└──────────────────────────────────────┘
```

**设计原则：**
1. **自动推荐**：根据 (产品 × Site) 配置自动推荐类型（SO→Job/PO；MTO→Job；Transfer→TO；Replenish→PO）
2. **可手动切换**：用户可修改推荐类型，影响后续子任务生成
3. **配置完成才下发**：未点击「确认创建」前，不进入 Site 列表
4. **自动从上方移除**：确认后，相关 Demand/Line 从上方 Pool 移除，Group 消失

#### 3.4.4 下方 Site 队列（右侧 45%）

**Site 纵向排列：**
- A厂 / B厂 / C厂 各占一区块
- 每个 Site 头部有 `Not Released` / `Released` 切换按钮
- Not Released：草稿/已排程但未执行
- Released：已开工/执行中

**按优先级排序：**
- Critical（红） > High（橙） > Normal（灰）
- 同一优先级内，按 DDL 升序
- 拖拽排序体现执行优先级和依赖关系

**Site Item 展示：**
```
⋮⋮ [JOB] JOB-111  Steel Bracket Assembly  HIGH  ▶ 执行中  [██████░░░░ 60%]
     锻造✓ → 机加▶ → 热处理○
     关联Demand: SO-1001, RP-001
```
- 点击展开显示 Process 执行链路（已完成/执行中/待执行）
- 进度条直观显示执行进度

#### 3.4.5 原型 v9 设计变更（最终版）

> 对应原型文件：`assets/prototypes/scheduler-page-v9.html`

**核心变更（基于 v8 用户反馈）：**

| 变更 | v8 | v9 |
|------|-----|-----|
| 右侧布局 | Site 纵向列表（A/B/C厂） | **三列：JOB / PO / TO** |
| Site 分配 | 拖拽时选 Site | **Job 不分配 Site**（Recipe 决定），**只有 PO/TO 需要 Site** |
| 列控制 | 无 | **每列可独立隐藏/显示**（👁 眼睛图标） |
| 类型选择 | 弹窗内切换 Job/PO/TO | **拖拽到列即决定类型**，弹窗只配数量/优先级（+ Site） |
| 优先级排序 | Site 内按优先级排序 | **列内拖拽排序 = 公司级执行优先级** |

**右侧三列布局：**

```
┌──────────────────────────────────┬─────────────┬─────────────┬─────────────┐
│ 上方 Demand Pool（左侧 42%）     │    JOB      │    PO       │    TO       │
│                                  │  [👁 15]    │  [👁 2]     │  [👁 1]     │
├──────────────────────────────────┼─────────────┼─────────────┼─────────────┤
│ Normal 10 | On Hold 3            │ ⋮⋮ JOB-111  │ ⋮⋮ PO-201   │ ⋮⋮ TO-002  │
│ 💡 系统建议...                   │   530件 HIGH│   500件 NORM│   150件 NORM│
│ 🔗 MERGED GROUP                  │   ▶ 执行中  │   📦 收货中 │   🚚 运输中│
│   [拖拽到右侧列]                  │             │   📍 A厂    │   📍 C厂    │
│ SO-1001 ▶ ACME Corp   500件     │ ⋮⋮ JOB-444  │ ⋮⋮ PO-967   │             │
│   ☑ RS1234 ...                  │   2100件    │   100件     │             │
│   ◻ RS5678 ...                  │   CRITICAL  │   HIGH      │             │
│ [2]项已选择 [🔗合并][清除]       │   ▶ 执行中  │   📦 收货中 │             │
│                                  │             │   📍 B厂    │             │
└──────────────────────────────────┴─────────────┴─────────────┴─────────────┘
```

**设计原则：**
1. **Job 不需要指定 Site**：Site 分配在 Job 的 Recipe 里决定，一个 Job 可能需要多个 Site 配合完成
2. **PO/TO 必须选 Site**：采购和调拨有明确的物理目的地
3. **列即类型**：拖拽到 JOB 列 → 创建 Job；拖拽到 PO 列 → 创建 PO；拖拽到 TO 列 → 创建 TO。类型由列决定，不需要弹窗内切换
4. **列内顺序 = 优先级**：拖拽列内 item 调整顺序，表示公司级执行优先级（Site Plan 会同步）
5. **可隐藏列**：用户可点击 👁 隐藏不需要关注的列（如只关注 Job 时隐藏 PO/TO）

**配置弹窗差异：**

| 拖入列 | 弹窗标题 | Site 选择 | 其他配置 |
|--------|---------|----------|---------|
| JOB | 创建 Job | ❌ 隐藏 | 数量 + 优先级 |
| PO | 创建 PO | ✅ 必填 | 数量 + 优先级 |
| TO | 创建 TO | ✅ 必填 | 数量 + 优先级 |

---

## 四、Site Plan页面设计（工厂级执行）

### 4.1 页面布局

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Site Plan — A厂                                    [今日: 2026-05-07]      │
├─────────────────────────────────────────────────────────────────────────────┤
│  【本Site待执行Job】 拖拽调整顺序，修改会同步Scheduler                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 顺序 │ Job编号 │ Part │ 数量 │ 策略 │ 交期 │ 状态 │ 产线 │ 操作     │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │  1   │ JB-001  │A-001 │ 100  │ 生产 │ 5/15 │ 开工 │ L1   │ [完工]   │    │
│  │  2   │ CJ-001  │A-001 │ 160  │ 生产 │ 5/18 │ 待料 │ L1   │ [开工]   │    │
│  │  3   │ RW-001  │A-001 │ 20   │ 返工 │ ASAP │ 开工 │ L2   │ [完工]   │    │
│  │  4   │ RP-001  │D-004 │ 500  │ 生产 │ 5/25 │ 待排 │ --   │ [开工]   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  [上移] [下移] [置顶] [暂停] [标记异常]                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  【产线负荷甘特图】                                                          │
│  L1产线: │████JB-001████│░░░░│████CJ-001████│░░░░░░░░░░░░░░░░░░░          │
│  L2产线: │░░░░│████RW-001██│░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░          │
│  L3产线: │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░          │
├─────────────────────────────────────────────────────────────────────────────┤
│  【本Site子任务看板】                                                        │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │  待执行     │ │  执行中     │ │  已完成     │ │  异常       │          │
│  │  PO-001     │ │  MO-001     │ │  TO-001     │ │  MO-002缺料 │          │
│  │  MO-003     │ │  (开工)     │ │  (已收货)   │ │  [申请调拨] │          │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 核心操作

| 操作 | 作用 | 同步行为 |
|------|------|----------|
| **拖拽调整顺序** | 改变Job执行顺序 | 实时同步到Scheduler页面的Job优先级 |
| **开工** | Job状态 DRAFT/SCHEDULED → EXECUTING | Scheduler页面状态更新 |
| **完工** | 标记生产/采购/调拨完成 | 更新Job完成数量，触发库存更新 |
| **标记异常** | Job状态 → ON_HOLD | Scheduler页面高亮提醒 |
| **申请调拨** | 缺料时向Scheduler发起Transfer请求 | 在Scheduler页面生成新的Transfer Demand |

---

## 五、核心业务流程

### 5.1 SO-MTO 处理流程

```mermaid
flowchart TD
    A[销售创建SO] --> B{产品配置}
    B -->|MTO比例: 100%| C[系统自动创建MTO Demand]
    B -->|MTO比例: 50%| D[系统创建混合Demand<br/>MTS:50% + MTO:50%]
    C --> E[Demand池: MTO标记🔴]
    D --> F[Demand池: 混合标记]
    F --> G{系统合并检查}
    G -->|同产品+Site+时间窗| H[建议合并MTS部分到其他Job]
    G -->|不满足| I[保持独立]
    E --> J[Scheduler确认排程]
    H --> J
    I --> J
    J --> K[生成MTO Job<br/>优先级=SO优先级+10]
    K --> L[进入Site Plan]
    L --> M[Site执行生产]
    M --> N{完工}
    N -->|MTO部分| O[直接绑定SO<br/>不入库存]
    N -->|MTS部分| P[入成品库]
```

### 5.2 Transfer 处理流程

```mermaid
flowchart TD
    A[Site B发现缺料] --> B[在Site Plan提交Transfer申请]
    B --> C[Scheduler收到Transfer Demand]
    C --> D[检查全公司库存]
    D --> E{Site C有可用库存?}
    E -->|是| F[创建Transfer Job<br/>调出方: Site C, 调入方: Site B]
    E -->|否| G[Transfer不可行<br/>转为Replenishment或采购]
    F --> H[Scheduler确认排程]
    H --> I[Site C执行出库]
    I --> J[Site B执行入库]
    J --> K[关闭Transfer Job]
```

### 5.3 Replenishment 处理流程

```mermaid
flowchart TD
    A[库存低于安全线] --> B[系统自动生成Replenishment Demand]
    B --> C[系统尝试合并到现有Candidate Job]
    C --> D[生成Candidate Job草稿]
    D --> E[Scheduler页面显示🟢草稿]
    E --> F{Scheduler审阅}
    F -->|批量确认| G[Job进入SCHEDULED状态]
    F -->|调整数量| H[修改后确认]
    F -->|取消| I[Demand关闭]
    G --> J[Site Plan执行]
```

### 5.4 返工 Rework 处理流程

```mermaid
flowchart TD
    A[质检不合格 20件] --> B[原Job标记异常 ON_HOLD]
    B --> C[系统自动创建Rework Job]
    C --> D[标记🔴置顶，优先级=99]
    D --> E[Scheduler页面高亮]
    E --> F[Scheduler确认排程]
    F --> G[Site执行返工]
    G --> H{返工质检}
    H -->|合格| I[关闭Rework Job<br/>恢复原Job执行]
    H -->|不合格| J[二次返工或报废]
```

### 5.5 SO变更处理流程

```mermaid
flowchart TD
    A[SO变更: +50件] --> B[系统创建变更Demand]
    B --> C{原Job状态}
    C -->|草稿/已排程| D[系统建议: 合并到原Job]
    C -->|执行中/部分完成| E[系统建议: 创建新Job]
    D --> F[Scheduler确认合并]
    E --> G[Scheduler确认新建]
    F --> H[更新原Job数量]
    G --> I[新Job进入Demand池]
    H --> J[Site Plan同步]
    I --> J
```

---

## 六、合并引擎规则（系统自动化）

### 6.1 合并条件（ALL必须满足）

```python
def can_merge(demand_a, demand_b):
    return (
        demand_a.part_id == demand_b.part_id and      # 同一产品
        demand_a.site_id == demand_b.site_id and      # 同一Site
        demand_a.bom_version == demand_b.bom_version and  # 同一BOM
        abs(demand_a.planned_start - demand_b.planned_start) <= TIME_WINDOW and  # 时间窗内
        demand_a.mto_qty == 0 and demand_b.mto_qty == 0 and  # 无MTO（MTO不可合并）
        demand_a.quality_grade == demand_b.quality_grade and  # 质量标准兼容
        demand_a.source_type not in ['REWORK', 'SAMPLE', 'TRANSFER'] and  # 非特殊类型
        demand_b.source_type not in ['REWORK', 'SAMPLE', 'TRANSFER']
    )
```

### 6.2 时间窗配置

| 策略 | 时间窗 | 说明 |
|------|--------|------|
| 激进合并 | ±14天 | 合并机会最多，库存周转慢 |
| 标准合并（推荐） | ±7天 | 平衡合并效率与交期风险 |
| 保守合并 | ±3天 | 交期最准，但合并机会少 |

---

## 七、优先级引擎

### 7.1 计算公式

```
优先级得分 = 基础分 + 客户加权 + 交期加权 + 延迟惩罚 + 产能匹配分

基础分 = 50（中位数）
客户加权 = VIP(+20) / 普通(+0) / 内部(-10)
交期加权 = max(0, 30 - 距离交期天数)  # 越近越高
延迟惩罚 = 已延迟天数 × 5
产能匹配分 = 0~10（Site产能利用率越低，匹配分越高）

最终得分范围: 0~100+
```

### 7.2 手动覆盖

- **置顶**：Scheduler一键置顶，得分临时设为999，取消置顶后恢复计算值
- **降级**：Scheduler可手动降低某Job优先级（如战略客户不急的单）
- **锁定**：Scheduler锁定某Job的优先级，系统不再自动调整

---

## 八、与现有模块的集成

| 现有模块 | 集成点 | 影响 |
|----------|--------|------|
| **产品模块** | Part配置增加"默认MTO比例" | SO创建时自动建议MTS/MTO拆分 |
| **库存模块** | 库存水位触发Replenishment | 自动生成Demand |
| **采购模块** | Job的采购子任务生成PO | PO来源从"采购申请"扩展到"Job驱动" |
| **生产模块** | Job的制造子任务生成工单 | 生产工单来源统一为Job |

---

## 九、待后续PRD细化的内容

1. 具体的数据库Schema和API设计
2. 权限矩阵（Scheduler/Site主管/班组长的操作权限）
3. 消息通知机制（Job状态变更时通知相关人）
4. 报表与KPI（Scheduler效率、Job准时完成率、Site产能利用率）
5. 历史数据迁移策略（现有SO/PO/生产工单如何映射到Job模型）
