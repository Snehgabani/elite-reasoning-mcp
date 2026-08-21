# src/leverage/prompt_optimizer.py
# SkillCompiler v2 — compiles exemplars from REAL trace data only.
# v1 (2026-08-08) emitted hardcoded fake exemplars ("Sample debug optimization
# task / Passed 100% verifier checks") regardless of data — fabricated evidence
# filed as results. v2 (2026-08-09, audit fix) reads .ai/metrics/runs/*/<task>.json
# and writes truthful per-category exemplars; categories with no real traces get
# an explicit EMPTY marker, never invented content.
import glob
import json
import os
from collections import defaultdict
from typing import Any, Dict, List

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class SkillCompiler:
    def __init__(self,
                 trace_dir: str = f"{REPO}/.ai/metrics/runs",
                 out_dir: str = f"{REPO}/.ai/skills/compiled",
                 lessons_file: str = f"{REPO}/.ai/memory/lessons.jsonl"):
        self.trace_dir = trace_dir
        self.out_dir = out_dir
        self.lessons_file = lessons_file
        os.makedirs(self.out_dir, exist_ok=True)


    # task 'type' -> exemplar category (v1 categories kept for compat)
    _CATEGORY_MAP = {
        "bug": "debug",
        "refactor": "architecture",
        "feature": "algorithm",
        "algorithm": "algorithm",
        "review": "review",
        "design": "review",
    }

    def _load_traces(self) -> List[Dict[str, Any]]:
        traces = []
        for path in sorted(glob.glob(os.path.join(self.trace_dir, "*", "*.json"))):
            try:
                with open(path, encoding="utf-8") as f:
                    d = json.load(f)
                d.setdefault("_path", path)
                traces.append(d)
            except Exception:
                continue  # unreadable trace: skip, never invent
        return traces

    def _load_lessons(self) -> List[Dict[str, Any]]:
        lessons = []
        if not os.path.exists(self.lessons_file):
            return lessons
        try:
            with open(self.lessons_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        lessons.append(json.loads(line))
                    except Exception:
                        continue
        except Exception:
            return lessons
        return lessons

    def _verifier_summary(self, trace: Dict[str, Any], max_chars: int = 400) -> str:
        """Short factual slice of verifier_output, or an explicit 'no verifier output'."""
        out = ""
        if isinstance(trace.get("verifier_output"), str):
            out = trace["verifier_output"].strip().replace("\n", " | ")
        if not out:
            return "NO VERIFIER OUTPUT RECORDED"
        return out[:max_chars]

    def compile_all(self) -> Dict[str, int]:
        traces = self._load_traces()
        by_cat: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for t in traces:
            cat = self._CATEGORY_MAP.get(str(t.get("type", "")), "general")
            by_cat[cat].append(t)

        lessons = self._load_lessons()
        compiled_counts: Dict[str, int] = {}
        for cat in self._CATEGORY_MAP.values():
            compiled_counts[cat] = 0

        all_cats = sorted(set(self._CATEGORY_MAP.values()) | set(by_cat.keys()))
        for cat in all_cats:
            cat_traces = by_cat[cat]
            winners = [t for t in cat_traces if t.get("passed") is True]
            losers = [t for t in cat_traces if t.get("passed") is not True]
            compiled_counts[cat] = len(winners)

            lines = [f"# Compiled Exemplars: {cat}", ""]
            lines.append(f"_Source: {len(cat_traces)} real traces "
                         f"({len(winners)} passed / {len(losers)} failed). "
                         f"Compiled {__import__('datetime').datetime.now().isoformat(timespec='minutes')}._")
            lines.append("")
            for i, w in enumerate(winners, 1):
                lines.append(f"## Exemplar {i} — {w.get('task_id')} ({w.get('mode', '?')})")
                lines.append(f"TASK: {w.get('_path')}")
                lines.append(f"WINNING EVIDENCE: score={w.get('score')} "
                             f"tokens={w.get('total_tokens')} "
                             f"time={w.get('time_seconds')}s "
                             f"backtracks={w.get('number_of_backtracks')} "
                             f"human_edit={w.get('human_edit_required')}")
                lines.append(f"VERIFIER: {self._verifier_summary(w)}")
                lines.append("")
            for los in losers:
                lines.append(f"## NON-WINNING TRACE (lesson material) — {los.get('task_id')} ({los.get('mode')})")
                lines.append(f"TASK: {los.get('_path')}")
                lines.append(f"STATE: passed={los.get('passed')} score={los.get('score')}")
                lines.append(f"VERIFIER: {self._verifier_summary(los)}")
                lines.append("")

            # Real lessons from the lesson store that mention this category
            cat_lessons = [l for l in lessons
                                      if str(l.get("tool", "")) == cat
                                      or cat in str(l.get("task", ""))]
            if cat_lessons:
                lines.append("## Lessons (from lessons.jsonl)")
                for l in cat_lessons[:5]:
                    lines.append(f"- {l.get('tool')}: {str(l.get('detail'))[:200]}")
                lines.append("")

            if not cat_traces:
                lines.append("_No real traces for this category yet — compiling nothing "
                             "(avoiding fabricated exemplars)._")
                lines.append("")

            with open(os.path.join(self.out_dir, f"{cat}.md"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines).rstrip() + "\n")

        # general category: anything unmapped
        others = [t for t in traces if self._CATEGORY_MAP.get(str(t.get("type", ""))) is None]
        compiled_counts["general"] = len([t for t in others if t.get("passed") is True])
        lines = ["# Compiled Exemplars: general", "",
                 f"_Source: {len(others)} real traces with unmapped types. "
                 f"Compiled {__import__('datetime').datetime.now().isoformat(timespec='seconds')}._", ""]
        if others:
            for i, t in enumerate(others, 1):
                if t.get("passed") is True:
                    lines.append(f"## Exemplar {i} — {t.get('task_id')}")
                    lines.append(f"TASK: {t.get('_path')}")
                    lines.append(f"VERIFIER: {self._verifier_summary(t)}")
                    lines.append("")
        else:
            lines.append("_No real unmapped-type traces._")
            lines.append("")
        with open(os.path.join(self.out_dir, "general.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines).rstrip() + "\n")

        return compiled_counts


def main() -> None:
    c = SkillCompiler()
    counts = c.compile_all()
    total = sum(counts.values())
    print(f"compiled: total_real_exemplars={total} per-category={counts}")
    print("NOTE: compiled only from real .ai/metrics/runs traces; empty categories are marked, not invented.")


if __name__ == "__main__":
    main()
