"""Test: ExperienceEngine — 复盘、技能固化、经验召回"""

import json, os, time
from pathlib import Path

import pytest


@pytest.fixture
def engine(temp_dir, monkeypatch):
    from dong_ai.experience_engine import ExperienceEngine, _LESSONS_DIR
    # Point to temp dir
    monkeypatch.setattr("dong_ai.experience_engine._LESSONS_DIR", temp_dir / "lessons")
    (temp_dir / "lessons").mkdir(parents=True, exist_ok=True)
    return ExperienceEngine(llm=None), temp_dir / "lessons"


class TestDebrief:
    def test_debrief_creates_skill_file(self, engine):
        eng, lessons_dir = engine
        path = eng.debrief(
            project_type="software",
            user_request="Build a CLI tool",
            design="## Design\nCLI with argparse",
            phases=[{"name": "design"}, {"name": "code"}],
            scores=[8.5, 9.0],
            report_text="Project completed successfully",
        )
        assert Path(path).exists()
        assert "lessons-software-" in Path(path).name

    def test_debrief_content_has_metadata(self, engine):
        eng, _ = engine
        path = eng.debrief(
            project_type="analysis",
            user_request="Analyze market data",
            design="## Plan",
            phases=[{"name": "phase1"}],
            scores=[7.5],
            report_text="Done",
        )
        text = Path(path).read_text()
        assert "tags:" in text
        assert "analysis" in text
        assert "评分: 7.5" in text

    def test_debrief_with_zero_scores(self, engine):
        eng, _ = engine
        path = eng.debrief(
            project_type="novel",
            user_request="Write a story",
            design="## Outline",
            phases=[],
            scores=[],
            report_text="",
        )
        text = Path(path).read_text()
        assert "评分: 0.0" in text

    def test_debrief_extracts_tags_from_request(self, engine):
        eng, _ = engine
        path = eng.debrief(
            project_type="software",
            user_request="Build a Django REST API backend",
            design="## Design with PostgreSQL",
            phases=[],
            scores=[8.0],
            report_text="",
        )
        text = Path(path).read_text()
        assert "django" in text.lower() or "rest" in text.lower()
        assert "postgresql" in text.lower() or "postgres" in text.lower()

    def test_default_lessons_when_no_llm(self, engine):
        eng, _ = engine
        lessons = eng._default_lessons("software", [8.0, 9.0])
        assert len(lessons) >= 1
        assert lessons[0]["type"] == "经验"
        assert "software" in lessons[0]["content"]

    def test_default_lessons_with_low_score(self, engine):
        eng, _ = engine
        lessons = eng._default_lessons("software", [5.5])
        types = [l["type"] for l in lessons]
        assert "教训" in types


class TestRecall:
    def test_recall_empty_when_no_lessons(self, engine):
        eng, _ = engine
        ctx = eng.recall("Build something")
        assert ctx == ""

    def test_recall_finds_relevant_lessons(self, engine):
        eng, lessons_dir = engine
        # Create a lesson
        eng.debrief("software", "Build a CLI with Python", "## Design", [],
                     [8.0], "Good project")
        # Recall with similar request
        ctx = eng.recall("Build a CLI tool", project_type="software")
        assert "历史经验" in ctx
        assert "software" in ctx

    def test_recall_ignores_unrelated(self, engine):
        eng, _ = engine
        eng.debrief("novel", "Write fantasy novel", "## Plot", [],
                     [9.0], "Great story")
        ctx = eng.recall("Build a data pipeline", project_type="software")
        assert ctx == "" or "历史经验" not in ctx

    def test_recall_returns_top_3(self, engine):
        eng, _ = engine
        for i in range(5):
            eng.debrief("software", f"Project {i}", "## Design", [],
                         [8.0], "Done")
        ctx = eng.recall("software project", project_type="software")
        count = ctx.count("###")
        assert count <= 3

    def test_recall_without_project_type(self, engine):
        eng, _ = engine
        eng.debrief("software", "Build CLI", "## Des", [], [8.0], "Done")
        ctx = eng.recall("CLI")
        # Should still find via keyword match
        assert ctx != ""


class TestProjectStats:
    def test_stats_empty(self, engine):
        eng, _ = engine
        stats = eng.project_stats()
        assert stats["total_projects"] == 0
        assert stats["avg_score"] == 0

    def test_stats_after_lessons(self, engine):
        eng, _ = engine
        eng.debrief("software", "A", "## D", [], [8.0], "R")
        eng.debrief("analysis", "B", "## D", [], [9.0], "R")
        stats = eng.project_stats()
        assert stats["total_projects"] == 2
        assert stats["by_type"]["software"] == 1
        assert stats["by_type"]["analysis"] == 1
        assert stats["avg_score"] == 8.5


class TestMetadataParsing:
    def test_parse_skill_meta(self, engine):
        eng, _ = engine
        text = """---
name: lessons-software-123
tags: [software, lessons, cli]
created: 2026-06-06
---
类型: software
评分: 8.5
需求: Build CLI tool
## 经验
"""
        meta = eng._parse_skill_meta(text)
        assert meta["type"] == "software"
        assert meta["score"] == 8.5
        assert "cli" in meta.get("tags", [])
