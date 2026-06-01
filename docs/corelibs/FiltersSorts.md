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


## DefaultFilter 完整梳理

### 函数签名

```
DefaultFilter(data, filtervalue): bool
永远只返回 true 或 false
```

---

### 一、参数规则

#### `data` — 接受任意类型，宽松处理

```
✅ string            → 直接做字符串匹配
✅ number            → toString() 转字符串再匹配
✅ boolean           → 转成 "true"/"false" 再匹配
✅ object            → key排序后 JSON.stringify 再匹配
✅ null              → 当空字符串 "" 处理
✅ undefined         → 当空字符串 "" 处理
✅ array             → toString() 转字符串再匹配

❌ 以上全部不报错，宽松处理
```

#### `filtervalue` — 必须是 string | null | undefined

```
✅ null              → 永远返回 true
✅ undefined         → 永远返回 true
✅ ""                → 永远返回 true
✅ string            → 见下方格式规则

❌ 报错：number
❌ 报错：boolean
❌ 报错：object
❌ 报错：array
```

---

### 二、data 转字符串规则

```
data类型       转换方式                          结果例子
──────────────────────────────────────────────────────────────────
string         直接用，转小写                    "Apple" → "apple"
number         toString() 转字符串               5000 → "5000"
boolean        true→"true" false→"false"         true → "true"
null           当 ""                             null → ""
undefined      当 ""                             undefined → ""
object         key排序后JSON.stringify，转小写    {b:2,a:1} → '{"a":1,"b":2}'
array          toString()，转小写                [1,2] → "1,2"
```

---

### 三、filtervalue 处理顺序

```
第一步：filtervalue 是否为空/null/undefined → 直接返回 true

第二步：filtervalue 是否以 ! 开头 → 记录需要取反，去掉 !

第三步：识别模式（按以下顺序判断）：

        以 @  开头 → 日期模式（见第五节，待确认）
        以 ~  开头 → 正则匹配
        以 >  开头 → 数字比较
        以 <  开头 → 数字比较
        以 >= 开头 → 数字比较
        以 <= 开头 → 数字比较
        含有 *     → 通配符匹配
        以 ^  开头 → 开头匹配
        以 $  结尾 → 结尾匹配
        ^ 和 $ 同时 → 完全等于匹配
        其他        → 包含匹配（逗号分隔AND逻辑）

第四步：执行对应模式的匹配

第五步：如果第二步记录了取反 → 对结果取反

第六步：返回最终 bool
```

---

### 四、各模式详细规则

#### 模式一：包含匹配（默认）

```
触发：普通字符串，没有任何特殊符号
规则：string.includes(keyword)，不区分大小写
逗号：逗号分隔多关键词，AND逻辑，全部包含才true

例子：
  "张"        → data含"张"返回true
  "apple"     → 不区分大小写
  "张三,销售"  → 同时含"张三"和"销售"才true
```

#### 模式二：开头匹配（`^`）

```
触发：filtervalue 以 ^ 开头，且不以 $ 结尾
规则：string.startsWith(keyword)，不区分大小写

例子：
  "^张"   → data以"张"开头返回true
  "^PO"   → data以"PO"开头返回true
```

#### 模式三：结尾匹配（`$`）

```
触发：filtervalue 以 $ 结尾，且不以 ^ 开头
规则：string.endsWith(keyword)，不区分大小写

例子：
  "丰$"    → data以"丰"结尾返回true
  "123$"   → data以"123"结尾返回true
```

#### 模式四：完全等于（`^...$`）

```
触发：filtervalue 同时以 ^ 开头且以 $ 结尾
规则：string === keyword，不区分大小写

例子：
  "^张三$"     → data完全等于"张三"返回true
  "^approved$" → 不区分大小写
```

#### 模式五：通配符（`*`）

```
触发：filtervalue 含有 *
规则：* 替换成正则 .*，做正则匹配，不区分大小写

例子：
  "PO*001"   → PO开头001结尾
  "*三"       → 以三结尾
  "张*"       → 以张开头
  "*2024*"   → 含2024
  "A*D*G*"   → 多段通配
```

#### 模式六：正则匹配（`~`）

```
触发：filtervalue 以 ~ 开头
规则：去掉~，转小写，new RegExp，做match
注意：无效正则不报错，返回false

例子：
  "~^\d{4}$"           → 匹配纯4位数字
  "~^PO-\d{4}-\d{3}$"  → 匹配采购单格式
  "~[invalid"           → 无效正则，返回false
```

#### 模式七：数字比较（`>` `<` `>=` `<=`）

```
触发：filtervalue 以 > 或 < 开头
规则：data能转成数字才比较，转不了就跳过走包含匹配
支持：> < >= <=

例子：
  ">3000"    → data > 3000
  "<=200"    → data <= 200
  ">=99.5"   → 支持小数
  
注意：
  data="hello" + filtervalue=">3000"
  → hello转不成数字 → 跳过数字比较 → 走包含匹配 → false
  → 不报错
```

#### 模式八：取反（`!`）

```
触发：filtervalue 以 ! 开头
规则：对最终结果取反，可叠加到任意模式
注意：! 只在最前面，处理完后去掉再走其他模式

例子：
  "!张"        → 不含"张"返回true
  "!^张"       → 不以"张"开头返回true
  "!^张三$"    → 不完全等于"张三"返回true
  "!张三,销售"  → 不是(同时含张三和销售)返回true
```

#### 模式九：日期（`@`）⚠️ 待确认

```
触发：filtervalue 以 @ 开头
详见待确认清单
```

---

### 五、待确认清单

```
⚠️ 日期处理：
  "@2024"           只有年，怎么处理？
  "@2024-01"        只有年月，怎么处理？
  "@2024-01-15"     完整日期，怎么处理？
  "@2024-01-01|2024-12-31"  日期范围，怎么处理？

  方案A：转字符串匹配（简单，不需要改datetime库）
  方案B：转时间戳数值比较（严谨，需要datetime库新增接口）
```

---

### 六、边界情况

```
filtervalue=""        → true（空条件保留所有）
filtervalue=null      → true
filtervalue=undefined → true
data=null + fv="张"   → "" 不含"张" → false
data=null + fv=""     → true（空条件）
data="" + fv=""       → true
"~[invalid"           → 无效正则，返回false，不报错
">abc"                → abc转不成数字，跳过，走包含匹配
```

---

### 七、一张图总结

```
DefaultFilter(data, filtervalue)
         │
         ├─ filtervalue是null/undefined/"" → 返回 true
         ├─ filtervalue不是string          → 报错
         │
         ▼
    data转成字符串（见第二节）
         │
         ├─ filtervalue以!开头 → 记录取反，去掉!
         │
         ▼
    识别模式：
         ├─ @ → 日期模式（待确认）
         ├─ ~ → 正则匹配
         ├─ >/< → 数字比较（转不了数字→跳过→包含匹配）
         ├─ 含* → 通配符
         ├─ ^开头且$结尾 → 完全等于
         ├─ ^开头 → 开头匹配
         ├─ $结尾 → 结尾匹配
         └─ 其他 → 包含匹配（逗号AND逻辑）
         │
         ▼
    需要取反 → 结果翻转
         │
         ▼
    返回 true 或 false
```



## DefaultSort 完整梳理

### 函数签名

```
DefaultSort(data, reverse=false, sortBy=null) → array
永远返回新数组，不修改原数组
```

---

### 一、参数规则

#### `data` — 必须是数组，否则报错

```
✅ 允许：[]                        空数组，直接返回[]
✅ 允许：[1, 2, 3]                 数字数组
✅ 允许：['a', 'b']                字符串数组
✅ 允许：[true, false]             布尔数组
✅ 允许：[[1,'a'], [2,'b']]        数组套数组
✅ 允许：[{name:'Alice'}, ...]     对象数组
✅ 允许：含null/undefined的数组    → null/undefined排最后，不报错
✅ 允许：混搭数组                  → 按类型分组排序，不报错

❌ 报错：null
❌ 报错：undefined
❌ 报错："hello"
❌ 报错：42
❌ 报错：{}
❌ 报错：true
```

---

#### `reverse` — 必须是布尔值，否则报错

```
✅ 允许：false  → 升序（默认）
✅ 允许：true   → 降序

❌ 报错：null
❌ 报错："true" / "false"
❌ 报错：0 / 1
❌ 报错：{}
```

---

#### `sortBy` — 五种合法类型

```
✅ 允许：null                → 直接比元素本身
✅ 允许：string（非空）      → 取对象的这个key的value来比
✅ 允许：number（正整数）    → 取数组/JSONB对象的第N个位置来比
✅ 允许：string[]（非空）    → 多个key依次比
✅ 允许：number[]（非空）    → 多个位置依次比

❌ 报错：""                  空字符串
❌ 报错：-1                  负数
❌ 报错：1.5                 小数
❌ 报错：NaN
❌ 报错：Infinity
❌ 报错：[]                  空数组
❌ 报错：['name', 0]         混合类型数组
❌ 报错：['', 'name']        含空字符串
❌ 报错：[0, -1]             含负数
❌ 报错：true / false
❌ 报错：{}
❌ 报错：function
```

---

### 二、混搭数据的优先级规则

**data里元素类型混杂时，按以下优先级排列，不报错：**

```
优先级（升序，从小到大）：

第一组  number + string   → 混在一起，按自然排序比较
第二组  boolean           → false 排 true 前面
第三组  array             → 多个array之间正常逐元素比较
第四组  object            → 多个object之间保持原顺序
第五组  null              → 排最后
第六组  undefined         → 压底

示例：
DefaultSort([{a:1}, 'hello', 42, true, null, [1,2], undefined, false])
→ [42, 'hello', false, true, [1,2], {a:1}, null, undefined]
```

**reverse=true 时：**

```
第一到四组整体翻转
null / undefined 永远压底，不参与翻转

示例：
DefaultSort([{a:1}, 'hello', 42, true, null, [1,2], undefined], true)
→ [42, 'hello', true, [1,2], {a:1}, null, undefined]
```

---

### 三、sortBy=null 时的处理规则

#### data 是普通值数组

```
number         → 直接数值比较          [3, 1, 2]      → [1, 2, 3]
string         → localeCompare         自然排序，'10'在'5'后面
boolean        → false < true          [true, false]  → [false, true]
null           → 排最后                [3, null, 1]   → [1, 3, null]
undefined      → 压底                  [3, undefined] → [3, undefined]
```

#### data 是数组套数组

```
→ 逐元素比较，先比第0个，相同再比第1个，以此类推
→ 子数组长度不一致：短的排前面（和短字符串一样）
   [1,2] < [1,2,3]（前两个相同，短的排前面）
→ 元素含null/undefined：null/undefined排最后
→ 子数组之间的元素混搭：按混搭优先级处理
```

#### data 是对象数组

```
→ 取第一个对象的key顺序作为标准
→ 按key顺序逐个value比较
→ 某个对象缺少key：当null处理，排最后
→ key顺序不同：不报错，强制按第一个对象的key顺序比
→ value是对象或数组：按混搭优先级，排在普通值后面
```

---

### 四、sortBy=字符串 时的处理规则

```
→ data是对象数组
→ 取每个对象的 obj[sortBy] 的value来比
→ 某个对象没有这个key：当null处理，排最后
→ value是对象或数组：按混搭优先级，排在普通值后面
→ value比较规则见第七节
```

---

### 五、sortBy=数字 时的处理规则

```
→ data是数组套数组：取 arr[sortBy] 的value来比
→ data是JSONB对象数组：取对象第N个key对应的value来比
   （JSONB的key是字符串，但可以用数字索引定位到第N个key）
→ 某个位置缺失：当null处理，排最后
→ value比较规则见第七节
```

---

### 六、sortBy=字符串数组 时的处理规则

```
→ data是对象数组
→ 依次按每个key比，相同才看下一个
→ 某个对象缺key：当null处理，排最后
→ value比较规则见第七节
```

---

### 七、sortBy=数字数组 时的处理规则

```
→ data是数组套数组 或 JSONB对象数组
→ 依次按每个位置比，相同才看下一个
→ 某个位置缺失：当null处理，排最后
→ value比较规则见第七节
```

---

### 八、value 比较的统一规则

**每次两两PK，按以下顺序判断：**

```
1. 两个都是 null        → 相等，顺序不变
2. 两个都是 undefined   → 相等，顺序不变
3. 一个null一个undefined → null排undefined前面
4. 其中一个是null/undefined → null/undefined排后面，另一个排前面
5. 两个都是 object      → 相等，顺序不变（保持原顺序）
6. 一个object一个非object → object排后面
7. 两个都是 array       → 逐元素比较
8. 一个array一个非array  → array排后面（但object在array后面，见混搭规则）
9. 两个都是 boolean     → false < true
10. 一个boolean一个非boolean → boolean排后面
11. 两个都是 number     → 数值比较
12. 两个都是 string     → localeCompare + numeric:true（'10'在'5'后面）
13. 一个string一个number → 统一转string再用localeCompare
```

---

### 九、一张图总结

```
DefaultSort(data, reverse, sortBy)
         │
         ├─ data不是数组        → 报错
         ├─ reverse不是布尔     → 报错
         └─ sortBy类型非法      → 报错
         │
         ▼
    浅拷贝data（不修改原数组）
         │
         ├─ sortBy=null
         │      ├─ 元素是普通值  → 直接比
         │      ├─ 元素是数组    → 逐元素比
         │      ├─ 元素是对象    → 按第一个对象key顺序比
         │      └─ 元素混搭      → 按类型优先级分组排
         │
         ├─ sortBy=string       → obj[key] 取value比
         ├─ sortBy=number       → item[n] 取value比
         ├─ sortBy=string[]     → 多key依次比
         └─ sortBy=number[]     → 多位置依次比
                  │
                  ▼
         比较时遇到混搭值 → 按混搭优先级处理
         缺失key/位置    → 当null处理排最后
                  │
                  ▼
         reverse=true → 翻转（null/undefined仍压底）
                  │
                  ▼
            返回新数组
```
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

// ❌ 删掉这两条：
expectError(() => DefaultSort([
    {dept:'销售部', level:'10'},
    {dept:'技术部'},
]), "对象数组-key数量不一致")

expectError(() => DefaultSort([
    {dept:'销售部', level:'10'},
    {dept:'技术部', salary:'5'},
]), "对象数组-key名字不一致")

// ✅ 改成这些：
expectResult(
    DefaultSort([
        {name:'Bob',  dept:'Sales'},
        {name:'Alice'            },   // 没有dept
        {name:'Charlie',dept:'IT'},
    ], false, 'dept'),
    [
        {name:'Charlie', dept:'IT'   },
        {name:'Bob',     dept:'Sales'},
        {name:'Alice'                },   // dept缺失=null → 排最后
    ],
    "sortBy字符串-缺失key当null排最后")

expectResult(
    DefaultSort([
        {dept:'Sales', level:'10'},
        {dept:'IT'              },    // 没有level
        {dept:'IT',    level:'5'},
    ], false, ['dept','level']),
    [
        {dept:'IT',    level:'5' },
        {dept:'IT'               },   // level缺失=null → 排最后
        {dept:'Sales', level:'10'},
    ],
    "sortBy字符串数组-缺失key当null排最后")



// ❌ 删掉这条：
expectError(() => DefaultSort([['a',1],['b']]), "子数组长度不一致")

// ✅ 改成这些：
expectResult(
    DefaultSort([['b',2],['a'],['a',1]], false, null),
    [['a'],['a',1],['b',2]],
    "子数组长度不一致-短的排前面")

// 原理和字符串一样：
// 'a' < 'ab' < 'b'
// ['a'] < ['a',1] < ['b',2]```

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


// ✅ 改成这些：
expectResult(
    DefaultSort([[2,3],[1,null],[1,1]], false, [0,1]),
    [[1,1],[1,null],[2,3]],
    "子数组含null-null排最后")

expectResult(
    DefaultSort([[2,3],[1,undefined],[1,1]], false, 1),
    [[1,1],[2,3],[1,undefined]],
    "子数组含undefined-undefined排最后")
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



// ✅ 改成这些：
expectResult(
    DefaultSort([[2,3],[1,null],[1,1]], false, [0,1]),
    [[1,1],[1,null],[2,3]],
    "子数组含null-null排最后")

expectResult(
    DefaultSort([[2,3],[1,undefined],[1,1]], false, 1),
    [[1,1],[2,3],[1,undefined]],
    "子数组含undefined-undefined排最后")
## 八、`sortBy` 其他非法类型

```javascript
expectError(() => DefaultSort([1,2], false, true),      "sortBy=布尔true");
expectError(() => DefaultSort([1,2], false, false),     "sortBy=布尔false");
expectError(() => DefaultSort([1,2], false, {}),        "sortBy=普通对象");
expectError(() => DefaultSort([1,2], false, ()=>{}),    "sortBy=函数");
```


```
// ✅ 全部新增：

// sortBy=null 直接排boolean
expectResult(
    DefaultSort([true, false, true, false]),
    [false, false, true, true],
    "boolean升序-false排前面")

expectResult(
    DefaultSort([true, false, true, false], true),
    [true, true, false, false],
    "boolean降序-true排前面")

// 对象数组里有boolean字段
expectResult(
    DefaultSort([
        {name:'Bob',   approved:true },
        {name:'Alice', approved:false},
        {name:'Carol', approved:true },
    ], false, 'approved'),
    [
        {name:'Alice', approved:false},
        {name:'Bob',   approved:true },
        {name:'Carol', approved:true },
    ],
    "sortBy字符串-boolean字段升序")

expectResult(
    DefaultSort([
        {name:'Bob',   approved:true },
        {name:'Alice', approved:false},
    ], true, 'approved'),
    [
        {name:'Bob',   approved:true },
        {name:'Alice', approved:false},
    ],
    "sortBy字符串-boolean字段降序")

// boolean和null混合
expectResult(
    DefaultSort([true, null, false, undefined, true], false),
    [false, true, true, null, undefined],
    "boolean含null和undefined-null排最后")
```
---

```
// ✅ 正常：JSONB对象-sortBy=数字-按第0个key的value排序
expectResult(
    DefaultSort([
        { dept:'Sales', level:'10', name:'Alice' },
        { dept:'IT',    level:'5',  name:'Bob'   },
        { dept:'HR',    level:'3',  name:'Carol'  },
    ], false, 0),
    [
        { dept:'HR',    level:'3',  name:'Carol' },
        { dept:'IT',    level:'5',  name:'Bob'   },
        { dept:'Sales', level:'10', name:'Alice' },
    ],
    "sortBy数字-JSONB对象-按第0个key(dept)排序");

// ✅ 正常：JSONB对象-sortBy=数字-按第1个key的value排序（数字字符串）
expectResult(
    DefaultSort([
        { dept:'Sales', level:'10', name:'Alice' },
        { dept:'IT',    level:'5',  name:'Bob'   },
        { dept:'HR',    level:'3',  name:'Carol' },
    ], false, 1),
    [
        { dept:'HR',    level:'3',  name:'Carol' },
        { dept:'IT',    level:'5',  name:'Bob'   },
        { dept:'Sales', level:'10', name:'Alice' },
    ],
    "sortBy数字-JSONB对象-按第1个key(level)排序-数字字符串正确排序");

// ✅ 正常：JSONB对象-sortBy=数字-降序
expectResult(
    DefaultSort([
        { dept:'Sales', level:'10', name:'Alice' },
        { dept:'IT',    level:'5',  name:'Bob'   },
        { dept:'HR',    level:'3',  name:'Carol' },
    ], true, 0),
    [
        { dept:'Sales', level:'10', name:'Alice' },
        { dept:'IT',    level:'5',  name:'Bob'   },
        { dept:'HR',    level:'3',  name:'Carol' },
    ],
    "sortBy数字-JSONB对象-降序");

// ✅ 正常：JSONB对象-sortBy=数字数组-先按第0个key再按第1个key
expectResult(
    DefaultSort([
        { dept:'Sales', level:'10', name:'Alice' },
        { dept:'IT',    level:'5',  name:'Bob'   },
        { dept:'Sales', level:'3',  name:'Carol' },
        { dept:'IT',    level:'10', name:'Dave'  },
    ], false, [0, 1]),
    [
        { dept:'IT',    level:'5',  name:'Bob'   },
        { dept:'IT',    level:'10', name:'Dave'  },
        { dept:'Sales', level:'3',  name:'Carol' },
        { dept:'Sales', level:'10', name:'Alice' },
    ],
    "sortBy数字数组-JSONB对象-先按第0个key(dept)再按第1个key(level)");

// ✅ 正常：JSONB对象-sortBy=数字数组-三级索引
expectResult(
    DefaultSort([
        { dept:'Sales', level:'10', name:'Zoe'   },
        { dept:'IT',    level:'5',  name:'Bob'   },
        { dept:'Sales', level:'10', name:'Alice' },
        { dept:'Sales', level:'3',  name:'Carol' },
    ], false, [0, 1, 2]),
    [
        { dept:'IT',    level:'5',  name:'Bob'   },
        { dept:'Sales', level:'3',  name:'Carol' },
        { dept:'Sales', level:'10', name:'Alice' },  // 前两个key相同，比第三个key name
        { dept:'Sales', level:'10', name:'Zoe'   },
    ],
    "sortBy数字数组-JSONB对象-三级索引");

// ✅ 正常：JSONB对象-sortBy=数字数组-降序
expectResult(
    DefaultSort([
        { dept:'Sales', level:'10', name:'Alice' },
        { dept:'IT',    level:'5',  name:'Bob'   },
        { dept:'Sales', level:'3',  name:'Carol' },
    ], true, [0, 1]),
    [
        { dept:'Sales', level:'10', name:'Alice' },
        { dept:'Sales', level:'3',  name:'Carol' },
        { dept:'IT',    level:'5',  name:'Bob'   },
    ],
    "sortBy数字数组-JSONB对象-降序");

// ✅ 正常：JSONB对象-缺失key当null排最后
expectResult(
    DefaultSort([
        { dept:'Sales', level:'10' },
        { dept:'IT'               },   // 没有level，第1个key=null
        { dept:'HR',    level:'3'  },
    ], false, 1),
    [
        { dept:'HR',    level:'3'  },
        { dept:'Sales', level:'10' },
        { dept:'IT'                },   // null排最后
    ],
    "sortBy数字-JSONB对象-缺失key当null排最后");

// ✅ 正常：所有value相同-保持原顺序
expectResult(
    DefaultSort([
        { dept:'Sales', level:'10' },
        { dept:'Sales', level:'10' },
        { dept:'Sales', level:'10' },
    ], false, [0, 1]),
    [
        { dept:'Sales', level:'10' },
        { dept:'Sales', level:'10' },
        { dept:'Sales', level:'10' },
    ],
    "sortBy数字数组-JSONB对象-所有value相同保持原顺序");

// ❌ 报错：index超出对象key数量
expectError(() => DefaultSort([
    { dept:'Sales', level:'10' },
], false, 99),
    "sortBy数字-JSONB对象-index超出key数量");

// ❌ 报错：数字数组含负数
expectError(() => DefaultSort([
    { dept:'Sales', level:'10' },
], false, [0, -1]),
    "sortBy数字数组-JSONB对象-含负数");

// ❌ 报错：数字数组含小数
expectError(() => DefaultSort([
    { dept:'Sales', level:'10' },
], false, [0, 1.5]),
    "sortBy数字数组-JSONB对象-含小数");
```


## 混搭排序优先级

```
第一组：number + string   → 正常比较，混在一起按自然排序
第二组：boolean           → false 先，true 后
第三组：array             → 保持原顺序
第四组：object            → 保持原顺序，排array后面
第五组：null              → 排最后
第六组：undefined         → 压底
```

```
// ✅ 完整混搭
expectResult(
    DefaultSort([{a:1}, 'hello', 42, true, null, [1,2], undefined, false, 'world', 10]),
    [10, 42, 'hello', 'world', false, true, [1,2], {a:1}, null, undefined],
    "混搭-完整优先级排序");

// ✅ number 和 string 混在一起自然排序
expectResult(
    DefaultSort([10, '9', 3, '20', 5]),
    [3, 5, '9', 10, '20'],
    "混搭-数字和数字字符串自然排序");

// ✅ boolean 排在数字字符串后面
expectResult(
    DefaultSort([true, 1, 'hello', false]),
    [1, 'hello', false, true],
    "混搭-boolean排在数字字符串后面");

// ✅ array 排在 boolean 后面
expectResult(
    DefaultSort([[1,2], true, 'hello', false]),
    ['hello', false, true, [1,2]],
    "混搭-array排在boolean后面");

// ✅ object 排在 array 后面
expectResult(
    DefaultSort([{a:1}, [1,2], 'hello', {b:2}]),
    ['hello', [1,2], {a:1}, {b:2}],
    "混搭-object排在array后面");

// ✅ null 排在 object 后面
expectResult(
    DefaultSort([null, {a:1}, 'hello', [1,2]]),
    ['hello', [1,2], {a:1}, null],
    "混搭-null排在object后面");

// ✅ undefined 压底
expectResult(
    DefaultSort([undefined, null, {a:1}, 'hello']),
    ['hello', {a:1}, null, undefined],
    "混搭-undefined压底");

// ✅ reverse=true 整体翻转，但null/undefined仍排最后
expectResult(
    DefaultSort([{a:1}, 'hello', 42, true, null, [1,2], undefined], true),
    [42, 'hello', true, [1,2], {a:1}, null, undefined],
    "混搭-降序-null和undefined仍排最后");

// ✅ 多个array保持原顺序
expectResult(
    DefaultSort([[3,2], [1,2], [3,1]]),
    [[1,2], [3,1], [3,2]],
    "混搭-多个array之间正常比较");

// ✅ 多个object保持原顺序
expectResult(
    DefaultSort([{b:2}, {a:1}, {c:3}]),
    [{b:2}, {a:1}, {c:3}],
    "混搭-多个object之间保持原顺序");
```

排序优先级（升序）：
  1. number + string  ← 最小，排最前
  2. boolean
  3. array
  4. object
  5. null
  6. undefined        ← 最大，排最后

reverse=true：
  1~4 整体翻转
  5~6 null/undefined 永远压底，不参与翻转
  
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

