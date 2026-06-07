"""Dongcode 工人调度 v4 — 动态员工生成 + 并行执行 + 交叉审查

不再有固定的 A/B/C 角色。
CEO 用 LLM 分析任务 → 动态生成需要的员工 → 他们自己干活 → 互相审查。

HTTP 调用统一走 ModelPool（自动 failover）。"""
from __future__ import annotations

import json, os, re, subprocess
from pathlib import Path
from typing import Any


class WorkerPool:
    def __init__(self, project_dir: str, model_endpoint: str = None) -> None:
        self.project_dir = Path(project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.model_endpoint = model_endpoint or ""
        self.model_name = "deepseek-chat"  # 向后兼容
        self.api_key = ""  # 向后兼容
        self.work_dir = self.project_dir / "work"
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def _llm_call(self, messages: list, system: str = "", **kwargs: Any) -> str:
        """统一 LLM 调用——走 ModelPool 自动 failover，失败时返回错误字符串"""
        from .model_pool import ModelPool
        max_tokens = kwargs.pop("max_tokens", 4096)
        temperature = kwargs.pop("temperature", 0.3)
        timeout = kwargs.pop("timeout", 120)
        try:
            return ModelPool().call(messages, system=system,
                                    max_tokens=max_tokens,
                                    temperature=temperature,
                                    timeout=timeout)
        except RuntimeError as e:
            return f"<API_ERROR: {e}>"
        except Exception as e:
            return f"<API_ERROR: {e}>"

    # ── CodeGraph 图记忆 ──

    def _get_graph_context(self, task_name: str, design: str) -> str:
        """查询图记忆，构造任务相关上下文"""
        try:
            from .datastore import get_repo
            gr = get_repo("graph")
            # 从任务名 + 设计中提取关键词
            import re
            words = set(re.findall(r'[a-zA-Z_]\w{2,}', task_name + " " + design))
            keywords = list(words)[:8]
            return gr.format_context("current", keywords)
        except Exception:
            return ""

    def _index_task_output(self, task_id: str, files: list, interfaces: list, lessons: list) -> None:
        """任务完成后，将产出写入图记忆"""
        try:
            from .datastore import get_repo
            gr = get_repo("graph")
            for f in files:
                gr.add_node("current", "file", Path(f).name, file_path=f)
            for iface in interfaces:
                gr.add_node("current", "function" if "(" in iface.get("signature","") else "interface",
                            iface.get("name","?"), file_path=iface.get("module_id",""),
                            signature=iface.get("signature",""))
            for l in lessons:
                gr.add_node("current", "lesson", l.get("pattern","")[:50],
                            detail=l.get("detail","")[:200])
        except Exception:
            pass

    def assign_task(self, task: dict, design: str, context: str, difficulty: int = 2) -> dict:
        """CEO 派活流程 + CodeGraph 记忆"""
        import concurrent.futures
        task_id = task.get("id", task.get("name", "unknown"))
        safe_id = "".join(c for c in task_id if c.isalnum() or c in "_-").strip() or "task"
        task_name = task.get("name", safe_id)
        mod_dir = self.work_dir / safe_id
        mod_dir.mkdir(exist_ok=True)

        # 注入图记忆上下文
        graph_context = self._get_graph_context(task_name, design)
        enriched_context = f"{context}\n{graph_context}" if graph_context else context

        self._stream("🏭 开工", f"{task_name}")
        result = {
            "module_id": task_id, "status": "failed",
            "files": [], "test_count": 0, "test_pass": 0,
            "quality_score": 0, "lessons": [], "interfaces": [],
        }

        for round_num in range(1, 4):
            if difficulty == 1 and round_num == 1:
                # Fast path: skip LLM worker generation, go straight to edit
                workers = [{"id": "editor", "name": "Editor",
                           "role": "修改文件", "mission": task_name,
                           "budget": 64000, "tools": ["read_file", "write_file"],
                           "rules": ["精确修改", "保持原有风格"],
                           "output_format": "修改后的完整文件"}]
            else:
                workers = self._generate_workers(task_name, design, context, f"第{round_num}轮", difficulty)
            self._stream("👥 员工", f"{' + '.join(w['name'] for w in workers)}")

            worker_results = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(workers)) as pool:
                futures = {}
                for w in workers:
                    w_dir = mod_dir / w["id"]
                    w_dir.mkdir(exist_ok=True)
                    self._stream(f"  {w['name']}", f"启动 ({w['budget']})")
                    future = pool.submit(self._run_worker_self_healing, w, task_id, task_name, w_dir, design, enriched_context)
                    futures[future] = w
                for future in concurrent.futures.as_completed(futures):
                    w = futures[future]
                    try:
                        w_result = future.result(timeout=300)
                        worker_results[w["id"]] = w_result
                        if w_result["status"] == "ok":
                            self._stream(f"  ✅ {w['name']}", f"完成 ({len(w_result.get('files',[]))} 文件)")
                        else:
                            self._stream(f"  ❌ {w['name']}", f"{w_result.get('error','未知错误')[:60]}")
                    except Exception as e:
                        self._stream(f"  ❌ {w['name']}", f"异常: {str(e)[:60]}")
                        worker_results[w["id"]] = {"status": "error", "error": str(e), "files": [], "interfaces": [], "lessons": []}

            review_passed = True
            if len(workers) >= 2 and difficulty > 1:
                self._stream("🔄 交叉审查", "")
                review_passed = self._cross_review(workers, worker_results, task_id, mod_dir)
                if not review_passed:
                    self._stream("⚠️ 审查未通过", "注入反馈重试")
                    feedbacks = []
                    for wid, wr in worker_results.items():
                        if wr.get("review_notes"):
                            feedbacks.append(f"[{wid}] {wr['review_notes']}")
                    if feedbacks:
                        design += "\n[审查反馈]\n" + "\n".join(feedbacks[:5])
                    continue
                self._stream("✅ 审查通过", "")

            self._stream("🧪 真实测试", "")
            test_count, test_pass, test_errors = self._run_real_tests(mod_dir)
            if test_count > 0 and test_pass < test_count:
                self._stream("❌ 测试失败", f"{test_pass}/{test_count}")
                design += "\n[测试失败]\n" + "\n".join(test_errors[:3])
                continue
            self._stream("✅ 测试通过", f"{test_pass}/{test_count}")

            all_files, all_interfaces, all_lessons = [], [], []
            for wr in worker_results.values():
                all_files.extend(wr.get("files", []))
                all_interfaces.extend(wr.get("interfaces", []))
                all_lessons.extend(wr.get("lessons", []))
            quality = 10.0 if test_pass == test_count else min(10.0, 10.0 * test_pass / max(test_count, 1))
            self._stream(f"✅ 第{round_num}轮通过", f"质量{quality:.1f}")
            result["status"] = "done"
            result["files"] = list(set(all_files))
            result["test_count"] = test_count
            result["test_pass"] = test_pass
            result["quality_score"] = quality
            result["interfaces"] = all_interfaces
            result["lessons"] = all_lessons
            # 写入图记忆
            self._index_task_output(task_id, all_files, all_interfaces, all_lessons)
            break
        return result

    def _stream(self, topic: str, msg: str) -> None:
        print(f"  [{topic}] {msg}")

    def _run_worker_self_healing(self, worker: dict, task_id: str, task_name: str, w_dir: Path, design: str, context: str) -> dict:
        """工人执行，自带自愈循环：失败了自己重试，最多 3 次"""
        last_error = ""
        for attempt in range(1, 4):
            try:
                if last_error:
                    worker["mission"] += f"\n\n⚠️ 上次尝试反馈: {last_error[:300]}"
                    worker["rules"].append("不要重复上次的错误做法")
                result = self._run_worker(worker, task_id, task_name, w_dir, design, context)
                if result["status"] == "ok":
                    if result.get("files") or result.get("interfaces"):
                        return result
                    if attempt < 3:
                        last_error = "产出为空"
                        worker["mission"] += "\n注意：上次产出为空，请确保输出具体内容。"
                        worker["rules"].append("必须输出至少一个文件")
                        continue
                else:
                    if attempt < 3:
                        last_error = result.get("error", "未知错误")
                        worker["mission"] += f"\n注意：上次失败({last_error})，换一种方式重试。"
                        continue
                return result
            except Exception as e:
                last_error = str(e)
                if attempt < 3:
                    continue
                return {"status": "error", "error": str(e), "files": [], "interfaces": [], "lessons": []}
        return {"status": "error", "error": "自愈失败", "files": [], "interfaces": [], "lessons": []}

    # ── CEO 用 LLM 动态生成员工 ──
    def _generate_workers(self, task_name: str, design: str, context: str, round_label: str, difficulty: int = 2) -> list:
        prompt = (
            f"任务: {task_name}\n"
            f"设计方案: {design[:1000]}\n"
            f"上下文: {context[:500]}\n"
            f"难度等级: {difficulty} (1=简单改动, 2=中等, 3=复杂)\n\n"
            f"难度1: 最多1人，无需交叉审查，直接执行\n"
            f"难度2: 2人，轻量交叉审查\n"
            f"难度3: 2-3人，完整交叉审查\n\n"
            f"请输出 JSON 格式员工清单（只输出 JSON，不要其他内容）：\n\n"
            "[\n"
            "  {\n"
            '    "id": "唯一的英文ID",\n'
            '    "name": "中文花名（2-4字，有互联网风格幽默感，如: 数据猎手/逻辑判官/代码浪人）",\n'
            '    "role": "一句话描述角色",\n'
            '    "mission": "这个员工的具体任务",\n'
            '    "budget": 64000,\n'
            '    "tools": ["web_search", "opencode", "codegraph", "pytest"],\n'
            '    "rules": ["规则1", "规则2"],\n'
            '    "output_format": "输出的格式要求"\n'
            "  }\n"
            "]\n\n"
            f"要求：\n"
            f"- 人数取决于任务复杂度，不是越多越好\n"
            f"- 代码任务至少配一个测试人员\n"
            f"- 涉及接口的任务要配集成检查人员\n"
            f"- 姓名要个性化，不要\"程序员A\"这类死板命名\n"
            f"- 预算：代码类 64K，其他 32K 或 16K\n"
            f"- 所有员工都可以使用 web_search 工具搜索网络资料\n"
        )
        resp = self._llm_call(
            [{"role": "user", "content": prompt}],
            system="你是一个项目规划专家。你负责分析任务需求，动态组建最合适的员工团队。",
            max_tokens=4096, temperature=0.5,
        )
        json_match = re.search(r'\[.*\]', resp, re.DOTALL)
        if json_match:
            try:
                workers = json.loads(json_match.group())
                if isinstance(workers, list) and len(workers) > 0:
                    return workers
            except: pass
        return [{
            "id": "coder", "name": "代码匠",
            "role": "负责写代码", "mission": task_name,
            "budget": 65536, "tools": ["web_search", "opencode", "codegraph"],
            "rules": ["写完整代码", "加注释", "不确定时先搜索查资料"],
            "output_format": "Python 文件",
        }, {
            "id": "tester", "name": "测试判官",
            "role": "负责写测试", "mission": f"为{task_name}写测试",
            "budget": 32768, "tools": ["web_search", "pytest"],
            "rules": ["覆盖正常和边界情况", "遇到不熟悉的用法先搜索"],
            "output_format": "pytest 测试文件",
        }]

    # ── 执行一个员工 ──
    def _run_worker(self, worker: dict, task_id: str, task_name: str, w_dir: Path, design: str, context: str) -> dict:
        name = worker.get("name", "员工")
        role = worker.get("role", "")
        mission = worker.get("mission", task_name)
        tools = worker.get("tools", [])
        rules = worker.get("rules", [])
        output_fmt = worker.get("output_format", "")
        budget = worker.get("budget", 32768)

        tools_str = ", ".join(tools)
        rules_str = "\n".join(f"- {r}" for r in rules)
        has_search = "web_search" in tools
        search_note = (
            "\n\n🔍 你可以使用以下工具:\n"
            "- read_file(path): 读取项目文件内容\n"
            "- write_file(path, content): 写入/修改文件\n"
            "- list_files(path): 浏览目录结构\n"
            "- run(command): 执行 shell 命令\n"
            "- web_search(query): 搜索网络资料\n"
            "优先使用 read_file 读取项目中的现有代码，而不是从头编写。"
        ) if has_search else ""

        system = (
            f"你是「{name}」—— {role}\n\n"
            f"你的使命: {mission}\n\n"
            f"你可用的工具: {tools_str}\n\n"
            f"你的工作纪律:\n{rules_str}\n\n"
            f"上下文预算: {budget} tokens（不要超出）\n\n"
            f"输出格式: {output_fmt}{search_note}\n\n"
            f"注意: 你只负责自己的使命，不要替别人干活。不确定的标记为不确定。"
        )
        user_msg = (
            f"项目任务: {task_name}\n"
            f"设计方案: {design}\n"
            f"项目目录: {self.project_dir}\n"
            f"项目上下文:\n{context[:budget//4]}\n\n"
            f"请在你的项目目录中工作。使用 read_file 读取现有文件，write_file 写入修改。"
        )

        if "修改" in mission or "翻译" in mission or "替换" in mission or "重构" in mission or "src/" in user_msg or "refactor" in mission.lower() or "rewrite" in mission.lower() or "edit" in mission.lower():
            return self._worker_edit_impl(name, task_id, self.project_dir, system, user_msg)
        elif "opencode" in tools or "代码" in mission or "写" in mission or "实现" in mission:
            return self._worker_code_impl(name, task_id, w_dir, system, user_msg)
        elif "pytest" in tools or "测试" in mission:
            return self._worker_test_impl(name, task_id, w_dir, system, user_msg)
        elif "集成" in mission or "codegraph" in tools:
            return self._worker_review_impl(name, task_id, w_dir, system, user_msg)
        else:
            return self._worker_general_impl(name, task_id, w_dir, system, user_msg)

    # ── 代码类员工 ──
    def _worker_code_impl(self, name: str, task_id: str, w_dir: Path, system: str, user_msg: str) -> dict:
        target_file = w_dir / f"{task_id}.py"
        code = self._call_llm_with_tools(
            [{"role": "user", "content": user_msg}],
            system=system, max_tokens=8192, temperature=0.3,
        )
        blocks = re.findall(r'```(?:\w+)?\n(.*?)```', code, re.DOTALL)
        final = blocks[0] if blocks else code
        # Safety: skip if output is suspiciously tiny (likely LLM error)
        if len(final) < 10:
            print(f"        {name}: output too short ({len(final)} chars), skipped")
            return {"status": "ok", "files": [], "interfaces": [], "lessons": [],
                    "review_notes": "output too short, skipped"}
        target_file.write_text(final)
        print(f"        {name}: 写入 {target_file.name} ({len(final)} chars)")
        interfaces = []
        sigs = re.findall(r'def (\w+)\(([^)]*)\)(?:\s*->\s*(\w+))?', final)
        for fn, args, ret in sigs:
            interfaces.append({"module_id": task_id, "name": fn, "signature": args, "return_type": ret or ""})
        return {"status": "ok", "files": [str(target_file)], "interfaces": interfaces, "lessons": [], "review_notes": ""}

    # ── 修改类员工（直接改项目文件）──
    def _worker_edit_impl(self, name: str, task_id: str, proj_dir: Path, system: str, user_msg: str) -> dict:
        # Try to extract target file from user_msg directly (skip LLM call if path is clear)
        import re as _re
        direct_paths = _re.findall(r'(src/\\S+\\.py)', user_msg)
        if direct_paths:
            target = str(proj_dir / direct_paths[0])
            plan = f"修改文件: {target}"
        else:
            # Fall back to LLM to identify file
            plan = self._llm_call([{"role": "user", "content": (
                f"{user_msg}\\n\\n"
                f"项目目录: {proj_dir}\\n"
                f"首先，告诉我你要修改哪个文件？列出文件路径和修改方案。"
            )}], system=system, max_tokens=2048, temperature=0.3)
            paths = _re.findall(r'(src/dong_ai/\\S+\\.py)', plan)
            target = str(proj_dir / paths[0]) if paths else str(proj_dir / "src/dong_ai/cli.py")
        
        try:
            from pathlib import Path as _Path
            p = _Path(target)
            current = p.read_text(encoding="utf-8") if p.exists() else "(file not found)"
        except:
            current = "(read error)"

        # Now have LLM read the file and produce the modified version
        result = self._call_llm_with_tools(
            [{"role": "user", "content": (
                f"{user_msg}\n\n"
                f"项目目录: {proj_dir}\n"
                f"目标文件: {target}\n\n"
                f"当前文件内容 ({len(current.split(chr(10)))} 行):\n"
                f"```\n{current}\n```\n\n"
                f"请输出修改后的完整文件内容，用```python ... ```代码块包裹。"
                f"保持原始文件的缩进和风格。只做必要的修改。"
            )}],
            system=system, max_tokens=16384, temperature=0.3,
        )

        blocks = _re.findall(r'```(?:python)?\n(.*?)```', result, _re.DOTALL)
        new_content = blocks[0] if blocks else ""

        if new_content and new_content != current and len(new_content) > 100:
            # Safety: output length should be at least 50% of original
            if len(new_content) < len(current) * 0.5 and len(current) > 1000:
                print(f"        {name}: output too short ({len(new_content)} vs {len(current)} chars), skipped")
                return {"status": "ok", "files": [], "interfaces": [], "lessons": [],
                        "review_notes": f"output truncated: {len(new_content)} vs {len(current)}"}
            # Safety: output should have similar number of functions
            orig_funcs = current.count("def ")
            new_funcs = new_content.count("def ")
            if orig_funcs > 5 and new_funcs < orig_funcs * 0.7:
                print(f"        {name}: too few functions ({new_funcs} vs {orig_funcs}), skipped")
                return {"status": "ok", "files": [], "interfaces": [], "lessons": [],
                        "review_notes": f"functions dropped: {new_funcs} vs {orig_funcs}"}
            p = _Path(target)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(new_content, encoding="utf-8")
            print(f"        {name}: 修改 {p.name} ({len(new_content)} chars)")
            return {"status": "ok", "files": [str(p)], "interfaces": [],
                    "lessons": [{"pattern": f"edit_{task_id}", "detail": f"Modified {p.name}", "severity": "info"}],
                    "review_notes": f"Modified {p.name}"}
        else:
            print(f"        {name}: 未产生有效修改")
            return {"status": "ok", "files": [], "interfaces": [], "lessons": [], "review_notes": "no changes produced"}

    # ── 测试类员工 ──
    def _worker_test_impl(self, name: str, task_id: str, w_dir: Path, system: str, user_msg: str) -> dict:
        test_file = w_dir / f"test_{task_id}.py"
        code = self._call_llm_with_tools(
            [{"role": "user", "content": user_msg}],
            system=system, max_tokens=4096, temperature=0.3,
        )
        blocks = re.findall(r'```(?:\w+)?\n(.*?)```', code, re.DOTALL)
        final = blocks[0] if blocks else code
        test_file.write_text(final)
        test_count = len(re.findall(r'def test_', final))
        print(f"        {name}: 写入 {test_file.name} ({len(final)} chars, {test_count} 个测试)")
        issues = re.findall(r'(?:问题|bug|错误)[：:]\s*(.+?)[\n.]', code)
        review_notes = "; ".join(issues[:3]) if issues else ""
        return {"status": "ok", "files": [str(test_file)], "interfaces": [],
                "lessons": [{"pattern": f"{task_id} 测试", "detail": review_notes[:200], "severity": "info"}],
                "review_notes": review_notes}

    # ── 审查/集成类员工 ──
    def _worker_review_impl(self, name: str, task_id: str, w_dir: Path, system: str, user_msg: str) -> dict:
        review = self._call_llm_with_tools(
            [{"role": "user", "content": user_msg}],
            system=system, max_tokens=4096, temperature=0.3,
        )
        print(f"        {name}: 审查完成 ({len(review)} chars)")
        sigs = re.findall(r'(\w+)\(([^)]*)\)(?:\s*->\s*(\w+))?', review)
        interfaces = [{"module_id": task_id, "name": n, "signature": s.strip(), "return_type": r.strip() if r else ""} for n, s, r in sigs]
        return {"status": "ok", "files": [], "interfaces": interfaces,
                "lessons": [{"pattern": f"{task_id} 审查", "detail": review[:200], "severity": "info"}],
                "review_notes": review[:500]}

    # ── 通用员工 ──
    def _worker_general_impl(self, name: str, task_id: str, w_dir: Path, system: str, user_msg: str) -> dict:
        output = self._llm_call(
            [{"role": "user", "content": user_msg}],
            system=system, max_tokens=4096, temperature=0.3,
        )
        target_file = w_dir / f"{task_id}_output.txt"
        target_file.write_text(output)
        print(f"        {name}: 输出 {target_file.name} ({len(output)} chars)")
        return {"status": "ok", "files": [str(target_file)], "interfaces": [], "lessons": [], "review_notes": ""}

    # ── 交叉审查 ──
    def _cross_review(self, workers: list, results: dict, task_id: str, mod_dir: Path) -> bool:
        all_passed = True
        for w in workers:
            wid = w["id"]
            if wid not in results or results[wid]["status"] != "ok":
                continue
            peers = [p for p in workers if p["id"] != wid]
            for peer in peers:
                peer_id = peer["id"]
                if peer_id not in results:
                    continue
                peer_files = results[peer_id].get("files", [])
                peer_text = ""
                for f in peer_files:
                    p = Path(f)
                    if p.exists():
                        peer_text += f"\n=== {Path(f).name} ===\n{p.read_text()[:3000]}\n"
                if not peer_text:
                    continue
                review = self._llm_call(
                    [{"role": "user", "content": f"审查以下工作输出，是否与你的工作存在实际冲突（同名函数不同签名、互相矛盾的逻辑）。\n\n工作输出:\n{peer_text}\n\n仅当存在真实冲突时判'不兼容'，否则判'兼容'。\n只输出：兼容/不兼容 + 理由（一句话）"}],
                    system=f"你是{peer.get('name','')}，负责交叉审查。",
                    max_tokens=1024, temperature=0.2,
                )
                if "不兼容" in review or "不通过" in review or "incompatible" in review.lower() or "conflict" in review.lower():
                    all_passed = False
                    results[wid]["review_notes"] = (results[wid].get("review_notes", "") + f"\n{peer['name']}审查: {review[:200]}").strip()
                    print(f"        {wid} ← {peer['name']}: ⚠️ 不兼容")
                else:
                    print(f"        {wid} ← {peer['name']}: ✅ 兼容")
        return all_passed

    # ── 带工具调用的模型请求（ReAct 循环）──
    def _call_llm_with_tools(self, messages: list, system: str = "", max_tokens: int = 4096, temperature: float = 0.3, max_tool_turns: int = 5) -> str:
        """调模型，检测工具调用，执行工具，继续，最多 5 轮"""
        from .memory import get_registered_tools, call_plugin_tool
        from .model_pool import ModelPool

        tools = get_registered_tools()
        # 同时加载 MCP 工具
        mcp_tools_added = []
        try:
            from .mcp_client import discover_mcp_servers, MCPClient
            mcp_servers = discover_mcp_servers()
            for srv in mcp_servers:
                try:
                    client = MCPClient(srv["name"], srv["command"], srv.get("args", []))
                    if client.connect():
                        for t in client.list_tools():
                            mcp_tools_added.append({
                                "name": t.get("name", f"mcp_{srv['name']}"),
                                "description": t.get("description", f"MCP tool from {srv['name']}"),
                                "exec": f"mcp:{srv['name']}",
                                "skill": f"mcp:{srv['name']}",
                                "_client": client,
                                "_mcp_schema": t.get("inputSchema", {}),
                            })
                except Exception:
                    pass
        except Exception:
            pass

        all_tools = tools + mcp_tools_added
        tools_desc = "\n".join([f"- {t['name']}: {t['description']}" for t in all_tools])
        current_system = system + (
            f"\n\n可用工具:\n{tools_desc}\n\n"
            f"如果你想调用工具，在回复中写:\n"
            f"[TOOL_CALL: 工具名]\n参数名=参数值\n[/TOOL_CALL]\n"
            f"我会执行工具并把结果给你。"
        ) if tools else system

        full_content = ""
        user_msg = messages[-1]["content"] if messages else ""
        pool = ModelPool()

        for turn in range(max_tool_turns + 1):
            # 上下文压缩
            total_chars = sum(len(m.get("content", "")) for m in messages)
            if turn >= 2 and total_chars > 15000:
                from .model_pool import ModelPool as _MP
                _pool = _MP()
                keep = messages[-2:] if len(messages) >= 2 else messages
                old_msgs = messages[:-2] if len(messages) >= 2 else []
                old_text = "\n".join(
                    f"[{m.get('role','')}] {m.get('content','')[:300]}"
                    for m in old_msgs
                )[:6000]
                try:
                    compressed = _pool.call(
                        [{"role": "user", "content": old_text}],
                        system="压缩以下工作对话为一段200字以内的摘要，保留关键决策、发现的问题、已完成的步骤。",
                        max_tokens=1024, temperature=0.2,
                    )
                except Exception:
                    compressed = old_text[:300]
                _cs = compressed[:500]
                messages = [{"role": "system", "content": f"[历史摘要] {_cs}"}] + keep
                new_total = sum(len(m.get("content", "")) for m in messages)
                print(f"        📦 上下文压缩: {total_chars} → {new_total} chars "
                      f"(移除了 {len(messages) - len(keep)} 条旧消息)")

            # 调用模型
            try:
                response = pool.call(
                    messages if not current_system else
                    [{"role": "system", "content": current_system}] + messages,
                    max_tokens=max_tokens, temperature=temperature, timeout=120,
                )
            except Exception as e:
                return full_content or f"<API_ERROR: {e}>"

            full_content += response

            # 检测工具调用
            tool_match = re.search(r'\[TOOL_CALL:\s*(\w+)\](.*?)\[/TOOL_CALL\]', response, re.DOTALL)
            if not tool_match:
                break

            tool_name = tool_match.group(1)
            tool_args_text = tool_match.group(2).strip()
            tool_kwargs = {}
            for line in tool_args_text.split("\n"):
                line = line.strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    tool_kwargs[k.strip()] = v.strip()

            print(f"        🔧 调用工具: {tool_name}({tool_kwargs})")
            # 检查是否为 MCP 工具
            mcp_result = None
            for mt in mcp_tools_added:
                if mt["name"] == tool_name:
                    try:
                        mc = mt["_client"]
                        result = mc.call_tool(tool_name, tool_kwargs)
                        mcp_result = result.get("content", str(result))
                    except Exception as e:
                        mcp_result = f"<MCP_ERROR: {e}>"
                    break
            if mcp_result is not None:
                tool_result = mcp_result
            else:
                tool_result = call_plugin_tool(tool_name, **tool_kwargs)

            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"工具 {tool_name} 返回:\n{tool_result[:2000]}\n\n继续你的工作。"})
            current_system = ""

        return full_content

    # ── 真实跑 pytest ──
    def _run_real_tests(self, mod_dir: Path) -> tuple[int, int, list]:
        test_files = list(mod_dir.rglob("test_*.py"))
        if not test_files:
            return 0, 0, ["无测试文件"]
        try:
            venv_python = str(Path(__file__).parent / ".venv" / "bin" / "python3")
            if not os.path.exists(venv_python):
                venv_python = "python3"
            result = subprocess.run(
                [venv_python, "-m", "pytest", str(mod_dir), "-v", "--tb=short", "-q"],
                capture_output=True, text=True, timeout=30, cwd=str(mod_dir),
                env={**os.environ, "PYTHONPATH": str(mod_dir) + ":" + os.environ.get("PYTHONPATH", "")},
            )
            output = result.stdout + result.stderr
            total = len(re.findall(r'(?i)PASSED|FAILED|ERROR', output))
            fails = len(re.findall(r'(?i)FAILED|ERROR', output))
            errors = [l.strip() for l in output.split("\n") if "FAILED" in l or "ERROR" in l][:5]
            return total, total - fails, errors
        except subprocess.TimeoutExpired:
            return 0, 0, ["pytest 超时"]
        except Exception as e:
            return 0, 0, [f"测试异常: {e}"]
