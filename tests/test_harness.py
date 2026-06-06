"""Dong AI — 核心模块测试（使用 conftest fixtures）

覆盖:
  - DesignEngine
  - ToolExecutor
  - Datastore / Repository
  - DisplayEngine
  - LLMClient
"""

import os, sys, json, tempfile, time
from pathlib import Path

import pytest


# ═══════════════════════════════════════════════════════════
# DesignEngine
# ═══════════════════════════════════════════════════════════

class TestDesignEngine:
    """设计引擎测试"""

    def test_design_returns_dict(self, design_engine):
        result = design_engine.design("帮我写一个网站")
        assert isinstance(result, dict)
        assert "design" in result
        assert "score" in result
        assert result["score"] > 0

    def test_design_with_max_retries(self, project_repo):
        """低分 LLM 触发重试，最终返回不超过阈值"""
        from dong_ai.design_engine import DesignEngine
        llm = type("LowScoreLLM", (), {
            "chat": lambda self, msgs, system="", **kw: type("R", (), {"text": "总分: 7.0", "usage": {"prompt": 0, "completion": 0, "total": 0}, "json": lambda: {"score": 7}})(),
            "chat_json": lambda self, msgs, system="", **kw: {"score": 7},
            "_usage_total": {"prompt": 0, "completion": 0, "total": 0},
            "usage": {"prompt": 0, "completion": 0, "total": 0},
        })()
        engine = DesignEngine(llm, project_repo)
        result = engine.design("测试", max_retries=2)
        assert result["score"] <= 7.5

    def test_design_saves_decisions(self, design_engine, project_repo):
        """设计方案应写入数据库"""
        design_engine.design("做一个日志系统")
        decisions = project_repo.get_decisions()
        # 应该包含 premortem, design_initial, red_team_review, design_final, self_score
        phases = [d["phase"] for d in decisions]
        assert any("premortem" in p for p in phases)
        assert any("red_team" in p for p in phases)
        assert any("self_score" in p for p in phases)

    def test_design_scoring_logic(self, design_engine):
        """评分 >= 9 直接返回，不触发后续重试"""
        # MockLLM 默认打分 9.2，应该一次通过
        result = design_engine.design("一个简单工具", max_retries=3)
        assert result["score"] >= 9.0


# ═══════════════════════════════════════════════════════════
# ToolExecutor
# ═══════════════════════════════════════════════════════════

class TestToolExecutorParse:
    """工具调用解析测试"""

    def test_parse_simple(self, tool_executor):
        text = "先搜索[TOOL_CALL:web_search] query=Python [/TOOL_CALL]然后写文件"
        calls = tool_executor.parse(text)
        assert len(calls) == 1
        assert calls[0][0] == "web_search"
        assert calls[0][1]["query"] == "Python"

    def test_parse_multi(self, tool_executor):
        text = (
            "[TOOL_CALL:memory] action=add target=user content=hello [/TOOL_CALL]"
            "[TOOL_CALL:write_file] path=test.txt content=hi [/TOOL_CALL]"
        )
        calls = tool_executor.parse(text)
        assert len(calls) == 2
        assert calls[0][0] == "memory"
        assert calls[1][0] == "write_file"

    def test_parse_empty(self, tool_executor):
        calls = tool_executor.parse("普通文本，没有工具调用")
        assert len(calls) == 0

    def test_parse_malformed(self, tool_executor):
        calls = tool_executor.parse("[TOOL_CALL:test]未闭合")
        assert len(calls) == 0

    def test_parse_multi_line_params(self, tool_executor):
        text = (
            "[TOOL_CALL:web_search]\n"
            "query=Python testing\n"
            "max_results=5\n"
            "[/TOOL_CALL]"
        )
        calls = tool_executor.parse(text)
        assert len(calls) == 1
        assert calls[0][0] == "web_search"
        assert calls[0][1]["query"] == "Python testing"
        assert calls[0][1]["max_results"] == "5"


class TestToolExecutorExecute:
    """工具执行测试"""

    def test_write_file(self, tool_executor):
        with tempfile.TemporaryDirectory() as tmp:
            result = tool_executor.do_write_file(
                path=str(Path(tmp) / "test.txt"), content="hello world"
            )
            assert "✅" in result
            assert (Path(tmp) / "test.txt").read_text() == "hello world"

    def test_write_file_creates_parent_dirs(self, tool_executor):
        with tempfile.TemporaryDirectory() as tmp:
            result = tool_executor.do_write_file(
                path=str(Path(tmp) / "sub" / "deep" / "test.txt"),
                content="nested"
            )
            assert "✅" in result

    def test_list_files(self, tool_executor):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.txt").write_text("a")
            (Path(tmp) / "b.txt").write_text("b")
            result = tool_executor.do_list_files(path=tmp)
            assert "a.txt" in result
            assert "b.txt" in result

    def test_read_file_not_found(self, tool_executor):
        result = tool_executor.do_read_file(path="/nonexistent/file.txt")
        assert "不存在" in result or "❌" in result

    def test_unknown_tool(self, tool_executor):
        result = tool_executor.execute("nonexistent_tool", {})
        assert "未知工具" in result

    def test_execute_all_max_turns(self, tool_executor):
        text = (
            "[TOOL_CALL:write_file] path=/tmp/a.txt content=a [/TOOL_CALL]"
            "[TOOL_CALL:write_file] path=/tmp/b.txt content=b [/TOOL_CALL]"
            "[TOOL_CALL:write_file] path=/tmp/c.txt content=c [/TOOL_CALL]"
            "[TOOL_CALL:write_file] path=/tmp/d.txt content=d [/TOOL_CALL]"
        )
        results = tool_executor.execute_all(text, max_turns=2)
        assert len(results) <= 2


# ═══════════════════════════════════════════════════════════
# Datastore
# ═══════════════════════════════════════════════════════════

class TestDatastore:
    """统一存储测试"""

    def test_memory_set_get(self, memory_repo):
        memory_repo.set("test_key", "test_value")
        assert memory_repo.get("test_key") == "test_value"
        memory_repo.delete("test_key")
        assert memory_repo.get("test_key") == ""

    def test_memory_list(self, memory_repo):
        memory_repo.set("list_test_1", "v1", "test")
        memory_repo.set("list_test_2", "v2", "test")
        items = memory_repo.list("test")
        assert len(items) >= 2
        memory_repo.delete("list_test_1")
        memory_repo.delete("list_test_2")

    def test_memory_list_all(self, memory_repo):
        memory_repo.set("cat_a_1", "a1", "alpha")
        memory_repo.set("cat_b_1", "b1", "beta")
        all_items = memory_repo.list()
        cats = {i["category"] for i in all_items}
        assert "alpha" in cats
        assert "beta" in cats
        memory_repo.delete("cat_a_1")
        memory_repo.delete("cat_b_1")

    def test_memory_query(self, memory_repo):
        memory_repo.set("config_port", "8080", "config")
        results = memory_repo.query("8080")
        assert len(results) >= 1
        assert results[0]["key"] == "config_port"
        memory_repo.delete("config_port")

    def test_session_flow(self, session_repo):
        import uuid
        sid = session_repo.create(f"test_session_{uuid.uuid4().hex[:8]}")
        session_repo.save_message(sid, "user", "你好")
        session_repo.save_message(sid, "assistant", "你好！")
        msgs = session_repo.get_messages(sid)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_session_recent(self, session_repo):
        sid = session_repo.create("recent_test")
        session_repo.save_message(sid, "user", "msg1")
        recent = session_repo.list_recent(10)
        assert len(recent) >= 1

    def test_session_search(self, session_repo):
        sid = session_repo.create("search_test")
        session_repo.save_message(sid, "user", "unique_search_term_xyz")
        results = session_repo.search("unique_search_term_xyz")
        assert len(results) >= 1

    def test_project_decisions(self, project_repo):
        project_repo.add_decision("测试阶段", "测试决策内容", 8.5)
        decisions = project_repo.get_decisions()
        found = any(d["phase"] == "测试阶段" for d in decisions)
        assert found

    def test_project_query(self, project_repo):
        project_repo.add_decision("架构", "选择微服务架构", 9.0)
        results = project_repo.query("微服务")
        assert len(results) >= 1

    def test_lore_add_query(self, lore_repo):
        lore_repo.add("character", "张三", "勇敢的骑士", 1)
        lore_repo.add("location", "黑暗森林", "神秘莫测", 1)
        results = lore_repo.query("骑士")
        assert len(results) >= 1
        results2 = lore_repo.query("森林")
        assert len(results2) >= 1

    def test_lore_count(self, lore_repo):
        lore_repo.add("item", "魔剑", "传说之剑", 1)
        assert lore_repo.count() >= 1

    def test_datastore_is_singleton(self, isolated_datastore):
        """Datastore 应该返回同一个实例"""
        from dong_ai.datastore import Datastore
        ds2 = Datastore()
        assert isolated_datastore is ds2

    def test_datastore_close_resets(self):
        """close() 后 __new__ 应创建新实例"""
        from dong_ai.datastore import Datastore
        Datastore._instance = None
        ds1 = Datastore()
        ds1.close()
        ds2 = Datastore()
        assert ds1 is not ds2
        ds2.close()
        Datastore._instance = None


# ═══════════════════════════════════════════════════════════
# DisplayEngine
# ═══════════════════════════════════════════════════════════

class TestDisplayEngine:
    """显示引擎测试"""

    def test_render_markdown_code(self):
        from dong_ai.display import render_markdown
        result = render_markdown("```python\nprint('hi')\n```")
        assert "print" in result

    def test_render_markdown_bold(self):
        from dong_ai.display import render_markdown
        result = render_markdown("这是 **粗体** 文字")
        assert "粗体" in result

    def test_render_markdown_code_inline(self):
        from dong_ai.display import render_markdown
        result = render_markdown("使用 `os.path.join()` 方法")
        assert "os.path.join" in result

    def test_box_top_bottom(self):
        from dong_ai.display import box_top, box_bottom
        import io, sys
        captured = io.StringIO()
        old = sys.stdout
        sys.stdout = captured
        box_top("测试标题")
        box_bottom()
        sys.stdout = old
        output = captured.getvalue()
        assert "测试标题" in output

    def test_print_assistant_formats(self):
        from dong_ai.display import print_assistant
        import io, sys
        captured = io.StringIO()
        old = sys.stdout
        sys.stdout = captured
        print_assistant("这是普通行\n招募团队干活\n评分: 8.5")
        sys.stdout = old
        output = captured.getvalue()
        assert "普通行" in output
        assert "招募" in output


# ═══════════════════════════════════════════════════════════
# LLMClient
# ═══════════════════════════════════════════════════════════

class TestLLMClient:
    """LLM 客户端测试"""

    def test_mock_chat(self, mock_llm):
        resp = mock_llm.chat([{"role": "user", "content": "帮我设计"}])
        assert len(resp.text) > 0
        assert isinstance(resp.usage, dict)

    def test_mock_json(self, mock_llm):
        resp = mock_llm.chat_json([{"role": "user", "content": "输出规划"}])
        assert isinstance(resp, dict)
        assert "project_name" in resp

    def test_mock_custom_response(self, mock_llm):
        mock_llm.set_response("定制", "这是定制响应")
        resp = mock_llm.chat([{"role": "user", "content": "给我定制方案"}])
        assert "定制响应" in resp.text

    def test_mock_tracks_calls(self, mock_llm):
        mock_llm.chat([{"role": "user", "content": "你好"}])
        mock_llm.chat([{"role": "user", "content": "再见"}])
        assert len(mock_llm.calls) == 2

    def test_mock_usage_accumulates(self, mock_llm):
        mock_llm.chat([{"role": "user", "content": "a"}])
        mock_llm.chat([{"role": "user", "content": "b"}])
        usage = mock_llm.usage
        assert usage["total"] >= 60  # 30 per call


# ═══════════════════════════════════════════════════════════
# CEO
# ═══════════════════════════════════════════════════════════

class TestCEO:
    """CEO 协调器测试"""

    def test_ceo_imports(self):
        from dong_ai.ceo import CEO
        assert CEO is not None

    def test_ceo_init(self, temp_dir, mock_llm):
        from dong_ai.ceo import CEO
        ceo = CEO(project_dir=str(temp_dir / "project"), llm_client=mock_llm)
        assert ceo.llm is not None
        assert ceo.ds is not None

    def test_ceo_make_plan_returns_dict(self, temp_dir, mock_llm):
        from dong_ai.ceo import CEO
        ceo = CEO(project_dir=str(temp_dir / "project"), llm_client=mock_llm)
        plan = ceo._make_plan("一个简单的文件监控系统")
        assert isinstance(plan, dict)
        assert "modules" in plan

    def test_ceo_split_phases(self, temp_dir, mock_llm):
        from dong_ai.ceo import CEO
        ceo = CEO(project_dir=str(temp_dir / "project"), llm_client=mock_llm)
        plan = {"project_name": "测试", "modules": [
            {"id": "m1", "name": "A", "deps": []},
            {"id": "m2", "name": "B", "deps": ["m1"]},
            {"id": "m3", "name": "C", "deps": ["m1"]},
        ]}
        phases = ceo._split_phases(plan)
        assert len(phases) >= 2
        assert phases[0]["tasks"][0]["id"] == "m1"
        phase2_ids = [t["id"] for t in phases[1]["tasks"]]
        assert "m2" in phase2_ids
        assert "m3" in phase2_ids

    def test_ceo_split_chain_deps(self, temp_dir):
        from dong_ai.ceo import CEO
        ceo = CEO(project_dir=str(temp_dir / "project"))
        plan = {"project_name": "链", "modules": [
            {"id": "m1", "name": "A", "deps": []},
            {"id": "m2", "name": "B", "deps": ["m1"]},
            {"id": "m3", "name": "C", "deps": ["m2"]},
        ]}
        phases = ceo._split_phases(plan)
        assert len(phases) == 3

    def test_ceo_split_no_deps(self, temp_dir):
        """无依赖模块合并到同一阶段"""
        from dong_ai.ceo import CEO
        ceo = CEO(project_dir=str(temp_dir / "project"))
        plan = {"project_name": "平", "modules": [
            {"id": "m1", "name": "A", "deps": []},
            {"id": "m2", "name": "B", "deps": []},
        ]}
        phases = ceo._split_phases(plan)
        assert len(phases) == 1
        assert len(phases[0]["tasks"]) == 2
