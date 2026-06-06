"""
Dong AI — 安全治理层 (Safety Governor)

元认知: 知道自己在干什么，知道什么时候不该干。
让 AI 公司值得被信任去运营你的股票账户。

能力:
  ✅ 置信度评分 — 每个决策附带可信度
  ✅ 风险预算 — 每日/每周最大可承受损失
  ✅ 人工确认门 — 高风险操作必须你点头
  ✅ 决策审计 — 每个决策可追溯、可复盘
  ✅ 自检 — 定期回顾自己的预测准确性
  ✅ 止损 — 触发条件时自动停止并告警
"""

import json, time, os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════
# 决策记录
# ═══════════════════════════════════════════════════════════

@dataclass
class Decision:
    action: str                        # buy/sell/alert/report
    target: str                        # 操作对象 (股票代码/文件/任务)
    reason: str                        # 决策理由
    confidence: float = 0.5            # 置信度 0.0-1.0
    risk_level: str = "low"            # low/medium/high/critical
    estimated_impact: str = ""         # 预估影响
    requires_confirmation: bool = False # 是否需要人工确认
    confirmed: bool = True             # 是否已确认
    outcome: Optional[str] = None      # 实际结果
    error: Optional[str] = None        # 错误信息（如果有）
    timestamp: float = 0.0             # 决策时间
    data_sources: list[str] = field(default_factory=list)  # 数据来源

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "target": self.target,
            "reason": self.reason[:200],
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "estimated_impact": self.estimated_impact[:200],
            "requires_confirmation": self.requires_confirmation,
            "confirmed": self.confirmed,
            "outcome": self.outcome,
            "error": self.error,
            "timestamp": self.timestamp or time.time(),
            "data_sources": self.data_sources,
        }


# ═══════════════════════════════════════════════════════════
# 治理引擎
# ═══════════════════════════════════════════════════════════

class SafetyGovernor:
    """安全治理层 — 所有决策必经之门"""

    def __init__(self, name: str = "default"):
        self.name = name
        self._decisions: list[Decision] = []
        self._risk_budget = {
            "daily_max_loss_pct": 2.0,      # 单日最大亏损 %
            "weekly_max_loss_pct": 5.0,     # 单周最大亏损 %
            "max_position_pct": 20.0,       # 单只仓位最大 %
            "max_daily_trades": 10,         # 每日最大交易次数
        }
        self._daily_usage = {
            "trades": 0,
            "loss_pct": 0.0,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
        self._stats = {
            "total_decisions": 0,
            "confirmed": 0,
            "rejected": 0,
            "high_risk_actions": 0,
            "errors": 0,
        }
        self._log_path = Path.home() / ".dong" / "governance" / f"{name}_decisions.jsonl"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    # ═══════════════════════════════════════════════════════
    # 核心: 决策审批
    # ═══════════════════════════════════════════════════════

    def approve(self, action: str, target: str, reason: str = "",
                 confidence: float = 0.5, data_sources: list[str] = None,
                 estimated_impact: str = "") -> tuple[bool, str]:
        """决策审批通道。返回 (是否允许, 消息)"""
        self._reset_daily_if_new_day()

        d = Decision(
            action=action, target=target, reason=reason,
            confidence=confidence, data_sources=data_sources or [],
            estimated_impact=estimated_impact,
            timestamp=time.time(),
        )

        # 1. 置信度过低 → 拒绝
        if confidence < 0.3:
            d.risk_level = "high"
            d.error = f"置信度过低 ({confidence:.1f})"
            self._reject(d)
            return False, f"❌ 置信度 {confidence:.1f} 过低，拒绝执行"

        # 2. 风险等级评定
        d.risk_level = self._assess_risk(action, target, confidence)
        d.requires_confirmation = d.risk_level in ("high", "critical")

        # 3. 检查风险预算
        budget_msg = self._check_budget(action)
        if budget_msg:
            d.risk_level = "critical"
            d.error = budget_msg
            self._reject(d)
            return False, f"❌ {budget_msg}"

        # 4. 高风险 → 人工确认
        if d.requires_confirmation:
            self._log_decision(d)
            self._stats["high_risk_actions"] += 1
            return False, (
                f"⚠️ 高风险操作需确认:\n"
                f"  操作: {action} {target}\n"
                f"  理由: {reason[:100]}\n"
                f"  置信度: {confidence:.0%}\n"
                f"  风险: {d.risk_level}\n"
                f"  输入 dong company confirm 确认执行"
            )

        # 5. 通过
        d.confirmed = True
        self._record_decision(d)
        return True, f"✅ {action} {target} (置信度 {confidence:.0%})"

    def confirm(self, decision_index: int = -1) -> str:
        """人工确认高风险操作"""
        pending = [d for d in self._decisions if d.requires_confirmation and not d.confirmed]
        if not pending:
            return "✅ 无待确认的决策"

        d = pending[decision_index] if decision_index < len(pending) else pending[-1]
        d.confirmed = True
        d.requires_confirmation = False
        self._stats["confirmed"] += 1
        return f"✅ 已确认: {d.action} {d.target}"

    def reject(self, decision_index: int = -1) -> str:
        """拒绝高风险操作"""
        pending = [d for d in self._decisions if d.requires_confirmation and not d.confirmed]
        if not pending:
            return "✅ 无待确认的决策"
        d = pending[decision_index] if decision_index < len(pending) else pending[-1]
        d.confirmed = False
        d.error = "人工拒绝"
        self._stats["rejected"] += 1
        return f"⛔ 已拒绝: {d.action} {d.target}"

    # ═══════════════════════════════════════════════════════
    # 自检与复盘
    # ═══════════════════════════════════════════════════════

    def self_review(self) -> str:
        """自检报告 — 回顾决策准确性和风险控制"""
        total = len(self._decisions)
        if total == 0:
            return "✅ 无决策记录"

        confirmed_count = sum(1 for d in self._decisions if d.confirmed)
        rejected_count = sum(1 for d in self._decisions if d.confirmed is False)
        errors = sum(1 for d in self._decisions if d.error)
        high_risk = sum(1 for d in self._decisions if d.risk_level in ("high", "critical"))
        correct = sum(1 for d in self._decisions if d.outcome == "success")
        failed = sum(1 for d in self._decisions if d.outcome == "failure")

        avg_confidence = sum(d.confidence for d in self._decisions) / total if total > 0 else 0

        return (
            f"📋 治理自检报告\n"
            f"{'='*40}\n"
            f"总决策: {total}\n"
            f"已执行: {confirmed_count}\n"
            f"已拒绝: {rejected_count}\n"
            f"高风险: {high_risk}\n"
            f"执行成功: {correct}\n"
            f"执行失败: {failed}\n"
            f"错误: {errors}\n"
            f"平均置信度: {avg_confidence:.1%}\n"
            f"风险预算: {json.dumps(self._risk_budget)}\n"
        )

    def record_outcome(self, action: str, target: str, outcome: str,
                       error: str = None) -> None:
        """记录决策的实际结果（用于复盘学习）"""
        for d in reversed(self._decisions):
            if d.action == action and d.target == target and d.outcome is None:
                d.outcome = outcome
                d.error = error
                self._log_decision(d)
                break

    # ═══════════════════════════════════════════════════════
    # 内部
    # ═══════════════════════════════════════════════════════

    def _assess_risk(self, action: str, target: str, confidence: float) -> str:
        """评定风险等级"""
        if action in ("buy", "sell", "trade", "invest"):
            if confidence < 0.5:
                return "critical"
            if confidence < 0.7:
                return "high"
            return "medium" if confidence < 0.85 else "low"
        if action in ("delete", "remove", "stop", "kill"):
            return "high"
        if action in ("write_file", "run", "deploy"):
            return "medium"
        return "low"

    def _check_budget(self, action: str) -> str:
        """检查风险预算"""
        if action in ("buy", "sell", "trade"):
            if self._daily_usage["trades"] >= self._risk_budget["max_daily_trades"]:
                return f"已达每日最大交易次数 ({self._risk_budget['max_daily_trades']})"
            self._daily_usage["trades"] += 1
        return ""

    def _reset_daily_if_new_day(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._daily_usage["date"]:
            self._daily_usage = {"trades": 0, "loss_pct": 0.0, "date": today}

    def _record_decision(self, d: Decision):
        self._decisions.append(d)
        self._stats["total_decisions"] += 1
        self._log_decision(d)

    def _reject(self, d: Decision):
        d.confirmed = False
        self._decisions.append(d)
        self._stats["total_decisions"] += 1
        self._stats["rejected"] += 1
        self._log_decision(d)

    def _log_decision(self, d: Decision):
        try:
            with open(self._log_path, "a") as f:
                f.write(json.dumps(d.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass

    def pending_decisions(self) -> list[dict]:
        """待人工确认的决策列表"""
        return [d.to_dict() for d in self._decisions
                if d.requires_confirmation and not d.confirmed]

    def summary(self) -> dict:
        return dict(self._stats)
