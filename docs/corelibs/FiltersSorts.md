## `DefaultFilter` 功能示例清单

### 一、默认模式：包含关键词（不区分大小写）

```javascript
DefaultFilter("张三丰",      "张")        // true  ✓ 含"张"
DefaultFilter("张三丰",      "丰")        // true  ✓ 含"丰"
DefaultFilter("李四",        "张")        // false ✗ 不含"张"
DefaultFilter("APPLE",       "apple")     // true  ✓ 大小写不敏感
DefaultFilter("Apple Juice", "apple")     // true  ✓
DefaultFilter("销售部经理",   "销售")     // true  ✓
```

### 二、逗号分隔多关键词（AND 逻辑，全部包含才返回 true）

```javascript
DefaultFilter("张三，销售部经理",  "张三,销售")   // true  ✓ 同时含"张三"和"销售"
DefaultFilter("张三，销售部经理",  "张三,财务")   // false ✗ 不含"财务"
DefaultFilter("ABC-001 已审批",    "ABC,审批")    // true  ✓
DefaultFilter("ABC-001 待审批",    "ABC,已审批")  // false ✗ 含"ABC"但不含"已审批"
```

### 三、以…开头（`^`）

```javascript
DefaultFilter("张三丰",   "^张")     // true  ✓
DefaultFilter("王张三",   "^张")     // false ✗ 含"张"但不以"张"开头
DefaultFilter("PO-00123", "^PO")    // true  ✓ 采购单号以PO开头
DefaultFilter("SO-00456", "^PO")    // false ✗
```

### 四、以…结尾（`$`）

```javascript
DefaultFilter("张三丰",   "丰$")    // true  ✓
DefaultFilter("丰收年",   "丰$")    // false ✗ 含"丰"但不以"丰"结尾
DefaultFilter("PO-00123", "123$")   // true  ✓
DefaultFilter("PO-00123", "456$")   // false ✗
```

### 五、完全等于（`^...$`）

```javascript
DefaultFilter("张三",   "^张三$")   // true  ✓ 完全匹配
DefaultFilter("张三丰", "^张三$")   // false ✗ 多了一个"丰"
DefaultFilter("张三",   "^张$")     // false ✗ 少了"三"
DefaultFilter("approved", "^approved$")  // true  ✓ 不区分大小写
DefaultFilter("APPROVED", "^approved$")  // true  ✓
```

### 六、通配符 `*`（匹配任意字符）

```javascript
DefaultFilter("PO-2024-001",  "PO*001")      // true  ✓ PO开头001结尾
DefaultFilter("PO-2025-001",  "PO*001")      // true  ✓
DefaultFilter("SO-2024-001",  "PO*001")      // false ✗ 不以PO开头
DefaultFilter("张三",          "*三")         // true  ✓ 以三结尾（等同于 三$）
DefaultFilter("张三",          "张*")         // true  ✓ 以张开头（等同于 ^张）
DefaultFilter("PO-2024-001",  "*2024*")      // true  ✓ 含2024（等同于默认包含）
DefaultFilter("ABC-DEF-GHI",  "A*D*G*")     // true  ✓ 多段通配
```

### 七、反向搜索 `!`（结果取反，可叠加到任意模式）

```javascript
DefaultFilter("张三",   "!张")        // false ✗ 含"张"，取反
DefaultFilter("李四",   "!张")        // true  ✓ 不含"张"，取反
DefaultFilter("王小明", "!^张")       // true  ✓ 不以"张"开头
DefaultFilter("张小明", "!^张")       // false ✗ 以"张"开头，取反
DefaultFilter("PO-001", "!^SO")      // true  ✓ 不以"SO"开头（只看采购单）
DefaultFilter("张三",   "!^张三$")    // false ✗ 完全等于"张三"，取反
DefaultFilter("张三丰", "!^张三$")    // true  ✓ 不完全等于"张三"
DefaultFilter("李四",   "!张,李")    // false ✗ 取反前：含"李"但不含"张" → false，取反 → true
// 注意：! 是对最终结果取反，不是对每个关键词分别取反
```

### 八、正则表达式（`~`，主要给开发者用）

```javascript
DefaultFilter("PO-2024-001",  "~^PO-\\d{4}-\\d{3}$")  // true  ✓ 标准采购单格式
DefaultFilter("PO-24-001",    "~^PO-\\d{4}-\\d{3}$")  // false ✗ 年份只有2位
DefaultFilter("ABC123",       "~^[A-Z]{3}\\d{3}$")    // true  ✓
DefaultFilter("abc123",       "~^[A-Z]{3}\\d{3}$")    // true  ✓ 不区分大小写
DefaultFilter("AB123",        "~^[A-Z]{3}\\d{3}$")    // false ✗ 字母只有2位
```

### 九、数字比较（`>`、`<`、`>=`、`<=`）

```javascript
DefaultFilter(5000,   ">3000")    // true  ✓ 5000 > 3000
DefaultFilter(2000,   ">3000")    // false ✗ 2000 不大于 3000
DefaultFilter(3000,   ">3000")    // false ✗ 等于不算大于
DefaultFilter(3000,   ">=3000")   // true  ✓ 等于算
DefaultFilter(150,    "<200")     // true  ✓
DefaultFilter(200,    "<200")     // false ✗
DefaultFilter(200,    "<=200")    // true  ✓
DefaultFilter("5000", ">3000")    // true  ✓ 字符串"5000"也能做数字比较
DefaultFilter(99.5,   ">=99.5")   // true  ✓ 支持小数
```

### 十、日期处理（毫秒时间戳）⚠️ 待架构师确认转换格式

```javascript
// 假设毫秒转成 "YYYY-MM-DD" 格式后再做字符串筛选
// 1705276800000 = 2024-01-15

DefaultFilter(1705276800000, "2024")          // true  ✓ 含"2024"（筛某一年）
DefaultFilter(1705276800000, "2024-01")       // true  ✓ 含"2024-01"（筛某月）
DefaultFilter(1705276800000, "^2024")         // true  ✓ 以"2024"开头
DefaultFilter(1705276800000, "^2024-01-15$")  // true  ✓ 完全等于某天
DefaultFilter(1705276800000, "^2024-01-16$")  // false ✗ 不等于
```

### 十一、布尔值

```javascript
DefaultFilter(true,  "true")    // true  ✓ 转成字符串"true"再匹配
DefaultFilter(false, "true")    // false ✗
DefaultFilter(true,  "^true$")  // true  ✓
DefaultFilter(false, "false")   // true  ✓
```

### 十二、对象 ⚠️ 待架构师确认处理方式

```javascript
// 方案：JSON.stringify 后再做字符串匹配
// {name:"张三", dept:"销售"} → '{"name":"张三","dept":"销售"}'

DefaultFilter({name:"张三", dept:"销售"}, "张三")   // true  ✓
DefaultFilter({name:"张三", dept:"销售"}, "财务")   // false ✗
DefaultFilter({name:"张三", dept:"销售"}, "销售")   // true  ✓
```

### 十三、边缘情况

```javascript
DefaultFilter("张三",    "")          // true  ✓ 空条件 = 全部保留
DefaultFilter("张三",    null)        // true  ✓
DefaultFilter("张三",    undefined)   // true  ✓
DefaultFilter(null,      "张")        // false ✗ null当空字符串处理
DefaultFilter(undefined, "张")        // false ✗
DefaultFilter("",        "张")        // false ✗
DefaultFilter("",        "")          // true  ✓ 空数据 + 空条件 = 保留
DefaultFilter("张三",    "~[invalid") // false ✗ 无效正则 = 当作不匹配
```

---

**需要架构师重点确认的两个问题（已用 ⚠️ 标出）：**

1. **日期毫秒** → 转成什么格式的字符串？（`YYYY-MM-DD`？还是其他？）
2. **对象** → 用 JSON.stringify 转字符串处理，还是另有方案？### 





## `DefaultSort` 功能示例清单

## 一、`data` 参数(仅数组)

```javascript
// ✅ 正常
expectResult(DefaultSort([]),             [],         "data=空数组");
expectResult(DefaultSort([1]),            [1],        "data=单元素");
expectResult(DefaultSort([3, 1, 2]),      [1, 2, 3],  "data=数字数组");
expectResult(DefaultSort(['b', 'a']),     ['a', 'b'], "data=字符串数组");

// ❌ 报错
expectError(() => DefaultSort(null),       "data=null");
expectError(() => DefaultSort(undefined),  "data=undefined");
expectError(() => DefaultSort("hello"),    "data=字符串");
expectError(() => DefaultSort(42),         "data=数字");
expectError(() => DefaultSort({}),         "data=普通对象");
expectError(() => DefaultSort(true),       "data=布尔值");
```

---

## 二、`reverse` 参数

```javascript
// ✅ 正常
expectResult(DefaultSort([3, 1, 2]),         [1, 2, 3], "reverse=不传（默认false）");
expectResult(DefaultSort([3, 1, 2], false),  [1, 2, 3], "reverse=false");
expectResult(DefaultSort([3, 1, 2], true),   [3, 2, 1], "reverse=true");

// ❌ 报错
expectError(() => DefaultSort([1, 2], null),    "reverse=null");
expectError(() => DefaultSort([1, 2], "true"),  "reverse=字符串'true'");
expectError(() => DefaultSort([1, 2], "false"), "reverse=字符串'false'");
expectError(() => DefaultSort([1, 2], 1),       "reverse=数字1");
expectError(() => DefaultSort([1, 2], 0),       "reverse=数字0");
expectError(() => DefaultSort([1, 2], {}),      "reverse=对象");
```

---

## 三、`sortBy=null`（直接对值排序）

```javascript
// ✅ 数字
expectResult(DefaultSort([5, 3, 8, 1]),                             [1, 3, 5, 8],            "直接排序-数字升序");
expectResult(DefaultSort([5, 3, 8, 1], true),                       [8, 5, 3, 1],            "直接排序-数字降序");
expectResult(DefaultSort([0, -1, 2, -3]),                            [-3, -1, 0, 2],          "直接排序-含负数");
expectResult(DefaultSort([1.5, 0.1, 3.2]),                           [0.1, 1.5, 3.2],         "直接排序-小数");

// ✅ 字符串
expectResult(DefaultSort(['banana', 'apple', 'cherry']),             ['apple', 'banana', 'cherry'],          "直接排序-字符串升序");
expectResult(DefaultSort(['banana', 'apple', 'cherry'], true),       ['cherry', 'banana', 'apple'],          "直接排序-字符串降序");

// ✅ 核心需求：数字字符串，'10' 要排在 '5' 后面
expectResult(DefaultSort(['10', '5', '3', '20']),                    ['3', '5', '10', '20'],                 "数字字符串自然排序");
expectResult(DefaultSort(['2', '10', '1', '20']),                    ['1', '2', '10', '20'],                 "数字字符串自然排序2");

// ✅ 混合字符串自然排序（localeCompare numeric:true）
expectResult(DefaultSort(['PROD-10', 'PROD-2', 'PROD-5']),           ['PROD-2', 'PROD-5', 'PROD-10'],        "混合字符串自然排序-SKU场景");
expectResult(DefaultSort(['PO-10', 'PO-2', 'PO-1']),                 ['PO-1', 'PO-2', 'PO-10'],             "混合字符串自然排序-采购单号");
expectResult(DefaultSort(['第10条', '第2条', '第1条']),               ['第1条', '第2条', '第10条'],            "混合字符串自然排序-中文数字");

// ✅ null/undefined 排最后
expectResult(DefaultSort([3, null, 1, undefined, 2]),                [1, 2, 3, null, undefined],             "null和undefined排最后");
expectResult(DefaultSort([null, null]),                               [null, null],                           "全null");
expectResult(DefaultSort([undefined, undefined]),                     [undefined, undefined],                 "全undefined");
expectResult(DefaultSort([null, undefined, null]),                    [null, undefined, null],                "null和undefined混合");
expectResult(DefaultSort([3, null, 1, undefined, 2], true),          [3, 2, 1, null, undefined],             "降序-null和undefined仍排最后");

// ✅ 数组套数组-sortBy=null 逐元素比较
expectResult(DefaultSort([['b', 2], ['a', 3], ['a', 1]]),            [['a', 1], ['a', 3], ['b', 2]],         "子数组逐元素比较-两层");
expectResult(DefaultSort([['b', 2, 'z'], ['a', 3, 'm'], ['a', 3, 'a']]), [['a', 3, 'a'], ['a', 3, 'm'], ['b', 2, 'z']], "子数组逐元素比较-三层");
expectResult(DefaultSort([['10', 2], ['5', 3], ['10', 1]]),          [['5', 3], ['10', 1], ['10', 2]],       "子数组逐元素比较-数字字符串正确排序");
expectResult(DefaultSort([['b', 2], ['a', 3], ['a', 1]], true),      [['b', 2], ['a', 3], ['a', 1]],         "子数组逐元素比较-降序");
expectResult(DefaultSort([['a'], ['b'], ['a']]),                      [['a'], ['a'], ['b']],                  "子数组逐元素比较-单元素");

// ✅ 对象数组-sortBy=null 按第一个对象key顺序逐value比较
expectResult(
    DefaultSort([
        { dept: '销售部', level: '10', name: '张三' },
        { dept: '技术部', level: '5',  name: '李四' },
        { dept: '销售部', level: '3',  name: '王五' },
    ]),
    [
        { dept: '技术部', level: '5',  name: '李四' },
        { dept: '销售部', level: '3',  name: '王五' },
        { dept: '销售部', level: '10', name: '张三' },
    ],
    "对象数组-按key顺序逐value比较");

expectResult(
    DefaultSort([
        { dept: '销售部', level: '10', name: '张三' },
        { dept: '销售部', level: '10', name: '王五' },
        { dept: '销售部', level: '10', name: '李四' },
    ]),
    [
        { dept: '销售部', level: '10', name: '李四' },
        { dept: '销售部', level: '10', name: '王五' },
        { dept: '销售部', level: '10', name: '张三' },
    ],
    "对象数组-前两个key相同再比第三个key");

expectResult(
    DefaultSort([
        { dept: '销售部', level: '10', name: '张三' },
        { level: '5',    dept: '技术部', name: '李四' },  // key顺序不同
    ]),
    [
        { dept: '技术部', level: '5',  name: '李四' },
        { dept: '销售部', level: '10', name: '张三' },
    ],
    "对象数组-key顺序不同时强制按第一个对象key顺序比较");

expectResult(
    DefaultSort([
        { dept: '销售部', level: '10', name: '张三' },
        { dept: '技术部', level: '5',  name: '李四' },
    ], true),
    [
        { dept: '销售部', level: '10', name: '张三' },
        { dept: '技术部', level: '5',  name: '李四' },
    ],
    "对象数组-降序");

// ✅ 不修改原数组
const original = [3, 1, 2];
DefaultSort(original);
expectResult(original, [3, 1, 2], "原数组不被修改");

// ✅ 全相同元素
expectResult(DefaultSort([2, 2, 2]),                                 [2, 2, 2],               "全相同元素-数字");
expectResult(DefaultSort(['a', 'a', 'a']),                           ['a', 'a', 'a'],          "全相同元素-字符串");

// ❌ 报错：对象数组key数量不一致
expectError(() => DefaultSort([
    { dept: '销售部', level: '10' },
    { dept: '技术部' },                // 少了level
]), "对象数组-key数量不一致");

// ❌ 报错：对象数组key名字不一致
expectError(() => DefaultSort([
    { dept: '销售部', level: '10' },
    { dept: '技术部', salary: '5' },   // salary和level不一样
]), "对象数组-key名字不一致");

// ❌ 报错：同位置value类型不一致
expectError(() => DefaultSort([
    { dept: '销售部', level: '10' },
    { dept: '技术部', level: 5    },   // level一个字符串一个数字
]), "对象数组-同位置value类型不一致");

// ❌ 报错：子数组长度不一致
expectError(() => DefaultSort([
    ['a', 1],
    ['b'],          // 少了第二个元素
]), "子数组长度不一致");
```
对对象怎么比
---
```javascript// sortBy=null 且 data是对象数组时
// 第一步：取第一个对象的keys作为标准
const standardKeys = Object.keys(data[0])

// 第二步：检查所有对象
// key数量不同 → 报错
// key名字不同 → 报错
// key顺序不同 → 不报错，强制按standardKeys顺序取值

// 第三步：按standardKeys顺序逐个value比较

```
## 四、`sortBy` = 字符串（按对象某个键排序）
```
```javascript
// ✅ 正常
expectResult(
    DefaultSort([{name:'Charlie'},{name:'Alice'},{name:'Bob'}], false, 'name').map(x=>x.name),
    ['Alice', 'Bob', 'Charlie'],
    "sortBy字符串-按name升序");

expectResult(
    DefaultSort([{name:'Charlie'},{name:'Alice'},{name:'Bob'}], true, 'name').map(x=>x.name),
    ['Charlie', 'Bob', 'Alice'],
    "sortBy字符串-按name降序");

expectResult(
    DefaultSort([{score:90},{score:70},{score:85}], false, 'score').map(x=>x.score),
    [70, 85, 90],
    "sortBy字符串-数字字段");

// ✅ 金额存为字符串（JSONB常见，要自然排序）
expectResult(
    DefaultSort([{amount:'200'},{amount:'1000'},{amount:'50'}], false, 'amount').map(x=>x.amount),
    ['50', '200', '1000'],
    "sortBy字符串-金额字符串自然排序（JSONB）");

// ✅ 某些对象缺少该字段 → undefined → 排最后
expectResult(
    DefaultSort([{name:'Bob'},{age:25},{name:'Alice'}], false, 'name').map(x=>x.name),
    ['Alice', 'Bob', undefined],
    "sortBy字符串-缺失字段排最后");

// ❌ 报错
expectError(() => DefaultSort([{name:'A'}], false, ''),  "sortBy=空字符串");
```

---

## 五、`sortBy` = 数字（按子数组某个索引排序）/对象

```javascript
// ✅ 正常：数组套数组-按index0排序
expectResult(
    DefaultSort([['b', 2], ['a', 3], ['c', 1]], false, 0),
    [['a', 3], ['b', 2], ['c', 1]],
    "sortBy数字-数组套数组-按index0排序");

// ✅ 正常：数组套数组-按index1排序
expectResult(
    DefaultSort([['b', 2], ['a', 3], ['c', 1]], false, 1),
    [['c', 1], ['b', 2], ['a', 3]],
    "sortBy数字-数组套数组-按index1排序");

// ✅ 正常：数组套数组-降序
expectResult(
    DefaultSort([['b', 2], ['a', 3], ['c', 1]], true, 0),
    [['c', 1], ['b', 2], ['a', 3]],
    "sortBy数字-数组套数组-降序");

// ✅ 正常：数组套数组-单元素子数组
expectResult(
    DefaultSort([['b'], ['a'], ['c']], false, 0),
    [['a'], ['b'], ['c']],
    "sortBy数字=0-数组套数组-合法边界值");

// ✅ 正常：数组套数组-数字字符串正确排序('10'在'5'后面)
expectResult(
    DefaultSort([['b','10'],['a','5'],['c','3']], false, 1),
    [['c','3'],['a','5'],['b','10']],
    "sortBy数字-数组套数组-数字字符串正确排序");

// ✅ 正常：JSONB对象数组-按index0排序
expectResult(
    DefaultSort([{0:'b',1:2},{0:'a',1:3},{0:'c',1:1}], false, 0),
    [{0:'a',1:3},{0:'b',1:2},{0:'c',1:1}],
    "sortBy数字-JSONB对象-按index0排序");

// ✅ 正常：JSONB对象数组-按index1排序
expectResult(
    DefaultSort([{0:'b',1:2},{0:'a',1:3},{0:'c',1:1}], false, 1),
    [{0:'c',1:1},{0:'b',1:2},{0:'a',1:3}],
    "sortBy数字-JSONB对象-按index1排序");

// ✅ 正常：JSONB对象数组-降序
expectResult(
    DefaultSort([{0:'b',1:2},{0:'a',1:3},{0:'c',1:1}], true, 0),
    [{0:'c',1:1},{0:'b',1:2},{0:'a',1:3}],
    "sortBy数字-JSONB对象-降序");

// ✅ 正常：JSONB对象数组-数字字符串正确排序('10'在'5'后面)
expectResult(
    DefaultSort([{0:'b',1:'10'},{0:'a',1:'5'},{0:'c',1:'3'}], false, 1),
    [{0:'c',1:'3'},{0:'a',1:'5'},{0:'b',1:'10'}],
    "sortBy数字-JSONB对象-数字字符串正确排序");

// ✅ 正常：JSONB对象数组-单字段
expectResult(
    DefaultSort([{0:'b'},{0:'a'},{0:'c'}], false, 0),
    [{0:'a'},{0:'b'},{0:'c'}],
    "sortBy数字=0-JSONB对象-合法边界值");

// ✅ 正常：所有value相同-保持原顺序
expectResult(
    DefaultSort([{0:'a'},{0:'a'},{0:'a'}], false, 0),
    [{0:'a'},{0:'a'},{0:'a'}],
    "sortBy数字-JSONB对象-所有value相同保持原顺序");

// ❌ 报错：负索引
expectError(() => DefaultSort([[1,2]], false, -1),
    "sortBy=-1-负索引");

// ❌ 报错：小数索引
expectError(() => DefaultSort([[1,2]], false, 1.5),
    "sortBy=1.5-小数索引");

// ❌ 报错：NaN
expectError(() => DefaultSort([[1,2]], false, NaN),
    "sortBy=NaN");

// ❌ 报错：Infinity
expectError(() => DefaultSort([[1,2]], false, Infinity),
    "sortBy=Infinity");

// ❌ 报错：数组索引越界
expectError(() => DefaultSort([[1,2]], false, 99),
    "sortBy数字-数组套数组-索引越界");

// ❌ 报错：JSONB对象key不存在
expectError(() => DefaultSort([{0:'a',1:'b'}], false, 99),
    "sortBy数字-JSONB对象-key不存在");

// ❌ 报错：同索引位置value类型不一致
expectError(() => DefaultSort([[1,'a'],[2,3]], false, 1),
    "sortBy数字-数组套数组-同索引value类型不一致");

// ❌ 报错：同索引位置value含null
expectError(() => DefaultSort([[1,null],[2,3]], false, 1),
    "sortBy数字-数组套数组-同索引value含null");

// ❌ 报错：同索引位置value含undefined
expectError(() => DefaultSort([[1,undefined],[2,3]], false, 1),
    "sortBy数字-数组套数组-同索引value含undefined");
// ❌ 报错
expectError(() => DefaultSort([[1,2]], false, -1),       "sortBy=-1（负索引）");
expectError(() => DefaultSort([[1,2]], false, 1.5),      "sortBy=1.5（小数索引）");
expectError(() => DefaultSort([[1,2]], false, NaN),      "sortBy=NaN");
expectError(() => DefaultSort([[1,2]], false, Infinity), "sortBy=Infinity");
```

---

## 六、`sortBy` = 字符串数组（多键对象排序，ERP最常用）

```javascript
// ✅ 正常
expectResult(
    DefaultSort([
        {last:'Smith', first:'Zoe'},
        {last:'Smith', first:'Alice'},
        {last:'Jones', first:'Bob'},
    ], false, ['last', 'first']).map(x=>`${x.last} ${x.first}`),
    ['Jones Bob', 'Smith Alice', 'Smith Zoe'],
    "sortBy字符串数组-姓+名两级排序");

expectResult(
    DefaultSort([
        {dept:'IT', last:'Wang'},
        {dept:'HR', last:'Zhang'},
        {dept:'IT', last:'Li'},
        {dept:'HR', last:'Chen'},
    ], false, ['dept', 'last']).map(x=>`${x.dept}-${x.last}`),
    ['HR-Chen', 'HR-Zhang', 'IT-Li', 'IT-Wang'],
    "sortBy字符串数组-部门+姓名");

expectResult(
    DefaultSort([
        {status:'paid',    date:'2024-03-01'},
        {status:'overdue', date:'2024-01-01'},
        {status:'paid',    date:'2024-01-15'},
    ], false, ['status', 'date']).map(x=>`${x.status}|${x.date}`),
    ['overdue|2024-01-01', 'paid|2024-01-15', 'paid|2024-03-01'],
    "sortBy字符串数组-状态+日期");

// ❌ 报错
expectError(() => DefaultSort([{name:'A'}], false, []),              "sortBy=空数组");
expectError(() => DefaultSort([{name:'A'}], false, ['name', 0]),     "sortBy=混合数组（字符串+数字）");
expectError(() => DefaultSort([{name:'A'}], false, ['', 'name']),    "sortBy=含空字符串元素");
expectError(() => DefaultSort([{name:'A'}], false, ['name', null]),  "sortBy=含null元素");
```

---

## 七、`sortBy` = 数字数组（多索引子数组排序）/对象

```javascript
// ✅ 正常
expectResult(
    DefaultSort([[2,'b'],[1,'z'],[1,'a'],[2,'a']], false, [0, 1]),
    [[1,'a'],[1,'z'],[2,'a'],[2,'b']],
    "sortBy数字数组-两级索引");

expectResult(
    DefaultSort([[1,2,3],[1,2,1],[1,1,5]], false, [0, 1, 2]),
    [[1,1,5],[1,2,1],[1,2,3]],
    "sortBy数字数组-三级索引");

// ❌ 报错
expectError(() => DefaultSort([[1,2]], false, [0, -1]),      "sortBy数字数组-含负数");
expectError(() => DefaultSort([[1,2]], false, [0, 1.5]),     "sortBy数字数组-含小数");
expectError(() => DefaultSort([[1,2]], false, [0, 'name']),  "sortBy数字数组-混合类型");
// ✅ 正常：数组套数组-单级索引
expectResult(
    DefaultSort([[2],[1],[3]], false, [0]),
    [[1],[2],[3]],
    "sortBy数字数组-数组套数组-单级索引");

// ✅ 正常：数组套数组-两级索引
expectResult(
    DefaultSort([[2,'b'],[1,'z'],[1,'a'],[2,'a']], false, [0, 1]),
    [[1,'a'],[1,'z'],[2,'a'],[2,'b']],
    "sortBy数字数组-数组套数组-两级索引");

// ✅ 正常：数组套数组-三级索引
expectResult(
    DefaultSort([[1,2,3],[1,2,1],[1,1,5]], false, [0, 1, 2]),
    [[1,1,5],[1,2,1],[1,2,3]],
    "sortBy数字数组-数组套数组-三级索引");

// ✅ 正常：数组套数组-数字字符串正确排序('10'在'5'后面)
expectResult(
    DefaultSort([['b','10'],['a','5'],['a','10'],['b','3']], false, [0, 1]),
    [['a','5'],['a','10'],['b','3'],['b','10']],
    "sortBy数字数组-数组套数组-数字字符串正确排序");

// ✅ 正常：数组套数组-reverse=true
expectResult(
    DefaultSort([[2,'b'],[1,'z'],[1,'a'],[2,'a']], true, [0, 1]),
    [[2,'b'],[2,'a'],[1,'z'],[1,'a']],
    "sortBy数字数组-数组套数组-降序");

// ✅ 正常：JSONB对象数组-单级索引
expectResult(
    DefaultSort([{0:'b'},{0:'a'},{0:'c'}], false, [0]),
    [{0:'a'},{0:'b'},{0:'c'}],
    "sortBy数字数组-JSONB对象-单级索引");

// ✅ 正常：JSONB对象数组-两级索引
expectResult(
    DefaultSort([{0:'b',1:2},{0:'a',1:3},{0:'a',1:1}], false, [0, 1]),
    [{0:'a',1:1},{0:'a',1:3},{0:'b',1:2}],
    "sortBy数字数组-JSONB对象-两级索引");

// ✅ 正常：JSONB对象数组-三级索引
expectResult(
    DefaultSort([{0:'b',1:2,2:'z'},{0:'a',1:3,2:'m'},{0:'a',1:3,2:'a'}], false, [0, 1, 2]),
    [{0:'a',1:3,2:'a'},{0:'a',1:3,2:'m'},{0:'b',1:2,2:'z'}],
    "sortBy数字数组-JSONB对象-三级索引");

// ✅ 正常：JSONB对象数组-数字字符串正确排序('10'在'5'后面)
expectResult(
    DefaultSort([{0:'销售部',1:'10'},{0:'技术部',1:'5'},{0:'销售部',1:'3'},{0:'技术部',1:'10'}], false, [0, 1]),
    [{0:'技术部',1:'5'},{0:'技术部',1:'10'},{0:'销售部',1:'3'},{0:'销售部',1:'10'}],
    "sortBy数字数组-JSONB对象-数字字符串正确排序");

// ✅ 正常：JSONB对象数组-reverse=true
expectResult(
    DefaultSort([{0:'a',1:1},{0:'b',1:2},{0:'a',1:3}], true, [0, 1]),
    [{0:'b',1:2},{0:'a',1:3},{0:'a',1:1}],
    "sortBy数字数组-JSONB对象-降序");

// ✅ 正常：所有value相同-保持原顺序
expectResult(
    DefaultSort([[1,'a'],[1,'a'],[1,'a']], false, [0, 1]),
    [[1,'a'],[1,'a'],[1,'a']],
    "sortBy数字数组-所有value相同-保持原顺序");

// ❌ 报错：含负数索引
expectError(() => DefaultSort([[1,2]], false, [0, -1]),
    "sortBy数字数组-含负数");

// ❌ 报错：含小数索引
expectError(() => DefaultSort([[1,2]], false, [0, 1.5]),
    "sortBy数字数组-含小数");

// ❌ 报错：混合类型索引
expectError(() => DefaultSort([[1,2]], false, [0, 'name']),
    "sortBy数字数组-混合类型");

// ❌ 报错：索引越界
expectError(() => DefaultSort([[1,2]], false, [0, 99]),
    "sortBy数字数组-索引越界");

// ❌ 报错：空数组
expectError(() => DefaultSort([[1,2]], false, []),
    "sortBy数字数组-空数组");

// ❌ 报错：同一索引位置value类型不一致
expectError(() => DefaultSort([[1,'a'],['b',2]], false, [0]),
    "sortBy数字数组-同索引value类型不一致");

// ❌ 报错：同一索引位置value含null
expectError(() => DefaultSort([[1,null],[2,3]], false, [0, 1]),
    "sortBy数字数组-同索引value含null");

// ❌ 报错：同一索引位置value含undefined
expectError(() => DefaultSort([[1,undefined],[2,3]], false, [0, 1]),
    "sortBy数字数组-同索引value含undefined");```

## 八、`sortBy` 其他非法类型

```javascript
expectError(() => DefaultSort([1,2], false, true),      "sortBy=布尔true");
expectError(() => DefaultSort([1,2], false, false),     "sortBy=布尔false");
expectError(() => DefaultSort([1,2], false, {}),        "sortBy=普通对象");
expectError(() => DefaultSort([1,2], false, ()=>{}),    "sortBy=函数");
```

---

## ERP 场景建议：该不该"卡死"边界？

| 参数                      | 建议         | 理由                                                                            |
| ----------------------- | ---------- | ----------------------------------------------------------------------------- |
| `data` 非数组              | ✅ **必须报错** | ERP里传进来非数组100%是代码bug，静默返回只会让问题藏得更深                                            |
| `data = null`           | ✅ **必须报错** | API返回null说明上游没处理，让调用方自己写 `DefaultSort(apiData ?? [])` 更清晰                     |
| `reverse` 非布尔           | ✅ **建议报错** | 数据库字段 `0/1` 在ERP里很常见，**不报错会造成排序方向静默错误**，不如强制转换：`DefaultSort(data, !!dbValue)` |
| `sortBy = ''`           | ✅ **必须报错** | 空字符串键在JSONB对象里永远取不到值，100%是笔误                                                  |
| `sortBy = []`           | ✅ **必须报错** | 传了空数组等于什么都没传，但代码看起来像传了，必然是bug                                                 |
| `sortBy` 混合数组           | ✅ **必须报错** | 字符串键和数字索引混在一起逻辑上自相矛盾                                                          |
| `sortBy` 负数/小数          | ✅ **必须报错** | 数组不存在负索引或小数索引，没有任何合法场景                                                        |
| `sortBy` 其他类型（布尔/对象/函数） | ✅ **必须报错** | 同上，传这些进来100%是写错了                                                              |

**总结一句话：** ERP的数据可以乱，但**传给这个函数的参数不能乱**。把所有非法参数在入口处报错，比让它在排序时静默失效要安全得多——调试一个"排序结果全一样"的bug比处理一个报错难多了。





## DefaultFilter 函数清单

### 函数签名

```
DefaultFilter(data, filtervalue): bool

输入：data        → 任意类型（见下方明细）
输入：filtervalue → string | null | undefined
输出：bool        → 永远只返回 true 或 false
```

---

### 第一步：data 的合法类型清单

```
data 类型          处理方式                        非法情况
─────────────────────────────────────────────────────────────
string            直接做字符串匹配                  无
number            转成字符串再匹配                  无
boolean           转成 "true"/"false" 再匹配        无
毫秒时间戳(number) 转成 "YYYY-MM-DD" 再匹配         ⚠️ 待架构师确认转换格式
object            JSON.stringify 后再匹配           ⚠️ 待架构师确认
null              当空字符串 "" 处理                无
undefined         当空字符串 "" 处理                无
array             ❌ 不支持，报错                   直接报错
```

---

### 第二步：filtervalue 的合法格式清单

```
格式                    例子                    规则说明
──────────────────────────────────────────────────────────────────
空/null/undefined       ""  null  undefined    → 永远返回 true
普通字符串              "张三"                  → 包含匹配，不区分大小写
逗号分隔多关键词        "张三,销售"             → AND逻辑，全部包含才true
^开头                   "^张"                  → data以"张"开头
$结尾                   "丰$"                  → data以"丰"结尾
^...$同时               "^张三$"               → 完全等于
*通配符                 "PO*001"               → *匹配任意字符
!前缀                   "!张"                  → 对最终结果取反
~前缀                   "~^\d{4}$"             → 正则匹配，不区分大小写
数字比较                ">3000"  "<=200"       → 转数字后比较，支持> < >= <=
```

---

### 第三步：内部需要写的子函数清单

```
函数名                      输入                  输出      说明
────────────────────────────────────────────────────────────────────────
normalizeData(data)         any                   string    把data转成可比较的字符串
parseFilterValue(fv)        string                object    解析filtervalue，识别是哪种模式
matchContains(str, kw)      string, string        bool      包含匹配，不区分大小写
matchStartsWith(str, kw)    string, string        bool      开头匹配
matchEndsWith(str, kw)      string, string        bool      结尾匹配
matchEquals(str, kw)        string, string        bool      完全等于匹配
matchWildcard(str, kw)      string, string        bool      通配符匹配，*转成正则
matchRegex(str, pattern)    string, string        bool      正则匹配，失败返回false
matchNumber(data, fv)       number|string, string bool      数字比较 > < >= <=
matchMultiple(str, kws[])   string, string[]      bool      逗号分隔多关键词AND逻辑
```

---

### 第四步：卡死的输入输出类型约束

```
约束项                               规则
────────────────────────────────────────────────────────────────
filtervalue 不是 string/null/undefined  → 报错
filtervalue 是 string 但格式非法        → 具体情况见下
  "~[invalid"（无效正则）               → 不报错，返回 false
  ">abc"（>后面不是数字）               → 报错
  逗号分隔但某个关键词是空字符串         → 报错，如 "张三,"
data 是 array                           → 报错
返回值                                  → 永远是 true 或 false，不能是 truthy/falsy
```


问题一：时间戳转日期字符串
调用方传进来之前自己转好 data 如果是时间戳，调用方先转成 "2024-01-15" 字符串再传进来 DefaultFilter 内部不做时间戳判断，只处理字符串 优点：函数职责清晰，不用猜 缺点：调用方麻烦一点

问题二：object 的 key 排序后再 stringify
```
// 不排序的问题：
JSON.stringify({ name:"张三", dept:"销售" })
// → '{"name":"张三","dept":"销售"}'

JSON.stringify({ dept:"销售", name:"张三" })
// → '{"dept":"销售","name":"张三"}'

// 同一个数据，key顺序不同，stringify结果不同
// 搜"张三"都能搜到，但搜'{"name"' 就只能搜到第一个

// 排序后再stringify：
function sortedStringify(obj) {
    const sorted = Object.keys(obj).sort().reduce((acc, key) => {
        acc[key] = obj[key]
        return acc
    }, {})
    return JSON.stringify(sorted)
}

sortedStringify({ name:"张三", dept:"销售" })
// → '{"dept":"销售","name":"张三"}'  ← 永远按key字母顺序

sortedStringify({ dept:"销售", name:"张三" })
// → '{"dept":"销售","name":"张三"}'  ← 结果一样 ✅
```


### true/false 状态筛选

**转成字符串 "true"/"false" 后，走普通字符串匹配**

javascript

```javascript
// data 是 boolean，先转字符串
DefaultFilter(true,  "true")    // "true".includes("true")  → true  ✅
DefaultFilter(false, "true")    // "false".includes("true") → false ✅
DefaultFilter(true,  "false")   // "true".includes("false") → false ✅
DefaultFilter(false, "false")   // "false".includes("false")→ true  ✅
```

**但这里有个坑需要卡死：**

```
"false".includes("true") → false  ✅ 没问题

但是：
"false".includes("als")  → true   ⚠️ 误匹配！
"false".includes("se")   → true   ⚠️ 误匹配！
```

**所以建议对 boolean 类型强制用完全等于匹配：**

javascript

```javascript
// data 是 boolean 时：
// filtervalue 只允许以下几种，否则报错：
"true"      → 完全等于匹配
"false"     → 完全等于匹配
"^true$"    → 完全等于匹配
"^false$"   → 完全等于匹配
"!true"     → 取反
"!false"    → 取反

// 不允许：
"tru"       → 报错，boolean不支持模糊匹配
"^true"     → 报错，boolean不支持开头匹配
```

## DefaultSort 函数清单

### 主函数签名

```
DefaultSort(data, reverse=false, sortBy=null): array

输入：data     → array                        非法一律报错
输入：reverse  → boolean                      非法一律报错
输入：sortBy   → string | number | string[] | number[] | null
输出：          → array                        永远返回新数组，不修改原数组
```

---

### 入口参数校验函数

```
函数名                        输入类型              输出        报错条件
────────────────────────────────────────────────────────────────────────────
validateData(data)            any                  void        不是array → 报错
                                                               null/undefined/string/number/object/boolean → 报错

validateReverse(reverse)      any                  void        不是boolean → 报错
                                                               null/"true"/"false"/0/1/{} → 报错

validateSortBy(sortBy)        any                  void        不是 string|number|string[]|number[]|null → 报错
                                                               string 且是空字符串 "" → 报错
                                                               number 且是负数 → 报错
                                                               number 且是小数 → 报错
                                                               number 且是 NaN → 报错
                                                               number 且是 Infinity → 报错
                                                               array 且是空数组 [] → 报错
                                                               array 且混了字符串和数字 → 报错
                                                               array 且元素含 null/undefined/"" → 报错
                                                               array 且元素含负数/小数/NaN/Infinity → 报错
                                                               boolean/object/function → 报错
```

---

### data 内部结构校验函数

```
函数名                           输入类型                    输出      报错条件
────────────────────────────────────────────────────────────────────────────────────
validateDataElements(data)       array                       void      元素含 null/undefined 且 sortBy 是数字/数字数组 → 报错
                                                                       同位置value类型不一致 → 报错

validateSubArrays(data)          array<array>                void      子数组长度不一致 → 报错
                                                                       索引越界（sortBy指定的index超出子数组长度）→ 报错

validateObjects(data, sortBy)    array<object>, string|      void      key数量不一致 → 报错
                                 string[]|null                         key名字不一致 → 报错
                                                                       sortBy指定的key不存在于所有对象 → 报错（sortBy是字符串时）
                                                                       sortBy是数字且对象里没有该数字key → 报错
```

---

### 取值函数

```
函数名                           输入类型                         输出          说明
────────────────────────────────────────────────────────────────────────────────────────
extractValue(item, sortBy)       any, string|number|null          any           从item里按sortBy取出要比较的值
                                                                                sortBy=null   → 返回item本身
                                                                                sortBy=string → 返回item[sortBy]
                                                                                sortBy=number → 返回item[sortBy]
```

---

### 比较函数

```
函数名                           输入类型              输出        说明
────────────────────────────────────────────────────────────────────────
compareValues(a, b)              any, any              number      返回负数/0/正数（同 sort 回调）
                                                                   两个都是 null/undefined → 返回 0
                                                                   其中一个是 null/undefined → 排最后（返回正数）
                                                                   两个都是 number → 直接相减
                                                                   两个都是 string → localeCompare + numeric:true
                                                                   类型不一致 → 报错

compareArrays(a, b)              array, array          number      逐元素调用 compareValues
                                                                   元素长度不一致 → 报错

compareObjects(a, b, keys)       object, object,       number      按 keys 顺序逐个取value
                                 string[]                          调用 compareValues 逐个比
                                                                   相同继续比下一个key
```

---

### sortBy 是数组时的多级比较函数

```
函数名                              输入类型                      输出      说明
──────────────────────────────────────────────────────────────────────────────────────
compareByMultipleKeys(a, b,         any, any, string[]|number[]   number    循环取每个key/index的value
    sortByArr)                                                               调用 compareValues 逐个比
                                                                             不同 → 停止返回结果
                                                                             相同 → 继续下一个
```

---

### 对象key标准化函数

```
函数名                           输入类型              输出          说明
────────────────────────────────────────────────────────────────────────
normalizeObjectKeys(data)        array<object>         string[]      取第一个对象的 Object.keys() 作为标准
                                                                      检查所有对象：
                                                                      key数量不同 → 报错
                                                                      key名字不同 → 报错
                                                                      key顺序不同 → 不报错，强制用标准顺序
                                                                      返回标准key顺序数组
```

---

### 主流程串联

```
函数名                           输入类型                          输出      说明
──────────────────────────────────────────────────────────────────────────────
DefaultSort(data,                array,                            array     1. validateData
    reverse, sortBy)             boolean,                                    2. validateReverse
                                 string|number|                              3. validateSortBy
                                 string[]|number[]|null                      4. 浅拷贝data（不修改原数组）
                                                                             5. 判断data元素类型走不同分支
                                                                             6. 调用对应compare函数排序
                                                                             7. reverse=true → 翻转结果
                                                                             8. 返回新数组
```

---

### 类型卡死总览表

```
参数/场景                              合法类型                        非法类型
──────────────────────────────────────────────────────────────────────────────────────
data                                   array                           其他一切
reverse                                boolean                         其他一切（含null/0/1）
sortBy                                 string(非空)                    ""
                                       number(非负非小数非NaN非Infinity) 负数/小数/NaN/Infinity
                                       string[](非空,元素非空字符串)    空数组/含空字符串/含null
                                       number[](非空,元素合法)          含负数/小数/NaN/Infinity
                                       null                            boolean/object/function
compareValues 两个值                   类型必须一致                    类型不一致 → 报错
子数组                                 长度必须一致                    长度不一致 → 报错
对象数组                               key名字和数量必须一致            不一致 → 报错
输出                                   array(新数组)                   永远不修改原数组
```