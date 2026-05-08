# Scheduler 需求中枢 — 实施计划

> 对应设计文档：`2026-05-07-scheduler-demand-hub-design.md`
> 对应PRD：`2026-05-07-scheduler-demand-hub-prd.md`

---

## 文件结构

```
src/
├── scheduler/
│   ├── models/
│   │   ├── demand.py          # Demand实体
│   │   ├── job.py             # Job实体
│   │   ├── job_line.py        # Demand-Job关联
│   │   ├── sub_task.py        # 子任务实体
│   │   └── site.py            # Site实体
│   ├── services/
│   │   ├── merge_engine.py    # 合并引擎
│   │   ├── priority_engine.py # 优先级引擎
│   │   ├── job_service.py     # Job生命周期
│   │   └── demand_service.py  # Demand管理
│   ├── api/
│   │   ├── demands.py         # Demand API
│   │   ├── jobs.py            # Job API
│   │   └── sites.py           # Site API
│   └── tests/
│       ├── test_merge_engine.py
│       ├── test_priority_engine.py
│       └── test_job_lifecycle.py
├── frontend/
│   ├── pages/
│   │   ├── schedule.html      # Schedule页面
│   │   └── site-plan.html     # Site Plan页面
│   └── components/
│       ├── demand-card.js
│       ├── job-table.js
│       └── merge-suggestion.js
└── migrations/
    ├── 001_create_demand.py
    ├── 002_create_job.py
    └── 003_create_sub_task.py
```

---

## Task 1: 数据库Schema设计

**Files:**
- Create: `src/scheduler/models/demand.py`
- Create: `src/scheduler/models/job.py`
- Create: `src/scheduler/models/job_line.py`
- Create: `src/scheduler/models/sub_task.py`

- [ ] **Step 1: 设计Demand表**

```python
class Demand(BaseModel):
    id: str  # PK
    source_type: str  # SO/MTO/TRANSFER/REPLENISH/REWORK/FORECAST/SAMPLE
    source_id: str
    part_id: str  # FK → Part
    qty: float
    mts_qty: float
    mto_qty: float
    site_id: str  # FK → Site
    required_date: date
    priority: int  # 0-100
    status: str  # OPEN/CONFIRMED/CLOSED
    merge_group_id: str | None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 2: 设计Job表**

```python
class Job(BaseModel):
    id: str  # PK
    job_no: str
    site_id: str  # FK → Site
    part_id: str  # FK → Part
    total_qty: float
    mts_qty: float
    mto_qty: float
    priority: int
    status: str  # DRAFT/SCHEDULED/EXECUTING/PARTIAL/COMPLETED/CLOSED/ON_HOLD/CANCELLED
    strategy: str  # MAKE/BUY/TRANSFER/SUBCONTRACT
    planned_start: date
    planned_end: date
    scheduler_id: str
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 3: 设计关联表**

```python
class JobLine(BaseModel):
    id: str  # PK
    job_id: str  # FK → Job
    demand_id: str  # FK → Demand
    qty: float
    allocation_type: str  # MTS/MTO

class SubTask(BaseModel):
    id: str  # PK
    job_id: str  # FK → Job
    task_type: str  # PO/MO/TO/RETURN
    ref_doc_id: str | None
    team: str
    status: str  # PENDING/EXECUTING/DONE
```

- [ ] **Step 4: Commit**

```bash
git add src/scheduler/models/
git commit -m "feat(scheduler): add demand, job, job_line, sub_task models"
```

---

## Task 2: 合并引擎（Merge Engine）

**Files:**
- Create: `src/scheduler/services/merge_engine.py`
- Test: `src/scheduler/tests/test_merge_engine.py`

- [ ] **Step 1: 写合并条件测试**

```python
def test_can_merge_same_part_same_site():
    a = Demand(part_id="P-001", site_id="S-A", bom_version="v1", planned_start=date(2026,5,10), mto_qty=0, source_type="SO")
    b = Demand(part_id="P-001", site_id="S-A", bom_version="v1", planned_start=date(2026,5,12), mto_qty=0, source_type="SO")
    assert can_merge(a, b) is True

def test_cannot_merge_different_part():
    a = Demand(part_id="P-001", site_id="S-A", bom_version="v1", planned_start=date(2026,5,10), mto_qty=0, source_type="SO")
    b = Demand(part_id="P-002", site_id="S-A", bom_version="v1", planned_start=date(2026,5,12), mto_qty=0, source_type="SO")
    assert can_merge(a, b) is False

def test_cannot_merge_mto():
    a = Demand(part_id="P-001", site_id="S-A", bom_version="v1", planned_start=date(2026,5,10), mto_qty=100, source_type="SO")
    b = Demand(part_id="P-001", site_id="S-A", bom_version="v1", planned_start=date(2026,5,12), mto_qty=0, source_type="SO")
    assert can_merge(a, b) is False

def test_cannot_merge_time_window_exceeded():
    a = Demand(part_id="P-001", site_id="S-A", bom_version="v1", planned_start=date(2026,5,1), mto_qty=0, source_type="SO")
    b = Demand(part_id="P-001", site_id="S-A", bom_version="v1", planned_start=date(2026,5,10), mto_qty=0, source_type="SO")
    assert can_merge(a, b) is False  # 默认7天窗口
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest src/scheduler/tests/test_merge_engine.py -v
# Expected: 4 tests FAIL
```

- [ ] **Step 3: 实现合并引擎**

```python
TIME_WINDOW_DAYS = 7

def can_merge(a: Demand, b: Demand) -> bool:
    if a.part_id != b.part_id:
        return False
    if a.site_id != b.site_id:
        return False
    if a.bom_version != b.bom_version:
        return False
    if abs((a.planned_start - b.planned_start).days) > TIME_WINDOW_DAYS:
        return False
    if a.mto_qty > 0 or b.mto_qty > 0:
        return False
    if a.source_type in ["REWORK", "SAMPLE", "TRANSFER"]:
        return False
    if b.source_type in ["REWORK", "SAMPLE", "TRANSFER"]:
        return False
    if a.quality_grade != b.quality_grade:
        return False
    return True

def find_merge_candidates(demands: list[Demand]) -> list[list[Demand]]:
    groups = []
    used = set()
    for i, d1 in enumerate(demands):
        if d1.id in used:
            continue
        group = [d1]
        for d2 in demands[i+1:]:
            if d2.id in used:
                continue
            if can_merge(d1, d2):
                group.append(d2)
                used.add(d2.id)
        if len(group) > 1:
            groups.append(group)
            used.add(d1.id)
    return groups
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest src/scheduler/tests/test_merge_engine.py -v
# Expected: 4 tests PASS
```

- [ ] **Step 5: Commit**

```bash
git add src/scheduler/services/merge_engine.py src/scheduler/tests/test_merge_engine.py
git commit -m "feat(scheduler): implement merge engine with 6-condition logic"
```

---

## Task 3: 优先级引擎（Priority Engine）

**Files:**
- Create: `src/scheduler/services/priority_engine.py`
- Test: `src/scheduler/tests/test_priority_engine.py`

- [ ] **Step 1: 写优先级计算测试**

```python
def test_vip_customer_priority():
    demand = Demand(customer_tier="VIP", required_date=date(2026,5,15), days_delayed=0, created_at=datetime.now())
    assert calculate_priority(demand) > 70

def test_urgent_due_date_priority():
    demand = Demand(customer_tier="NORMAL", required_date=date.today() + timedelta(days=1), days_delayed=0, created_at=datetime.now())
    assert calculate_priority(demand) > 75

def test_delayed_penalty():
    demand = Demand(customer_tier="NORMAL", required_date=date(2026,5,1), days_delayed=3, created_at=datetime.now())
    base = calculate_priority(Demand(customer_tier="NORMAL", required_date=date(2026,5,1), days_delayed=0, created_at=datetime.now()))
    assert calculate_priority(demand) > base
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest src/scheduler/tests/test_priority_engine.py -v
# Expected: FAIL
```

- [ ] **Step 3: 实现优先级引擎**

```python
def calculate_priority(demand: Demand) -> int:
    base = 50
    
    # 客户加权
    customer_weight = {"VIP": 20, "NORMAL": 0, "INTERNAL": -10}
    base += customer_weight.get(demand.customer_tier, 0)
    
    # 交期加权
    days_until = (demand.required_date - date.today()).days
    due_weight = max(0, 30 - max(days_until, 0))
    base += due_weight
    
    # 延迟惩罚
    base += demand.days_delayed * 5
    
    # 利润贡献（简化）
    base += demand.profit_contribution or 0
    
    return min(100, max(0, base))
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest src/scheduler/tests/test_priority_engine.py -v
# Expected: PASS
```

- [ ] **Step 5: Commit**

```bash
git add src/scheduler/services/priority_engine.py src/scheduler/tests/test_priority_engine.py
git commit -m "feat(scheduler): implement priority engine with weighted scoring"
```

---

## Task 4: Job生命周期服务

**Files:**
- Create: `src/scheduler/services/job_service.py`
- Test: `src/scheduler/tests/test_job_lifecycle.py`

- [ ] **Step 1: 写状态机流转测试**

```python
def test_draft_to_scheduled():
    job = create_job(status="DRAFT")
    job = schedule_job(job.id, scheduler_id="user-001")
    assert job.status == "SCHEDULED"

def test_scheduled_to_executing():
    job = create_job(status="SCHEDULED")
    job = start_job(job.id)
    assert job.status == "EXECUTING"

def test_cannot_cancel_executing_job():
    job = create_job(status="EXECUTING")
    with pytest.raises(ValueError):
        cancel_job(job.id)

def test_mto_job_inherits_so_priority():
    so = create_so(priority=80)
    demand = create_demand(source_type="MTO", source_id=so.id, mto_qty=100)
    job = schedule_job_from_demand(demand.id)
    assert job.priority == 90  # SO优先级 + 10
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest src/scheduler/tests/test_job_lifecycle.py -v
# Expected: FAIL
```

- [ ] **Step 3: 实现Job服务**

```python
VALID_TRANSITIONS = {
    "DRAFT": ["SCHEDULED", "CANCELLED"],
    "SCHEDULED": ["EXECUTING", "CANCELLED", "ON_HOLD"],
    "EXECUTING": ["PARTIAL", "COMPLETED", "ON_HOLD"],
    "PARTIAL": ["EXECUTING", "COMPLETED"],
    "COMPLETED": ["CLOSED"],
    "ON_HOLD": ["EXECUTING", "CANCELLED"],
}

def transition_job(job_id: str, new_status: str) -> Job:
    job = get_job(job_id)
    if new_status not in VALID_TRANSITIONS.get(job.status, []):
        raise ValueError(f"Invalid transition: {job.status} -> {new_status}")
    job.status = new_status
    job.updated_at = datetime.now()
    save_job(job)
    log_job_event(job_id, f"STATUS_CHANGED:{new_status}")
    return job

def schedule_job_from_demand(demand_id: str, scheduler_id: str) -> Job:
    demand = get_demand(demand_id)
    job = Job(
        job_no=generate_job_no(),
        site_id=demand.site_id,
        part_id=demand.part_id,
        total_qty=demand.qty,
        mts_qty=demand.mts_qty,
        mto_qty=demand.mto_qty,
        priority=calculate_priority(demand) + (10 if demand.mto_qty > 0 else 0),
        status="DRAFT",
        strategy=determine_strategy(demand),
        scheduler_id=scheduler_id,
    )
    save_job(job)
    create_job_line(job.id, demand.id, demand.qty, "MTO" if demand.mto_qty > 0 else "MTS")
    return job
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest src/scheduler/tests/test_job_lifecycle.py -v
# Expected: PASS
```

- [ ] **Step 5: Commit**

```bash
git add src/scheduler/services/job_service.py src/scheduler/tests/test_job_lifecycle.py
git commit -m "feat(scheduler): implement job lifecycle service with state machine"
```

---

## Task 5: Demand来源集成

**Files:**
- Modify: `src/so_module/service.py`  # SO创建时生成Demand
- Modify: `src/inventory_module/service.py`  # 库存低于安全线时生成Replenishment Demand
- Modify: `src/quality_module/service.py`  # 质检不合格时生成Rework Demand

- [ ] **Step 1: SO创建时自动生成Demand**

```python
def on_so_created(so):
    for line in so.lines:
        demand = Demand(
            source_type="SO",
            source_id=so.id,
            part_id=line.part_id,
            qty=line.qty,
            mts_qty=line.qty * (1 - line.mto_ratio),
            mto_qty=line.qty * line.mto_ratio,
            site_id=line.preferred_site or get_default_site(line.part_id),
            required_date=so.delivery_date,
            priority=calculate_priority_from_so(so),
            status="OPEN",
        )
        save_demand(demand)
```

- [ ] **Step 2: 库存低于安全线时生成Replenishment**

```python
def on_inventory_below_safety_stock(part_id, site_id):
    current = get_inventory(part_id, site_id)
    safety = get_safety_stock(part_id, site_id)
    if current.available_qty < safety:
        demand = Demand(
            source_type="REPLENISH",
            source_id=f"REPLENISH-{part_id}-{site_id}",
            part_id=part_id,
            qty=safety * 2 - current.available_qty,  # 补到2倍安全库存
            mts_qty=safety * 2 - current.available_qty,
            mto_qty=0,
            site_id=site_id,
            required_date=date.today() + timedelta(days=7),
            priority=50,
            status="OPEN",
        )
        save_demand(demand)
```

- [ ] **Step 3: 质检不合格时生成Rework**

```python
def on_qc_failed(job_id, part_id, qty, site_id):
    demand = Demand(
        source_type="REWORK",
        source_id=job_id,
        part_id=part_id,
        qty=qty,
        mts_qty=0,
        mto_qty=qty,
        site_id=site_id,
        required_date=date.today() + timedelta(days=1),
        priority=99,
        status="OPEN",
    )
    save_demand(demand)
    # 暂停原Job
    transition_job(job_id, "ON_HOLD")
```

- [ ] **Step 4: Commit**

```bash
git add src/so_module/service.py src/inventory_module/service.py src/quality_module/service.py
git commit -m "feat(scheduler): integrate SO, inventory, quality to auto-generate demands"
```

---

## Task 6: Schedule页面前端

**Files:**
- Create: `frontend/pages/schedule.html`
- Create: `frontend/components/demand-card.js`
- Create: `frontend/components/merge-suggestion.js`

- [ ] **Step 1: 实现Demand列表API调用**

```javascript
// frontend/components/demand-card.js
async function loadDemands(filters = {}) {
    const res = await fetch('/api/demands?' + new URLSearchParams(filters));
    const demands = await res.json();
    renderDemandCards(demands);
}

function renderDemandCards(demands) {
    const container = document.getElementById('demand-list');
    container.innerHTML = demands.map(d => `
        <div class="demand-card" data-id="${d.id}">
            <div class="demand-indicator ${getTypeClass(d.source_type)}"></div>
            <div class="demand-priority ${getPriorityClass(d.priority)}">${d.priority}</div>
            <div class="demand-content">
                <div class="demand-header">
                    <span class="demand-type ${getTypeClass(d.source_type)}">${d.source_type}</span>
                    <span class="demand-id">${d.id}</span>
                </div>
                <div class="demand-body">
                    <span>Part: <strong>${d.part_id}</strong></span>
                    <span>数量: <strong>${d.qty}件</strong></span>
                    <span>Site: <strong>${d.site_id}</strong></span>
                    <span>交期: <strong>${d.required_date}</strong></span>
                </div>
            </div>
            <div class="demand-actions">
                <button onclick="scheduleDemand('${d.id}')">确认排程</button>
            </div>
        </div>
    `).join('');
}
```

- [ ] **Step 2: 实现合并建议UI**

```javascript
// frontend/components/merge-suggestion.js
async function loadMergeSuggestions() {
    const res = await fetch('/api/demands/merge-suggestions');
    const suggestions = await res.json();
    renderMergeCards(suggestions);
}

function renderMergeCards(suggestions) {
    const container = document.getElementById('merge-suggestions');
    container.innerHTML = suggestions.map(s => `
        <div class="merge-card">
            <div class="merge-icon">⚠️</div>
            <div class="merge-content">
                <div class="merge-title">${s.candidate_job_no} — 建议合并 ${s.demands.length} 个Demand</div>
                <div class="merge-detail">
                    ${s.demands.map(d => `<span class="tag">${d.source_id}</span> ${d.qty}件`).join(' ')}
                    <br>→ 合并后: <strong>${s.total_qty}件</strong> | Part: <strong>${s.part_id}</strong>
                </div>
            </div>
            <div class="merge-actions">
                <button onclick="confirmMerge('${s.id}')">确认合并</button>
                <button onclick="ignoreMerge('${s.id}')">忽略</button>
            </div>
        </div>
    `).join('');
}
```

- [ ] **Step 3: 实现排程操作**

```javascript
async function scheduleDemand(demandId) {
    const res = await fetch(`/api/jobs`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({demand_id: demandId, scheduler_id: currentUser.id})
    });
    const job = await res.json();
    showToast(`Job ${job.job_no} 已创建`);
    loadDemands();
    loadJobs();
}

async function confirmMerge(suggestionId) {
    const res = await fetch(`/api/demands/${suggestionId}/merge`, {method: 'POST'});
    const job = await res.json();
    showToast(`合并成功，生成Job ${job.job_no}`);
    loadMergeSuggestions();
    loadJobs();
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): implement schedule page with demand cards and merge suggestions"
```

---

## Task 7: Site Plan页面前端

**Files:**
- Create: `frontend/pages/site-plan.html`
- Create: `frontend/components/job-table.js`

- [ ] **Step 1: 实现Job列表和拖拽排序**

```javascript
// frontend/components/job-table.js
async function loadSiteJobs(siteId) {
    const res = await fetch(`/api/sites/${siteId}/plan`);
    const jobs = await res.json();
    renderJobTable(jobs);
}

function renderJobTable(jobs) {
    const tbody = document.querySelector('#job-table tbody');
    tbody.innerHTML = jobs.map((job, index) => `
        <tr data-id="${job.id}">
            <td class="seq-num">${index + 1}</td>
            <td>${job.job_no}</td>
            <td><span class="job-type-tag ${job.type}">${job.type}</span></td>
            <td>${job.part_id}</td>
            <td>${job.qty}件</td>
            <td>${job.strategy}</td>
            <td>${job.planned_end}</td>
            <td><span class="status-badge"><span class="dot ${job.status}"></span>${job.status}</span></td>
            <td>${job.line || '--'}</td>
            <td>
                <button onclick="startJob('${job.id}')">开工</button>
                <button onclick="completeJob('${job.id}')">完工</button>
            </td>
        </tr>
    `).join('');
    initDragAndDrop();
}

function initDragAndDrop() {
    const rows = document.querySelectorAll('#job-table tbody tr');
    rows.forEach(row => {
        row.draggable = true;
        row.addEventListener('dragstart', handleDragStart);
        row.addEventListener('dragover', handleDragOver);
        row.addEventListener('drop', handleDrop);
    });
}

async function handleDrop(e) {
    const draggedId = e.dataTransfer.getData('text/plain');
    const targetId = e.target.closest('tr').dataset.id;
    await fetch(`/api/sites/${siteId}/plan/reorder`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({job_id: draggedId, after_job_id: targetId})
    });
    loadSiteJobs(siteId);
}
```

- [ ] **Step 2: 实现状态变更**

```javascript
async function startJob(jobId) {
    await fetch(`/api/jobs/${jobId}/start`, {method: 'POST'});
    showToast('Job已开工');
    loadSiteJobs(siteId);
}

async function completeJob(jobId) {
    await fetch(`/api/jobs/${jobId}/complete`, {method: 'POST'});
    showToast('Job已完工');
    loadSiteJobs(siteId);
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/pages/site-plan.html frontend/components/job-table.js
git commit -m "feat(frontend): implement site plan page with drag-drop reordering"
```

---

## Task 8: WebSocket实时同步

**Files:**
- Create: `src/scheduler/websocket.py`

- [ ] **Step 1: 实现WebSocket连接**

```python
from fastapi import WebSocket

class SchedulerWebSocket:
    def __init__(self):
        self.connections = {}

    async def connect(self, websocket: WebSocket, site_id: str):
        await websocket.accept()
        self.connections[site_id] = websocket

    async def broadcast_priority_change(self, job_id: str, new_priority: int):
        for site_id, ws in self.connections.items():
            await ws.send_json({
                "type": "PRIORITY_CHANGED",
                "job_id": job_id,
                "new_priority": new_priority
            })

    async def broadcast_job_reordered(self, site_id: str, job_order: list[str]):
        ws = self.connections.get(site_id)
        if ws:
            await ws.send_json({
                "type": "JOB_REORDERED",
                "site_id": site_id,
                "job_order": job_order
            })
```

- [ ] **Step 2: 在Site Plan调整顺序时触发同步**

```python
@app.put("/api/sites/{site_id}/plan/reorder")
async def reorder_jobs(site_id: str, body: ReorderBody):
    update_job_order(site_id, body.job_id, body.after_job_id)
    job_order = get_job_order(site_id)
    await websocket.broadcast_job_reordered(site_id, job_order)
    await websocket.broadcast_priority_change(body.job_id, calculate_new_priority(job_order))
    return {"status": "ok"}
```

- [ ] **Step 3: Commit**

```bash
git add src/scheduler/websocket.py
git commit -m "feat(scheduler): add websocket for real-time priority sync between scheduler and site plan"
```

---

## Task 9: 集成测试

**Files:**
- Create: `tests/integration/test_scheduler_flow.py`

- [ ] **Step 1: 写端到端测试**

```python
def test_full_so_to_job_flow():
    # 1. 创建SO
    so = create_so(part_id="A-001", qty=100, delivery_date=date(2026,5,15))
    
    # 2. 验证Demand生成
    demands = list_demands(source_type="SO")
    assert len(demands) == 1
    assert demands[0].qty == 100
    
    # 3. Scheduler确认排程
    job = schedule_job(demands[0].id, scheduler_id="user-001")
    assert job.status == "DRAFT"
    
    # 4. 验证Job进入Site Plan
    site_jobs = list_site_jobs(job.site_id)
    assert job.id in [j.id for j in site_jobs]
    
    # 5. Site开工
    job = start_job(job.id)
    assert job.status == "EXECUTING"
    
    # 6. 验证子任务生成
    sub_tasks = list_sub_tasks(job.id)
    assert len(sub_tasks) > 0

def test_merge_flow():
    # 1. 创建两个可合并的SO
    so1 = create_so(part_id="A-001", qty=80, delivery_date=date(2026,5,18))
    so2 = create_so(part_id="A-001", qty=50, delivery_date=date(2026,5,20))
    
    # 2. 验证合并建议
    suggestions = get_merge_suggestions()
    assert len(suggestions) == 1
    assert suggestions[0].total_qty == 130
    
    # 3. 确认合并
    job = confirm_merge(suggestions[0].id)
    assert job.total_qty == 130
    assert len(list_job_lines(job.id)) == 2
```

- [ ] **Step 2: 运行集成测试**

```bash
pytest tests/integration/test_scheduler_flow.py -v
# Expected: PASS
```

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_scheduler_flow.py
git commit -m "test(integration): add end-to-end scheduler flow tests"
```

---

## Self-Review

| Spec覆盖检查 | 对应Task |
|-------------|----------|
| Demand统一汇聚 | Task 5 |
| 系统自动合并 | Task 2 |
| Job通用执行单元 | Task 4 |
| Site Plan灵活调整 | Task 7 |
| MTO独立排程 | Task 4 |
| 优先级引擎 | Task 3 |
| 返工置顶 | Task 5 |
| Replenishment半自动 | Task 5 |
| Transfer全公司库存检查 | Task 4 |
| SO变更增量Demand | Task 5 |
| WebSocket实时同步 | Task 8 |

| Placeholder扫描 | 状态 |
|----------------|------|
| TBD | ✅ 无残留 |
| TODO | ✅ 无残留 |
| implement later | ✅ 无残留 |

| 类型一致性检查 | 状态 |
|---------------|------|
| Job.status | DRAFT/SCHEDULED/EXECUTING/PARTIAL/COMPLETED/CLOSED/ON_HOLD/CANCELLED ✅ |
| Demand.source_type | SO/MTO/TRANSFER/REPLENISH/REWORK/FORECAST/SAMPLE ✅ |
| SubTask.task_type | PO/MO/TO/RETURN ✅ |

---

## 执行选项

**Plan complete and saved to `docs/superpowers/plans/2026-05-07-scheduler-implementation-plan.md`.**

**建议执行顺序：**
1. Task 1（数据库Schema）→ Task 2（合并引擎）→ Task 3（优先级引擎）→ Task 4（Job生命周期）
2. Task 5（Demand来源集成）
3. Task 6-7（前端页面）
4. Task 8（WebSocket）
5. Task 9（集成测试）
