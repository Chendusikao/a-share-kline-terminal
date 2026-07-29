# A 股 K 线终端实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** 构建一套个人使用的桌面 Web 应用，提供 A 股前复权 K 线、可调技术指标、透明技术面评分与自选股批量扫描。

**Architecture:** React + ECharts 负责深色专业看盘界面；FastAPI + AKShare 负责行情获取、缓存、指标计算、规则解读与扫描任务。FastAPI 同时托管构建后的前端，应用在 Windows 本机通过 PowerShell 一键启动。

**Tech Stack:** Node.js 24、Python 3.14、React、TypeScript、Vite、ECharts、TanStack Query、FastAPI、Pydantic、AKShare、pandas、SQLite、SQLAlchemy、pytest、Vitest、Playwright。

## Global Constraints

- 仅支持 A 股前复权日线；不做实时行情、交易、回测、AI 解读、自定义公式、登录或基本面分析。
- 界面为简体中文、单一深色专业终端主题，遵循 A 股红涨绿跌惯例。
- 数据仅用于技术分析；页面显示“数据来源：AKShare”与“不构成投资建议”。
- 应用仅监听 `127.0.0.1`，不在首版提供云端同步或远程访问。
- GitHub 用于源码和 CI；GitHub Pages 不用于完整应用部署，因为其不能运行服务端 Python。

---

## Task 1: 工程与本机运行

- 建立 `frontend/`、`backend/`、`scripts/` 和 GitHub Actions CI。
- 前端使用 React、TypeScript、Vite、ECharts、TanStack Query 与 React Router；后端使用 FastAPI、Pydantic、AKShare、pandas、SQLite、SQLAlchemy。
- `scripts/setup.ps1` 创建虚拟环境、安装锁定依赖并构建前端；`scripts/start.ps1` 启动 FastAPI、托管静态文件并打开浏览器。
- 开发期保留独立前后端热更新命令；用户日常使用只运行 `start.ps1`。
- CI 执行格式检查、类型检查、前后端单元测试、端到端测试和生产构建；默认不访问真实 AKShare 网络。

## Task 2: 行情、缓存与指标

- 股票列表每日刷新并缓存；搜索接口支持股票代码和中文名称。
- 详情页默认加载近 3 年前复权日线，支持 3 个月、6 个月、1 年、3 年、全部区间。
- SQLite 保存股票列表、K 线、扫描批次与扫描结果。前复权数据刷新时，按股票完整替换缓存，避免除权后历史价格不一致。
- AKShare 请求超时或失败时：若存在缓存则展示缓存并标注更新时间；若无缓存则返回可重试的 `DATA_UNAVAILABLE` 错误。
- 内置指标：MA、MACD、RSI、KDJ、BOLL、ATR 和 20 日均量。用户可控制显示、参数及颜色，不支持公式编辑。
- 默认参数：MA `5/10/20/60`、MACD `12/26/9`、RSI `14`、KDJ `9/3/3`、BOLL `20/2`、ATR `14`。
- 参数由后端统一校验：MA 周期 `2–250`、最多 8 条且不重复；MACD 快线小于慢线；RSI/ATR `2–100`；KDJ 周期 `2–100`、平滑 `1–20`；BOLL 周期 `2–250`、标准差 `0.5–5`。历史不足时返回 `null` 和原因，不填充伪造数据。

## Task 3: 规则解读与综合评分

- 后端返回趋势、动量、量价、关键位置、风险五类结构化解读。每条解读包含方向（偏多/偏空/中性/风险）、摘要、严重程度与可见证据；前端不重新推断信号。
- 技术面总分由五项 `0–100` 分项经权重计算并四舍五入：

| 分项 | 默认权重 | 规则 |
|---|---:|---|
| 趋势 | 35 | 以 50 为基准，根据收盘价/MA20、MA20/MA60、MA20 五日斜率各加减 20、20、10 分 |
| 动量 | 25 | 以 50 为基准，根据 DIF/DEA、MACD 柱体变化和 RSI 区间加减分 |
| 量价 | 15 | 依据当日涨跌方向与成交量相对 20 日均量的确认程度评分 |
| 区间位置 | 15 | 取收盘价在前 20 日与 60 日高低区间中的百分位均值 |
| 风险质量 | 10 | 从 100 分扣除 RSI 极值、ATR 高波动、异常单日波动和三倍放量风险 |

- 评分具体规则：
  - 趋势分以 50 起算：收盘价高于/低于 MA20 加/减 20；MA20 高于/低于 MA60 加/减 20；MA20 高于/低于五日前值加/减 10；最终限制为 `0–100`。
  - 动量分以 50 起算：DIF 高于/低于 DEA 加/减 20；MACD 柱体较前一日扩大/缩小加/减 15；RSI 在 `55–70` 加 15，`50–55` 加 5，`45–50` 减 5，`30–45` 减 15，超过 70 或低于 30 进入风险扣分。
  - 量价分：成交量/20 日均量大于等于 1.5 时，上涨 80、下跌 20、平盘 50；位于 `0.7–1.5` 时，上涨 60、下跌 40、平盘 50；低于 0.7 时为 50。
  - 区间位置分：分别计算 `(收盘价 - 区间最低)/(区间最高 - 区间最低) × 100` 的 20 日、60 日结果，裁剪至 `0–100` 后取平均。
  - 风险质量分以 100 起算：RSI 极值、ATR/收盘价高于此前 60 日 80 分位、单日绝对涨跌超过前日 ATR 比例两倍、成交量/20 日均量达到 3 倍，各扣 25 分，最终限制为 `0–100`。
- 用户可设置五项非负权重；至少一项必须大于零。前后端均自动归一化为 100%，响应中回传有效权重；设置页显示原始值、实际占比与恢复默认按钮。
- 总分等级固定为：`0–34` 弱、`35–44` 偏弱、`45–55` 中性、`56–65` 偏强、`66–100` 强。
- 评分至少需要 80 个有效交易日；不足时只展示可用指标和原因。评分始终与分项、权重及证据一起展示，不生成买卖建议或收益预测。

## Task 4: 公共接口与数据模型

- `GET /api/v1/health`
- `GET /api/v1/market/status`
- `GET /api/v1/stocks/search?q={query}&limit={1..20}`
- `POST /api/v1/analysis`
  - 请求：`symbol`、`range`、`forceRefresh`、`indicatorConfig`、`scoreWeights`。
  - 响应：股票信息、行情日期、K 线、指标序列、总分与分项、有效权重、五类解读、缓存状态和警告。
- `POST /api/v1/scans`
  - 请求：最多 20 个唯一股票代码、指标配置、评分权重、`forceRefresh`。
  - 返回 HTTP `202` 与 `scanId`。
- `GET /api/v1/scans/{scanId}`：返回状态、完成数、总数、市场日期、结果和逐股票错误。
- `GET /api/v1/scans/latest`
- 统一错误码：`SYMBOL_NOT_FOUND`、`INVALID_CONFIG`、`DATA_UNAVAILABLE`、`INSUFFICIENT_HISTORY`、`SCAN_NOT_FOUND`。
- 所有日期使用 `YYYY-MM-DD`；所有数值不得返回 `NaN`，缺失值用 `null`。
- SQLite 表：
  - `stocks(symbol, name, exchange, updated_at)`
  - `daily_candles(symbol, trade_date, open, high, low, close, volume, amount, adjustment, fetched_at)`
  - `scan_runs(id, market_date, config_hash, status, created_at, completed_at)`
  - `scan_results(run_id, symbol, score, grade, breakdown_json, insights_json, data_status, error_code)`

## Task 5: 深色终端界面

- 路由：扫描首页、股票详情页、设置页。
- 股票详情采用“图表主导 + 右侧解读”：左侧 K 线、成交量和副图；右侧总分、分项、五类解读与关键位置。
- K 线支持缩放、拖动、十字光标、区间切换和指标叠加；窄于 1024px 时右侧解读移动至图表下方。
- 自选股与最近浏览保存在版本化 `localStorage`；自选股最大 20 只。
- 首页展示批量扫描表格，默认按总分降序，显示股票、总分、等级、较上次变化、关键信号、行情日期和缓存状态。

## Task 6: 批量扫描

- 交易日 16:00 后，若最新市场日期晚于最近成功扫描日期，首次打开应用自动扫描；用户也可以手动刷新。
- 后端采用进程内异步任务和最多 3 个并发请求；单股失败重试两次，不影响其他股票。
- 前端每秒轮询任务状态，显示 `已完成/总数`、失败原因和单行重试。
- 扫描使用详情页相同的指标参数与评分权重；扫描只拉取计算评分所需的最小历史窗口。
- 应用重启后未完成任务标记为失败；仅保留最近 30 个扫描批次，用于计算“较上次变化”。

## Task 7: 测试与验收

- 后端单元测试验证全部指标到 `1e-6` 精度、评分边界、权重归一化、等级临界值与证据生成。
- 使用 Mock AKShare 验证搜索、缓存命中、前复权全量替换、超时重试、旧缓存降级和无缓存失败。
- 扫描测试覆盖 20 只上限、三并发、部分失败、单行重试、同交易日去重、重启恢复及 30 个批次保留策略。
- 前端使用 Vitest/Testing Library 验证 K 线映射、配置持久化、评分展示、加载、缓存、空数据和错误状态。
- Playwright 验收完整流程：搜索 `000001`、查看前复权日 K、修改 MA 与评分权重、确认图表和证据同步、加入自选、完成批量扫描、重启后恢复状态。
- `setup.ps1` 和 `start.ps1` 必须在当前 Windows 环境完成干净安装、构建、启动和健康检查。
