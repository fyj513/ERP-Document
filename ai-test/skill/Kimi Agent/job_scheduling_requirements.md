# Job 拆分排产系统 — 需求规格说明书（第一部分）

> 版本：v1.0  
> 定位：前端与后端研发团队可直接依据本文档进行开发  
> 关联文档：《业务概念与信息架构设计》（concept_design.md）

---

# 第 1 章：概述

## 1.1 项目背景

### 1.1.1 离散制造业排产的核心矛盾

离散制造企业的生产排产长期面临一个结构性矛盾：**BOM（Bill of Materials，物料清单）天然是多层级树状结构**，它描述的是"由哪些零部件组成产品"的静态组成关系；而**排程（Scheduling）需要的是扁平化的、按执行单元组织的序列**，它描述的是"谁在什么时间做什么"的动态执行安排。这两者在数据结构、组织逻辑和关注维度上存在本质差异，直接对接往往导致系统性问题。

以汽车发动机制造为例：一台发动机由缸体、曲轴、缸盖、进排气系统四大模块组成，每个模块又包含多层子零部件，BOM 树可能深达 5 层，涉及数十个节点。但排程时，铸造车间需要同时看到缸体铸造毛坯和缸盖铸造毛坯的加工任务，以便合并安排熔炼和浇注批次；机加车间需要将所有 CNC 工序聚合后统一分配设备负荷；装配车间则需要按照"子组件完成后才能总装"的顺序组织工位。传统按 BOM 层级逐层排程的方式，完全无法满足这种"跨层级、按团队聚合"的需求。

### 1.1.2 当前系统存在的四大问题

| 问题 | 详细说明 | 造成的后果 |
|------|---------|-----------|
| **层级跳跃** | 不同 BOM 分支可能由同一团队负责。如果按 BOM 层级逐层排程，同一团队的任务被割裂到多个不连续的时段。例如铸造车间既要做缸体铸造毛坯（第 4 层），也要做缸盖铸造毛坯（另一分支的第 4 层），按层级排程会被分到两个不同的时间段，无法合并生产批次。 | 增加换型次数、浪费产能、延长生产周期 |
| **工序衔接混乱** | 子节点的生产必须完成后，父节点才能开始装配。BOM 树天然表达了这种父子依赖，但传统工单系统往往只关注单个节点，不跨节点维护依赖关系。 | "料不齐就上线"的生产事故、装配停线待料、紧急插单打乱计划 |
| **工艺方案多变** | 同一零部件在不同批量、不同交期要求下，可能走完全不同的工艺路线。例如小批量时用重力铸造（简单、成本低），大批量时用低压铸造（质量稳定、效率高）；紧急订单可能委外加工，常规订单则自制。 | 固定工艺路线无法适应灵活生产需求、计划员频繁手动调整 |
| **多人协作盲区** | 一个 Job 涉及多个团队（铸造、锻造、机加、装配、总装），传统工单往往只关注单个团队的派工。跨团队的交接点（如"铸造完成后通知机加取件"）和等待时间（如"机加等待热处理返回"）成为黑箱。 | 责任不清、交接延误无人负责、整体进度不可见 |

### 1.1.3 建设目标

本系统的建设目标是：**构建一个支持"BOM 展开 → Recipe 配置 → Process 聚合 → 排程执行"完整闭环的 Job 拆分排产系统**，解决离散制造企业中 BOM 树状结构与排程扁平化需求之间的结构性矛盾，实现：

1. **全局可视**：Job 创建后即能看到完整的物料全景和工艺路线；
2. **团队聚合**：按执行团队将分散在 BOM 不同层级的任务合并为统一派工单元；
3. **依赖显性化**：父子节点间的工艺依赖自动转化为 Process 间的有向无环图（DAG）；
4. **灵活适配**：同一 Job 内支持 MTS/MTO 混合模式，同一零件支持多 Recipe 选择；
5. **闭环反馈**：Signal 机制打通外部事件（物料到货、质检通过等）与排程引擎的联动。

---

## 1.2 设计思考

### 1.2.1 "先展开、再聚合、后排程"三段式设计哲学

本系统采用三段式设计哲学，将 BOM 到排程的转换过程拆解为三个清晰阶段：

```
┌─────────────────────────────────────────────────────────────────┐
│  第一阶段：展开（Explode）                                         │
│  ─────────────────────────────────────────────────────────────── │
│  将 Job 的 BOM 树完整展开到底，每个节点成为一个可配置单元。         │
│  输出：完整实例化的 JobBOMNode 树，包含所有中间节点和叶子节点。       │
├─────────────────────────────────────────────────────────────────┤
│  第二阶段：聚合（Group）                                           │
│  ─────────────────────────────────────────────────────────────── │
│  按 "执行团队（team）" 将 BOM 分支聚合为 Process。                   │
│  同一团队负责的连续工序 → 合并为一个排程单元。                       │
│  输出：Process 列表 + ProcessDependency 有向无环图。                 │
├─────────────────────────────────────────────────────────────────┤
│  第三阶段：排程（Schedule）                                        │
│  ─────────────────────────────────────────────────────────────── │
│  根据优先级、依赖关系、信号触发、产能约束，确定 Process 的           │
│  执行顺序与起止时间。                                               │
│  输出：带 scheduled_start / scheduled_end 的排程结果。             │
└─────────────────────────────────────────────────────────────────┘
```

这种三段式设计的核心价值在于**关注点分离**：展开阶段只关心"物料组成的完整性"，聚合阶段只关心"团队分工的合理性"，排程阶段只关心"时间和资源的优化"。每个阶段的输出是下一个阶段的输入，接口清晰，便于独立迭代和优化。

### 1.2.2 四个关键设计决策

**决策 1：BOM 直接拆分到底**

传统 MES 系统通常采用"只展开一层、逐层下推"的方式：先排产成品，下层物料作为子工单延后处理。这种方式的问题在于：排产时无法看到完整的物料全景，经常出现排产后才发现某下层零部件缺料或产能不足的情况。

本系统采用"一次性展开到底"策略：在 Job 创建阶段，就将 BOM 树完整展开为包含所有中间节点和叶子节点的 JobBOMNode 树。叶子节点（原材料/采购件）虽然不生成独立的 Process，但它们在 BOM 树中的存在明确了物料需求。这样，排程前就能发现潜在缺料风险，避免中途停线。

**决策 2：Recipe 从叶子到根倒序配置**

叶子节点（原材料/采购件）不需要配置 Recipe，因为它们不是"加工"出来的，而是"采购"或"领用"的。中间节点才需要配置 Recipe，描述如何将下层物料加工/装配为当前节点。

配置顺序采用"从叶子到根"的倒序：先配置最深层的中间节点（如"缸体铸造毛坯"），再逐层向上配置（"缸体机加工件"→"缸体组件模块"→"发动机总成"）。这种倒序符合"先加工后装配"的物理逻辑：必须先确定底层零件如何制造，才能确定上层组件如何装配。如果正向从根节点开始配置，会出现"已知装配方案但未知零件如何加工"的逻辑倒置。

**决策 3：Process 按 team group，而非按 BOM 层级 group**

传统方式按 BOM 层级排程：每个层级是一个排程单元。这种方式的问题已在"层级跳跃"中说明。

本系统按 team 聚合：跨层级的、同一 team 的节点合并为一个 Process。例如机加车间负责的"缸体机加工件"（第 3 层）、"活塞销"（第 4 层）、"曲轴"（第 3 层）等，虽然分布在 BOM 的不同层级和不同分支，但都被合并到机加车间对应的 Process 中。这样，一个 Process 对应一张派工单，现场执行者看到的是"我需要完成的全部任务列表"，而非分散在不同层级的碎片化指令。

**决策 4：Make to Stock (MTS) vs Make to Order (MTO) 混合支持**

同一 Job 内可混合两种模式：部分数量面向库存生产（MTS），部分面向客户订单生产（MTO）。系统需要分别记录每种模式的数量，因为：

- **优先级计算**：MTO 部分通常与客户交期挂钩，优先级更高；MTS 部分可以适度延后；
- **交期承诺**：MTO 部分需要承诺客户交期，MTS 部分只需满足库存补货点；
- **成本核算**：MTO 成本归属到具体客户订单，MTS 成本归属到库存成本中心。

例如某发动机 Job 生产 100 台，其中 20 台为 MTS（补充安全库存），80 台为 MTO（客户订单）。系统在排程时优先保障 MTO 的 80 台按时交付，MTS 的 20 台可在产能富余时段插单生产。

---

## 1.3 应用场景

### 场景 A：汽车发动机装配（MTS + MTO 混合）

**业务背景**：某发动机厂接到客户订单，需要生产 100 台 2.5L 柴油发动机，同时需要补充 20 台库存。发动机由缸体、曲轴、缸盖、进排气系统四大模块组成，每个模块包含多层零部件。

**系统应用流程**：

1. **创建 Job**：录入 Part Number（ENG-D250）和数量（100 台），设定 MTS=20、MTO=80，优先级 High，目标交期 2024-08-30；
2. **展开 BOM**：系统展开 5 层 BOM 树，呈现 35 个节点的完整物料树（18 个中间节点 + 17 个叶子节点）；
3. **配置 Recipe**：为 18 个中间节点逐一配置工艺路线。例如缸体铸造毛坯选择低压铸造 Recipe，缸体机加工件选择 CNC 加工 Recipe，发动机总成选择总装调试 Recipe；
4. **生成 Process**：系统自动将同一铸造车间负责的缸体铸造毛坯、主轴承盖、缸盖铸造毛坯合并为 P-CAST-01 Process；将机加车间负责的多个零件合并为 P-MC-01、P-MC-02、P-MC-03 三个 Process；
5. **排程输出**：排程引擎根据 15 个 Process 的 DAG 依赖关系、各 team 产能（铸造 2 条线、机加 5 台 CNC、装配 3 个工位、总装 1 条线），输出各 Process 的开始/结束时间。关键路径为 P-CAST-01 → P-MC-01 → P-ASSY-01 → P-ASSY-04 → P-FINAL，总工期约 22 个工作日。

**典型特征**：BOM 层级深（5 层）、涉及 team 多（6 个团队）、自制件比例高（需配置 18 个 Recipe）、MTS/MTO 混合。

### 场景 B：定制机械设备（MTO 为主，涉及委外）

**业务背景**：某食品机械厂接到客户定制订单，生产 1 台专用包装机。BOM 展开后发现多个零部件需要委外加工（表面处理、热处理）。

**系统应用流程**：

1. **创建 Job**：纯 MTO 模式，数量 1 台，优先级 Critical（客户定制交期紧）；
2. **展开 BOM**：BOM 树包含自制件和采购件，部分零件需要委外热处理；
3. **配置 Recipe**：Recipe 选择时需要区分"自制"和"委外"两种 team。例如齿轮零件的 Recipe R-HT-01 由"热处理供应商 A"执行，属于 outsource 类型；而齿轮磨削 Recipe R-GRIND-01 由"机加车间"执行，属于 internal 类型；
4. **生成 Process**：自制 Process 和委外 Process 在系统内统一建模。委外 Process（如 P-OUTSOURCE-01）的排程逻辑不同：不检查内部产能，而是校验供应商交期承诺；
5. **排程输出**：自制 Process 与委外 Process 之间存在强依赖。例如必须先完成热处理（委外）后，才能进行磨削（自制）。系统通过 ProcessDependency 显式建模这种跨组织边界的依赖关系，确保不会出现"料未到就上线"的情况。

**典型特征**：单件小批、委外环节多、自制/委外混合、依赖关系跨组织边界。

### 场景 C：批量电子组装（MTS 为主）

**业务背景**：某电子厂为双十一备货，需要生产 10,000 台智能音箱。BOM 展开后有 PCB、外壳、喇叭、电池等多个模块。

**系统应用流程**：

1. **创建 Job**：纯 MTS 模式，数量 10,000 台，优先级 Normal（按库存补货点触发）；
2. **展开 BOM**：BOM 树相对扁平（3~4 层），模块间耦合度低；
3. **配置 Recipe**：
   - PCB 由 SMT 贴片团队负责 → Recipe R-SMT-01（贴片→回流焊→AOI 检测）；
   - 外壳由注塑团队负责 → Recipe R-INJ-01（注塑→去毛刺→检验）；
   - 最终装配由组装团队负责 → Recipe R-ASSY-01（PCB 装入外壳→装喇叭→装电池→功能测试→包装）；
4. **生成 Process**：系统按 team 自动 group 为三大 Process（P-SMT-01、P-INJ-01、P-ASSY-01），分别排程。由于模块间独立性高，SMT 和注塑可以并行生产，最终装配等待两者齐套后开始；
5. **排程输出**：大批量生产适合经济批量排程。系统可将 10,000 台拆分为多个生产批次（如每批 2,000 台），按周转批量组织生产，减少在制品库存。

**典型特征**：大批量、BOM 相对扁平、模块独立性高、适合批量排程策略。

---

## 1.4 术语表

| 术语 | 英文 | 定义 |
|------|------|------|
| Job | Job | 作业/工单，参与排产的最顶层单元，一份完整的生产指令。对应数据库表 `job`。 |
| BOM | Bill of Materials | 多层级物料清单，描述产品"由哪些零部件组成"的树状结构。对应数据库表 `bom`、`bom_node`、`bom_node_relation`。 |
| BOMNode | BOM Node | BOM 中的单个节点，可以是中间节点（需配置 Recipe）或叶子节点（原材料/采购件）。对应数据库表 `bom_node`。 |
| Recipe | Recipe | 工艺路线，描述某零件"如何加工/装配"的方案，包含执行团队（team）和有序的任务列表（tasks）。对应数据库表 `recipe`、`recipe_task`。 |
| Process | Process | 排程最小单元，由同一 team 负责的、来自 BOM 不同分支的节点 group 而成。一个 Process 对应一张派工单。对应数据库表 `process`。 |
| Task | Task | Recipe 内的单个操作步骤，如"CNC 铣面"、"钻孔"。对应数据库表 `recipe_task`（模板）和 `process_task`（实例）。 |
| Part Number | Part Number | 物料编码，零件或产品在主数据中的唯一标识。对应数据库表 `part_number`。 |
| Team | Team | 执行团队/工作中心/车间，负责执行一个或多个 Process。对应数据库表 `team`。 |
| Signal | Signal | 外部信号/事件，如物料到达、质检通过、设备就绪等，可触发排程引擎重新计算或 Process 状态变更。对应数据库表 `signal`。 |
| MTS | Make to Stock | 面向库存生产，为补充库存而生产，无特定客户订单绑定。 |
| MTO | Make to Order | 面向订单生产，为特定客户订单而生产，交期与客户合同挂钩。 |
| DAG | Directed Acyclic Graph | 有向无环图，Process 间的依赖关系必须构成 DAG，否则存在循环依赖错误。 |
| JobBOMNode | Job BOM Node | Job 实例化的 BOM 节点，某 Job 中某个 BOM 节点的具体配置状态（含选中的 Recipe）。对应数据库表 `job_bom_node`。 |
| JobRecipe | Job Recipe | Job 中某节点选定的 Recipe 实例，记录具体的工艺选择历史。对应数据库表 `job_recipe`。 |
| ProcessTask | Process Task | Process 内的任务实例，由 RecipeTask 展开生成，含实际计划起止时间。对应数据库表 `process_task`。 |
| ProcessDependency | Process Dependency | Process 间的依赖关系，如"A 完成后 B 才能开始"。对应数据库表 `process_dependency`。 |

---

# 第 2 章：概念体系

## 2.1 核心概念定义

### 2.1.1 Job（作业/工单）

**概念说明**

Job 是排产系统的最顶层单元，代表一份完整的生产指令。一个 Job 描述"要生产什么产品（Part Number）、生产多少数量、什么时候需要完成"。Job 的生命周期贯穿从创建、BOM 展开、Recipe 配置、Process 生成、排程、释放到车间、执行、完成的完整过程。

**关键属性**

| 属性 | 数据类型 | 说明 |
|------|---------|------|
| job_id | String (PK) | 唯一标识，格式如 `JOB-2024-0892`，由系统自动生成 |
| part_number | FK → PartNumber | 产品型号，决定使用哪个 BOM |
| quantity_total | Integer | 总生产数量，如 100 |
| quantity_mts | Integer | Make to Stock 数量，如 20 |
| quantity_mto | Integer | Make to Order 数量，如 80 |
| priority | Enum | 优先级：Critical / High / Normal / Low，影响排程权重 |
| target_date | Date | 目标交期，排程引擎据此倒排或正排 |
| status | Enum | 状态：见第 3.3 节 Job 状态机 |
| bom_id | FK → BOM | 关联的 BOM 模板版本 |
| scheduled_start | DateTime | 排程后计算出的计划开始时间 |
| scheduled_end | DateTime | 排程后计算出的计划完成时间 |
| actual_start | DateTime | 实际开始时间（首个 Process 启动时记录） |
| actual_end | DateTime | 实际完成时间（最后一个 Process 完成时记录） |
| created_by | String | 创建人 |
| created_at | DateTime | 创建时间 |

**与其他概念的关系**

- 一个 Job 关联一个 BOM（通过 `bom_id`），BOM 展开后生成多个 **JobBOMNode**；
- 一个 Job 生成多个 **Process**（1:N）；
- 一个 Job 可收到多个 **Signal**（1:N）；
- Job 的 `part_number` 指向 **PartNumber** 主数据。

**举例**

`JOB-2024-0892`：生产 100 台 ENG-D250 柴油发动机，其中 20 台 MTS、80 台 MTO，优先级 High，目标交期 2024-08-30。该 Job 展开后生成 35 个 JobBOMNode，最终聚合为 15 个 Process。

---

### 2.1.2 BOM（物料清单）

**概念说明**

BOM 是产品的结构化物料定义，以树状结构描述"产品由哪些零部件组成，每个零部件需要多少数量"。BOM 是模板数据，不随 Job 变化。同一个 Part Number 可以有多个 BOM 版本（如 v2.2、v2.3、v3.0），但同一时间只有一个版本为 Active。

BOM 的核心特征是多层级树状结构：根节点是成品（如发动机总成），叶子节点是原材料/采购件（如铝合金锭、灰铸铁毛坯），中间节点是自制件/半成品（如缸体机加工件、活塞组）。

**关键属性**

| 属性 | 数据类型 | 说明 |
|------|---------|------|
| bom_id | String (PK) | 唯一标识 |
| part_number | FK → PartNumber | 根节点产品型号 |
| version | String | BOM 版本号，如 `v2.3` |
| version_status | Enum | Active / Obsolete / Draft，同一时间只有一个 Active |
| description | Text | 描述说明 |
| max_depth | Integer | BOM 最大深度（缓存值，方便查询） |
| total_nodes | Integer | 总节点数（缓存值） |
| created_at | DateTime | 创建时间 |

**与其他概念的关系**

- 一个 BOM 包含多个 **BOMNode**（1:N），通过 `bom_node` 表存储节点，通过 `bom_node_relation` 表存储父子关系；
- 多个 **Recipe** 通过 `applicable_part_numbers` 与 BOM 的节点间接关联；
- 一个 **Job** 选择一个 BOM 版本（N:1）。

**举例**

ENG-D250 的 BOM v2.3：根节点为"柴油发动机总成"，最大深度 5 层，共 35 个节点。BOM 树中每个节点包含 `quantity_per_parent`（父节点所需本节点数量），如每台发动机需要 1 个缸体、4 个活塞、8 个活塞销等。

---

### 2.1.3 BOMNode（BOM 节点）

**概念说明**

BOMNode 是 BOM 树中的单个节点，代表一个零部件或原材料。节点分为两类：

- **中间节点（Intermediate Node）**：有子节点的自制件/半成品，需要配置 Recipe 来描述如何加工/装配。在 UI 中用 🔵 蓝色圆圈表示。
- **叶子节点（Leaf Node）**：无子节点的原材料/采购件，不需要配置 Recipe（不是"加工"出来的，是"采购"或"领用"的）。在 UI 中用 ⬜ 灰色方块表示。

**关键属性**

| 属性 | 数据类型 | 说明 |
|------|---------|------|
| node_id | String (PK) | 唯一标识 |
| bom_id | FK → BOM | 所属 BOM |
| part_number | FK → PartNumber | 物料编码 |
| node_type | Enum | `intermediate`（中间节点）/ `leaf`（叶子节点） |
| level | Integer | 在 BOM 树中的层级，根节点 = 1 |
| quantity_per_parent | Decimal | 父节点所需本节点的数量 |
| unit | String | 计量单位（件 / kg / m 等） |
| is_configurable | Boolean | 是否需要配置 Recipe（中间节点为 true，叶子为 false） |
| default_recipe_id | FK → Recipe | 默认 Recipe（可选，加速配置） |
| drawing_no | String | 图号（可选） |

**与其他概念的关系**

- 通过 **BOMNodeRelation** 与父节点/子节点关联（N:1 父关系，1:N 子关系）；
- 中间节点可选关联一个 **Recipe**（通过 `default_recipe_id` 或运行时选择）；
- Job 创建时，每个 BOMNode 实例化为 **JobBOMNode**。

**举例**

"缸体铸造毛坯"是一个中间节点（`node_type=intermediate`，`is_configurable=true`），位于 BOM 树第 4 层。它的子节点是"铝合金锭 AL-Si10Cu"（叶子节点）。它的 `quantity_per_parent=1`，表示每台缸体机加工件需要 1 个缸体铸造毛坯。

---

### 2.1.4 Recipe（工艺路线）

**概念说明**

Recipe 是某零件的加工方案，回答"这个零件由哪个团队（team）执行、包含哪些工序步骤（tasks）、需要多长时间"。Recipe 是模板数据，同一个 Part Number 可以有多个可选 Recipe（如低压铸造 vs 重力铸造）。

Recipe 的核心属性是执行团队（`default_team_id`）和任务列表（`recipe_tasks`）。执行团队决定了该 Recipe 对应的 Process 将被聚合到哪个 team 的 Process 中。

**关键属性**

| 属性 | 数据类型 | 说明 |
|------|---------|------|
| recipe_id | String (PK) | 唯一标识 |
| recipe_code | String | 编码，如 `R-CAST-01`，便于识别 |
| name | String | 名称，如"低压铸造" |
| description | Text | 描述 |
| applicable_part_numbers | Array[String] | 适用的 Part Number 列表 |
| applicable_quantity_min | Integer | 最小适用批量 |
| applicable_quantity_max | Integer | 最大适用批量 |
| default_team_id | FK → Team | 默认执行团队 |
| version | String | 版本 |
| status | Enum | Active / Inactive |
| estimated_duration_minutes | Integer | 预估总时长（分钟），所有 Task 标准工时之和 |
| setup_time_minutes | Integer | 换型/准备时间 |
| created_at | DateTime | 创建时间 |

**与其他概念的关系**

- 一个 Recipe 包含多个 **RecipeTask**（1:N），按 `sequence_no` 排序；
- Recipe 通过 `default_team_id` 关联 **Team**；
- 运行时，Job 中的某节点通过 **JobRecipe** 记录具体选择了哪个 Recipe。

**举例**

Recipe `R-CAST-01`（低压铸造）：适用于 Part Number "缸体铸造毛坯"，适用批量 ≥ 50，执行团队为"铸造车间"，包含 6 个 Tasks：模具准备（30min）→ 熔炼（120min）→ 低压浇注（90min）→ 冷却固化（60min）→ 脱模清理（45min）→ 尺寸初检（30min），预估总时长 480 分钟。

---

### 2.1.5 Process（排程单元）

**概念说明**

Process 是排程的最小单元，由同一 team 负责的、来自 BOM 树不同分支的节点 group 而成。Process 是"可被执行的工单"——一个 Process 对应一张派工单，下发到车间后，team 按照 Process 内的 Task 序列依次执行。

Process 的生成遵循三条核心规则：
1. 同一 team 负责的、在 BOM 树中连续的分支，合并为一个 Process；
2. 如果同一 team 在不同分支上的工作存在依赖关系（必须等 A 完成才能做 B），则拆分为两个 Process；
3. 如果同一 team 的工作被其他 team 的工序隔开，则拆分为多个 Process。

**关键属性**

| 属性 | 数据类型 | 说明 |
|------|---------|------|
| process_id | String (PK) | 唯一标识 |
| process_code | String | 编码，如 `P-CAST-01` |
| job_id | FK → Job | 所属 Job |
| team_id | FK → Team | 执行团队 |
| process_name | String | 名称，如"缸体与缸盖铸造" |
| process_type | Enum | `internal`（自制）/ `outsource`（委外）/ `inspection`（检验） |
| status | Enum | 状态：pending / ready / scheduled / released / in_progress / completed / cancelled |
| sequence_no | Integer | 在 Job 内的显示排序 |
| scheduled_start | DateTime | 计划开始时间（排程后填充） |
| scheduled_end | DateTime | 计划结束时间（排程后填充） |
| actual_start | DateTime | 实际开始时间 |
| actual_end | DateTime | 实际结束时间 |
| priority_score | Float | 优先级得分（排程引擎计算） |
| notes | Text | 备注 |
| created_at | DateTime | 创建时间 |

**与其他概念的关系**

- 一个 Process 属于一个 **Job**（N:1）；
- 一个 Process 由一个 **Team** 执行（N:1）；
- 一个 Process 包含多个 **ProcessTask**（1:N）；
- Process 之间通过 **ProcessDependency** 形成 DAG（N:M）。

**举例**

`P-CAST-01`（缸体与缸盖铸造）：属于 `JOB-2024-0892`，执行团队"铸造车间"，包含 3 个节点（缸体铸造毛坯、主轴承盖、缸盖铸造毛坯），任务汇总为：模具准备→熔炼→浇注(缸体)×100→浇注(缸盖)×100→冷却→脱模→清砂→初检。前置依赖：无（原材料已到位）。后置 Process：P-MC-01（缸体机加工）、P-MC-03（缸盖机加工）。

---

### 2.1.6 Task（任务步骤）

**概念说明**

Task 是 Recipe 内的单个操作步骤，是最细粒度的工艺描述。Task 分为两层：Recipe 层面的模板（RecipeTask）和 Process 层面的实例（ProcessTask）。RecipeTask 描述"这个工序是什么、标准工时多少"；ProcessTask 描述"这个工序在这次排程中计划什么时候开始、什么时候结束、由谁执行"。

**关键属性（RecipeTask — 模板层）**

| 属性 | 数据类型 | 说明 |
|------|---------|------|
| task_id | String (PK) | 唯一标识 |
| recipe_id | FK → Recipe | 所属 Recipe |
| sequence_no | Integer | 在 Recipe 内的顺序号 |
| task_name | String | 名称，如"CNC 铣面" |
| task_type | Enum | `setup` / `machining` / `assembly` / `inspection` / `material_move` |
| description | Text | 详细说明 |
| work_center | String | 具体工作中心（可选） |
| standard_time_minutes | Integer | 标准工时（分钟/件） |
| required_skill | String | 所需技能等级 |
| inspection_type | Enum | `self`（自检）/ `mutual`（互检）/ `qc`（专检）/ `none` |

**关键属性（ProcessTask — 实例层）**

| 属性 | 数据类型 | 说明 |
|------|---------|------|
| process_task_id | String (PK) | 唯一标识 |
| process_id | FK → Process | 所属 Process |
| recipe_task_id | FK → RecipeTask | 来源的 RecipeTask |
| job_node_id | FK → JobBOMNode | 关联的 JobBOMNode |
| sequence_no | Integer | 在 Process 内的顺序 |
| task_name | String | 任务名称（继承自 RecipeTask，可覆盖） |
| planned_start | DateTime | 计划开始 |
| planned_end | DateTime | 计划结束 |
| actual_start | DateTime | 实际开始 |
| actual_end | DateTime | 实际结束 |
| status | Enum | `pending` / `in_progress` / `completed` / `skipped` |
| operator_id | String | 操作员 |

**与其他概念的关系**

- RecipeTask 属于 **Recipe**（N:1）；
- ProcessTask 属于 **Process**（N:1），继承自 **RecipeTask**；
- ProcessTask 关联 **JobBOMNode**，标记该任务是为哪个 BOM 节点执行的。

**举例**

RecipeTask："CNC 铣面"，属于 Recipe `R-MC-01`，sequence_no=1，task_type=`machining`，standard_time_minutes=45，work_center="CNC-01"。

对应的 ProcessTask：属于 Process `P-MC-01`，planned_start=2024-08-05 08:00，planned_end=2024-08-05 08:45，status=`pending`，operator_id 待分配。

---

## 2.2 实体关系总览

### 2.2.1 核心实体关系图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              核心实体关系图                                        │
└─────────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
  │  PartNumber  │◄────────┤    BOM       ├────────►│   BOMNode    │
  │  (物料主数据)  │  1:N    │  (物料清单模板) │  1:N   │  (BOM节点)    │
  └───────┬──────┘         └──────┬───────┘         └───┬──────┬───┘
          │                       │                     │      │
          │                       │                     │      │ N:1(parent)
          │                       │                     │      │
          │                  ┌────┴────┐               │      │
          │                  │  Job    │◄──────────────┘      │
          │                  │(作业/工单)│        1:N             │
          │                  └────┬────┘                      │
          │                       │                            │
          │                       │                            │
     ┌────┴────┐                  │                    ┌───────┴──────┐
     │  Team   │◄─────────────────┤                    │   Recipe     │
     │(执行团队) │              N:1 │                    │ (工艺路线模板)  │
     └────┬────┘                  │                    └───────┬──────┘
          ▲                      │                            │
          │                      │                            │ 1:N
          │                 ┌────┴────┐                      │
          │                 │ Process │◄─────────────────────┘
          └─────────────────┤(排程单元)│         N:M (via JobRecipe)
                         N:1 └────┬────┘
                                  │
                            ┌─────┴──────┐         ┌────────────────┐
                            │ProcessTask │         │ProcessDependency│
                            │(排程任务实例) │         │ (Process依赖)   │
                            └────────────┘         └────────────────┘
                                                            │
                                                            │
                            ┌──────────────┐                 │
                            │   Signal     │                 │
                            │  (外部信号)   │                 │
                            └──────────────┘                 │
                                                               │
                            ┌──────────────────────────────────┘
                            │
                            ▼
                      ┌──────────────┐
                      │   JobBOMNode │
                      │(Job BOM节点) │
                      └──────────────┘
                            │
                            │ 1:N
                            ▼
                      ┌──────────────┐
                      │  JobRecipe   │
                      │(Job Recipe选择)│
                      └──────────────┘
```

### 2.2.2 关系基数与约束详述

```
PartNumber (1) ───< (N) BOM
  - 一个物料编码可以对应多个版本的 BOM（但同一时间只有一个 Active）
  - BOM 的根节点 Part Number 指向 PartNumber

BOM (1) ───< (N) BOMNode
  - 一个 BOM 包含多个节点（完整树的所有节点平铺存储）

BOMNode (1) ───< (N) BOMNodeRelation [as parent]
BOMNode (1) ───< (N) BOMNodeRelation [as child]
  - 通过 BOMNodeRelation 表构建树状结构
  - 一个父节点可以有多个子节点
  - 一个子节点只有一个父节点（严格树结构）

BOM (1) ───< (N) Recipe (间接，通过 applicable_part_numbers)
  - 一个 BOM 的多个节点可以关联多个 Recipe

Recipe (1) ───< (N) RecipeTask
  - 一个 Recipe 包含多个有序的任务步骤

Job (1) ───< (N) JobBOMNode
  - Job 创建时，将 BOM 树完整展开，生成 JobBOMNode 实例
  - JobBOMNode 自关联形成树结构（parent_job_node_id）

JobBOMNode (N) ───> (1) Recipe [via JobRecipe]
  - 每个需要配置的 JobBOMNode 选择一个 Recipe
  - 通过 JobRecipe 中间表记录选择历史

Job (1) ───< (N) Process
  - 一个 Job 拆分为多个 Process

Team (1) ───< (N) Process
  - 每个 Process 由一个 Team 执行
  - 同一 Team 在同一 Job 中可能有多个 Process（被其他 team 的工序隔开）

Process (1) ───< (N) ProcessTask
  - 一个 Process 包含多个任务实例

Process (1) ───< (N) ProcessDependency [as predecessor]
Process (1) ───< (N) ProcessDependency [as successor]
  - Process 之间通过 ProcessDependency 形成依赖图（DAG）

Job (1) ───< (N) Signal
  - 一个 Job 可以收到多个 Signal

Process (1) ───< (N) Signal
  - Signal 可以触发特定 Process 的状态变更

Team (1) ───< (N) Recipe
  - Recipe 的默认执行 Team
```

### 2.2.3 关键关系约束汇总

| 关系 | 基数 | 约束说明 |
|------|------|---------|
| Job → JobBOMNode | 1:N | 级联创建，Job 删除时级联删除所有 JobBOMNode |
| JobBOMNode → Recipe | N:1 | 可选，叶子节点 recipe_id 为空；中间节点配置后必填 |
| Job → Process | 1:N | 级联创建，Process 由系统根据 Recipe 配置自动生成 |
| Process → Team | N:1 | 必填，每个 Process 必须有明确的执行团队 |
| Process → Process（依赖） | N:M | 通过 ProcessDependency 关联，必须构成 DAG（无环） |
| BOMNode → Recipe | N:M | 通过 applicable_part_numbers 间接关联，运行时筛选匹配 |
| JobBOMNode → JobBOMNode（父子） | 1:N | 自关联，parent_job_node_id 指向父节点，构建实例化 BOM 树 |

---

# 第 3 章：业务流程

## 3.1 完整流程示例：汽车发动机装配 Job

本节基于概念设计文档中的核心示例，详细描述一个 Job 从创建到排程的完整端到端流程。该示例覆盖系统全部核心功能，是开发团队理解业务逻辑的首要参考。

### 3.1.1 步骤 1：创建 Job

**操作人**：计划员（Planner）

**输入**：
- 客户订单信息（客户代码、订单号、交期要求）
- 库存补货需求（安全库存预警触发的 MTS 需求）

**操作**：

计划员在系统中点击"新建 Job"，进入 Step 1 页面，填写以下信息：

| 字段 | 值 | 来源/说明 |
|------|-----|----------|
| Job ID | `JOB-2024-0892` | 系统自动生成，格式 `JOB-YYYY-NNNN` |
| Part Number | `ENG-D250` | 下拉选择，从 PartNumber 主数据查询 |
| 生产数量 | 100 台 | 手动输入 |
| MTS 数量 | 20 台 | 手动输入，来自库存补货需求 |
| MTO 数量 | 80 台 | 手动输入，来自客户订单 |
| 优先级 | High | 单选，客户订单交期紧 |
| 目标交期 | 2024-08-30 | 日期选择器，客户合同要求 |
| 客户订单号 | `CO-2024-5678` | 可选，关联客户订单 |
| 备注 | "客户要求附带出厂检测报告" | 可选，多行文本 |

**校验**：
- `quantity_mts + quantity_mto = quantity_total`（20 + 80 = 100，校验通过）
- Part Number `ENG-D250` 在系统中存在且有 Active BOM
- 目标交期 ≥ 今天 + 1 天

**输出**：
- Job 记录创建，status = `DRAFT`
- 系统查询到 ENG-D250 的 Active BOM 为 v2.3
- 页面自动进入 Step 2

---

### 3.1.2 步骤 2：BOM 展开

**操作人**：计划员

**输入**：
- Job ID: `JOB-2024-0892`
- BOM ID: `BOM-ENG-D250-v2.3`

**系统处理**：

系统遍历 BOM 树，将每个 BOMNode 实例化为 JobBOMNode，构建完整的实例化 BOM 树。处理逻辑：

1. 从根节点（`ENG-D250 柴油发动机总成`）开始深度优先遍历；
2. 对每个 BOMNode，创建对应的 JobBOMNode，记录：
   - `job_id` = `JOB-2024-0892`
   - `node_id` = 原 BOMNode ID
   - `parent_job_node_id` = 父节点的 JobBOMNode ID（根节点为 null）
   - `quantity_required` = `quantity_per_parent × 生产数量`（考虑层级数量累积）
   - `quantity_completed` = 0
   - `recipe_config_status` = `pending`（中间节点）/ `skipped`（叶子节点）
   - `level` = 节点在 BOM 树中的层级

**BOM 展开结果统计**：

| 指标 | 数值 | 说明 |
|------|------|------|
| 总节点数 | 35 | 完整展开到底的所有节点 |
| 中间节点 | 18 | 需配置 Recipe 的自制件/半成品 |
| 叶子节点 | 17 | 原材料/采购件，无需配置 Recipe |
| BOM 最大深度 | 5 层 | 成品 → 模块 → 子部件 → 毛坯 → 原材料 |

**BOM 树结构**（关键分支）：

```
ENG-D250 柴油发动机总成（成品）─── level=1，中间节点，🔵
│
├─ 缸体组件模块 ─── level=2，中间节点，🔵
│   ├─ 缸体机加工件 ─── level=3，中间节点，🔵
│   │   ├─ 缸体铸造毛坯 ─── level=4，中间节点，🔵
│   │   │   └─ 铝合金锭 AL-Si10Cu ─── level=5，叶子节点，⬜
│   │   ├─ 主轴承盖 ─── level=4，中间节点，🔵
│   │   │   └─ 灰铸铁毛坯 HT250 ─── level=5，叶子节点，⬜
│   │   └─ 缸体螺栓套件 ─── level=4，叶子节点，⬜
│   ├─ 活塞组 ─── level=3，中间节点，🔵
│   │   ├─ 活塞 ─── level=4，中间节点，🔵
│   │   │   └─ 铝合金棒料 AL-4032 ─── level=5，叶子节点，⬜
│   │   ├─ 活塞销 ─── level=4，中间节点，🔵
│   │   │   └─ 合金钢管 20CrMnTi ─── level=5，叶子节点，⬜
│   │   └─ 活塞环 ─── level=4，叶子节点，⬜
│   └─ 连杆组 ─── level=3，中间节点，🔵
│       ├─ 连杆体 ─── level=4，中间节点，🔵
│       │   └─ 锻钢毛坯 42CrMo ─── level=5，叶子节点，⬜
│       └─ 连杆轴承 ─── level=4，叶子节点，⬜
│
├─ 曲轴组件模块 ─── level=2，中间节点，🔵
│   ├─ 曲轴 ─── level=3，中间节点，🔵
│   │   ├─ 曲轴毛坯 ─── level=4，中间节点，🔵
│   │   │   └─ 球墨铸铁 QT700-2 ─── level=5，叶子节点，⬜
│   │   └─ 主轴瓦 ─── level=4，叶子节点，⬜
│   └─ 飞轮 ─── level=3，中间节点，🔵
│       └─ 铸铁圆盘 HT300 ─── level=4，叶子节点，⬜
│
├─ 缸盖组件模块 ─── level=2，中间节点，🔵
│   ├─ 缸盖机加工件 ─── level=3，中间节点，🔵
│   │   ├─ 缸盖铸造毛坯 ─── level=4，中间节点，🔵
│   │   │   └─ 铝合金锭 AL-Si7Mg ─── level=5，叶子节点，⬜
│   │   └─ 气门座圈 ─── level=4，叶子节点，⬜
│   ├─ 气门组 ─── level=3，中间节点，🔵
│   │   ├─ 进气门 ─── level=4，中间节点，🔵
│   │   │   └─ 耐高温钢棒 21-4N ─── level=5，叶子节点，⬜
│   │   ├─ 排气门 ─── level=4，中间节点，🔵
│   │   │   └─ 耐高温钢棒 Inconel 751 ─── level=5，叶子节点，⬜
│   │   └─ 气门弹簧 ─── level=4，叶子节点，⬜
│   └─ 凸轮轴 ─── level=3，中间节点，🔵
│       ├─ 凸轮轴毛坯 ─── level=4，中间节点，🔵
│       │   └─ 冷硬铸铁棒 CHC-1 ─── level=5，叶子节点，⬜
│       └─ 凸轮轴轴承 ─── level=4，叶子节点，⬜
│
└─ 进排气系统模块 ─── level=2，中间节点，🔵
    ├─ 进气歧管 ─── level=3，中间节点，🔵
    │   ├─ 歧管注塑件 ─── level=4，中间节点，🔵
    │   │   └─ PA66-GF30 原料 ─── level=5，叶子节点，⬜
    │   └─ 节气门体 ─── level=4，叶子节点，⬜
    ├─ 排气歧管 ─── level=3，中间节点，🔵
    │   ├─ 歧管铸钢件 ─── level=4，中间节点，🔵
    │   │   └─ 铸钢毛坯 ZG25Cr20Ni14 ─── level=5，叶子节点，⬜
    │   └─ 氧传感器 ─── level=4，叶子节点，⬜
    └─ 涡轮增压器 ─── level=3，叶子节点，⬜
```

**输出**：
- 35 个 JobBOMNode 记录创建
- Job status 变为 `BOM_SELECTED`
- 页面进入 Step 3

---

### 3.1.3 步骤 3：Recipe 倒序配置

**操作人**：工艺工程师 / 计划员

**输入**：
- 已展开的 JobBOMNode 树（35 个节点，其中 18 个中间节点待配置）
- Recipe 主数据（系统中已维护的工艺路线模板）

**配置原则**：从叶子到根倒序配置，先配置最深层的中间节点，逐层向上。

#### 第 1 轮：配置第 4 层节点（最接近原材料的中间节点）

系统按 `level` 降序排列待配置节点，默认选中第一个节点。本轮涉及 12 个第 4 层中间节点：

**节点：缸体铸造毛坯**
- Part Number: 缸体铸造毛坯，材质: AL-Si10Cu，批量: 100
- 系统筛选匹配的 Recipe（根据 `applicable_part_numbers` + `applicable_quantity_min/max`）：

| Recipe ID | 名称 | Team | Tasks 数量 | 预估工时 | 适用条件 |
|-----------|------|------|-----------|---------|---------|
| R-CAST-01 | 低压铸造 | 铸造车间 | 6 | 480 min | 批量 ≥ 50 |
| R-CAST-02 | 重力铸造 | 铸造车间 | 5 | 360 min | 批量 < 50 |
- **选择**：R-CAST-01（批量 100 适用）
- 系统记录 JobRecipe，标记该 JobBOMNode status = `configured`

**节点：主轴承盖**
- 匹配 Recipe：R-CAST-03（砂型铸造，铸造车间，5 tasks）

**节点：活塞**
- 匹配 Recipe：R-FORGE-01（热锻 + 精车，锻造车间，7 tasks）

**节点：活塞销**
- 匹配 Recipe：R-TURN-01（数控车削，机加车间，4 tasks）

**节点：连杆体**
- 匹配 Recipe：R-FORGE-02（模锻 + 数控加工，锻造车间，8 tasks）

**节点：曲轴毛坯**
- 匹配 Recipe：R-CAST-04（壳型铸造，铸造车间，6 tasks）

**节点：飞轮**
- 匹配 Recipe：R-TURN-02（车削 + 钻孔，机加车间，5 tasks）

**节点：缸盖铸造毛坯**
- 匹配 Recipe：R-CAST-01（低压铸造，铸造车间，6 tasks）

**节点：进气门 / 排气门**
- 匹配 Recipe：R-FORGE-03（热锻 + 高频淬火，锻造车间，6 tasks）
- 两个节点共用同一 Recipe（同一 Part Number 族）

**节点：凸轮轴毛坯**
- 匹配 Recipe：R-CAST-05（离心铸造，铸造车间，5 tasks）

**节点：歧管注塑件**
- 匹配 Recipe：R-INJ-01（注塑成型，注塑车间，4 tasks）

**节点：歧管铸钢件**
- 匹配 Recipe：R-CAST-06（熔模铸造，精密铸造车间，7 tasks）

#### 第 2 轮：配置第 3 层节点

本轮涉及 7 个第 3 层中间节点：

**节点：缸体机加工件**
- 前置依赖：缸体铸造毛坯（子节点）已配置 R-CAST-01
- 匹配 Recipe：R-MC-01（CNC 铣面→钻孔→镗缸→精铣，机加车间，4 tasks）

**节点：活塞组（装配）**
- 前置依赖：活塞、活塞销、活塞环齐套
- 匹配 Recipe：R-ASSY-01（压装活塞销→装活塞环→检验，装配车间，3 tasks）

**节点：连杆组（装配）**
- 前置依赖：连杆体、连杆轴承齐套
- 匹配 Recipe：R-ASSY-02（压装轴承→螺栓拧紧→检验，装配车间，3 tasks）

**节点：曲轴**
- 前置依赖：曲轴毛坯已完成
- 匹配 Recipe：R-MC-02（车削→磨削→动平衡→精磨，机加车间，4 tasks）

**节点：缸盖机加工件**
- 匹配 Recipe：R-MC-03（CNC 铣面→钻气道→镗气门座→精铣，机加车间，4 tasks）

**节点：气门组（装配）**
- 匹配 Recipe：R-ASSY-03（装气门座→装气门→装弹簧→气密检验，装配车间，4 tasks）

**节点：凸轮轴**
- 匹配 Recipe：R-MC-04（车削→凸轮磨削→精磨轴颈，机加车间，3 tasks）

#### 第 3 轮：配置第 2 层节点

本轮涉及 4 个第 2 层中间节点（模块级）：

**节点：缸体组件模块**
- 前置依赖：缸体机加工件、活塞组、连杆组齐套
- 匹配 Recipe：R-ASSY-04（装活塞连杆→入缸体→装轴承盖→扭矩检验，装配车间，4 tasks）

**节点：曲轴组件模块**
- 匹配 Recipe：R-ASSY-05（装主轴瓦→装曲轴→装飞轮→转动检验，装配车间，4 tasks）

**节点：缸盖组件模块**
- 匹配 Recipe：R-ASSY-06（装气门组→装凸轮轴→调气门间隙→缸盖试漏，装配车间，4 tasks）

**节点：进排气系统模块**
- 匹配 Recipe：R-ASSY-07（装进气歧管→装排气歧管→装增压器→管路连接，装配车间，4 tasks）

#### 第 4 轮：配置第 1 层节点（根节点）

**节点：ENG-D250 柴油发动机总成**
- 前置依赖：四大模块（缸体组件、曲轴组件、缸盖组件、进排气系统）齐套
- 匹配 Recipe：R-FINAL-01（总装→冷磨→热试→调整→终检→入库，总装车间，10 tasks）
- Tasks 明细：缸体曲轴合装→装缸盖→装进排气系统→装附件→冷磨合→热试→调整→喷漆→终检→入库

**Recipe 配置完成汇总**：

| 层级 | 节点数 | Recipe 数量 | 涉及 Team |
|------|--------|------------|----------|
| 第 4 层 | 12 | 12 | 铸造、锻造、机加、注塑、精密铸造 |
| 第 3 层 | 7 | 7 | 机加、装配 |
| 第 2 层 | 4 | 4 | 装配 |
| 第 1 层 | 1 | 1 | 总装 |
| **合计** | **24** | **24** | **6 个 Team** |

> 注：中间节点共 18 个，但表中出现 24 是因为部分节点（如进气门/排气门共用 R-FORGE-03）分别计数。实际配置节点数为 18。

**输出**：
- 18 个 JobRecipe 记录创建
- 所有中间节点 JobBOMNode status = `configured`
- Job status 保持 `RECIPE_CFG`（等待用户确认完成）

---

### 3.1.4 步骤 4：Process 生成

**操作人**：系统自动化（用户点击"生成 Process"触发）

**输入**：
- Job ID: `JOB-2024-0892`
- 已配置 Recipe 的 JobBOMNode 树（18 个已配置节点 + 17 个叶子节点）
- Team 映射：每个已配置节点 → 其 Recipe 的 `default_team_id`

**系统处理**：Process 生成算法执行 7 个步骤：

**算法步骤 1：构建 Team-Annotated BOM Tree**
遍历 JobBOMNode 树，为每个中间节点标注 `team_id`：
- 叶子节点：无 team（不生成 Process）
- 中间节点：从选定的 Recipe 获取 `default_team_id`

**算法步骤 2：自底向上识别 Team 连续区间**
从叶子向根遍历，判断每个节点是否与其子节点同 team：
- 缸体铸造毛坯（team=铸造）的子节点是铝合金锭（无 team）→ 不合并
- 缸体机加工件（team=机加）的子节点缸体铸造毛坯（team=铸造）→ team 不同 → 不合并
- 缸体组件模块（team=装配）的子节点：缸体机加工件（team=机加）、活塞组（team=装配）、连杆组（team=装配）→ 至少一个子节点同 team → 与活塞组、连杆组所在 Process 合并

**算法步骤 3：向上聚合（Group）**
对标记为"新 Process"的节点，检查父节点和兄弟节点：
- 如果父节点同 team → 加入父节点的 Process
- 如果兄弟节点同 team 且也是"新 Process"→ 合并为同一 Process
- 否则 → 创建独立新 Process

**算法步骤 4：建立 Process 间依赖关系**
遍历每个 Process 包含的节点，分析父子依赖：
- 节点 N 的父节点 P 在 Process Pp 中，且 Pp ≠ N 的 Process → Pp 是 N 的 Process 的前置依赖（finish_to_start）
- 节点 N 的子节点 C 在 Process Pc 中，且 Pc ≠ N 的 Process → N 的 Process 是 Pc 的前置依赖

**算法步骤 5：依赖图校验**
- 检查 Process 依赖图是否构成 DAG（有向无环图）
- 如果存在环 → 报错（Recipe 配置有逻辑错误）
- 拓扑排序验证可达性

**算法步骤 6：Process 内 Task 展开**
对每个 Process：
- 收集包含的所有 JobBOMNode
- 按 BOM 层级（从深到浅）排序
- 对每个节点，展开其 Recipe 的 RecipeTask 列表
- 按 sequence_no 拼接为 ProcessTask 序列

**算法步骤 7：持久化**
将 Process、ProcessTask、ProcessDependency 写入数据库。

**生成的 15 个 Process**：

| 序号 | Process 编码 | 名称 | Team | 包含节点数 | 预估时长 | 前置依赖 |
|------|-------------|------|------|-----------|---------|---------|
| 1 | P-CAST-01 | 缸体与缸盖铸造 | 铸造车间 | 3 | 14 天 | 无 |
| 2 | P-CAST-02 | 曲轴与凸轮轴铸造 | 铸造车间 | 2 | 10 天 | 无 |
| 3 | P-CAST-03 | 排气歧管精密铸造 | 精密铸造车间 | 1 | 12 天 | 无 |
| 4 | P-FORGE-01 | 活塞与连杆锻造 | 锻造车间 | 2 | 8 天 | 无 |
| 5 | P-FORGE-02 | 气门锻造 | 锻造车间 | 2 | 6 天 | 无 |
| 6 | P-MC-01 | 缸体机加工 | 机加车间 | 2 | 12 天 | P-CAST-01 |
| 7 | P-MC-02 | 曲轴与飞轮机加工 | 机加车间 | 2 | 15 天 | P-CAST-02 |
| 8 | P-MC-03 | 缸盖与凸轮轴机加工 | 机加车间 | 2 | 13 天 | P-CAST-01, P-CAST-02 |
| 9 | P-INJ-01 | 进气歧管注塑 | 注塑车间 | 1 | 5 天 | 无 |
| 10 | P-ASSY-01 | 活塞与连杆组件装配 | 装配车间 | 2 | 4 天 | P-FORGE-01, P-MC-01 |
| 11 | P-ASSY-02 | 气门组与缸盖组件装配 | 装配车间 | 2 | 5 天 | P-FORGE-02, P-MC-03 |
| 12 | P-ASSY-03 | 曲轴组件装配 | 装配车间 | 1 | 3 天 | P-MC-02 |
| 13 | P-ASSY-04 | 进排气系统装配 | 装配车间 | 1 | 3 天 | P-INJ-01, P-CAST-03 |
| 14 | P-ASSY-05 | 缸体组件装配 | 装配车间 | 1 | 4 天 | P-ASSY-01 |
| 15 | P-FINAL | 发动机总装与调试 | 总装车间 | 1 | 5 天 | P-ASSY-02, P-ASSY-03, P-ASSY-04, P-ASSY-05 |

**输出**：
- 15 个 Process 记录
- 约 30+ 个 ProcessDependency 记录
- 50~200 个 ProcessTask 记录（取决于 Recipe 展开）
- Job status 变为 `READY`（待排程）

---

### 3.1.5 步骤 5：排程

**操作人**：系统自动化（排程引擎）+ 计划员确认

**输入**：
- 15 个 Process + ProcessDependency DAG
- Team 产能数据：铸造车间 2 条线、机加车间 5 台 CNC、装配车间 3 个工位、总装车间 1 条线、精密铸造车间 1 条线、注塑车间 2 台注塑机、锻造车间 2 条线
- Job 优先级：High（权重系数 1.5）
- Signal：原材料已齐套（无需等待采购）

**排程引擎处理**：

1. **拓扑排序**：按 DAG 依赖关系确定 Process 的先后约束顺序；
2. **正向排程（ASAP）**：从第一个无前置依赖的 Process 开始，按最早可开始时间排程；
3. **反向排程（Target-Based）**：从目标交期（2024-08-30）倒排，确定每个 Process 的最晚必须开始时间；
4. **产能校验**：检查每个 Team 在排程时段内的负荷是否超过产能，如超载则后延或拆分；
5. **关键路径计算**：找出决定总工期的最长 Process 链。

**排程结果**：

```
Week 1        Week 2        Week 3        Week 4        Week 5
|-------------|-------------|-------------|-------------|-------------|
[P-CAST-01    ]              
[P-CAST-02    ]
              [P-CAST-03    ]
[P-FORGE-01   ]
[P-FORGE-02   ]
              [P-MC-01      ]
              [P-MC-02      ]
              [P-MC-03      ]
[P-INJ-01     ]
              [P-ASSY-01    ]
              [P-ASSY-02    ]              
                             [P-ASSY-03    ]
                             [P-ASSY-04    ]
                             [P-ASSY-05    ]
                                            [P-FINAL        ]
```

**关键路径**：`P-CAST-01 → P-MC-01 → P-ASSY-01 → P-ASSY-04 → P-FINAL`，共约 22 个工作日。

**输出**：
- 每个 Process 的 `scheduled_start` 和 `scheduled_end`
- Job 的 `scheduled_start` = P-CAST-01.scheduled_start
- Job 的 `scheduled_end` = P-FINAL.scheduled_end
- Job status 变为 `SCHEDULED`

---

## 3.2 业务流程图

### 3.2.1 主流程（mermaid 风格描述）

```
[计划员] 点击"新建 Job"
    │
    ▼
┌─────────────┐
│  Step 1     │  输入：产品型号、数量、MTS/MTO、优先级、交期
│  创建 Job   │  输出：Job 记录（status=DRAFT）
│             │  校验：Part Number 存在性、数量>0、MTS+MTO=总量
└──────┬──────┘
       │ 点击"下一步"
       ▼
┌─────────────┐
│  Step 2     │  输入：选择 BOM 版本
│  选择 BOM   │  系统处理：完整展开 BOM 为 JobBOMNode 树
│             │  输出：35 个 JobBOMNode（18 中间 + 17 叶子）
│             │  status=BOM_SELECTED
└──────┬──────┘
       │ 点击"确认 BOM"
       ▼
┌─────────────┐
│  Step 3     │  输入：倒序配置 Recipe（从叶子到根）
│ 配置 Recipe │  系统处理：筛选匹配的 Recipe 列表
│             │  操作：为每个中间节点选择 Recipe，创建 JobRecipe
│             │  输出：18 个 JobRecipe 记录
│             │  status=RECIPE_CFG
└──────┬──────┘
       │ 点击"完成配置"
       ▼
┌─────────────┐
│  Step 4     │  系统处理：Process 生成算法
│ 生成 Process│  输出：15 个 Process + ProcessTask + ProcessDependency
│             │  status=READY
└──────┬──────┘
       │ 点击"执行排程"
       ▼
┌─────────────┐
│  排程引擎   │  输入：Process DAG + Team 产能 + 优先级 + Signal
│  计算排程   │  输出：每个 Process 的 scheduled_start/end
│             │  status=SCHEDULED
└──────┬──────┘
       │ 计划员确认排程结果
       ▼
┌─────────────┐
│ 释放到车间 │  输出：派工单下发到各 Team
│             │  status=RELEASED
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 车间执行   │  Team 按计划执行 Process，反馈实际进度
│             │  status=IN_PROGRESS → COMPLETED
└─────────────┘
```

### 3.2.2 各步骤输入/输出/操作人汇总

| 步骤 | 步骤名称 | 操作人 | 系统操作 | 输入 | 输出 | 状态变更 |
|------|---------|--------|---------|------|------|---------|
| 1 | 创建 Job | 计划员 | 生成 Job ID，校验输入 | 产品型号、数量、优先级、交期 | Job 记录 | → DRAFT |
| 2 | 选择 BOM | 计划员 | 展开 BOM 为 JobBOMNode | BOM 版本选择 | 35 个 JobBOMNode | → BOM_SELECTED |
| 3 | 配置 Recipe | 工艺工程师/计划员 | 筛选匹配 Recipe | 点击选择 Recipe | 18 个 JobRecipe | → RECIPE_CFG |
| 4 | 生成 Process | 系统（用户触发） | Process 生成算法 | 已配置 JobBOMNode 树 | 15 个 Process | → READY |
| 5 | 排程 | 系统（用户触发） | 排程引擎计算 | Process DAG + 产能 + 优先级 | 排程结果 | → SCHEDULED |
| 6 | 释放执行 | 计划员 | 下发派工单 | 排程确认 | 派工单 | → RELEASED |
| 7 | 车间执行 | 车间操作员 | 进度采集 | 实际执行反馈 | 实际进度 | → IN_PROGRESS → COMPLETED |

---

## 3.3 状态流转

### 3.3.1 Job 状态机

**状态定义**：

| 状态 | 英文 | 说明 | 进入条件 |
|------|------|------|---------|
| DRAFT | 草稿 | Job 刚创建，基础信息已录入 | 创建 Job 后自动进入 |
| BOM_SELECT | BOM 选择中 | 正在选择 BOM 版本 | 点击"选择 BOM"后进入 |
| RECIPE_CFG | Recipe 配置中 | 正在倒序配置 Recipe | 确认 BOM 后进入 |
| READY | 待排程 | Recipe 配置完成，可参与排程 | 所有中间节点已配置 Recipe |
| SCHEDULED | 已排程 | 排程引擎已计算起止时间 | 排程引擎运行后进入 |
| RELEASED | 已释放 | 已下发到车间执行 | 计划员点击"释放到车间" |
| IN_PROGRESS | 执行中 | 至少一个 Process 已开始执行 | 首个 Process 启动后进入 |
| COMPLETED | 已完成 | 所有 Process 全部完成 | 最后一个 Process 完成后进入 |
| ON_HOLD | 暂停 | 因故暂停执行 | 执行中手动暂停 |
| PARTIAL | 部分完成 | 部分 Process 完成，部分未开始 | 特殊场景 |
| CANCELLED | 已取消 | Job 被取消 | 任何状态（需权限） |

**状态流转图（ASCII）**：

```
                        ┌─────────────┐
                        │   DRAFT     │  ←── 草稿
                        │  （刚创建）   │
                        └──────┬──────┘
                               │ 用户点击"选择 BOM"
                               ▼
                        ┌─────────────┐
                        │ BOM_SELECT  │  ←── BOM 选择中
                        │ （展开 BOM树）│
                        └──────┬──────┘
                               │ 用户确认 BOM
                               ▼
                        ┌─────────────┐
                        │  RECIPE_CFG │  ←── Recipe 配置中
                        │ （倒序配置）  │
                        └──────┬──────┘
                               │ 所有中间节点已配置 Recipe
                               ▼
                        ┌─────────────┐
                        │  READY      │  ←── 待排程
                        │ （可参与排程） │
                        └──────┬──────┘
                               │ 排程引擎运行
                               ▼
                        ┌─────────────┐
                        │  SCHEDULED  │  ←── 已排程
                        │ （排程完成）  │
                        └──────┬──────┘
                               │ 释放到车间执行
                               ▼
                        ┌─────────────┐
                        │  RELEASED   │  ←── 已释放
                        │ （已下发工单） │
                        └──────┬──────┘
                               │ 第一个 Process 开始
                               ▼
                  ┌──────────────────────────┐
                  │       IN_PROGRESS        │  ←── 执行中
                  │    （至少一个 Process      │
                  │        已开始执行）         │
                  └────────────┬─────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
      ┌──────────┐    ┌──────────┐    ┌──────────┐
      │ ON_HOLD  │    │  PARTIAL │    │COMPLETED │  ←── 完成
      │ （暂停）  │    │ （部分完成）│    │（全部完成） │
      └────┬─────┘    └────┬─────┘    └──────────┘
           │             │
           │ 恢复         │
           └──────┬──────┘
                  ▼
           ┌──────────┐
           │IN_PROGRESS│  ←── 恢复执行
           └──────────┘

特殊转换：
─────────────────────────────────────────
• 任何状态 ──→ CANCELLED（取消）：管理员权限，已释放后不可直接取消
• READY ──→ SCHEDULED：系统自动（排程引擎定时任务）
• SCHEDULED ──→ READY：手动取消排程（修改后重新排程）
• IN_PROGRESS ──→ ON_HOLD：手动暂停（如物料短缺、设备故障）
• ON_HOLD ──→ IN_PROGRESS：手动恢复
```

**状态转换规则**：

| 转换 | 触发条件 | 执行人 | 校验 |
|------|---------|--------|------|
| DRAFT → BOM_SELECT | 点击"选择 BOM" | 计划员 | Job 基础信息完整 |
| BOM_SELECT → RECIPE_CFG | 确认 BOM 版本 | 计划员 | BOM 版本为 Active |
| RECIPE_CFG → READY | 所有中间节点 configured | 系统自动 | 无 pending 节点 |
| READY → SCHEDULED | 排程引擎运行 | 系统 | Process DAG 无环、产能数据可用 |
| SCHEDULED → RELEASED | 点击"释放到车间" | 计划员 | 排程结果已确认 |
| RELEASED → IN_PROGRESS | 首个 Task 开始执行 | 系统 | 车间反馈开工 |
| IN_PROGRESS → COMPLETED | 所有 Process 完成 | 系统 | 全部 Task 状态=completed |
| IN_PROGRESS → ON_HOLD | 手动暂停 | 计划员/主管 | 有权限 |
| 任何 → CANCELLED | 取消 Job | 管理员 | Job 未全部完成 |

---

### 3.3.2 Process 状态机

**状态定义**：

| 状态 | 说明 | 进入条件 |
|------|------|---------|
| PENDING | 待创建 | Process 生成前的初始状态 |
| READY | 可排程 | Process 已生成，等待排程 |
| SCHEDULED | 已排程 | 排程引擎已分配起止时间 |
| RELEASED | 已释放 | 派工单已下发到 Team |
| IN_PROGRESS | 执行中 | Team 已开始执行该 Process |
| COMPLETED | 已完成 | Process 内所有 Task 完成 |
| CANCELLED | 已取消 | Process 被取消 |

**状态流转图（ASCII）**：

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌──────────┐    ┌──────────┐
│ PENDING │───►│  READY  │───►│SCHEDULED│───►│RELEASED  │───►│IN_PROGRESS│
│ （待创建） │    │（可排程）  │    │（已排程）  │    │（已释放）  │    │（执行中）   │
└─────────┘    └────┬────┘    └─────────┘    └──────────┘    └────┬─────┘
                    ▲                                            │
                    │            ┌──────────┐                    │
                    └────────────┤ COMPLETED│◄───────────────────┘
                                 │（已完成）  │    所有 Task 完成
                                 └──────────┘
```

**Process 状态与 Job 状态的联动**：

| Job 状态 | Process 状态分布 | 说明 |
|---------|-----------------|------|
| READY | 全部 READY | 等待排程 |
| SCHEDULED | 全部 SCHEDULED | 排程完成 |
| RELEASED | 全部 RELEASED | 已下发 |
| IN_PROGRESS | 部分 IN_PROGRESS，部分 RELEASED/SCHEDULED | 逐步开工 |
| COMPLETED | 全部 COMPLETED | 全部完成 |

---

### 3.3.3 Recipe 配置状态（JobBOMNode 级别）

**状态定义**：

| 状态 | 说明 | 图标 |
|------|------|------|
| PENDING | 待配置，等待用户选择 Recipe | 🔵 |
| CONFIGURED | 已配置 Recipe | 🔵✓ |
| SKIPPED | 跳过（叶子节点或特殊场景） | ⬜ |

**状态流转图（ASCII）**：

```
┌─────────┐         ┌───────────┐         ┌──────────┐
│ PENDING │────────►│CONFIGURED │────────►│ SKIPPED  │
│（待配置） │         │（已配置）   │         │（跳过）   │
│  🔵 圆圈  │         │  🔵✓ 对勾  │         │  ⬜ 方块   │
└─────────┘         └───────────┘         └──────────┘
        ▲                                          │
        └──────────────────────────────────────────┘
                      可取消配置，回到待配置状态
```

**状态转换规则**：

| 转换 | 触发条件 | 说明 |
|------|---------|------|
| PENDING → CONFIGURED | 用户选择 Recipe 并确认 | 系统创建 JobRecipe 记录 |
| CONFIGURED → PENDING | 用户取消配置 | 删除 JobRecipe 记录，恢复为待配置 |
| PENDING → SKIPPED | 系统标记（叶子节点） | 叶子节点自动标记为 skipped |
| SKIPPED → PENDING | 不支持 | 叶子节点无需配置 |

---


# 第 4 章：UI/UX 设计

## 4.1 页面布局总览

### 4.1.1 整体布局结构

系统采用经典的三段式布局：顶部导航栏 + 左侧边栏 + 右侧主内容区。整体风格为工业制造系统常见的"功能导向、信息密集"型设计，强调操作效率和数据可读性。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  顶部导航栏 (height: 56px)                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  [Logo] Job 拆分排产系统              [当前 Job: JOB-2024-0892]     │    │
│  │                                        [通知] [用户: 张计划] [设置] │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
├──────────┬──────────────────────────────────────────────────────────────────┤
│          │                                                                    │
│  左侧     │  右侧主内容区（根据当前步骤切换）                                   │
│  边栏     │                                                                    │
│ (380px)  │  ┌──────────────────────────────────────────────────────────┐   │
│          │  │  步骤指示器（Step Indicator）                               │   │
│  ┌──────┐│  │  ┌────────┐ ┌────────┐ ┌────────────┐ ┌────────────┐  │   │
│  │      ││  │  │ Step 1 │→│ Step 2 │→│   Step 3   │→│   Step 4   │  │   │
│  │ Job  ││  │  │ 基础信息│ │ BOM选择 │ │ Recipe配置  │ │ 预览与排程  │  │   │
│  │ 列表 ││  │  │   ●    │ │   ●    │ │     ●      │ │     ○      │  │   │
│  │      ││  │  └────────┘ └────────┘ └────────────┘ └────────────┘  │   │
│  ├──────┤│  └──────────────────────────────────────────────────────────┘   │
│  │ 新建 ││                                                                    │
│  │ Job  ││  ═══════════════════════════════════════════════════════════   │
│  ├──────┤│                                                                    │
│  │ 最近 ││  【当前步骤对应的页面内容】                                         │
│  │ 访问 ││                                                                    │
│  │ 列表 ││                                                                    │
│  ├──────┤│                                                                    │
│  │ 帮助 ││                                                                    │
│  └──────┘│                                                                    │
│          │                                                                    │
├──────────┴────────────────────────────────────────────────────────────────────┤
│  底部状态栏 (height: 32px)                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  [Job 状态: RECIPE_CFG]  [最后保存: 2024-08-01 14:32:05]  [提示:   │    │
│  │   请继续配置剩余 10 个节点的 Recipe]                                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.1.2 顶部导航栏

| 元素 | 说明 | 规格 |
|------|------|------|
| Logo + 系统名称 | 固定显示 | 左侧，font-size: 18px, font-weight: 600 |
| 当前 Job 信息 | 显示当前打开的 Job ID | 居中偏左，格式 `JOB-2024-0892 · ENG-D250 · 100台` |
| 通知铃铛 | 显示未读通知数量（红点） | 右侧，点击展开通知面板 |
| 用户信息 | 当前登录用户 | 右侧下拉菜单：个人设置、退出登录 |

### 4.1.3 左侧边栏（380px）

| 区域 | 内容 | 交互 |
|------|------|------|
| Job 列表入口 | 图标 + "Job 列表"文字 | 点击进入 Job 列表页 |
| 新建 Job 按钮 | 主按钮样式 | 点击打开 Step 1 创建页面 |
| 最近访问 | 最近打开的 5 个 Job | 点击快速切换 |
| 帮助入口 | 图标 + "帮助"文字 | 点击打开帮助文档/快捷键 |

### 4.1.4 底部状态栏

| 元素 | 说明 | 示例值 |
|------|------|--------|
| 当前 Job 状态 | 后端 status 的中文映射 | "Recipe 配置中" |
| 最后保存时间 | 自动保存的时间戳 | "最后保存: 2024-08-01 14:32:05" |
| 操作提示 | 上下文相关的提示文字 | "请继续配置剩余 10 个节点的 Recipe" |

### 4.1.5 步骤指示器（Step Indicator）

步骤指示器位于主内容区顶部，横向排列 4 个步骤。每个步骤显示：编号、名称、状态圆点。

**步骤定义**：

| 步骤 | 名称 | 后端状态对应 | 说明 |
|------|------|-------------|------|
| Step 1 | 基础信息 | DRAFT | 创建 Job，录入基础信息 |
| Step 2 | BOM 选择 | DRAFT → BOM_SELECTED | 选择 BOM 版本，展开 BOM 树 |
| Step 3 | Recipe 配置 | RECIPE_CFG | 倒序配置各节点的 Recipe |
| Step 4 | 预览与排程 | READY → SCHEDULED | 预览 Process，执行排程 |

**步骤状态样式**：

| 状态 | 视觉表现 | 说明 |
|------|---------|------|
| 已完成 | ● 实心圆（主题色） | 步骤已完成，可点击回溯 |
| 进行中 | ● 实心圆（主题色）+ 标题高亮 | 当前所在步骤 |
| 待完成 | ○ 空心圆（灰色） | 后续步骤，不可点击 |
| 有错误 | ● 实心圆（红色） | 步骤中存在校验错误 |

```
已完成 ────  ┌────────┐
             │ Step 1 │  ● = 主题色实心圆，标题 = 主题色
             │ 基础信息│  可点击回溯
             └────────┘

进行中 ────  ┌────────────┐
             │   Step 3   │  ● = 主题色实心圆 + 脉冲动画
             │ Recipe配置  │  标题 = 主题色加粗
             └────────────┘

待完成 ────  ┌────────────┐
             │   Step 4   │  ○ = 灰色空心圆
             │ 预览与排程  │  标题 = 灰色
             └────────────┘
```

**步骤导航规则**：
- 已完成步骤可点击回溯；
- 进行中步骤是当前页面；
- 待完成步骤不可点击（需完成当前步骤后自动进入）；
- 从已完成步骤返回修改后，后续步骤的状态需要重新校验（如修改 Step 1 的数量后，Step 3 的 Recipe 匹配可能需要重新校验）。

---

## 4.2 Step 1：Job 基础信息录入

### 4.2.1 页面结构

```
┌────────────────────────────────────────────────────────────────┐
│ Step 1: 基础信息录入                                            │
│ 请填写 Job 的基本信息，所有带 * 的字段为必填项                    │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────────────────────────────────────────────┐     │
│  │ 基础信息（必填）                                       │     │
│  │                                                       │     │
│  │  Job ID               [ JOB-2024-0892          ] 只读 │     │
│  │                                                       │     │
│  │  产品型号 (Part Number)                               │     │
│  │  [ 🔍 搜索 Part Number 或输入关键字...          ] *  │     │
│  │  [ ENG-D250 - 2.5L 柴油发动机 ]                        │     │
│  │                                                       │     │
│  │  生产数量              [        100              ] *  │     │
│  │  单位                 [ 台 ]  只读                    │     │
│  │                                                       │     │
│  │  生产模式：                                           │     │
│  │  ○ 全部 Make to Stock (面向库存)                       │     │
│  │  ○ 全部 Make to Order (面向订单)                       │     │
│  │  ● 混合模式 ◄──────────────────────────────          │     │
│  │    ├─ MTS 数量: [        20        ] 件               │     │
│  │    └─ MTO 数量: [        80        ] 件               │     │
│  │    合计: 100 件  ✓                                   │     │
│  │                                                       │     │
│  │  优先级               [ ● Critical  ] ○ High          │     │
│  │                       ○ Normal  ○ Low                 │     │
│  │                                                       │     │
│  │  目标交期             [ 📅 2024-08-30            ] *  │     │
│  │                                                       │     │
│  │  备注                 [ 多行文本输入框...          ]  │     │
│  │                       0/500 字                       │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐     │
│  │ 扩展信息（可选）                                       │     │
│  │                                                       │     │
│  │  客户订单号           [ 输入                       ]  │     │
│  │                                                       │     │
│  │  关联图纸/附件        [ 📎 点击上传或拖拽到此处     ]  │     │
│  │                       支持 PDF, DWG, STEP 格式        │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                                │
│                                         [ 取消 ] [ 保存草稿 ]  │
│                                         [        下一步 ──>  ] │
└────────────────────────────────────────────────────────────────┘
```

### 4.2.2 表单字段详细定义

#### 字段 1：Job ID

| 属性 | 值 |
|------|-----|
| 标签 | Job ID |
| 数据类型 | String |
| 控件类型 | 文本输入框（只读） |
| 默认值 | 系统自动生成，格式 `JOB-YYYY-NNNN` |
| 校验规则 | 不可编辑 |
| 说明 | 系统按创建顺序自动生成唯一标识 |

#### 字段 2：Part Number（产品型号）

| 属性 | 值 |
|------|-----|
| 标签 | 产品型号 (Part Number) |
| 数据类型 | String (FK → PartNumber) |
| 控件类型 | 可搜索下拉框（ComboBox / Select） |
| 必填 | 是 |
| 占位文字 | "搜索 Part Number 或输入关键字..." |
| 搜索触发 | 输入 ≥ 2 个字符后触发模糊搜索 |
| 搜索结果格式 | `{part_number} - {part_name}`（如 `ENG-D250 - 2.5L 柴油发动机`） |
| 校验规则 | ① 必填；② 选中的 Part Number 必须存在且有至少一个 Active BOM |
| 错误提示 | "该产品型号没有可用的 BOM，请先维护 BOM 数据" |
| 联动效果 | 选中后，系统自动查询该 Part Number 的 Active BOM 版本列表 |

#### 字段 3：生产数量

| 属性 | 值 |
|------|-----|
| 标签 | 生产数量 |
| 数据类型 | Integer |
| 控件类型 | 数字输入框 |
| 必填 | 是 |
| 默认值 | 空 |
| 最小值 | 1 |
| 最大值 | 999999 |
| 步进 | 1 |
| 单位 | "台"（根据 Part Number 的默认单位自动带出） |
| 校验规则 | ① 必填；② 正整数；③ 1 ~ 999999 |
| 错误提示 | "请输入有效的生产数量（1-999999）" |
| 联动效果 | 修改后自动更新 MTS + MTO 的合计校验 |

#### 字段 4：生产模式（MTS / MTO）

| 属性 | 值 |
|------|-----|
| 标签 | 生产模式 |
| 数据类型 | Enum + Integer |
| 控件类型 | 单选按钮组 + 条件展示的数字输入框 |
| 必填 | 是 |
| 选项 | ① 全部 MTS；② 全部 MTO；③ 混合模式 |
| 默认值 | 混合模式 |
| 混合模式子字段 | MTS 数量（数字输入框）、MTO 数量（数字输入框） |
| 校验规则 | ① `MTS 数量 + MTO 数量 = 生产数量`；② MTS 和 MTO 均为 ≥ 0 的整数 |
| 实时校验 | 输入 MTS/MTO 时实时显示合计数量，不匹配时标红提示 |
| 错误提示 | "MTS 数量 + MTO 数量 必须等于生产数量（当前：X + Y ≠ Z）" |

#### 字段 5：优先级

| 属性 | 值 |
|------|-----|
| 标签 | 优先级 |
| 数据类型 | Enum |
| 控件类型 | 单选按钮组（横向排列） |
| 必填 | 是 |
| 选项 | Critical（紧急）/ High（高）/ Normal（中）/ Low（低） |
| 默认值 | Normal |
| 视觉区分 | Critical = 红色圆点，High = 橙色圆点，Normal = 蓝色圆点，Low = 灰色圆点 |
| 说明 | 影响排程引擎的权重系数和 Process 的 priority_score |

#### 字段 6：目标交期

| 属性 | 值 |
|------|-----|
| 标签 | 目标交期 |
| 数据类型 | Date |
| 控件类型 | 日期选择器 |
| 必填 | 是 |
| 默认值 | 空 |
| 最小日期 | 今天 + 1 天 |
| 校验规则 | ① 必填；② 必须 ≥ 今天 + 1 天 |
| 错误提示 | "目标交期必须至少为明天" |

#### 字段 7：备注

| 属性 | 值 |
|------|-----|
| 标签 | 备注 |
| 数据类型 | String |
| 控件类型 | 多行文本输入框（Textarea） |
| 必填 | 否 |
| 最大长度 | 500 字符 |
| 占位文字 | "请输入备注信息..." |
| 字符计数 | 右下角显示 "0/500" |

#### 字段 8：客户订单号（扩展信息）

| 属性 | 值 |
|------|-----|
| 标签 | 客户订单号 |
| 数据类型 | String |
| 控件类型 | 文本输入框 |
| 必填 | 否 |
| 说明 | 用于 MTO 场景，关联客户订单 |

#### 字段 9：关联图纸/附件（扩展信息）

| 属性 | 值 |
|------|-----|
| 标签 | 关联图纸/附件 |
| 数据类型 | File |
| 控件类型 | 文件上传区（支持点击和拖拽） |
| 必填 | 否 |
| 支持格式 | PDF, DWG, STEP, JPG, PNG |
| 最大文件大小 | 50MB |
| 多文件 | 最多 5 个文件 |

### 4.2.3 按钮定义

| 按钮 | 说明 | 点击行为 | 校验 |
|------|------|---------|------|
| 取消 | 放弃当前 Job | 弹出确认对话框 → 确认后删除 Job 草稿 → 返回 Job 列表页 | 无 |
| 保存草稿 | 保存但不进入下一步 | 保存当前表单数据 → Job status = DRAFT → 显示"保存成功"提示 → 留在当前页 | 仅校验必填字段不为空 |
| 下一步 | 完成 Step 1 | 校验全部必填字段 → 保存数据 → 进入 Step 2 | 全部必填字段校验通过 |

### 4.2.4 自动保存机制

- 表单输入后 5 秒无操作，自动触发保存；
- 保存时 Job status 保持 DRAFT；
- 底部状态栏显示"自动保存成功"；
- 网络异常时显示"保存失败，请检查网络连接"，不影响用户继续编辑。

---

## 4.3 Step 2：BOM 选择

### 4.3.1 页面结构

```
┌────────────────────────────────────────────────────────────────┐
│ Step 2: 选择 BOM                                                │
│ 选择要使用的 BOM 版本，系统将完整展开为可配置的节点树              │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────────────────────────────────────────────┐     │
│  │ BOM 版本选择                                          │     │
│  │                                                       │     │
│  │ 可用版本：                                             │     │
│  │  ● BOM v2.3  (Active, 2024-06-15 更新)                │     │
│  │    更新说明：优化了缸盖铸造毛坯的铝合金材质规格          │     │
│  │                                                       │     │
│  │  ○ BOM v2.2  (Obsolete, 2024-03-01 更新)              │     │
│  │  ○ BOM v3.0  (Draft, 2024-08-01 更新)  ← [预览]       │     │
│  │                                                       │     │
│  │  [刷新列表]                                           │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐     │
│  │ BOM 树预览                                            │     │
│  │                                                       │     │
│  │  ▼ ENG-D250 柴油发动机总成                             │     │
│  │    │  Part: ENG-D250  │  Qty: 1  │  自制件             │     │
│  │    ├─ ▼ 缸体组件模块                                   │     │
│  │    │    │  Part: ASM-BLOCK  │  Qty: 1  │  自制件        │     │
│  │    │    ├─ ▼ 缸体机加工件                                │     │
│  │    │    │    │  Part: MC-BLOCK  │  Qty: 1  │  自制件    │     │
│  │    │    │    ├─ ▼ 缸体铸造毛坯                             │     │
│  │    │    │    │    │  Part: CAST-BLOCK │ Qty:1 │ 自制件  │     │
│  │    │    │    │    └─ ⬜ 铝合金锭 AL-Si10Cu                │     │
│  │    │    │    │         Part: AL-Si10Cu │ Qty:25kg │ 采购件│    │
│  │    │    │    └─ ⬜ 缸体螺栓套件                            │     │
│  │    │    │         Part: BOLT-KIT-01 │ Qty:1 │ 采购件      │     │
│  │    │    ├─ ▼ 活塞组                                       │     │
│  │    │    │    ├─ ▼ 活塞                                    │     │
│  │    │    │    │    └─ ⬜ 铝合金棒料 AL-4032                 │     │
│  │    │    │    ├─ ▼ 活塞销                                  │     │
│  │    │    │    │    └─ ⬜ 合金钢管 20CrMnTi                  │     │
│  │    │    │    └─ ⬜ 活塞环                                  │     │
│  │    │    ...（可展开/折叠）                                 │     │
│  │    ...                                                     │     │
│  │                                                            │     │
│  │  图例: 🔵 需要配置 Recipe (18)   ⬜ 叶子节点 (17)           │     │
│  │        总计: 35 节点    最大深度: 5 层                      │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐     │
│  │ BOM 统计摘要                                          │     │
│  │                                                       │     │
│  │  ┌────────────┐  ┌────────────┐  ┌─────────────────┐ │     │
│  │  │  中间节点   │  │  叶子节点   │  │    总节点数      │ │     │
│  │  │    18      │  │    17      │  │       35        │ │     │
│  │  └────────────┘  └────────────┘  └─────────────────┘ │     │
│  │                                                       │     │
│  │  需配置 Recipe: 18 个                                 │     │
│  │  预估涉及 Team: 铸造、锻造、机加、装配、总装、注塑      │     │
│  │  BOM 最大深度: 5 层                                    │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                                │
│  [ <── 上一步 ]                          [ 确认 BOM 并继续 ──> ]│
└────────────────────────────────────────────────────────────────┘
```

### 4.3.2 BOM 版本选择区

**BOM 版本卡片**：

| 属性 | 说明 |
|------|------|
| 版本号 | 如 "BOM v2.3" |
| 状态标签 | Active（绿色）/ Obsolete（灰色）/ Draft（橙色） |
| 更新日期 | 版本创建日期 |
| 更新说明 | 版本变更简述 |
| 选择方式 | 单选（Radio），同一时间只能选一个版本 |

**版本选择规则**：
- 默认选中最新 Active 版本；
- Obsolete 版本可选但需警告提示；
- Draft 版本仅管理员可选；
- 选中版本后，BOM 树预览区自动刷新。

### 4.3.3 BOM 树渲染规则

**节点渲染样式**：

| 节点类型 | 图标 | 颜色 | 可展开 | 背景 |
|---------|------|------|--------|------|
| 中间节点（待配置） | 🔵 蓝色空心圆 | `#1890ff` | 是（有子节点） | 白色 |
| 中间节点（已配置） | 🔵✓ 蓝色圆+对勾 | `#1890ff` + `#52c41a` | 是 | 淡蓝色背景 `#e6f7ff` |
| 中间节点（当前选中） | 🔵◐ 蓝色圆+高亮边框 | `#1890ff` + `#faad14` | 是 | 黄色边框 `#faad14` |
| 叶子节点 | ⬜ 灰色方块 | `#bfbfbf` | 否 | 白色 |

**节点展开/折叠**：
- 点击节点左侧的 ▼/▶ 图标切换展开/折叠状态；
- 默认展开前 2 层，第 3 层及以下默认折叠；
- 展开/折叠状态保存在前端 State 中，不影响后端数据。

**节点信息展示**：
每个节点行显示：图标 + Part Number + 节点名称 + 数量信息 + 类型标签

```
格式示例：
▶ 🔵 缸体铸造毛坯          Qty: 1 × 100 = 100    [自制件]
  │      │                          │                │
  │      │                          │                └── 节点类型（自制件/采购件）
  │      │                          └── 数量（单位用量 × 总数量）
  │      └── Part Name
  └── 节点类型图标（🔵中间节点 / ⬜叶子节点）
```

### 4.3.4 按钮定义

| 按钮 | 说明 | 点击行为 |
|------|------|---------|
| 上一步 | 返回 Step 1 | 保存当前 BOM 选择 → 回到 Step 1 |
| 确认 BOM 并继续 | 确认选择的 BOM | 校验已选择 Active BOM → 系统展开 BOM 生成 JobBOMNode → status=BOM_SELECTED → 进入 Step 3 |

### 4.3.5 边界情况处理

| 场景 | 处理方式 |
|------|---------|
| Part Number 无可用 BOM | 显示空状态提示："该产品型号没有可用的 BOM，请先维护 BOM 数据。" 提供链接跳转到 BOM 维护页面 |
| BOM 展开后无中间节点（全是叶子） | 显示提示："该 BOM 全部为采购件，无需 Recipe 配置，可直接排程。" 跳过 Step 3 直接进入 Step 4 |
| BOM 展开后节点数 > 100 | 显示性能警告："BOM 节点较多，展开可能需要较长时间。" 提供"逐层展开"选项 |

---

## 4.4 Step 3：Recipe 配置（核心交互）

Step 3 是整个系统的核心交互步骤，采用"从左到右"的双面板布局：左侧为 BOM 树导航，右侧为 Recipe 配置区。

### 4.4.1 页面结构

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Step 3: 配置 Recipe                                                       │
│ 请从叶子节点向根节点倒序配置 Recipe。系统已按最优顺序排列，请依次完成。     │
├───────────────────────────────┬──────────────────────────────────────────┤
│                               │                                          │
│  BOM 树（左侧面板）             │  Recipe 配置区（右侧面板）                │
│  宽: 45%                      │  宽: 55%                                 │
│                               │                                          │
│  ▼ ENG-D250 发动机总成          │  ┌────────────────────────────────────┐ │
│   ├─ ▼ 缸体组件模块             │  │  当前配置节点                        │ │
│   │    ├─ ▼ 缸体机加工件        │  │                                    │ │
│   │    │    ├─ 🔵 缸体铸造毛坯   │  │  缸体铸造毛坯                       │ │
│   │    │    │    ◄── 当前选中   │  │  Part: CAST-BLOCK-001              │ │
│   │    │    │    └─ ⬜ 铝合金锭  │  │  材质: AL-Si10Cu                   │ │
│   │    │    └─ ⬜ 螺栓套件       │  │  批量: 100 件                      │ │
│   │    ├─ ▼ 活塞组              │  │  层级: 第 4 层                     │ │
│   │    │    ├─ 🔵✓ 活塞         │  │                                    │ │
│   │    │    │   └─ ⬜ ...       │  │  适用条件：批量 ≥ 50               │ │
│   │    │    ├─ 🔵 活塞销        │  │                                    │ │
│   │    │    └─ ⬜ 活塞环        │  │  ┌──────────────────────────────┐  │ │
│   │    └─ 🔵 连杆组             │  │  │ 【可选 Recipe】               │  │ │
│   │         ├─ 🔵 连杆体        │  │  │                              │  │ │
│   │         └─ ⬜ 连杆轴承      │  │  │ ┌──────────────────────────┐ │  │ │
│   ├─ ▼ 曲轴组件模块             │  │  │ │ ● R-CAST-01 低压铸造     │ │  │ │
│   │    ├─ ▼ 曲轴                │  │  │ │   Team: 铸造车间          │ │  │ │
│   │    │    ├─ 🔵✓ 曲轴毛坯     │  │  │ │   Tasks: 6 道工序        │ │  │ │
│   │    │    │   └─ ⬜ ...       │  │  │ │   预估: 480 分钟         │ │  │ │
│   │    │    └─ ⬜ 主轴瓦        │  │  │ │   [查看详情 ▼]           │ │  │ │
│   │    └─ 🔵✓ 飞轮              │  │  │ └──────────────────────────┘ │  │ │
│   ...                         │  │  │                              │  │ │
│                               │  │  │ ┌──────────────────────────┐ │  │ │
│   图例:                       │  │  │ │ ○ R-CAST-02 重力铸造     │ │  │ │
│   🔵 待配置                    │  │  │ │   Team: 铸造车间          │ │  │ │
│   🔵✓ 已配置                   │  │  │ │   Tasks: 5 道工序        │ │  │ │
│   🔵◐ 当前选中                 │  │  │ │   预估: 360 分钟         │ │  │ │
│   🔵⊘ 已跳过                   │  │  │ │   适用: 批量 < 50        │ │  │ │
│   ⬜ 叶子节点                  │  │  │ │   [查看详情 ▼]           │ │  │ │
│                               │  │  │ └──────────────────────────┘ │  │ │
│                               │  │  │                              │  │ │
│                               │  │  │ [  确认选择  ] [  跳过  ]     │  │ │
│                               │  │  └──────────────────────────────┘  │ │
│                               │  │                                    │ │
│                               │  │  ┌──────────────────────────────┐  │ │
│                               │  │  │  配置进度                      │  │ │
│                               │  │  │  ████████░░░░░░░░░░  8/18 完成 │  │ │
│                               │  │  │  已完成: 铸造毛坯、曲轴毛坯...  │  │ │
│                               │  │  │  下一个: 主轴承盖              │  │ │
│                               │  │  │  剩余: 10 个                   │  │ │
│                               │  │  └──────────────────────────────┘  │ │
│                               │  │                                    │ │
├───────────────────────────────┴──────────────────────────────────────────┤
│  [ <── 上一步 ]              [ 保存进度 ]  [ 完成配置，去预览 ──> ]        │
└──────────────────────────────────────────────────────────────────────────┘
```

### 4.4.2 左侧面板 — BOM 树导航

**功能说明**：
左侧 BOM 树用于导航和展示配置状态。树按"从深到浅"的倒序排列展示，当前待配置的节点自动高亮。

**树节点状态说明**：

| 状态 | 图标 | CSS 样式 | 说明 |
|------|------|---------|------|
| 待配置 | 🔵 | `color: #1890ff; border: 2px solid #1890ff; background: #fff` | 等待用户配置 |
| 已配置 | 🔵✓ | `color: #1890ff; background: #f6ffed; border-color: #52c41a` | 已选择 Recipe |
| 当前选中 | 🔵◐ | `color: #1890ff; box-shadow: 0 0 0 3px #faad14; border-color: #faad14` | 当前正在配置的节点 |
| 已跳过 | 🔵⊘ | `color: #bfbfbf; border-color: #d9d9d9; text-decoration: line-through` | 手动跳过 |
| 叶子节点 | ⬜ | `color: #bfbfbf; background: #f5f5f5` | 无需配置 |

**树的交互行为**：

| 操作 | 行为 |
|------|------|
| 点击节点 | 如果节点是可配置的中间节点，选中该节点，右侧面板显示其 Recipe 列表 |
| 点击 ▼/▶ | 展开/折叠子树 |
| 已配置节点点击 | 可以重新打开修改（弹出确认："修改 Recipe 将导致重新排程，是否继续？"） |
| 自动滚动 | 切换当前节点时，左侧树自动滚动使当前节点可见 |

**节点排序规则**：
系统按 `level` 降序 + `config_order` 升序排列待配置节点列表。默认自动选中列表中第一个待配置节点。

### 4.4.3 右侧面板 — Recipe 配置区

右侧面板分为三个子区域：当前节点信息区、Recipe 选择区、配置进度区。

#### 子区域 A：当前配置节点信息

```
┌────────────────────────────────────┐
│  当前配置节点                        │
│                                    │
│  ┌────┐ 缸体铸造毛坯                │
│  │ 🔵 │ Part: CAST-BLOCK-001      │
│  └────┘ 材质: AL-Si10Cu            │
│          批量: 100 件               │
│          层级: 第 4 层              │
│          父节点: 缸体机加工件        │
│                                    │
│  适用条件：批量 ≥ 50                │
└────────────────────────────────────┘
```

字段说明：

| 字段 | 说明 | 数据来源 |
|------|------|---------|
| 节点名称 | BOMNode 的名称 | `bom_node.part_number` → `part_number.part_name` |
| Part 编码 | Part Number | `bom_node.part_number` |
| 材质 | 材质信息（从 PartNumber 扩展字段取） | `part_number.material` |
| 批量 | 该节点的总需求量 | `job_bom_node.quantity_required` |
| 层级 | 在 BOM 树中的层级 | `job_bom_node.level` |
| 父节点 | 父节点名称 | `parent_job_bom_node` → `bom_node` |

#### 子区域 B：Recipe 选择区

**Recipe 卡片样式**：

每个可选 Recipe 以卡片形式展示：

```
┌─────────────────────────────────────────┐
│ ○ R-CAST-01 低压铸造                    │  ← Radio 单选
│   ┌──────┬────────────┬──────────────┐ │
│   │ 铸造  │ 6 道工序   │ 预估 480 分钟 │ │  ← 彩色 Team 标签 + 关键信息
│   │ 车间 │            │              │ │
│   └──────┴────────────┴──────────────┘ │
│   [查看详情 ▼]                          │  ← 可展开查看 Tasks 明细
└─────────────────────────────────────────┘
```

**Recipe 卡片字段**：

| 字段 | 说明 | 样式 |
|------|------|------|
| Recipe 编码 | 如 `R-CAST-01` | font-size: 14px, font-weight: 600 |
| Recipe 名称 | 如"低压铸造" | font-size: 14px |
| Team 标签 | 如"铸造车间" | 彩色标签，每个 Team 分配唯一颜色 |
| Tasks 数量 | 如"6 道工序" | font-size: 13px, color: #595959 |
| 预估工时 | 如"预估 480 分钟" | font-size: 13px, color: #595959 |
| 适用条件 | 如"批量 ≥ 50" | font-size: 12px, color: #8c8c8c |

**Team 颜色分配表（示例）**：

| Team | 颜色值 | 背景色 | 文字色 |
|------|--------|--------|--------|
| 铸造车间 | `#1890ff` | `#e6f7ff` | `#1890ff` |
| 锻造车间 | `#fa8c16` | `#fff7e6` | `#fa8c16` |
| 机加车间 | `#52c41a` | `#f6ffed` | `#52c41a` |
| 装配车间 | `#722ed1` | `#f9f0ff` | `#722ed1` |
| 总装车间 | `#eb2f96` | `#fff0f6` | `#eb2f96` |
| 注塑车间 | `#13c2c2` | `#e6fffb` | `#13c2c2` |
| 精密铸造车间 | `#f5222d` | `#fff1f0` | `#f5222d` |

**Recipe 详情展开**：

点击"查看详情 ▼"后展开显示完整 Tasks 列表：

```
展开后:
┌─────────────────────────────────────────┐
│ ● R-CAST-01 低压铸造  ← 已选中           │
│   Team: 铸造车间  |  预估: 480 分钟      │
│   适用条件: 批量 ≥ 50                    │
│                                         │
│   任务列表:                              │
│   ┌─────┬──────────────┬───────┬──────┐│
│   │ 序号 │ 任务名称      │ 工时  │ 类型  ││
│   ├─────┼──────────────┼───────┼──────┤│
│   │  1  │ 模具准备      │ 30min │ setup ││
│   │  2  │ 熔炼         │ 120min│machining│
│   │  3  │ 低压浇注      │ 90min │machining│
│   │  4  │ 冷却固化      │ 60min │machining│
│   │  5  │ 脱模清理      │ 45min │machining│
│   │  6  │ 尺寸初检      │ 30min │inspection│
│   └─────┴──────────────┴───────┴──────┘│
│   设备要求: 低压铸造机 500T              │
│   技能要求: 铸造高级技工                 │
│   [收起详情 ▲]                          │
└─────────────────────────────────────────┘
```

**操作按钮**：

| 按钮 | 说明 | 行为 |
|------|------|------|
| 确认选择 | 确认选中当前 Recipe | 创建 JobRecipe 记录 → 标记节点为"已配置" → 自动切换到下一个待配置节点 |
| 跳过 | 跳过当前节点 | 标记节点为"已跳过"（需二次确认）→ 切换到下一个 |

#### 子区域 C：配置进度区

```
┌──────────────────────────────┐
│  配置进度                      │
│                               │
│  ████████░░░░░░░░░░  8/18 完成 │  ← 进度条
│  44%                          │
│                               │
│  最近完成:                     │
│  ✓ 缸体铸造毛坯  →  R-CAST-01 │
│  ✓ 曲轴毛坯      →  R-CAST-04 │
│  ✓ 活塞          →  R-FORGE-01│
│  ...                          │
│                               │
│  下一个: 主轴承盖              │
│  剩余: 10 个                   │
│                               │
│  [查看全部节点列表]            │
└──────────────────────────────┘
```

进度条说明：
- 已完成节点数 / 总需配置节点数
- 进度条颜色：已完成部分 = `#52c41a`（绿色），未完成部分 = `#f5f5f5`（灰色）
- 百分比实时更新

### 4.4.4 Recipe 配置流程

```
用户进入 Step 3:
  │
  ▼
系统自动按"从深到浅"排序待配置节点列表（18 个节点）
  │
  ▼
默认选中第一个待配置节点（最深的中间节点：缸体铸造毛坯）
  │
  ▼
左侧面板：高亮当前节点（🔵◐）
右侧面板：显示该节点的信息 + 匹配 Recipe 列表
  │
  ▼
用户浏览 Recipe 详情（点击"查看详情"展开 Tasks 列表）
  │
  ▼
用户选择一个 Recipe（点击 Radio） → 点击"确认选择"
  │
  ▼
系统：
  ① 创建 JobRecipe 记录
  ② 更新 JobBOMNode.recipe_config_status = "configured"
  ③ 左侧节点图标变为 🔵✓
  ④ 进度条更新（8/18 → 9/18）
  ⑤ 自动切换到下一个待配置节点
  │
  ▼
循环直到所有 18 个节点配置完成
  │
  ▼
"完成配置，去预览"按钮变为可用状态
```

### 4.4.5 配置中断与恢复

| 场景 | 处理方式 |
|------|---------|
| 用户点击"保存进度" | 保存当前所有配置状态（JobRecipe + JobBOMNode status），可退出后恢复 |
| 浏览器意外关闭 | 自动保存机制每 30 秒触发一次，下次进入 Step 3 时恢复到上次进度 |
| 用户修改已配置节点 | 弹出确认对话框："修改 Recipe 将导致重新排程，是否继续？" → 确认后更新配置 |
| 某个节点无匹配 Recipe | 该节点高亮红色 → 右侧显示："该节点无匹配的 Recipe，请维护工艺数据" → 提供链接跳转到 Recipe 维护页 |

---

## 4.5 Step 4：工艺路线总览与排程

### 4.5.1 页面结构

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Step 4: 工艺路线总览与排程                                                │
│ 查看配置完成的完整工艺路线，按 Team 分组预览，确认后执行排程。              │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  视图切换: [ 树形视图 ] [ 列表视图 ] [ Process 视图 ] [ 甘特图 ]    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ═══════════════ 默认视图：Process 汇总 ═══════════════════             │
│                                                                          │
│  系统将基于 Recipe 配置生成 15 个 Process，涉及 6 个 Team：               │
│                                                                          │
│  ┌───────────┬──────────────┬────────┬─────────────┬──────────────────┐ │
│  │ Process   │    Team      │ 节点数 │   预估时长   │     前置依赖      │ │
│  ├───────────┼──────────────┼────────┼─────────────┼──────────────────┤ │
│  │ P-CAST-01 │  铸造车间     │   3    │    14 天    │        无        │ │
│  │ P-CAST-02 │  铸造车间     │   2    │    10 天    │        无        │ │
│  │ P-CAST-03 │  精密铸造车间 │   1    │    12 天    │        无        │ │
│  │ P-FORGE-01│  锻造车间     │   2    │     8 天    │        无        │ │
│  │ P-FORGE-02│  锻造车间     │   2    │     6 天    │        无        │ │
│  │ P-MC-01   │  机加车间     │   2    │    12 天    │  P-CAST-01       │ │
│  │ P-MC-02   │  机加车间     │   2    │    15 天    │  P-CAST-02       │ │
│  │ P-MC-03   │  机加车间     │   2    │    13 天    │  P-CAST-01,02    │ │
│  │ P-INJ-01  │  注塑车间     │   1    │     5 天    │        无        │ │
│  │ P-ASSY-01 │  装配车间     │   2    │     4 天    │  P-FORGE-01,     │ │
│  │           │              │        │             │  P-MC-01         │ │
│  │ P-ASSY-02 │  装配车间     │   2    │     5 天    │  P-FORGE-02,     │ │
│  │           │              │        │             │  P-MC-03         │ │
│  │ P-ASSY-03 │  装配车间     │   1    │     3 天    │  P-MC-02         │ │
│  │ P-ASSY-04 │  装配车间     │   1    │     3 天    │  P-INJ-01,       │ │
│  │           │              │        │             │  P-CAST-03       │ │
│  │ P-ASSY-05 │  装配车间     │   1    │     4 天    │  P-ASSY-01       │ │
│  │ P-FINAL   │  总装车间     │   1    │     5 天    │  全部前置完成     │ │
│  └───────────┴──────────────┴────────┴─────────────┴──────────────────┘ │
│                                                                          │
│  关键路径: P-CAST-01 → P-MC-01 → P-ASSY-01 → P-ASSY-05 → P-FINAL      │
│  预估总工期: 约 22 个工作日                                               │
│                                                                          │
│  ═════════════════════ 排程选项 ═══════════════════════                  │
│                                                                          │
│  排程策略:                                                               │
│  ○ 立即排程（ASAP — 尽快开始）                                            │
│  ● 基于目标交期倒排（Target: 2024-08-30）◄────────────────              │
│  ○ 有限产能排程（考虑设备负荷约束）                                        │
│                                                                          │
│  高级选项（可展开）:                                                      │
│  [ 展开 ▼ ]                                                               │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│  [ <── 返回修改 Recipe ]  [ 生成 Process ]  [ 执行排程 ▶ ]               │
└──────────────────────────────────────────────────────────────────────────┘
```

### 4.5.2 视图切换

系统提供 4 种视图，用户可通过 Tab 切换：

| 视图 | 说明 | 适用场景 |
|------|------|---------|
| 树形视图 | 按 BOM 树层级展示，每个节点显示选中的 Recipe | 检查 Recipe 配置的完整性 |
| 列表视图 | 平铺展示所有节点和对应的 Recipe | 快速浏览全部配置 |
| Process 视图 | 按 Team 分组展示即将生成的 Process（默认视图） | 确认 Process 分组合理性 |
| 甘特图 | 排程完成后显示各 Process 的时间轴 | 查看排程结果 |

**树形视图样式**：

```
▼ ENG-D250 柴油发动机总成
  │  Recipe: R-FINAL-01 (总装车间)  [查看详情 ▼]
  │  Tasks: 缸体曲轴合装→装缸盖→装进排气系统→...→终检→入库 (10 tasks)
  │
  ├─ ▼ 缸体组件模块
  │  │  Recipe: R-ASSY-04 (装配车间)  [查看详情 ▼]
  │  │  Tasks: 装活塞连杆→入缸体→装轴承盖→扭矩检验 (4 tasks)
  │  │
  │  ├─ ▼ 缸体机加工件
  │  │  │  Recipe: R-MC-01 (机加车间)  [查看详情 ▼]
  │  │  │  Tasks: CNC铣面→钻孔→镗缸→精铣 (4 tasks)
  │  │  │
  │  │  └─ ▼ 缸体铸造毛坯
  │  │     │  Recipe: R-CAST-01 (铸造车间)  [查看详情 ▼]
  │  │     │  Tasks: 模具准备→熔炼→浇注→冷却→脱模→初检 (6 tasks)
  │  │     └─ ⬜ 铝合金锭 AL-Si10Cu  (采购件，无需配置)
```

### 4.5.3 Process 汇总表

Process 汇总表是 Step 4 的默认视图，展示按 Team 分组后的 Process 预览。

**表格列定义**：

| 列名 | 说明 | 宽度 |
|------|------|------|
| Process 编码 | 如 `P-CAST-01` | 120px |
| Process 名称 | 如"缸体与缸盖铸造" | 200px |
| Team | 执行团队，彩色标签 | 120px |
| 节点数 | 该 Process 包含的 BOM 节点数量 | 80px |
| 预估时长 | 所有 Task 标准工时之和 | 100px |
| 前置依赖 | 前置 Process 编码列表 | 200px |
| 操作 | [查看详情] 按钮 | 100px |

**行样式**：
- 同一 Team 的 Process 行用相同颜色的左边框标识（Team 颜色）；
- 关键路径上的 Process 行背景高亮（淡黄色 `#fffbe6`）；
- 鼠标悬停行高亮。

### 4.5.4 排程选项

**排程策略选择**：

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| 立即排程（ASAP） | 从当前日期开始，尽可能早地完成所有 Process | 紧急订单，追求最短交付周期 |
| 基于目标交期倒排 | 从目标交期倒推，确定每个 Process 的最晚开始时间 | 有明确交期要求 |
| 有限产能排程 | 考虑设备负荷约束，避免超载 | 产能紧张，需要平衡负荷 |

**高级选项（可展开）**：

```
展开后:
┌────────────────────────────────────────────────────┐
│ 高级排程选项                                        │
│                                                     │
│  排程起始日期:  [ 📅 2024-08-01    ]               │
│  资源约束:      [● 考虑设备负荷] [○ 考虑人员技能]   │
│  拆分策略:      [● 不拆分] [○ 按经济批量拆分]      │
│  缓冲时间:      [  10  ] 分钟（Process 间等待时间） │
│  优先级权重:    [● 标准] [○ 交期优先] [○ 产能优先]  │
│                                                     │
│  [恢复默认]                                         │
└────────────────────────────────────────────────────┘
```

### 4.5.5 按钮定义

| 按钮 | 说明 | 点击行为 | 前置条件 |
|------|------|---------|---------|
| 返回修改 Recipe | 回到 Step 3 | 跳转到 Step 3 | 无 |
| 生成 Process | 调用 Process 生成算法 | 调用 API → 生成 15 个 Process → 表格更新显示 | Recipe 配置全部完成 |
| 执行排程 | 启动排程引擎 | 调用 API → 排程引擎运行 → 切换到甘特图视图 | Process 已生成 |

### 4.5.6 排程完成后的甘特图视图

排程完成后，系统自动切换到甘特图视图：

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 甘特图视图                                                               │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Team      │ W1(8/1-8/7) │ W2(8/8-8/14) │ W3(8/15-8/21) │ W4(8/22-8/28) │
│ ──────────┼─────────────┼──────────────┼───────────────┼───────────────│
│ 铸造车间   │ P-CAST-01   │              │               │               │
│           │ ██████████  │ P-CAST-03    │               │               │
│           │ P-CAST-02   │ ██████████   │               │               │
│           │ ████████    │              │               │               │
│ ──────────┼─────────────┼──────────────┼───────────────┼───────────────│
│ 锻造车间   │ P-FORGE-01  │              │               │               │
│           │ ████████    │ P-FORGE-02   │               │               │
│           │             │ ██████       │               │               │
│ ──────────┼─────────────┼──────────────┼───────────────┼───────────────│
│ 机加车间   │             │ P-MC-01      │ P-MC-03       │               │
│           │             │ ██████████   │ ██████████    │               │
│           │             │ P-MC-02      │               │               │
│           │             │ █████████████│               │               │
│ ──────────┼─────────────┼──────────────┼───────────────┼───────────────│
│ 装配车间   │             │              │ P-ASSY-01     │ P-ASSY-03     │
│           │             │              │ ████          │ ███           │
│           │             │              │ P-ASSY-02     │ P-ASSY-04     │
│           │             │              │ █████         │ ███           │
│           │             │              │               │ P-ASSY-05     │
│           │             │              │               │ ████          │
│ ──────────┼─────────────┼──────────────┼───────────────┼───────────────│
│ 总装车间   │             │              │               │               │
│           │             │              │               │ P-FINAL       │
│           │             │              │               │ █████         │
│                                                                          │
│  图例: █████ = Process 执行时段    ═════ = 关键路径                      │
│        P-CAST-01 灰色 = 非关键路径    P-CAST-01 红色边框 = 关键路径        │
│                                                                          │
│  [ 重新排程 ]  [ 调整排程 ]  [ 释放到车间 ▶ ]                             │
└──────────────────────────────────────────────────────────────────────────┘
```

**甘特图交互**：

| 操作 | 行为 |
|------|------|
| 鼠标悬停 Process 条 | 显示 Tooltip：Process 名称、起止时间、Team、进度 |
| 点击 Process 条 | 展开详情面板，显示该 Process 的所有 Task |
| 拖拽调整 | 支持有限度的手动调整（需权限） |
| 缩放 | 支持日/周/月视图切换 |

---

## 4.6 视图切换

### 4.6.1 配置视图（倒序树）

配置视图即 Step 3 的主视图，以"倒序 BOM 树 + Recipe 选择面板"为核心。设计目的是支持用户按"从叶子到根"的顺序高效配置 Recipe。

**视图特征**：
- 左侧：BOM 树，节点按层级倒序排列，当前节点高亮；
- 右侧：Recipe 选择面板，显示当前节点的可选 Recipe；
- 顶部：配置进度指示器；
- 底部：操作按钮（上一步 / 保存进度 / 完成配置）。

### 4.6.2 预览视图（按 Team 分组）

预览视图即 Step 4 的 Process 视图，以"按 Team 分组的 Process 汇总表"为核心。设计目的是让用户在排程前确认 Process 分组的合理性。

**视图特征**：
- 表格形式展示所有 Process；
- 按 Team 分组，同一 Team 的 Process 连续排列；
- 显示关键路径标识；
- 提供排程选项和排程按钮。

### 4.6.3 视图切换规则

| 切换方向 | 触发条件 | 状态保持 |
|---------|---------|---------|
| 配置视图 → 预览视图 | 点击"完成配置" | 保存所有配置，生成 Process |
| 预览视图 → 配置视图 | 点击"返回修改 Recipe" | 保留已生成 Process 但不保存，返回后可修改 |
| 预览视图 → 甘特图 | 执行排程完成后 | 排程结果自动保存 |
| 甘特图 → 预览视图 | 点击"重新排程"前的确认 | 取消当前排程 |

---

## 4.7 关键交互说明

### 4.7.1 节点展开/折叠

**交互行为**：

| 操作 | 效果 | 动画 |
|------|------|------|
| 点击 ▶（折叠图标） | 展开该节点的子树 | 300ms 高度展开动画 |
| 点击 ▼（展开图标） | 折叠该节点的子树 | 300ms 高度折叠动画 |
| 双击节点名称 | 切换展开/折叠状态 | 同上述动画 |
| Ctrl + 点击 ▶ | 展开该节点及其所有子孙节点 | 级联展开 |
| Ctrl + 点击 ▼ | 折叠该节点及其所有子孙节点 | 级联折叠 |

**状态持久化**：展开/折叠状态保存在前端 React State 中，切换视图或返回上一步后恢复。

### 4.7.2 Recipe 选择面板（模态框详情）

**触发方式**：点击 Recipe 卡片上的"查看详情 ▼"。

**展开内容**：
- Recipe 基础信息（编码、名称、Team、预估时长）；
- Tasks 明细表格（序号、名称、工时、类型）；
- 扩展信息（适用条件、设备要求、技能要求、质量标准）。

**展开动画**：300ms 高度展开，ease-in-out。

**收起方式**：点击"收起详情 ▲"或点击其他 Recipe 卡片的"查看详情"。

### 4.7.3 步骤导航

**导航规则**：

| 场景 | 行为 |
|------|------|
| 完成当前步骤 | "下一步"按钮变为可用（主题色），点击后进入下一步 |
| 当前步骤未完成 | "下一步"按钮禁用（灰色），Tooltip 提示"请完成当前步骤必填项" |
| 返回上一步 | 点击"上一步"按钮，保存当前进度后返回 |
| 点击步骤指示器 | 仅允许跳转到已完成的步骤，不允许跳转到待完成的步骤 |
| 从已完成步骤返回修改 | 弹出确认对话框："返回修改将导致后续步骤重新校验，是否继续？" |

### 4.7.4 步骤状态（Step Status）

每个步骤有三种状态：

| 状态 | 图标 | 颜色 | 说明 |
|------|------|------|------|
| pending | ○ | `#bfbfbf` 灰色 | 尚未开始 |
| active | ● | `#1890ff` 蓝色 + 脉冲 | 进行中 |
| completed | ● | `#52c41a` 绿色 + 对勾 | 已完成 |
| error | ● | `#f5222d` 红色 + 感叹号 | 有错误需处理 |

### 4.7.5 自动保存机制

**保存触发条件**：

| 触发条件 | 保存内容 | 提示方式 |
|---------|---------|---------|
| 30 秒无操作 | 当前表单数据 | 底部状态栏 "已自动保存" |
| 用户点击"保存进度" | 当前表单数据 | Toast 提示 "保存成功" |
| 切换步骤时 | 当前步骤所有数据 | 无提示（自动保存） |
| 浏览器 beforeunload | 尝试保存（若未保存过） | 若有未保存内容弹出确认对话框 |

### 4.7.6 键盘快捷键

| 快捷键 | 功能 | 适用步骤 |
|--------|------|---------|
| Ctrl + S | 保存当前进度 | 全部 |
| Ctrl + Enter | 确认当前操作（等同于点击"确认选择"） | Step 3 |
| Tab | 在表单字段间切换 | Step 1 |
| ↑ / ↓ | 在 BOM 树节点间上下移动 | Step 2, 3 |
| → | 展开当前节点 | Step 2, 3 |
| ← | 折叠当前节点 | Step 2, 3 |
| 1 / 2 / 3 / 4 | 快速切换步骤（仅可切换到已完成步骤） | 全部 |
| ? | 打开快捷键帮助面板 | 全部 |

### 4.7.7 响应式适配

**最小支持分辨率**：1366 × 768

**适配规则**：

| 屏幕宽度 | 布局调整 |
|---------|---------|
| ≥ 1440px | 标准布局（左侧边栏 380px + 主内容区弹性） |
| 1366px ~ 1439px | 左侧边栏收缩为图标模式（仅图标，hover 展开文字） |
| < 1366px | 提示"建议使用更大屏幕以获得最佳体验"，但功能可用 |

### 4.7.8 错误提示规范

| 错误类型 | 展示方式 | 持续时间 | 操作 |
|---------|---------|---------|------|
| 表单校验错误 | 字段下方红色文字提示 | 持续，修正后消失 | 修正输入 |
| 系统错误（API 失败） | 全局 Toast 通知（红色） | 5 秒 | 重试或联系管理员 |
| 网络中断 | 顶部横幅提示（黄色） | 持续，恢复后消失 | 检查网络 |
| 并发冲突 | 模态对话框 | 需用户确认 | 刷新页面或覆盖 |
| 权限不足 | 全局 Toast 通知（红色） | 5 秒 | 联系管理员 |

**Toast 通知位置**：右上角，最多同时显示 3 条，新通知从顶部推入，旧通知被挤出。

---

> **文档第一部分结束**
> 
> 本文档涵盖：
> - 第 1 章：概述（项目背景、设计思考、应用场景、术语表）
> - 第 2 章：概念体系（6 个核心概念定义、实体关系图、约束汇总）
> - 第 3 章：业务流程（完整流程示例、业务流程图、3 套状态机）
> - 第 4 章：UI/UX 设计（页面布局、4 个步骤详设、视图切换、关键交互）
> 
> 后续文档（第二部分）将涵盖：数据库设计（第 5 章）、接口设计（第 6 章）、排程引擎设计（第 7 章）。
# Job 拆分排产系统 — 数据库设计

> 版本：v1.0  
> 作者：数据库架构师  
> 定位：基于《业务概念与信息架构设计》的数据库物理设计文档  
> 配套文档：`concept_design.md`

---

## 目录

- [5.1 设计原则](#51-设计原则)
- [5.2 ER 关系图](#52-er-关系图)
- [5.3 表结构设计](#53-表结构设计)
- [5.4 索引设计](#54-索引设计)
- [5.5 关键查询场景与索引策略](#55-关键查询场景与索引策略)
- [5.6 数据量估算](#56-数据量估算)

---

## 5.1 设计原则

### 5.1.1 命名规范

| 层级 | 规范 | 示例 |
|------|------|------|
| 数据库名 | 小写下划线 | `job_split_scheduling` |
| 表名 | 小写下划线，复数形式 | `part_numbers`、`bom_nodes` |
| 字段名 | 小写下划线 | `part_number`、`created_at` |
| 索引名 | `ix_表名_字段名` / `uq_表名_字段名` | `ix_jobs_status`、`uq_part_numbers_part_number` |
| 外键名 | `fk_子表_父表` | `fk_jobs_part_numbers` |
| 主键名 | `pk_表名` | `pk_jobs` |

### 5.1.2 主键策略

| 场景 | 策略 | 说明 |
|------|------|------|
| 主业务表（Job、Process 等） | 雪花算法生成 64 位整数 | 分布式环境下保证唯一性，含时间戳可排序 |
| 配置模板表（BOM、Recipe 等） | 雪花算法生成 64 位整数 | 同上 |
| 关联/关系表 | 自增 `BIGINT UNSIGNED` | 简单高效，无分布式冲突风险 |
| 编码类字段 | 业务编码字符串 | 如 `part_number`、`recipe_code`，天然唯一 |

> **雪花算法格式**：1bit 符号 + 41bit 时间戳（毫秒）+ 10bit 工作节点 + 12bit 序列号，共 64bit。

### 5.1.3 时间字段与软删除

所有业务表必须包含以下三个审计字段：

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `created_at` | `DATETIME(3)` | `CURRENT_TIMESTAMP(3)` | 记录创建时间，精确到毫秒 |
| `updated_at` | `DATETIME(3)` | `CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)` | 记录最后更新时间 |
| `deleted_at` | `DATETIME(3)` | `NULL` | 软删除标志，`NULL` 表示未删除，非 `NULL` 表示删除时间 |

> 软删除通过为每张表添加 `WHERE deleted_at IS NULL` 的默认查询条件实现，被软删除的数据物理保留，可用于审计和追溯。

### 5.1.4 索引策略

| 策略类型 | 规则 | 示例 |
|----------|------|------|
| 主键索引 | 每张表必有主键，默认聚簇索引 | `PRIMARY KEY (id)` |
| 外键索引 | 所有外键字段必须建立索引 | `FOREIGN KEY (bom_id) REFERENCES boms(bom_id)` 同时创建 `ix_xxx_bom_id` |
| 状态索引 | 状态过滤字段建立索引 | `status` 字段频繁用于 `WHERE status = ?` |
| 复合索引 | 高频组合查询字段建立复合索引，遵循最左前缀原则 | `(job_id, status)` 优于单独索引 |
| 唯一索引 | 业务唯一性约束字段 | `uq_xxx_code` 类索引 |

### 5.1.5 字符集与存储引擎

| 配置项 | 设定值 | 说明 |
|--------|--------|------|
| 字符集 | `utf8mb4` | 支持完整 Unicode，包括 Emoji 和生僻字 |
| 排序规则 | `utf8mb4_unicode_ci` | 区分大小写，支持多语言排序 |
| 存储引擎 | `InnoDB` | 支持事务、行级锁、外键约束 |
| 事务隔离级别 | `READ COMMITTED` | 避免幻读，同时保证并发性能 |

### 5.1.6 字段设计通用规范

| 数据类型 | 使用场景 | 示例 |
|----------|----------|------|
| `BIGINT UNSIGNED` | 雪花算法主键、大整数计数 | 所有表的主键 |
| `VARCHAR(n)` | 变长字符串，长度明确 | `VARCHAR(64)` 编码，`VARCHAR(255)` 名称 |
| `TEXT` | 长文本描述 | 备注、说明字段 |
| `DECIMAL(18,6)` | 精确小数（数量、金额） | `quantity_per_parent` |
| `DATETIME(3)` | 日期时间，精确到毫秒 | 所有时间戳字段 |
| `TINYINT UNSIGNED` | 小范围整数枚举 | 状态码、布尔值 |
| `INT UNSIGNED` | 中范围整数 | 数量、时长、排序号 |
| `FLOAT` | 浮点数值（非精确计算） | 优先级得分 |

---

## 5.2 ER 关系图

### 5.2.1 实体关系概览（文字描述）

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              完整 ER 关系图                                            │
└──────────────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
  │  part_numbers   │◄─────────┤     boms        │◄─────────┤   bom_nodes     │
  │   (PK: part_    │   1:N    │   (PK: bom_id)  │   1:N    │ (PK: node_id)   │
  │    number)      │          │  FK→part_numbers│          │ FK→boms         │
  └────────┬────────┘          └─────────────────┘          └────────┬────────┘
           ▲                                                       │
           │                                                       │ N:1(parent)
           │                   ┌─────────────────┐                 │
           │                   │bom_node_relations│◄────────────────┘
           │                   │(PK: relation_id)│   1:N
           │                   │ FK→bom_nodes    │
           │                   │   (parent/child)│
           │                   └─────────────────┘
           │
           │         ┌─────────────────┐         ┌─────────────────┐
           └─────────┤    recipes      │◄────────┤  recipe_tasks   │
              N:M    │ (PK: recipe_id) │   1:N   │ (PK: task_id)   │
           (via      │ FK→teams        │         │ FK→recipes      │
    recipe_applicable │                 │         └─────────────────┘
          _parts)    └─────────────────┘
                           ▲
                           │ N:1
           ┌───────────────┴───────────────┐
           │                               │
  ┌────────┴────────┐            ┌─────────┴───────┐
  │   job_recipes   │            │     teams       │
  │ (PK: job_recipe_│            │ (PK: team_id)   │
  │      id)        │            │ FK→teams(parent)│
  │ FK→jobs         │            └────────┬────────┘
  │ FK→job_bom_nodes│                     │
  │ FK→recipes      │                     │ 1:N
  └─────────────────┘            ┌────────┴────────┐
                                 │    processes    │
  ┌─────────────────┐            │ (PK: process_id)│
  │   job_bom_nodes │            │ FK→jobs        │◄──────────┐
  │ (PK: job_node_id│            │ FK→teams        │           │
  │ FK→jobs         │            └────────┬────────┘           │
  │ FK→bom_nodes    │                     │                    │
  │ FK→job_bom_nodes│        ┌────────────┼────────────┐       │
  │   (parent,自关联)│        │            │            │       │
  │ FK→recipes      │        ▼            ▼            ▼       │
  └─────────────────┘  ┌──────────┐ ┌──────────┐ ┌──────────┐  │
                       │process_  │ │process_  │ │ signals  │  │
                       │  tasks   │ │dependencies│ │          │  │
                       │          │ │           │ │          │  │
                       └──────────┘ └──────────┘ └──────────┘  │
                                                               │
  ┌─────────────────┐                                          │
  │      jobs       │──────────────────────────────────────────┘
  │  (PK: job_id)   │        1:N
  │ FK→part_numbers │
  │ FK→boms         │
  └─────────────────┘
```

### 5.2.2 关系类型详述

| 父实体 | 子实体 | 关系类型 | 外键字段 | 级联规则 | 说明 |
|--------|--------|----------|----------|----------|------|
| `part_numbers` | `boms` | 1:N | `boms.part_number` | RESTRICT | 一个物料可有多版本 BOM |
| `boms` | `bom_nodes` | 1:N | `bom_nodes.bom_id` | CASCADE | BOM 删除时级联删除节点 |
| `boms` | `bom_node_relations` | 1:N | `bom_node_relations.bom_id` | CASCADE | BOM 树结构边 |
| `bom_nodes` | `bom_node_relations` | 1:N（parent）| `bom_node_relations.parent_node_id` | CASCADE | 父节点引用 |
| `bom_nodes` | `bom_node_relations` | 1:N（child）| `bom_node_relations.child_node_id` | CASCADE | 子节点引用 |
| `teams` | `teams` | 1:N（自关联）| `teams.parent_team_id` | SET NULL | 团队层级结构 |
| `teams` | `recipes` | 1:N | `recipes.default_team_id` | SET NULL | Recipe 默认执行团队 |
| `recipes` | `recipe_tasks` | 1:N | `recipe_tasks.recipe_id` | CASCADE | 工艺路线任务 |
| `part_numbers` | `recipe_applicable_parts` | 1:N | `recipe_applicable_parts.part_number` | CASCADE | Recipe 适用物料 |
| `recipes` | `recipe_applicable_parts` | 1:N | `recipe_applicable_parts.recipe_id` | CASCADE | Recipe 适用物料 |
| `part_numbers` | `jobs` | 1:N | `jobs.part_number` | RESTRICT | Job 生产的产品 |
| `boms` | `jobs` | 1:N | `jobs.bom_id` | SET NULL | Job 使用的 BOM |
| `jobs` | `job_bom_nodes` | 1:N | `job_bom_nodes.job_id` | CASCADE | Job 实例化 BOM 节点 |
| `bom_nodes` | `job_bom_nodes` | 1:N | `job_bom_nodes.node_id` | RESTRICT | 关联模板节点 |
| `job_bom_nodes` | `job_bom_nodes` | 1:N（自关联）| `job_bom_nodes.parent_job_node_id` | SET NULL | 实例树父子关系 |
| `recipes` | `job_bom_nodes` | 1:N | `job_bom_nodes.selected_recipe_id` | SET NULL | 节点选中的 Recipe |
| `jobs` | `job_recipes` | 1:N | `job_recipes.job_id` | CASCADE | Recipe 选择记录 |
| `job_bom_nodes` | `job_recipes` | 1:1 | `job_recipes.job_node_id` | CASCADE | 配置节点关联 |
| `recipes` | `job_recipes` | N:1 | `job_recipes.recipe_id` | RESTRICT | 选中的 Recipe |
| `jobs` | `processes` | 1:N | `processes.job_id` | CASCADE | Job 拆分的 Process |
| `teams` | `processes` | N:1 | `processes.team_id` | RESTRICT | Process 执行团队 |
| `processes` | `process_tasks` | 1:N | `process_tasks.process_id` | CASCADE | Process 内任务 |
| `recipe_tasks` | `process_tasks` | N:1 | `process_tasks.recipe_task_id` | SET NULL | 来源模板任务 |
| `job_bom_nodes` | `process_tasks` | N:1 | `process_tasks.job_node_id` | SET NULL | 关联 BOM 节点 |
| `jobs` | `process_dependencies` | 1:N | `process_dependencies.job_id` | CASCADE | 依赖所属 Job |
| `processes` | `process_dependencies` | 1:N（pre）| `process_dependencies.predecessor_process_id` | CASCADE | 前置 Process |
| `processes` | `process_dependencies` | 1:N（succ）| `process_dependencies.successor_process_id` | CASCADE | 后置 Process |
| `jobs` | `signals` | 1:N | `signals.job_id` | CASCADE | 信号关联 Job |
| `processes` | `signals` | 1:N | `signals.process_id` | SET NULL | 信号关联 Process |

---

## 5.3 表结构设计

---

### 5.3.1 `part_numbers` — 物料编码主数据

> **说明**：物料编码主数据表，存储所有原材料、半成品、成品、外购件的编码信息。是整个系统的基础数据之一。

| 序号 | 字段名 | 数据类型 | 长度/精度 | 可空 | 默认值 | 约束 | 说明 |
|------|--------|----------|-----------|------|--------|------|------|
| 1 | `part_number` | `VARCHAR` | 64 | NOT NULL | - | **PK** | 物料编码，唯一标识 |
| 2 | `part_name` | `VARCHAR` | 255 | NOT NULL | - | - | 物料名称 |
| 3 | `part_category` | `VARCHAR` | 32 | NOT NULL | - | - | 物料类别：`raw_material`(原材料) / `semi_finished`(半成品) / `finished_good`(成品) / `purchased_part`(外购件) |
| 4 | `default_uom` | `VARCHAR` | 32 | NOT NULL | `'EA'` | - | 默认计量单位（件/千克/米/升等） |
| 5 | `drawing_revision` | `VARCHAR` | 64 | NULL | NULL | - | 图纸版本号 |
| 6 | `is_active` | `TINYINT` | 1 | NOT NULL | `1` | - | 是否启用：1=启用，0=停用 |
| 7 | `created_at` | `DATETIME(3)` | - | NOT NULL | `CURRENT_TIMESTAMP(3)` | - | 创建时间 |
| 8 | `updated_at` | `DATETIME(3)` | - | NOT NULL | `CURRENT_TIMESTAMP(3)` | - | 更新时间（ON UPDATE） |
| 9 | `deleted_at` | `DATETIME(3)` | - | NULL | `NULL` | - | 软删除时间，NULL=未删除 |

**主键**：`pk_part_numbers` → `part_number`

**索引**：
- `ix_part_numbers_category` → `part_category` — 按类别查询物料
- `ix_part_numbers_active` → `is_active` — 查询启用的物料
- `ix_part_numbers_deleted` → `deleted_at` — 软删除过滤

**注释**：物料编码是系统的核心业务主键，建议使用企业内部的编码规范（如 `ENG-D250`、`AL-Si10Cu`）。编码一旦创建不建议修改，以免影响历史数据追溯。

---

### 5.3.2 `boms` — BOM 模板

> **说明**：BOM（物料清单）模板表，描述产品的结构化物料组成。一个 Part Number 可拥有多个版本的 BOM，但同一时间仅一个版本为 `Active`。

| 序号 | 字段名 | 数据类型 | 长度/精度 | 可空 | 默认值 | 约束 | 说明 |
|------|--------|----------|-----------|------|--------|------|------|
| 1 | `bom_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **PK** | BOM 唯一标识，雪花算法 |
| 2 | `part_number` | `VARCHAR` | 64 | NOT NULL | - | **FK** | 根节点产品型号，关联 `part_numbers` |
| 3 | `version` | `VARCHAR` | 32 | NOT NULL | `'1.0'` | - | BOM 版本号 |
| 4 | `version_status` | `VARCHAR` | 16 | NOT NULL | `'Draft'` | - | 版本状态：`Active`(生效) / `Obsolete`(作废) / `Draft`(草稿) |
| 5 | `description` | `TEXT` | - | NULL | NULL | - | BOM 描述说明 |
| 6 | `max_depth` | `TINYINT UNSIGNED` | - | NOT NULL | `1` | - | BOM 最大深度（缓存值，根=1） |
| 7 | `total_nodes` | `INT UNSIGNED` | - | NOT NULL | `0` | - | 总节点数（缓存值） |
| 8 | `created_at` | `DATETIME(3)` | - | NOT NULL | `CURRENT_TIMESTAMP(3)` | - | 创建时间 |
| 9 | `updated_at` | `DATETIME(3)` | - | NOT NULL | `CURRENT_TIMESTAMP(3)` | - | 更新时间 |
| 10 | `deleted_at` | `DATETIME(3)` | - | NULL | `NULL` | - | 软删除时间 |

**主键**：`pk_boms` → `bom_id`

**外键**：
- `fk_boms_part_numbers` → `part_number` REFERENCES `part_numbers(part_number)` ON DELETE RESTRICT

**索引**：
- `ix_boms_part_number` → `part_number` — 按产品型号查询 BOM
- `ix_boms_status` → `version_status` — 按状态查询生效/作废的 BOM
- `uq_boms_part_version` → `part_number, version` — 同一产品的版本号唯一

**注释**：`max_depth` 和 `total_nodes` 为冗余缓存字段，在 BOM 编辑时自动计算并更新，用于前端展示和快速统计，避免频繁递归查询。

---

### 5.3.3 `bom_nodes` — BOM 节点

> **说明**：BOM 中的单个节点，对应一个零部件或原材料。将 BOM 树的所有节点平铺存储，通过 `bom_node_relations` 表构建树状结构。

| 序号 | 字段名 | 数据类型 | 长度/精度 | 可空 | 默认值 | 约束 | 说明 |
|------|--------|----------|-----------|------|--------|------|------|
| 1 | `node_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **PK** | 节点唯一标识，雪花算法 |
| 2 | `bom_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 所属 BOM |
| 3 | `part_number` | `VARCHAR` | 64 | NOT NULL | - | **FK** | 物料编码，关联 `part_numbers` |
| 4 | `node_type` | `VARCHAR` | 16 | NOT NULL | - | - | 节点类型：`intermediate`(中间节点，需配 Recipe) / `leaf`(叶子节点) |
| 5 | `level` | `TINYINT UNSIGNED` | - | NOT NULL | `1` | - | 在 BOM 树中的层级（根=1） |
| 6 | `quantity_per_parent` | `DECIMAL` | (18,6) | NOT NULL | `1.000000` | - | 父节点所需本节点的数量 |
| 7 | `unit` | `VARCHAR` | 32 | NOT NULL | `'EA'` | - | 计量单位（件/kg/m） |
| 8 | `is_configurable` | `TINYINT` | 1 | NOT NULL | `1` | - | 是否需要配置 Recipe：1=是，0=否 |
| 9 | `default_recipe_id` | `BIGINT UNSIGNED` | - | NULL | NULL | **FK** | 默认 Recipe（可选），关联 `recipes` |
| 10 | `drawing_no` | `VARCHAR` | 128 | NULL | NULL | - | 图号（可选） |

**主键**：`pk_bom_nodes` → `node_id`

**外键**：
- `fk_bom_nodes_boms` → `bom_id` REFERENCES `boms(bom_id)` ON DELETE CASCADE
- `fk_bom_nodes_part_numbers` → `part_number` REFERENCES `part_numbers(part_number)` ON DELETE RESTRICT
- `fk_bom_nodes_recipes` → `default_recipe_id` REFERENCES `recipes(recipe_id)` ON DELETE SET NULL

**索引**：
- `ix_bom_nodes_bom_id` → `bom_id` — 按 BOM 查询节点
- `ix_bom_nodes_part_number` → `part_number` — 按物料编码查询使用位置
- `ix_bom_nodes_type` → `node_type` — 区分中间节点和叶子节点
- `ix_bom_nodes_level` → `level` — 按层级查询

**注释**：`node_type` 与 `is_configurable` 通常保持一致（`intermediate` 对应 `is_configurable=1`），但设计上解耦以支持特殊场景（如某些中间节点可标记为不可配置）。

---

### 5.3.4 `bom_node_relations` — BOM 树结构（父子关系）

> **说明**：BOM 树结构的边表，通过 `parent_node_id` 和 `child_node_id` 构建完整的树状层次关系。采用"邻接表模型"存储树结构。

| 序号 | 字段名 | 数据类型 | 长度/精度 | 可空 | 默认值 | 约束 | 说明 |
|------|--------|----------|-----------|------|--------|------|------|
| 1 | `relation_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **PK** | 关系唯一标识，雪花算法 |
| 2 | `bom_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 所属 BOM |
| 3 | `parent_node_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 父节点，关联 `bom_nodes` |
| 4 | `child_node_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 子节点，关联 `bom_nodes` |
| 5 | `sort_order` | `INT UNSIGNED` | - | NOT NULL | `0` | - | 同级节点的排序号 |

**主键**：`pk_bom_node_relations` → `relation_id`

**外键**：
- `fk_bnr_boms` → `bom_id` REFERENCES `boms(bom_id)` ON DELETE CASCADE
- `fk_bnr_parent` → `parent_node_id` REFERENCES `bom_nodes(node_id)` ON DELETE CASCADE
- `fk_bnr_child` → `child_node_id` REFERENCES `bom_nodes(node_id)` ON DELETE CASCADE

**索引**：
- `ix_bnr_bom_id` → `bom_id` — 按 BOM 查询关系
- `ix_bnr_parent` → `parent_node_id` — 查询某节点的所有子节点
- `ix_bnr_child` → `child_node_id` — 查询某节点的父节点（ UNIQUE 约束保证每个子节点只有一个父）
- `uq_bnr_parent_child` → `parent_node_id, child_node_id` — 同一父子关系唯一

**注释**：严格树结构约束——每个 `child_node_id` 只能出现一次（通过唯一索引保证）。排序号 `sort_order` 用于前端 BOM 树的同级节点展示顺序。

---

### 5.3.5 `teams` — 执行团队/工作中心

> **说明**：执行团队/工作中心表，包括车间、产线、工位、供应商等。支持层级结构（通过 `parent_team_id` 自关联）。

| 序号 | 字段名 | 数据类型 | 长度/精度 | 可空 | 默认值 | 约束 | 说明 |
|------|--------|----------|-----------|------|--------|------|------|
| 1 | `team_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **PK** | 团队唯一标识，雪花算法 |
| 2 | `team_code` | `VARCHAR` | 64 | NOT NULL | - | **UQ** | 团队编码，如 `CAST-01`、`MC-LINE-A` |
| 3 | `team_name` | `VARCHAR` | 128 | NOT NULL | - | - | 团队名称，如"铸造车间" |
| 4 | `team_type` | `VARCHAR` | 32 | NOT NULL | - | - | 团队类型：`workshop`(车间) / `production_line`(产线) / `work_center`(工作中心) / `supplier`(供应商) |
| 5 | `parent_team_id` | `BIGINT UNSIGNED` | - | NULL | NULL | **FK** | 上级团队，自关联 |
| 6 | `capacity_per_day` | `INT UNSIGNED` | - | NULL | NULL | - | 日产能（单位视业务而定，如件/天） |
| 7 | `shift_count` | `TINYINT UNSIGNED` | - | NOT NULL | `1` | - | 班次数量 |
| 8 | `location` | `VARCHAR` | 255 | NULL | NULL | - | 物理位置描述 |
| 9 | `is_active` | `TINYINT` | 1 | NOT NULL | `1` | - | 是否启用：1=启用，0=停用 |
| 10 | `created_at` | `DATETIME(3)` | - | NOT NULL | `CURRENT_TIMESTAMP(3)` | - | 创建时间 |
| 11 | `updated_at` | `DATETIME(3)` | - | NOT NULL | `CURRENT_TIMESTAMP(3)` | - | 更新时间 |
| 12 | `deleted_at` | `DATETIME(3)` | - | NULL | `NULL` | - | 软删除时间 |

**主键**：`pk_teams` → `team_id`

**外键**：
- `fk_teams_parent` → `parent_team_id` REFERENCES `teams(team_id)` ON DELETE SET NULL

**索引**：
- `uq_teams_code` → `team_code` — 编码唯一
- `ix_teams_type` → `team_type` — 按类型查询
- `ix_teams_parent` → `parent_team_id` — 查询子团队
- `ix_teams_active` → `is_active` — 过滤启用状态

**注释**：`supplier` 类型用于委外加工场景，此时 `capacity_per_day` 表示供应商的日交付能力，`location` 记录供应商地址/联系方式。

---

### 5.3.6 `recipes` — 工艺路线模板

> **说明**：工艺路线模板表，定义某零部件的加工方案。包含适用批量范围、默认执行团队、预估时长等信息。

| 序号 | 字段名 | 数据类型 | 长度/精度 | 可空 | 默认值 | 约束 | 说明 |
|------|--------|----------|-----------|------|--------|------|------|
| 1 | `recipe_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **PK** | 工艺路线唯一标识，雪花算法 |
| 2 | `recipe_code` | `VARCHAR` | 64 | NOT NULL | - | **UQ** | 编码，如 `R-CAST-01`、`R-MC-01` |
| 3 | `name` | `VARCHAR` | 128 | NOT NULL | - | - | 名称，如"低压铸造" |
| 4 | `description` | `TEXT` | - | NULL | NULL | - | 详细描述 |
| 5 | `applicable_quantity_min` | `INT UNSIGNED` | - | NOT NULL | `1` | - | 最小适用批量 |
| 6 | `applicable_quantity_max` | `INT UNSIGNED` | - | NULL | `NULL` | - | 最大适用批量，NULL 表示无上限 |
| 7 | `default_team_id` | `BIGINT UNSIGNED` | - | NULL | NULL | **FK** | 默认执行团队 |
| 8 | `version` | `VARCHAR` | 16 | NOT NULL | `'1.0'` | - | 版本号 |
| 9 | `status` | `VARCHAR` | 16 | NOT NULL | `'Active'` | - | 状态：`Active`(生效) / `Inactive`(停用) |
| 10 | `estimated_duration_minutes` | `INT UNSIGNED` | - | NOT NULL | `0` | - | 预估总时长（分钟） |
| 11 | `setup_time_minutes` | `INT UNSIGNED` | - | NOT NULL | `0` | - | 换型/准备时间（分钟） |
| 12 | `created_at` | `DATETIME(3)` | - | NOT NULL | `CURRENT_TIMESTAMP(3)` | - | 创建时间 |
| 13 | `updated_at` | `DATETIME(3)` | - | NOT NULL | `CURRENT_TIMESTAMP(3)` | - | 更新时间 |
| 14 | `deleted_at` | `DATETIME(3)` | - | NULL | `NULL` | - | 软删除时间 |

**主键**：`pk_recipes` → `recipe_id`

**外键**：
- `fk_recipes_teams` → `default_team_id` REFERENCES `teams(team_id)` ON DELETE SET NULL

**索引**：
- `uq_recipes_code` → `recipe_code` — 编码唯一
- `ix_recipes_team` → `default_team_id` — 按团队查询 Recipe
- `ix_recipes_status` → `status` — 过滤生效/停用的 Recipe
- `ix_recipes_qty_range` → `applicable_quantity_min, applicable_quantity_max` — 按批量范围查询

**注释**：`estimated_duration_minutes` 为所有 `recipe_tasks` 的 `standard_time_minutes` 之和加上 `setup_time_minutes` 的缓存值，在 Recipe 编辑时自动更新。

---

### 5.3.7 `recipe_applicable_parts` — Recipe 适用的 Part Number（多对多关系）

> **说明**：Recipe 与 Part Number 的多对多关联表。一个 Recipe 可适用于多个 Part Number，一个 Part Number 也可匹配多个 Recipe。

| 序号 | 字段名 | 数据类型 | 长度/精度 | 可空 | 默认值 | 约束 | 说明 |
|------|--------|----------|-----------|------|--------|------|------|
| 1 | `id` | `BIGINT UNSIGNED` | - | NOT NULL | AUTO_INCREMENT | **PK** | 自增主键 |
| 2 | `recipe_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 工艺路线 |
| 3 | `part_number` | `VARCHAR` | 64 | NOT NULL | - | **FK** | 物料编码 |

**主键**：`pk_recipe_applicable_parts` → `id`

**外键**：
- `fk_rap_recipes` → `recipe_id` REFERENCES `recipes(recipe_id)` ON DELETE CASCADE
- `fk_rap_part_numbers` → `part_number` REFERENCES `part_numbers(part_number)` ON DELETE CASCADE

**索引**：
- `ix_rap_recipe` → `recipe_id` — 查询某 Recipe 适用的物料
- `ix_rap_part` → `part_number` — 查询某物料可用的 Recipe
- `uq_rap_recipe_part` → `recipe_id, part_number` — 同一组合唯一

---

### 5.3.8 `recipe_tasks` — 工艺路线任务

> **说明**：工艺路线中的单个任务/工序，如"CNC 铣面"、"钻孔"。一个 Recipe 包含多个有序的任务步骤。

| 序号 | 字段名 | 数据类型 | 长度/精度 | 可空 | 默认值 | 约束 | 说明 |
|------|--------|----------|-----------|------|--------|------|------|
| 1 | `task_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **PK** | 任务唯一标识，雪花算法 |
| 2 | `recipe_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 所属工艺路线 |
| 3 | `sequence_no` | `INT UNSIGNED` | - | NOT NULL | `1` | - | 任务顺序号（同一 Recipe 内递增） |
| 4 | `task_name` | `VARCHAR` | 128 | NOT NULL | - | - | 任务名称，如"CNC 铣面" |
| 5 | `task_type` | `VARCHAR` | 32 | NOT NULL | - | - | 任务类型：`setup`(准备) / `machining`(加工) / `assembly`(装配) / `inspection`(检验) / `material_move`(物料搬运) |
| 6 | `description` | `TEXT` | - | NULL | NULL | - | 详细说明 |
| 7 | `work_center` | `VARCHAR` | 128 | NULL | NULL | - | 具体工作中心/设备（可选） |
| 8 | `standard_time_minutes` | `INT UNSIGNED` | - | NOT NULL | `0` | - | 标准工时（分钟/件） |
| 9 | `required_skill` | `VARCHAR` | 64 | NULL | NULL | - | 所需技能等级，如"铸造高级技工" |
| 10 | `inspection_type` | `VARCHAR` | 16 | NULL | `'none'` | - | 检验类型：`self`(自检) / `mutual`(互检) / `qc`(专检) / `none`(无需检验) |

**主键**：`pk_recipe_tasks` → `task_id`

**外键**：
- `fk_rt_recipes` → `recipe_id` REFERENCES `recipes(recipe_id)` ON DELETE CASCADE

**索引**：
- `ix_rt_recipe_seq` → `recipe_id, sequence_no` — 按 Recipe 查询有序任务列表
- `ix_rt_type` → `task_type` — 按任务类型查询

---

### 5.3.9 `jobs` — 作业/工单

> **说明**：作业/工单表，排产的最顶层单元。一个 Job 对应一份生产指令，包含产品型号、数量、优先级、目标交期等核心信息。

| 序号 | 字段名 | 数据类型 | 长度/精度 | 可空 | 默认值 | 约束 | 说明 |
|------|--------|----------|-----------|------|--------|------|------|
| 1 | `job_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **PK** | 工单唯一标识，雪花算法 |
| 2 | `job_no` | `VARCHAR` | 64 | NOT NULL | - | **UQ** | 工单编号，如 `JOB-2024-0892` |
| 3 | `part_number` | `VARCHAR` | 64 | NOT NULL | - | **FK** | 产品型号，关联 `part_numbers` |
| 4 | `quantity_total` | `INT UNSIGNED` | - | NOT NULL | `0` | - | 总生产数量 |
| 5 | `quantity_mts` | `INT UNSIGNED` | - | NOT NULL | `0` | - | Make to Stock 数量 |
| 6 | `quantity_mto` | `INT UNSIGNED` | - | NOT NULL | `0` | - | Make to Order 数量 |
| 7 | `priority` | `VARCHAR` | 16 | NOT NULL | `'Normal'` | - | 优先级：`Critical`(紧急) / `High`(高) / `Normal`(普通) / `Low`(低) |
| 8 | `target_date` | `DATE` | - | NOT NULL | - | - | 目标交期 |
| 9 | `status` | `VARCHAR` | 32 | NOT NULL | `'DRAFT'` | - | 状态（见下方状态说明） |
| 10 | `created_by` | `VARCHAR` | 64 | NOT NULL | - | - | 创建人 |
| 11 | `bom_id` | `BIGINT UNSIGNED` | - | NULL | NULL | **FK** | 关联的 BOM 模板 |
| 12 | `scheduled_start` | `DATETIME(3)` | - | NULL | NULL | - | 排程后：计划开始时间 |
| 13 | `scheduled_end` | `DATETIME(3)` | - | NULL | NULL | - | 排程后：计划结束时间 |
| 14 | `actual_start` | `DATETIME(3)` | - | NULL | NULL | - | 实际开始时间 |
| 15 | `actual_end` | `DATETIME(3)` | - | NULL | NULL | - | 实际结束时间 |
| 16 | `created_at` | `DATETIME(3)` | - | NOT NULL | `CURRENT_TIMESTAMP(3)` | - | 创建时间 |
| 17 | `updated_at` | `DATETIME(3)` | - | NOT NULL | `CURRENT_TIMESTAMP(3)` | - | 更新时间 |
| 18 | `deleted_at` | `DATETIME(3)` | - | NULL | `NULL` | - | 软删除时间 |

**主键**：`pk_jobs` → `job_id`

**外键**：
- `fk_jobs_part_numbers` → `part_number` REFERENCES `part_numbers(part_number)` ON DELETE RESTRICT
- `fk_jobs_boms` → `bom_id` REFERENCES `boms(bom_id)` ON DELETE SET NULL

**索引**：
- `uq_jobs_no` → `job_no` — 工单编号唯一
- `ix_jobs_part_number` → `part_number` — 按产品型号查询 Job
- `ix_jobs_status` → `status` — 按状态查询（最常用）
- `ix_jobs_priority` → `priority` — 按优先级查询
- `ix_jobs_target_date` → `target_date` — 按交期查询
- `ix_jobs_created_by` → `created_by` — 查询某人创建的 Job
- `ix_jobs_scheduled` → `scheduled_start, scheduled_end` — 排程时间范围查询

**状态说明**：

| 状态值 | 说明 |
|--------|------|
| `DRAFT` | 草稿，刚创建 |
| `BOM_SELECTED` | 已选择 BOM |
| `RECIPE_CFG` | Recipe 配置中 |
| `READY` | 待排程 |
| `SCHEDULED` | 已排程 |
| `RELEASED` | 已释放（工单已下发） |
| `IN_PROGRESS` | 执行中 |
| `ON_HOLD` | 暂停 |
| `PARTIAL` | 部分完成 |
| `COMPLETED` | 已完成 |
| `CANCELLED` | 已取消 |

---

### 5.3.10 `job_bom_nodes` — Job 实例化的 BOM 节点

> **说明**：Job 创建时，将 BOM 树完整展开生成的实例节点。每个节点记录所需的实际数量、完成数量、选中的 Recipe 以及配置状态。通过 `parent_job_node_id` 自关联形成实例树。

| 序号 | 字段名 | 数据类型 | 长度/精度 | 可空 | 默认值 | 约束 | 说明 |
|------|--------|----------|-----------|------|--------|------|------|
| 1 | `job_node_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **PK** | 实例节点唯一标识，雪花算法 |
| 2 | `job_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 所属 Job |
| 3 | `node_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 关联的 BOM 模板节点 |
| 4 | `parent_job_node_id` | `BIGINT UNSIGNED` | - | NULL | NULL | **FK** | 父节点实例（自关联） |
| 5 | `quantity_required` | `DECIMAL` | (18,6) | NOT NULL | `0.000000` | - | 本 Job 需要该节点的总数量 |
| 6 | `quantity_completed` | `DECIMAL` | (18,6) | NOT NULL | `0.000000` | - | 已完成数量 |
| 7 | `selected_recipe_id` | `BIGINT UNSIGNED` | - | NULL | NULL | **FK** | 选定的 Recipe |
| 8 | `recipe_config_status` | `VARCHAR` | 16 | NOT NULL | `'pending'` | - | 配置状态：`pending`(待配置) / `configured`(已配置) / `skipped`(跳过) |
| 9 | `config_order` | `INT UNSIGNED` | - | NOT NULL | `0` | - | 配置顺序（倒序配置时使用，越深越先） |
| 10 | `level` | `TINYINT UNSIGNED` | - | NOT NULL | `1` | - | 层级（冗余存储，方便查询） |
| 11 | `created_at` | `DATETIME(3)` | - | NOT NULL | `CURRENT_TIMESTAMP(3)` | - | 创建时间 |
| 12 | `updated_at` | `DATETIME(3)` | - | NOT NULL | `CURRENT_TIMESTAMP(3)` | - | 更新时间 |

**主键**：`pk_job_bom_nodes` → `job_node_id`

**外键**：
- `fk_jbn_jobs` → `job_id` REFERENCES `jobs(job_id)` ON DELETE CASCADE
- `fk_jbn_bom_nodes` → `node_id` REFERENCES `bom_nodes(node_id)` ON DELETE RESTRICT
- `fk_jbn_parent` → `parent_job_node_id` REFERENCES `job_bom_nodes(job_node_id)` ON DELETE SET NULL
- `fk_jbn_recipes` → `selected_recipe_id` REFERENCES `recipes(recipe_id)` ON DELETE SET NULL

**索引**：
- `ix_jbn_job_id` → `job_id` — 按 Job 查询节点列表（高频）
- `ix_jbn_node_id` → `node_id` — 按模板节点查询实例
- `ix_jbn_parent` → `parent_job_node_id` — 查询子节点
- `ix_jbn_config_status` → `recipe_config_status` — 按配置状态过滤
- `ix_jbn_recipe` → `selected_recipe_id` — 按选中 Recipe 查询
- `ix_jbn_level` → `level` — 按层级排序（倒序配置时使用）

---

### 5.3.11 `job_recipes` — Job 中节点选择的 Recipe 记录

> **说明**：记录 Job 中每个需配置节点选中的 Recipe，包含选择人、选择时间和备注。用于审计追溯和配置历史记录。

| 序号 | 字段名 | 数据类型 | 长度/精度 | 可空 | 默认值 | 约束 | 说明 |
|------|--------|----------|-----------|------|--------|------|------|
| 1 | `job_recipe_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **PK** | 记录唯一标识，雪花算法 |
| 2 | `job_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 所属 Job |
| 3 | `job_node_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 应用的 Job BOM 节点 |
| 4 | `recipe_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 选用的 Recipe |
| 5 | `selected_by` | `VARCHAR` | 64 | NOT NULL | - | - | 选择人 |
| 6 | `selected_at` | `DATETIME(3)` | - | NOT NULL | `CURRENT_TIMESTAMP(3)` | - | 选择时间 |
| 7 | `notes` | `TEXT` | - | NULL | NULL | - | 备注说明 |

**主键**：`pk_job_recipes` → `job_recipe_id`

**外键**：
- `fk_jr_jobs` → `job_id` REFERENCES `jobs(job_id)` ON DELETE CASCADE
- `fk_jr_job_nodes` → `job_node_id` REFERENCES `job_bom_nodes(job_node_id)` ON DELETE CASCADE
- `fk_jr_recipes` → `recipe_id` REFERENCES `recipes(recipe_id)` ON DELETE RESTRICT

**索引**：
- `ix_jr_job_id` → `job_id` — 按 Job 查询选择记录
- `ix_jr_job_node` → `job_node_id` — 按节点查询选择的 Recipe
- `uq_jr_job_node` → `job_node_id` — 每个节点只能有一条有效记录（重新选择时软删除旧记录，或更新）

---

### 5.3.12 `processes` — 排程单元

> **说明**：排程的最小单元，由同一 Team 负责的、在 BOM 树中连续的节点集合合并而成。一个 Job 拆分为多个 Process，每个 Process 对应一张派工单。

| 序号 | 字段名 | 数据类型 | 长度/精度 | 可空 | 默认值 | 约束 | 说明 |
|------|--------|----------|-----------|------|--------|------|------|
| 1 | `process_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **PK** | 排程单元唯一标识，雪花算法 |
| 2 | `process_code` | `VARCHAR` | 64 | NOT NULL | - | - | 编码，如 `P-CAST-01` |
| 3 | `job_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 所属 Job |
| 4 | `team_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 执行团队 |
| 5 | `process_name` | `VARCHAR` | 128 | NOT NULL | - | - | 名称，如"缸体与缸盖铸造" |
| 6 | `process_type` | `VARCHAR` | 16 | NOT NULL | - | - | 类型：`internal`(自制) / `outsource`(委外) / `inspection`(检验) |
| 7 | `status` | `VARCHAR` | 16 | NOT NULL | `'PENDING'` | - | 状态：`PENDING`/`READY`/`SCHEDULED`/`RELEASED`/`IN_PROGRESS`/`COMPLETED`/`CANCELLED` |
| 8 | `sequence_no` | `INT UNSIGNED` | - | NOT NULL | `0` | - | 在 Job 内的排序号 |
| 9 | `scheduled_start` | `DATETIME(3)` | - | NULL | NULL | - | 计划开始时间 |
| 10 | `scheduled_end` | `DATETIME(3)` | - | NULL | NULL | - | 计划结束时间 |
| 11 | `actual_start` | `DATETIME(3)` | - | NULL | NULL | - | 实际开始时间 |
| 12 | `actual_end` | `DATETIME(3)` | - | NULL | NULL | - | 实际结束时间 |
| 13 | `priority_score` | `FLOAT` | - | NULL | NULL | - | 优先级得分（排程引擎计算） |
| 14 | `notes` | `TEXT` | - | NULL | NULL | - | 备注 |
| 15 | `created_at` | `DATETIME(3)` | - | NOT NULL | `CURRENT_TIMESTAMP(3)` | - | 创建时间 |
| 16 | `updated_at` | `DATETIME(3)` | - | NOT NULL | `CURRENT_TIMESTAMP(3)` | - | 更新时间 |
| 17 | `deleted_at` | `DATETIME(3)` | - | NULL | `NULL` | - | 软删除时间 |

**主键**：`pk_processes` → `process_id`

**外键**：
- `fk_processes_jobs` → `job_id` REFERENCES `jobs(job_id)` ON DELETE CASCADE
- `fk_processes_teams` → `team_id` REFERENCES `teams(team_id)` ON DELETE RESTRICT

**索引**：
- `ix_processes_job_id` → `job_id` — 按 Job 查询 Process 列表（高频）
- `ix_processes_team_id` → `team_id` — 按团队查询待执行 Process
- `ix_processes_status` → `status` — 按状态查询
- `ix_processes_scheduled` → `scheduled_start, scheduled_end` — 按排程时间范围查询
- `ix_processes_type` → `process_type` — 按类型过滤
- `ix_processes_job_seq` → `job_id, sequence_no` — 按 Job 内顺序查询

---

### 5.3.13 `process_tasks` — Process 内任务实例

> **说明**：Process 内展开的具体任务实例，来源于 RecipeTask。记录任务的计划/实际起止时间、执行状态、操作员等信息。

| 序号 | 字段名 | 数据类型 | 长度/精度 | 可空 | 默认值 | 约束 | 说明 |
|------|--------|----------|-----------|------|--------|------|------|
| 1 | `process_task_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **PK** | 任务实例唯一标识，雪花算法 |
| 2 | `process_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 所属 Process |
| 3 | `recipe_task_id` | `BIGINT UNSIGNED` | - | NULL | NULL | **FK** | 来源的 RecipeTask |
| 4 | `job_node_id` | `BIGINT UNSIGNED` | - | NULL | NULL | **FK** | 关联的 JobBOMNode |
| 5 | `sequence_no` | `INT UNSIGNED` | - | NOT NULL | `1` | - | 在 Process 内的顺序 |
| 6 | `task_name` | `VARCHAR` | 128 | NOT NULL | - | - | 任务名称（冗余存储，便于直接展示） |
| 7 | `planned_start` | `DATETIME(3)` | - | NULL | NULL | - | 计划开始 |
| 8 | `planned_end` | `DATETIME(3)` | - | NULL | NULL | - | 计划结束 |
| 9 | `actual_start` | `DATETIME(3)` | - | NULL | NULL | - | 实际开始 |
| 10 | `actual_end` | `DATETIME(3)` | - | NULL | NULL | - | 实际结束 |
| 11 | `status` | `VARCHAR` | 16 | NOT NULL | `'pending'` | - | 状态：`pending`(待执行) / `in_progress`(执行中) / `completed`(已完成) / `skipped`(已跳过) |
| 12 | `operator_id` | `VARCHAR` | 64 | NULL | NULL | - | 操作员 ID |

**主键**：`pk_process_tasks` → `process_task_id`

**外键**：
- `fk_pt_processes` → `process_id` REFERENCES `processes(process_id)` ON DELETE CASCADE
- `fk_pt_recipe_tasks` → `recipe_task_id` REFERENCES `recipe_tasks(task_id)` ON DELETE SET NULL
- `fk_pt_job_nodes` → `job_node_id` REFERENCES `job_bom_nodes(job_node_id)` ON DELETE SET NULL

**索引**：
- `ix_pt_process_seq` → `process_id, sequence_no` — 按 Process 查询有序任务列表（高频）
- `ix_pt_status` → `status` — 按状态查询
- `ix_pt_operator` → `operator_id` — 查询某操作员的任务
- `ix_pt_planned` → `planned_start, planned_end` — 按计划时间范围查询

---

### 5.3.14 `process_dependencies` — Process 依赖关系

> **说明**：Process 之间的依赖关系表，形成有向无环图（DAG）。排程引擎根据依赖关系确定 Process 的执行顺序。

| 序号 | 字段名 | 数据类型 | 长度/精度 | 可空 | 默认值 | 约束 | 说明 |
|------|--------|----------|-----------|------|--------|------|------|
| 1 | `dependency_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **PK** | 依赖关系唯一标识，雪花算法 |
| 2 | `job_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 所属 Job |
| 3 | `predecessor_process_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 前置 Process |
| 4 | `successor_process_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 后置 Process |
| 5 | `dependency_type` | `VARCHAR` | 32 | NOT NULL | `'finish_to_start'` | - | 依赖类型：`finish_to_start`(完成-开始) / `start_to_start`(开始-开始) / `finish_to_finish`(完成-完成) |
| 6 | `dependency_source` | `VARCHAR` | 16 | NOT NULL | `'system_generated'` | - | 来源：`system_generated`(系统生成) / `manual`(手动添加) |
| 7 | `lead_lag_minutes` | `INT` | - | NOT NULL | `0` | - | 提前/延后时间（分钟，可为负数） |

**主键**：`pk_process_dependencies` → `dependency_id`

**外键**：
- `fk_pd_jobs` → `job_id` REFERENCES `jobs(job_id)` ON DELETE CASCADE
- `fk_pd_predecessor` → `predecessor_process_id` REFERENCES `processes(process_id)` ON DELETE CASCADE
- `fk_pd_successor` → `successor_process_id` REFERENCES `processes(process_id)` ON DELETE CASCADE

**索引**：
- `ix_pd_job_id` → `job_id` — 按 Job 查询依赖关系
- `ix_pd_predecessor` → `predecessor_process_id` — 查询某 Process 的后置依赖
- `ix_pd_successor` → `successor_process_id` — 查询某 Process 的前置依赖
- `uq_pd_pre_succ` → `predecessor_process_id, successor_process_id` — 同一对 Process 之间只能有一种依赖关系

**注释**：`lead_lag_minutes` 支持负值表示"提前"（如前置 Process 完成前 X 分钟，后置即可开始），正值表示"延后"（如前置完成后等待 X 分钟）。

---

### 5.3.15 `signals` — 信号/事件

> **说明**：信号/事件表，记录触发排程或状态变更的外部事件，如物料到达、质检通过、设备就绪、手动触发等。排程引擎消费未处理的信号，驱动 Process 状态流转。

| 序号 | 字段名 | 数据类型 | 长度/精度 | 可空 | 默认值 | 约束 | 说明 |
|------|--------|----------|-----------|------|--------|------|------|
| 1 | `signal_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **PK** | 信号唯一标识，雪花算法 |
| 2 | `signal_type` | `VARCHAR` | 32 | NOT NULL | - | - | 信号类型：`material_received`(物料到达) / `quality_passed`(质检通过) / `equipment_ready`(设备就绪) / `manual_trigger`(手动触发) |
| 3 | `job_id` | `BIGINT UNSIGNED` | - | NOT NULL | - | **FK** | 关联 Job |
| 4 | `process_id` | `BIGINT UNSIGNED` | - | NULL | NULL | **FK** | 关联 Process（可选） |
| 5 | `ref_document` | `VARCHAR` | 128 | NULL | NULL | - | 关联单据号，如收货单号、质检报告号 |
| 6 | `triggered_by` | `VARCHAR` | 64 | NOT NULL | - | - | 触发人/系统名称 |
| 7 | `triggered_at` | `DATETIME(3)` | - | NOT NULL | `CURRENT_TIMESTAMP(3)` | - | 触发时间 |
| 8 | `processed` | `TINYINT` | 1 | NOT NULL | `0` | - | 是否已被排程引擎消费：0=未处理，1=已处理 |
| 9 | `processed_at` | `DATETIME(3)` | - | NULL | NULL | - | 处理时间 |
| 10 | `created_at` | `DATETIME(3)` | - | NOT NULL | `CURRENT_TIMESTAMP(3)` | - | 创建时间 |

**主键**：`pk_signals` → `signal_id`

**外键**：
- `fk_signals_jobs` → `job_id` REFERENCES `jobs(job_id)` ON DELETE CASCADE
- `fk_signals_processes` → `process_id` REFERENCES `processes(process_id)` ON DELETE SET NULL

**索引**：
- `ix_signals_job` → `job_id` — 按 Job 查询信号
- `ix_signals_process` → `process_id` — 按 Process 查询信号
- `ix_signals_type` → `signal_type` — 按类型查询
- `ix_signals_processed` → `processed` — 查询未处理信号（排程引擎消费用，高频）
- `ix_signals_triggered` → `triggered_at` — 按触发时间排序

**注释**：排程引擎定期扫描 `processed = 0` 的信号，根据信号类型驱动对应的 Process 状态变更。处理完成后将 `processed` 设为 1 并记录 `processed_at`，避免重复消费。

---

## 5.4 索引设计

### 5.4.1 索引汇总表

| 表名 | 索引名 | 类型 | 字段 | 说明 |
|------|--------|------|------|------|
| `part_numbers` | `pk_part_numbers` | PRIMARY | `part_number` | 主键 |
| `part_numbers` | `ix_part_numbers_category` | BTREE | `part_category` | 按类别查询 |
| `part_numbers` | `ix_part_numbers_active` | BTREE | `is_active` | 过滤启用状态 |
| `boms` | `pk_boms` | PRIMARY | `bom_id` | 主键 |
| `boms` | `ix_boms_part_number` | BTREE | `part_number` | 按产品型号查询 |
| `boms` | `ix_boms_status` | BTREE | `version_status` | 按版本状态查询 |
| `boms` | `uq_boms_part_version` | UNIQUE | `part_number, version` | 版本唯一约束 |
| `bom_nodes` | `pk_bom_nodes` | PRIMARY | `node_id` | 主键 |
| `bom_nodes` | `ix_bom_nodes_bom_id` | BTREE | `bom_id` | 按 BOM 查询节点 |
| `bom_nodes` | `ix_bom_nodes_part_number` | BTREE | `part_number` | 按物料编码查询 |
| `bom_nodes` | `ix_bom_nodes_type` | BTREE | `node_type` | 区分中间/叶子节点 |
| `bom_nodes` | `ix_bom_nodes_level` | BTREE | `level` | 按层级查询 |
| `bom_node_relations` | `pk_bom_node_relations` | PRIMARY | `relation_id` | 主键 |
| `bom_node_relations` | `ix_bnr_bom_id` | BTREE | `bom_id` | 按 BOM 查询关系 |
| `bom_node_relations` | `ix_bnr_parent` | BTREE | `parent_node_id` | 查询子节点 |
| `bom_node_relations` | `ix_bnr_child` | BTREE | `child_node_id` | 查询父节点 |
| `bom_node_relations` | `uq_bnr_parent_child` | UNIQUE | `parent_node_id, child_node_id` | 父子关系唯一 |
| `teams` | `pk_teams` | PRIMARY | `team_id` | 主键 |
| `teams` | `uq_teams_code` | UNIQUE | `team_code` | 编码唯一 |
| `teams` | `ix_teams_type` | BTREE | `team_type` | 按类型查询 |
| `teams` | `ix_teams_parent` | BTREE | `parent_team_id` | 查询子团队 |
| `teams` | `ix_teams_active` | BTREE | `is_active` | 过滤启用状态 |
| `recipes` | `pk_recipes` | PRIMARY | `recipe_id` | 主键 |
| `recipes` | `uq_recipes_code` | UNIQUE | `recipe_code` | 编码唯一 |
| `recipes` | `ix_recipes_team` | BTREE | `default_team_id` | 按团队查询 |
| `recipes` | `ix_recipes_status` | BTREE | `status` | 过滤生效状态 |
| `recipes` | `ix_recipes_qty_range` | BTREE | `applicable_quantity_min, applicable_quantity_max` | 批量范围查询 |
| `recipe_applicable_parts` | `pk_recipe_applicable_parts` | PRIMARY | `id` | 主键 |
| `recipe_applicable_parts` | `ix_rap_recipe` | BTREE | `recipe_id` | 按 Recipe 查询 |
| `recipe_applicable_parts` | `ix_rap_part` | BTREE | `part_number` | 按物料查询 |
| `recipe_applicable_parts` | `uq_rap_recipe_part` | UNIQUE | `recipe_id, part_number` | 组合唯一 |
| `recipe_tasks` | `pk_recipe_tasks` | PRIMARY | `task_id` | 主键 |
| `recipe_tasks` | `ix_rt_recipe_seq` | BTREE | `recipe_id, sequence_no` | 有序任务查询 |
| `recipe_tasks` | `ix_rt_type` | BTREE | `task_type` | 按任务类型查询 |
| `jobs` | `pk_jobs` | PRIMARY | `job_id` | 主键 |
| `jobs` | `uq_jobs_no` | UNIQUE | `job_no` | 工单编号唯一 |
| `jobs` | `ix_jobs_part_number` | BTREE | `part_number` | 按产品查询 |
| `jobs` | `ix_jobs_status` | BTREE | `status` | 按状态查询 |
| `jobs` | `ix_jobs_priority` | BTREE | `priority` | 按优先级查询 |
| `jobs` | `ix_jobs_target_date` | BTREE | `target_date` | 按交期查询 |
| `jobs` | `ix_jobs_created_by` | BTREE | `created_by` | 按创建人查询 |
| `jobs` | `ix_jobs_scheduled` | BTREE | `scheduled_start, scheduled_end` | 排程时间范围 |
| `job_bom_nodes` | `pk_job_bom_nodes` | PRIMARY | `job_node_id` | 主键 |
| `job_bom_nodes` | `ix_jbn_job_id` | BTREE | `job_id` | 按 Job 查询（高频） |
| `job_bom_nodes` | `ix_jbn_node_id` | BTREE | `node_id` | 按模板节点查询 |
| `job_bom_nodes` | `ix_jbn_parent` | BTREE | `parent_job_node_id` | 查询子节点 |
| `job_bom_nodes` | `ix_jbn_config_status` | BTREE | `recipe_config_status` | 按配置状态过滤 |
| `job_bom_nodes` | `ix_jbn_level` | BTREE | `level` | 按层级排序 |
| `job_recipes` | `pk_job_recipes` | PRIMARY | `job_recipe_id` | 主键 |
| `job_recipes` | `ix_jr_job_id` | BTREE | `job_id` | 按 Job 查询 |
| `job_recipes` | `uq_jr_job_node` | UNIQUE | `job_node_id` | 节点 Recipe 唯一 |
| `processes` | `pk_processes` | PRIMARY | `process_id` | 主键 |
| `processes` | `ix_processes_job_id` | BTREE | `job_id` | 按 Job 查询（高频） |
| `processes` | `ix_processes_team_id` | BTREE | `team_id` | 按团队查询 |
| `processes` | `ix_processes_status` | BTREE | `status` | 按状态查询 |
| `processes` | `ix_processes_scheduled` | BTREE | `scheduled_start, scheduled_end` | 时间范围查询 |
| `processes` | `ix_processes_job_seq` | BTREE | `job_id, sequence_no` | Job 内排序 |
| `process_tasks` | `pk_process_tasks` | PRIMARY | `process_task_id` | 主键 |
| `process_tasks` | `ix_pt_process_seq` | BTREE | `process_id, sequence_no` | 有序任务查询（高频） |
| `process_tasks` | `ix_pt_status` | BTREE | `status` | 按状态查询 |
| `process_tasks` | `ix_pt_operator` | BTREE | `operator_id` | 按操作员查询 |
| `process_dependencies` | `pk_process_dependencies` | PRIMARY | `dependency_id` | 主键 |
| `process_dependencies` | `ix_pd_job_id` | BTREE | `job_id` | 按 Job 查询 |
| `process_dependencies` | `ix_pd_predecessor` | BTREE | `predecessor_process_id` | 查询后置依赖 |
| `process_dependencies` | `ix_pd_successor` | BTREE | `successor_process_id` | 查询前置依赖 |
| `process_dependencies` | `uq_pd_pre_succ` | UNIQUE | `predecessor_process_id, successor_process_id` | 依赖唯一 |
| `signals` | `pk_signals` | PRIMARY | `signal_id` | 主键 |
| `signals` | `ix_signals_job` | BTREE | `job_id` | 按 Job 查询 |
| `signals` | `ix_signals_type` | BTREE | `signal_type` | 按类型查询 |
| `signals` | `ix_signals_processed` | BTREE | `processed` | 查询未处理信号（高频） |
| `signals` | `ix_signals_triggered` | BTREE | `triggered_at` | 按时间排序 |

### 5.4.2 索引统计

| 类别 | 数量 | 说明 |
|------|------|------|
| 主键索引（PRIMARY） | 15 | 每张表 1 个 |
| 唯一索引（UNIQUE） | 8 | 业务唯一性约束 |
| 普通索引（BTREE） | 52 | 高频查询字段 |
| **合计** | **75** | |

---

## 5.5 关键查询场景与索引策略

### 5.5.1 查询场景汇总

| 序号 | 查询场景 | 业务模块 | 频率 | 索引方案 |
|------|----------|----------|------|----------|
| 1 | 按 Job 查询所有 Process 列表 | 排程预览/甘特图 | **极高** | `ix_processes_job_id` |
| 2 | 按 Job 查询所有 JobBOMNode 树 | Recipe 配置 | **极高** | `ix_jbn_job_id` |
| 3 | 查询某团队的待执行 Process | 车间作业看板 | **高** | `ix_processes_team_id` + `ix_processes_status` |
| 4 | 查询未处理的 Signal | 排程引擎定时任务 | **高** | `ix_signals_processed` |
| 5 | 按状态查询 Job 列表 | Job 管理首页 | **高** | `ix_jobs_status` |
| 6 | 按 BOM 查询完整节点和关系树 | BOM 选择/预览 | **高** | `ix_bom_nodes_bom_id` + `ix_bnr_bom_id` |
| 7 | 按 Recipe 查询有序 Task 列表 | Recipe 详情展示 | **中** | `ix_rt_recipe_seq` |
| 8 | 查询某 Job 的 Process 依赖图 | 排程引擎/关键路径 | **中** | `ix_pd_job_id` + `ix_pd_predecessor/successor` |
| 9 | 按产品型号 + 批量匹配可用 Recipe | Recipe 推荐 | **中** | `ix_rap_part` + `ix_recipes_qty_range` |
| 10 | 按排程时间范围查询 Process | 产能负荷分析 | **中** | `ix_processes_scheduled` |

### 5.5.2 关键查询场景详细分析

#### 场景 1：按 Job 查询所有 Process 列表

```sql
-- 甘特图展示、Process 汇总表
SELECT p.*, t.team_name, t.team_code
FROM processes p
  INNER JOIN teams t ON p.team_id = t.team_id
WHERE p.job_id = ? AND p.deleted_at IS NULL
ORDER BY p.sequence_no;
```

**索引使用**：`ix_processes_job_id` (BTREE on `job_id`) → 快速定位某 Job 的所有 Process，按 `sequence_no` 排序输出。

**优化建议**：`job_id` 为高频过滤条件，单独索引比复合索引更灵活，可与其他条件（如 `status`）组合使用。

---

#### 场景 2：按 Job 查询 JobBOMNode 完整树

```sql
-- Recipe 配置页面左侧 BOM 树
SELECT jbn.*, bn.part_number, pn.part_name, pn.part_category,
       r.recipe_code, r.name as recipe_name
FROM job_bom_nodes jbn
  INNER JOIN bom_nodes bn ON jbn.node_id = bn.node_id
  INNER JOIN part_numbers pn ON bn.part_number = pn.part_number
  LEFT JOIN recipes r ON jbn.selected_recipe_id = r.recipe_id
WHERE jbn.job_id = ?
ORDER BY jbn.level, jbn.config_order;
```

**索引使用**：`ix_jbn_job_id` (BTREE on `job_id`) → 一次性取出某 Job 的所有实例节点。配合 `ORDER BY jbn.level` 实现倒序配置展示。

---

#### 场景 3：查询某团队的待执行 Process

```sql
-- 车间作业看板
SELECT p.*, j.job_no, j.priority, j.target_date
FROM processes p
  INNER JOIN jobs j ON p.job_id = j.job_id
WHERE p.team_id = ?
  AND p.status IN ('READY', 'SCHEDULED', 'RELEASED')
  AND p.deleted_at IS NULL
ORDER BY p.priority_score DESC, p.scheduled_start;
```

**索引使用**：`ix_processes_team_id` + `ix_processes_status` → 先按 `team_id` 过滤，再按 `status` 过滤。若数据库支持 Index Merge，两个独立索引可满足；否则建议创建复合索引 `ix_processes_team_status` on `(team_id, status)`。

---

#### 场景 4：查询未处理的 Signal（排程引擎消费）

```sql
-- 排程引擎定时任务（每 30 秒执行一次）
SELECT * FROM signals
WHERE processed = 0
ORDER BY triggered_at
LIMIT 100;
```

**索引使用**：`ix_signals_processed` (BTREE on `processed`) → 快速定位未处理信号。由于 `processed = 0` 的记录量有限（随消费不断减少），此索引效率极高。

**优化建议**：考虑将已处理信号定期归档至历史表，保持 `signals` 表的数据量在可控范围内。

---

#### 场景 5：按状态查询 Job 列表

```sql
-- Job 管理首页
SELECT j.*, pn.part_name
FROM jobs j
  INNER JOIN part_numbers pn ON j.part_number = pn.part_number
WHERE j.status = ?
  AND j.deleted_at IS NULL
ORDER BY j.created_at DESC
LIMIT 20 OFFSET ?;
```

**索引使用**：`ix_jobs_status` (BTREE on `status`) → 按状态过滤。配合 `ORDER BY created_at DESC` 实现分页查询。

---

#### 场景 6：按 BOM 查询完整节点和关系树

```sql
-- BOM 选择页面展示完整树
-- 步骤 1：查询所有节点
SELECT * FROM bom_nodes WHERE bom_id = ?;
-- 步骤 2：查询所有关系
SELECT * FROM bom_node_relations WHERE bom_id = ? ORDER BY sort_order;
```

**索引使用**：`ix_bom_nodes_bom_id` + `ix_bnr_bom_id` → 分别取出节点和边，在应用层组装为树结构。

---

#### 场景 7：按 Recipe 查询有序 Task 列表

```sql
-- Recipe 详情展开
SELECT * FROM recipe_tasks
WHERE recipe_id = ?
ORDER BY sequence_no;
```

**索引使用**：`ix_rt_recipe_seq` (BTREE on `recipe_id, sequence_no`) → 覆盖查询，一步到位获取有序任务列表。

---

#### 场景 8：查询某 Job 的 Process 依赖图

```sql
-- 排程引擎构建 DAG、关键路径分析
SELECT pd.*, pp.process_code as pre_code, sp.process_code as succ_code
FROM process_dependencies pd
  INNER JOIN processes pp ON pd.predecessor_process_id = pp.process_id
  INNER JOIN processes sp ON pd.successor_process_id = sp.process_id
WHERE pd.job_id = ?;
```

**索引使用**：`ix_pd_job_id` (BTREE on `job_id`) → 取出某 Job 的所有依赖边。排程引擎在内存中构建 DAG 进行拓扑排序。

---

#### 场景 9：按产品型号 + 批量匹配可用 Recipe

```sql
-- Recipe 推荐引擎
SELECT r.*
FROM recipes r
  INNER JOIN recipe_applicable_parts rap ON r.recipe_id = rap.recipe_id
WHERE rap.part_number = ?
  AND r.status = 'Active'
  AND r.deleted_at IS NULL
  AND r.applicable_quantity_min <= ?
  AND (r.applicable_quantity_max IS NULL OR r.applicable_quantity_max >= ?);
```

**索引使用**：`ix_rap_part` (BTREE on `part_number`) 定位适用的 Recipe → `ix_recipes_status` 过滤生效状态 → `ix_recipes_qty_range` 筛选批量范围。

---

#### 场景 10：按排程时间范围查询 Process

```sql
-- 产能负荷分析、甘特图数据
SELECT p.*, t.team_name
FROM processes p
  INNER JOIN teams t ON p.team_id = t.team_id
WHERE p.scheduled_start BETWEEN ? AND ?
  AND p.deleted_at IS NULL
ORDER BY p.team_id, p.scheduled_start;
```

**索引使用**：`ix_processes_scheduled` (BTREE on `scheduled_start, scheduled_end`) → 快速定位排程时间范围内的 Process。适合甘特图展示和产能冲突检测。

---

### 5.5.3 复合索引建议（高并发场景）

在高并发制造业环境中，以下复合索引可进一步提升性能：

| 索引名 | 表 | 字段 | 适用场景 |
|--------|------|------|----------|
| `ix_processes_team_status` | `processes` | `team_id, status` | 车间看板高频查询 |
| `ix_jobs_status_created` | `jobs` | `status, created_at` | Job 列表分页 |
| `ix_signals_processed_triggered` | `signals` | `processed, triggered_at` | 信号消费排序 |
| `ix_jbn_job_status` | `job_bom_nodes` | `job_id, recipe_config_status` | 查询待配置节点 |

---

## 5.6 数据量估算

### 5.6.1 估算假设

以**中型离散制造企业**为基准：

| 假设项 | 数值 | 说明 |
|--------|------|------|
| 产品型号（SKU）数量 | 500 | 包括在售产品和历史产品 |
| 日均新建 Job 数 | 20 | 工作日 |
| 年均工作日 | 250 | 排除节假日 |
| BOM 平均节点数 | 50 | 含中间节点和叶子节点 |
| 平均 Recipe 数/产品 | 3 | 不同批量对应不同工艺 |
| 平均 Process 数/Job | 15 | 按 Team 聚合后的排程单元 |
| 平均 Task 数/Process | 5 | 每个 Process 内的工序数 |
| 团队（Team）数量 | 30 | 含车间、产线、供应商 |

### 5.6.2 各表数据量估算

| 表名 | 单条大小(约) | 初始存量 | 日增量 | 年增量 | 3 年总量(估算) | 增长特征 |
|------|-------------|----------|--------|--------|----------------|----------|
| `part_numbers` | 0.5 KB | 5,000 | 5 | 1,250 | 8,750 | 缓慢增长，主数据 |
| `boms` | 0.3 KB | 1,500 | 2 | 500 | 3,000 | 缓慢增长，版本变更产生新记录 |
| `bom_nodes` | 0.3 KB | 75,000 | 100 | 25,000 | 150,000 | 与 BOM 数量成正比 |
| `bom_node_relations` | 0.2 KB | 74,000 | 99 | 24,750 | 148,500 | 约 = BOM 节点数 - BOM 数 |
| `teams` | 0.5 KB | 30 | 0 | 2 | 36 | 几乎不变，配置型数据 |
| `recipes` | 0.5 KB | 5,000 | 5 | 1,250 | 8,750 | 缓慢增长，工艺积累 |
| `recipe_applicable_parts` | 0.1 KB | 15,000 | 15 | 3,750 | 26,250 | 与 Recipe 数成正比 |
| `recipe_tasks` | 0.3 KB | 50,000 | 50 | 12,500 | 87,500 | 每个 Recipe 平均 10 个任务 |
| `jobs` | 0.5 KB | 50,000 | 20 | 5,000 | 65,000 | 稳定增长，核心业务数据 |
| `job_bom_nodes` | 0.3 KB | 2,500,000 | 1,000 | 250,000 | 3,250,000 | 高增速，= Job × 平均节点数 |
| `job_recipes` | 0.3 KB | 1,250,000 | 500 | 125,000 | 1,625,000 | 与中间节点配置数成正比 |
| `processes` | 0.5 KB | 750,000 | 300 | 75,000 | 975,000 | 高增速，= Job × 平均 Process 数 |
| `process_tasks` | 0.3 KB | 3,750,000 | 1,500 | 375,000 | 4,875,000 | 最高增速，= Process × 平均 Task 数 |
| `process_dependencies` | 0.2 KB | 1,500,000 | 600 | 150,000 | 1,950,000 | 与 Process 数成正比，约 2× |
| `signals` | 0.3 KB | 500,000 | 100 | 25,000 | 575,000 | 中增速，事件驱动型 |

### 5.6.3 数据库容量估算

| 时间维度 | 数据总量（行数） | 纯数据容量（约） | 含索引容量（约） |
|----------|-----------------|-----------------|-----------------|
| 初始部署 | ~10,644,530 | ~3.2 GB | ~8 GB |
| 运行 1 年后 | ~10,944,530 | ~3.5 GB | ~9 GB |
| 运行 3 年后 | ~12,649,030 | ~4.5 GB | ~12 GB |

> **说明**：
> 1. 纯数据容量按平均每行 0.3 KB 估算；索引容量约为数据容量的 1.5~2 倍。
> 2. `process_tasks` 和 `job_bom_nodes` 是数据量最大的两张表，合计占总数据量的 60% 以上。
> 3. 随着系统运行，建议对 `process_tasks`、`job_bom_nodes`、`process_dependencies` 等历史数据实施**归档策略**（如将超过 2 年的已完成 Job 相关数据迁移到历史库），以保持主库查询性能。

### 5.6.4 归档策略建议

| 表名 | 归档条件 | 归档周期 | 归档方式 |
|------|----------|----------|----------|
| `process_tasks` | 所属 Job 已完成且超过 1 年 | 每月 | 迁移至历史库 `process_tasks_history` |
| `process_dependencies` | 所属 Job 已完成且超过 1 年 | 每月 | 迁移至历史库 |
| `job_bom_nodes` | 所属 Job 已完成且超过 1 年 | 每月 | 迁移至历史库 |
| `job_recipes` | 所属 Job 已完成且超过 1 年 | 每月 | 迁移至历史库 |
| `processes` | Job 已完成且超过 2 年 | 每季度 | 迁移至历史库 |
| `signals` | 已处理且超过 3 个月 | 每周 | 直接删除或迁移 |

---

## 附录 A：DDL 语句示例（MySQL）

以下为建表语句的核心示例，供开发参考：

```sql
-- 示例：jobs 表
CREATE TABLE jobs (
    job_id BIGINT UNSIGNED NOT NULL COMMENT '工单唯一标识（雪花算法）',
    job_no VARCHAR(64) NOT NULL COMMENT '工单编号',
    part_number VARCHAR(64) NOT NULL COMMENT '产品型号',
    quantity_total INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '总生产数量',
    quantity_mts INT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'MTS数量',
    quantity_mto INT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'MTO数量',
    priority VARCHAR(16) NOT NULL DEFAULT 'Normal' COMMENT '优先级',
    target_date DATE NOT NULL COMMENT '目标交期',
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT' COMMENT '状态',
    created_by VARCHAR(64) NOT NULL COMMENT '创建人',
    bom_id BIGINT UNSIGNED NULL COMMENT '关联BOM',
    scheduled_start DATETIME(3) NULL COMMENT '计划开始',
    scheduled_end DATETIME(3) NULL COMMENT '计划结束',
    actual_start DATETIME(3) NULL COMMENT '实际开始',
    actual_end DATETIME(3) NULL COMMENT '实际结束',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
    deleted_at DATETIME(3) NULL DEFAULT NULL COMMENT '软删除时间',
    PRIMARY KEY (job_id),
    UNIQUE KEY uq_jobs_no (job_no),
    KEY ix_jobs_part_number (part_number),
    KEY ix_jobs_status (status),
    KEY ix_jobs_priority (priority),
    KEY ix_jobs_target_date (target_date),
    KEY ix_jobs_created_by (created_by),
    KEY ix_jobs_scheduled (scheduled_start, scheduled_end),
    CONSTRAINT fk_jobs_part_numbers FOREIGN KEY (part_number) REFERENCES part_numbers(part_number) ON DELETE RESTRICT,
    CONSTRAINT fk_jobs_boms FOREIGN KEY (bom_id) REFERENCES boms(bom_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='作业/工单表';
```

## 附录 B：术语表

| 术语 | 说明 |
|------|------|
| PK | Primary Key，主键 |
| FK | Foreign Key，外键 |
| IX | Index，普通索引 |
| UQ | Unique，唯一索引 |
| BTREE | B-Tree 索引，MySQL InnoDB 默认索引类型 |
| DAG | Directed Acyclic Graph，有向无环图 |
| 雪花算法 | Snowflake ID，分布式唯一 ID 生成算法 |
| 软删除 | Logical Delete，通过标记删除时间实现逻辑删除 |
| 归档 | Archive，将历史数据迁移至存储成本更低的介质 |

---

> **文档结束**  
> 本文档为 Job 拆分排产系统的完整数据库设计，包含 15 张表的字段定义、索引设计、查询优化策略和数据量估算，指导后续的数据库 DDL 创建和应用程序开发。
# Job 拆分排产系统 — 接口设计（第 3 部分）

> 版本：v1.0  
> 作者：系统架构师  
> 定位：基于业务概念设计（concept_design.md）的 RESTful API 完整接口规范  
> 基础路径：`/api/v1`

---

## 目录

- [第 6 章：接口设计](#第-6-章接口设计)
  - [6.1 接口规范](#61-接口规范)
  - [6.2 接口清单](#62-接口清单)
  - [6.3 WebSocket 实时通知](#63-websocket-实时通知)
  - [6.4 接口安全](#64-接口安全)

---

## 第 6 章：接口设计

### 6.1 接口规范

#### 6.1.1 基础规范

| 项目 | 规范 |
|------|------|
| 通信协议 | HTTPS |
| 数据格式 | JSON（application/json） |
| 字符编码 | UTF-8 |
| 基础路径（Base URL） | `/api/v1` |
| 请求体编码 | Content-Type: application/json |
| 日期时间格式 | ISO 8601：`2024-08-15T09:30:00+08:00` |
| 日期格式 | `YYYY-MM-DD`，如 `2024-08-15` |
| 字段命名规范 | snake_case（下划线命名） |
| 时区 | 默认东八区（Asia/Shanghai），API 均返回带时区偏移的时间 |

#### 6.1.2 通用响应格式

所有 API 响应均遵循以下统一格式：

```json
{
  "code": 200,
  "message": "success",
  "data": {},
  "timestamp": 1714982400000,
  "request_id": "req_abc123xyz789"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| code | int | 业务状态码，`200` 表示成功，非 `200` 表示错误或异常 |
| message | string | 状态描述，成功时通常为 `"success"`，失败时为错误说明 |
| data | object / array / null | 响应数据体，具体结构由各个接口定义 |
| timestamp | long | 服务器响应时间戳（Unix 毫秒） |
| request_id | string | 请求唯一标识，用于链路追踪和问题排查 |

**成功响应示例：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "part_number": "ENG-D250",
    "status": "DRAFT"
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240815093000123456"
}
```

**失败响应示例：**

```json
{
  "code": 40001,
  "message": "参数校验失败：生产数量必须大于 0",
  "data": {
    "field": "quantity_total",
    "rejected_value": 0,
    "hint": "生产数量必须为正整数，范围 1~999999"
  },
  "timestamp": 1714982400123,
  "request_id": "req_20240815093000123457"
}
```

#### 6.1.3 错误码定义

系统采用 **5 位数字错误码**，前 3 位为类别，后 2 位为具体错误。

| 错误码 | 类别 | 含义 | 说明 |
|--------|------|------|------|
| 200 | 成功 | 请求成功 | 通用成功状态码 |

**系统级错误（500xx）**

| 错误码 | 含义 | 触发场景 |
|--------|------|---------|
| 50000 | 系统内部错误 | 未预期的服务端异常 |
| 50001 | 服务暂时不可用 | 系统维护或过载保护 |
| 50002 | 数据库操作失败 | 数据库连接异常或写入失败 |
| 50003 | 缓存服务异常 | Redis / 缓存集群不可用 |
| 50004 | 外部服务调用失败 | 调用的下游服务超时或异常 |
| 50005 | 消息队列异常 | MQ 发布/消费失败 |
| 50006 | 排程引擎异常 | 排程引擎内部计算错误 |

**参数错误（400xx）**

| 错误码 | 含义 | 触发场景 |
|--------|------|---------|
| 40000 | 参数校验失败 | 通用参数非法（缺少、类型错误、格式不符） |
| 40001 | 必填参数缺失 | 某个必填字段未提供 |
| 40002 | 参数格式错误 | 字符串格式、日期格式、JSON 格式等不符合要求 |
| 40003 | 参数值超出范围 | 数值超出允许的最小/最大值 |
| 40004 | 参数值格式不匹配正则 | 编码类字段（如 Job ID）格式不符合规范 |
| 40005 | 数组参数元素数量超限 | 批量操作传入的数组长度超过上限（如最多 100 条） |
| 40006 | 参数值不在枚举范围内 | 传入的枚举值不在系统定义的可选值列表中 |
| 40007 | 日期范围不合法 | 开始时间大于结束时间，或日期格式错误 |
| 40008 | JSON 结构错误 | 请求体 JSON 解析失败或结构不符合 Schema |

**业务错误（401xx）**

| 错误码 | 含义 | 触发场景 |
|--------|------|---------|
| 40100 | 业务规则校验失败 | 通用业务逻辑错误 |
| 40101 | Part Number 不存在 | 传入的产品型号未在系统中维护 |
| 40102 | BOM 不存在或不可用 | 指定的 BOM 不存在或版本状态非 Active |
| 40103 | Recipe 不存在或不可用 | 指定的 Recipe 不存在或状态为 Inactive |
| 40104 | 该节点无匹配的 Recipe | BOM 节点找不到任何可用的 Recipe |
| 40105 | Recipe 适用批量不匹配 | Recipe 的适用数量范围与 Job 数量不匹配 |
| 40106 | BOM 展开失败 | BOM 树结构异常（如存在循环引用） |
| 40107 | Process 生成失败 | 依赖图存在环或缺少必要的 Recipe 配置 |

**状态错误（409xx）**

| 错误码 | 含义 | 触发场景 |
|--------|------|---------|
| 40900 | 状态冲突 | 通用状态转换错误 |
| 40901 | Job 当前状态不允许此操作 | 如尝试更新非 DRAFT 状态的 Job |
| 40902 | Recipe 配置未完成 | 在 Recipe 未全部配置时尝试生成 Process |
| 40903 | Process 已存在 | 当前 Job 已生成 Process，不可重复生成 |
| 40904 | 排程结果不存在 | 查询排程结果但该 Job 尚未排程 |
| 40905 | 该 Process 不处于可排程状态 | Process 状态非 ready / pending 时尝试排程 |
| 40906 | Process 依赖图存在循环 | Process 间的依赖关系构成环路 |
| 40907 | 排程引擎正在运行中 | 同一 Job 的排程请求并发冲突 |
| 40908 | 已释放的 Job 不可取消 | RELEASED 或 IN_PROGRESS 状态的 Job 不允许取消 |
| 40909 | Signal 已处理或已过期 | 尝试处理已消费或已过期的信号 |

**权限错误（403xx）**

| 错误码 | 含义 | 触发场景 |
|--------|------|---------|
| 40300 | 无权限执行此操作 | 通用权限不足 |
| 40301 | Token 无效或已过期 | JWT Token 解析失败或过期 |
| 40302 | 角色权限不足 | 当前用户角色无权执行该操作（如普通用户尝试取消已排程 Job） |
| 40303 | 资源访问越权 | 用户尝试访问不属于自己/本部门的 Job |
| 40304 | 接口调用频率超限 | 触发接口限流保护 |
| 40305 | 签名验证失败 | 请求签名不匹配或时间戳偏差过大（重放攻击防护） |

**未找到（404xx）**

| 错误码 | 含义 | 触发场景 |
|--------|------|---------|
| 40400 | 资源不存在 | 通用 404 |
| 40401 | Job 不存在 | 指定的 job_id 未找到 |
| 40402 | BOM 不存在 | 指定的 bom_id 未找到 |
| 40403 | Recipe 不存在 | 指定的 recipe_id 未找到 |
| 40404 | Process 不存在 | 指定的 process_id 未找到 |
| 40405 | BOM 节点不存在 | 指定的 node_id 未找到 |
| 40406 | Signal 不存在 | 指定的 signal_id 未找到 |
| 40407 | Team 不存在 | 指定的 team_id 未找到 |

#### 6.1.4 分页规范

对于返回列表的查询接口，统一使用以下分页参数和响应格式。

**请求参数（Query）：**

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| page | int | 否 | 1 | 页码，从 1 开始 |
| page_size | int | 否 | 20 | 每页数量，可选值：10, 20, 50, 100 |

**响应格式：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 100,
      "total_pages": 5
    }
  },
  "timestamp": 1714982400000,
  "request_id": "req_abc123xyz789"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| list | array | 数据列表 |
| pagination.page | int | 当前页码 |
| pagination.page_size | int | 每页数量 |
| pagination.total | int | 总记录数 |
| pagination.total_pages | int | 总页数（自动计算） |

---

### 6.2 接口清单

#### 6.2.1 Job 管理接口

| 序号 | 接口名称 | 方法 | 路径 | 说明 |
|------|---------|------|------|------|
| J1 | 创建 Job | POST | `/jobs` | 创建新 Job，录入基础信息 |
| J2 | 查询 Job 列表 | GET | `/jobs` | 支持分页、多维度筛选 |
| J3 | 获取 Job 详情 | GET | `/jobs/{job_id}` | 包含基础信息、BOM、Recipe 配置状态 |
| J4 | 更新 Job | PUT | `/jobs/{job_id}` | 更新基础信息，仅限 DRAFT 状态 |
| J5 | 删除 Job | DELETE | `/jobs/{job_id}` | 软删除，仅限特定状态 |
| J6 | 提交排程 | POST | `/jobs/{job_id}/schedule` | 将 Job 提交给排程引擎 |
| J7 | 取消排程 | POST | `/jobs/{job_id}/unschedule` | 取消已排程的 Job |
| J8 | 释放执行 | POST | `/jobs/{job_id}/release` | 将已排程的 Job 释放到车间 |
| J9 | 暂停 Job | POST | `/jobs/{job_id}/pause` | 暂停执行中的 Job |
| J10 | 恢复 Job | POST | `/jobs/{job_id}/resume` | 恢复暂停的 Job |

---

**J1. 创建 Job**

- **接口：** `POST /jobs`
- **权限：** production_planner, admin
- **说明：** 创建新 Job，录入产品型号、数量、优先级等基础信息。创建成功后 Job 状态为 `DRAFT`。

**请求参数（Request Body）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| part_number | string | 是 | 产品型号（Part Number），必须在系统中已维护 | "ENG-D250" |
| quantity_total | int | 是 | 总生产数量，范围 1~999999 | 100 |
| quantity_mts | int | 是 | Make to Stock 数量 | 20 |
| quantity_mto | int | 是 | Make to Order 数量 | 80 |
| priority | string | 是 | 优先级：Critical / High / Normal / Low | "High" |
| target_date | string | 是 | 目标交期（YYYY-MM-DD），必须 >= 今天+1 | "2024-08-30" |
| customer_order_no | string | 否 | 客户订单号 | "CO-2024-5678" |
| notes | string | 否 | 备注说明 | "客户要求加急，优先安排" |

**请求示例：**

```json
{
  "part_number": "ENG-D250",
  "quantity_total": 100,
  "quantity_mts": 20,
  "quantity_mto": 80,
  "priority": "High",
  "target_date": "2024-08-30",
  "customer_order_no": "CO-2024-5678",
  "notes": "客户要求加急，优先安排"
}
```

**校验规则：**

- `quantity_total` 必须等于 `quantity_mts` + `quantity_mto`
- `quantity_total` > 0 且 <= 999999
- `target_date` >= 当前日期 + 1 天
- `part_number` 必须在 PartNumber 主数据中存在

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "part_number": "ENG-D250",
    "part_name": "2.5L 柴油发动机",
    "quantity_total": 100,
    "quantity_mts": 20,
    "quantity_mto": 80,
    "priority": "High",
    "target_date": "2024-08-30",
    "status": "DRAFT",
    "customer_order_no": "CO-2024-5678",
    "notes": "客户要求加急，优先安排",
    "created_by": "user_001",
    "created_at": "2024-08-01T10:30:00+08:00",
    "bom_id": null,
    "available_bom_count": 3
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801103000123456"
}
```

**失败响应（示例）：**

```json
{
  "code": 40001,
  "message": "参数校验失败：quantity_mts + quantity_mto 必须等于 quantity_total",
  "data": {
    "field": "quantity_total",
    "hint": "MTS(20) + MTO(90) = 110，不等于 total(100)"
  },
  "timestamp": 1714982400123,
  "request_id": "req_20240801103000123457"
}
```

---

**J2. 查询 Job 列表**

- **接口：** `GET /jobs`
- **权限：** production_planner, production_manager, admin
- **说明：** 分页查询 Job 列表，支持多维度筛选和排序。

**请求参数（Query）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| page | int | 否 | 页码，默认 1 | 1 |
| page_size | int | 否 | 每页数量，默认 20 | 20 |
| status | string | 否 | 状态筛选（支持多选，逗号分隔） | "DRAFT,READY,SCHEDULED" |
| priority | string | 否 | 优先级筛选 | "High" |
| part_number | string | 否 | 产品型号模糊匹配 | "ENG" |
| target_date_from | string | 否 | 目标交期开始 | "2024-08-01" |
| target_date_to | string | 否 | 目标交期结束 | "2024-09-30" |
| created_by | string | 否 | 创建人 | "user_001" |
| sort_by | string | 否 | 排序字段：created_at / target_date / priority | "created_at" |
| sort_order | string | 否 | 排序方向：asc / desc | "desc" |

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [
      {
        "job_id": "JOB-2024-0892",
        "part_number": "ENG-D250",
        "part_name": "2.5L 柴油发动机",
        "quantity_total": 100,
        "priority": "High",
        "target_date": "2024-08-30",
        "status": "DRAFT",
        "status_label": "草稿",
        "created_by": "user_001",
        "created_at": "2024-08-01T10:30:00+08:00",
        "bom_configured": false,
        "recipe_progress": "0/18",
        "recipe_progress_pct": 0
      },
      {
        "job_id": "JOB-2024-0891",
        "part_number": "PKG-L200",
        "part_name": "L200 包装机",
        "quantity_total": 5,
        "priority": "Normal",
        "target_date": "2024-09-15",
        "status": "SCHEDULED",
        "status_label": "已排程",
        "created_by": "user_002",
        "created_at": "2024-07-28T14:15:00+08:00",
        "bom_configured": true,
        "recipe_progress": "12/12",
        "recipe_progress_pct": 100,
        "scheduled_start": "2024-08-05T08:00:00+08:00",
        "scheduled_end": "2024-08-20T18:00:00+08:00"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 156,
      "total_pages": 8
    }
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801110000123458"
}
```

---

**J3. 获取 Job 详情**

- **接口：** `GET /jobs/{job_id}`
- **权限：** production_planner, production_manager, admin（需数据权限校验）
- **说明：** 获取单个 Job 的完整信息，包括基础信息、BOM 信息、Recipe 配置进度汇总。

**请求参数（Path）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| job_id | string | 是 | Job 唯一标识 | "JOB-2024-0892" |

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "part_number": "ENG-D250",
    "part_name": "2.5L 柴油发动机",
    "quantity_total": 100,
    "quantity_mts": 20,
    "quantity_mto": 80,
    "priority": "High",
    "priority_score": 95.5,
    "target_date": "2024-08-30",
    "status": "RECIPE_CFG",
    "status_label": "Recipe 配置中",
    "customer_order_no": "CO-2024-5678",
    "notes": "客户要求加急，优先安排",
    "created_by": "user_001",
    "created_by_name": "张三",
    "created_at": "2024-08-01T10:30:00+08:00",
    "updated_at": "2024-08-01T14:20:00+08:00",
    "bom_id": "BOM-ENG-D250-V1",
    "bom_version": "V1.0",
    "bom_part_name": "柴油发动机总成",
    "bom_total_nodes": 35,
    "bom_intermediate_nodes": 18,
    "bom_leaf_nodes": 17,
    "bom_max_depth": 5,
    "recipe_config": {
      "total_configurable": 18,
      "configured": 8,
      "pending": 10,
      "skipped": 0,
      "progress_pct": 44
    },
    "process_summary": {
      "process_count": 0,
      "status": "not_generated"
    },
    "schedule_summary": {
      "scheduled": false,
      "scheduled_start": null,
      "scheduled_end": null
    },
    "actual_timeline": {
      "actual_start": null,
      "actual_end": null
    }
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801113000123459"
}
```

---

**J4. 更新 Job**

- **接口：** `PUT /jobs/{job_id}`
- **权限：** production_planner, admin
- **说明：** 更新 Job 基础信息。仅允许在 `DRAFT` 状态下更新。

**请求参数（Path）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| job_id | string | 是 | Job 唯一标识 | "JOB-2024-0892" |

**请求参数（Request Body）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| quantity_total | int | 否 | 总生产数量 | 120 |
| quantity_mts | int | 否 | MTS 数量 | 40 |
| quantity_mto | int | 否 | MTO 数量 | 80 |
| priority | string | 否 | 优先级 | "Critical" |
| target_date | string | 否 | 目标交期 | "2024-09-05" |
| customer_order_no | string | 否 | 客户订单号 | "CO-2024-5679" |
| notes | string | 否 | 备注 | "数量变更，客户追加 20 台" |

**业务规则：**

- Job 状态必须为 `DRAFT`，否则返回 `40901`
- `quantity_total` 变更后，已配置的 Recipe 可能需要重新校验适用批量范围
- 如果 BOM 已选择，修改数量后需提示用户确认 Recipe 批量匹配

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "part_number": "ENG-D250",
    "quantity_total": 120,
    "quantity_mts": 40,
    "quantity_mto": 80,
    "priority": "Critical",
    "target_date": "2024-09-05",
    "status": "DRAFT",
    "updated_at": "2024-08-01T15:00:00+08:00",
    "quantity_changed": true,
    "recipe_revalidate_needed": true,
    "affected_recipe_count": 3
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801150000123460"
}
```

---

**J5. 删除 Job**

- **接口：** `DELETE /jobs/{job_id}`
- **权限：** production_manager, admin
- **说明：** 软删除 Job。仅允许删除 `DRAFT` 和 `CANCELLED` 状态的 Job。

**请求参数（Path）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| job_id | string | 是 | Job 唯一标识 | "JOB-2024-0892" |

**业务规则：**

- 仅 `DRAFT` 和 `CANCELLED` 状态可删除，否则返回 `40901`
- 软删除：设置 `deleted_at` 和 `deleted_by` 字段，不物理删除数据
- 已删除 Job 不可再被查询和操作

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "deleted": true,
    "deleted_by": "admin_001",
    "deleted_at": "2024-08-01T16:00:00+08:00"
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801160000123461"
}
```

---

**J6. 提交排程**

- **接口：** `POST /jobs/{job_id}/schedule`
- **权限：** production_planner, admin
- **说明：** 将 READY 状态的 Job 提交给排程引擎。

**请求参数（Path）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| job_id | string | 是 | Job 唯一标识 | "JOB-2024-0892" |

**请求参数（Request Body）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| strategy | string | 否 | 排程策略：asap / target_date_backward / finite_capacity | "target_date_backward" |
| target_date | string | 否 | 目标交期（覆盖 Job 的 target_date） | "2024-08-30" |
| priority_override | string | 否 | 临时覆盖优先级 | "Critical" |

**业务规则：**

- Job 状态必须为 `READY`（已生成 Process），否则返回 `40901`
- 如果排程引擎正在运行，返回 `40907`
- 排程是异步操作，接口立即返回 `ACCEPTED`，通过 WebSocket 推送排程完成事件

**成功响应：**

```json
{
  "code": 200,
  "message": "排程请求已接受，正在异步处理中",
  "data": {
    "job_id": "JOB-2024-0892",
    "schedule_request_id": "SCH-REQ-20240801-001",
    "status": "scheduling",
    "strategy": "target_date_backward",
    "estimated_seconds": 15,
    "poll_url": "/api/v1/jobs/JOB-2024-0892/schedule-result"
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801170000123462"
}
```

---

**J7. 取消排程**

- **接口：** `POST /jobs/{job_id}/unschedule`
- **权限：** production_planner, admin
- **说明：** 取消已排程的 Job，将状态从 `SCHEDULED` 回退到 `READY`。

**业务规则：**

- Job 状态必须为 `SCHEDULED`，否则返回 `40901`
- 取消排程后，已生成的 Process 保留，但排程时间被清空
- 如果 Job 已 `RELEASED`，不可取消排程，返回 `40908`

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "previous_status": "SCHEDULED",
    "current_status": "READY",
    "schedule_cleared": true,
    "processes_preserved": 15
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801180000123463"
}
```

---

**J8. 释放执行**

- **接口：** `POST /jobs/{job_id}/release`
- **权限：** production_manager, admin
- **说明：** 将已排程的 Job 释放到车间执行，状态从 `SCHEDULED` → `RELEASED`。

**请求参数（Request Body）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| release_type | string | 否 | 释放方式：all（全部）/ partial（部分 Process） | "all" |
| release_process_ids | array | 否 | 部分释放时指定 Process ID 列表 | ["P-CAST-01", "P-FORGE-01"] |
| released_by | string | 是 | 释放操作人 | "manager_001" |

**业务规则：**

- Job 状态必须为 `SCHEDULED`，否则返回 `40901`
- 释放后，各 Process 的状态从 `scheduled` → `released`
- 系统生成对应的派工单（Work Order）PDF

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "status": "RELEASED",
    "release_type": "all",
    "released_processes": 15,
    "released_by": "manager_001",
    "released_at": "2024-08-02T08:00:00+08:00",
    "work_orders_generated": 15
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240802080000123464"
}
```

---

**J9. 暂停 Job**

- **接口：** `POST /jobs/{job_id}/pause`
- **权限：** production_manager, admin
- **说明：** 暂停执行中的 Job。

**请求参数（Request Body）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| pause_reason | string | 是 | 暂停原因 | "物料缺货，等待采购" |
| paused_by | string | 是 | 暂停操作人 | "manager_001" |

**业务规则：**

- Job 状态必须为 `RELEASED` 或 `IN_PROGRESS`，否则返回 `40901`
- 暂停后，当前正在执行的 Process 允许完成当前 Task，但不再开始新 Task
- 系统记录暂停时间，影响后续排程的可用工时计算

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "previous_status": "IN_PROGRESS",
    "current_status": "ON_HOLD",
    "pause_reason": "物料缺货，等待采购",
    "paused_by": "manager_001",
    "paused_at": "2024-08-05T10:30:00+08:00",
    "active_processes_at_pause": 3
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240805103000123465"
}
```

---

**J10. 恢复 Job**

- **接口：** `POST /jobs/{job_id}/resume`
- **权限：** production_manager, admin
- **说明：** 恢复暂停的 Job。

**请求参数（Request Body）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| resume_reason | string | 否 | 恢复原因 | "物料已到货，可继续生产" |
| resumed_by | string | 是 | 恢复操作人 | "manager_001" |

**业务规则：**

- Job 状态必须为 `ON_HOLD`，否则返回 `40901`
- 恢复后，Job 状态回到 `IN_PROGRESS`
- 系统需重新评估排程（物料到货时间可能改变关键路径）

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "previous_status": "ON_HOLD",
    "current_status": "IN_PROGRESS",
    "resume_reason": "物料已到货，可继续生产",
    "resumed_by": "manager_001",
    "resumed_at": "2024-08-08T08:00:00+08:00",
    "total_hold_hours": 69.5
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240808080000123466"
}
```

---

#### 6.2.2 BOM 管理接口

| 序号 | 接口名称 | 方法 | 路径 | 说明 |
|------|---------|------|------|------|
| B1 | 获取 BOM 列表 | GET | `/boms` | 查询可用的 BOM 模板 |
| B2 | 获取 BOM 详情 | GET | `/boms/{bom_id}` | 获取 BOM 基础信息 |
| B3 | 展开 BOM 树 | GET | `/boms/{bom_id}/tree` | 获取完整的多层级 BOM 树 |
| B4 | 为 Job 选择 BOM | POST | `/jobs/{job_id}/bom` | 为 Job 选择并展开 BOM |

---

**B1. 获取 BOM 列表**

- **接口：** `GET /boms`
- **权限：** 所有已认证用户
- **说明：** 查询 BOM 模板列表，支持按产品型号、版本状态筛选。

**请求参数（Query）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| page | int | 否 | 页码 | 1 |
| page_size | int | 否 | 每页数量 | 20 |
| part_number | string | 否 | 产品型号筛选 | "ENG-D250" |
| version_status | string | 否 | 版本状态：Active / Obsolete / Draft | "Active" |
| keyword | string | 否 | BOM 编码或描述关键词 | "柴油发动机" |

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [
      {
        "bom_id": "BOM-ENG-D250-V1",
        "part_number": "ENG-D250",
        "part_name": "2.5L 柴油发动机",
        "version": "V1.0",
        "version_status": "Active",
        "description": "ENG-D250 柴油发动机总成 BOM",
        "total_nodes": 35,
        "max_depth": 5,
        "created_at": "2024-06-15T09:00:00+08:00"
      },
      {
        "bom_id": "BOM-ENG-D250-V2",
        "part_number": "ENG-D250",
        "part_name": "2.5L 柴油发动机",
        "version": "V2.0",
        "version_status": "Draft",
        "description": "ENG-D250 V2 改进版 BOM（测试中）",
        "total_nodes": 38,
        "max_depth": 5,
        "created_at": "2024-08-01T10:00:00+08:00"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 2,
      "total_pages": 1
    }
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801120000123467"
}
```

---

**B2. 获取 BOM 详情**

- **接口：** `GET /boms/{bom_id}`
- **权限：** 所有已认证用户

**请求参数（Path）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| bom_id | string | 是 | BOM 唯一标识 | "BOM-ENG-D250-V1" |

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "bom_id": "BOM-ENG-D250-V1",
    "part_number": "ENG-D250",
    "part_name": "2.5L 柴油发动机",
    "version": "V1.0",
    "version_status": "Active",
    "description": "ENG-D250 柴油发动机总成 BOM",
    "total_nodes": 35,
    "intermediate_nodes": 18,
    "leaf_nodes": 17,
    "max_depth": 5,
    "created_at": "2024-06-15T09:00:00+08:00",
    "updated_at": "2024-06-15T09:00:00+08:00",
    "created_by": "bom_admin",
    "stats": {
      "total_part_numbers": 32,
      "teams_involved": ["铸造车间", "锻造车间", "机加车间", "装配车间", "注塑车间", "精密铸造车间", "总装车间"],
      "estimated_recipe_config_time": "约 30 分钟"
    }
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801121000123468"
}
```

---

**B3. 展开 BOM 树**

- **接口：** `GET /boms/{bom_id}/tree`
- **权限：** 所有已认证用户
- **说明：** 获取 BOM 的完整多级树结构，用于 BOM 预览和 Recipe 配置界面。支持按展开深度控制。

**请求参数（Path + Query）：**

| 字段 | 位置 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|------|--------|
| bom_id | Path | string | 是 | BOM 唯一标识 | "BOM-ENG-D250-V1" |
| max_depth | Query | int | 否 | 最大展开深度，不传则全部展开 | 5 |
| include_leaf_details | Query | boolean | 否 | 是否包含叶子节点详细信息 | true |

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "bom_id": "BOM-ENG-D250-V1",
    "part_number": "ENG-D250",
    "part_name": "柴油发动机总成",
    "version": "V1.0",
    "total_nodes": 35,
    "intermediate_nodes": 18,
    "leaf_nodes": 17,
    "max_depth": 5,
    "tree": {
      "node_id": "BN-001",
      "part_number": "ENG-D250",
      "part_name": "柴油发动机总成",
      "level": 1,
      "node_type": "intermediate",
      "quantity_per_parent": 1,
      "unit": "台",
      "is_configurable": true,
      "default_recipe_id": "R-FINAL-01",
      "children_count": 4,
      "children": [
        {
          "node_id": "BN-002",
          "part_number": "BLK-001",
          "part_name": "缸体组件模块",
          "level": 2,
          "node_type": "intermediate",
          "quantity_per_parent": 1,
          "unit": "套",
          "is_configurable": true,
          "children": [
            {
              "node_id": "BN-003",
              "part_number": "BLK-MC-001",
              "part_name": "缸体机加工件",
              "level": 3,
              "node_type": "intermediate",
              "quantity_per_parent": 1,
              "unit": "件",
              "is_configurable": true,
              "children": [
                {
                  "node_id": "BN-004",
                  "part_number": "BLK-CAST-001",
                  "part_name": "缸体铸造毛坯",
                  "level": 4,
                  "node_type": "intermediate",
                  "quantity_per_parent": 1,
                  "unit": "件",
                  "is_configurable": true,
                  "children": [
                    {
                      "node_id": "BN-005",
                      "part_number": "AL-Si10Cu",
                      "part_name": "铝合金锭 AL-Si10Cu",
                      "level": 5,
                      "node_type": "leaf",
                      "quantity_per_parent": 12.5,
                      "unit": "kg",
                      "is_configurable": false
                    }
                  ]
                },
                {
                  "node_id": "BN-006",
                  "part_number": "CAP-001",
                  "part_name": "主轴承盖",
                  "level": 4,
                  "node_type": "intermediate",
                  "quantity_per_parent": 5,
                  "unit": "件",
                  "is_configurable": true,
                  "children": [
                    {
                      "node_id": "BN-007",
                      "part_number": "HT250",
                      "part_name": "灰铸铁毛坯 HT250",
                      "level": 5,
                      "node_type": "leaf",
                      "quantity_per_parent": 2.8,
                      "unit": "kg",
                      "is_configurable": false
                    }
                  ]
                }
              ]
            }
          ]
        }
      ]
    }
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801122000123469"
}
```

**响应字段说明（BOM 树节点）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| node_id | string | 节点唯一标识 |
| part_number | string | 物料编码 |
| part_name | string | 物料名称 |
| level | int | 层级（根节点=1） |
| node_type | string | intermediate（需配置 Recipe）/ leaf（采购件/原材料） |
| quantity_per_parent | decimal | 父节点所需本节点数量 |
| unit | string | 计量单位 |
| is_configurable | boolean | 是否需要配置 Recipe |
| default_recipe_id | string | 默认 Recipe（如有） |
| children | array | 子节点列表（叶子节点为空数组） |
| children_count | int | 直接子节点数量 |

---

**B4. 为 Job 选择 BOM**

- **接口：** `POST /jobs/{job_id}/bom`
- **权限：** production_planner, admin
- **说明：** 为 DRAFT 状态的 Job 选择 BOM，系统将 BOM 完整展开为 JobBOMNode 实例。

**请求参数（Path + Body）：**

| 字段 | 位置 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|------|--------|
| job_id | Path | string | 是 | Job 唯一标识 | "JOB-2024-0892" |
| bom_id | Body | string | 是 | 选择的 BOM ID | "BOM-ENG-D250-V1" |
| selected_by | Body | string | 是 | 选择人 | "user_001" |

**业务规则：**

- Job 状态必须为 `DRAFT`，否则返回 `40901`
- BOM 必须存在且 `version_status` 为 `Active`，否则返回 `40102`
- 选择 BOM 后，系统自动展开 BOM 树，创建 `JobBOMNode` 记录
- Job 状态变更为 `BOM_SELECTED`
- 一个 Job 只能选择一次 BOM，重复选择返回 `40100`

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "bom_id": "BOM-ENG-D250-V1",
    "bom_version": "V1.0",
    "status": "BOM_SELECTED",
    "nodes_created": 35,
    "intermediate_nodes": 18,
    "leaf_nodes": 17,
    "max_depth": 5,
    "config_order_sequence": [
      "BN-004", "BN-006", "BN-008", "BN-009", "BN-010",
      "BN-011", "BN-012", "BN-013", "BN-014", "BN-015",
      "BN-016", "BN-017", "BN-018", "BN-019", "BN-020",
      "BN-021", "BN-022", "BN-001"
    ],
    "next_step": "配置 Recipe，请从叶子节点向根节点倒序配置",
    "status_transition": "BOM_SELECTED -> RECIPE_CFG"
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801130000123470"
}
```

---

#### 6.2.3 Recipe 管理接口

| 序号 | 接口名称 | 方法 | 路径 | 说明 |
|------|---------|------|------|------|
| R1 | 查询节点可用 Recipe | GET | `/bom-nodes/{node_id}/recipes` | 根据 BOM 节点筛选匹配的 Recipe |
| R2 | 获取 Recipe 详情 | GET | `/recipes/{recipe_id}` | 包含完整的 tasks 列表 |
| R3 | 配置节点 Recipe | POST | `/jobs/{job_id}/nodes/{node_id}/recipe` | 为 Job 的某个 BOM 节点选择 Recipe |
| R4 | 批量配置 Recipe | POST | `/jobs/{job_id}/recipes/batch` | 批量配置多个节点的 Recipe |
| R5 | 获取 Recipe 配置状态 | GET | `/jobs/{job_id}/recipe-config-status` | 获取所有节点的 Recipe 配置进度 |
| R6 | 取消节点 Recipe | DELETE | `/jobs/{job_id}/nodes/{node_id}/recipe` | 取消已配置的 Recipe |

---

**R1. 查询节点可用 Recipe**

- **接口：** `GET /bom-nodes/{node_id}/recipes`
- **权限：** 所有已认证用户
- **说明：** 根据 BOM 节点的 Part Number 和 Job 的生产数量，筛选所有匹配的 Recipe。

**请求参数（Path + Query）：**

| 字段 | 位置 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|------|--------|
| node_id | Path | string | 是 | BOM 节点 ID | "BN-004" |
| job_id | Query | string | 是 | 关联的 Job ID（用于数量校验） | "JOB-2024-0892" |
| include_inactive | Query | boolean | 否 | 是否包含已禁用的 Recipe | false |

**业务规则：**

- 根据节点的 `part_number` 匹配 Recipe 的 `applicable_part_numbers`
- 校验 Job 的 `quantity_total` 是否在 Recipe 的 `applicable_quantity_min` ~ `applicable_quantity_max` 范围内
- 默认只返回 `status = Active` 的 Recipe

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "node_id": "BN-004",
    "part_number": "BLK-CAST-001",
    "part_name": "缸体铸造毛坯",
    "quantity": 100,
    "matched_recipe_count": 2,
    "recipes": [
      {
        "recipe_id": "RCP-CAST-001",
        "recipe_code": "R-CAST-01",
        "name": "低压铸造",
        "description": "适用于大批量铝合金铸件的低压铸造工艺",
        "default_team_id": "TEAM-CAST",
        "default_team_name": "铸造车间",
        "version": "V1.2",
        "status": "Active",
        "applicable_quantity_min": 50,
        "applicable_quantity_max": 999999,
        "quantity_match": true,
        "estimated_duration_minutes": 480,
        "setup_time_minutes": 60,
        "task_count": 6,
        "is_default": true,
        "is_recommended": true,
        "recommend_reason": "批量 100 满足低压铸造最小批量要求，质量稳定"
      },
      {
        "recipe_id": "RCP-CAST-002",
        "recipe_code": "R-CAST-02",
        "name": "重力铸造",
        "description": "适用于小批量的重力铸造工艺",
        "default_team_id": "TEAM-CAST",
        "default_team_name": "铸造车间",
        "version": "V1.0",
        "status": "Active",
        "applicable_quantity_min": 1,
        "applicable_quantity_max": 49,
        "quantity_match": false,
        "estimated_duration_minutes": 360,
        "setup_time_minutes": 30,
        "task_count": 5,
        "is_default": false,
        "is_recommended": false,
        "recommend_reason": "批量 100 超出最大适用批量 49，不推荐"
      }
    ]
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801140000123471"
}
```

---

**R2. 获取 Recipe 详情**

- **接口：** `GET /recipes/{recipe_id}`
- **权限：** 所有已认证用户

**请求参数（Path）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| recipe_id | string | 是 | Recipe 唯一标识 | "RCP-CAST-001" |

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "recipe_id": "RCP-CAST-001",
    "recipe_code": "R-CAST-01",
    "name": "低压铸造",
    "description": "适用于大批量铝合金铸件的低压铸造工艺",
    "applicable_part_numbers": ["BLK-CAST-001", "HD-CAST-001"],
    "applicable_quantity_min": 50,
    "applicable_quantity_max": 999999,
    "default_team_id": "TEAM-CAST",
    "default_team_name": "铸造车间",
    "version": "V1.2",
    "status": "Active",
    "estimated_duration_minutes": 480,
    "setup_time_minutes": 60,
    "created_at": "2024-01-15T09:00:00+08:00",
    "tasks": [
      {
        "task_id": "RT-CAST-001-01",
        "sequence_no": 1,
        "task_name": "模具准备",
        "task_type": "setup",
        "description": "模具预热、喷涂脱模剂、组装芯盒",
        "work_center": "低压铸造区-A线",
        "standard_time_minutes": 30,
        "required_skill": "铸造高级技工",
        "inspection_type": "self"
      },
      {
        "task_id": "RT-CAST-001-02",
        "sequence_no": 2,
        "task_name": "熔炼",
        "task_type": "machining",
        "description": "铝合金锭熔化、除气、成分调整",
        "work_center": "熔炼炉-2#",
        "standard_time_minutes": 120,
        "required_skill": "熔炼操作工",
        "inspection_type": "qc"
      },
      {
        "task_id": "RT-CAST-001-03",
        "sequence_no": 3,
        "task_name": "低压浇注",
        "task_type": "machining",
        "description": "控制压力 0.2-0.4MPa 进行浇注",
        "work_center": "低压铸造机-500T",
        "standard_time_minutes": 90,
        "required_skill": "铸造高级技工",
        "inspection_type": "self"
      },
      {
        "task_id": "RT-CAST-001-04",
        "sequence_no": 4,
        "task_name": "冷却固化",
        "task_type": "machining",
        "description": "自然冷却至可开模温度",
        "work_center": "低压铸造机-500T",
        "standard_time_minutes": 60,
        "required_skill": "铸造操作工",
        "inspection_type": "none"
      },
      {
        "task_id": "RT-CAST-001-05",
        "sequence_no": 5,
        "task_name": "脱模清理",
        "task_type": "machining",
        "description": "开模取出铸件、去除浇冒口",
        "work_center": "清理工位",
        "standard_time_minutes": 45,
        "required_skill": "清理工",
        "inspection_type": "self"
      },
      {
        "task_id": "RT-CAST-001-06",
        "sequence_no": 6,
        "task_name": "尺寸初检",
        "task_type": "inspection",
        "description": "关键尺寸抽检，合格率需 >= 95%",
        "work_center": "检验台",
        "standard_time_minutes": 30,
        "required_skill": "质检员",
        "inspection_type": "qc"
      }
    ]
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801141000123472"
}
```

---

**R3. 配置节点 Recipe**

- **接口：** `POST /jobs/{job_id}/nodes/{node_id}/recipe`
- **权限：** production_planner, admin
- **说明：** 为 Job 的某个 BOM 节点选择 Recipe。这是最核心的配置接口之一。

**请求参数（Path + Body）：**

| 字段 | 位置 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|------|--------|
| job_id | Path | string | 是 | Job 唯一标识 | "JOB-2024-0892" |
| node_id | Path | string | 是 | BOM 节点 ID（JobBOMNode 的 node_id） | "BN-004" |
| recipe_id | Body | string | 是 | 选中的 Recipe ID | "RCP-CAST-001" |
| selected_by | Body | string | 是 | 选择人 ID | "user_001" |
| notes | Body | string | 否 | 配置备注 | "选择低压铸造，批量 100 适用" |

**业务规则：**

- Job 状态必须为 `BOM_SELECTED` 或 `RECIPE_CFG`，否则返回 `40901`
- 节点必须是中间节点（`is_configurable = true`），否则返回 `40100`
- Recipe 必须存在且 Active，否则返回 `40403`
- Recipe 的适用 Part Number 必须与节点匹配，否则返回 `40100`
- Recipe 的适用数量范围必须包含 Job 的数量，否则返回 `40105`
- 配置成功后，系统通过 WebSocket 推送 `recipe.config_progress` 事件

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "job_node_id": "JBN-2024-0892-004",
    "node_id": "BN-004",
    "node_name": "缸体铸造毛坯",
    "recipe_id": "RCP-CAST-001",
    "recipe_code": "R-CAST-01",
    "recipe_name": "低压铸造",
    "team_id": "TEAM-CAST",
    "team_name": "铸造车间",
    "recipe_config_status": "configured",
    "selected_by": "user_001",
    "selected_at": "2024-08-01T15:30:00+08:00",
    "notes": "选择低压铸造，批量 100 适用",
    "overall_config_progress": {
      "total_configurable": 18,
      "configured": 9,
      "pending": 9,
      "skipped": 0,
      "progress_pct": 50
    },
    "next_recommended_node": {
      "node_id": "BN-006",
      "node_name": "主轴承盖",
      "reason": "同为第 4 层节点，继续按倒序配置"
    },
    "is_all_configured": false
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801153000123473"
}
```

**失败响应（Recipe 批量不匹配）：**

```json
{
  "code": 40105,
  "message": "Recipe 适用批量不匹配",
  "data": {
    "recipe_id": "RCP-CAST-002",
    "recipe_name": "重力铸造",
    "job_quantity": 100,
    "applicable_min": 1,
    "applicable_max": 49,
    "hint": "Job 数量 100 超出该 Recipe 最大适用批量 49"
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801153000123474"
}
```

---

**R4. 批量配置 Recipe**

- **接口：** `POST /jobs/{job_id}/recipes/batch`
- **权限：** production_planner, admin
- **说明：** 批量为多个节点配置 Recipe，用于导入或快速配置场景。

**请求参数（Path + Body）：**

| 字段 | 位置 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|------|--------|
| job_id | Path | string | 是 | Job 唯一标识 | "JOB-2024-0892" |
| configurations | Body | array | 是 | 配置列表（最多 50 条） | 见下 |

**configurations 数组元素：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| node_id | string | 是 | 节点 ID | "BN-004" |
| recipe_id | string | 是 | Recipe ID | "RCP-CAST-001" |
| notes | string | 否 | 备注 | "" |

**请求示例：**

```json
{
  "configurations": [
    {
      "node_id": "BN-004",
      "recipe_id": "RCP-CAST-001",
      "notes": "缸体铸造毛坯 - 低压铸造"
    },
    {
      "node_id": "BN-006",
      "recipe_id": "RCP-CAST-003",
      "notes": "主轴承盖 - 砂型铸造"
    },
    {
      "node_id": "BN-008",
      "recipe_id": "RCP-FORGE-001",
      "notes": "活塞 - 热锻+精车"
    }
  ]
}
```

**业务规则：**

- 批量操作的事务性：全部成功或全部失败（原子性）
- 单批次最多 50 条配置
- 每条配置遵循与单条配置相同的校验规则

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "total_submitted": 3,
    "success_count": 3,
    "fail_count": 0,
    "results": [
      {
        "node_id": "BN-004",
        "recipe_id": "RCP-CAST-001",
        "status": "success",
        "recipe_config_status": "configured"
      },
      {
        "node_id": "BN-006",
        "recipe_id": "RCP-CAST-003",
        "status": "success",
        "recipe_config_status": "configured"
      },
      {
        "node_id": "BN-008",
        "recipe_id": "RCP-FORGE-001",
        "status": "success",
        "recipe_config_status": "configured"
      }
    ],
    "overall_config_progress": {
      "total_configurable": 18,
      "configured": 11,
      "pending": 7,
      "skipped": 0,
      "progress_pct": 61
    }
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801154000123475"
}
```

---

**R5. 获取 Recipe 配置状态**

- **接口：** `GET /jobs/{job_id}/recipe-config-status`
- **权限：** 所有已认证用户（需数据权限校验）

**请求参数（Path + Query）：**

| 字段 | 位置 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|------|--------|
| job_id | Path | string | 是 | Job 唯一标识 | "JOB-2024-0892" |
| level | Query | int | 否 | 按层级筛选 | 4 |
| status | Query | string | 否 | 按配置状态筛选：pending / configured / skipped | "pending" |

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "overall": {
      "total_configurable": 18,
      "configured": 8,
      "pending": 10,
      "skipped": 0,
      "progress_pct": 44
    },
    "by_level": {
      "5": { "total": 0, "configured": 0, "pending": 0 },
      "4": { "total": 13, "configured": 8, "pending": 5 },
      "3": { "total": 5, "configured": 0, "pending": 5 },
      "2": { "total": 4, "configured": 0, "pending": 4 },
      "1": { "total": 1, "configured": 0, "pending": 1 }
    },
    "nodes": [
      {
        "job_node_id": "JBN-2024-0892-004",
        "node_id": "BN-004",
        "part_number": "BLK-CAST-001",
        "part_name": "缸体铸造毛坯",
        "level": 4,
        "recipe_config_status": "configured",
        "recipe_id": "RCP-CAST-001",
        "recipe_name": "低压铸造",
        "team_name": "铸造车间",
        "selected_by": "user_001",
        "selected_at": "2024-08-01T15:30:00+08:00"
      },
      {
        "job_node_id": "JBN-2024-0892-006",
        "node_id": "BN-006",
        "part_number": "CAP-001",
        "part_name": "主轴承盖",
        "level": 4,
        "recipe_config_status": "pending",
        "recipe_id": null,
        "recipe_name": null,
        "team_name": null,
        "selected_by": null,
        "selected_at": null
      }
    ]
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801155000123476"
}
```

---

**R6. 取消节点 Recipe**

- **接口：** `DELETE /jobs/{job_id}/nodes/{node_id}/recipe`
- **权限：** production_planner, admin
- **说明：** 取消已配置的 Recipe，将节点恢复为 `pending` 状态。

**业务规则：**

- 节点当前必须为 `configured` 状态，否则返回 `40900`
- 取消配置后，如果该节点已参与 Process 生成，需要级联删除已生成的 Process（如果 Job 已 READY）
- 如果 Job 已 `SCHEDULED` 或更后状态，不允许取消 Recipe，返回 `40901`

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "node_id": "BN-004",
    "previous_recipe_id": "RCP-CAST-001",
    "recipe_config_status": "pending",
    "overall_config_progress": {
      "total_configurable": 18,
      "configured": 7,
      "pending": 11,
      "skipped": 0,
      "progress_pct": 39
    },
    "cascade_deleted": {
      "processes_deleted": 0,
      "reason": "Job 尚未生成 Process"
    }
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801160000123477"
}
```

---

#### 6.2.4 Process 管理接口

| 序号 | 接口名称 | 方法 | 路径 | 说明 |
|------|---------|------|------|------|
| P1 | 生成 Process | POST | `/jobs/{job_id}/processes/generate` | 系统根据已配置的 Recipe 自动生成 Process |
| P2 | 获取 Process 列表 | GET | `/jobs/{job_id}/processes` | 获取 Job 的所有 Process |
| P3 | 获取 Process 详情 | GET | `/processes/{process_id}` | 包含 tasks、依赖关系 |
| P4 | 更新 Process 顺序 | PUT | `/jobs/{job_id}/processes/reorder` | 手动调整 Process 执行顺序 |
| P5 | 获取 Process 依赖图 | GET | `/jobs/{job_id}/processes/dependency-graph` | 获取 DAG 结构 |

---

**P1. 生成 Process**

- **接口：** `POST /jobs/{job_id}/processes/generate`
- **权限：** production_planner, admin
- **说明：** 触发 Process 生成算法。系统解析已配置的 BOM 树，按 team group 规则自动生成 Process、ProcessTask 和 ProcessDependency。这是"展开 → 聚合 → 排程"三段式中"聚合"阶段的核心入口。

**请求参数（Path + Body）：**

| 字段 | 位置 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|------|--------|
| job_id | Path | string | 是 | Job 唯一标识 | "JOB-2024-0892" |
| generated_by | Body | string | 是 | 触发人 | "user_001" |

**业务规则：**

- Job 状态必须为 `RECIPE_CFG` 且所有中间节点已配置 Recipe，否则返回 `40902`
- 如果 Job 已生成过 Process（`process_summary.process_count > 0`），返回 `40903`
- Process 生成后自动进行 DAG 校验，如发现循环依赖返回 `40906`
- 生成成功后，Job 状态自动变更为 `READY`
- 生成过程为同步操作（一般 1~3 秒内完成），结果直接在响应中返回

**成功响应：**

```json
{
  "code": 200,
  "message": "Process 生成成功",
  "data": {
    "job_id": "JOB-2024-0892",
    "status": "READY",
    "process_count": 15,
    "generation_time_ms": 1250,
    "processes": [
      {
        "process_id": "PROC-2024-0892-01",
        "process_code": "P-CAST-01",
        "process_name": "缸体与缸盖铸造",
        "process_type": "internal",
        "team_id": "TEAM-CAST",
        "team_name": "铸造车间",
        "sequence_no": 1,
        "nodes": ["缸体铸造毛坯", "主轴承盖", "缸盖铸造毛坯"],
        "node_count": 3,
        "estimated_hours": 18.5,
        "status": "pending",
        "predecessors": [],
        "successors": ["P-MC-01", "P-MC-03"]
      },
      {
        "process_id": "PROC-2024-0892-02",
        "process_code": "P-CAST-02",
        "process_name": "曲轴与凸轮轴铸造",
        "process_type": "internal",
        "team_id": "TEAM-CAST",
        "team_name": "铸造车间",
        "sequence_no": 2,
        "nodes": ["曲轴毛坯", "凸轮轴毛坯"],
        "node_count": 2,
        "estimated_hours": 14.0,
        "status": "pending",
        "predecessors": [],
        "successors": ["P-MC-02", "P-MC-04"]
      },
      {
        "process_id": "PROC-2024-0892-03",
        "process_code": "P-CAST-03",
        "process_name": "排气歧管精密铸造",
        "process_type": "internal",
        "team_id": "TEAM-PRECISION-CAST",
        "team_name": "精密铸造车间",
        "sequence_no": 3,
        "nodes": ["歧管铸钢件"],
        "node_count": 1,
        "estimated_hours": 16.0,
        "status": "pending",
        "predecessors": [],
        "successors": ["P-ASSY-EX"]
      },
      {
        "process_id": "PROC-2024-0892-04",
        "process_code": "P-FORGE-01",
        "process_name": "活塞与连杆锻造",
        "process_type": "internal",
        "team_id": "TEAM-FORGE",
        "team_name": "锻造车间",
        "sequence_no": 4,
        "nodes": ["活塞", "连杆体"],
        "node_count": 2,
        "estimated_hours": 12.0,
        "status": "pending",
        "predecessors": [],
        "successors": ["P-MC-05", "P-ASSY-01", "P-ASSY-02"]
      },
      {
        "process_id": "PROC-2024-0892-05",
        "process_code": "P-FORGE-02",
        "process_name": "气门锻造",
        "process_type": "internal",
        "team_id": "TEAM-FORGE",
        "team_name": "锻造车间",
        "sequence_no": 5,
        "nodes": ["进气门", "排气门"],
        "node_count": 2,
        "estimated_hours": 10.0,
        "status": "pending",
        "predecessors": [],
        "successors": ["P-ASSY-03"]
      },
      {
        "process_id": "PROC-2024-0892-06",
        "process_code": "P-MC-01",
        "process_name": "缸体机加工",
        "process_type": "internal",
        "team_id": "TEAM-MC",
        "team_name": "机加车间",
        "sequence_no": 6,
        "nodes": ["缸体机加工件", "活塞销"],
        "node_count": 2,
        "estimated_hours": 14.0,
        "status": "pending",
        "predecessors": ["P-CAST-01"],
        "successors": ["P-ASSY-04"]
      },
      {
        "process_id": "PROC-2024-0892-07",
        "process_code": "P-MC-02",
        "process_name": "曲轴与飞轮机加工",
        "process_type": "internal",
        "team_id": "TEAM-MC",
        "team_name": "机加车间",
        "sequence_no": 7,
        "nodes": ["曲轴", "飞轮"],
        "node_count": 2,
        "estimated_hours": 16.0,
        "status": "pending",
        "predecessors": ["P-CAST-02"],
        "successors": ["P-ASSY-05"]
      },
      {
        "process_id": "PROC-2024-0892-08",
        "process_code": "P-MC-03",
        "process_name": "缸盖与凸轮轴机加工",
        "process_type": "internal",
        "team_id": "TEAM-MC",
        "team_name": "机加车间",
        "sequence_no": 8,
        "nodes": ["缸盖机加工件", "凸轮轴"],
        "node_count": 2,
        "estimated_hours": 15.0,
        "status": "pending",
        "predecessors": ["P-CAST-01", "P-CAST-02"],
        "successors": ["P-ASSY-06"]
      },
      {
        "process_id": "PROC-2024-0892-09",
        "process_code": "P-INJ-01",
        "process_name": "进气歧管注塑",
        "process_type": "internal",
        "team_id": "TEAM-INJ",
        "team_name": "注塑车间",
        "sequence_no": 9,
        "nodes": ["歧管注塑件"],
        "node_count": 1,
        "estimated_hours": 8.0,
        "status": "pending",
        "predecessors": [],
        "successors": ["P-ASSY-EX"]
      },
      {
        "process_id": "PROC-2024-0892-10",
        "process_code": "P-ASSY-01",
        "process_name": "活塞与连杆组件装配",
        "process_type": "internal",
        "team_id": "TEAM-ASSY",
        "team_name": "装配车间",
        "sequence_no": 10,
        "nodes": ["活塞组", "连杆组"],
        "node_count": 2,
        "estimated_hours": 10.0,
        "status": "pending",
        "predecessors": ["P-FORGE-01", "P-MC-01"],
        "successors": ["P-ASSY-04"]
      },
      {
        "process_id": "PROC-2024-0892-11",
        "process_code": "P-ASSY-02",
        "process_name": "气门组与缸盖组件装配",
        "process_type": "internal",
        "team_id": "TEAM-ASSY",
        "team_name": "装配车间",
        "sequence_no": 11,
        "nodes": ["气门组", "缸盖组件模块"],
        "node_count": 2,
        "estimated_hours": 12.0,
        "status": "pending",
        "predecessors": ["P-FORGE-02", "P-MC-03"],
        "successors": ["P-FINAL"]
      },
      {
        "process_id": "PROC-2024-0892-12",
        "process_code": "P-ASSY-03",
        "process_name": "曲轴组件装配",
        "process_type": "internal",
        "team_id": "TEAM-ASSY",
        "team_name": "装配车间",
        "sequence_no": 12,
        "nodes": ["曲轴组件模块"],
        "node_count": 1,
        "estimated_hours": 8.0,
        "status": "pending",
        "predecessors": ["P-MC-02"],
        "successors": ["P-FINAL"]
      },
      {
        "process_id": "PROC-2024-0892-13",
        "process_code": "P-ASSY-04",
        "process_name": "进排气系统装配",
        "process_type": "internal",
        "team_id": "TEAM-ASSY",
        "team_name": "装配车间",
        "sequence_no": 13,
        "nodes": ["进排气系统模块"],
        "node_count": 1,
        "estimated_hours": 6.0,
        "status": "pending",
        "predecessors": ["P-INJ-01", "P-CAST-03"],
        "successors": ["P-FINAL"]
      },
      {
        "process_id": "PROC-2024-0892-14",
        "process_code": "P-ASSY-05",
        "process_name": "缸体组件装配",
        "process_type": "internal",
        "team_id": "TEAM-ASSY",
        "team_name": "装配车间",
        "sequence_no": 14,
        "nodes": ["缸体组件模块"],
        "node_count": 1,
        "estimated_hours": 8.0,
        "status": "pending",
        "predecessors": ["P-ASSY-01"],
        "successors": ["P-FINAL"]
      },
      {
        "process_id": "PROC-2024-0892-15",
        "process_code": "P-FINAL",
        "process_name": "发动机总装与调试",
        "process_type": "internal",
        "team_id": "TEAM-FINAL-ASSY",
        "team_name": "总装车间",
        "sequence_no": 15,
        "nodes": ["发动机总成"],
        "node_count": 1,
        "estimated_hours": 40.0,
        "status": "pending",
        "predecessors": ["P-ASSY-02", "P-ASSY-03", "P-ASSY-04", "P-ASSY-05"],
        "successors": []
      }
    ],
    "dag_validated": true,
    "critical_path": ["P-CAST-01", "P-MC-01", "P-ASSY-01", "P-ASSY-04", "P-FINAL"],
    "estimated_total_hours": 176.5,
    "teams_involved": ["铸造车间", "精密铸造车间", "锻造车间", "机加车间", "注塑车间", "装配车间", "总装车间"]
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801170000123478"
}
```

**失败响应（DAG 存在环）：**

```json
{
  "code": 40906,
  "message": "Process 依赖图存在循环依赖",
  "data": {
    "cycle_path": ["P-MC-01", "P-ASSY-01", "P-ASSY-04", "P-MC-01"],
    "hint": "请检查以下节点的 Recipe 配置是否存在逻辑错误",
    "affected_nodes": ["缸体机加工件", "活塞组", "缸体组件模块"],
    "suggestion": "建议取消 P-MC-01 相关节点的 Recipe 重新配置"
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801170000123479"
}
```

---

**P2. 获取 Process 列表**

- **接口：** `GET /jobs/{job_id}/processes`
- **权限：** 所有已认证用户

**请求参数（Path + Query）：**

| 字段 | 位置 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|------|--------|
| job_id | Path | string | 是 | Job 唯一标识 | "JOB-2024-0892" |
| team_id | Query | string | 否 | 按团队筛选 | "TEAM-CAST" |
| status | Query | string | 否 | 按状态筛选 | "pending" |

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "process_count": 15,
    "processes": [
      {
        "process_id": "PROC-2024-0892-01",
        "process_code": "P-CAST-01",
        "process_name": "缸体与缸盖铸造",
        "team_id": "TEAM-CAST",
        "team_name": "铸造车间",
        "sequence_no": 1,
        "estimated_hours": 18.5,
        "status": "pending",
        "scheduled_start": null,
        "scheduled_end": null,
        "predecessor_count": 0,
        "successor_count": 2
      }
    ]
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801180000123480"
}
```

---

**P3. 获取 Process 详情**

- **接口：** `GET /processes/{process_id}`
- **权限：** 所有已认证用户

**请求参数（Path）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| process_id | string | 是 | Process 唯一标识 | "PROC-2024-0892-01" |

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "process_id": "PROC-2024-0892-01",
    "process_code": "P-CAST-01",
    "process_name": "缸体与缸盖铸造",
    "job_id": "JOB-2024-0892",
    "process_type": "internal",
    "team_id": "TEAM-CAST",
    "team_name": "铸造车间",
    "sequence_no": 1,
    "status": "pending",
    "priority_score": 95.5,
    "estimated_hours": 18.5,
    "scheduled_start": null,
    "scheduled_end": null,
    "actual_start": null,
    "actual_end": null,
    "notes": "",
    "created_at": "2024-08-01T17:00:00+08:00",
    "nodes": [
      {
        "job_node_id": "JBN-2024-0892-004",
        "part_number": "BLK-CAST-001",
        "part_name": "缸体铸造毛坯",
        "recipe_id": "RCP-CAST-001",
        "recipe_name": "低压铸造"
      },
      {
        "job_node_id": "JBN-2024-0892-006",
        "part_number": "CAP-001",
        "part_name": "主轴承盖",
        "recipe_id": "RCP-CAST-003",
        "recipe_name": "砂型铸造"
      }
    ],
    "tasks": [
      {
        "process_task_id": "PT-2024-0892-0001",
        "sequence_no": 1,
        "task_name": "模具准备",
        "task_type": "setup",
        "planned_start": null,
        "planned_end": null,
        "status": "pending"
      }
    ],
    "predecessors": [],
    "successors": [
      {
        "process_id": "PROC-2024-0892-06",
        "process_code": "P-MC-01",
        "dependency_type": "finish_to_start",
        "lead_lag_minutes": 0
      }
    ]
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801181000123481"
}
```

---

**P4. 更新 Process 顺序**

- **接口：** `PUT /jobs/{job_id}/processes/reorder`
- **权限：** production_manager, admin
- **说明：** 手动调整 Process 的执行顺序。仅允许在 `READY` 状态调整。

**请求参数（Path + Body）：**

| 字段 | 位置 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|------|--------|
| job_id | Path | string | 是 | Job 唯一标识 | "JOB-2024-0892" |
| process_orders | Body | array | 是 | 新的 Process 顺序列表 | 见下 |

**process_orders 元素：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| process_id | string | 是 | Process ID | "PROC-2024-0892-01" |
| sequence_no | int | 是 | 新的顺序号 | 1 |

**业务规则：**

- Job 状态必须为 `READY`，否则返回 `40901`
- 调整顺序不得违反依赖关系约束（即前置 Process 的 sequence_no 必须小于后置）
- 调整后需重新进行 DAG 校验

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "reordered_processes": 15,
    "dag_validated": true,
    "updated_sequence": [
      {"process_id": "PROC-2024-0892-01", "sequence_no": 1},
      {"process_id": "PROC-2024-0892-02", "sequence_no": 2}
    ]
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801190000123482"
}
```

---

**P5. 获取 Process 依赖图**

- **接口：** `GET /jobs/{job_id}/processes/dependency-graph`
- **权限：** 所有已认证用户

**请求参数（Path）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| job_id | string | 是 | Job 唯一标识 | "JOB-2024-0892" |

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "process_count": 15,
    "dependency_count": 18,
    "nodes": [
      {
        "process_id": "PROC-2024-0892-01",
        "process_code": "P-CAST-01",
        "process_name": "缸体与缸盖铸造",
        "team_name": "铸造车间",
        "estimated_hours": 18.5,
        "status": "pending",
        "depth_level": 1
      },
      {
        "process_id": "PROC-2024-0892-15",
        "process_code": "P-FINAL",
        "process_name": "发动机总装与调试",
        "team_name": "总装车间",
        "estimated_hours": 40.0,
        "status": "pending",
        "depth_level": 5
      }
    ],
    "edges": [
      {
        "from": "PROC-2024-0892-01",
        "to": "PROC-2024-0892-06",
        "dependency_type": "finish_to_start",
        "lead_lag_minutes": 0,
        "is_critical_path": true
      }
    ],
    "critical_path": ["P-CAST-01", "P-MC-01", "P-ASSY-01", "P-ASSY-04", "P-FINAL"],
    "critical_path_hours": 176.5,
    "is_dag": true
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801192000123483"
}
```

---

#### 6.2.5 排程接口

| 序号 | 接口名称 | 方法 | 路径 | 说明 |
|------|---------|------|------|------|
| S1 | 触发排程 | POST | `/scheduling/run` | 触发排程引擎（全局/指定 Job） |
| S2 | 获取排程结果 | GET | `/jobs/{job_id}/schedule-result` | 获取排程结果 |
| S3 | 获取排程甘特图 | GET | `/jobs/{job_id}/gantt` | 获取甘特图数据 |
| S4 | 重新排程 | POST | `/jobs/{job_id}/reschedule` | 重新排程 |

---

**S1. 触发排程**

- **接口：** `POST /scheduling/run`
- **权限：** system, production_manager, admin
- **说明：** 触发排程引擎。支持全局排程（所有 READY Job）或指定 Job 排程。

**请求参数（Request Body）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| scope | string | 是 | 排程范围：all（全局）/ specific（指定 Job） | "specific" |
| job_ids | array | 条件必填 | scope=specific 时提供 | ["JOB-2024-0892"] |
| strategy | string | 否 | 排程策略：asap / target_date_backward / finite_capacity | "target_date_backward" |
| look_ahead_days | int | 否 | 排程前瞻天数 | 90 |

**业务规则：**

- 全局排程需要 system 或 production_manager 角色
- 排程是异步操作，接口返回 `schedule_request_id` 用于轮询
- 排程引擎运行期间，相关 Job 被加锁，防止并发排程

**成功响应：**

```json
{
  "code": 200,
  "message": "排程任务已提交",
  "data": {
    "schedule_request_id": "SCH-REQ-202408020800-001",
    "scope": "specific",
    "job_count": 1,
    "strategy": "target_date_backward",
    "status": "running",
    "submitted_at": "2024-08-02T08:00:00+08:00",
    "estimated_seconds": 15,
    "poll_url": "/api/v1/scheduling/status/SCH-REQ-202408020800-001"
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240802080000123484"
}
```

---

**S2. 获取排程结果**

- **接口：** `GET /jobs/{job_id}/schedule-result`
- **权限：** 所有已认证用户

**请求参数（Path）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| job_id | string | 是 | Job 唯一标识 | "JOB-2024-0892" |

**业务规则：**

- Job 状态必须为 `SCHEDULED` 或 `RELEASED` 或 `IN_PROGRESS`，否则返回 `40904`

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "schedule_status": "completed",
    "strategy": "target_date_backward",
    "target_date": "2024-08-30",
    "scheduled_at": "2024-08-02T08:00:15+08:00",
    "process_results": [
      {
        "process_id": "PROC-2024-0892-01",
        "process_code": "P-CAST-01",
        "process_name": "缸体与缸盖铸造",
        "team_id": "TEAM-CAST",
        "sequence_no": 1,
        "scheduled_start": "2024-08-05T08:00:00+08:00",
        "scheduled_end": "2024-08-09T18:30:00+08:00",
        "estimated_hours": 18.5,
        "status": "scheduled",
        "is_on_critical_path": true
      },
      {
        "process_id": "PROC-2024-0892-06",
        "process_code": "P-MC-01",
        "process_name": "缸体机加工",
        "team_id": "TEAM-MC",
        "sequence_no": 6,
        "scheduled_start": "2024-08-12T08:00:00+08:00",
        "scheduled_end": "2024-08-16T18:00:00+08:00",
        "estimated_hours": 14.0,
        "status": "scheduled",
        "is_on_critical_path": true
      }
    ],
    "summary": {
      "total_processes": 15,
      "scheduled_processes": 15,
      "critical_path_hours": 176.5,
      "scheduled_start": "2024-08-05T08:00:00+08:00",
      "scheduled_end": "2024-08-29T17:00:00+08:00",
      "target_date_met": true,
      "days_before_target": 1
    }
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240802090000123485"
}
```

---

**S3. 获取排程甘特图**

- **接口：** `GET /jobs/{job_id}/gantt`
- **权限：** 所有已认证用户

**请求参数（Path + Query）：**

| 字段 | 位置 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|------|--------|
| job_id | Path | string | 是 | Job 唯一标识 | "JOB-2024-0892" |
| view_start | Query | string | 否 | 视图开始日期 | "2024-08-01" |
| view_end | Query | string | 否 | 视图结束日期 | "2024-09-10" |

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "job_id": "JOB-2024-0892",
    "job_name": "ENG-D250 x100",
    "view_range": {
      "start": "2024-08-01T00:00:00+08:00",
      "end": "2024-09-10T00:00:00+08:00"
    },
    "teams": [
      {
        "team_id": "TEAM-CAST",
        "team_name": "铸造车间",
        "lanes": [
          {
            "lane_id": "TEAM-CAST-1",
            "lane_name": "铸造一线",
            "items": [
              {
                "process_id": "PROC-2024-0892-01",
                "process_code": "P-CAST-01",
                "process_name": "缸体与缸盖铸造",
                "start": "2024-08-05T08:00:00+08:00",
                "end": "2024-08-09T18:30:00+08:00",
                "progress_pct": 0,
                "is_critical_path": true,
                "color": "#FF6B6B"
              },
              {
                "process_id": "PROC-2024-0892-02",
                "process_code": "P-CAST-02",
                "process_name": "曲轴与凸轮轴铸造",
                "start": "2024-08-05T08:00:00+08:00",
                "end": "2024-08-08T16:00:00+08:00",
                "progress_pct": 0,
                "is_critical_path": false,
                "color": "#4ECDC4"
              }
            ]
          }
        ]
      }
    ],
    "milestones": [
      {
        "date": "2024-08-30T00:00:00+08:00",
        "label": "目标交期",
        "type": "target_date"
      },
      {
        "date": "2024-08-29T17:00:00+08:00",
        "label": "计划完成",
        "type": "planned_end"
      }
    ],
    "dependencies": [
      {
        "from": "PROC-2024-0892-01",
        "to": "PROC-2024-0892-06",
        "type": "finish_to_start"
      }
    ]
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240802100000123486"
}
```

---

**S4. 重新排程**

- **接口：** `POST /jobs/{job_id}/reschedule`
- **权限：** production_manager, admin
- **说明：** 取消当前排程并重新触发排程。用于 Recipe 修改、产能变化等场景。

**业务规则：**

- Job 状态必须为 `SCHEDULED` 或 `RELEASED`，否则返回 `40901`
- 如果 Job 已 `IN_PROGRESS`，不允许重新排程未完成的 Process，返回 `40908`
- 重新排程保留已完成 Process 的实际时间，只重排未完成的

**成功响应：**

```json
{
  "code": 200,
  "message": "重新排程请求已提交",
  "data": {
    "job_id": "JOB-2024-0892",
    "schedule_request_id": "SCH-REQ-202408021100-002",
    "previous_schedule_cleared": true,
    "status": "rescheduling",
    "poll_url": "/api/v1/scheduling/status/SCH-REQ-202408021100-002"
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240802110000123487"
}
```

---

#### 6.2.6 Signal 接口

| 序号 | 接口名称 | 方法 | 路径 | 说明 |
|------|---------|------|------|------|
| SG1 | 发送 Signal | POST | `/signals` | 发送信号触发 Process |
| SG2 | 获取 Signal 列表 | GET | `/signals` | 查询信号记录 |
| SG3 | 确认 Signal | POST | `/signals/{signal_id}/ack` | 确认信号已处理 |

---

**SG1. 发送 Signal**

- **接口：** `POST /signals`
- **权限：** system, production_operator, admin
- **说明：** 发送外部信号（如物料到货、质量检验通过、设备就绪等），排程引擎消费后触发相应 Process 的状态变更或排程调整。

**请求参数（Request Body）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| signal_type | string | 是 | 信号类型：material_received / quality_passed / equipment_ready / manual_trigger | "material_received" |
| job_id | string | 条件必填 | 关联的 Job ID | "JOB-2024-0892" |
| process_id | string | 否 | 关联的 Process ID | "PROC-2024-0892-01" |
| ref_document | string | 否 | 关联单据号 | "GR-2024-0892-001" |
| ref_document_type | string | 否 | 单据类型：goods_receipt / inspection_report / equipment_log | "goods_receipt" |
| triggered_by | string | 是 | 触发人/系统 | "system_wms" |
| triggered_at | string | 否 | 触发时间（ISO 8601），默认当前时间 | "2024-08-05T09:00:00+08:00" |
| metadata | object | 否 | 扩展元数据 | {"warehouse_location": "A-03-05", "batch_no": "B2024080501"} |

**业务规则：**

- `signal_type` 必须在系统定义的枚举范围内，否则返回 `40006`
- `job_id` 必须存在，否则返回 `40401`
- 系统对 Signal 进行幂等性处理（同一 `ref_document` 重复发送将被去重）
- Signal 发送后，排程引擎异步消费，通过 WebSocket 推送 `signal.received` 事件

**请求示例：**

```json
{
  "signal_type": "material_received",
  "job_id": "JOB-2024-0892",
  "process_id": "PROC-2024-0892-01",
  "ref_document": "GR-2024-0892-001",
  "ref_document_type": "goods_receipt",
  "triggered_by": "system_wms",
  "triggered_at": "2024-08-05T09:00:00+08:00",
  "metadata": {
    "warehouse_location": "A-03-05",
    "batch_no": "B2024080501",
    "received_quantity": 1250
  }
}
```

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "signal_id": "SIG-202408050900-001",
    "signal_type": "material_received",
    "signal_type_label": "物料到货",
    "job_id": "JOB-2024-0892",
    "process_id": "PROC-2024-0892-01",
    "status": "received",
    "ref_document": "GR-2024-0892-001",
    "triggered_by": "system_wms",
    "triggered_at": "2024-08-05T09:00:00+08:00",
    "received_at": "2024-08-05T09:00:02+08:00",
    "processed": false,
    "processing_result": null,
    "metadata": {
      "warehouse_location": "A-03-05",
      "batch_no": "B2024080501",
      "received_quantity": 1250
    }
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240805090000123488"
}
```

---

**SG2. 获取 Signal 列表**

- **接口：** `GET /signals`
- **权限：** production_planner, production_manager, admin

**请求参数（Query）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| page | int | 否 | 页码 | 1 |
| page_size | int | 否 | 每页数量 | 20 |
| job_id | string | 否 | 按 Job 筛选 | "JOB-2024-0892" |
| signal_type | string | 否 | 按类型筛选 | "material_received" |
| processed | boolean | 否 | 按处理状态筛选 | false |
| triggered_by | string | 否 | 按触发人筛选 | "system_wms" |
| triggered_at_from | string | 否 | 触发时间起 | "2024-08-01T00:00:00+08:00" |
| triggered_at_to | string | 否 | 触发时间止 | "2024-08-31T23:59:59+08:00" |

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [
      {
        "signal_id": "SIG-202408050900-001",
        "signal_type": "material_received",
        "signal_type_label": "物料到货",
        "job_id": "JOB-2024-0892",
        "process_id": "PROC-2024-0892-01",
        "ref_document": "GR-2024-0892-001",
        "processed": true,
        "processing_result": "Process PROC-2024-0892-01 status updated to ready",
        "triggered_by": "system_wms",
        "triggered_at": "2024-08-05T09:00:00+08:00",
        "processed_at": "2024-08-05T09:00:05+08:00"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 45,
      "total_pages": 3
    }
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240805100000123489"
}
```

---

**SG3. 确认 Signal**

- **接口：** `POST /signals/{signal_id}/ack`
- **权限：** production_operator, production_manager, admin
- **说明：** 人工确认信号已处理，用于排程引擎消费失败时的手动干预。

**请求参数（Path + Body）：**

| 字段 | 位置 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|------|--------|
| signal_id | Path | string | 是 | Signal 唯一标识 | "SIG-202408050900-001" |
| ack_by | Body | string | 是 | 确认人 | "operator_001" |
| ack_notes | Body | string | 否 | 确认备注 | "已人工核对物料到货，可开始生产" |

**业务规则：**

- Signal 必须存在且未被确认，否则返回 `40909`
- 确认后，系统执行 Signal 对应的业务逻辑（如更新 Process 状态）

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "signal_id": "SIG-202408050900-001",
    "status": "acknowledged",
    "acknowledged_by": "operator_001",
    "acknowledged_at": "2024-08-05T10:00:00+08:00",
    "ack_notes": "已人工核对物料到货，可开始生产",
    "cascade_effect": {
      "processes_affected": 1,
      "process_updates": [
        {
          "process_id": "PROC-2024-0892-01",
          "previous_status": "pending",
          "current_status": "ready"
        }
      ]
    }
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240805100000123490"
}
```

---

#### 6.2.7 基础数据接口

| 序号 | 接口名称 | 方法 | 路径 | 说明 |
|------|---------|------|------|------|
| D1 | 获取 Part Number 列表 | GET | `/part-numbers` | 物料编码查询 |
| D2 | 获取 Team 列表 | GET | `/teams` | 团队/工作中心查询 |
| D3 | 获取 Recipe 列表 | GET | `/recipes` | 工艺路线查询 |

---

**D1. 获取 Part Number 列表**

- **接口：** `GET /part-numbers`
- **权限：** 所有已认证用户
- **说明：** 查询物料编码主数据，用于 Job 创建时的产品型号选择。

**请求参数（Query）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| page | int | 否 | 页码 | 1 |
| page_size | int | 否 | 每页数量 | 20 |
| keyword | string | 否 | 编码或名称关键词 | "ENG" |
| part_category | string | 否 | 分类筛选：raw_material / semi_finished / finished_good / purchased_part | "finished_good" |
| is_active | boolean | 否 | 是否只显示启用状态 | true |

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [
      {
        "part_number": "ENG-D250",
        "part_name": "2.5L 柴油发动机",
        "part_category": "finished_good",
        "part_category_label": "成品",
        "default_uom": "台",
        "drawing_revision": "R3.2",
        "is_active": true,
        "has_active_bom": true,
        "active_bom_count": 1
      },
      {
        "part_number": "PKG-L200",
        "part_name": "L200 包装机",
        "part_category": "finished_good",
        "part_category_label": "成品",
        "default_uom": "台",
        "drawing_revision": "R1.5",
        "is_active": true,
        "has_active_bom": true,
        "active_bom_count": 2
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 156,
      "total_pages": 8
    }
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801100000123491"
}
```

---

**D2. 获取 Team 列表**

- **接口：** `GET /teams`
- **权限：** 所有已认证用户

**请求参数（Query）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| page | int | 否 | 页码 | 1 |
| page_size | int | 否 | 每页数量 | 50 |
| team_type | string | 否 | 类型筛选：workshop / production_line / work_center / supplier | "workshop" |
| is_active | boolean | 否 | 是否只显示启用状态 | true |

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [
      {
        "team_id": "TEAM-CAST",
        "team_code": "CAST",
        "team_name": "铸造车间",
        "team_type": "workshop",
        "team_type_label": "车间",
        "parent_team_id": null,
        "capacity_per_day": 16,
        "shift_count": 2,
        "location": "A栋-1楼",
        "is_active": true
      },
      {
        "team_id": "TEAM-MC",
        "team_code": "MC",
        "team_name": "机加车间",
        "team_type": "workshop",
        "team_type_label": "车间",
        "parent_team_id": null,
        "capacity_per_day": 40,
        "shift_count": 2,
        "location": "B栋-1楼",
        "is_active": true
      },
      {
        "team_id": "TEAM-ASSY",
        "team_code": "ASSY",
        "team_name": "装配车间",
        "team_type": "workshop",
        "team_type_label": "车间",
        "parent_team_id": null,
        "capacity_per_day": 24,
        "shift_count": 2,
        "location": "C栋-1楼",
        "is_active": true
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 50,
      "total": 7,
      "total_pages": 1
    }
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801100000123492"
}
```

---

**D3. 获取 Recipe 列表**

- **接口：** `GET /recipes`
- **权限：** 所有已认证用户

**请求参数（Query）：**

| 字段 | 类型 | 必填 | 说明 | 示例值 |
|------|------|------|------|--------|
| page | int | 否 | 页码 | 1 |
| page_size | int | 否 | 每页数量 | 20 |
| keyword | string | 否 | 编码或名称关键词 | "铸造" |
| part_number | string | 否 | 适用物料编码 | "BLK-CAST-001" |
| team_id | string | 否 | 执行团队筛选 | "TEAM-CAST" |
| status | string | 否 | 状态筛选：Active / Inactive | "Active" |

**成功响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [
      {
        "recipe_id": "RCP-CAST-001",
        "recipe_code": "R-CAST-01",
        "name": "低压铸造",
        "description": "适用于大批量铝合金铸件的低压铸造工艺",
        "default_team_id": "TEAM-CAST",
        "default_team_name": "铸造车间",
        "status": "Active",
        "estimated_duration_minutes": 480,
        "applicable_part_numbers": ["BLK-CAST-001", "HD-CAST-001"],
        "applicable_quantity_range": "50 ~ 999999",
        "version": "V1.2",
        "task_count": 6
      },
      {
        "recipe_id": "RCP-CAST-002",
        "recipe_code": "R-CAST-02",
        "name": "重力铸造",
        "description": "适用于小批量的重力铸造工艺",
        "default_team_id": "TEAM-CAST",
        "default_team_name": "铸造车间",
        "status": "Active",
        "estimated_duration_minutes": 360,
        "applicable_part_numbers": ["BLK-CAST-001"],
        "applicable_quantity_range": "1 ~ 49",
        "version": "V1.0",
        "task_count": 5
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 32,
      "total_pages": 2
    }
  },
  "timestamp": 1714982400000,
  "request_id": "req_20240801100000123493"
}
```

---

### 6.3 WebSocket 实时通知

系统通过 WebSocket 提供实时事件推送，客户端无需轮询即可获取状态变更通知。

#### 6.3.1 连接规范

| 项目 | 规范 |
|------|------|
| 协议 | WSS（WebSocket Secure） |
| 连接地址 | `wss://api.example.com/ws/v1/notifications` |
| 认证方式 | 连接时通过 Query Parameter 传递 JWT Token：`?token={jwt_token}` |
| 心跳机制 | 客户端每 30 秒发送一次 `ping`，服务端回复 `pong` |
| 重连策略 | 断线后指数退避重连（1s, 2s, 4s, 8s, 最大 30s） |
| 订阅模式 | 连接后发送 `subscribe` 消息指定订阅的 Job 或事件类型 |

#### 6.3.2 消息格式

所有 WebSocket 消息采用统一 JSON 格式：

```json
{
  "event": "job.status_changed",
  "timestamp": 1714982400000,
  "payload": {}
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| event | string | 事件类型标识 |
| timestamp | long | 事件产生时间戳（Unix 毫秒） |
| payload | object | 事件负载数据，结构因事件类型而异 |

#### 6.3.3 事件类型定义

**事件 1：`job.status_changed` — Job 状态变更**

当 Job 的状态发生流转时推送。

```json
{
  "event": "job.status_changed",
  "timestamp": 1714982400000,
  "payload": {
    "job_id": "JOB-2024-0892",
    "previous_status": "RECIPE_CFG",
    "current_status": "READY",
    "previous_status_label": "Recipe 配置中",
    "current_status_label": "待排程",
    "changed_by": "user_001",
    "changed_at": "2024-08-01T17:00:00+08:00",
    "trigger": "process_generated",
    "trigger_label": "Process 生成完成"
  }
}
```

| 字段 | 说明 |
|------|------|
| trigger | 状态变更的触发原因：user_action（用户操作）/ process_generated（Process 生成）/ scheduling_completed（排程完成）/ signal_received（信号触发）/ auto_transition（自动流转） |

**事件 2：`process.scheduled` — Process 排程完成**

当排程引擎完成某个 Job 的排程计算时推送。

```json
{
  "event": "process.scheduled",
  "timestamp": 1714982400000,
  "payload": {
    "job_id": "JOB-2024-0892",
    "schedule_request_id": "SCH-REQ-202408020800-001",
    "status": "completed",
    "scheduled_processes": 15,
    "scheduled_start": "2024-08-05T08:00:00+08:00",
    "scheduled_end": "2024-08-29T17:00:00+08:00",
    "target_date_met": true,
    "critical_path_hours": 176.5,
    "teams_scheduled": ["铸造车间", "锻造车间", "机加车间", "装配车间", "注塑车间", "总装车间"]
  }
}
```

**事件 3：`signal.received` — 新信号到达**

当系统收到新的 Signal 时推送。

```json
{
  "event": "signal.received",
  "timestamp": 1714982400000,
  "payload": {
    "signal_id": "SIG-202408050900-001",
    "signal_type": "material_received",
    "signal_type_label": "物料到货",
    "job_id": "JOB-2024-0892",
    "process_id": "PROC-2024-0892-01",
    "ref_document": "GR-2024-0892-001",
    "triggered_by": "system_wms",
    "received_at": "2024-08-05T09:00:02+08:00",
    "processed": false
  }
}
```

**事件 4：`recipe.config_progress` — Recipe 配置进度更新**

当用户配置（或取消配置）某个节点的 Recipe 时推送。

```json
{
  "event": "recipe.config_progress",
  "timestamp": 1714982400000,
  "payload": {
    "job_id": "JOB-2024-0892",
    "node_id": "BN-004",
    "node_name": "缸体铸造毛坯",
    "action": "configured",
    "action_label": "已配置",
    "recipe_id": "RCP-CAST-001",
    "recipe_name": "低压铸造",
    "selected_by": "user_001",
    "progress": {
      "total_configurable": 18,
      "configured": 9,
      "pending": 9,
      "skipped": 0,
      "progress_pct": 50
    },
    "is_all_configured": false,
    "next_recommended_node": {
      "node_id": "BN-006",
      "node_name": "主轴承盖",
      "reason": "同为第 4 层节点，继续按倒序配置"
    }
  }
}
```

| 字段 | 说明 |
|------|------|
| action | configured（已配置）/ cancelled（已取消）/ skipped（已跳过） |

**事件 5：`scheduling.running` — 排程引擎运行中**

当排程引擎开始运行时推送，用于前端展示排程进度条。

```json
{
  "event": "scheduling.running",
  "timestamp": 1714982400000,
  "payload": {
    "schedule_request_id": "SCH-REQ-202408020800-001",
    "status": "running",
    "progress_pct": 65,
    "current_phase": "capacity_allocation",
    "current_phase_label": "产能分配计算中",
    "elapsed_seconds": 10,
    "estimated_remaining_seconds": 5
  }
}
```

**事件 6：`error.notification` — 系统错误通知**

当系统发生需要用户关注的错误时推送。

```json
{
  "event": "error.notification",
  "timestamp": 1714982400000,
  "payload": {
    "error_code": 40906,
    "error_message": "Process 依赖图存在循环依赖",
    "related_job_id": "JOB-2024-0892",
    "severity": "high",
    "severity_label": "高",
    "description": "生成 Process 时发现 DAG 存在环路，请检查 Recipe 配置",
    "suggested_action": "检查缸体机加工件、活塞组、缸体组件模块的 Recipe 配置"
  }
}
```

#### 6.3.4 订阅消息

客户端连接后需发送订阅消息以接收特定事件：

```json
{
  "action": "subscribe",
  "topics": ["job.status_changed", "recipe.config_progress"],
  "filters": {
    "job_ids": ["JOB-2024-0892"]
  }
}
```

服务端回复确认：

```json
{
  "action": "subscribe_ack",
  "subscribed_topics": ["job.status_changed", "recipe.config_progress"],
  "timestamp": 1714982400000
}
```

---

### 6.4 接口安全

#### 6.4.1 JWT Token 认证

系统采用 JWT（JSON Web Token）进行身份认证。

**认证流程：**

1. 用户登录后，服务端返回 `access_token` 和 `refresh_token`
2. 客户端在每个 HTTP 请求的 Header 中携带：`Authorization: Bearer {access_token}`
3. Token 有效期：access_token 2 小时，refresh_token 7 天
4. Token 过期后返回 `40301`，客户端使用 refresh_token 换取新的 access_token

**Token 载荷结构：**

```json
{
  "sub": "user_001",
  "name": "张三",
  "role": "production_planner",
  "dept": "production_dept",
  "iat": 1714982400,
  "exp": 1714989600,
  "jti": "jwt_abc123xyz789"
}
```

#### 6.4.2 接口权限控制（RBAC）

系统基于角色的访问控制定义如下角色：

| 角色标识 | 角色名称 | 权限说明 |
|----------|---------|---------|
| admin | 系统管理员 | 全部操作权限，包括删除、系统配置 |
| production_manager | 生产经理 | 排程管理、Job 释放/暂停/恢复、删除 |
| production_planner | 生产计划员 | Job 创建/编辑/提交排程、Recipe 配置 |
| production_operator | 生产操作员 | 查看 Job 和 Process、发送 Signal、确认 Signal |
| viewer | 只读用户 | 仅查看所有数据，不可修改 |

**权限矩阵（关键操作）：**

| 操作 | admin | production_manager | production_planner | production_operator | viewer |
|------|-------|-------------------|-------------------|---------------------|--------|
| 创建 Job | Y | Y | Y | - | - |
| 编辑 Job（DRAFT） | Y | Y | Y | - | - |
| 删除 Job | Y | Y | - | - | - |
| 选择 BOM | Y | Y | Y | - | - |
| 配置 Recipe | Y | Y | Y | - | - |
| 生成 Process | Y | Y | Y | - | - |
| 提交排程 | Y | Y | Y | - | - |
| 释放执行 | Y | Y | - | - | - |
| 暂停/恢复 Job | Y | Y | - | - | - |
| 发送 Signal | Y | Y | Y | Y | - |
| 确认 Signal | Y | Y | Y | Y | - |
| 查看所有数据 | Y | Y | Y | Y | Y |

#### 6.4.3 请求签名与时间戳防重放

对于关键操作（排程、释放、Signal 发送），请求需附加签名以防止重放攻击。

**签名规则：**

1. 提取请求参数（Query + Body），按 key 字典序排序
2. 拼接为字符串：`key1=value1&key2=value2&...&timestamp={timestamp}&nonce={nonce}`
3. 使用 HMAC-SHA256 计算签名，密钥为用户的 API Secret
4. 在 Header 中传递：
   - `X-Timestamp`: 请求时间戳（Unix 秒），与服务器时间偏差不能超过 300 秒
   - `X-Nonce`: 随机字符串（UUID），同一 Nonce 5 分钟内不可重复使用
   - `X-Signature`: 签名字符串

**示例：**

```http
POST /api/v1/jobs/JOB-2024-0892/schedule HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json
X-Timestamp: 1714982400
X-Nonce: a1b2c3d4e5f6789012345678
X-Signature: sha256=3f2a1b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a

{
  "strategy": "target_date_backward"
}
```

#### 6.4.4 敏感操作日志记录

以下操作会被记录到审计日志，保留时间不少于 180 天：

| 操作类型 | 记录内容 |
|----------|---------|
| Job 创建/更新/删除 | 操作人、操作时间、变更字段前后值 |
| BOM 选择 | 操作人、选择的 BOM ID |
| Recipe 配置 | 操作人、节点 ID、选择的 Recipe ID |
| Process 生成 | 触发人、生成时间、生成的 Process 数量 |
| 排程操作 | 触发人、排程策略、排程耗时、排程结果 |
| 释放执行 | 操作人、释放时间、释放的 Process 列表 |
| 暂停/恢复 | 操作人、原因、时间 |
| Signal 发送/确认 | 操作人/系统、Signal 类型、关联 Job/Process |
| 权限变更 | 操作人、被变更用户、角色变更 |

**审计日志格式：**

```json
{
  "log_id": "AUD-202408011700-001",
  "action": "job.schedule",
  "resource_type": "job",
  "resource_id": "JOB-2024-0892",
  "actor": "user_001",
  "actor_role": "production_planner",
  "actor_ip": "192.168.1.100",
  "request_id": "req_20240801170000123462",
  "timestamp": "2024-08-01T17:00:00+08:00",
  "details": {
    "strategy": "target_date_backward",
    "previous_status": "READY",
    "current_status": "SCHEDULING"
  },
  "result": "success"
}
```

#### 6.4.5 接口限流

为防止恶意调用和系统过载，对各类接口实施限流：

| 接口类别 | 限流策略 | 说明 |
|----------|---------|------|
| 认证接口 | 5 次/分钟/IP | 登录、Token 刷新 |
| 写操作接口 | 60 次/分钟/用户 | 创建、更新、删除 |
| 读操作接口 | 300 次/分钟/用户 | 查询、列表、详情 |
| 排程接口 | 10 次/分钟/用户 | 排程、重新排程 |
| WebSocket 连接 | 3 个/用户 | 每个用户最多 3 个并发连接 |

超过限流阈值时返回 `40304` 错误码，响应中包含 `Retry-After` Header 提示重试时间。

---

## 附录：接口汇总表

### 完整接口清单（35 个接口）

| 分类 | 序号 | 方法 | 路径 | 接口名称 |
|------|------|------|------|---------|
| Job | J1 | POST | `/jobs` | 创建 Job |
| Job | J2 | GET | `/jobs` | 查询 Job 列表 |
| Job | J3 | GET | `/jobs/{job_id}` | 获取 Job 详情 |
| Job | J4 | PUT | `/jobs/{job_id}` | 更新 Job |
| Job | J5 | DELETE | `/jobs/{job_id}` | 删除 Job |
| Job | J6 | POST | `/jobs/{job_id}/schedule` | 提交排程 |
| Job | J7 | POST | `/jobs/{job_id}/unschedule` | 取消排程 |
| Job | J8 | POST | `/jobs/{job_id}/release` | 释放执行 |
| Job | J9 | POST | `/jobs/{job_id}/pause` | 暂停 Job |
| Job | J10 | POST | `/jobs/{job_id}/resume` | 恢复 Job |
| BOM | B1 | GET | `/boms` | 获取 BOM 列表 |
| BOM | B2 | GET | `/boms/{bom_id}` | 获取 BOM 详情 |
| BOM | B3 | GET | `/boms/{bom_id}/tree` | 展开 BOM 树 |
| BOM | B4 | POST | `/jobs/{job_id}/bom` | 为 Job 选择 BOM |
| Recipe | R1 | GET | `/bom-nodes/{node_id}/recipes` | 查询节点可用 Recipe |
| Recipe | R2 | GET | `/recipes/{recipe_id}` | 获取 Recipe 详情 |
| Recipe | R3 | POST | `/jobs/{job_id}/nodes/{node_id}/recipe` | 配置节点 Recipe |
| Recipe | R4 | POST | `/jobs/{job_id}/recipes/batch` | 批量配置 Recipe |
| Recipe | R5 | GET | `/jobs/{job_id}/recipe-config-status` | 获取 Recipe 配置状态 |
| Recipe | R6 | DELETE | `/jobs/{job_id}/nodes/{node_id}/recipe` | 取消节点 Recipe |
| Process | P1 | POST | `/jobs/{job_id}/processes/generate` | 生成 Process |
| Process | P2 | GET | `/jobs/{job_id}/processes` | 获取 Process 列表 |
| Process | P3 | GET | `/processes/{process_id}` | 获取 Process 详情 |
| Process | P4 | PUT | `/jobs/{job_id}/processes/reorder` | 更新 Process 顺序 |
| Process | P5 | GET | `/jobs/{job_id}/processes/dependency-graph` | 获取 Process 依赖图 |
| 排程 | S1 | POST | `/scheduling/run` | 触发排程 |
| 排程 | S2 | GET | `/jobs/{job_id}/schedule-result` | 获取排程结果 |
| 排程 | S3 | GET | `/jobs/{job_id}/gantt` | 获取排程甘特图 |
| 排程 | S4 | POST | `/jobs/{job_id}/reschedule` | 重新排程 |
| Signal | SG1 | POST | `/signals` | 发送 Signal |
| Signal | SG2 | GET | `/signals` | 获取 Signal 列表 |
| Signal | SG3 | POST | `/signals/{signal_id}/ack` | 确认 Signal |
| 基础数据 | D1 | GET | `/part-numbers` | 获取 Part Number 列表 |
| 基础数据 | D2 | GET | `/teams` | 获取 Team 列表 |
| 基础数据 | D3 | GET | `/recipes` | 获取 Recipe 列表 |

### WebSocket 事件汇总

| 事件类型 | 触发场景 |
|----------|---------|
| `job.status_changed` | Job 状态发生流转 |
| `process.scheduled` | 排程引擎完成某个 Job 的排程 |
| `signal.received` | 系统收到新的外部 Signal |
| `recipe.config_progress` | Recipe 配置进度更新 |
| `scheduling.running` | 排程引擎运行中（进度推送） |
| `error.notification` | 系统错误通知 |

---

> **文档结束**  
> 本文档为 Job 拆分排产系统的完整 RESTful API 接口规范，包含 35 个 HTTP 接口和 6 类 WebSocket 事件，覆盖 Job 生命周期管理、BOM 展开、Recipe 配置、Process 生成、排程、Signal 处理等全部核心业务流程。
