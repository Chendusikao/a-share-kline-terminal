# A 股 K 线终端

仅在 Windows 本机运行的 A 股前复权日线技术分析终端。它把行情、指标、评分和自选扫描放在一个本地工作台里，适合学习技术分析、复盘历史行情和管理自己的观察列表。

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

- 行情与图表：搜索股票代码/名称，查看前复权日线、K 线、成交量和可切换的副图指标。
- 技术分析：支持 MA、MACD、RSI、KDJ、BOLL、ATR、均量；周期、颜色、显示开关和评分权重均可调整。
- 透明评分：展示趋势、动量、量价、关键位置和风险质量分项，并列出后端结构化证据；不生成买卖建议。
- 自选与扫描：维护最多 20 只自选股，批量扫描、按总分排序、显示较上次变化，失败任务可单股重试。
- 新手辅助：首次访问引导、指标小词典、默认/趋势/波段/短线四套参数预设；点击“定位图表”可核对解读证据。
- 数据可靠性：行情状态、缓存命中/旧缓存/网络更新状态、扫描进度和重启恢复均可见；网络不可用时明确提示。
- 本地优先：FastAPI 在本机托管前端，SQLite 保存缓存和任务状态，默认只监听 `127.0.0.1`。

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
