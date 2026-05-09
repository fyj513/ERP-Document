---
title: Build工具使用
topicId: build-tool
author: PRAM Team
version: 1.0
---

# 🔧 Build工具入门

PRAM3的Build工具位于项目根目录的`Build/`文件夹中，用于**创建库模板**、**构建客户端/服务器库**和**更新工具本身**。

---

<!-- quiz -->
**题目**：Build工具不能用于以下哪项操作？

- A. 创建新库模板
- B. 构建PRAM3库
- C. 更新构建工具
- D. 部署到生产环境

**答案**：D

**解析**：Build工具的三个核心命令是`add`（创建模板）、`build`（构建库）和`update`（更新工具），不包含部署功能。
<!-- /quiz -->

---

# 📋 查看帮助

进入`Build`目录后运行：

```bash
./builder -h
```

会显示三个命令：
- `add` — 创建库模板
- `build` — 构建客户端/服务器库
- `update` — 检查并更新工具

Windows用户请使用`./builder.exe -h`。

---

<!-- quiz -->
**题目**：在Windows上查看Build工具帮助的正确命令是？

- A. `./builder -h`
- B. `./builder.exe -h`
- C. `builder help`
- D. `build.bat -h`

**答案**：B

**解析**：Windows平台使用`builder.exe`可执行文件，命令为`./builder.exe -h`。
<!-- /quiz -->

---

# ➕ 创建新库

使用`add`命令创建库模板：

**交互模式**（推荐新手）：
```bash
./builder add -i=true
```

会依次询问库名、导出路径、描述、版本、是否客户端/服务器构建等。

**非交互模式**：
```bash
./builder add -n HashFunctions -d "cryptographic hash"
```

---

<!-- quiz -->
**题目**：使用交互模式创建新库的参数是什么？

- A. `-interactive`
- B. `-i=true`
- C. `--mode=interactive`
- D. `-mode i`

**答案**：B

**解析**：交互模式使用`-i=true`参数，工具会逐步询问所需信息。
<!-- /quiz -->

---

# 🏗️ 构建项目

编写完业务代码后，在`Build`目录执行：

```bash
./builder build
```

即可构建当前PRAM3库。Windows用户使用：

```powershell
./builder.exe build
```

---

<!-- quiz -->
**题目**：编译PRAM3库的正确命令是？

- A. `./builder compile`
- B. `./builder build`
- C. `npm run build`
- D. `./build.sh`

**答案**：B

**解析**：Build工具使用`build`子命令来编译PRAM3库。
<!-- /quiz -->

---

# 📚 本课小结

## 核心知识点

1. **三个命令**：`add`创建模板、`build`构建库、`update`更新工具
2. **查看帮助**：`./builder -h`或`./builder.exe -h`
3. **创建库**：`./builder add -i=true`交互式创建
4. **构建**：`./builder build`编译当前库
5. **平台差异**：Windows用`.exe`，Unix用`./builder`

---

<!-- quiz -->
**题目**：以下关于Build工具的描述，正确的是？

- A. 只有Linux/macOS能使用builder
- B. `add`命令用于编译代码
- C. 交互模式会询问库名、版本等信息
- D. 创建库后不需要构建直接可用

**答案**：C

**解析**：交互模式`-i=true`会逐步询问库名、导出路径、描述、版本等信息。A错误，Windows也可用；B错误，add用于创建模板；D错误，需要build构建。
<!-- /quiz -->
