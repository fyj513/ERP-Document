# 图表导出目录

本目录存放 **Mermaid 等图表工具的导出文件**（PNG/SVG/PDF）。

## 📂 用途

当你需要将 Mermaid 图表导出为图片文件时（例如用于 PPT、Word 文档、分享给非技术人员），将导出文件放在这里。

## 🔄 与 Mermaid 代码块的关系

| 场景 | 存放位置 | 说明 |
|------|----------|------|
| 源代码（优先） | 文档中的 `mermaid` 代码块 | 可直接编辑、版本控制友好 |
| 导出文件 | `assets/diagrams/` | 用于外部引用、演示文稿 |

## 📝 命名规范

```
{图表类型}-{主题}-{日期}.{扩展名}
```

示例：

| 文件名 | 说明 |
|--------|------|
| `flowchart-入库流程-20250427.svg` | 入库流程图（SVG 矢量格式） |
| `er-库存数据模型-20250427.png` | 库存模块 ER 图（PNG 位图格式） |
| `sequence-下单时序-20250427.svg` | 下单时序图 |

## 🛠️ 如何导出 Mermaid 图表

### 方法一：VS Code 插件
1. 安装插件 **Markdown Preview Mermaid Support**
2. 在预览中右键图表 → 另存为图片

### 方法二：在线工具
1. 访问 [Mermaid Live Editor](https://mermaid.live/)
2. 粘贴 Mermaid 代码
3. 点击下载 PNG/SVG

### 方法三：命令行
```bash
# 安装 mermaid-cli
npm install -g @mermaid-js/mermaid-cli

# 导出 SVG
mmdc -i input.mmd -o output.svg

# 导出 PNG
mmdc -i input.mmd -o output.png
```

## ⚠️ 注意事项

1. **源文件优先**：文档中的 Mermaid 代码块是"真相来源"，导出文件只是衍生品
2. **更新时同步**：修改了 Mermaid 代码后，记得重新导出并覆盖旧文件
3. **推荐 SVG 格式**：矢量图缩放不失真，体积也更小
