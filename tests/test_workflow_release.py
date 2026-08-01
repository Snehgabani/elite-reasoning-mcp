import json

from core.eval.exporters import export_eval_harness
from core.memory.persistent_store import EliteStore
from core.orchestration.workflow_run import build_workflow_run, workflow_run_markdown
from core.tools.doctor import build_doctor_report


def test_workflow_run_persists_steps_and_status(tmp_path):
    store = EliteStore(str(tmp_path))
    run = build_workflow_run(
        "Build a release-grade MCP feature with tests, evidence, and validation.",
        store=store,
        persist=True,
    )

    stored = store.get_workflow_run(run["run_id"])

    assert stored is not None
    assert stored["run_id"] == run["run_id"]
    assert stored["status"] == "planned"
    assert len(stored["steps"]) == 6
    assert any("test" in gate.lower() or "validation" in gate.lower() for gate in stored["validation_gates"])

    assert store.update_workflow_step(run["run_id"], 4, "passed", "pytest passed") is True
    updated = store.get_workflow_run(run["run_id"])
    assert updated is not None
    assert updated["steps"][3]["status"] == "passed"
    assert updated["steps"][3]["evidence"] == "pytest passed"


def test_workflow_markdown_contains_machine_readable_json(tmp_path):
    store = EliteStore(str(tmp_path))
    run = build_workflow_run("Research benchmarks and cite evidence before building.", store=store)
    rendered = workflow_run_markdown(run)

    assert "# Elite Workflow Run" in rendered
    assert "## JSON" in rendered
    payload = rendered.split("```json", 1)[1].split("```", 1)[0]
    parsed = json.loads(payload)
    assert parsed["run_id"] == run["run_id"]
    assert parsed["budget_tier"] in {"standard", "high_risk", "research_grade", "trivial"}


def test_workflow_surfaces_degraded_memory_reads(tmp_path):
    class MemoryUnavailableStore(EliteStore):
        def search_memory_items(self, *args, **kwargs):
            raise RuntimeError("database temporarily unavailable")

    store = MemoryUnavailableStore(str(tmp_path / "brain"))
    run = build_workflow_run("Build a release-grade feature.", store=store, persist=False)

    assert run["memory_context"] == []
    assert run["warnings"] == [
        "Trusted memory context could not be read; proceeding without it."
    ]
    assert "Trusted memory context could not be read" in workflow_run_markdown(run)


def test_memory_items_are_quality_gated(tmp_path):
    store = EliteStore(str(tmp_path))
    trusted_id = store.record_memory_item(
        memory_type="project_fact",
        content="Elite workflow requires pytest and ruff before release.",
        scope="elite",
        confidence=0.9,
        trust_score=0.9,
    )
    secret_id = store.record_memory_item(
        memory_type="credential",
        content="fake secret should never auto-inject",
        scope="elite",
        confidence=0.9,
        trust_score=0.9,
        privacy_class="secret",
    )

    trusted = store.search_memory_items("pytest release", scope="elite")
    all_items = store.search_memory_items("secret", scope="elite", include_quarantined=True, min_trust=0.0)

    assert trusted_id in {item["id"] for item in trusted}
    assert secret_id not in {item["id"] for item in trusted}
    assert any(item["id"] == secret_id and item["quarantined"] for item in all_items)


def test_eval_harness_exporters_cover_optional_frameworks():
    files = export_eval_harness("all")

    assert "evals/promptfooconfig.yaml" in files
    assert "tests/evals/test_elite_reasoning.py" in files
    assert "evals/elite_reasoning.py" in files
    assert "promptfoo" in files["evals/promptfooconfig.yaml"].lower()
    assert "deepeval" in files["tests/evals/test_elite_reasoning.py"].lower()
    assert "inspect_ai" in files["evals/elite_reasoning.py"]


def test_doctor_report_checks_required_tables(tmp_path):
    store = EliteStore(str(tmp_path))
    report = build_doctor_report(store)

    assert report["db_exists"] is True
    assert report["required_tables_present"] is True
    assert "workflow_runs" not in report["missing_tables"]
    assert report["status"] in {"release_ready", "degraded", "blocked"}
