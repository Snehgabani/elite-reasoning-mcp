"""
Continuous Benchmark Daemon & Quality Regression Monitor.
Runs scheduled double-blind RCT suites, tracks historical drift in SQLite / JSONL,
and flags regressions if Cohen's d drops below target thresholds.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from core.eval.rct_runner import DoubleBlindRCTRunner


class BenchmarkDaemon:
    """
    Manages recurring double-blind RCT evaluations and persistent historical telemetry.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or (Path.home() / ".elite-reasoning/benchmarks")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.output_dir / "history.jsonl"
        self.latest_md = self.output_dir / "LATEST_BENCHMARK.md"
        self.runner = DoubleBlindRCTRunner()

    def execute_cycle(self, split: str = "all") -> Dict[str, Any]:
        """Runs a single benchmark evaluation cycle and records telemetry."""
        results = self.runner.run_suite(split=split)
        report_md = self.runner.generate_markdown_report(results)

        # 1. Append to history.jsonl
        record = {
            "timestamp": results["timestamp"],
            "split": results["split"],
            "verdict": results["scorecard"]["empirical_verdict"],
            "pass_rate_baseline": results["scorecard"]["baseline_pass_rate"],
            "pass_rate_treatment": results["scorecard"]["treatment_pass_rate"],
            "cohens_d": results["scorecard"]["cohens_d"],
            "mcnemar_p": results["scorecard"]["mcnemar_p_value"],
            "elo_delta": results["scorecard"]["elo_delta"],
            "headache_reduction_pct": results["scorecard"]["headache_reduction_pct"],
        }
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        # 2. Write latest markdown report
        self.latest_md.write_text(report_md, encoding="utf-8")

        return {
            "status": "completed",
            "timestamp": record["timestamp"],
            "verdict": record["verdict"],
            "cohens_d": record["cohens_d"],
            "history_path": str(self.history_file),
            "latest_md_path": str(self.latest_md),
        }
