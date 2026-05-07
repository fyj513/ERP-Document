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
