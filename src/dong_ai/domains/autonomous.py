"""
Dong AI — 全自营领域引擎

不是写死的领域代码，是 Agent 自己学会任何领域。

用户只需要说:
  dong company start --domain "盯A股消费板块，涨幅超3%提醒"
  dong company start --domain "监控我电商店铺的每日订单量"
  dong company start --domain "帮我追踪AI行业最新论文"

流程:
  1. Agent 上网搜索该领域的数据源/API/策略
  2. 自动配置监控规则和频率
  3. 按计划执行 tick (数据采集+分析)
  4. 异常时自动告警
  5. 每天生成领域日报
  6. 每次执行后复盘，经验存入 skill
"""

import json, time, re, traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from . import Domain, register


@register
class AutonomousDomain(Domain):
    """全自营领域 — 用自然语言描述，Agent 自己学会运营"""

    name = "auto"
    description = "全自营领域引擎 — 你说需求，Agent 自己学会运营"

    def __init__(self, runtime, config=None):
        super().__init__(runtime, config or {})
        self.domain_prompt = ""
        self._plan: dict = {}
        self._last_check: dict = {}
        self._findings: list[dict] = []
        self._ticks = 0

    def init(self):
        """初始化: 用 Agent 研究这个领域，制定运营计划"""
        self.domain_prompt = self.config.get("description", self.config.get("prompt", ""))

        if not self.domain_prompt:
            self.alert("⚠️ 未指定领域描述，请在配置中设置 description", "warn")
            return

        self.alert(f"🔍 研究领域: {self.domain_prompt[:60]}...")
        plan = self._research_domain(self.domain_prompt)
        if plan:
            self._plan = plan
            self._save_plan()
            self.alert(f"✅ 运营计划已生成: {len(plan.get('tasks',[]))} 项任务")
        else:
            self.alert("⚠️ 未能生成运营计划，将使用默认策略", "warn")
            self._plan = self._default_plan()

    def _research_domain(self, prompt: str) -> dict:
        """用 CEO 研究领域并生成运营计划"""
        try:
            from dong_ai.model_pool import ModelPool
            pool = ModelPool()

            # 搜索该领域相关资料
            search_results = ""
            try:
                from dong_ai.web_search import search_formatted
                search_results = search_formatted(f"{prompt} 数据源 API 监控策略", 5)
            except Exception:
                pass

            system = (
                "你是一个领域运营专家。分析用户需求，制定自动化运营计划。\n"
                "输出 JSON 格式，不要其他文字：\n"
                "{\n"
                '  "name": "领域简称",\n'
                '  "description": "领域描述",\n'
                '  "tasks": [\n'
                '    {\n'
                '      "name": "任务名",\n'
                '      "interval_minutes": 60,\n'
                '      "action": "web_search|web_fetch|analyze|report",\n'
                '      "prompt": "执行时的具体指令",\n'
                '      "alert_on": "触发告警的条件描述"\n'
                "    }\n"
                "  ],\n"
                '  "data_sources": ["数据源1"],\n'
                '  "alert_channels": ["log"]\n'
                "}"
            )

            user_msg = f"用户需求: {prompt}\n\n"
            if search_results:
                user_msg += f"搜索到的相关资料:\n{search_results[:1000]}\n\n"
            user_msg += "请制定运营计划，JSON 格式。"

            resp = ""
            for token in pool.call_stream(
                [{"role": "user", "content": user_msg}],
                system=system,
                max_tokens=2048, temperature=0.3,
            ):
                resp += token

            # 提取 JSON
            json_match = re.search(r'\{.*\}', resp, re.DOTALL)
            if json_match:
                plan = json.loads(json_match.group())
                if isinstance(plan, dict) and "tasks" in plan:
                    return plan
        except Exception as e:
            self.alert(f"研究失败: {e}", "warn")

        return self._default_plan()

    def _default_plan(self) -> dict:
        """兜底计划"""
        return {
            "name": self.domain_prompt[:20],
            "description": self.domain_prompt,
            "tasks": [
                {
                    "name": "领域情报收集",
                    "interval_minutes": 60,
                    "action": "web_search",
                    "prompt": f"搜索关于 {self.domain_prompt} 的最新信息和动态",
                    "alert_on": "发现重大变化或异常",
                },
                {
                    "name": "状态分析",
                    "interval_minutes": 1440,
                    "action": "analyze",
                    "prompt": f"分析 {self.domain_prompt} 的当前状态和趋势",
                    "alert_on": "出现需要关注的变化",
                },
            ],
            "data_sources": ["web"],
            "alert_channels": ["log"],
        }

    def tick(self):
        """按计划执行任务"""
        super().tick()
        self._ticks += 1

        if not self._plan.get("tasks"):
            return

        for task in self._plan["tasks"]:
            interval = task.get("interval_minutes", 60)
            task_name = task.get("name", "未知任务")

            # 检查是否到执行时间
            last = self._last_check.get(task_name, 0)
            if time.time() - last < interval * 60:
                continue

            self._last_check[task_name] = time.time()
            self._execute_task(task)

    def _execute_task(self, task: dict):
        """执行单个运营任务"""
        task_name = task.get("name", "任务")
        action = task.get("action", "web_search")
        prompt = task.get("prompt", "")
        alert_on = task.get("alert_on", "")

        try:
            from dong_ai.model_pool import ModelPool
            pool = ModelPool()
            result = ""

            if action == "web_search":
                from dong_ai.web_search import search_formatted
                result = search_formatted(prompt, 5)
                result = result or "无搜索结果"
            elif action == "web_fetch":
                from dong_ai.mcp_servers.web_tools import fetch_url
                url = prompt.strip()
                if url.startswith("http"):
                    r = fetch_url(url)
                    result = r.get("content", "")[:2000]
            elif action == "analyze":
                # 用 LLM 分析
                for token in pool.call_stream(
                    [{"role": "user", "content": prompt}],
                    system="你是领域分析专家。简洁、有洞察。",
                    max_tokens=1024, temperature=0.3,
                ):
                    result += token

            # 记录发现
            finding = {
                "time": datetime.now().isoformat(),
                "task": task_name,
                "result": result[:500],
            }
            self._findings.append(finding)

            # 检查是否需要告警
            if alert_on and result:
                alert_check = ""
                for token in pool.call_stream(
                    [{"role": "user", "content": f"任务结果:\n{result[:1000]}\n\n告警条件: {alert_on}\n\n是否需要告警？只输出 YES 或 NO。"}],
                    system="告警判断专家。只输出 YES 或 NO。",
                    max_tokens=10, temperature=0,
                ):
                    alert_check += token
                if "YES" in alert_check:
                    self.alert(f"🔔 {task_name}: {result[:200]}")

            self.runtime._log("auto_domain", f"{task_name} 完成")

        except Exception as e:
            self.alert(f"⚠️ {task_name} 执行失败: {e}", "warn")

    def report(self) -> str:
        """领域日报"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            f"🌐 自营领域日报 — {now}",
            f"{'='*40}",
            f"领域: {self._plan.get('description', self.domain_prompt)[:60]}",
            f"运营计划: {len(self._plan.get('tasks',[]))} 项任务",
            f"今日发现: {len(self._findings)} 条",
        ]
        if self._findings:
            lines.append(f"\n最近发现:")
            for f in self._findings[-5:]:
                lines.append(f"  [{f['task']}] {f['result'][:100]}")
        self._findings.clear()
        return "\n".join(lines)

    def _save_plan(self):
        """持久化运营计划"""
        path = self.config_path
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "description": self.domain_prompt,
            "plan": self._plan,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
