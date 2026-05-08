# Scheduler 需求中枢 — 产品需求文档 (PRD)

> 对应设计文档：`2026-05-07-scheduler-demand-hub-design.md`

---

## 一、Problem Statement

当前ERP系统中，客户订单（SO）是唯一进入排程的需求来源。Make to Order（MTO）、库存补货（Replenishment）、跨工厂调拨（Transfer）、返工（Rework）等需求游离于排程体系之外，导致：

1. **排程盲区**：Scheduler只能看到SO，看不到MTO、补货、调拨等真实产能需求，排程结果与实际生产脱节
2. **信息孤岛**：各Site各自为政，没有统一视图知道全公司在忙什么、哪里还有产能
3. **追踪困难**：PO、生产工单、调拨单分散在不同模块，无法从一张单追溯到"为什么做这个需求"
4. **响应迟钝**：SO变更、紧急插单时，需要人工在多个模块间协调，无法快速评估对现有计划的影响

我们需要一个"公司唯一大脑"——Scheduler需求中枢，让所有需要行动的需求（Demand）统一汇聚、统一排程、统一追踪。

---

## 二、Solution

构建 **Scheduler 需求中枢**，包含两大核心页面 + 一个通用执行单元：

### 2.1 核心概念

| 概念 | 说明 |
|------|------|
| **Schedule 页面** | 公司级调度大脑。所有Demand在此汇聚，Scheduler决定：做不做、何时做、在哪个Site做、用什么策略（生产/采购/调拨/委外）。 |
| **Site Plan 页面** | 工厂级执行面板。各Site在此查看分配给本Site的Job，标记执行状态、调整执行顺序（同步回Scheduler）。 |
| **Job** | BOM完全展开后的执行载体。一旦Scheduler确认Demand，就生成Job。Job自动将顶层产品的BOM逐层展开到底层原材料，每层半成品生成制造子任务（MO），每层原材料/外购件生成采购子任务（PO），并自动计算每层的净需求（需求数量 - 可用库存）。 |
| **Demand** | 任何触发行动的原始需求。来源包括：SO、MTO、Transfer、Replenishment、Rework、Forecast、样品。 |

### 2.2 解决什么问题

- ✅ SO、MTO、Transfer、Replenishment、Rework、样品全部进入同一个Demand池，Scheduler在一个页面看到全局
- ✅ 系统自动按规则合并可合并的Demand（如多个SO的MTS部分），减少Scheduler手动操作
- ✅ Job作为通用容器，将PO、生产工单、调拨单统一挂接，实现端到端追踪
- ✅ Site Plan可调整执行顺序并实时同步Scheduler，既放权又统一
- ✅ SO变更/紧急插单作为增量Demand进入Scheduler，快速评估影响并调整计划

---

## 三、User Stories

### Schedule 页面（Scheduler/计划经理）

1. As a Scheduler，我希望在一个页面看到所有待处理的Demand（不管来源是SO、MTO、调拨还是补货），so that 我不会遗漏任何需要排程的需求。
2. As a Scheduler，我希望系统自动将可合并的Demand（同一产品+同一Site+同一BOM+时间窗内）标记为合并建议，so that 我不需要手动逐个比对哪些可以一起生产。
3. As a Scheduler，我希望确认系统建议的合并时，能看到合并后的总数量、最早交期、涉及的SO列表，so that 我在确认前了解合并的影响。
4. As a Scheduler，我希望对系统建议的合并进行手动拆分（如认为不应该合并），so that 特殊需求可以独立处理。
5. As a Scheduler，我希望为每个Job设置优先级（系统自动计算加权得分，我可手动调整或置顶），so that Site知道执行顺序。
6. As a Scheduler，我希望看到各Site的实时产能负荷（如A厂80%、B厂40%），so that 我在指派Job时避免超载。
7. As a Scheduler，我希望将一个Job从"生产"策略改为"采购"或"调拨"策略，so that 在产能不足时有替代方案。
8. As a Scheduler，我希望在SO变更（增量/交期提前）时，系统自动创建变更Demand并建议合并或新建Job，so that 我快速响应客户需求变化。
9. As a Scheduler，我希望紧急插单能够高亮显示并支持一键置顶，so that 我可以立即安排产能处理突发需求。
10. As a Scheduler，我希望看到返工Demand自动置顶并以红色标记，so that 返工不会淹没在普通需求中。
11. As a Scheduler，我希望Replenishment Demand以草稿态进入页面，支持批量确认，so that 系统补货建议不会直接执行，保留我的审阅权。
12. As a Scheduler，我希望Transfer Demand在创建前能看到全公司各Site的可用库存，so that 我决定是否调拨以及从哪里调拨。

### Site Plan 页面（Site主管/班组长）

13. As a Site主管，我希望在Site Plan页面看到所有分配给本Site的Job列表，so that 我知道本工厂今天要做什么。
14. As a Site主管，我希望拖拽调整Job的执行顺序，并且修改会同步到Scheduler页面，so that 我根据现场实际情况灵活排产，同时让Scheduler知道。
15. As a Site主管，我希望看到每个Job的详细子任务（PO是否已下发、物料是否齐套、产线分配），so that 我掌握执行前置条件。
16. As a Site主管，我希望标记Job为"开工""部分完工""完工""异常暂停"，so that Scheduler实时掌握进度。
17. As a Site主管，我希望在缺料时一键向Scheduler发起调拨申请，so that 我不需要跳出系统去口头协调。
18. As a Site主管，我希望看到本Site各产线的甘特图负荷，so that 我直观了解产能瓶颈在哪条产线。

### 销售/客服（SO变更场景）

19. As a 销售，我在SO变更（加量/提前交期）后，希望系统自动通知Scheduler并生成变更Demand，so that 我不需要手动发邮件或打电话协调。
20. As a 销售，我希望看到SO关联的Job状态和预计完工时间，so that 我答复客户时数据准确。

### 采购部（Job驱动采购场景）

21. As a 采购员，我希望在Job确认排程后，系统自动生成PO草稿或PO建议（根据产品配置的auto issue设置），so that 我不需要手动创建PO。
22. As a 采购员，我希望看到哪些Job在等待我下单（采购子任务状态），so that 我按优先级处理。

### 仓库（Job驱动出入库场景）

23. As a 仓管员，我希望在Transfer Job确认后，看到调出/调入任务，so that 我知道要发多少货、收多少货。
24. As a 仓管员，我希望在生产Job完工后，看到入库任务和数量，so that 我及时完成入库。

### 质量部（返工场景）

25. As a 质检员，我在发现批量不合格时，希望一键发起返工Demand并关联原Job，so that 返工需求立即进入Scheduler排程。

---

## 四、Implementation Decisions

### 4.1 新增/修改的模块

| 模块 | 动作 | 说明 |
|------|------|------|
| **Schedule 页面** | 新建 | 公司级Demand池 + Job排程决策面板 |
| **Site Plan 页面** | 新建 | 工厂级Job执行面板（每Site一个） |
| **Demand 服务** | 新建 | 统一管理所有Demand的CRUD、合并引擎、优先级引擎 |
| **Job 服务** | 新建 | Job生命周期管理、子任务生成（PO/MO/TO）、状态机 |
| **产品模块** | 修改 | Part配置增加"默认MTO比例"字段 |
| **SO模块** | 修改 | SO创建/变更时自动生成Demand，支持MTS/MTO拆分 |
| **库存模块** | 修改 | 库存低于安全线时触发Replenishment Demand |
| **采购模块** | 修改 | PO来源支持"Job驱动"，从Job的采购子任务自动生成PO |
| **生产模块** | 修改 | 生产工单来源统一为Job的制造子任务 |

### 4.2 关键接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/demands` | GET/POST/PUT | Demand的CRUD |
| `/api/demands/{id}/merge` | POST | 确认合并多个Demand |
| `/api/demands/{id}/split` | POST | 拆分Demand |
| `/api/jobs` | GET/POST/PUT | Job的CRUD |
| `/api/jobs/{id}/schedule` | POST | Scheduler确认排程 |
| `/api/jobs/{id}/subtasks` | GET/POST | 子任务管理 |
| `/api/sites/{id}/plan` | GET | 获取Site的Job执行计划 |
| `/api/sites/{id}/plan/reorder` | PUT | 调整Site内Job顺序 |
| `/api/sites/{id}/capacity` | GET | 获取Site实时产能负荷 |
| `/api/parts/{id}/mto-ratio` | PUT | 设置产品默认MTO比例 |

### 4.3 架构决策

1. **Demand与Job分离**：Demand是"为什么做"，Job是"怎么做"。一个Job可关联多个Demand（合并场景），一个Demand也可拆分到多个Job（拆分场景）。通过JOB_LINE中间表维护多对多关系。

2. **合并引擎在服务端**：合并建议由后端算法计算，前端仅展示结果。避免前端大量计算导致性能问题。

3. **实时同步采用WebSocket**：Site Plan调整顺序后，通过WebSocket实时推送Scheduler页面更新，避免轮询。

4. **子任务异步生成**：Scheduler确认Job后，子任务（PO/MO/TO）通过消息队列异步生成，避免阻塞页面响应。

5. **优先级计算定时刷新**：Demand优先级每5分钟重新计算一次（交期紧迫度会随时间变化），但Scheduler手动锁定的不刷新。

### 4.4 数据模型决策

- **DEMAND表**：存储原始需求，保留来源信息（SO号、Transfer申请号等），即使合并后也不删除，便于追溯。
- **JOB表**：存储排程后的执行单元，是调度系统的核心实体。
- **JOB_LINE表**：维护Demand与Job的多对多关系及数量分配（MTS/MTO）。
- **SUB_TASK表**：Job的下游执行指令，类型包括PO、MO、TO、RETURN。

---

## 五、Testing Decisions

### 5.1 测试策略

- **单元测试**：合并引擎的6条件判断逻辑、优先级计算公式的边界条件（如交期恰好为当天）、Job状态机流转。
- **集成测试**：SO创建→生成Demand→合并建议→Scheduler确认→生成Job→子任务生成→Site执行→状态同步的全流程。
- **端到端测试**：Scheduler在页面完成一次完整的排程操作（合并、调整优先级、指派Site），验证Site Plan实时同步。

### 5.2 关键测试用例

1. **合并边界**：两个Demand时间窗相差1天（应合并）vs 相差8天（不应合并，默认7天窗口）。
2. **MTO隔离**：两个SO的MTO部分即使产品相同、Site相同、时间窗重叠，系统也必须阻止合并。
3. **优先级动态变化**：Job初始优先级70，交期从3天后变为1天后，定时刷新后优先级应上升。
4. **Site顺序同步**：Site主管拖拽调整Job顺序后，Scheduler页面5秒内刷新显示新顺序。
5. **SO变更合并**：原Job已开工，SO增量应创建新Job，系统不能错误合并到已执行中的Job。

---

## 六、Out of Scope

以下功能不在本PRD范围内，留待后续版本：

1. **AI智能排程**：基于机器学习预测最优排程方案。本期仅提供规则引擎+人工决策。
2. **多层级BOM自动展开**：Job的制造子任务目前支持单层BOM，多级BOM展开后续迭代。
3. **外协/委外管理**：Job策略中的"SUBCONTRACT"标记存在，但完整的外协流程（外协报价、外协收货）后续迭代。
4. **移动端Site Plan**：本期仅提供Web端，移动端现场扫码报工后续迭代。
5. **财务成本实时结转**：Job的成本归集逻辑在后续财务模块集成时细化。
6. **跨区域/跨国Transfer的关税/汇率**：Transfer本期仅处理同一公司内的数量转移，不涉及跨境复杂财务。

---

## 七、Further Notes

1. **历史数据迁移**：现有SO、PO、生产工单需要映射到新的Demand/Job模型。建议采用"只读归档+新单走新流程"的迁移策略，避免大规模数据改造风险。

2. **性能考虑**：如果公司每天有上千个Demand进入，Schedule页面需要分页+虚拟滚动。合并引擎的计算应在后台异步进行，页面打开时直接读取缓存结果。

3. **权限设计**：Scheduler可操作所有Demand和Job；Site主管只能看到和操作分配给本Site的Job；销售只能看到和操作自己创建的SO及其关联Demand。

4. **消息通知**：以下事件需要推送通知——
   - Scheduler确认Job后 → 通知相关Site主管
   - Site标记Job异常 → 通知Scheduler
   - 采购子任务生成后 → 通知采购员
   - SO变更创建增量Demand → 通知Scheduler和销售
