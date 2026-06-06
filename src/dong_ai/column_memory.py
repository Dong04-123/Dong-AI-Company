"""
Dong AI — Column Memory

上下文分层管理，实现"大项目不失忆"。
不是无限窗口，是精确控制当前该看什么。

5 列:
  C0 常驻   — 项目名/类型/阶段/约束/目标  → 永不卸载
  C1 符号   — 函数/类签名、文件位置        → 按需加载
  C2 依赖   — 调用链、继承关系            → 按需加载
  C3 决策   — 评分、设计决策、关键选择     → 按需加载
  C4 历史   — 压缩摘要、旧对话            → 窗口满时优先卸载

用法:
  cm = ColumnMemory(project_id="myproj", context_limit=64000)
  cm.register("C1", data=symbols_text, token_count=3000)
  cm.load("C2")       # 加载依赖列
  cm.unload("C4")     # 卸载历史列
  ctx = cm.active()   # 当前窗口中所有激活列的内容
  ok, msg = cm.check_budget()  # 预算检查 + 自动压缩
"""

import json, re, time
from typing import Optional
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════
# 列定义
# ═══════════════════════════════════════════════════════════

COLUMNS = {
    "C0": {"name": "常驻", "priority": 99, "never_unload": True},
    "C1": {"name": "符号", "priority": 50, "never_unload": False},
    "C2": {"name": "依赖", "priority": 40, "never_unload": False},
    "C3": {"name": "决策", "priority": 60, "never_unload": False},
    "C4": {"name": "历史", "priority": 10, "never_unload": False},
}

COLUMN_ORDER = ["C0", "C3", "C1", "C2", "C4"]  # 卸载优先级（C0 最后卸）


@dataclass
class Column:
    id: str
    data: str = ""
    token_count: int = 0
    loaded: bool = False
    last_accessed: float = 0
    compressed: str = ""        # 压缩后的摘要

    def touch(self):
        self.last_accessed = time.time()


class ColumnMemory:
    """列式上下文管理器"""

    def __init__(self, project_id: str = "current",
                 context_limit: int = 64000,
                 warn_at: float = 0.7):
        self.project_id = project_id
        self.context_limit = context_limit
        self.warn_at = warn_at           # 超过 70% 触发警告/压缩
        self._cols: dict[str, Column] = {}
        self._compression_callback = None  # 可选的 LLM 压缩回调
        self._usage_history: list[dict] = []

    # ═══════════════════════════════════════════════════════
    # 列管理
    # ═══════════════════════════════════════════════════════

    def register(self, col_id: str, data: str = "",
                 token_count: int = 0) -> None:
        """注册列数据（不自动加载）"""
        base_id = col_id.split("_")[0] if "_" in col_id else col_id
        if base_id not in COLUMNS:
            raise ValueError(f"未知列: {col_id}，可用: {list(COLUMNS.keys())}")
        self._cols[col_id] = Column(
            id=col_id, data=data,
            token_count=token_count or self._estimate_tokens(data),
            loaded=False,
        )

    def load(self, col_id: str) -> str:
        """加载指定列到窗口"""
        col = self._cols.get(col_id)
        if not col:
            return ""
        col.loaded = True
        col.touch()
        return col.data

    def unload(self, col_id: str) -> str:
        """卸载列（返回其压缩摘要）"""
        col = self._cols.get(col_id)
        if not col or not col.loaded:
            return ""
        if COLUMNS.get(col_id, {}).get("never_unload"):
            return ""  # 常驻列不能卸载

        col.loaded = False
        return col.compressed or col.data[:200]

    def is_loaded(self, col_id: str) -> bool:
        col = self._cols.get(col_id)
        return col is not None and col.loaded

    def get(self, col_id: str) -> str:
        """获取列内容（自动 touch）"""
        col = self._cols.get(col_id)
        if col:
            col.touch()
            return col.data
        return ""

    def compress(self, col_id: str, summary: str) -> None:
        """设置列的压缩摘要"""
        col = self._cols.get(col_id)
        if col:
            col.compressed = summary

    # ═══════════════════════════════════════════════════════
    # 上下文拼接
    # ═══════════════════════════════════════════════════════

    def active(self) -> str:
        """返回所有已加载列拼接后的上下文"""
        parts = []
        for col_id in COLUMN_ORDER:
            col = self._cols.get(col_id)
            if col and col.loaded and col.data:
                label = COLUMNS[col_id]["name"]
                parts.append(f"【{label}】\n{col.data}")
        return "\n\n".join(parts)

    def token_usage(self) -> dict:
        """各列 + 总计 token 用量"""
        total = 0
        details = {}
        for col_id in COLUMN_ORDER:
            col = self._cols.get(col_id)
            if col and col.loaded:
                t = col.token_count
                details[col_id] = {"tokens": t, "name": COLUMNS[col_id]["name"]}
                total += t
        return {"total": total, "limit": self.context_limit,
                "pct": round(total / self.context_limit * 100, 1),
                "columns": details}

    # ═══════════════════════════════════════════════════════
    # 预算监控 + 自动压缩
    # ═══════════════════════════════════════════════════════

    def check_budget(self) -> tuple[bool, str]:
        """检查窗口预算。返回 (ok, message)"""
        usage = self.token_usage()
        pct = usage["pct"]
        total = usage["total"]
        limit = usage["limit"]

        if total >= limit:
            return self._do_compress(usage)

        if pct >= self.warn_at * 100:
            msg = f"⚠️ 上下文 {pct}% ({total:,}/{limit:,})"
            return True, msg  # 只是警告，不强制压缩

        return True, f"✅ 上下文 {pct}% ({total:,}/{limit:,})"

    def _do_compress(self, usage: dict) -> tuple[bool, str]:
        """主动压缩：按优先级从低到高卸载列"""
        freed = 0
        unloaded = []

        # 按 COLUMN_ORDER 反向（先卸 C4 历史）
        for col_id in reversed(COLUMN_ORDER):
            col = self._cols.get(col_id)
            if not col or not col.loaded:
                continue
            if COLUMNS.get(col_id, {}).get("never_unload"):
                continue

            summary = self.unload(col_id)
            freed += col.token_count
            unloaded.append(col_id)

            usage = self.token_usage()
            if usage["total"] < self.context_limit * 0.6:
                break

        if unloaded:
            msg = (f"📦 列已卸载: {', '.join(unloaded)}, "
                   f"释放 {freed:,} tokens, "
                   f"当前 {self.token_usage()['pct']}%")
            self._usage_history.append({
                "action": "compress",
                "unloaded": unloaded,
                "freed": freed,
                "remaining_pct": self.token_usage()["pct"],
                "time": time.time(),
            })
            return True, msg

        return False, "🚫 窗口已满，无可卸载的列"

    def set_compression_callback(self, fn) -> None:
        """设置 LLM 压缩回调: fn(col_id, data) -> summary"""
        self._compression_callback = fn

    # ═══════════════════════════════════════════════════════
    # 持久化
    # ═══════════════════════════════════════════════════════

    def save_state(self) -> dict:
        """保存列状态到 checkpoint"""
        state = {}
        for col_id, col in self._cols.items():
            state[col_id] = {
                "loaded": col.loaded,
                "data_len": len(col.data),
                "tokens": col.token_count,
                "compressed": col.compressed[:200] if col.compressed else "",
            }
        return {
            "project_id": self.project_id,
            "columns": state,
            "history": self._usage_history[-10:],
        }

    def restore_state(self, col0_data: str = "",
                      col0_tokens: int = 500) -> None:
        """从 checkpoint 恢复。只自动加载 C0"""
        self.register("C0", col0_data, col0_tokens)
        self.load("C0")

    # ═══════════════════════════════════════════════════════
    # 工具接口（供 Agent 调用）
    # ═══════════════════════════════════════════════════════

    def cmd_status(self) -> str:
        """状态概览（供 /dash 或 dong status）"""
        usage = self.token_usage()
        lines = [f"📊 Column Memory ({usage['total']:,}/{usage['limit']:,} tokens, {usage['pct']}%)"]
        for col_id in COLUMN_ORDER:
            col = self._cols.get(col_id)
            if col:
                icon = "📌" if col.loaded else "💤"
                nm = COLUMNS[col_id]["name"]
                sz = f"{col.token_count:,}t" if col.loaded else f"{len(col.data)}B"
                lock = " 🔒" if COLUMNS[col_id]["never_unload"] else ""
                lines.append(f"  {icon} {col_id} {nm} {sz}{lock}")
        if self._usage_history:
            last = self._usage_history[-1]
            lines.append(f"  最后操作: {last['action']} 释放 {last.get('freed',0):,}t")
        return "\n".join(lines)

    def _estimate_tokens(self, text: str) -> int:
        """粗略估算 token 数（4 字符 ≈ 1 token）"""
        return max(0, len(text) // 4)
