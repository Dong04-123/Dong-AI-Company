#!/usr/bin/env python3
"""
Example 1: Quick CEO project execution with mock LLM.

Shows the simplest way to use Dong AI Company — feed a request,
get a governance pipeline (red/blue debate → workers → board review).

Run:
  python3 examples/01_quick_project.py
"""

# Use mock LLM so this runs without any API keys
from dong_ai.llm import LLMConfig, create_client
from dong_ai.design_engine import DesignEngine
from dong_ai.datastore import get_repo


class MockLLM:
    """Simple mock that returns canned responses"""
    def chat(self, messages, system="", **kwargs):
        from types import SimpleNamespace
        text = messages[-1]["content"] if messages else ""
        if "分类" in text or "类型" in text:
            resp = "software"
        elif "规划" in text or "阶段" in text or "JSON" in text:
            resp = '[{"name":"设计","tasks":[{"id":"t1","name":"架构设计","deps":[]}]},{"name":"编码","tasks":[{"id":"t2","name":"实现功能","deps":["t1"]}]}]'
        elif "设计" in text:
            resp = '{"score":8.5,"design":"## 架构\\n采用模块化设计","project_name":"Demo Project","requirements":[{"id":"R1","desc":"核心功能","verify":"test_core"}]}'
        elif "评分" in text or "打分" in text:
            resp = "总分: 8.5"
        else:
            resp = "完成用户需求。评分: 8.0"
        return SimpleNamespace(text=resp, usage={"total": 30}, json=lambda: __import__("json").loads(resp))

    def chat_json(self, messages, system="", **kwargs):
        import json
        resp = self.chat(messages, system, **kwargs)
        return json.loads(resp.text)


def main():
    print("╭─ Dong AI Company — Quick Demo ─────────────────╮")
    print("┊")

    # Create mock components
    llm = MockLLM()
    ds = get_repo("project")
    design_engine = DesignEngine(llm, ds)

    # CEO with injected mock
    from dong_ai.ceo import CEO
    ceo = CEO(project_dir="/tmp/dong_demo", design_engine=design_engine, llm_client=llm)

    print("┊  🔄 Running project: Build a CLI todo app...")
    ceo.run("Build a CLI todo app with add/list/delete commands")

    print("┊")
    print("┊  📄 Report:", ceo.report_path)
    print("╰──────────────────────────────────────────────────╯")
    print()
    print(ceo.report_path.read_text()[:1000] if ceo.report_path.exists() else "(report not found)")


if __name__ == "__main__":
    main()
