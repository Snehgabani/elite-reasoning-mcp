from __future__ import annotations
# src/leverage/lessons.py
# REFLEXION PERSISTENT LESSON STORE (Shinn et al., arXiv:2303.11366).
#
# Captures tool failures WITH root-cause text into .ai/memory/lessons.jsonl
# (deduplicated, cross-session). Injected into every execute_singularity run so
# the agent never repeats a past mistake. Nightly digest -> .ai/memory/lessons.md
#
# Note: tool_usage.jsonl only logs success booleans — root causes live in the
# tool RESULT strings (failure_type / <reason>), so capture happens at the
# tool boundary in mcp_server.py via LessonStore.record().

import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MEMORY_DIR = ROOT / ".ai" / "memory"

LESSONS_FILE = MEMORY_DIR / "lessons.jsonl"
DIGEST_FILE = MEMORY_DIR / "lessons.md"
MAX_DETAIL = 700          # per-lesson root-cause text cap
DEDUP_WINDOW_DAYS = 7    # same fingerprint within a week = already learned


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def fingerprint(tool: str, detail: str) -> str:
    norm = " ".join((detail or "").split())[:160].lower()
    return hashlib.sha1(f"{tool}|{norm}".encode()).hexdigest()[:16]


class LessonStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else LESSONS_FILE

    def _load(self) -> list:
        if not self.path.exists():
            return []
        rows = []
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
        except OSError:
            pass
        return rows

    def record(self, tool: str, task: str, detail: str, fp: str | None = None) -> bool:
        """Append a failure lesson unless already learned within the window."""
        detail = (detail or "").strip()
        if not detail:
            return False
        fp = fp or fingerprint(tool, detail)
        cutoff = time.time() - DEDUP_WINDOW_DAYS * 86400
        rows = self._load()
        if any(r.get("fingerprint") == fp and r.get("ts_unix", 0) >= cutoff for r in rows):
            return False  # dedupe: identical lesson already stored this week
        entry = {
            "ts": _now_iso(),
            "ts_unix": time.time(),
            "tool": tool,
            "task": (task or "")[:120],
            "detail": detail[:MAX_DETAIL],
            "fingerprint": fp,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return True

    def search_relevant(self, query: str, n: int = 5) -> list[dict]:
        """
        Retrieves top n failure lessons ranked by keyword relevance overlap with the query.
        Falls back to newest lessons if no query terms match.
        """
        rows = self._load()
        if not rows:
            return []
        
        query_tokens = set(re.findall(r"\w+", (query or "").lower()))
        if not query_tokens:
            return self.recent(n)

        scored_rows = []
        for r in rows:
            text = f"{r.get('tool', '')} {r.get('task', '')} {r.get('detail', '')}".lower()
            text_tokens = set(re.findall(r"\w+", text))
            overlap = len(query_tokens.intersection(text_tokens))
            recency_bonus = min(0.5, (r.get("ts_unix", 0) - (time.time() - 86400 * 30)) / (86400 * 30))
            score = overlap + recency_bonus
            scored_rows.append((score, r))

        scored_rows.sort(key=lambda x: x[0], reverse=True)
        return [
            {"tool": r.get("tool", "?"), "detail": (r.get("detail") or "")[:260]}
            for score, r in scored_rows[:n]
        ]

    def recent(self, n: int = 5) -> list[dict]:
        """Newest n lessons, newest first — injected verbatim into new runs."""
        rows = self._load()
        return [
            {"tool": r.get("tool", "?"), "detail": (r.get("detail") or "")[:260]}
            for r in rows[-n:][::-1]
        ]

    def digest(self, save: bool = True) -> str:
        """Markdown digest for the nightly lessons.md (deterministic, stdlib-only)."""
        rows = self._load()
        per_tool = Counter(r.get("tool", "?") for r in rows)
        lines = [
            "# Persistent Lessons — daily digest",
            f"generated: {_now_iso()}",
            f"total lessons: {len(rows)}",
            "",
            "## By tool (most failures)",
        ]
        lines += [f"- {t}: {c}" for t, c in per_tool.most_common()] or ["- (none yet)"]
        lines += ["", "## Latest failures (deduplicated, newest first)"]
        for r in rows[-8:][::-1]:
            lines.append(f"- [{r.get('ts','')}] {r.get('tool')}: {(r.get('detail') or '')[:220]}")
        text = "\n".join(lines) + "\n"
        if save:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            DIGEST_FILE.write_text(text, encoding="utf-8")
        return text


def main() -> None:
    """CLI entry for the nightly cron: writes lessons.md, prints a one-liner."""
    store = LessonStore()
    digest = store.digest(save=True)
    count = digest.splitlines()[2].split(":")[-1].strip()
    print(f"lessons digest: {count} lessons -> {DIGEST_FILE}")


if __name__ == "__main__":
    main()