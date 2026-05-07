## 1. 进入 Build 目录

bash

运行

```
cd Build
```

## 2. 运行帮助命令，检查是否正常

bash

运行

```
./builder -h
```

出现以下内容说明 build 工具正常：

plaintext

```
builder
Usage:
[options] COMMAND

Commands:
add      Setup scaffolding for a new library
build    PRAM3 library builder, handles building the client and server libraries for PRAM
update   Check for updates to this tool and apply them if one is found

Options:
-h,--help
```

## 3. 进入 Source 目录（按实际路径修改）

bash

运行

```
cd /workspaces/pram3_corelibs/Source
```

## 4. 运行交互式创建命令

bash

运行

```
../Build/builder add -i=true
```

## 5. 按提示输入信息

- Library name：输入库名，如 `HashFunctions`
- Export path：直接回车（使用默认）
- Description：功能描述，如 `cryptographic hash function implementations`
- Version：直接回车（默认 `0.1.0`）
- Build for client?：输入 `y`
- Build for server?：输入 `n`（按项目需求选择）
- Global variables：直接回车
- Dependencies：直接回车
- Target directory：直接回车

执行后会在 `Source/HashFunctions` 自动生成完整库模板。

## 6. 开始写代码

在生成的模板目录中编写业务代码。

## 7. 写完代码后编译（生成成品）

bash

运行

```
cd Build
./build.sh
```

## 8. 提交并推送到远程仓库

bash

运行

```
# 保存所有修改
git add .

# 提交版本
git commit -m "完成哈希函数开发"

# 推送到云端保存
git push
```





































# Build 工具使用指南

> 本文档说明项目根目录下 `Build/` 目录中的构建工具使用方式。

## 文档目的与适用场景

### 目的

说明 `Build/` 目录下工具的核心用途：

- `builder add`：创建 PRAM3 库模板
- `builder build`：构建 PRAM3 客户端/服务器库
- `builder update`：更新构建工具本身

本指南不介绍整个项目的编译流程，只说明 `Build/` 工具的使用方法。

### 适用人员与场景

- 需要使用 `builder add` 快速生成库模板的开发者
- 需要执行 `builder build` 构建 PRAM3 库的开发者
- 需要查看 `builder -h`、确认参数用法的开发者
- 需要排查 `Build/` 工具用法的维护人员



## 1. 目录结构

项目根目录下存在 `Build/` 目录，内部包含构建工具文件：

- `build.bat` — Windows 批处理脚本
- `build.sh` — Linux / macOS Shell 脚本
- `builder` — 可执行构建工具（适用于类 Unix 系统）
- `builder.exe` — Windows 可执行构建工具
- `build.pkr.hcl` — 可能的构建配置文件

## 2. 运行方式

### 2.1 查看帮助

在 `Build/` 目录下运行帮助命令：

```bash
cd Build
./builder -h
```

在 Windows PowerShell 中：

```powershell
cd Build
./builder.exe -h
```

### 2.2 帮助输出内容

帮助信息会展示工具支持的命令和选项。这个 `Build` 工具不是用于整个项目的通用编译，而是用于 PRAM3 库的构建和管理，主要负责：

- 库模板创建
- 客户端/服务器库构建
- 构建工具自身的更新

常见命令及其含义：

- `add` — 创建一个新的库模板，用于快速生成 PRAM3 库的初始目录结构和配置文件。
- `build` — 构建 PRAM3 的客户端和服务器库，执行当前库的打包、编译或生成操作。
- `update` — 检查并应用构建工具本身的更新，确保你使用的 `builder` 版本是最新的。

常见选项及其作用：

- `-h`, `--help` — 显示帮助信息。
- `-i`, `--interactive` — 是否进入交互模式，交互模式会逐步询问参数值。
- `-n`, `--name` — 指定要创建的库名称。
- `-d`, `--desc` — 指定要创建的库描述。
- `-v`, `--version` — 指定库版本号，格式为 `major.minor.build`。
- `-c`, `--client` — 指示是否为客户端环境构建库。
- `-s`, `--server` — 指示是否为服务器环境构建库。
- `-p`, `--export-path` — 指定导出库文件的目标路径。
- `-g`, `--globals` — 指定该库向外提供的全局变量列表。
- `--deps`, `--depends-on` — 指定库依赖关系，格式为 `libName:versionKind:version`。

## 3. 常用示例

### 3.1 查看 `add` 子命令帮助

在 Linux/macOS 和 Windows 上，`add` 命令参数相同：

```bash
cd Build
./builder add -h
```

如果你在 Windows 下使用可执行文件，命令也一致，只是改为：

```powershell
cd Build
./builder.exe add -h
```

该帮助会显示 `add` 命令的使用方法和可选参数。

### 3.2 创建新库模板

创建新库模板时，Linux/macOS 和 Windows 的命令写法相同：

```bash
cd Build
./builder add -n keyDerivation -d "Used to derive encryption keys from user credentials" --interactive=false
```

Windows 下也可以这样写：

```powershell
cd Build
./builder.exe add -n keyDerivation -d "Used to derive encryption keys from user credentials" --interactive=false
```

如果你希望使用交互模式，可以添加 `-i=true`：

```bash
cd Build
./builder add -i=true
```

交互模式会逐步询问：

- Library name
- Export path
- Description
- Version
- Build for client?
- Build for server?
- Global variables
- Dependencies
- Target directory

### 3.3 构建项目

构建当前库时，Linux/macOS 和 Windows 的命令也是相同的：

```bash
cd Build
./builder build
```

或在 Windows 下：

```powershell
cd Build
./builder.exe build
```

## 4. 使用建议

- 如果你使用的是 Windows，优先使用 `builder.exe` 或 `build.bat`。
- 如果你使用 macOS / Linux，优先使用 `./builder` 或 `build.sh`。
- 先使用 `-h` 查看可用命令，再执行具体构建操作。
- 如果出现权限问题，可先执行 `chmod +x builder`。

## 5. 适用人员

本文档适用于需要使用项目构建工具的开发人员，尤其是：

- 负责库模板创建的开发者
- 负责客户端/服务器库构建的开发者
- 需要调试或升级 `Build/` 目录下工具的维护人员
