# 知模实验室：独立安装源码

本目录由当前 `project1` 源码整理，保留现有应用的前后端、必要配置、公开示例数据、内置模型、字体和图标。所有命令在 Windows PowerShell 中执行。

默认前端地址为 **http://127.0.0.1:19032/**，后端地址为 **http://127.0.0.1:19031/**。本目录的依赖与运行数据独立保存。

## 1. 准备环境

- Python：64 位 3.11 或 3.12（本目录环境为 3.13.15，已实测可用）。
- Node.js：24.12 或以上（含 npm）；`frontend/package.json` 的 engines 另允许 22.18.x。

## 2. 安装依赖

在项目根目录依次执行，每条命令成功后再执行下一条：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
npm.cmd --prefix .\frontend ci --include=dev --no-audit --no-fund
```

Python 依赖安装到 `.venv/`，前端依赖安装到 `frontend/node_modules/`。直接使用虚拟环境的 Python 路径，无需激活脚本。

前端启动时会自己寻找解释器，顺序为：`FOREST_PYTHON` 环境变量 → 项目根 `.venv/` → `.local/.venv/`。只要虚拟环境建在项目根目录，就不需要设置任何环境变量；三处都找不到时会直接报出已尝试的路径。

## 3. 内置模型（已随项目提供，不需要下载）

| 模型 | 位置 | 体积 |
| --- | --- | --- |
| 语义检索 bge-small-zh-v1.5 | `frontend/public/models/Xenova/bge-small-zh-v1.5/` | 23.3 MB |
| 语音输入 SenseVoice | `data/models/sensevoice/` | 230.1 MB |

两者都已随项目提供且不应删除：缺少语义模型时，语义召回通道会关闭、方法搜索退化为纯文本匹配（浏览器控制台提示模型不可用）；缺少语音模型时语音接口直接返回 503。前端用 `env.allowRemoteModels = false` 禁止联网取模型，只从本地 `/models/` 读取。

任何 Vite 命令（`dev`／`build`／`preview`）加载配置时，都会把 `frontend/public/` 同步到 `.local/public/`，模型随之出现在浏览器可访问的路径下，这一步是自动的。

核对文件是否完整（只看体积，不联网）：

```powershell
Get-ChildItem .\frontend\public\models\Xenova\bge-small-zh-v1.5 -Recurse -File | Measure-Object Length -Sum
Get-ChildItem .\data\models\sensevoice -File | Measure-Object Length -Sum
```

两者分别应约为 23.3 MB（6 个文件）与 230.1 MB（5 个文件）。若体积明显偏小，说明文件缺失或不完整，从安装包备份中恢复即可——项目不再提供联网下载脚本。

## 4. 启动后端：19031

打开 PowerShell 窗口 A，执行后保持窗口开启：

```powershell
Set-Location -LiteralPath 'E:\文件\竞赛\project1-standalone\backend'
$env:FOREST_ENV = 'development'
$env:PYTHONDONTWRITEBYTECODE = '1'
..\.venv\Scripts\python.exe -X utf8 -B app.py --port 19031
```

出现 `Running on http://127.0.0.1:19031` 表示后端开始监听。应用会在 `.local/runtime/` 初始化自己的运行目录，并把 `data/*.csv` 的示例数据补齐到 `.local/runtime/data/`。

后端只提供 `/api` 接口，不托管静态文件。

常用参数：`--host 0.0.0.0` 开放局域网访问（需要为 Python 放行入站）；`--allow-origin <来源>` 追加允许的前端来源；`--data-dir .local/preview-1` 改用 `.local` 内的独立数据目录做隔离预览，登录 Cookie 会自动按端口区分。端口也可用环境变量 `FOREST_PORT` 覆盖。

## 5. 启动前端（开发）：19032

另开 PowerShell 窗口 B，执行后保持窗口开启：

```powershell
Set-Location -LiteralPath 'E:\文件\竞赛\project1-standalone\frontend'
npm.cmd run dev
```

浏览器打开：

- 首页：http://127.0.0.1:19032/ （需要登录，未登录会跳到 `/signin`）
- 参考路线：http://127.0.0.1:19032/learning
- 学习路线：http://127.0.0.1:19032/route
- 数据集：http://127.0.0.1:19032/datasets

前端把 `/api` 代理到 `http://127.0.0.1:19031`，默认值与后端端口一致，因此不需要设置 `FOREST_BACKEND_URL`。只有后端不在默认地址时，才需要在启动前设置：

```powershell
$env:FOREST_BACKEND_URL = 'http://127.0.0.1:19031'
```

端口来自 `frontend/src/config.ts` 的 `server.port`，并启用 `--strictPort`：19032 被占用会直接报错而不是自动换端口。临时换端口用 `npm.cmd run dev -- --port 19033`。

模型接口在页面左下角「接口设置」中配置（上游地址、模型、API Key）。API Key 由用户在界面中填写，按账号加密保存在本地；系统不再从环境变量读取密钥，也不会向浏览器返回完整密钥。

## 6. 构建与预览（生产形态）

```powershell
Set-Location -LiteralPath 'E:\文件\竞赛\project1-standalone\frontend'
npm.cmd run build
npm.cmd run preview
```

`build` 同时执行类型检查（vue-tsc）与打包，任一失败则整体失败；产物在 `frontend/dist/`（含 `assets/`、`models/`、`ort/`），可直接作为静态站点发布。`preview` 托管这些产物，并在 19032 上同样把 `/api` 代理到 19031，浏览器行为与开发环境一致。

`dev` 与 `preview` 使用同一个端口 19032，不能同时运行；切换前先 `Ctrl+C`。

如果改用其他静态服务器（例如 `npx serve dist -s`），它不转发 `/api`：接口请求会被静态服务器接管（`-s` 模式下回退到 `index.html`），前端拿不到数据。此时要么自行配置反向代理，要么在网址后加 `?backend=http://127.0.0.1:19031` 让页面直接访问后端（非生产模式下后端允许本机来源跨域）。

HTTPS 是可选的：把 `dev-cert.pem` 与 `dev-key.pem` 放进 `.local/certs/` 即自动启用，`FOREST_HTTPS=0` 强制使用 HTTP。`127.0.0.1` 与 `localhost` 本身属于浏览器的安全上下文，麦克风、剪贴板等受限功能不需要证书，只有局域网访问才需要。

## 7. 检查

前后端均已启动后，在第三个 PowerShell 窗口执行：

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:19031/api/health'
Invoke-RestMethod -Uri 'http://127.0.0.1:19032/api/health'
```

两个地址均返回 `service: forest-learning-lab` 即正常：前者说明后端自身可访问，后者经由前端代理，说明前端与后端的连接也已打通。

## 8. 停止与改端口

停止服务：在窗口 A 和窗口 B 中分别按 `Ctrl+C`。之后重启直接执行第 4、5 节，无需重复安装依赖或校验模型。

改端口需要同步三处（以把后端改成 19033、前端改成 19034 为例）：

- 后端：`backend/config.py` 的 `SERVER_PORT`，或启动时加 `--port 19033`
- 前端：`frontend/src/config.ts` 的 `server.port` 改成 19034
- 前端代理目标：设置 `FOREST_BACKEND_URL=http://127.0.0.1:19033`

访问地址随之变成 http://127.0.0.1:19034/。

## 9. 文件结构

```text
project1/
├─ backend/                 后端接口、对话与学习逻辑、实验算法
│  ├─ app.py                本地后端入口（python app.py）
│  ├─ config.py             后端参数、运行路径与默认端口
│  └─ agent/assets/          公开资源与字体
│     └─ model-providers.json  前后端共享的供应商、协议和模型预设
├─ frontend/                页面、画布、卡片、前端构建配置与锁文件
│  ├─ src/config.ts         前端参数与默认端口
│  ├─ public/               公开静态文件、内置语义检索模型与推理运行时
│  ├─ dist/                 构建产物（生成，不参与交付）
│  └─ vite.config.ts        开发/预览服务器与 /api 代理配置
├─ data/                    公开内置示例CSV与SenseVoice语音模型（data/models/sensevoice）
├─ docs/                    作品介绍文档与运行截图
├─ requirements.txt         Python运行依赖
└─ README.md                安装、启动、停止与检查步骤
```

安装和运行后生成的文件：

```text
.local/
├─ runtime/                 本目录的账号、会话、卡片、成绩、上传、图表与密钥
├─ public/                  检索模型、浏览器推理资源与静态文件副本
├─ cache/                   Vite与类型检查缓存
├─ logs/                    模型请求的诊断日志
└─ certs/                   本地HTTPS证书（如启用）
frontend/dist/              前端生产构建结果
.venv/                      独立Python环境
frontend/node_modules/      本目录的Node依赖
```

交付时仅包含源码与必要公开资源。安装后如需重新压缩纯源码，应排除 `.local/`、`.venv/`、`frontend/node_modules/`、`frontend/dist/` 与生成的 Python 字节码目录；**不要排除 `frontend/public/models/` 和 `data/models/`**，它们是必需的内置模型。

整理日期：2026-11-15。已核对文件、语法、相对路径与端口配置，并实测依赖安装产物、开发服务器启动、生产构建与预览代理。

