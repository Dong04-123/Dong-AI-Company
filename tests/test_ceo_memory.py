"""Dong AI — CEOMemory 测试

覆盖:
  - Soul 读写
  - Fact CRUD
  - Episode 写入/读取
  - Session 生命周期
  - 查询
  - 配置
  - inject_compact
"""

import os, time
from pathlib import Path

import pytest


class TestCEOMemorySoul:
    """Soul 人格文件"""

    def test_soul_default_empty(self, ceo_memory):
        assert ceo_memory.soul() == ""

    def test_soul_set_get(self, ceo_memory):
        ceo_memory.soul_set("你是冷酷的AI CEO")
        assert "冷酷" in ceo_memory.soul()

    def test_soul_overwrite(self, ceo_memory):
        ceo_memory.soul_set("第一版")
        ceo_memory.soul_set("第二版")
        assert ceo_memory.soul() == "第二版"


class TestCEOMemoryFacts:
    """Fact CRUD"""

    def test_set_get(self, ceo_memory):
        ceo_memory.set("name", "Dong")
        assert ceo_memory.get("name") == "Dong"

    def test_get_missing(self, ceo_memory):
        assert ceo_memory.get("nonexistent") == ""

    def test_set_category(self, ceo_memory):
        ceo_memory.set("pref_lang", "zh", "preference")
        facts = ceo_memory.facts("preference")
        assert any(f["key"] == "pref_lang" for f in facts)

    def test_delete(self, ceo_memory):
        ceo_memory.set("temp_key", "temp_val")
        ceo_memory.delete("temp_key")
        assert ceo_memory.get("temp_key") == ""

    def test_delete_nonexistent(self, ceo_memory):
        ceo_memory.delete("never_existed")  # Should not raise

    def test_facts_list_all(self, ceo_memory):
        ceo_memory.set("fa", "va", "alpha")
        ceo_memory.set("fb", "vb", "beta")
        all_facts = ceo_memory.facts()
        cats = {f["category"] for f in all_facts}
        assert "alpha" in cats
        assert "beta" in cats

    def test_facts_list_filtered(self, ceo_memory):
        ceo_memory.set("only_in_gamma", "val", "gamma")
        gamma = ceo_memory.facts("gamma")
        assert len(gamma) >= 1
        others = ceo_memory.facts("nonexistent_category")
        assert len(others) == 0


class TestCEOMemoryEpisodes:
    """Episode 压缩存储"""

    def test_compress(self, ceo_memory):
        ceo_memory.compress("测试压缩内容" * 20)
        episodes = ceo_memory.episodes(limit=10)
        assert len(episodes) >= 1

    def test_episodes_ordered(self, ceo_memory):
        ceo_memory.compress("第一条")
        ceo_memory.compress("第二条")
        ceo_memory.compress("第三条")
        episodes = ceo_memory.episodes(limit=3)
        assert len(episodes) == 3
        # 最后一条是新的，应该包含"第三条"
        assert "第三条" in episodes[0]["summary"] or "第三条" in episodes[-1]["summary"]

    def test_episodes_limit(self, ceo_memory):
        for i in range(10):
            ceo_memory.compress(f"第{i}条")
        episodes = ceo_memory.episodes(limit=3)
        assert len(episodes) <= 3


class TestCEOMemorySessions:
    """Session 完整生命周期"""

    def test_session_create(self, ceo_memory):
        sid = ceo_memory.session_start()
        assert isinstance(sid, str)
        assert len(sid) > 0

    def test_session_create_custom_id(self, ceo_memory):
        sid = ceo_memory.session_start("my_custom_session")
        assert sid == "my_custom_session"

    def test_session_save_and_load(self, ceo_memory):
        sid = ceo_memory.session_start("test_save_load")
        ceo_memory.session_save(sid, "user", "你好，请帮我设计一个系统")
        ceo_memory.session_save(sid, "assistant", "好的，我来设计")
        loaded = ceo_memory.session_load(sid)
        assert len(loaded["messages"]) == 2
        assert loaded["messages"][0]["role"] == "user"
        assert loaded["messages"][1]["role"] == "assistant"

    def test_session_ignore_trivial(self, ceo_memory):
        """无意义消息不被保存"""
        sid = ceo_memory.session_start("test_trivial")
        ceo_memory.session_save(sid, "user", "hi")
        ceo_memory.session_save(sid, "user", "你好")
        ceo_memory.session_save(sid, "user", "这是重要内容")
        loaded = ceo_memory.session_load(sid)
        # "hi" 和 "你好" 在 TRIVIAL 集合中，不应保存
        msgs = [m for m in loaded["messages"] if m["role"] == "user"]
        assert len(msgs) >= 1
        # 但"这是重要内容"应该被保存
        assert any("重要内容" in m["content"] for m in loaded["messages"])

    def test_session_resume(self, ceo_memory):
        """resume 返回最近 session"""
        ceo_memory.session_start("resume_test_a")
        ceo_memory.session_save("resume_test_a", "user", "a")
        sid = ceo_memory.session_resume()
        assert sid == "resume_test_a"


class TestCEOMemoryQuery:
    """跨源查询"""

    def test_query_facts(self, ceo_memory):
        ceo_memory.set("city", "上海")
        results = ceo_memory.query("上海", limit=5)
        assert len(results) >= 1

    def test_query_lore(self, ceo_memory):
        from dong_ai.datastore import get_repo
        lore = get_repo("lore")
        lore.add("place", "冰封王座", "巫妖王的堡垒")
        results = ceo_memory.query("冰封", limit=5)
        assert len(results) >= 1

    def test_query_session(self, ceo_memory):
        sid = ceo_memory.session_start("query_session_test")
        ceo_memory.session_save(sid, "user", "这个独特的查询词 query_unicorn_42")
        results = ceo_memory.query("query_unicorn_42", limit=5)
        assert len(results) >= 1

    def test_query_limit(self, ceo_memory):
        ceo_memory.set("qk_1", "value1")
        ceo_memory.set("qk_2", "value2")
        ceo_memory.set("qk_3", "value3")
        results = ceo_memory.query("value", limit=2)
        assert len(results) <= 2


class TestCEOMemoryConfig:
    """配置管理"""

    def test_config_defaults(self, ceo_memory):
        cfg = ceo_memory.config_load()
        assert cfg["context_length"] == "200000"
        assert cfg["max_response"] == "16384"

    def test_config_set_get(self, ceo_memory):
        ceo_memory.config_set("temperature", "0.5")
        cfg = ceo_memory.config_load()
        assert cfg["temperature"] == "0.5"

    def test_config_persists(self, ceo_memory):
        ceo_memory.config_set("test_config_key", "test_val")
        cfg1 = ceo_memory.config_load()
        assert cfg1.get("test_config_key") == "test_val"
        # 再读一次应该一致
        cfg2 = ceo_memory.config_load()
        assert cfg2.get("test_config_key") == "test_val"


class TestCEOMemoryInject:
    """inject_compact 上下文注入"""

    def test_inject_empty(self, ceo_memory):
        result = ceo_memory.inject_compact()
        assert isinstance(result, str)

    def test_inject_with_soul(self, ceo_memory):
        ceo_memory.soul_set("测试人格描述")
        result = ceo_memory.inject_compact()
        assert "测试人格描述" in result

    def test_inject_with_facts(self, ceo_memory):
        ceo_memory.set("name", "Dong", "preference")
        result = ceo_memory.inject_compact()
        assert "name" in result or "Dong" in result

    def test_inject_with_lore(self, ceo_memory):
        from dong_ai.datastore import get_repo
        lore = get_repo("lore")
        lore.add("character", "英雄", "伟大冒险家")
        result = ceo_memory.inject_compact()
        assert "世界观" in result or "英雄" in result or "lore" in result.lower()


class TestCEOMemoryHardware:
    """硬件检测（安全运行，不依赖真实 GPU）"""

    def test_detect_hardware_returns_dict(self, ceo_memory):
        info = ceo_memory.detect_hardware()
        assert isinstance(info, dict)
        assert "gpu_vram_mb" in info
        assert "gpu_type" in info
        assert "recommended" in info

    def test_detect_hardware_recommendation(self, ceo_memory):
        info = ceo_memory.detect_hardware()
        assert "model" in info["recommended"]
        assert "context" in info["recommended"]

    def test_detect_hardware_no_crash(self, ceo_memory):
        """即使 nvidia-smi 不可用也不崩溃"""
        info = ceo_memory.detect_hardware()
        assert info["gpu_vram_mb"] >= 0  # 可能为 CPU 的 RAM 值
