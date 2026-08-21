"""
Unit tests for AST Symbol Outliner & Call Graph Explorer (core/search/symbol_indexer.py).
"""

from __future__ import annotations

from core.search.symbol_indexer import (
    extract_symbol_outline,
    extract_call_graph,
    OutlineResult,
    CallGraphResult,
)

SAMPLE_CODE = """
import os
from typing import List, Optional

@decorator_a
@decorator_b(param="val")
class DataPipeline:
    \"\"\"Main pipeline processing data chunks.\"\"\"

    def __init__(self, name: str, batch_size: int = 100) -> None:
        self.name = name
        self.batch_size = batch_size
        self.records = []
        for i in range(100):
            self.records.append(i * 2)

    @validate_input
    async def process_item(self, item_id: str) -> bool:
        \"\"\"Asynchronously processes a single record.\"\"\"
        raw = self.fetch_raw(item_id)
        cleaned = clean_payload(raw)
        return self.save_result(cleaned)

    def fetch_raw(self, item_id: str) -> dict:
        return {"id": item_id, "data": "raw"}

    def save_result(self, data: dict) -> bool:
        return True


def clean_payload(raw: dict) -> dict:
    \"\"\"Cleans raw payload dict.\"\"\"
    return {k: v.strip() if isinstance(v, str) else v for k, v in raw.items()}


def orchestrate(item_ids: List[str]) -> int:
    \"\"\"Entry point orchestrating all pipeline tasks.\"\"\"
    pipe = DataPipeline("prod")
    count = 0
    for i in item_ids:
        raw = pipe.fetch_raw(i)
        cleaned = clean_payload(raw)
        pipe.save_result(cleaned)
        count += 1
    return count
"""


def test_extract_symbol_outline():
    res = extract_symbol_outline(SAMPLE_CODE, filename="pipeline.py")
    assert isinstance(res, OutlineResult)
    assert res.filename == "pipeline.py"
    assert res.total_raw_lines > 30
    assert res.total_outline_lines < res.total_raw_lines
    assert res.token_reduction_pct > 20.0  # Significant reduction

    # Verify Class Outline
    assert len(res.classes) == 1
    cls_sym = res.classes[0]
    assert cls_sym.name == "DataPipeline"
    assert "decorator_a" in cls_sym.decorators[0]
    assert len(cls_sym.methods) == 4
    method_names = [m.name for m in cls_sym.methods]
    assert "__init__" in method_names
    assert "process_item" in method_names
    assert "fetch_raw" in method_names
    assert "save_result" in method_names

    # Verify Functions
    fn_names = [f.name for f in res.functions]
    assert "clean_payload" in fn_names
    assert "orchestrate" in fn_names

    # Verify Skeleton Code
    assert "class DataPipeline:" in res.skeleton_code
    assert "async def process_item" in res.skeleton_code
    assert "def orchestrate" in res.skeleton_code
    assert "..." in res.skeleton_code


def test_extract_call_graph_and_blast_radius():
    cg = extract_call_graph(SAMPLE_CODE, filename="pipeline.py")
    assert isinstance(cg, CallGraphResult)
    assert cg.total_symbols >= 5

    # Check caller and callee relationships
    assert "clean_payload" in cg.nodes
    clean_node = cg.nodes["clean_payload"]
    assert "process_item" in clean_node.callers or "orchestrate" in clean_node.callers

    # Check blast radius
    blast = cg.get_blast_radius("clean_payload")
    assert len(blast) >= 1
    assert "orchestrate" in blast or "process_item" in blast


def test_syntax_error_graceful_handling():
    bad_code = "def broken_func(:\n    return 1"
    res = extract_symbol_outline(bad_code, filename="bad.py")
    assert "SyntaxError" in res.skeleton_code

    cg = extract_call_graph(bad_code, filename="bad.py")
    assert cg.total_symbols == 0
