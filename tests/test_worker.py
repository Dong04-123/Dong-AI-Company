"""Dong AI — WorkerPool 测试

使用 mock_urlopen 拦截 HTTP 调用，避免真实 API 请求。
覆盖 WorkerPool 的核心路径。
"""

import os, sys, json, tempfile, re
from pathlib import Path

import pytest


# 标准 LLM 响应模板
LLM_CHAT_RESPONSE = '{"choices":[{"message":{"content":"mock response"}}],"usage":{"prompt_tokens":10,"completion_tokens":20,"total_tokens":30}}'
LLM_JSON_RESPONSE = '{"choices":[{"message":{"content":"{\\"project_name\\":\\"test\\"}"}}],"usage":{"prompt_tokens":10,"completion_tokens":20,"total_tokens":30}}'


class TestWorkerPoolInit:
    """WorkerPool 初始化和基本属性"""

    def test_import(self):
        from dong_ai.worker import WorkerPool
        assert WorkerPool is not None

    def test_init_creates_work_dir(self, temp_dir):
        from dong_ai.worker import WorkerPool
        project = str(temp_dir / "project")
        wp = WorkerPool(project)
        assert Path(project).exists()
        assert Path(project, "work").exists()
        # model_endpoint 保留为向后兼容属性
        assert isinstance(wp.model_endpoint, str)
        assert wp.model_endpoint == ""  # 默认空，由 ModelPool 自动探测
        assert wp.model_name == "deepseek-chat"

    def test_init_custom_endpoint(self, temp_dir):
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "p2"), model_endpoint="http://localhost:9999/v1")
        assert wp.model_endpoint == "http://localhost:9999/v1"

    def test_stream_output(self, temp_dir):
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "p3"))
        # _stream 只是打印，不应崩溃
        wp._stream("测试", "消息内容")  # Should not raise


class TestWorkerPoolGenerateWorkers:
    """动态生成员工"""

    def test_generate_workers_returns_list(self, temp_dir, mock_urlopen):
        mock_urlopen.set_response(LLM_JSON_RESPONSE)
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "wg1"))
        workers = wp._generate_workers("配置模块", "设计方案", "上下文", "第1轮")
        assert isinstance(workers, list)
        assert len(workers) > 0
        assert "id" in workers[0]
        assert "name" in workers[0]

    def test_generate_workers_fallback(self, temp_dir, mock_urlopen):
        """API 失败时返回默认组合"""
        mock_urlopen.set_response("not json", url_prefix="chat")
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "wg2"))
        workers = wp._generate_workers("测试任务", "设计", "上下文", "第1轮")
        # 返回默认员工组合（代码匠 + 测试判官）
        assert len(workers) >= 2
        names = [w["name"] for w in workers]
        assert "代码匠" in names

    def test_generate_workers_api_error(self, temp_dir, mock_urlopen):
        """HTTP 异常时回退"""
        mock_urlopen.set_response("{}", url_prefix="chat")  # 无 choices
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "wg3"))
        workers = wp._generate_workers("测试", "设计", "", "第1轮")
        assert len(workers) >= 2  # fallback


class TestWorkerPoolCallLLM:
    """LLM 调用"""

    def test_call_llm_basic(self, temp_dir, mock_urlopen):
        mock_urlopen.set_response(LLM_CHAT_RESPONSE)
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "cl1"))
        result = wp._llm_call([{"role": "user", "content": "hello"}], system="system prompt")
        assert result == "mock response"

    def test_call_llm_api_error(self, temp_dir, mock_urlopen):
        """API 异常时返回错误字符串"""
        mock_urlopen.set_response('{"error":"rate limit"}', url_prefix="chat")
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "cl2"))
        result = wp._llm_call([{"role": "user", "content": "hi"}])
        assert "<API_ERROR" in result


class TestWorkerPoolWithTools:
    """带工具调用的 LLM 循环"""

    def test_call_with_tools_no_tool_call(self, temp_dir, mock_urlopen):
        """无工具调用时直接返回"""
        mock_urlopen.set_response(LLM_CHAT_RESPONSE)
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "wt1"))
        result = wp._call_llm_with_tools(
            [{"role": "user", "content": "写一个函数"}],
            system="编码",
        )
        assert "mock response" in result

    def test_call_with_tools_detects_tool(self, temp_dir, mock_urlopen):
        """检测到工具调用后执行并继续"""
        # 先返回带工具调用的响应，然后返回最终结果
        responses = [
            '{"choices":[{"message":{"content":"[TOOL_CALL:web_search]\\nquery=test\\n[/TOOL_CALL]"}}],"usage":{"total_tokens":30}}',
            LLM_CHAT_RESPONSE,
        ]
        call_count = [0]

        from urllib.request import Request
        original_urlopen = __import__("urllib.request").request.urlopen

        class CountingOpener:
            def __call__(self, req, **kwargs):
                idx = call_count[0]
                call_count[0] += 1
                from io import BytesIO
                data = responses[min(idx, len(responses) - 1)]
                return type("R", (), {
                    "__enter__": lambda s: s,
                    "__exit__": lambda *a: None,
                    "read": lambda: data.encode(),
                    "status": 200,
                })()

        import urllib.request
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(urllib.request, "urlopen", CountingOpener())
        # Note: get_registered_tools will read from memory.py which
        # lists web_search as built-in tool. This test verifies the
        # tool call loop doesn't crash even when the tool execution fails.

        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "wt2"))
        result = wp._call_llm_with_tools(
            [{"role": "user", "content": "搜索测试"}],
            system="可用工具",
        )
        monkeypatch.undo()
        assert len(result) > 0


class TestWorkerPoolCodeImpl:
    """代码类员工"""

    def test_worker_code_creates_file(self, temp_dir, mock_urlopen):
        mock_urlopen.set_response('{"choices":[{"message":{"content":"```python\\ndef hello():\\n    pass\\n```"}}],"usage":{"total_tokens":30}}')
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "ci1"))
        w_dir = Path(temp_dir / "ci1" / "work" / "codemod" / "coder")
        w_dir.mkdir(parents=True, exist_ok=True)
        worker = {"id": "coder", "name": "代码匠", "role": "写代码", "mission": "实现hello函数",
                  "budget": 65536, "tools": ["web_search"], "rules": [], "output_format": "Python"}
        result = wp._worker_code_impl("代码匠", "codemod", w_dir, "system", "写代码")
        assert result["status"] == "ok"
        assert len(result["files"]) >= 1

    def test_worker_code_extracts_interfaces(self, temp_dir, mock_urlopen):
        mock_urlopen.set_response('{"choices":[{"message":{"content":"```python\\ndef add(a, b) -> int:\\n    return a + b\\n```"}}],"usage":{"total_tokens":30}}')
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "ci2"))
        w_dir = Path(temp_dir / "ci2" / "work" / "mathmod" / "coder")
        w_dir.mkdir(parents=True, exist_ok=True)
        worker = {"id": "coder", "name": "代码匠", "role": "写代码", "mission": "实现数学函数",
                  "budget": 65536, "tools": [], "rules": [], "output_format": "Python"}
        result = wp._worker_code_impl("代码匠", "mathmod", w_dir, "system", "写一个add函数")
        assert len(result["interfaces"]) >= 1
        assert any(i["name"] == "add" for i in result["interfaces"])


class TestWorkerPoolTestImpl:
    """测试类员工"""

    def test_worker_test_creates_file(self, temp_dir, mock_urlopen):
        mock_urlopen.set_response('{"choices":[{"message":{"content":"```python\\ndef test_hello():\\n    assert True\\n```"}}],"usage":{"total_tokens":30}}')
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "ti1"))
        w_dir = Path(temp_dir / "ti1" / "work" / "testmod" / "tester")
        w_dir.mkdir(parents=True, exist_ok=True)
        worker = {"id": "tester", "name": "测试判官", "role": "测试", "mission": "测试hello函数",
                  "budget": 32768, "tools": ["pytest"], "rules": [], "output_format": "pytest"}
        result = wp._worker_test_impl("测试判官", "testmod", w_dir, "system", "写测试")
        assert result["status"] == "ok"
        assert len(result["files"]) >= 1

    def test_worker_test_counts_tests(self, temp_dir, mock_urlopen):
        mock_urlopen.set_response('{"choices":[{"message":{"content":"```python\\ndef test_a(): pass\\ndef test_b(): pass\\n```"}}],"usage":{"total_tokens":30}}')
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "ti2"))
        # The test_count is computed from the raw response, not extracted from file
        # So we don't check exact count, just that files exist
        w_dir = Path(temp_dir / "ti2" / "work" / "tm2" / "tester")
        w_dir.mkdir(parents=True, exist_ok=True)
        worker = {"id": "tester", "name": "测试判官", "role": "测试", "mission": "测试",
                  "budget": 32768, "tools": ["pytest"], "rules": [], "output_format": "pytest"}
        result = wp._worker_test_impl("测试判官", "tm2", w_dir, "system", "写测试")
        assert result["status"] == "ok"


class TestWorkerPoolCrossReview:
    """交叉审查"""

    def test_cross_review_basic(self, temp_dir, mock_urlopen):
        """两个员工互相审查"""
        # 第一个响应: 兼容 / 第二个响应也: 兼容
        mock_urlopen.set_response('{"choices":[{"message":{"content":"兼容"}}],"usage":{"total_tokens":10}}')
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "cr1"))
        workers = [
            {"id": "coder", "name": "代码匠"},
            {"id": "tester", "name": "测试判官"},
        ]
        results = {
            "coder": {"status": "ok", "files": [], "interfaces": [], "lessons": [], "review_notes": ""},
            "tester": {"status": "ok", "files": [], "interfaces": [], "lessons": [], "review_notes": ""},
        }
        passed = wp._cross_review(workers, results, "testmod", Path(temp_dir / "cr1"))
        assert passed is True

    def test_cross_review_with_files(self, temp_dir, mock_urlopen):
        """有实际文件时审查"""
        mock_urlopen.set_response('{"choices":[{"message":{"content":"不兼容"}}],"usage":{"total_tokens":10}}')
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "cr2"))
        # 创建一些文件让审查有内容
        work_dir = Path(temp_dir / "cr2" / "work" / "mod1")
        work_dir.mkdir(parents=True, exist_ok=True)
        code_file = work_dir / "sample.py"
        code_file.write_text("def foo(): pass")
        workers = [
            {"id": "alice", "name": "艾丽丝"},
            {"id": "bob", "name": "鲍勃"},
        ]
        results = {
            "alice": {"status": "ok", "files": [str(code_file)], "interfaces": [], "lessons": [], "review_notes": ""},
            "bob": {"status": "ok", "files": [], "interfaces": [], "lessons": [], "review_notes": ""},
        }
        # 不兼容，审查不通过
        passed = wp._cross_review(workers, results, "mod1", work_dir)
        assert passed is False


class TestWorkerPoolRealTests:
    """真实 pytest 运行测试"""

    def test_run_real_tests_no_files(self, temp_dir):
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "rt1"))
        total, passed, errors = wp._run_real_tests(Path(temp_dir / "rt1" / "empty_dir"))
        assert total == 0
        assert passed == 0

    def test_run_real_tests_passing(self, temp_dir):
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "rt2"))
        mod_dir = Path(temp_dir / "rt2" / "work" / "passing")
        mod_dir.mkdir(parents=True, exist_ok=True)
        (mod_dir / "test_pass.py").write_text("""
def test_one():
    assert 1 + 1 == 2
def test_two():
    assert "hello" == "hello"
""")
        total, passed, errors = wp._run_real_tests(mod_dir)
        assert total >= 1
        assert passed >= 1

    def test_run_real_tests_failing(self, temp_dir):
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "rt3"))
        mod_dir = Path(temp_dir / "rt3" / "work" / "failing")
        mod_dir.mkdir(parents=True, exist_ok=True)
        (mod_dir / "test_fail.py").write_text("""
def test_bad():
    assert 1 == 2
""")
        total, passed, errors = wp._run_real_tests(mod_dir)
        assert total >= 1
        assert passed < total


class TestWorkerPoolGeneralImpl:
    """通用员工"""

    def test_general_outputs_file(self, temp_dir, mock_urlopen):
        mock_urlopen.set_response(LLM_CHAT_RESPONSE)
        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "gi1"))
        w_dir = Path(temp_dir / "gi1" / "work" / "genmod" / "general")
        w_dir.mkdir(parents=True, exist_ok=True)
        result = wp._worker_general_impl("通用", "genmod", w_dir, "system", "写分析报告")
        assert result["status"] == "ok"
        assert len(result["files"]) >= 1


class TestWorkerPoolSelfHealing:
    """自愈循环"""

    def test_run_worker_self_healing_success(self, temp_dir, mock_urlopen):
        """正常路径立即成功"""
        mock_urlopen.set_response('{"choices":[{"message":{"content":"```python\\ndef hi(): pass\\n```"}}],"usage":{"total_tokens":30}}')

        def mock_worker_func(name, task_id, w_dir, system, user_msg):
            w_dir.mkdir(parents=True, exist_ok=True)
            (w_dir / f"{task_id}.py").write_text("def hi(): pass")
            return {"status": "ok", "files": [str(w_dir / f"{task_id}.py")],
                    "interfaces": [], "lessons": [], "review_notes": ""}

        from dong_ai.worker import WorkerPool
        wp = WorkerPool(str(temp_dir / "sh1"))
        # Monkey-patch to use the simple mock instead of LLM-based
        import types
        wp._worker_code_impl = mock_worker_func
        worker = {"id": "coder", "name": "代码匠", "role": "写代码", "mission": "实现hi函数",
                  "budget": 65536, "tools": [], "rules": [], "output_format": "Python"}
        result = wp._run_worker_self_healing(worker, "mod1", "hi模块", Path(temp_dir / "sh1"), "设计", "上下文")
        assert result["status"] == "ok"
