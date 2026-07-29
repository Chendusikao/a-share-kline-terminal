# A 股 K 线终端

仅在 Windows 本机运行的 A 股前复权日线技术分析终端。当前提交建立工程、深色中文应用壳、本机启动方式与持续集成；行情、指标和扫描功能将在后续任务中实现。

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

应用仅监听 `http://127.0.0.1:8000`。启动脚本在健康检查通过后打开浏览器；在终端按 `Ctrl+C` 停止服务。

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

CI 默认设置 `A_SHARE_ALLOW_AKSHARE_NETWORK=0`，所有测试不得访问真实 AKShare 网络。

数据来源：AKShare。不构成投资建议。
