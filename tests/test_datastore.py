"""Test: Datastore + GraphRepository + Repos

Tests the unified persistence layer:
  - Datastore singleton, init, close
  - GraphRepository (add_node, add_dep, traverse, merge, etc.)
  - SessionRepo (save, load, list, delete)
  - MemoryRepo (set, get, query, delete)
  - LoreRepo (set, get, search)
  - ConfigRepo (load, save via CEOMemory)
"""

import json
import pytest
from datetime import datetime, timezone
from dong_ai.datastore import Datastore, get_repo


# ═══════════════════════════════════════════════════════════════
# Datastore — lifecycle
# ═══════════════════════════════════════════════════════════════

class TestDatastoreLifecycle:
    """Datastore singleton and close."""

    def test_singleton_returns_same_instance(self, isolated_datastore):
        ds1 = Datastore()
        ds2 = Datastore()
        assert ds1 is ds2
        assert ds1.conn is ds2.conn

    def test_singleton_reset_creates_new(self, isolated_datastore):
        ds1 = Datastore()
        Datastore._instance = None
        ds2 = Datastore()
        assert ds1 is not ds2

    def test_init_creates_directory_and_tables(self, isolated_datastore):
        ds = isolated_datastore
        tables = ds.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [r[0] for r in tables]
        for required in ("facts", "sessions", "messages", "decisions",
                         "modules", "lore", "codegraph", "code_deps", "logs"):
            assert required in names, f"Table {required} missing"

    def test_close_clears_instance(self, isolated_datastore):
        ds = isolated_datastore
        ds.close()
        assert Datastore._instance is None

    def test_close_allows_connection_cleanup(self, isolated_datastore):
        ds = isolated_datastore
        conn = ds.conn
        conn.execute("SELECT 1")  # verify alive
        ds.close()
        assert Datastore._instance is None


# ═══════════════════════════════════════════════════════════════
# MemoryRepository
# ═══════════════════════════════════════════════════════════════

class TestMemoryRepo:
    """MemoryRepository: set/get/query/delete/list."""

    def test_set_and_get(self, memory_repo):
        memory_repo.set("test_key", "hello world")
        assert memory_repo.get("test_key") == "hello world"

    def test_get_missing_returns_empty(self, memory_repo):
        assert memory_repo.get("nonexistent") == ""

    def test_set_overwrites(self, memory_repo):
        memory_repo.set("key", "first", category="fact")
        memory_repo.set("key", "second", category="preference")
        assert memory_repo.get("key") == "second"

    def test_delete_removes_key(self, memory_repo):
        memory_repo.set("tmp", "to_delete")
        memory_repo.delete("tmp")
        assert memory_repo.get("tmp") == ""

    def test_delete_nonexistent_does_not_raise(self, memory_repo):
        memory_repo.delete("no_key")  # should not raise

    def test_list_returns_all(self, memory_repo):
        memory_repo.set("a", "1", category="fact")
        memory_repo.set("b", "2", category="preference")
        items = memory_repo.list()
        keys = {i["key"] for i in items}
        assert "a" in keys
        assert "b" in keys

    def test_list_filters_by_category(self, memory_repo):
        memory_repo.set("fact1", "v1", category="fact")
        memory_repo.set("pref1", "v2", category="preference")
        facts = memory_repo.list(category="fact")
        assert len(facts) == 1
        assert facts[0]["key"] == "fact1"

    def test_query_finds_kv(self, memory_repo):
        memory_repo.set("user_name", "Alice")
        results = memory_repo.query("Alice")
        assert len(results) >= 1
        assert results[0]["key"] == "user_name"

    def test_query_returns_empty_for_no_match(self, memory_repo):
        results = memory_repo.query("zzz_nonexistent_zzz")
        assert results == []

    def test_set_with_custom_category_and_source(self, memory_repo):
        memory_repo.set("ck", "cv", category="custom_cat", source="test")
        items = memory_repo.list(category="custom_cat")
        assert len(items) == 1
        assert items[0]["source"] == "test"


# ═══════════════════════════════════════════════════════════════
# SessionRepository
# ═══════════════════════════════════════════════════════════════

class TestSessionRepo:
    """SessionRepository: create, save, load, list, delete."""

    def test_create_returns_sid(self, session_repo):
        sid = session_repo.create("my_session")
        assert sid == "my_session"

    def test_create_generates_sid_when_none(self, session_repo):
        sid = session_repo.create()
        assert sid.startswith("s")

    def test_save_and_get_messages(self, session_repo):
        sid = session_repo.create("test_sid")
        session_repo.save_message(sid, "user", "hello")
        session_repo.save_message(sid, "assistant", "hi there")
        msgs = session_repo.get_messages(sid)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "hello"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "hi there"

    def test_get_messages_empty_session(self, session_repo):
        sid = session_repo.create("empty_sid")
        msgs = session_repo.get_messages(sid)
        assert msgs == []

    def test_list_recent_returns_sessions(self, session_repo):
        session_repo.create("s1")
        session_repo.create("s2")
        sessions = session_repo.list_recent(limit=10)
        assert len(sessions) >= 2
        ids = {s["id"] for s in sessions}
        assert "s1" in ids
        assert "s2" in ids

    def test_list_recent_respects_limit(self, session_repo):
        for i in range(5):
            session_repo.create(f"s{i}")
        sessions = session_repo.list_recent(limit=3)
        assert len(sessions) <= 3

    def test_search_finds_messages(self, session_repo):
        sid = session_repo.create("search_sid")
        session_repo.save_message(sid, "user", "I love Python programming")
        results = session_repo.search("Python")
        assert len(results) >= 1
        assert "Python" in results[0]["content"]

    def test_search_empty_no_match(self, session_repo):
        sid = session_repo.create("empty_search")
        session_repo.save_message(sid, "user", "hello")
        results = session_repo.search("nonexistent")
        assert results == []

    def test_save_message_truncates_long_content(self, session_repo):
        sid = session_repo.create("trunc_sid")
        long = "x" * 5000
        session_repo.save_message(sid, "user", long)
        msgs = session_repo.get_messages(sid)
        assert len(msgs[0]["content"]) <= 2000

    def test_create_ignores_duplicate(self, session_repo):
        sid = session_repo.create("dup")
        # second create with same id should not raise
        session_repo.create("dup")
        sessions = session_repo.list_recent()
        dup_count = sum(1 for s in sessions if s["id"] == "dup")
        assert dup_count == 1


# ═══════════════════════════════════════════════════════════════
# LoreRepository
# ═══════════════════════════════════════════════════════════════

class TestLoreRepo:
    """LoreRepository: add, query, count."""

    def test_add_and_query(self, lore_repo):
        lore_repo.add("character", "Alice", "A brave adventurer", chapter=1)
        results = lore_repo.query("Alice")
        assert len(results) >= 1
        assert results[0]["key"] == "Alice"

    def test_add_multiple_categories(self, lore_repo):
        lore_repo.add("location", "Forest", "Dark and mysterious", chapter=1)
        lore_repo.add("chapter", "Chapter 1", "The beginning", chapter=1)
        results = lore_repo.query("Forest")
        assert len(results) == 1
        assert results[0]["category"] == "location"

    def test_query_by_description(self, lore_repo):
        lore_repo.add("item", "Sword of Truth", "A legendary blade", chapter=2)
        results = lore_repo.query("legendary")
        assert len(results) >= 1
        assert results[0]["key"] == "Sword of Truth"

    def test_query_no_match(self, lore_repo):
        results = lore_repo.query("zzz_nonexistent")
        assert results == []

    def test_count_starts_zero(self, lore_repo):
        assert lore_repo.count() == 0

    def test_count_after_adds(self, lore_repo):
        lore_repo.add("character", "Bob", "Bob the builder")
        lore_repo.add("character", "Eve", "Eve the explorer")
        assert lore_repo.count() == 2

    def test_add_without_chapter_defaults_zero(self, lore_repo):
        lore_repo.add("character", "Default", "No chapter")
        results = lore_repo.query("Default")
        assert results[0]["value"] == "No chapter"

    def test_add_and_query_returns_source_field(self, lore_repo):
        lore_repo.add("character", "Test", "Testing")
        results = lore_repo.query("Test")
        assert results[0]["source"] == "lore"


# ═══════════════════════════════════════════════════════════════
# ProjectRepository / GraphRepository
# ═══════════════════════════════════════════════════════════════

class TestProjectRepo:
    """ProjectRepository: decisions, query."""

    def test_add_and_get_decisions(self, project_repo):
        project_repo.add_decision("design", "Use microservices", score=8.5)
        decisions = project_repo.get_decisions()
        assert len(decisions) >= 1
        assert decisions[0]["phase"] == "design"
        assert decisions[0]["score"] == 8.5

    def test_get_decisions_empty_when_none(self, project_repo):
        assert project_repo.get_decisions() == []

    def test_get_decisions_respects_limit(self, project_repo):
        for i in range(5):
            project_repo.add_decision("phase", f"decision {i}", score=i)
        decisions = project_repo.get_decisions(limit=3)
        assert len(decisions) <= 3

    def test_query_decisions(self, project_repo):
        project_repo.add_decision("design", "Important decision about architecture")
        results = project_repo.query("architecture")
        assert len(results) >= 1
        assert results[0]["source"] == "decisions"

    def test_query_no_match(self, project_repo):
        results = project_repo.query("zzz_nonexistent")
        assert results == []


class TestGraphRepo:
    """GraphRepository: nodes, deps, traverse, merge, format."""

    def test_add_node_and_get_project_nodes(self, project_repo, isolated_datastore):
        gr = get_repo("graph")
        gr.add_node("proj1", "function", "main",
                     file_path="src/main.py", line_number=10,
                     signature="main()", detail="entry point")
        nodes = gr.get_project_nodes("proj1")
        assert len(nodes) == 1
        assert nodes[0]["node_name"] == "main"
        assert nodes[0]["node_type"] == "function"

    def test_get_project_nodes_filters_by_type(self, project_repo, isolated_datastore):
        gr = get_repo("graph")
        gr.add_node("proj2", "function", "foo")
        gr.add_node("proj2", "class", "Bar")
        funcs = gr.get_project_nodes("proj2", node_type="function")
        assert len(funcs) == 1
        assert funcs[0]["node_type"] == "function"
        classes = gr.get_project_nodes("proj2", node_type="class")
        assert len(classes) == 1

    def test_add_dep_and_get_deps(self, project_repo, isolated_datastore):
        gr = get_repo("graph")
        gr.add_node("proj3", "function", "a")
        gr.add_node("proj3", "function", "b")
        gr.add_dep("proj3", "a", "b", dep_type="import")
        deps = gr.get_deps("proj3")
        assert len(deps) == 1
        assert deps[0]["from_node"] == "a"
        assert deps[0]["to_node"] == "b"

    def test_traverse_finds_related_nodes(self, project_repo, isolated_datastore):
        gr = get_repo("graph")
        gr.add_node("proj4", "function", "main")
        gr.add_node("proj4", "function", "helper")
        gr.add_node("proj4", "function", "utils")
        gr.add_dep("proj4", "main", "helper")
        gr.add_dep("proj4", "helper", "utils")
        result = gr.traverse("proj4", "main", depth=2)
        assert result["total"] >= 1
        assert result["direct"] >= 1  # helper is direct dep
        assert result["risk"] > 0

    def test_traverse_returns_empty_for_isolated_node(self, project_repo, isolated_datastore):
        gr = get_repo("graph")
        gr.add_node("proj_isolated", "function", "lonely")
        result = gr.traverse("proj_isolated", "lonely")
        assert result["nodes"] == []

    def test_list_projects_aggregates(self, project_repo, isolated_datastore):
        gr = get_repo("graph")
        gr.add_node("plist1", "function", "f1")
        gr.add_node("plist1", "class", "C1")
        projects = gr.list_projects()
        ids = [p["id"] for p in projects]
        assert "plist1" in ids

    def test_merge_project_combines_nodes(self, project_repo, isolated_datastore):
        gr = get_repo("graph")
        gr.add_node("src_p", "function", "src_fn")
        gr.add_node("dst_p", "function", "dst_fn")
        count = gr.merge_project("src_p", "dst_p")
        assert count == 2  # both nodes now in dst_p
        src_nodes = gr.get_project_nodes("src_p")
        assert src_nodes == []  # src is empty

    def test_format_context_returns_string(self, project_repo, isolated_datastore):
        gr = get_repo("graph")
        gr.add_node("fmt_proj", "function", "fmt_fn")
        gr.add_node("fmt_proj", "class", "FmtClass")
        context = gr.format_context("fmt_proj")
        assert isinstance(context, str)
        # format_context shows summary counts, not individual names without keywords
        assert "项目代码库" in context
        assert "2 符号" in context or "函数" in context

    def test_format_context_with_keywords(self, project_repo, isolated_datastore):
        gr = get_repo("graph")
        gr.add_node("fmt_kw", "function", "calc_sum")
        context = gr.format_context("fmt_kw", keywords=["calc"])
        assert isinstance(context, str)

    def test_get_deps_filters_by_node(self, project_repo, isolated_datastore):
        gr = get_repo("graph")
        gr.add_node("dep_proj", "function", "x")
        gr.add_node("dep_proj", "function", "y")
        gr.add_node("dep_proj", "function", "z")
        gr.add_dep("dep_proj", "x", "y")
        gr.add_dep("dep_proj", "x", "z")
        deps = gr.get_deps("dep_proj", node_name="x")
        assert len(deps) == 2

    def test_query_graph(self, project_repo, isolated_datastore):
        gr = get_repo("graph")
        gr.add_node("q_proj", "function", "search_target")
        results = gr.query("search_target", project_id="q_proj")
        assert len(results) >= 1

    def test_query_graph_no_match(self, project_repo, isolated_datastore):
        gr = get_repo("graph")
        results = gr.query("zzz_nonexistent", project_id="no_match_proj")
        assert results == []


# ═══════════════════════════════════════════════════════════════
# ConfigRepo (via CEOMemory)
# ═══════════════════════════════════════════════════════════════

class TestConfigRepo:
    """CEOMemory config_load/config_set tested via isolated_datastore."""

    def test_config_load_returns_defaults(self, isolated_datastore, temp_dir):
        from dong_ai.ceo_memory import CEOMemory
        mem = CEOMemory()
        cfg = mem.config_load()
        assert cfg["context_length"] == "200000"
        assert cfg["max_response"] == "16384"
        assert "mode" in cfg

    def test_config_set_and_load(self, isolated_datastore, temp_dir):
        from dong_ai.ceo_memory import CEOMemory
        mem = CEOMemory()
        mem.config_set("temperature", "0.5")
        cfg = mem.config_load()
        assert cfg["temperature"] == "0.5"

    def test_config_set_overwrites(self, isolated_datastore, temp_dir):
        from dong_ai.ceo_memory import CEOMemory
        mem = CEOMemory()
        mem.config_set("max_response", "4096")
        cfg = mem.config_load()
        assert cfg["max_response"] == "4096"

    def test_config_load_handles_missing_file(self, isolated_datastore, temp_dir):
        from dong_ai.ceo_memory import CEOMemory
        mem = CEOMemory()
        # Remove config file to verify defaults are used
        cfg_path = mem.base_dir.parent / "config.ini"
        if cfg_path.exists():
            cfg_path.unlink()
        cfg = mem.config_load()
        assert cfg["context_length"] == "32768"
