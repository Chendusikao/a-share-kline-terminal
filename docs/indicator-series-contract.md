# 指标序列 API 约定

`POST /api/v1/analysis` 的 `indicators.series` 使用稳定公共键。参数只影响计算和显示标签，不改变 RSI、ATR 等序列键：

| 指标族 | 公共键 |
|---|---|
| MA | `ma{period}`，例如 `ma5`、`ma20` |
| MACD | `macdDif`、`macdDea`、`macdHistogram` |
| RSI | `rsi` |
| KDJ | `kdjK`、`kdjD`、`kdjJ` |
| BOLL | `bollMiddle`、`bollUpper`、`bollLower` |
| ATR | `atr` |
| 20 日均量 | `volumeMa20` |

前端从同一份 `indicatorConfig` 获取 RSI/ATR 周期、颜色和每个指标族的 `enabled` 状态。比如 RSI 周期改为 21 后，API 键仍为 `rsi`，界面标签显示为 `RSI21`。关闭某个指标族后，该族不会出现在叠加线、副图选择或成交量均线中。
