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
