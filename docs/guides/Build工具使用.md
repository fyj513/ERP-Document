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

```bash
cd Build
./builder add -h
```

该帮助会显示 `add` 命令的使用方法和可选参数。

### 3.2 创建新库模板

```bash
cd Build
./builder add -n mylib -d "My PRAM3 library" --interactive=false
```

- `-n`, `--name`：库名称
- `-d`, `--desc`：库描述
- `--interactive=false`：非交互模式

### 3.3 构建项目

```bash
cd Build
./builder build
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
