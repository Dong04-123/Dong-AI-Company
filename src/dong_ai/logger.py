"""
Dong AI — 结构化日志系统

用法:
  from .logger import get_logger
  log = get_logger("ceo")
  log.info("phase_design", design_id="xxx", score=8.5)
  log.error("api_failed", endpoint="deepseek", error="timeout")

日志文件: ~/.dong/logs/{date}.jsonl
终端输出: 自动检测（可关闭）
保留策略: 自动清理 30 天前的日志
"""

from __future__ import annotations

import json, os, sys, time, traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta


_LOG_DIR = Path.home() / ".dong" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── 日志保留 ──
_MAX_LOG_AGE_DAYS = 30

# 追踪 ID（每个 CEO 调用链路一个 ID）
_trace_id = ""

def set_trace_id(tid: str) -> None:
    global _trace_id
    _trace_id = tid


def _cleanup_old_logs() -> None:
    """自动清理过期日志"""
    cutoff = time.time() - _MAX_LOG_AGE_DAYS * 86400
    try:
        for f in _LOG_DIR.glob("*.jsonl"):
            if f.stat().st_mtime < cutoff:
                f.unlink()
    except OSError:
        pass


class Logger:
    """结构化日志器"""

    def __init__(self, name: str) -> None:
        self.name = name
        self._today = ""
        self._file = None
        self._inited = False

    def _ensure(self) -> None:
        if self._inited:
            return
        self._inited = True
        _cleanup_old_logs()

    def _log(self, level: str, event: str, **kwargs) -> None:
        self._ensure()
        now = datetime.now(timezone.utc)
        record = {
            "t": now.isoformat(),
            "ts": now.timestamp(),
            "level": level,
            "logger": self.name,
            "event": event,
            "trace_id": _trace_id,
            **kwargs,
        }
        # JSONL 写文件（按日轮转）
        today = now.strftime("%Y-%m-%d")
        if today != self._today:
            self._today = today
            if self._file:
                try:
                    self._file.close()
                except Exception:
                    pass
            self._file = open(_LOG_DIR / f"{today}.jsonl", "a", encoding="utf-8")
        line = json.dumps(record, ensure_ascii=False)
        self._file.write(line + "\n")
        self._file.flush()

    def info(self, event: str, **kwargs) -> None:
        self._log("INFO", event, **kwargs)

    def warn(self, event: str, **kwargs) -> None:
        self._log("WARN", event, **kwargs)

    def error(self, event: str, **kwargs) -> None:
        self._log("ERROR", event, **kwargs)

    def debug(self, event: str, **kwargs) -> None:
        self._log("DEBUG", event, **kwargs)


_loggers = {}

def get_logger(name: str) -> Logger:
    if name not in _loggers:
        _loggers[name] = Logger(name)
    return _loggers[name]
