"""Dong AI — 定时任务调度器

用法:
  dong cron list         列出所有定时任务
  dong cron add --every 1h --cmd "dong run '检查'"  添加任务
  dong cron remove <id>  删除任务
  dong cron start        启动调度器（后台）
"""

import json, os, time, threading
from pathlib import Path

CRON_FILE = Path.home() / ".dong" / "cron.json"


def load_tasks() -> list:
    if CRON_FILE.exists():
        try:
            return json.loads(CRON_FILE.read_text())["tasks"]
        except: pass
    return []


def save_tasks(tasks: list):
    CRON_FILE.parent.mkdir(parents=True, exist_ok=True)
    CRON_FILE.write_text(json.dumps({"tasks": tasks}, ensure_ascii=False, indent=2))


def _parse_interval(text: str) -> int:
    """解析 '30m', '2h', '1d' 为秒数"""
    text = text.strip().lower()
    if text.endswith("s"):
        return int(text[:-1])
    if text.endswith("m"):
        return int(text[:-1]) * 60
    if text.endswith("h"):
        return int(text[:-1]) * 3600
    if text.endswith("d"):
        return int(text[:-1]) * 86400
    return int(text)


def add_task(name: str, command: str, interval: str):
    tasks = load_tasks()
    tid = f"cron_{int(time.time())}"
    tasks.append({
        "id": tid,
        "name": name,
        "command": command,
        "interval": interval,
        "interval_seconds": _parse_interval(interval),
        "last_run": None,
        "enabled": True,
    })
    save_tasks(tasks)
    print(f"  ✅ 已添加定时任务: {name} (每{interval})")
    print(f"  ID: {tid}")


def remove_task(tid: str):
    tasks = load_tasks()
    before = len(tasks)
    tasks = [t for t in tasks if t["id"] != tid]
    if len(tasks) < before:
        save_tasks(tasks)
        print(f"  ✅ 已删除: {tid}")
    else:
        print(f"  ⚠️ 未找到: {tid}")


def list_tasks():
    tasks = load_tasks()
    if not tasks:
        print("没有定时任务")
        print("添加: dong cron add --every 30m --cmd 'dong run \"检查\"'")
        return
    print(f"定时任务 ({len(tasks)} 个):")
    for t in tasks:
        status = "●" if t.get("enabled", True) else "○"
        last = t.get("last_run", "从未") or "从未"
        print(f"  {status} {t['id']:<20} {t['name']:<20} 每{t['interval']:<6} 上次:{last[:16]}")
        print(f"     cmd: {t['command']}")


class CronScheduler:
    """简单的循环定时调度器"""

    def __init__(self):
        self._timers = []
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        print("  Cron 调度器已启动")
        self._schedule_all()

    def stop(self):
        self._running = False
        for t in self._timers:
            t.cancel()
        self._timers.clear()
        print("  Cron 调度器已停止")

    def _schedule_all(self):
        tasks = load_tasks()
        for t in tasks:
            if t.get("enabled", True):
                self._schedule_one(t)

    def _schedule_one(self, task):
        if not self._running:
            return
        secs = task.get("interval_seconds", 3600)

        def run():
            if not self._running:
                return
            try:
                print(f"  [Cron] 执行: {task['name']}")
                import subprocess
                result = subprocess.run(
                    task["command"], shell=True, capture_output=True, text=True, timeout=300
                )
                tasks = load_tasks()
                for t in tasks:
                    if t["id"] == task["id"]:
                        t["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        t["last_output"] = (result.stdout or result.stderr or "")[:200]
                        break
                save_tasks(tasks)
            except Exception as e:
                print(f"  [Cron] 失败 {task['name']}: {e}")
            # 重新调度
            self._schedule_one(task)

        timer = threading.Timer(secs, run)
        timer.daemon = True
        timer.start()
        self._timers.append(timer)
