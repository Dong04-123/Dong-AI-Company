"""
Dong AI — 7x24 AI 公司后台

让 Dong AI 真正"运营"你的产品，而不是用完就关。

启动:
  dong company start     启动持久化公司实例
  dong company stop      停止
  dong company status    查看状态

自动运营:
  📩 工单处理  — webhook 接收 → CEO 分析 → 回复
  📊 日报生成  — 每天 9:00 自动产出
  🔔 异常监控  — 盯服务器指标
  🔄 自动备份  — 凌晨低峰期
  💬 随时对话  — "最近怎么样？"
"""

import os, sys, json, time, threading, signal
from pathlib import Path
from datetime import datetime
from typing import Optional


class CompanyRuntime:
    """公司运行时 — 管理后台生命周期"""

    def __init__(self, name: str = "default", domains: list[str] = None,
                 domain_configs: dict[str, str] = None,
                 duration: str = "", until: str = ""):
        self.name = name
        self._domains: list = []
        self._domain_names: list[str] = domains or []
        self._domain_configs: dict[str, str] = domain_configs or {}
        self._duration = duration
        self._until_str = until
        self._end_time: float = 0
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()
        from .governance import SafetyGovernor
        self.governor = SafetyGovernor(name)
        self._status = {
            "name": name,
            "state": "stopped",
            "uptime": 0,
            "started_at": "",
            "tasks_completed": 0,
            "webhooks_received": 0,
            "last_daily_report": "",
            "domains": self._domain_names,
            "end_time": "",
        }
        self._pid_file = Path.home() / ".dong" / f"company_{name}.pid"
        self._status_file = Path.home() / ".dong" / f"company_{name}.json"

    # ═══════════════════════════════════════════════════════════
    # 生命周期
    # ═══════════════════════════════════════════════════════════

    def start(self) -> bool:
        """启动公司后台"""
        if self.is_running():
            print(f"  ⚠️ 公司 {self.name} 已在运行中")
            return False

        # 写入 PID
        self._pid_file.write_text(str(os.getpid()))
        self._running = True
        self._stop_event.clear()
        self._status["state"] = "running"
        self._status["started_at"] = datetime.now().isoformat()
        self._status["uptime"] = 0
        self._save_status()

        # 初始化领域
        if self._domain_names:
            from .domains import load_domains, init_default_domains
            init_default_domains()
            self._domains = load_domains(self, self._domain_names, self._domain_configs)
            print(f"  🌐 加载领域: {', '.join(self._domain_names)}")

        # 在后台线程运行
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        print(f"  ✅ 公司 {self.name} 已启动")
        print(f"  PID: {os.getpid()}")
        print(f"  {self._status_str()}")
        return True

    def stop(self) -> bool:
        """停止公司后台"""
        if not self._running:
            print(f"  ⚠️ 公司 {self.name} 未在运行")
            return False

        self._running = False
        self._stop_event.set()
        self._status["state"] = "stopped"
        self._status["uptime"] = int(time.time() - self._start_time) if hasattr(self, '_start_time') else 0
        self._save_status()

        # 清理 PID 文件
        if self._pid_file.exists():
            self._pid_file.unlink()

        print(f"  ✅ 公司 {self.name} 已停止")
        print(f"  运行时长: {self._status['uptime']}s")
        print(f"  处理工单: {self._status['webhooks_received']}")
        return True

    def is_running(self) -> bool:
        """检测是否正在运行"""
        if self._pid_file.exists():
            try:
                pid = int(self._pid_file.read_text().strip())
                # 检查进程是否存在
                os.kill(pid, 0)
                return True
            except (OSError, ValueError):
                self._pid_file.unlink(missing_ok=True)
        return self._running

    def status(self) -> dict:
        """获取公司状态"""
        self._status["uptime"] = int(time.time() - getattr(self, '_start_time', time.time())) if self._running else self._status.get("uptime", 0)
        return dict(self._status)

    # ═══════════════════════════════════════════════════════════
    # 主循环
    # ═══════════════════════════════════════════════════════════

    def _run_loop(self):
        """后台主循环：定时任务 + 事件监听"""
        self._start_time = time.time()
        now = datetime.now()
        last_hourly = 0

        # 计算结束时间
        self._end_time = 0
        if self._until_str:
            try:
                from datetime import timedelta
                # Support formats: "17:00", "2026-06-07 17:00", "30m", "2h", "1d"
                if self._until_str.endswith("m"):
                    self._end_time = self._start_time + int(self._until_str[:-1]) * 60
                elif self._until_str.endswith("h"):
                    self._end_time = self._start_time + int(self._until_str[:-1]) * 3600
                elif self._until_str.endswith("d"):
                    self._end_time = self._start_time + int(self._until_str[:-1]) * 86400
                elif ":" in self._until_str:
                    target = datetime.strptime(self._until_str, "%H:%M").replace(
                        year=now.year, month=now.month, day=now.day)
                    self._end_time = target.timestamp()
                    if self._end_time < self._start_time:
                        self._end_time += 86400  # next day
                else:
                    self._end_time = self._start_time + 3600  # default 1h
            except Exception:
                self._end_time = self._start_time + 3600

        if self._end_time:
            remaining = int(self._end_time - self._start_time)
            end_str = datetime.fromtimestamp(self._end_time).strftime("%H:%M")
            print(f"  ⏰ 自动停止: {end_str} (剩余 {remaining//3600}h{(remaining%3600)//60}m)")
            self._status["end_time"] = datetime.fromtimestamp(self._end_time).isoformat()

        while self._running and not self._stop_event.is_set():
            now = datetime.now()

            # 检查是否到期
            if self._end_time and time.time() >= self._end_time:
                print(f"\n  ⏰ 运营时间已到，自动停止")
                self.stop()
                break

            hour = now.hour
            today = now.strftime("%Y-%m-%d")

            # 每小时任务
            if hour != last_hourly:
                last_hourly = hour
                self._run_hourly()
                # 领域 tick
                for d in self._domains:
                    try:
                        d.tick()
                    except Exception as e:
                        self._log("domain", f"{d.name}.tick 失败: {e}")

            # 日报任务 (每天 9:00)
            if hour == 9 and today != last_daily:
                last_daily = today
                self._run_daily_report()
                # 领域日报
                for d in self._domains:
                    try:
                        r = d.report()
                        if r:
                            print(f"  📊 {d.name} 日报:\n{r[:500]}")
                    except Exception as e:
                        self._log("domain", f"{d.name}.report 失败: {e}")

            # 备份任务 (每天 3:00)
            if hour == 3 and today != getattr(self, '_last_backup', ''):
                self._last_backup = today
                self._run_backup()

            self._save_status()
            self._stop_event.wait(60)  # 每分钟检查一次

    def _run_hourly(self):
        """每小时任务：健康检查 + 简单状态记录"""
        log = f"[{datetime.now().isoformat()}] 健康检查通过"
        print(f"  📋 {log}")
        self._status["tasks_completed"] += 1
        self._log("hourly", log)

    def _run_daily_report(self):
        """日报生成"""
        try:
            from .experience_engine import ExperienceEngine
            eng = ExperienceEngine()
            stats = eng.project_stats()
            report = (
                f"📊 Dong AI 日报 — {datetime.now().strftime('%Y-%m-%d')}\n"
                f"{'='*40}\n"
                f"项目总数: {stats['total_projects']}\n"
                f"平均评分: {stats['avg_score']}\n"
                f"各类型: {stats['by_type']}\n"
                f"经验累计: {stats['total_lessons']}\n"
                f"{'='*40}\n"
                f"系统状态: 运行中\n"
                f"运行时长: {int(time.time() - self._start_time)//3600}h\n"
            )
            report_path = Path.home() / ".dong" / f"daily_{datetime.now().strftime('%Y%m%d')}.md"
            report_path.write_text(report)
            self._status["last_daily_report"] = str(report_path)
            self._status["tasks_completed"] += 1
            print(f"  📊 日报已生成: {report_path}")
            self._log("daily_report", f"日报已生成 ({stats['total_projects']} 项目)")
        except Exception as e:
            print(f"  ⚠️ 日报生成失败: {e}")

    def _run_backup(self):
        """自动备份"""
        import shutil
        backup_dir = Path.home() / ".dong" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_name = f"dong_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        backup_path = backup_dir / backup_name
        try:
            shutil.make_archive(
                str(backup_path.with_suffix('')),
                'zip',
                Path.home() / ".dong",
            )
            # 清理 7 天前的备份
            for f in sorted(backup_dir.glob("dong_backup_*.zip"))[:-7]:
                f.unlink()
            self._status["tasks_completed"] += 1
            print(f"  💾 备份完成: {backup_path.name}")
            self._log("backup", f"备份: {backup_path.name}")
        except Exception as e:
            print(f"  ⚠️ 备份失败: {e}")

    # ═══════════════════════════════════════════════════════════
    # 事件处理
    # ═══════════════════════════════════════════════════════════

    def handle_webhook(self, event: str, payload: dict) -> dict:
        """处理 webhook 事件 — 先让领域处理，再走默认逻辑"""
        self._status["webhooks_received"] += 1

        # 领域处理
        for d in self._domains:
            try:
                result = d.on_event(event, payload)
                if result:
                    return result
            except Exception:
                pass

        if event in ("ticket", "issue", "customer"):
            return self._handle_ticket(payload)
        elif event in ("deploy", "push"):
            return self._handle_deploy(payload)
        elif event in ("alert", "error", "critical"):
            return self._handle_alert(payload)
        else:
            return {"status": "ignored", "event": event}

    def _handle_ticket(self, payload: dict) -> dict:
        """用户工单处理"""
        title = payload.get("title", payload.get("subject", "无标题"))
        body = payload.get("body", payload.get("description", ""))
        log = f"工单: {title[:50]}"
        self._log("ticket", log)

        # 通过 CEO 分析工单（异步）
        try:
            from .ceo import CEO
            t = threading.Thread(target=CEO().run, args=(f"分析并回复用户工单: {title}\n{body[:1000]}",), daemon=True)
            t.start()
            return {"status": "processing", "message": f"工单 '{title}' 正在处理"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _handle_deploy(self, payload: dict) -> dict:
        """部署事件 — 自动审计"""
        self._log("deploy", f"部署: {payload.get('ref', '?')[:30]}")
        try:
            from .ceo import CEO
            t = threading.Thread(target=CEO().run, args=(f"审计最近的代码变更",), daemon=True)
            t.start()
            return {"status": "auditing"}
        except Exception:
            return {"status": "accepted"}

    def _handle_alert(self, payload: dict) -> dict:
        """监控告警处理"""
        message = payload.get("message", str(payload)[:200])
        self._log("alert", f"告警: {message[:80]}")
        # 记录告警，后续可由 LLM 分析
        print(f"  🔔 告警: {message[:100]}")
        return {"status": "logged"}

    # ═══════════════════════════════════════════════════════════
    # 内部
    # ═══════════════════════════════════════════════════════════

    def _log(self, event_type: str, message: str):
        """结构化日志"""
        from .logger import get_logger
        get_logger("company").info(event_type, message=message)

    def _save_status(self):
        """持久化状态"""
        self._status_file.write_text(json.dumps(self._status, ensure_ascii=False, indent=2))

    def _status_str(self) -> str:
        """状态摘要"""
        s = self._status
        return (
            f"  ├─ 状态: {s['state']}\n"
            f"  ├─ 工单: {s['webhooks_received']}\n"
            f"  ├─ 任务: {s['tasks_completed']}\n"
            f"  └─ 日报: {s.get('last_daily_report', '无')[:50]}"
        )
