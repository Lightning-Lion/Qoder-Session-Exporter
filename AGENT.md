# Qoder Session Exporter

导出 Qoder App 聊天记录为可离线浏览的静态 HTML。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│ 浏览器侧 (Qoder Electron webview)                           │
│                                                             │
│   expand-disclosure.js    export-session.js                 │
│   ────────────────        ────────────────                  │
│   展开所有折叠区域 +      收集样式 → 提取资源 →              │
│   清理高度限制             替换路径 → 嵌入数据块              │
│                            → 下载单一 HTML                   │
└──────────┬──────────────────────────────────────┘           │
           │ 用户手动下载 exported_<ts>.html                   │
           ▼                                                   │
┌─────────────────────────────────────────────────────────────┐
│ 本地侧 (终端)                                               │
│                                                             │
│   python3 fix-font.py exported_<ts>.html                    │
│                                                             │
│   ┌──────────────────────────────────────────────────┐      │
│   │ Step 1  复制 HTML 到 sessions/                   │      │
│   │ Step 2  提取 __qoder_assets__ 数据块              │      │
│   │         解码 data URI → sessions/assets/         │      │
│   │ Step 3  复制 aicoding-seti.woff 到 sessions/     │      │
│   │ Step 4  vscode-file:// 回退（fetch 失败资源）     │      │
│   │ Step 5  修复 ../../media/ 字体路径                │      │
│   │ Step 6  CSS 去重 + 压缩 + 外置为 styles.css      │      │
│   └──────────────────────────────────────────────────┘      │
│                                                             │
│   ./serve.sh → 启动 HTTP 服务并自动打开浏览器                │
└─────────────────────────────────────────────────────────────┘
```

## 工作流程

### 第 0 步：准备（浏览器控制台）

在 Qoder 的聊天页面打开开发者工具（F12 → Console），执行：

1. 复制 `expand-disclosure.js` 全部内容，粘贴执行
   - `expandAll()` — 展开所有折叠的对话区域
   - `removeAllConstraints()` — 清理聊天框的高度限制，防止内容截断

### 第 1 步：导出（浏览器控制台）

2. 复制 `export-session.js` 全部内容，粘贴执行
   - 收集页面所有 `<style>` 和外部样式表
   - 扫描 CSS 中的 `vscode-file://` URL，用 `fetch()` 获取内容并转为 data URI
   - 在样式中将 URL 替换为 `./assets/<filename>` 形式
   - 将 data URI 映射表以 `<script id="__qoder_assets__" type="application/json">` 嵌入 HTML 末尾
   - 注入 `@font-face { font-family: 'qoder-seti'; src: url('./aicoding-seti.woff') }`
   - 浏览器自动下载单一 `exported_<ts>.html` 文件

### 第 2 步：修复（终端）

3. `python3 fix-font.py /path/to/exported_<ts>.html`

自动执行以下流程：

| 步骤 | 操作 | 说明 |
|------|------|------|
| **1** | 复制到 `sessions/` | 在脚本同级的 `sessions/` 目录创建工作副本 |
| **2** | 拆分 assets | 从 HTML 提取 `__qoder_assets__` 数据块，解码 data URI 为 `sessions/assets/*` 文件，并移除数据块 |
| **3** | 字体复制 | 将 Qoder.app 内的 `aicoding-seti.woff` 复制到 `sessions/`，修正 `@font-face` 引用 |
| **4** | vscode-file 回退 | 扫描 HTML 中残留的 `vscode-file://vscode-app/` 引用（上一步 fetch 失败的资源），从本地 Qoder.app 复制并替换路径 |
| **5** | media 字体修复 | 将 `../../media/xxxx.ttf/woff` 等相对路径替换为本地文件 |
| **6** | CSS 优化 | 去重（移除完全相同的样式块）、压缩（去掉注释和多余空白）、外置（所有 `<style>` 合并写出 `styles.css`，HTML 中替换为 `<link>`，大小从 ~11 MB → ~6 MB） |

### 第 3 步：预览

4. 运行 `./serve.sh`（或 `python3 -m http.server 8080 -d sessions`）

由于 `sessions/` 中的资源使用相对路径引用，直接双击 HTML 文件可能因 `file://` 协议限制无法加载外部资源，建议通过 HTTP 服务预览。

## 输出目录结构

```
sessions/
├── exported_<ts>.html      # ~1 MB，纯对话内容 + <link> 引用 styles.css
├── styles.css               # ~6.4 MB，压缩后的全量 CSS
├── assets/                  # SVG 图标、小图片等（从 data URI 解码而来）
│   └── *.svg
├── aicoding-seti.woff      # qoder-seti 图标字体
├── aicoding-icon-0123.ttf  # codicon 图标字体
├── codicon.ttf
├── iconfont.woff
├── InstrumentSans*.ttf      # UI 正文字体
├── logo-*.woff              # Logo 字体
├── cline-bot.woff           # 扩展图标字体
└── *.svg                    # 语言图标（延用 vscode-file 回退复制出来的文件）
```

## 关键设计决策

### 为什么不在 export-session.js 中全部处理完？

因为浏览器环境（Qoder webview）可以访问 `vscode-file://` 协议来 fetch 资源，但**无法写入文件系统**。只能通过 Blob 下载单一文件。而本地终端可以读写文件系统，适合做拆分、复制、压缩等重操作。

### 为什么 CSS 要外置？

原始的 Qoder 页面包含大量 CSS：主题变量、SparkDesign tokens、Tailwind 框架、codicon 图标字体映射等，全部内联到 `<style>` 中总大小约 **11.5 MB**，占导出 HTML 的 **90%**。外置后 HTML 降至约 1 MB，样式文件通过 `<link>` 异步加载，不阻塞首屏渲染。

### 两个阶段的资源处理

| 资源类型 | export-session.js 处理 | fix-font.py 处理 |
|----------|----------------------|-----------------|
| SVG 图标 / 小图片 | fetch → data URI → 嵌入 HTML 数据块 | 解码 data URI → 写为 `assets/` 文件 |
| aicoding-seti.woff | 注入 `@font-face` 引用 `./aicoding-seti.woff` | 从 Qoder.app 复制到 `sessions/` |
| vscode-file:// 资源 | 尝试 fetch（可能失败） | 本地文件系统回退复制 |
| ../../media/ 字体 | 保持原路径 | 替换为本地文件 |
| CSS 样式 | 原样收集 | 去重 + 压缩 + 外置 |