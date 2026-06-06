"""
Dong AI — 结构化日志系统

用法:
  from .logger import get_logger
  log = get_logger("ceo")
  log.info("phase_design", design_id="xxx", score=8.5)
  log.error("api_failed", endpoint="deepseek", error="timeout")

日志文件: ~/.dong/logs/{date}.jsonl
终端输出: 彩色 + 时间戳（可关闭）
"""

import json, os, sys, time, traceback
from pathlib import Path
from datetime import datetime, timezone


_LOG_DIR = Path.home() / ".dong" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# 追踪 ID（每个 CEO 调用链路一个 ID）
_trace_id = ""

def set_trace_id(tid: str):
    global _trace_id
    _trace_id = tid


class Logger:
    """结构化日志器"""
    
    def __init__(self, name: str):
        self.name = name
        self._today = ""
        self._file = None
    
    def _log(self, level: str, event: str, **kwargs):
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
        # JSONL 写文件
        today = now.strftime("%Y-%m-%d")
        if today != self._today:
            self._today = today
            if self._file:
                try: self._file.close()
                except: pass
            self._file = open(_LOG_DIR / f"{today}.jsonl", "a", encoding="utf-8")
        line = json.dumps(record, ensure_ascii=False)
        self._file.write(line + "\n")
        self._file.flush()
    
    def info(self, event: str, **kwargs):
        self._log("INFO", event, **kwargs)
    
    def warn(self, event: str, **kwargs):
        self._log("WARN", event, **kwargs)
    
    def error(self, event: str, **kwargs):
        self._log("ERROR", event, **kwargs)
    
    def debug(self, event: str, **kwargs):
        self._log("DEBUG", event, **kwargs)


_loggers = {}

def get_logger(name: str) -> Logger:
    if name not in _loggers:
        _loggers[name] = Logger(name)
    return _loggers[name]
