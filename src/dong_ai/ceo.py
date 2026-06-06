"""Dong AI — CEO (v2)

薄协调器，拆分为独立引擎：
  DesignEngine → 设计阶段
  WorkerPool → 阶段执行（并行工人）
  ReviewBoard → 评分
"""

import json, os, copy, re, sys, time
from pathlib import Path
from datetime import datetime, timezone

from .datastore import get_repo
from .llm import create_client
from .design_engine import DesignEngine
from .logger import get_logger

log = get_logger("ceo")


class CEO:
    """CEO — 项目全流程协调器"""

    def __init__(self, project_dir: str = None, design_engine=None,
                 llm_client=None, experience_engine=None):
        self.project_dir = Path(project_dir or Path.home() / ".dong" / "projects" / "current")
        self.project_dir.mkdir(parents=True, exist_ok=True)

        if llm_client is not None:
            self.llm = llm_client
        else:
            from .model_pool import ModelPool
            from .llm import LLMConfig
            pool = ModelPool()
            try:
                best = pool.best()
                cfg = LLMConfig(
                    model=best["models"][0],
                    base_url=best["base_url"],
                    api_key=best.get("api_key", ""),
                )
            except RuntimeError:
                cfg = LLMConfig()
            self.llm = create_client(cfg)
        self.ds = get_repo("project")
        self.design_engine = design_engine or DesignEngine(self.llm, self.ds)
        self.experience_engine = experience_engine

        self.plan = {}
        self.plan_path = self.project_dir / "plan.json"
        self.checkpoint_path = self.project_dir / "checkpoint.json"
        self.report_path = self.project_dir / "final_report.md"
        self._evidence = []  # 执行证据
        self._design = ""
        self._requirements = []  # 设计需求清单

        # 读取模式
        self._mode_config = {}
        try:
            from .ceo_memory import CEOMemory
            mem = CEOMemory()
            full_cfg = mem.config_load()
            self._mode = full_cfg.get("mode", "auto")
            self._mode_config = {
                "ceo_context": int(full_cfg.get("ceo_context", full_cfg.get("context_length", 64000))),
                "ceo_max_tokens": int(full_cfg.get("ceo_max_tokens", full_cfg.get("max_response", 8192))),
                "worker_context": int(full_cfg.get("worker_context", 16000)),
                "worker_max_tokens": int(full_cfg.get("worker_max_tokens", 4096)),
            }
        except Exception:
            self._mode = "auto"
            self._mode_config = {"ceo_context": 32768, "ceo_max_tokens": 8192}

    def run(self, user_request: str, resume: bool = False):
        """全流程入口 — 自动识别项目类型，路由到对应管线"""
        log.info("ceo_run", request=user_request[:50], resume=resume)

        if resume:
            ckpt = self._load_checkpoint()
            if ckpt:
                print(f"  📋 检测到上次中断，从阶段 {ckpt['phase_idx']+1} 恢复")
                self.plan = ckpt.get("plan", {})
                phases = ckpt.get("phases", [])
                start_idx = ckpt["phase_idx"]
                project_type = ckpt.get("project_type", "software")
            else:
                print("  ⚠️ 没有 checkpoint，从头开始")
                resume = False

        if not resume:
            print("\n" + "█" * 60)
            print(f"  Dong AI 启动 | {user_request[:40]}")
            print("█" * 60)

            # 识别项目类型
            project_type = self._detect_project_type(user_request)
            self._project_type = project_type
            type_labels = {
                "software": "💻 软件开发",
                "novel": "📖 小说创作",
                "game": "🎮 游戏开发",
                "analysis": "📊 分析报告",
                "audit": "🔍 审计审查",
            }
            print(f"  📋 识别项目类型: {type_labels.get(project_type, project_type)}")

            # 加载相关技能
            skill_context = ""
            try:
                from .memory import load_relevant_skills, format_skills_for_prompt
                skills = load_relevant_skills(user_request)
                if skills:
                    skill_context = format_skills_for_prompt(skills)
                    print(f"  📚 加载 {len(skills)} 个相关技能")
            except Exception:
                pass

            # 加载历史经验
            experience_context = ""
            if self.experience_engine:
                try:
                    experience_context = self.experience_engine.recall(
                        user_request, project_type)
                    if experience_context:
                        print(f"  📖 加载 {experience_context.count('###')} 条历史经验")
                except Exception:
                    pass

            # 设计阶段
            print("\n  📋 设计阶段")
            enriched_request = user_request
            if skill_context:
                enriched_request = f"{user_request}\n\n{skill_context}"
            if experience_context:
                enriched_request = f"{enriched_request}\n\n{experience_context}"
            design_result = self.design_engine.design(enriched_request)
            print(f"  ✅ 设计完成，评分: {design_result['score']:.1f}")
            self._requirements = design_result.get("requirements", [])
            if self._requirements:
                print(f"  📋 拆解为 {len(self._requirements)} 条可验证需求")
                for r in self._requirements[:5]:
                    print(f"     [{r['id']}] {r['desc'][:50]}")
                if len(self._requirements) > 5:
                    print(f"     ... 共 {len(self._requirements)} 条")
            self.ds.add_decision("design_final", design_result["design"][:500])
            self._design = design_result["design"]

            # 根据项目类型生成管线阶段
            phases = self._build_pipeline(project_type, design_result["design"])
            self.plan = {"project_name": design_result.get("project_name", "未知"), "phases": phases}
            (self.plan_path).write_text(json.dumps(self.plan, ensure_ascii=False, indent=2))
            start_idx = 0

        # 执行阶段
        for p_idx in range(start_idx, len(phases)):
            phase = phases[p_idx]
            phase_name = phase.get("name", f"阶段{p_idx+1}")
            print(f"\n  📋 执行 {p_idx+1}/{len(phases)}: {phase_name}")

            # 跑 WorkerPool
            success = self._execute_phase(phase, p_idx)

            # 董事会评分
            score = self._board_review(phase_name, phase.get("tasks", []))
            self.ds.add_decision(f"phase_{p_idx}_board", f"阶段评分: {score}", score=score)
            print(f"  📋 {phase_name} 评分: {score:.1f}")

            # 需求覆盖率检
            if self._requirements and p_idx < len(phases):
                task_ids = [t.get("id", "") for t in phase.get("tasks", [])]
                cov = self.design_engine.get_coverage(self._requirements, task_ids)
                if cov["missing"]:
                    print(f"  ⚠️ 未覆盖需求 ({len(cov['missing'])} 条):")
                    for r in cov["missing"][:3]:
                        print(f"     [{r['id']}] {r['desc'][:60]}")
                    # 未覆盖需求扣分
                    penalty = min(3.0, len(cov["missing"]) * 0.5)
                    score = max(1.0, score - penalty)
                    print(f"  📋 扣分 {penalty:.1f}，最终评分: {score:.1f}")

            # 阶段门：评分 < 6.0 不放行
            if score < 6.0:
                print(f"  🚫 {phase_name} 评分低于阈值(6.0)，项目终止")
                self.ds.add_decision(f"phase_{p_idx}_gate", f"BLOCKED: 评分{score}", score=score)
                break

            # checkpoint
            self._save_checkpoint(p_idx, phases, self.plan)

            if not success:
                print(f"  ⚠️ {phase_name} 未完全通过，进入报告阶段")
                break

        # 清理 checkpoint（项目完成时）
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()

        # 最终报告
        report = self._generate_report()
        self.report_path.write_text(report, encoding="utf-8")
        print(f"\n  📋 项目完成 | 报告: {self.report_path}")

        # 复盘 → 经验固化
        if self.experience_engine:
            try:
                scores = []
                for p in self.plan.get("phases", []):
                    pname = p.get("name", "")
                    decs = self.ds.get_decisions(f"phase_{pname}_board")
                    if decs:
                        scores.append(decs[-1].get("score", 7.0))
                path = self.experience_engine.debrief(
                    project_type, user_request, self._design,
                    self.plan.get("phases", []), scores or [7.0],
                    report, self._requirements,
                )
                print(f"  📖 经验已存档 | {Path(path).name}")
            except Exception as e:
                print(f"  ⚠️ 复盘失败: {e}")

    # ── 设计 → 计划 ──

    def _make_plan(self, design: str) -> dict:
        """拆模块"""
        plan_str = self.llm.chat([
            {"role": "user", "content": (
                f"设计方案：\n{design}\n\n"
                f"拆成可独立开发的模块(3-6个)，输出JSON：\n"
                f"{{'project_name':'','modules':[{{'id':'m1','name':'','description':'','deps':[],'prompt':''}}]}}"
            )}
        ], system="项目规划专家。输出严格JSON。", max_tokens=8192, temperature=0.3)

        json_match = re.search(r'\{.*\}', plan_str.text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except Exception:
                pass
        return {"project_name": "未知", "modules": []}

    def _split_phases(self, plan: dict) -> list:
        """按依赖分组"""
        modules = plan.get("modules", [])
        remaining = set(m["id"] for m in modules)
        mod_map = {m["id"]: m for m in modules}
        phases = []
        while remaining:
            current = []
            for mid in list(remaining):
                m = mod_map[mid]
                deps = set(m.get("deps", []))
                if deps.isdisjoint(remaining) or deps.issubset(set(remaining) - {mid}):
                    if deps.isdisjoint(remaining):
                        current.append(m)
            if not current:
                current = [mod_map[next(iter(remaining))]]
            for m in current:
                remaining.discard(m["id"])
            phases.append({
                "name": f"阶段{len(phases)+1}",
                "tasks": [
                    {"name": m["name"], "description": m.get("description", ""),
                     "id": m["id"], "deps": m.get("deps", [])}
                    for m in current
                ],
            })
        return phases

    # ── 阶段执行（WorkerPool）──

    def _execute_phase(self, phase: dict, phase_idx: int) -> bool:
        """用 WorkerPool 执行一个阶段的所有任务，捕获证据"""
        from worker import WorkerPool

        wp = WorkerPool(str(self.project_dir))
        all_ok = True

        for task in phase.get("tasks", []):
            task_name = task.get("name", task.get("id", "unknown"))
            print(f"    ▶ 任务: {task_name}")
            self.ds.add_decision(f"phase_{phase_idx}_task_start", f"启动: {task_name}")

            result = wp.assign_task(
                task,
                design=getattr(self, "_design", ""),
                context=f"项目: {self.plan.get('project_name', '')}",
            )

            status = "done" if result.get("status") == "done" else "failed"
            quality = result.get("quality_score", 0)

            # 捕获证据
            evidence = {
                "task_name": task_name,
                "status": status,
                "quality_score": quality,
                "files": result.get("files", []),
                "test_count": result.get("test_count", 0),
                "test_pass": result.get("test_pass", 0),
                "interfaces": result.get("interfaces", []),
                "lessons": result.get("lessons", []),
            }
            self._evidence.append((phase_idx, task_name, evidence))

            self.ds.add_decision(
                f"phase_{phase_idx}_task_{task.get('id', '?')}",
                f"{task_name}: {status} (质量{quality:.1f}, 测试{evidence['test_pass']}/{evidence['test_count']})",
                score=quality,
            )

            if status != "done":
                all_ok = False
                print(f"    ❌ {task_name} 失败")
            else:
                print(f"    ✅ {task_name}: {len(evidence['files'])} 文件, {evidence['test_pass']}/{evidence['test_count']} 测试通过")

        return all_ok

    # ── 董事会评分 ──

    def _board_review(self, phase_name: str, tasks: list) -> float:
        """用 LLM 给阶段质量打分"""
        if not tasks:
            return 7.0
        task_desc = "\n".join(f"- {t.get('name', '?')}: {t.get('description', '')[:100]}" for t in tasks)
        decisions = self.ds.get_decisions(limit=10)
        decision_text = "\n".join(f"  [{d['phase']}] {d['content'][:100]}" for d in decisions)

        prompt = (
            f"阶段名称: {phase_name}\n"
            f"任务清单:\n{task_desc}\n\n"
            f"阶段执行记录:\n{decision_text}\n\n"
            f"请根据任务完成情况和执行质量，给这个阶段综合评分(1-10)。\n"
            f"输出格式：总分: X.X"
        )
        resp = self.llm.chat(
            [{"role": "user", "content": prompt}],
            system="严格的评审委员。8分以上已经很优秀。",
            max_tokens=200, temperature=0.1,
        )
        try:
            score = float(re.search(r'总分[：:]\s*(\d+\.?\d*)', resp.text).group(1))
            return max(1.0, min(10.0, score))
        except Exception:
            return 7.0

    # ── Checkpoint ──

    def _save_checkpoint(self, phase_idx: int, phases: list, plan: dict):
        """保存执行状态，支持中断恢复"""
        ckpt = {
            "phase_idx": phase_idx,
            "phases": phases,
            "plan": plan,
            "project_type": getattr(self, "_project_type", "software"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.checkpoint_path.write_text(json.dumps(ckpt, ensure_ascii=False, indent=2))
        log.info("checkpoint_saved", phase_idx=phase_idx)

    # ── 项目类型检测与管线路由 ──

    def _detect_project_type(self, request: str) -> str:
        """识别项目类型：software / novel / game / analysis / audit"""
        try:
            resp = self.llm.chat([{"role": "user", "content": (
                f"用户需求：{request[:200]}\n\n"
                f"判断这是哪种项目类型？只输出类型名，不要其他内容：\n"
                f"software - 软件开发/工具/系统/API\n"
                f"novel    - 小说/故事/创作/世界观\n"
                f"game     - 游戏/交互/玩法\n"
                f"analysis - 分析/研究/报告\n"
                f"audit    - 审计/审查/检查"
            )}], system="分类专家。只输出类型名。", max_tokens=50, temperature=0.1)
            for t in ("software", "novel", "game", "analysis", "audit"):
                if t in resp.text.lower():
                    return t
        except Exception:
            pass
        return "software"

    def _build_pipeline(self, project_type: str, design: str) -> list:
        """CEO 根据项目类型 + 设计，用 LLM 动态生成管线"""
        try:
            resp = self.llm.chat([{"role": "user", "content": (
                f"项目类型：{project_type}\n"
                f"设计方案：{design[:2000]}\n\n"
                f"为这个项目设计执行管线（3-6个阶段），每个阶段包含1-3个任务。\n"
                f"任务间用 deps 表达依赖关系。\n"
                f"只输出 JSON，不要其他内容：\n"
                f'[\n'
                f'  {{"name":"阶段名","tasks":[{{"id":"t1","name":"任务名","description":"描述","deps":[]}}]}}\n'
                f']'
            )}], system="项目管理专家。输出严格JSON。", max_tokens=4096, temperature=0.3)

            json_match = re.search(r'\[.*\]', resp.text, re.DOTALL)
            if json_match:
                phases = json.loads(json_match.group())
                if isinstance(phases, list) and len(phases) >= 2:
                    return phases
        except Exception:
            pass
        # 兜底：简单两阶段
        return [
            {"name": "规划", "tasks": [{"id": "plan", "name": "方案细化", "description": design[:200], "deps": []}]},
            {"name": "执行", "tasks": [{"id": "exec", "name": "落地执行", "description": "按设计方案执行", "deps": ["plan"]}]},
        ]

    def _load_checkpoint(self) -> dict:
        """加载 checkpoint"""
        if self.checkpoint_path.exists():
            try:
                return json.loads(self.checkpoint_path.read_text())
            except Exception:
                pass
        return {}

    # ── 报告 ──

    def _generate_report(self) -> str:
        """生成项目总结报告 — 含执行证据、文件清单、测试结果"""
        decisions = self.ds.get_decisions(limit=50)
        project_name = self.plan.get("project_name", "未知项目")

        lines = []
        lines.append(f"# {project_name} — 执行报告\n")
        lines.append(f"> 生成时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append(f"> 设计评分: {getattr(self.design_engine, '_last_score', '—')}\n")

        # === 设计决策 ===
        lines.append("---\n")
        lines.append("## 📋 设计决策\n")
        design_phases = {"premortem", "design_initial", "red_team_review", "design_final", "self_score"}
        for d in decisions:
            lines.append(f"- **[{d['phase']}]** {d['content'][:300]}")

        # === 执行记录 ===
        lines.append("\n---\n")
        lines.append("## 🏗️ 执行记录\n")
        for phase_idx, task_name, ev in self._evidence:
            icon = "✅" if ev["status"] == "done" else "❌"
            lines.append(f"\n### {icon} 阶段{phase_idx+1}/{task_name}\n")
            lines.append(f"- 状态: {ev['status']}")
            lines.append(f"- 质量评分: {ev['quality_score']:.1f}")
            lines.append(f"- 测试: {ev['test_pass']}/{ev['test_count']} 通过")

            if ev["files"]:
                lines.append(f"\n**产出文件 ({len(ev['files'])} 个):**\n")
                for f in ev["files"][:10]:
                    fp = Path(f)
                    try:
                        size = fp.stat().st_size if fp.exists() else 0
                        lines.append(f"- `{fp.name}` ({size:,} 字节)")
                    except Exception:
                        lines.append(f"- `{fp.name}`")

            if ev["lessons"]:
                lines.append(f"\n**经验教训:**\n")
                for l in ev["lessons"]:
                    lines.append(f"- [{l.get('severity','info')}] {l.get('pattern','')}: {l.get('detail','')[:100]}")

        # === 评分汇总 ===
        scores = [d["score"] for d in decisions if d.get("score", 0) > 0]
        if scores:
            lines.append("\n---\n")
            lines.append("## 📊 评分汇总\n")
            avg = sum(scores) / len(scores)
            lines.append(f"- **平均评分:** {avg:.2f}")
            lines.append(f"- **最高分:** {max(scores):.1f}")
            lines.append(f"- **最低分:** {min(scores):.1f}")
            lines.append(f"- **评分次数:** {len(scores)}")

            # 可视化评分条
            bar_len = 20
            filled = int(avg / 10 * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            lines.append(f"\n  {bar} {avg:.1f}/10\n")

        # === 项目资产 ===
        if self._evidence:
            all_files = set()
            for _, _, ev in self._evidence:
                for f in ev.get("files", []):
                    all_files.add(f)
            if all_files:
                lines.append("\n---\n")
                lines.append("## 📁 项目资产\n")
                lines.append(f"- 计划文件: `{self.plan_path}`")
                lines.append(f"- 执行报告: `{self.report_path}`")
                lines.append(f"- 产出文件: {len(all_files)} 个")
                lines.append(f"- 工作目录: `{self.project_dir / 'work/'}`")

        # === 模型信息 ===
        lines.append("\n---\n")
        lines.append("## ⚙️ 技术信息\n")
        lines.append(f"- 引擎: Dong AI Company v{getattr(__import__('dong_ai'), '__version__', '0.1.0')}")
        from model_pool import ModelPool
        pool = ModelPool()
        try:
            best = pool.best()
            lines.append(f"- 主模型: {best['name']} ({best['models'][0]})")
            lines.append(f"- 可用模型: {len(pool.available())} 个")
        except Exception:
            pass

        return "\n".join(lines)
