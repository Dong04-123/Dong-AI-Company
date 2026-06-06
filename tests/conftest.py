"""Dong AI — 共享测试基础设施

提供所有测试模块可重用的 fixtures。
所有模块引用均通过 dong_ai 包。
"""

import json, os, sys, tempfile, time
from pathlib import Path

import pytest

from dong_ai.datastore import Datastore, get_repo


# ═══════════════════════════════════════════════════════════
# Mock LLM
# ═══════════════════════════════════════════════════════════

class MockResponse:
    def __init__(self, text: str, usage: dict = None):
        self.text = text
        self.usage = usage or {"prompt": 10, "completion": 20, "total": 30}

    def json(self):
        try:
            return json.loads(self.text)
        except json.JSONDecodeError:
            return {"error": "not json"}


class MockLLM:
    """关键词驱动的 LLM 模拟器。"""

    DEFAULTS = {
        "风险": "风险1: 技术选型错误 → 前期充分调研\n风险2: 需求变更 → 敏捷迭代",
        "设计": "## 架构设计方案\n采用微服务架构，模块划分如下...",
        "审查": "问题1: 耦合度过高\n建议: 拆分接口",
        "打分": "总分: 9.2",
        "规划": '{"project_name": "测试项目", "modules": [{"id": "m1", "name": "模块1", "deps": []}]}',
        "生成员工": '[{"id":"coder","name":"代码匠","role":"写代码","mission":"实现功能","budget":65536,"tools":["web_search"],"rules":["写完整代码"],"output_format":"Python文件"}]',
        "兼容": "兼容",
        "不兼容": "不兼容",
        "默认": "这是一个测试响应。",
    }

    def __init__(self):
        self.responses = dict(self.DEFAULTS)
        self.calls = []
        self._usage_total = {"prompt": 0, "completion": 0, "total": 0}

    def chat(self, messages, system="", **kwargs):
        self.calls.append((messages, system, kwargs))
        content = messages[-1]["content"] if messages else ""
        resp = self.responses.get("默认", "默认响应")
        best_pos = float("inf")
        for key, val in self.responses.items():
            if key == "默认":
                continue
            lower_content = content.lower()
            lower_key = key.lower()
            idx = lower_content.find(lower_key)
            if idx != -1 and idx < best_pos:
                best_pos = idx
                resp = val
        u = {"prompt": 10, "completion": 20, "total": 30}
        for k in u: self._usage_total[k] += u[k]
        return MockResponse(resp, u)

    def chat_json(self, messages, system="", **kwargs):
        return json.loads(self.chat(messages, system, **kwargs).text)

    @property
    def usage(self):
        return dict(self._usage_total)

    def set_response(self, keyword: str, text: str):
        self.responses[keyword] = text


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def mock_llm():
    return MockLLM()


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory(prefix="dong_test_") as tmp:
        original_home = os.environ.get("HOME", "")
        os.environ["HOME"] = tmp
        yield Path(tmp)
        os.environ["HOME"] = original_home


@pytest.fixture
def isolated_datastore(temp_dir):
    Datastore._instance = None
    ds = Datastore()
    yield ds
    ds.close()
    Datastore._instance = None


@pytest.fixture
def memory_repo(isolated_datastore):
    import dong_ai.datastore as ds_mod
    old_cache = ds_mod._repo_cache.copy()
    ds_mod._repo_cache.clear()
    yield get_repo("memory")
    ds_mod._repo_cache.update(old_cache)


@pytest.fixture
def session_repo(isolated_datastore):
    import dong_ai.datastore as ds_mod
    old_cache = ds_mod._repo_cache.copy()
    ds_mod._repo_cache.clear()
    yield get_repo("session")
    ds_mod._repo_cache.update(old_cache)


@pytest.fixture
def project_repo(isolated_datastore):
    import dong_ai.datastore as ds_mod
    old_cache = ds_mod._repo_cache.copy()
    ds_mod._repo_cache.clear()
    yield get_repo("project")
    ds_mod._repo_cache.update(old_cache)


@pytest.fixture
def lore_repo(isolated_datastore):
    import dong_ai.datastore as ds_mod
    old_cache = ds_mod._repo_cache.copy()
    ds_mod._repo_cache.clear()
    yield get_repo("lore")
    ds_mod._repo_cache.update(old_cache)


@pytest.fixture
def design_engine(mock_llm, project_repo):
    from dong_ai.design_engine import DesignEngine
    return DesignEngine(mock_llm, project_repo)


@pytest.fixture
def tool_executor():
    from dong_ai.tool_executor import ToolExecutor
    return ToolExecutor()


@pytest.fixture
def ceo_memory(temp_dir):
    from dong_ai.ceo_memory import CEOMemory
    return CEOMemory()


@pytest.fixture
def mock_urlopen(monkeypatch):
    import urllib.request
    from io import BytesIO

    class MockHTTPResponse:
        def __init__(self, json_data: str, status: int = 200):
            self._data = json_data.encode("utf-8")
            self.status = status

        def read(self):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class MockURLopener:
        def __init__(self):
            self.default_response = '{"choices":[{"message":{"content":"mock response"}}]}'
            self.responses = {}

        def __call__(self, req, **kwargs):
            url = getattr(req, "full_url", str(req))
            matched = self.default_response
            matched_len = -1
            for prefix, resp in self.responses.items():
                if prefix in url and len(prefix) > matched_len:
                    matched = resp
                    matched_len = len(prefix)
            return MockHTTPResponse(matched)

        def set_response(self, json_str: str, url_prefix: str = ""):
            if url_prefix:
                self.responses[url_prefix] = json_str
            else:
                self.default_response = json_str

    opener = MockURLopener()
    monkeypatch.setattr(urllib.request, "urlopen", opener)
    return opener
