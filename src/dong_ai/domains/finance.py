"""
Dong AI — 金融领域

自动盯盘: A股/美股/港股/期货
策略: 价格突破、成交量异常、均线交叉
通知: 飞书/webhook/日志

依赖: pip install akshare  (免费数据源)

配置 (~/.dong/domains/finance.json):
{
  "watchlist": ["600519", "000001", "AAPL", "TSLA"],
  "strategies": {
    "price_breakout": {"enabled": true, "threshold_pct": 3.0},
    "volume_spike": {"enabled": true, "threshold_pct": 200},
    "ma_cross": {"enabled": false}
  },
  "interval_minutes": 5
}
"""

import json, time, re
from datetime import datetime
from typing import Any

from . import Domain, register


@register
class FinanceDomain(Domain):
    name = "finance"
    description = "全球金融市场监控 — 股票/期货/外汇"
    config_key = "domain_finance"

    def __init__(self, runtime, config=None):
        super().__init__(runtime, config or {})
        self._last_prices: dict[str, float] = {}
        self._alerts: list[dict] = []
        self._akshare_available = False

    def init(self):
        """初始化: 检测数据源"""
        try:
            import akshare as ak
            self._ak = ak
            self._akshare_available = True
            self.alert("📈 金融领域已启动，数据源: AKShare")
        except ImportError:
            self._akshare_available = False
            self.alert("⚠️ AKShare 未安装: pip install akshare", "warn")

        # 默认监控列表
        self.watchlist = self.config.get("watchlist", [
            # A股
            "600519", "000001", "300750", "601318",
            # 指数
            "000001.SH", "399001.SZ", "399006.SZ",
        ])
        self.strategies = self.config.get("strategies", {
            "price_breakout": {"enabled": True, "threshold_pct": 3.0},
            "volume_spike": {"enabled": True, "threshold_pct": 200},
        })
        self.interval = self.config.get("interval_minutes", 5)
        self._tick_counter = 0

    def tick(self):
        """每分钟检查 — 按 interval 频率执行"""
        super().tick()
        self._tick_counter += 1
        if self._tick_counter % self.interval != 0:
            return

        if not self._akshare_available:
            return

        self._check_prices()

    def _check_prices(self):
        """检查股票价格和策略触发"""
        try:
            import akshare as ak
        except ImportError:
            return

        for symbol in self.watchlist:
            try:
                self._check_stock(symbol)
            except Exception as e:
                self.alert(f"{symbol} 检查失败: {e}", "warn")
                continue

    def _check_stock(self, symbol: str):
        """检查单只股票"""
        try:
            if symbol.isdigit() or symbol.startswith(("0", "3", "6")):
                # A 股 — 实时行情
                df = self._ak.stock_zh_a_spot_em()
                row = df[df["代码"] == symbol]
                if row.empty:
                    return
                row = row.iloc[0]
                current = float(row["最新价"])
                change_pct = float(row["涨跌幅"])
                volume = float(row["成交量"])
                volume_pct = float(row.get("量比", 0))

                name = row.get("名称", symbol)
            else:
                # 美股 — 实时行情 (通过新浪)
                df = self._ak.stock_us_spot_em()
                row = df[df["代码"] == symbol]
                if row.empty:
                    return
                row = row.iloc[0]
                current = float(row["最新价"])
                change_pct = float(row["涨跌幅"])
                volume = float(row.get("成交量", 0))
                volume_pct = 0
                name = row.get("名称", symbol)

            # 策略检查
            last = self._last_prices.get(symbol)
            self._last_prices[symbol] = current

            alerts = []

            # 涨幅突破
            if self.strategies.get("price_breakout", {}).get("enabled"):
                threshold = self.strategies["price_breakout"]["threshold_pct"]
                if abs(change_pct) >= threshold:
                    direction = "📈" if change_pct > 0 else "📉"
                    alerts.append(f"{direction} {name}({symbol}) 涨幅 {change_pct:+.2f}% (阈值 {threshold}%)")

            # 成交量异常
            if self.strategies.get("volume_spike", {}).get("enabled") and volume_pct > 0:
                threshold = self.strategies["volume_spike"]["threshold_pct"]
                if volume_pct >= threshold:
                    alerts.append(f"📊 {name}({symbol}) 成交量异常: 量比 {volume_pct:.1f} (阈值 {threshold}%)")

            for alert in alerts:
                self.alert(alert)
                self._alerts.append({"time": datetime.now().isoformat(), "message": alert})

        except Exception as e:
            self.alert(f"{symbol} 数据获取失败: {e}", "warn")

    def on_event(self, event: str, payload: dict) -> dict | None:
        """处理金融相关 webhook"""
        if event == "price_alert":
            symbol = payload.get("symbol", "")
            action = payload.get("action", "notify")
            self.alert(f"🔔 手动告警: {symbol} → {action}")
            return {"status": "alerted", "symbol": symbol}
        return None

    def report(self) -> str:
        """金融日报"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            f"📈 金融监控日报 — {now}",
            f"{'='*40}",
            f"监控标的: {len(self.watchlist)} 只",
            f"今日告警: {len(self._alerts)} 条",
            f"运行时长: {self._tick_count} ticks",
        ]
        if self._alerts:
            lines.append(f"\n最近告警:")
            for a in self._alerts[-5:]:
                lines.append(f"  {a['message']}")
        self._alerts.clear()
        return "\n".join(lines)
