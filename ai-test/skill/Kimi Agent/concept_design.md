# Job 拆分排产系统 — 业务概念与信息架构设计

> 版本：v1.0  
> 作者：业务架构师  
> 定位：指导数据库设计与接口设计的核心业务文档

---

## 目录

1. [设计思考](#1-设计思考)
2. [应用场景](#2-应用场景)
3. [完整流程示例](#3-完整流程示例)
4. [实体定义与关系](#4-实体定义与关系)
5. [ER 逻辑图](#5-er-逻辑图)
6. [状态流转](#6-状态流转)
7. [Process 生成算法描述](#7-process-生成算法描述)
8. [UI 页面结构与交互状态定义](#8-ui-页面结构与交互状态定义)

---

## 1. 设计思考

### 1.1 解决什么问题

离散制造企业的排产面临一个核心矛盾：

- **BOM（物料清单）天然是多层级树状结构**，描述的是"由哪些零部件组成"的静态关系；
- **排程（Scheduling）需要的是扁平化的、按执行单元组织的序列**，描述的是"谁在什么时间做什么"的动态安排。

将这两者直接对接，往往会遇到以下问题：

| 问题 | 说明 |
|------|------|
| 层级跳跃 | 不同 BOM 分支可能由同一团队负责，如果按 BOM 层级逐层排程，会造成同一团队的任务被割裂到多个不连续的时段 |
| 工序衔接混乱 | 子节点的生产必须完成后，父节点才能开始装配。如果不对这种依赖进行显式建模，会出现"料不齐就上线"的生产事故 |
| 工艺方案多变 | 同一零部件在不同批量、不同交期要求下，可能走完全不同的工艺路线（如委外加工 vs 自制、粗加工 vs 精加工） |
| 多人协作盲区 | 一个 Job 涉及多个团队（机加、装配、质检），传统工单往往只关注单个团队，跨团队的交接点和等待时间成为黑箱 |

### 1.2 设计哲学

本系统采用"**先展开、再聚合、后排程**"的三段式设计：

```
┌─────────────────────────────────────────────────────────────────┐
│  第一阶段：展开（Explode）                                         │
│  将 Job 的 BOM 树完整展开到底，每个节点成为一个可配置单元             │
├─────────────────────────────────────────────────────────────────┤
│  第二阶段：聚合（Group）                                           │
│  按 "执行团队（team）" 将 BOM 分支聚合为 Process                   │
│  同一团队负责的连续工序 → 合并为一个排程单元                        │
├─────────────────────────────────────────────────────────────────┤
│  第三阶段：排程（Schedule）                                        │
│  根据优先级、依赖关系、信号触发，确定 Process 的执行顺序与时间        │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 关键设计决策

**决策 1：BOM 直接拆分到底**

- 不采用"只展开一层，逐层下推"的传统方式；
- 在 Job 创建阶段一次性将 BOM 展开为完整的叶子节点树；
- 好处：排程前就能看到完整的物料全景，避免中途缺料导致停线。

**决策 2：Recipe 从叶子到根倒序配置**

- 叶子节点（原材料/采购件）不需要配置 Recipe；
- 从最深的中间节点开始，逐层向上配置；
- 好处：先确定底层加工工艺，再确定上层装配工艺，符合"先加工后装配"的物理逻辑。

**决策 3：Process 按 team group，而非按 BOM 层级 group**

- 传统方式：按 BOM 层级排程，每个层级是一个排程单元；
- 本系统：跨层级的、同一 team 的节点合并为一个 Process；
- 好处：减少团队切换成本，一个 Process 对应一张派工单，现场执行更清晰。

**决策 4：Make to Stock (MTS) vs Make to Order (MTO) 混合支持**

- 同一 Job 内可混合两种模式：部分数量面向库存、部分面向订单；
- 系统需要记录每种模式的数量，影响优先级计算和交期承诺。

---

## 2. 应用场景

### 场景 A：汽车发动机装配（核心示例，详见第 3 节）

某发动机厂接到客户订单，需要生产 100 台柴油发动机。每台发动机由缸体、曲轴、缸盖、进排气系统四大模块组成，每个模块又包含多层零部件。系统需要：

1. 创建 Job，录入 Part Number（发动机型号）和数量（100 台）；
2. 展开 BOM，看到 5 层、60+ 个节点的完整物料树；
3. 为每个自制件节点选择 Recipe（机加、铸造、热处理等）；
4. 系统自动将同一机加车间负责的 20+ 个零件合并为几个 Process；
5. 排程引擎输出各 Process 的开始/结束时间、设备占用、人员需求。

### 场景 B：定制机械设备（MTO 为主）

某食品机械厂接到客户定制订单，生产 1 台专用包装机。BOM 展开后发现多个零部件需要委外加工（表面处理、热处理）。系统需要：

- 在 Recipe 选择时区分"自制"和"委外"两种 team；
- 委外 Process 的排程需要考虑供应商交期，而非内部产能；
- 自制 Process 与委外 Process 之间存在强依赖（如必须先完成热处理才能磨削）。

### 场景 C：批量电子组装（MTS 为主）

某电子厂为双十一备货，需要生产 10,000 台智能音箱。BOM 展开后有 PCB、外壳、喇叭、电池等多个模块。

- PCB 由 SMT 贴片团队负责；
- 外壳由注塑团队负责；
- 最终装配由组装团队负责；
- 系统按 team 自动 group 为三大 Process，分别排程。

---

## 3. 完整流程示例

### 3.1 示例背景：汽车发动机装配 Job

**Job 基础信息：**

| 字段 | 值 |
|------|-----|
| Job ID | JOB-2024-0892 |
| 产品型号 | ENG-D250（2.5L 柴油发动机） |
| 生产数量 | 100 台 |
| MTS 数量 | 20 台（备库存） |
| MTO 数量 | 80 台（客户订单） |
| 优先级 | High（客户订单交期紧） |
| 目标交期 | 2024-08-30 |

### 3.2 BOM 树结构（完整展开到底）

```
ENG-D250 柴油发动机总成（成品）─── 需配置 Recipe
│
├─ 缸体组件模块 ─── 需配置 Recipe
│   ├─ 缸体机加工件 ─── 需配置 Recipe
│   │   ├─ 缸体铸造毛坯 ─── 需配置 Recipe
│   │   │   └─ 铝合金锭 AL-Si10Cu ─── 叶子节点（采购件）⬜
│   │   ├─ 主轴承盖 ─── 需配置 Recipe
│   │   │   └─ 灰铸铁毛坯 HT250 ─── 叶子节点（采购件）⬜
│   │   └─ 缸体螺栓套件 ─── 叶子节点（采购件）⬜
│   ├─ 活塞组 ─── 需配置 Recipe
│   │   ├─ 活塞 ─── 需配置 Recipe
│   │   │   └─ 铝合金棒料 AL-4032 ─── 叶子节点（采购件）⬜
│   │   ├─ 活塞销 ─── 需配置 Recipe
│   │   │   └─ 合金钢管 20CrMnTi ─── 叶子节点（采购件）⬜
│   │   └─ 活塞环 ─── 叶子节点（采购件）⬜
│   └─ 连杆组 ─── 需配置 Recipe
│       ├─ 连杆体 ─── 需配置 Recipe
│       │   └─ 锻钢毛坯 42CrMo ─── 叶子节点（采购件）⬜
│       └─ 连杆轴承 ─── 叶子节点（采购件）⬜
│
├─ 曲轴组件模块 ─── 需配置 Recipe
│   ├─ 曲轴 ─── 需配置 Recipe
│   │   ├─ 曲轴毛坯 ─── 需配置 Recipe
│   │   │   └─ 球墨铸铁 QT700-2 ─── 叶子节点（采购件）⬜
│   │   └─ 主轴瓦 ─── 叶子节点（采购件）⬜
│   └─ 飞轮 ─── 需配置 Recipe
│       └─ 铸铁圆盘 HT300 ─── 叶子节点（采购件）⬜
│
├─ 缸盖组件模块 ─── 需配置 Recipe
│   ├─ 缸盖机加工件 ─── 需配置 Recipe
│   │   ├─ 缸盖铸造毛坯 ─── 需配置 Recipe
│   │   │   └─ 铝合金锭 AL-Si7Mg ─── 叶子节点（采购件）⬜
│   │   └─ 气门座圈 ─── 叶子节点（采购件）⬜
│   ├─ 气门组 ─── 需配置 Recipe
│   │   ├─ 进气门 ─── 需配置 Recipe
│   │   │   └─ 耐高温钢棒 21-4N ─── 叶子节点（采购件）⬜
│   │   ├─ 排气门 ─── 需配置 Recipe
│   │   │   └─ 耐高温钢棒 Inconel 751 ─── 叶子节点（采购件）⬜
│   │   └─ 气门弹簧 ─── 叶子节点（采购件）⬜
│   └─ 凸轮轴 ─── 需配置 Recipe
│       ├─ 凸轮轴毛坯 ─── 需配置 Recipe
│       │   └─ 冷硬铸铁棒 CHC-1 ─── 叶子节点（采购件）⬜
│       └─ 凸轮轴轴承 ─── 叶子节点（采购件）⬜
│
└─ 进排气系统模块 ─── 需配置 Recipe
    ├─ 进气歧管 ─── 需配置 Recipe
    │   ├─ 歧管注塑件 ─── 需配置 Recipe
    │   │   └─ PA66-GF30 原料 ─── 叶子节点（采购件）⬜
    │   └─ 节气门体 ─── 叶子节点（采购件）⬜
    ├─ 排气歧管 ─── 需配置 Recipe
    │   ├─ 歧管铸钢件 ─── 需配置 Recipe
    │   │   └─ 铸钢毛坯 ZG25Cr20Ni14 ─── 叶子节点（采购件）⬜
    │   └─ 氧传感器 ─── 叶子节点（采购件）⬜
    └─ 涡轮增压器 ─── 叶子节点（采购件）⬜

图例：
  ─── 需配置 Recipe 的中间节点（🔵 圆圈）
  ─── 叶子节点，无需配置 Recipe（⬜ 方块）
```

**BOM 统计：**
- 总节点数：35 个
- 中间节点（需配置 Recipe）：18 个
- 叶子节点（采购件/原材料）：17 个
- BOM 最大深度：5 层（成品 → 模块 → 子部件 → 毛坯 → 原材料）

### 3.3 Recipe 配置过程（倒序：从叶子到根）

#### 第 1 步：配置第 4 层节点（最接近原材料）

**节点：缸体铸造毛坯**
- 系统根据 Part Number = "缸体铸造毛坯" + 材质 = "AL-Si10Cu" + 批量 = 100 筛选 Recipe：

| Recipe ID | 名称 | Team | Tasks | 适用条件 |
|-----------|------|------|-------|---------|
| R-CAST-01 | 低压铸造 | 铸造车间 | 模具准备→熔炼→浇注→冷却→脱模→初检 | 批量 ≥ 50 |
| R-CAST-02 | 重力铸造 | 铸造车间 | 熔炼→浇注→冷却→清砂→初检 | 批量 < 50 |
- **选择**：R-CAST-01（低压铸造，批量 100 适用）

**节点：主轴承盖**
- 匹配 Recipe：R-CAST-03（砂型铸造，铸造车间）

**节点：活塞**
- 匹配 Recipe：R-FORGE-01（热锻 + 精车，锻造车间）

**节点：活塞销**
- 匹配 Recipe：R-TURN-01（数控车削，机加车间）

**节点：连杆体**
- 匹配 Recipe：R-FORGE-02（模锻 + 数控加工，锻造车间）

**节点：曲轴毛坯**
- 匹配 Recipe：R-CAST-04（壳型铸造，铸造车间）

**节点：飞轮**
- 匹配 Recipe：R-TURN-02（车削 + 钻孔，机加车间）

**节点：缸盖铸造毛坯**
- 匹配 Recipe：R-CAST-01（低压铸造，铸造车间）

**节点：进气门 / 排气门**
- 匹配 Recipe：R-FORGE-03（热锻 + 高频淬火，锻造车间）

**节点：凸轮轴毛坯**
- 匹配 Recipe：R-CAST-05（离心铸造，铸造车间）

**节点：歧管注塑件**
- 匹配 Recipe：R-INJ-01（注塑成型，注塑车间）

**节点：歧管铸钢件**
- 匹配 Recipe：R-CAST-06（熔模铸造，精密铸造车间）

#### 第 2 步：配置第 3 层节点

**节点：缸体机加工件**
- 前置依赖：缸体铸造毛坯已完成
- 匹配 Recipe：R-MC-01（CNC 铣面→钻孔→镗缸→精铣，机加车间）

**节点：活塞组（装配）**
- 前置依赖：活塞、活塞销、活塞环齐套
- 匹配 Recipe：R-ASSY-01（压装活塞销→装活塞环→检验，装配车间）

**节点：连杆组（装配）**
- 前置依赖：连杆体、连杆轴承齐套
- 匹配 Recipe：R-ASSY-02（压装轴承→螺栓拧紧→检验，装配车间）

**节点：曲轴**
- 前置依赖：曲轴毛坯已完成
- 匹配 Recipe：R-MC-02（车削→磨削→动平衡→精磨，机加车间）

**节点：缸盖机加工件**
- 匹配 Recipe：R-MC-03（CNC 铣面→钻气道→镗气门座→精铣，机加车间）

**节点：气门组（装配）**
- 匹配 Recipe：R-ASSY-03（装气门座→装气门→装弹簧→气密检验，装配车间）

**节点：凸轮轴**
- 匹配 Recipe：R-MC-04（车削→凸轮磨削→精磨轴颈，机加车间）

#### 第 3 步：配置第 2 层节点

**节点：缸体组件模块**
- 前置依赖：缸体机加工件、活塞组、连杆组齐套
- 匹配 Recipe：R-ASSY-04（装活塞连杆→入缸体→装轴承盖→扭矩检验，装配车间）

**节点：曲轴组件模块**
- 匹配 Recipe：R-ASSY-05（装主轴瓦→装曲轴→装飞轮→转动检验，装配车间）

**节点：缸盖组件模块**
- 匹配 Recipe：R-ASSY-06（装气门组→装凸轮轴→调气门间隙→缸盖试漏，装配车间）

**节点：进排气系统模块**
- 匹配 Recipe：R-ASSY-07（装进气歧管→装排气歧管→装增压器→管路连接，装配车间）

#### 第 4 步：配置第 1 层节点（根节点）

**节点：ENG-D250 柴油发动机总成**
- 前置依赖：四大模块齐套
- 匹配 Recipe：R-FINAL-01（总装→冷磨→热试→调整→终检→入库，总装车间）
- Tasks：缸体曲轴合装→装缸盖→装进排气系统→装附件→冷磨合→热试→调整→喷漆→终检→入库

### 3.4 Recipe 配置完成后汇总

| 层级 | 节点 | Recipe | Team | Tasks 数量 |
|------|------|--------|------|-----------|
| 4 | 缸体铸造毛坯 | R-CAST-01 | 铸造车间 | 6 |
| 4 | 主轴承盖 | R-CAST-03 | 铸造车间 | 5 |
| 4 | 活塞 | R-FORGE-01 | 锻造车间 | 7 |
| 4 | 活塞销 | R-TURN-01 | 机加车间 | 4 |
| 4 | 连杆体 | R-FORGE-02 | 锻造车间 | 8 |
| 4 | 曲轴毛坯 | R-CAST-04 | 铸造车间 | 6 |
| 4 | 飞轮 | R-TURN-02 | 机加车间 | 5 |
| 4 | 缸盖铸造毛坯 | R-CAST-01 | 铸造车间 | 6 |
| 4 | 进气门 | R-FORGE-03 | 锻造车间 | 6 |
| 4 | 排气门 | R-FORGE-03 | 锻造车间 | 6 |
| 4 | 凸轮轴毛坯 | R-CAST-05 | 铸造车间 | 5 |
| 4 | 歧管注塑件 | R-INJ-01 | 注塑车间 | 4 |
| 4 | 歧管铸钢件 | R-CAST-06 | 精密铸造车间 | 7 |
| 3 | 缸体机加工件 | R-MC-01 | 机加车间 | 4 |
| 3 | 活塞组 | R-ASSY-01 | 装配车间 | 3 |
| 3 | 连杆组 | R-ASSY-02 | 装配车间 | 3 |
| 3 | 曲轴 | R-MC-02 | 机加车间 | 4 |
| 3 | 缸盖机加工件 | R-MC-03 | 机加车间 | 4 |
| 3 | 气门组 | R-ASSY-03 | 装配车间 | 4 |
| 3 | 凸轮轴 | R-MC-04 | 机加车间 | 3 |
| 2 | 缸体组件模块 | R-ASSY-04 | 装配车间 | 4 |
| 2 | 曲轴组件模块 | R-ASSY-05 | 装配车间 | 4 |
| 2 | 缸盖组件模块 | R-ASSY-06 | 装配车间 | 4 |
| 2 | 进排气系统模块 | R-ASSY-07 | 装配车间 | 4 |
| 1 | 发动机总成 | R-FINAL-01 | 总装车间 | 10 |

### 3.5 Process 生成（按 team group）

系统解析已配置的 BOM 树，按 team 将节点 group 为 Process。group 规则：

1. 同一 team 负责的、在 BOM 树中连续的分支，合并为一个 Process；
2. 如果同一 team 在不同分支上的工作存在依赖关系（必须等 A 完成才能做 B），则拆分为两个 Process；
3. 如果同一 team 的工作被其他 team 的工序隔开，则拆分为多个 Process。

**生成的 Process 列表：**

```
Process 1: P-CAST-01
  名称：缸体与缸盖铸造
  Team：铸造车间
  包含节点：缸体铸造毛坯、主轴承盖、缸盖铸造毛坯
  任务汇总：模具准备→熔炼→浇注(缸体)×100→浇注(缸盖)×100→冷却→脱模→清砂→初检
  前置依赖：无（原材料已到位）
  后置 Process：P-MC-01（缸体机加工）, P-MC-03（缸盖机加工）

Process 2: P-CAST-02
  名称：曲轴与凸轮轴铸造
  Team：铸造车间
  包含节点：曲轴毛坯、凸轮轴毛坯
  任务汇总：壳型/离心铸造→浇注×100→冷却→清砂→尺寸初检
  前置依赖：无
  后置 Process：P-MC-02（曲轴机加工）, P-MC-04（凸轮轴机加工）

Process 3: P-CAST-03
  名称：排气歧管精密铸造
  Team：精密铸造车间
  包含节点：歧管铸钢件
  任务汇总：蜡模制作→制壳→脱蜡→焙烧→浇注→清砂→精整
  前置依赖：无
  后置 Process：P-ASSY-EX（进排气系统装配）

Process 4: P-FORGE-01
  名称：活塞与连杆锻造
  Team：锻造车间
  包含节点：活塞、连杆体
  任务汇总：下料→加热→模锻(活塞)×100→模锻(连杆)×100→切边→校正→冷却
  前置依赖：无
  后置 Process：P-MC-05（活塞销机加工）, P-ASSY-01（活塞组装配）, P-ASSY-02（连杆组装配）

Process 5: P-FORGE-02
  名称：气门锻造
  Team：锻造车间
  包含节点：进气门、排气门
  任务汇总：热锻×200(进/排气各100)→高频淬火→回火→校直
  前置依赖：无
  后置 Process：P-ASSY-03（气门组装配）

Process 6: P-MC-01
  名称：缸体机加工
  Team：机加车间
  包含节点：缸体机加工件、活塞销
  任务汇总：CNC铣面→钻孔→镗缸→精铣 + 数控车削活塞销
  前置依赖：P-CAST-01 完成
  后置 Process：P-ASSY-04（缸体组件装配）

Process 7: P-MC-02
  名称：曲轴与飞轮机加工
  Team：机加车间
  包含节点：曲轴、飞轮
  任务汇总：车削→磨削→动平衡→精磨 + 车削钻孔
  前置依赖：P-CAST-02 完成
  后置 Process：P-ASSY-05（曲轴组件装配）

Process 8: P-MC-03
  名称：缸盖与凸轮轴机加工
  Team：机加车间
  包含节点：缸盖机加工件、凸轮轴
  任务汇总：CNC铣面→钻气道→镗气门座→凸轮磨削
  前置依赖：P-CAST-01, P-CAST-02 完成
  后置 Process：P-ASSY-06（缸盖组件装配）

Process 9: P-INJ-01
  名称：进气歧管注塑
  Team：注塑车间
  包含节点：歧管注塑件
  任务汇总：烘料→注塑成型→去毛刺→尺寸检验
  前置依赖：无
  后置 Process：P-ASSY-EX（进排气系统装配）

Process 10: P-ASSY-01
  名称：活塞与连杆组件装配
  Team：装配车间
  包含节点：活塞组、连杆组
  任务汇总：压装活塞销→装活塞环 + 压装轴承→螺栓拧紧
  前置依赖：P-FORGE-01, P-MC-01 完成
  后置 Process：P-ASSY-04（缸体组件装配）

Process 11: P-ASSY-02
  名称：气门组与缸盖组件装配
  Team：装配车间
  包含节点：气门组、缸盖组件模块
  任务汇总：装气门座→装气门→装弹簧→气密检验→装凸轮轴→调间隙
  前置依赖：P-FORGE-02, P-MC-03 完成
  后置 Process：P-FINAL（发动机总装）

Process 12: P-ASSY-03
  名称：曲轴组件装配
  Team：装配车间
  包含节点：曲轴组件模块
  任务汇总：装主轴瓦→装曲轴→装飞轮→转动检验
  前置依赖：P-MC-02 完成
  后置 Process：P-FINAL（发动机总装）

Process 13: P-ASSY-04
  名称：进排气系统装配
  Team：装配车间
  包含节点：进排气系统模块
  任务汇总：装进气歧管→装排气歧管→装增压器→管路连接
  前置依赖：P-INJ-01, P-CAST-03 完成
  后置 Process：P-FINAL（发动机总装）

Process 14: P-ASSY-05
  名称：缸体组件装配
  Team：装配车间
  包含节点：缸体组件模块
  任务汇总：装活塞连杆→入缸体→装轴承盖→扭矩检验
  前置依赖：P-ASSY-01 完成
  后置 Process：P-FINAL（发动机总装）

Process 15: P-FINAL
  名称：发动机总装与调试
  Team：总装车间
  包含节点：发动机总成（根节点）
  任务汇总：缸体曲轴合装→装缸盖→装进排气系统→装附件→冷磨合→热试→调整→喷漆→终检→入库
  前置依赖：P-ASSY-02, P-ASSY-03, P-ASSY-04, P-ASSY-05 全部完成
  后置 Process：无（Job 完成）
```

### 3.6 排程结果

排程引擎根据以下输入计算：

- **Job 优先级**：High → 优先安排设备与人员
- **Process 依赖图**：15 个 Process 构成 DAG（有向无环图）
- **各 team 产能**：铸造车间 2 条线、机加车间 5 台 CNC、装配车间 3 个工位、总装车间 1 条线
- **Signal（收货信号）**：原材料已齐套，无需等待采购

**排程甘特图（简化）：**

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

**关键路径**：P-CAST-01 → P-MC-01 → P-ASSY-01 → P-ASSY-04 → P-FINAL，共约 22 个工作日。

---

## 4. 实体定义与关系

### 4.1 实体清单

| 实体 | 说明 | 对应业务概念 |
|------|------|-------------|
| Job | 作业/工单，排产最顶层单元 | 一份生产指令 |
| BOM | 物料清单模板 | 产品的结构化物料定义 |
| BOMNode | BOM 中的单个节点 | 一个零部件/原材料 |
| BOMNodeRelation | BOM 节点间的父子关系 | 树状结构的边 |
| JobBOMNode | Job 实例化的 BOM 节点 | 某 Job 中某个节点的具体配置 |
| Recipe | 工艺路线模板 | 某零件的加工方案 |
| RecipeTask | 工艺路线中的单个任务 | 一道工序（如"钻孔"） |
| JobRecipe | Job 中某节点选定的 Recipe 实例 | 具体的工艺选择记录 |
| Process | 排程单元 | 某团队的一组工作安排 |
| ProcessTask | Process 内的任务实例 | 排程后的具体任务 |
| ProcessDependency | Process 间的依赖关系 | 前置/后置关系 |
| Team | 执行团队/工作中心 | 车间、产线、工位 |
| Signal | 外部信号/事件 | 物料到达、设备就绪等 |
| PartNumber | 物料编码主数据 | 零件的唯一标识 |

### 4.2 实体详细定义

#### Entity: Job（作业/工单）

| 字段 | 类型 | 说明 |
|------|------|------|
| job_id | PK, string | 唯一标识，如 JOB-2024-0892 |
| part_number | FK | 产品型号，关联 PartNumber |
| quantity_total | int | 总生产数量 |
| quantity_mts | int | Make to Stock 数量 |
| quantity_mto | int | Make to Order 数量 |
| priority | enum | 优先级：Critical / High / Normal / Low |
| target_date | date | 目标交期 |
| status | enum | 状态（见第 6 节状态流转） |
| created_at | datetime | 创建时间 |
| created_by | string | 创建人 |
| bom_id | FK | 关联的 BOM 模板 |
| scheduled_start | datetime | 排程后：计划开始时间 |
| scheduled_end | datetime | 排程后：计划结束时间 |
| actual_start | datetime | 实际开始时间 |
| actual_end | datetime | 实际结束时间 |

#### Entity: BOM（物料清单模板）

| 字段 | 类型 | 说明 |
|------|------|------|
| bom_id | PK, string | 唯一标识 |
| part_number | FK | 根节点产品型号 |
| version | string | BOM 版本号 |
| version_status | enum | Active / Obsolete / Draft |
| description | text | 描述 |
| created_at | datetime | 创建时间 |
| max_depth | int | BOM 最大深度（缓存值） |
| total_nodes | int | 总节点数（缓存值） |

#### Entity: BOMNode（BOM 节点）

| 字段 | 类型 | 说明 |
|------|------|------|
| node_id | PK, string | 唯一标识 |
| bom_id | FK | 所属 BOM |
| part_number | FK | 物料编码 |
| node_type | enum | intermediate（中间节点，需配 Recipe）/ leaf（叶子节点） |
| level | int | 在 BOM 树中的层级（根=1） |
| quantity_per_parent | decimal | 父节点所需本节点的数量 |
| unit | string | 计量单位（件/kg/m） |
| is_configurable | boolean | 是否需要配置 Recipe |
| default_recipe_id | FK | 默认 Recipe（可选） |
| drawing_no | string | 图号（可选） |

#### Entity: BOMNodeRelation（BOM 树结构）

| 字段 | 类型 | 说明 |
|------|------|------|
| relation_id | PK, string | 唯一标识 |
| bom_id | FK | 所属 BOM |
| parent_node_id | FK | 父节点 |
| child_node_id | FK | 子节点 |
| sort_order | int | 同级节点的排序 |

#### Entity: JobBOMNode（Job 实例化的 BOM 节点）

| 字段 | 类型 | 说明 |
|------|------|------|
| job_node_id | PK, string | 唯一标识 |
| job_id | FK | 所属 Job |
| node_id | FK | 关联的 BOMNode |
| parent_job_node_id | FK | 父节点实例（自关联） |
| quantity_required | decimal | 本 Job 需要该节点的总数量 |
| quantity_completed | decimal | 已完成数量 |
| selected_recipe_id | FK | 选定的 Recipe |
| recipe_config_status | enum | pending / configured / skipped |
| config_order | int | 配置顺序（倒序配置时使用） |
| level | int | 层级（冗余存储，方便查询） |

#### Entity: Recipe（工艺路线模板）

| 字段 | 类型 | 说明 |
|------|------|------|
| recipe_id | PK, string | 唯一标识 |
| recipe_code | string | 编码，如 R-CAST-01 |
| name | string | 名称，如"低压铸造" |
| description | text | 描述 |
| applicable_part_numbers | array | 适用的 Part Number 列表 |
| applicable_quantity_min | int | 最小适用批量 |
| applicable_quantity_max | int | 最大适用批量 |
| default_team_id | FK | 默认执行团队 |
| version | string | 版本 |
| status | enum | Active / Inactive |
| estimated_duration_minutes | int | 预估总时长（分钟） |
| setup_time_minutes | int | 换型/准备时间 |
| created_at | datetime | 创建时间 |

#### Entity: RecipeTask（工艺路线任务）

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | PK, string | 唯一标识 |
| recipe_id | FK | 所属 Recipe |
| sequence_no | int | 任务顺序号 |
| task_name | string | 任务名称，如"CNC 铣面" |
| task_type | enum | setup / machining / assembly / inspection / material_move |
| description | text | 详细说明 |
| work_center | string | 具体工作中心（可选） |
| standard_time_minutes | int | 标准工时（分钟/件） |
| required_skill | string | 所需技能等级 |
| inspection_type | enum | self / mutual / qc / none |

#### Entity: JobRecipe（Job 中的 Recipe 选择记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| job_recipe_id | PK, string | 唯一标识 |
| job_id | FK | 所属 Job |
| job_node_id | FK | 应用的 JobBOMNode |
| recipe_id | FK | 选用的 Recipe |
| selected_by | string | 选择人 |
| selected_at | datetime | 选择时间 |
| notes | text | 备注 |

#### Entity: Process（排程单元）

| 字段 | 类型 | 说明 |
|------|------|------|
| process_id | PK, string | 唯一标识 |
| process_code | string | 编码，如 P-CAST-01 |
| job_id | FK | 所属 Job |
| team_id | FK | 执行团队 |
| process_name | string | 名称 |
| process_type | enum | internal / outsource / inspection |
| status | enum | pending / ready / scheduled / released / in_progress / completed / cancelled |
| sequence_no | int | 在 Job 内的排序 |
| scheduled_start | datetime | 计划开始 |
| scheduled_end | datetime | 计划结束 |
| actual_start | datetime | 实际开始 |
| actual_end | datetime | 实际结束 |
| priority_score | float | 优先级得分（排程引擎计算） |
| notes | text | 备注 |
| created_at | datetime | 创建时间 |

#### Entity: ProcessTask（Process 内任务实例）

| 字段 | 类型 | 说明 |
|------|------|------|
| process_task_id | PK, string | 唯一标识 |
| process_id | FK | 所属 Process |
| recipe_task_id | FK | 来源的 RecipeTask |
| job_node_id | FK | 关联的 JobBOMNode |
| sequence_no | int | 在 Process 内的顺序 |
| task_name | string | 任务名称 |
| planned_start | datetime | 计划开始 |
| planned_end | datetime | 计划结束 |
| actual_start | datetime | 实际开始 |
| actual_end | datetime | 实际结束 |
| status | enum | pending / in_progress / completed / skipped |
| operator_id | string | 操作员 |

#### Entity: ProcessDependency（Process 依赖关系）

| 字段 | 类型 | 说明 |
|------|------|------|
| dependency_id | PK, string | 唯一标识 |
| job_id | FK | 所属 Job |
| predecessor_process_id | FK | 前置 Process |
| successor_process_id | FK | 后置 Process |
| dependency_type | enum | finish_to_start / start_to_start / finish_to_finish |
| dependency_source | enum | system_generated（系统生成）/ manual（手动添加） |
| lead_lag_minutes | int | 提前/延后时间（可为负数） |

#### Entity: Team（执行团队/工作中心）

| 字段 | 类型 | 说明 |
|------|------|------|
| team_id | PK, string | 唯一标识 |
| team_code | string | 编码 |
| team_name | string | 名称，如"铸造车间" |
| team_type | enum | workshop / production_line / work_center / supplier |
| parent_team_id | FK | 上级团队（层级结构） |
| capacity_per_day | int | 日产能（单位视业务而定） |
| shift_count | int | 班次数量 |
| location | string | 物理位置 |
| is_active | boolean | 是否启用 |

#### Entity: Signal（信号/事件）

| 字段 | 类型 | 说明 |
|------|------|------|
| signal_id | PK, string | 唯一标识 |
| signal_type | enum | material_received / quality_passed / equipment_ready / manual_trigger |
| job_id | FK | 关联 Job |
| process_id | FK | 关联 Process（可选） |
| ref_document | string | 关联单据号，如收货单号 |
| triggered_by | string | 触发人/系统 |
| triggered_at | datetime | 触发时间 |
| processed | boolean | 是否已被排程引擎消费 |

#### Entity: PartNumber（物料编码主数据）

| 字段 | 类型 | 说明 |
|------|------|------|
| part_number | PK, string | 物料编码 |
| part_name | string | 物料名称 |
| part_category | enum | raw_material / semi_finished / finished_good / purchased_part |
| default_uom | string | 默认单位 |
| drawing_revision | string | 图纸版本 |
| is_active | boolean | 是否启用 |

---

## 5. ER 逻辑图

### 5.1 核心实体关系图（文字描述）

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              核心实体关系图                                        │
└─────────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
  │  PartNumber  │◄────────┤    BOM       ├────────►│   BOMNode    │
  │  (物料主数据)  │  1:N    │  (物料清单模板) │  1:N   │  (BOM节点)    │
  └──────────────┘         └──────┬───────┘         └──────┬───────┘
         ▲                        │                        │
         │                        │                        │ N:1(parent)
         │                   ┌────┴────┐                   │
         │                   │  Job    │◄──────────────────┘
         │                   │(作业/工单)│         1:N
         │                   └────┬────┘
         │                        │
    ┌────┴────┐                   │                    ┌──────────────┐
    │  Team   │◄──────────────────┤                    │   Recipe     │
    │(执行团队) │              N:1 │                    │ (工艺路线模板)  │
    └────┬────┘                    │                    └──────┬───────┘
         ▲                        │                           │
         │                   ┌────┴────┐                      │ 1:N
         │                   │ Process │◄─────────────────────┘
         └───────────────────┤(排程单元)│         N:M (via JobRecipe)
                         N:1 └────┬────┘
                                  │
                            ┌─────┴──────┐
                            │ProcessTask │
                            │(排程任务实例) │
                            └────────────┘
```

### 5.2 完整实体关系详述

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

BOM (1) ───< (N) Recipe
  - 一个 BOM 的多个节点可以关联多个 Recipe
  - Recipe 通过 applicable_part_numbers 字段与 PartNumber 关联

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

### 5.3 关键关系约束

| 关系 | 基数 | 约束 |
|------|------|------|
| Job → JobBOMNode | 1:N | 级联创建，Job 删除时级联删除 |
| JobBOMNode → Recipe | N:1 | 可选，叶子节点可为空 |
| Job → Process | 1:N | 级联创建，Process 由系统生成 |
| Process → Team | N:1 | 必填 |
| Process → Process (依赖) | N:M | 通过 ProcessDependency，必须构成 DAG（无环） |
| BOMNode → Recipe | N:M | 通过 applicable_part_numbers 间接关联 |

---

## 6. 状态流转

### 6.1 Job 状态机

```
                    ┌─────────────┐
                    │   DRAFT     │  草稿
                    │  （刚创建）   │
                    └──────┬──────┘
                           │ 用户点击"选择 BOM"
                           ▼
                    ┌─────────────┐
                    │ BOM_SELECT  │  BOM 选择中
                    │  （展开 BOM树）│
                    └──────┬──────┘
                           │ 用户确认 BOM
                           ▼
                    ┌─────────────┐
                    │  RECIPE_CFG │  Recipe 配置中
                    │  （倒序配置）  │
                    └──────┬──────┘
                           │ 所有中间节点已配置 Recipe
                           ▼
                    ┌─────────────┐
                    │  READY      │  待排程
                    │（可参与排程）  │
                    └──────┬──────┘
                           │ 排程引擎运行
                           ▼
                    ┌─────────────┐
                    │  SCHEDULED  │  已排程
                    │（排程完成）   │
                    └──────┬──────┘
                           │ 释放到车间执行
                           ▼
                    ┌─────────────┐
                    │  RELEASED   │  已释放
                    │（已下发工单）  │
                    └──────┬──────┘
                           │ 第一个 Process 开始
                           ▼
              ┌──────────────────────────┐
              │       IN_PROGRESS        │  执行中
              │    （至少一个 Process     │
              │        已开始执行）         │
              └────────────┬─────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
      ┌──────────┐  ┌──────────┐  ┌──────────┐
      │ ON_HOLD  │  │  PARTIAL │  │COMPLETED │  完成
      │ （暂停）  │  │ （部分完成）│  │（全部完成） │
      └────┬─────┘  └────┬─────┘  └──────────┘
           │             │
           └──────┬──────┘
                  │ 恢复
                  ▼
           ┌──────────┐
           │IN_PROGRESS│
           └──────────┘

特殊转换：
- 任何状态 → CANCELLED（取消）：管理员权限，已释放后不可直接取消
- READY → SCHEDULED：系统自动（排程引擎定时任务）
- SCHEDULED → READY：手动取消排程（修改后重新排程）
```

### 6.2 Process 状态机

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

### 6.3 Recipe 配置状态（JobBOMNode 级别）

```
┌─────────┐         ┌───────────┐         ┌──────────┐
│ PENDING │────────►│CONFIGURED │────────►│ SKIPPED  │
│（待配置） │         │（已配置）   │         │（跳过）   │
│  🔵 圆圈  │         │           │         │          │
└─────────┘         └───────────┘         └──────────┘
        ▲                                          │
        └──────────────────────────────────────────┘
                      可取消配置，回到待配置状态
```

---

## 7. Process 生成算法描述

### 7.1 算法概述

Process 生成是连接"BOM + Recipe 配置"与"排程引擎"的关键桥梁。核心思想是：

> **将 BOM 树中由同一 team 负责的、具有连续依赖关系的节点集合，合并为一个排程单元（Process）。**

### 7.2 算法输入

| 输入 | 说明 |
|------|------|
| Job ID | 当前 Job |
| JobBOMNode 树 | 完整展开并配置了 Recipe 的 BOM 实例树 |
| Team 映射 | 每个 JobBOMNode → 其 Recipe 对应的 team |

### 7.3 算法步骤

```
步骤 1：构建 Team-Annotated BOM Tree
─────────────────────────────────────
遍历 JobBOMNode 树，为每个节点标注 team_id。
  - 叶子节点：无 team（不生成 Process）
  - 中间节点：从选定的 Recipe 获取 default_team_id

步骤 2：自底向上识别"Team 连续区间"
─────────────────────────────────────
从叶子节点向上遍历：

  对于每个中间节点 N：
    a) 获取 N 的 team_id = T_N
    b) 获取 N 的所有子节点的 team_id 集合 = {T_child1, T_child2, ...}
    
    c) 判断：是否存在子节点 team 与 T_N 相同？
       
       如果 YES（至少一个子节点的 team = T_N）：
          → N 与该子节点属于同一个 Process，合并
       
       如果 NO（所有子节点的 team ≠ T_N）：
          → N 需要开启一个新的 Process（或加入父节点的 Process，见步骤 3）

步骤 3：向上聚合（Group）
────────────────────────
对于步骤 2 中标记为"新 Process"的节点 N：

  a) 向上检查父节点 P：
     如果 P.team_id == N.team_id：
        → N 加入 P 所在的 Process
     
  b) 如果父节点 team 不同：
     → 检查同级兄弟节点：
        如果存在兄弟节点 S，S.team_id == N.team_id 且 S 也是"新 Process"：
          → N 和 S 合并为同一个 Process
        
  c) 如果都无法合并：
     → N 创建独立的新 Process

步骤 4：建立 Process 间依赖关系
───────────────────────────────
遍历 Process 集合，分析跨 Process 的依赖：

  对于每个 Process Pi：
    a) 获取 Pi 包含的所有 JobBOMNode 节点集合
    b) 对于 Pi 中的每个节点 N：
       - 找到 N 在 BOM 树中的父节点 P
       - 找到 P 所在的 Process Pp
       - 如果 Pp ≠ Pi：
         → 创建依赖：Pp 是 Pi 的前置 Process（finish_to_start）
       
    c) 对于 Pi 中的每个节点 N：
       - 找到 N 在 BOM 树中的所有子节点 {C1, C2, ...}
       - 找到每个子节点 Ci 所在的 Process Pci
       - 如果 Pci ≠ Pi：
         → 创建依赖：Pi 是 Pci 的前置 Process（finish_to_start）

步骤 5：依赖图校验
─────────────────
检查生成的 Process 依赖图是否构成 DAG（有向无环图）：
  - 如果存在环，报错（说明 Recipe 配置有逻辑错误）
  - 拓扑排序，验证可达性

步骤 6：Process 内 Task 展开
───────────────────────────
对于每个 Process：
  a) 收集该 Process 包含的所有 JobBOMNode
  b) 按 BOM 层级（从深到浅）排序节点
  c) 对每个节点，展开其 Recipe 的 RecipeTask 列表
  d) 按 sequence_no 拼接为 ProcessTask 序列
  e) 标记前置/后置 Process 关系

步骤 7：持久化
─────────────
将生成的 Process、ProcessTask、ProcessDependency 写入数据库。
```

### 7.4 算法伪代码

```python
def generate_processes(job_id: str) -> List[Process]:
    # 步骤 1: 获取已配置 Recipe 的 JobBOMNode 树
    job_nodes = get_configured_job_bom_nodes(job_id)
    
    # 步骤 2: 自底向上标记 team 连续区间
    team_groups = {}  # team_id -> List[node_group]
    
    for node in sorted(job_nodes, key=lambda n: -n.level):  # 从深到浅
        team_id = node.selected_recipe.team_id
        
        # 检查子节点是否同 team
        children = get_children(node)
        same_team_children = [c for c in children if c.team_id == team_id]
        
        if same_team_children:
            # 合并到子节点的 Process 中
            target_process = find_process_containing_nodes(same_team_children)
            add_node_to_process(node, target_process)
        else:
            # 标记为待分配
            node.pending_process = True
    
    # 步骤 3: 向上聚合
    for node in sorted(job_nodes, key=lambda n: -n.level):
        if node.pending_process:
            team_id = node.selected_recipe.team_id
            parent = get_parent(node)
            
            if parent and parent.team_id == team_id and parent.process:
                add_node_to_process(node, parent.process)
            else:
                # 创建新 Process
                process = create_new_process(job_id, team_id)
                add_node_to_process(node, process)
    
    # 步骤 4: 建立依赖关系
    processes = get_all_processes_for_job(job_id)
    for proc in processes:
        for node in proc.nodes:
            # 检查父子依赖
            parent = get_parent(node)
            if parent and parent.process and parent.process != proc:
                create_dependency(parent.process, proc, "finish_to_start")
            
            for child in get_children(node):
                if child.process and child.process != proc:
                    create_dependency(proc, child.process, "finish_to_start")
    
    # 步骤 5: 校验 DAG
    if not is_dag(processes):
        raise ProcessGenerationError("依赖关系存在循环，请检查 Recipe 配置")
    
    # 步骤 6: 展开 Task
    for proc in processes:
        expand_process_tasks(proc)
    
    return processes
```

### 7.5 合并规则详细说明

| 场景 | 判定 | 结果 |
|------|------|------|
| 父节点与子节点 team 相同 | 连续区间 | 合并为同一 Process |
| 父节点与子节点 team 不同 | 区间断裂 | 分别属于不同 Process |
| 同一 team 的多个兄弟节点，中间无其他 team | 可合并 | 合并为同一 Process |
| 同一 team 的多个节点，被其他 team 工序隔开 | 不可合并 | 分为多个 Process |
| 叶子节点 | 无需配置 Recipe | 不生成独立 Process，作为父节点的输入物料 |

### 7.6 示例验证

以 3.5 节的发动机 Job 为例验证算法：

**铸造车间 Team：**
- 缸体铸造毛坯、主轴承盖、缸盖铸造毛坯 → 连续分支 → **P-CAST-01**
- 曲轴毛坯、凸轮轴毛坯 → 另一分支，与上面被"机加"隔开 → **P-CAST-02**
- 歧管铸钢件 → 属于精密铸造（不同 team）→ **P-CAST-03**（独立）

**机加车间 Team：**
- 缸体机加工件、活塞销 → 同分支 → **P-MC-01**
- 曲轴、飞轮 → 另一分支 → **P-MC-02**
- 缸盖机加工件、凸轮轴 → 又一分支 → **P-MC-03**

---

## 8. UI 页面结构与交互状态定义

### 8.1 整体页面布局

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  顶部导航栏：Job 拆分排产系统                    [用户] [设置] [帮助]         │
├──────────┬──────────────────────────────────────────────────────────────────┤
│          │                                                                    │
│  左侧     │  右侧主内容区（根据当前步骤切换）                                    │
│  导航     │                                                                    │
│  面板     │  ┌──────────────────────────────────────────────────────────────┐  │
│          │  │                    步骤指示器                                  │  │
│  ┌──────┐│  │  [Step 1]        [Step 2]        [Step 3]        [Step 4]    │  │
│  │ Job  ││  │  创建 Job   →   选择 BOM   →   配置 Recipe  →   预览 & 排程   │  │
│  │ 列表 ││  │   ●              ○              ○              ○              │  │
│  ├──────┤│  └──────────────────────────────────────────────────────────────┘  │
│  │ 新建 ││                                                                    │
│  │ Job  ││  ════════════════════════════════════════════════════════════════   │
│  ├──────┤│                                                                    │
│  │      ││  【Step 1 内容】/【Step 2 内容】/【Step 3 内容】/【Step 4 内容】    │
│  │ 最近 ││                                                                    │
│  │ 访问 ││                                                                    │
│  │      ││                                                                    │
│  └──────┘│                                                                    │
│          │                                                                    │
├──────────┴────────────────────────────────────────────────────────────────────┤
│  底部状态栏：当前状态 / 最后保存时间 / 操作提示                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Step 1：创建 Job

**页面结构：**

```
┌──────────────────────────────────────────────────────────────┐
│ Step 1: 创建新 Job                                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  基础信息（必填）                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 产品型号 (Part Number)  [ 输入 / 下拉选择      ] *   │   │
│  │                                                       │   │
│  │ 生产数量               [ 输入数量               ] *   │   │
│  │                       件                             │   │
│  │                                                       │   │
│  │ 生产模式：                                            │   │
│  │  ○ 全部 Make to Stock                                │   │
│  │  ○ 全部 Make to Order                                │   │
│  │  ● 混合模式                                          │   │
│  │    ├─ MTS 数量: [    20   ] 件                       │   │
│  │    └─ MTO 数量: [    80   ] 件                       │   │
│  │                                                       │   │
│  │ 优先级                 [ ● High  ○ Normal  ○ Low ]   │   │
│  │                                                       │   │
│  │ 目标交期               [ 日期选择器              ]    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  扩展信息（可选）                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 客户订单号             [ 输入                       ] │   │
│  │ 备注                   [ 多行文本输入              ] │   │
│  │ 关联图纸               [ 上传附件按钮              ] │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│                                   [ 取消 ]  [ 保存草稿 ] [ 下一步 ]│
└──────────────────────────────────────────────────────────────┘
```

**字段校验规则：**

| 字段 | 校验规则 |
|------|---------|
| Part Number | 必填，必须在 PartNumber 主数据中存在 |
| 生产数量 | 必填，整数，> 0，≤ 999999 |
| MTS + MTO | 必须等于生产数量 |
| 优先级 | 必填，默认 Normal |
| 目标交期 | 必填，必须 >= 今天 + 1 天 |

**交互：**
- 填写完成后点击"下一步" → Job 状态变为 DRAFT → 进入 Step 2
- 点击"保存草稿" → 保存但不进入下一步，留在当前页
- Part Number 选择后，系统自动查询可用的 BOM 版本

### 8.3 Step 2：选择 BOM

**页面结构：**

```
┌──────────────────────────────────────────────────────────────┐
│ Step 2: 选择 BOM                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  BOM 版本选择                                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 可用 BOM 版本：                                       │   │
│  │  ● BOM v2.3 (Active, 2024-06-15)                      │   │
│  │  ○ BOM v2.2 (Obsolete, 2024-03-01)                    │   │
│  │  ○ BOM v3.0 (Draft, 2024-08-01)                       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  BOM 树预览                                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                                                       │   │
│  │  ▼ ENG-D250 柴油发动机总成                             │   │
│  │    ├─ ▼ 缸体组件模块                                  │   │
│  │    │    ├─ ▼ 缸体机加工件                              │   │
│  │    │    │    ├─ ▼ 缸体铸造毛坯                         │   │
│  │    │    │    │    └─ ⬜ 铝合金锭 AL-Si10Cu             │   │
│  │    │    │    └─ ⬜ 缸体螺栓套件                        │   │
│  │    │    ├─ ▼ 活塞组                                   │   │
│  │    │    │    ├─ ▼ 活塞                                │   │
│  │    │    │    │    └─ ⬜ 铝合金棒料 AL-4032             │   │
│  │    │    │    ...                                      │   │
│  │    │    ...                                           │   │
│  │    ...                                                  │   │
│  │                                                       │   │
│  │  图例: 🔵 需要配置 Recipe (18)   ⬜ 叶子节点 (17)      │   │
│  │        总计: 35 节点    最大深度: 5 层                  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  BOM 统计摘要                                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  中间节点: 18  │  叶子节点: 17  │  总数量: 35          │   │
│  │  需配置 Recipe 的节点: 18                            │   │
│  │  预估涉及 Team: 铸造、锻造、机加、装配、总装、注塑      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  [ 上一步 ]                          [ 确认 BOM 并继续 ]    │
└──────────────────────────────────────────────────────────────┘
```

**BOM 树渲染规则：**

| 元素 | 样式 | 说明 |
|------|------|------|
| 中间节点（需配置 Recipe） | 🔵 蓝色圆圈图标 + 节点名称 | 可展开/折叠 |
| 叶子节点 | ⬜ 灰色方块图标 + 节点名称 | 不可展开 |
| 已选中/当前节点 | 高亮背景色 | 交互反馈 |
| 展开图标 | ▼（已展开）/ ▶（已折叠） | 点击切换 |

**交互：**
- 点击节点可展开/折叠子树
- 选择 BOM 版本后，树重新加载
- 点击"确认 BOM 并继续" → 系统展开 BOM 生成 JobBOMNode → 状态变为 BOM_SELECTED → 进入 Step 3

### 8.4 Step 3：配置 Recipe（核心交互）

**页面结构：**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 3: 配置 Recipe                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  配置指引: 从叶子节点向根节点倒序配置，请按右侧列表顺序逐一完成                    │
│                                                                              │
│  ┌─────────────────────────────┐  ┌─────────────────────────────────────────┐│
│  │   BOM 树（左侧面板）          │  │   Recipe 配置区（右侧面板）               ││
│  │                             │  │                                         ││
│  │   ▼ ENG-D250 发动机总成       │  │   ┌─────────────────────────────────┐  ││
│  │    ├─ ▼ 缸体组件模块          │  │   │ 当前配置节点                      │  ││
│  │    │    ├─ ▼ 缸体机加工件      │  │   │                                 │  ││
│  │    │    │    ├─ 🔵 缸体铸造毛坯 ◄├────┤ 缸体铸造毛坯                    │  ││
│  │    │    │    │    └─ ⬜ ...    │  │   │ Part: PM-CAST-BLOCK-001        │  ││
│  │    │    │    └─ ⬜ 螺栓套件    │  │   │ 材质: AL-Si10Cu                │  ││
│  │    │    ├─ ▼ 活塞组           │  │   │ 批量: 100                      │  ││
│  │    │    │    ├─ 🔵 活塞       │  │   │                                 │  ││
│  │    │    │    │    └─ ⬜ ...   │  │   │ 【可选 Recipe】                  │  ││
│  │    │    │    ├─ 🔵 活塞销     │  │   │ ┌─────────────────────────────┐ │  ││
│  │    │    │    └─ ⬜ 活塞环     │  │   │ │ ● R-CAST-01 低压铸造        │ │  ││
│  │    │    └─ 🔵 连杆组          │  │   │ │   Team: 铸造车间             │ │  ││
│  │    │         ├─ 🔵 连杆体     │  │   │ │   Tasks: 6 道               │ │  ││
│  │    │         └─ ⬜ 连杆轴承   │  │   │ │   预估: 480 分钟             │ │  ││
│  │    ...                        │  │   │ │   [查看详情]                 │ │  ││
│  │                             │  │   │ └─────────────────────────────┘ │  ││
│  │   图例: 🔵 待配置 ⬜ 叶子    │  │   │ ┌─────────────────────────────┐ │  ││
│  │   🔵✓ 已配置  🔵◐ 当前     │  │   │ │ ○ R-CAST-02 重力铸造        │ │  ││
│  │                             │  │   │ │   Team: 铸造车间             │ │  ││
│  │                             │  │   │ │   Tasks: 5 道               │ │  ││
│  │                             │  │   │ │   预估: 360 分钟             │ │  ││
│  │                             │  │   │ └─────────────────────────────┘ │  ││
│  │                             │  │   │                                 │  ││
│  │                             │  │   │ [确认选择]  [跳过]  [自定义修改]   │  ││
│  │                             │  │   └─────────────────────────────────┘  ││
│  │                             │  │                                         ││
│  │                             │  │   ┌─────────────────────────────────┐  ││
│  │                             │  │   │ 配置进度                        │  ││
│  │                             │  │   │ ████████░░░░░░░░░░  8/18 完成   │  ││
│  │                             │  │   │ 下一个: 主轴承盖                 │  ││
│  │                             │  │   └─────────────────────────────────┘  ││
│  └─────────────────────────────┘  └─────────────────────────────────────────┘│
│                                                                              │
│  [ 上一步 ]                               [ 保存进度 ] [ 完成配置，去预览 ]    │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Recipe 配置流程：**

```
用户进入 Step 3 时：
  │
  ▼
系统自动按"从深到浅"排序待配置节点列表
  │
  ▼
默认选中第一个待配置节点（最深的中间节点）
  │
  ▼
左侧面板高亮当前节点，右侧显示该节点的 Recipe 列表
  │
  ▼
用户浏览 Recipe 详情（点击"查看详情"展开 Tasks 列表）
  │
  ▼
用户选择一个 Recipe → 点击"确认选择"
  │
  ▼
系统标记该节点为"已配置"，左侧图标变为 🔵✓
  │
  ▼
自动切换到下一个待配置节点
  │
  ▼
... 循环直到所有 18 个节点配置完成
  │
  ▼
"完成配置"按钮变为可用状态
```

**节点图标状态：**

| 状态 | 图标 | 说明 |
|------|------|------|
| 待配置 | 🔵 | 蓝色空心圆，等待用户配置 |
| 当前选中 | 🔵◐ | 蓝色圆 + 高亮边框 |
| 已配置 | 🔵✓ | 蓝色圆 + 对勾 |
| 叶子节点 | ⬜ | 灰色方块，无需配置 |
| 跳过 | 🔵⊘ | 蓝色圆 + 禁止符号（特殊场景） |

**Recipe 详情展开：**

```
点击"查看详情"后展开：
┌─────────────────────────────────────┐
│ R-CAST-01 低压铸造                    │
│ Team: 铸造车间  |  预估: 480 分钟     │
│                                     │
│ 任务列表:                            │
│  1. 模具准备      30 min   setup     │
│  2. 熔炼         120 min  machining  │
│  3. 低压浇注      90 min  machining  │
│  4. 冷却固化      60 min  machining  │
│  5. 脱模清理      45 min  machining  │
│  6. 尺寸初检      30 min  inspection │
│                                     │
│ 适用条件: 批量 ≥ 50                   │
│ 设备要求: 低压铸造机 500T             │
│ 技能要求: 铸造高级技工               │
└─────────────────────────────────────┘
```

**交互规则：**
- 用户必须配置完所有中间节点才能进入下一步
- 提供"保存进度"功能，可保存当前配置状态，下次继续
- 已配置的节点可以重新打开修改
- 修改某个节点的 Recipe 后，依赖该节点的后续配置可能需要重新校验

### 8.5 Step 4：总 Recipe 预览与排程

**页面结构：**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 4: 总 Recipe 预览 & 排程                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  模式切换: [ 树形视图 ] [ 列表视图 ] [ Process 视图 ] [ 甘特图 ]        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ═══════════════════ 树形视图 ═══════════════════                            │
│                                                                              │
│  ▼ ENG-D250 柴油发动机总成                                                  │
│  │  Recipe: R-FINAL-01 (总装车间)  [查看详情 ▼]                             │
│  │  Tasks: 缸体曲轴合装→装缸盖→装进排气系统→...→终检→入库 (10 tasks)        │
│  │                                                                         │
│  ├─ ▼ 缸体组件模块                                                          │
│  │  │  Recipe: R-ASSY-04 (装配车间)  [查看详情 ▼]                           │
│  │  │  Tasks: 装活塞连杆→入缸体→装轴承盖→扭矩检验 (4 tasks)                  │
│  │  │                                                                       │
│  │  ├─ ▼ 缸体机加工件                                                        │
│  │  │  │  Recipe: R-MC-01 (机加车间)  [查看详情 ▼]                          │
│  │  │  │  Tasks: CNC铣面→钻孔→镗缸→精铣 (4 tasks)                          │
│  │  │  │                                                                     │
│  │  │  └─ ▼ 缸体铸造毛坯                                                      │
│  │  │     │  Recipe: R-CAST-01 (铸造车间) [查看详情 ▼]                       │
│  │  │     │  Tasks: 模具准备→熔炼→浇注→冷却→脱模→初检 (6 tasks)               │
│  │  │     └─ ⬜ 铝合金锭 AL-Si10Cu  (采购件，无需配置)                        │
│  │  │                                                                        │
│  │  ... (其他分支展开结构类似)                                                │
│  │                                                                            │
│  ═══════════════════ Process 汇总 ═══════════════════                         │
│                                                                              │
│  系统将生成 15 个 Process，涉及 6 个 Team：                                    │
│                                                                              │
│  ┌──────────┬──────────────┬────────┬─────────────────┬────────────────────┐ │
│  │ Process  │    Team      │ 节点数 │    预估时长      │     前置依赖        │ │
│  ├──────────┼──────────────┼────────┼─────────────────┼────────────────────┤ │
│  │ P-CAST-01│  铸造车间     │   3    │    14 天        │        无          │ │
│  │ P-CAST-02│  铸造车间     │   2    │    10 天        │        无          │ │
│  │ P-CAST-03│  精密铸造车间 │   1    │    12 天        │        无          │ │
│  │ P-FORGE-1│  锻造车间     │   2    │     8 天        │        无          │ │
│  │ P-FORGE-2│  锻造车间     │   2    │     6 天        │        无          │
│  │ P-MC-01  │  机加车间     │   2    │    12 天        │  P-CAST-01         │ │
│  │ P-MC-02  │  机加车间     │   2    │    15 天        │  P-CAST-02         │ │
│  │ ...      │  ...         │  ...   │   ...           │  ...               │ │
│  │ P-FINAL  │  总装车间     │   1    │     5 天        │  全部前置完成       │ │
│  └──────────┴──────────────┴────────┴─────────────────┴────────────────────┘ │
│                                                                              │
│  ═══════════════════ 操作区 ═══════════════════                               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  [ 返回修改 Recipe ]  [ 生成 Process ]  [ 执行排程 ▶ ]              │    │
│  │                                                                     │    │
│  │  执行排程选项:                                                       │    │
│  │  ○ 立即排程（ ASAP ）                                                │    │
│  │  ● 基于目标交期倒排（Target: 2024-08-30）                            │    │
│  │  ○ 有限产能排程（考虑设备负荷）                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**排程执行流程：**

```
用户点击"生成 Process"：
  │
  ▼
系统调用 Process 生成算法（第 7 节）
  │
  ▼
生成 15 个 Process + ProcessTask + ProcessDependency
  │
  ▼
Job 状态变为 READY → 展示 Process 汇总表
  │
  ▼
用户点击"执行排程"：
  │
  ▼
系统调用排程引擎：
  - 输入：Process 图 + Team 产能 + 优先级 + Signal
  - 输出：每个 Process 的 scheduled_start / scheduled_end
  │
  ▼
Job 状态变为 SCHEDULED → 展示甘特图
  │
  ▼
用户可点击"释放到车间" → Job 状态变为 RELEASED
```

### 8.6 UI 状态与后端状态映射

| UI 步骤 | 前端状态 | 后端 Job Status | 说明 |
|---------|---------|----------------|------|
| 刚进入创建页 | `creating` | - | 未创建 Job |
| 填写基本信息 | `editing_basic` | DRAFT | Job 已创建，信息编辑中 |
| Step 2 BOM 选择 | `selecting_bom` | DRAFT | 选择 BOM 版本 |
| BOM 确认后 | `bom_confirmed` | BOM_SELECTED | BOM 已展开为 JobBOMNode |
| Step 3 Recipe 配置 | `configuring_recipe` | RECIPE_CFG | Recipe 配置进行中 |
| 配置全部完成 | `recipe_configured` | RECIPE_CFG | 等待用户确认 |
| 进入 Step 4 | `previewing` | RECIPE_CFG | 预览模式 |
| 生成 Process | `generating_process` | READY | Process 已生成 |
| 执行排程 | `scheduling` | READY → SCHEDULED | 排程引擎运行 |
| 排程完成 | `scheduled` | SCHEDULED | 排程完成，展示甘特图 |
| 释放到车间 | `releasing` | RELEASED | 工单下发 |

### 8.7 错误处理与边界情况

| 场景 | 处理方式 |
|------|---------|
| Part Number 无可用 BOM | 提示用户："该产品型号没有可用的 BOM，请先维护 BOM 数据" |
| BOM 展开后无中间节点（全是叶子） | 提示："该 BOM 全部为采购件，无需 Recipe 配置，可直接排程" |
| 某个节点无匹配的 Recipe | 高亮该节点，提示："该节点无匹配的 Recipe，请维护工艺数据" |
| Recipe 配置过程中断（浏览器关闭） | 自动保存当前进度到服务端，下次打开恢复 |
| 排程引擎无可用产能 | 提示："XX 团队产能不足，请调整交期或增加产能" |
| Process 依赖图存在环 | 报错："工艺配置存在循环依赖，请检查以下节点..." |
| 用户修改已排程的 Recipe | 提示："修改 Recipe 将导致重新排程，是否继续？" |

---

## 附录 A：术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| 作业/工单 | Job | 参与排产的最顶层单元，一份生产指令 |
| 物料清单 | BOM | Bill of Materials，产品的结构化物料定义 |
| 工艺路线 | Recipe | 某零部件的加工方案，包含 team 和 tasks |
| 工序/排产单元 | Process | 排程的最小单元，由同一 team 的 BOM 分支 group 而成 |
| 任务 | Task | Recipe 内的具体操作步骤 |
| 团队 | Team | 负责执行工艺的班组/车间/工作中心 |
| 信号 | Signal | 触发排程或状态变更的外部事件 |
| 面向库存生产 | MTS | Make to Stock，为库存而生产 |
| 面向订单生产 | MTO | Make to Order，为客户订单而生产 |
| 关键路径 | Critical Path | 决定 Job 总工期的最长 Process 链 |

## 附录 B：数据量估算

以典型发动机 Job 为例：

| 数据项 | 数量级 | 说明 |
|--------|--------|------|
| BOM 节点数 | 30~100 | 取决于产品复杂度 |
| 中间节点（需配 Recipe） | 15~50 | 约占总节点 50% |
| Recipe 数/节点 | 2~5 | 可选工艺方案 |
| 生成 Process 数 | 10~30 | 取决于 team 数量和 BOM 结构 |
| Process 依赖关系 | 20~60 | 形成 DAG |
| Task 总数（展开后） | 50~200 | 所有 ProcessTask 之和 |

---

> **文档结束**  
> 本文档为 Job 拆分排产系统的核心业务概念与信息架构设计，指导后续的数据库设计、接口设计和前端开发。
