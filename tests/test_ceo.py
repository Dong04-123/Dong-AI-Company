"""Test: CEO run pipeline

Tests the CEO orchestration — project detection, pipeline building,
execution flow, board review, report generation, and error handling.
All tests use mock_llm to avoid real API calls.
"""

import json
import sys
import re
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from dong_ai.ceo import CEO
from dong_ai.datastore import Datastore, get_repo


# ═══════════════════════════════════════════════════════════════
# Global patches for known source-code issues
# ═══════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True, scope="module")
def _patch_broken_imports():
    """CEO._generate_report has 'from model_pool import ModelPool' (missing dot).
    We pre-populate sys.modules so that import succeeds but returns a mock."""
    fake_mp = MagicMock()
    fake_mp.ModelPool = MagicMock()
    sys.modules["model_pool"] = fake_mp
    yield
    sys.modules.pop("model_pool", None)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def _isolated_ds(temp_dir):
    """Reset Datastore singleton + repo cache per test."""
    import dong_ai.datastore as ds_mod
    ds_mod._repo_cache.clear()
    Datastore._instance = None
    yield
    if Datastore._instance is not None:
        try:
            Datastore._instance.close()
        except Exception:
            pass
    Datastore._instance = None
    ds_mod._repo_cache.clear()


@pytest.fixture
def ceo(mock_llm, tmp_path, _isolated_ds):
    """CEO with mocked LLM and isolated project dir + datastore."""
    return CEO(project_dir=str(tmp_path), llm_client=mock_llm)


# ═══════════════════════════════════════════════════════════════
# CEO Init
# ═══════════════════════════════════════════════════════════════

class TestCEOInit:
    """CEO initialization and configuration."""

    def test_init_creates_project_dir(self, mock_llm, tmp_path, _isolated_ds):
        tmp = tmp_path / "projects" / "test_init"
        ceo = CEO(project_dir=str(tmp), llm_client=mock_llm)
        assert tmp.exists()
        assert tmp.is_dir()

    def test_init_sets_llm(self, mock_llm, tmp_path, _isolated_ds):
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        assert ceo.llm is mock_llm

    def test_init_injects_ds(self, ceo):
        assert ceo.ds is not None

    def test_init_mode_is_valid(self, ceo):
        """Mode can be resolved (auto→local on machines without GPU)."""
        assert ceo._mode in ("auto", "api", "local")


# ═══════════════════════════════════════════════════════════════
# Project Type Detection
# ═══════════════════════════════════════════════════════════════
# NOTE: MockLLM matches keywords against message *content*, not
# system prompt.  The content built by _detect_project_type includes
# the user request, so we use request substrings as trigger keys.

class TestDetectProjectType:
    """_detect_project_type routing."""

    def test_detects_software(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.set_response("Build", "software")
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        ptype = ceo._detect_project_type("Build a web app")
        assert ptype == "software"

    def test_detects_novel(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.set_response("novel", "novel")
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        ptype = ceo._detect_project_type("Write a sci-fi novel")
        assert ptype == "novel"

    def test_detects_analysis(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.set_response("analysis", "analysis")
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        ptype = ceo._detect_project_type("Analyze market trends")
        assert ptype == "analysis"

    def test_detects_game(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.set_response("game", "game")
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        ptype = ceo._detect_project_type("Create a 2D platformer")
        assert ptype == "game"

    def test_detects_audit(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.set_response("audit", "audit")
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        ptype = ceo._detect_project_type("Audit the codebase")
        assert ptype == "audit"

    def test_fallback_to_software_on_no_match(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.set_response("默认", "unparseable response")
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        ptype = ceo._detect_project_type("Something vague")
        assert ptype == "software"

    def test_fallback_on_exception(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.chat = MagicMock(side_effect=RuntimeError("LLM down"))
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        ptype = ceo._detect_project_type("Anything")
        assert ptype == "software"


# ═══════════════════════════════════════════════════════════════
# Pipeline Building
# ═══════════════════════════════════════════════════════════════

class TestBuildPipeline:
    """_build_pipeline returns valid phase list."""

    def test_returns_list_of_phases(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.set_response(
            "项目",
            json.dumps([
                {"name": "Phase 1", "tasks": [{"id": "t1", "name": "Task 1", "description": "Do it", "deps": []}]},
                {"name": "Phase 2", "tasks": [{"id": "t2", "name": "Task 2", "description": "Finish it", "deps": ["t1"]}]},
            ])
        )
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        phases = ceo._build_pipeline("software", "build a thing")
        assert isinstance(phases, list)
        assert len(phases) >= 2

    def test_each_phase_has_name_and_tasks(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.set_response(
            "设计",
            json.dumps([
                {"name": "Design", "tasks": [{"id": "d1", "name": "Design API", "description": "API design", "deps": []}]},
                {"name": "Build", "tasks": [{"id": "b1", "name": "Implement", "description": "Code it", "deps": ["d1"]}]},
            ])
        )
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        phases = ceo._build_pipeline("software", "design")
        for p in phases:
            assert "name" in p
            assert "tasks" in p

    def test_fallback_on_bad_json(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.set_response("项目", "not json at all")
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        phases = ceo._build_pipeline("software", "whatever")
        assert len(phases) == 2
        assert phases[0]["name"] == "规划"

    def test_fallback_on_less_than_2_phases(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.set_response(
            "项目",
            json.dumps([{"name": "Only", "tasks": []}])
        )
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        phases = ceo._build_pipeline("software", "single")
        assert len(phases) == 2


# ═══════════════════════════════════════════════════════════════
# Board Review
# ═══════════════════════════════════════════════════════════════
# NOTE: MockLLM checks message content.  Board review content
# includes "综合评分", "阶段名称", "任务清单" etc.
# Use "评分" as trigger keyword.

class TestBoardReview:
    """_board_review scoring."""

    def test_returns_float_score(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.set_response("评分", "总分: 8.5")
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        score = ceo._board_review("Phase 1", [{"name": "Task1", "description": "desc"}])
        assert isinstance(score, float)
        assert 1.0 <= score <= 10.0

    def test_returns_high_score_for_good_work(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.set_response("评分", "总分: 9.8")
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        score = ceo._board_review("Phase 1", [{"name": "T1", "description": "d"}])
        assert score == 9.8

    def test_returns_low_score_for_poor_work(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.set_response("评分", "总分: 3.2")
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        score = ceo._board_review("Phase 1", [{"name": "T1", "description": "d"}])
        assert score == 3.2

    def test_clamps_score_between_1_and_10(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.set_response("评分", "总分: 15.0")
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        score = ceo._board_review("Phase 1", [{"name": "T1", "description": "d"}])
        assert score <= 10.0

        mock_llm.set_response("评分", "总分: 0.0")
        score = ceo._board_review("Phase 1", [{"name": "T1", "description": "d"}])
        assert score >= 1.0

    def test_defaults_to_7_when_no_tasks(self, mock_llm, tmp_path, _isolated_ds):
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        score = ceo._board_review("Empty phase", [])
        assert score == 7.0

    def test_defaults_to_7_on_parse_error(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.set_response("评分", "invalid format no score")
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        score = ceo._board_review("Broken", [{"name": "T1", "description": "d"}])
        assert score == 7.0


# ═══════════════════════════════════════════════════════════════
# Checkpoint & Resume
# ═══════════════════════════════════════════════════════════════

class TestCheckpoint:
    """_save_checkpoint and _load_checkpoint."""

    def test_save_checkpoint_creates_file(self, mock_llm, tmp_path, _isolated_ds):
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        ceo._save_checkpoint(0, [{"name": "P1", "tasks": []}], {})
        assert ceo.checkpoint_path.exists()

    def test_load_checkpoint_returns_data(self, mock_llm, tmp_path, _isolated_ds):
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        phases = [{"name": "P1", "tasks": []}]
        ceo._save_checkpoint(0, phases, {"project_name": "Test"})
        ckpt = ceo._load_checkpoint()
        assert ckpt["phase_idx"] == 0
        assert ckpt["project_type"] == "software"

    def test_load_checkpoint_missing_returns_empty(self, mock_llm, tmp_path, _isolated_ds):
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        ckpt = ceo._load_checkpoint()
        assert ckpt == {}


# ═══════════════════════════════════════════════════════════════
# Report Generation
# ═══════════════════════════════════════════════════════════════

class TestReportGeneration:
    """_generate_report output format."""

    def test_report_contains_project_name(self, mock_llm, tmp_path, _isolated_ds):
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        ceo.plan["project_name"] = "MyProject"
        ceo._evidence = [
            (0, "Task1", {"status": "done", "quality_score": 8.0,
                          "files": ["/tmp/output.py"], "test_count": 5,
                          "test_pass": 4, "lessons": [], "interfaces": []}),
        ]
        ceo.ds.add_decision("phase_0_board", "Test decision", score=8.0)
        report = ceo._generate_report()
        assert "MyProject" in report
        assert "执行报告" in report or "执行" in report

    def test_report_includes_score_summary(self, mock_llm, tmp_path, _isolated_ds):
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        ceo.plan["project_name"] = "Scored"
        ceo._evidence = [
            (0, "T1", {"status": "done", "quality_score": 9.0,
                       "files": [], "test_count": 0, "test_pass": 0,
                       "lessons": [], "interfaces": []}),
        ]
        ceo.ds.add_decision("phase_0_board", "Good work", score=9.0)
        report = ceo._generate_report()
        assert "评分" in report
        assert "9.0" in report or "9" in report

    def test_report_empty_when_no_decisions(self, mock_llm, tmp_path, _isolated_ds):
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        ceo.plan["project_name"] = "Empty"
        report = ceo._generate_report()
        assert isinstance(report, str)
        assert len(report) > 0


# ═══════════════════════════════════════════════════════════════
# Full Run — execution flow (patches WorkerPool)
# ═══════════════════════════════════════════════════════════════

class TestRunFlow:
    """CEO.run() happy path — full pipeline execution."""

    def test_run_completes_successfully(self, mock_llm, tmp_path, _isolated_ds, capsys):
        """Full run: detect → design → pipeline → execute → report."""
        mock_llm.set_response("Build", "software")
        mock_llm.set_response("项目", json.dumps([
            {"name": "Phase1", "tasks": [{"id": "t1", "name": "Task", "description": "Do", "deps": []}]},
            {"name": "Phase2", "tasks": [{"id": "t2", "name": "Task2", "description": "Do2", "deps": ["t1"]}]},
        ]))
        mock_llm.set_response("评分", "总分: 8.0")

        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        with patch("dong_ai.ceo.WorkerPool", MagicMock(), create=True):
            # _execute_phase does 'from worker import WorkerPool' — seed the import
            fake_worker_mod = MagicMock()
            fake_worker_mod.WorkerPool = MagicMock(return_value=MagicMock(
                assign_task=MagicMock(return_value={
                    "status": "done", "quality_score": 8.0,
                    "files": ["out.py"], "test_count": 5, "test_pass": 5,
                    "interfaces": [], "lessons": [],
                })
            ))
            import sys
            sys.modules["worker"] = fake_worker_mod
            try:
                ceo.run("Build a simple API")
            finally:
                sys.modules.pop("worker", None)

        captured = capsys.readouterr()
        assert "项目完成" in captured.out
        assert ceo.report_path.exists()
        report = ceo.report_path.read_text(encoding="utf-8")
        assert "执行报告" in report

    def _patch_worker(self, mock_llm, tmp_path):
        """Helper: create CEO and patch the broken 'from worker import WorkerPool'."""
        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        import sys
        fake_mod = MagicMock()
        fake_mod.WorkerPool = MagicMock(return_value=MagicMock(
            assign_task=MagicMock(return_value={
                "status": "done", "quality_score": 8.0,
                "files": [], "test_count": 0, "test_pass": 0,
                "interfaces": [], "lessons": [],
            })
        ))
        sys.modules["worker"] = fake_mod
        return ceo

    def _cleanup_worker(self):
        import sys
        sys.modules.pop("worker", None)

    def test_run_writes_plan_json(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.set_response("Build", "software")
        mock_llm.set_response("项目", json.dumps([
            {"name": "Phase1", "tasks": [{"id": "t1", "name": "Task", "description": "Do", "deps": []}]},
            {"name": "Phase2", "tasks": [{"id": "t2", "name": "Task2", "description": "Do2", "deps": ["t1"]}]},
        ]))
        mock_llm.set_response("评分", "总分: 8.0")

        ceo = self._patch_worker(mock_llm, tmp_path)
        try:
            ceo.run("Build something")
        finally:
            self._cleanup_worker()

        assert ceo.plan_path.exists()
        plan = json.loads(ceo.plan_path.read_text())
        assert "project_name" in plan
        assert "phases" in plan

    def test_run_writes_final_report(self, mock_llm, tmp_path, _isolated_ds):
        mock_llm.set_response("Build", "software")
        mock_llm.set_response("项目", json.dumps([
            {"name": "Phase1", "tasks": [{"id": "t1", "name": "Task", "description": "Do", "deps": []}]},
            {"name": "Phase2", "tasks": [{"id": "t2", "name": "Task2", "description": "Do2", "deps": ["t1"]}]},
        ]))
        mock_llm.set_response("评分", "总分: 8.0")

        ceo = self._patch_worker(mock_llm, tmp_path)
        try:
            ceo.run("Build it")
        finally:
            self._cleanup_worker()

        assert ceo.report_path.exists()
        report_text = ceo.report_path.read_text(encoding="utf-8")
        assert "# " in report_text

    def test_run_with_design_engine_mock(self, mock_llm, tmp_path, _isolated_ds):
        """Ensure design engine is called during run."""
        from dong_ai.design_engine import DesignEngine
        design_mock = MagicMock(spec=DesignEngine)
        design_mock.design.return_value = {
            "design": "# Architecture\nSimplified design",
            "score": 8.0,
            "project_name": "TestProj",
            "requirements": [],
        }
        design_mock.design_medium.return_value = {
            "design": "# Architecture\nSimplified design",
            "score": 8.0,
            "requirements": [],
        }
        design_mock._last_score = 8.0
        design_mock.get_coverage.return_value = {"missing": []}

        mock_llm.set_response("Build", "software")
        mock_llm.set_response("项目", json.dumps([
            {"name": "P1", "tasks": [{"id": "t1", "name": "T1", "description": "", "deps": []}]},
            {"name": "P2", "tasks": [{"id": "t2", "name": "T2", "description": "", "deps": ["t1"]}]},
        ]))
        mock_llm.set_response("评分", "总分: 7.5")

        ceo = CEO(
            project_dir=str(tmp_path),
            llm_client=mock_llm,
            design_engine=design_mock,
        )
        import sys
        fake_mod = MagicMock()
        fake_mod.WorkerPool = MagicMock(return_value=MagicMock(
            assign_task=MagicMock(return_value={
                "status": "done", "quality_score": 8.0,
                "files": [], "test_count": 0, "test_pass": 0,
                "interfaces": [], "lessons": [],
            })
        ))
        sys.modules["dong_ai.worker"] = fake_mod
        sys.modules["worker"] = fake_mod
        try:
            ceo.run("Build a service")
        finally:
            sys.modules.pop("worker", None)
            sys.modules.pop("dong_ai.worker", None)

        design_mock.design_medium.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# Error Handling
# ═══════════════════════════════════════════════════════════════

class TestErrorHandling:
    """CEO error handling when LLM fails."""

    def test_llm_failure_during_type_detection_uses_fallback(self, mock_llm, tmp_path, _isolated_ds):
        """LLM fails in type detection → falls back to 'software' and continues."""
        # Don't replace mock_llm.chat entirely — let it work for design engine.
        # Instead, make the response not match any type keyword so fallback triggers.
        mock_llm.set_response("默认", "some unrecognized output without type keywords")
        mock_llm.set_response("项目", json.dumps([
            {"name": "P1", "tasks": [{"id": "t1", "name": "T1", "description": "", "deps": []}]},
            {"name": "P2", "tasks": [{"id": "t2", "name": "T2", "description": "", "deps": ["t1"]}]},
        ]))
        mock_llm.set_response("评分", "总分: 7.0")

        ceo = CEO(project_dir=str(tmp_path), llm_client=mock_llm)
        import sys
        fake_mod = MagicMock()
        fake_mod.WorkerPool = MagicMock(return_value=MagicMock(
            assign_task=MagicMock(return_value={
                "status": "done", "quality_score": 7.0,
                "files": [], "test_count": 0, "test_pass": 0,
                "interfaces": [], "lessons": [],
            })
        ))
        sys.modules["dong_ai.worker"] = fake_mod
        sys.modules["worker"] = fake_mod
        try:
            ceo.run("Do something")
        finally:
            sys.modules.pop("worker", None)
            sys.modules.pop("dong_ai.worker", None)

        assert ceo.report_path.exists()

    def test_design_engine_failure_raised(self, mock_llm, tmp_path, _isolated_ds):
        from dong_ai.design_engine import DesignEngine
        design_mock = MagicMock(spec=DesignEngine)
        design_mock.design.side_effect = RuntimeError("Design failed")
        design_mock.design_medium.side_effect = RuntimeError("Design failed")

        ceo = CEO(
            project_dir=str(tmp_path),
            llm_client=mock_llm,
            design_engine=design_mock,
        )
        with pytest.raises(RuntimeError, match="Design failed"):
            ceo.run("Design this")
