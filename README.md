# A 股 K 线终端

仅在 Windows 本机运行的 A 股前复权日线技术分析终端。当前版本已提供股票搜索、K 线与内置指标、透明技术评分、自选股批量扫描、SQLite 缓存和重启恢复。

## 技术栈

| 分层 | 技术 |
| --- | --- |
| 前端 | React 19、TypeScript 7、Vite 8、React Router、TanStack Query、Apache ECharts |
| 后端 | Python 3.14、FastAPI、Pydantic、Uvicorn |
| 行情与分析 | AKShare、pandas；内置 MA、MACD、RSI、KDJ、BOLL、ATR 与均量指标 |
| 数据存储 | SQLite、SQLAlchemy |
| 测试与质量 | pytest、Ruff、mypy、Vitest、Testing Library、Playwright |
| 本地运行与 CI | PowerShell、GitHub Actions；默认仅监听 `127.0.0.1` |

## 功能概览

- A 股前复权日线、缓存降级与可见数据状态。
- 可调指标、透明技术面评分与结构化证据，不生成买卖建议。
- 自选股、批量扫描、失败重试、进度轮询与重启恢复。
- 深色专业终端界面，遵循 A 股红涨绿跌惯例。

## 环境要求

- Node.js 24
- Python 3.14
- PowerShell 5.1 或更高版本

## 安装与日常启动

首次安装：

```powershell
.\scripts\setup.ps1
```

以后日常使用只需：

```powershell
.\scripts\start.ps1
```

应用仅监听 `http://127.0.0.1:8000`。启动脚本会等待健康检查成功后再打开浏览器，并在服务未就绪或异常退出时返回失败；在终端按 `Ctrl+C` 停止服务。

默认网关采用显式网络许可：`start.ps1` 在变量未设置时为交互式本机运行设置 `A_SHARE_ALLOW_AKSHARE_NETWORK=1`。需要严格离线运行时，应在启动前明确设置：

```powershell
$env:A_SHARE_ALLOW_AKSHARE_NETWORK = "0"
.\scripts\start.ps1 -NoBrowser
```

此时任何未注入假的 AKShare 调用都会在应用内失败关闭，不会发出网络请求。CI 和全部自动化测试固定使用该离线模式。

市场状态和扫描日期使用随应用发布的上交所/深交所本地交易日历；日历有效期有明确边界，超出已发布范围时返回“不可用”，不会把普通工作日猜作交易日。

## 开发

在两个 PowerShell 窗口分别运行前后端热更新服务：

```powershell
.\scripts\dev-backend.ps1
.\scripts\dev-frontend.ps1
```

前端开发服务位于 `http://127.0.0.1:5173`，并将 `/api` 代理到本机后端。生产模式由 FastAPI 托管 `frontend/dist`。

常用校验命令：

```powershell
npm --prefix frontend run format:check
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build

Push-Location backend
..\.venv\Scripts\python.exe -m ruff format --check .
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m mypy
..\.venv\Scripts\python.exe -m pytest
Pop-Location

npm --prefix frontend run test:e2e
```

指标序列的后端/前端公共键约定见 [docs/indicator-series-contract.md](docs/indicator-series-contract.md)。

数据来源：AKShare。不构成投资建议。
