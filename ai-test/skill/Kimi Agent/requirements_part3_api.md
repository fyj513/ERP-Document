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
