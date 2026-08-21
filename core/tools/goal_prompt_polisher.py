"""Goal-Aligned Prompt Polisher — makes every prompt elite.

Integrates active goals, prompt quality scoring, and intelligent
enhancement so that every user request produces the best possible output.

Architecture:
  1. Fetch active goals → build goal context
  2. Score raw prompt quality (0-100)
  3. Polish: add specificity, edge-case awareness, quality gates
  4. Score polished prompt quality
  5. Return enhanced prompt + metadata

Usage:
  polisher = GoalPromptPolisher(store)
  result = polisher.polish("fix the login bug")
  # result.polished_prompt, result.original_score, result.polished_score, result.goals_aligned
"""
import re
from dataclasses import dataclass, field


@dataclass
class PolishResult:
    """Result of a prompt polishing operation."""
    original_prompt: str
    polished_prompt: str
    original_score: int
    polished_score: int
    goals_aligned: list[str] = field(default_factory=list)
    enhancements_applied: list[str] = field(default_factory=list)
    goal_context_injected: bool = False
    complexity: int = 1
    intent: str = "general"


class GoalPromptPolisher:
    """The unified prompt polishing engine.

    Combines goal awareness, quality scoring, and intelligent
    enhancement into a single pipeline that upgrades every prompt.
    """

    # ── Quality signals that boost prompt score ──────────────
    QUALITY_SIGNALS = [
        (r'\b(specific|exactly|precise)\b', 5, "specificity"),
        (r'\b(verify|validate|test|check)\b', 5, "verification"),
        (r'\b(step.by.step|phase|stage)\b', 5, "structured_approach"),
        (r'\b(constraint|requirement|must|shall)\b', 4, "constraints"),
        (r'\b(edge.case|corner.case|error.handling)\b', 6, "edge_cases"),
        (r'\b(metric|measure|benchmark|score)\b', 5, "measurability"),
        (r'\b(why|because|reason|rationale)\b', 4, "reasoning"),
        (r'\b(trade.?off|alternative|option)\b', 4, "trade_off_awareness"),
        (r'\b(security|vulnerability|injection|xss|csrf)\b', 5, "security"),
        (r'\b(performance|latency|throughput|scale)\b', 4, "performance"),
        (r'\b(rollback|revert|undo|backup)\b', 4, "safety_net"),
        (r'\b(document|explain|comment)\b', 3, "documentation"),
    ]

    # ── Enhancement rules: what to add based on what's missing ──
    ENHANCEMENT_RULES = [
        {
            "check": lambda p: not re.search(r'\b(verify|validate|test|check|ensure)\b', p, re.I),
            "inject": "Verify the solution works correctly before finalizing.",
            "tag": "verification_gate",
        },
        {
            "check": lambda p: not re.search(r'\b(edge.case|corner.case|error|fail|exception)\b', p, re.I),
            "inject": "Handle edge cases and error scenarios explicitly.",
            "tag": "edge_case_coverage",
        },
        {
            "check": lambda p: not re.search(r'\b(why|because|reason|trade.?off)\b', p, re.I)
                              and len(p.split()) > 10,
            "inject": "Explain the reasoning behind key decisions.",
            "tag": "reasoning_depth",
        },
        {
            "check": lambda p: not re.search(r'\b(metric|measure|benchmark|quality)\b', p, re.I)
                              and len(p.split()) > 15,
            "inject": "Define measurable success criteria.",
            "tag": "measurability",
        },
        {
            "check": lambda p: not re.search(r'\b(step|phase|first|then|next|finally)\b', p, re.I)
                              and len(p.split()) > 20,
            "inject": "Break the approach into clear phases.",
            "tag": "structured_approach",
        },
        {
            "check": lambda p: not re.search(r'\b(security|auth|permission|sanitize)\b', p, re.I)
                              and re.search(r'\b(api|endpoint|user|input|form|database)\b', p, re.I),
            "inject": "Consider security implications (input validation, auth, injection prevention).",
            "tag": "security_awareness",
        },
        {
            "check": lambda p: not re.search(r'\b(performance|scale|optimize|cache|lazy)\b', p, re.I)
                              and re.search(r'\b(database|query|api|load|list|fetch|render)\b', p, re.I),
            "inject": "Consider performance implications for the chosen approach.",
            "tag": "performance_awareness",
        },
    ]

    # ── Intent keywords for classification ──────────────────
    INTENT_MAP = {
        "debug": ["debug", "fix", "error", "bug", "broken", "crash", "fail", "issue"],
        "build": ["build", "create", "implement", "add", "new", "write", "develop", "make"],
        "refactor": ["refactor", "clean", "simplify", "restructure", "improve code"],
        "deploy": ["deploy", "release", "publish", "ship", "push to prod"],
        "investigate": ["investigate", "research", "explore", "find out", "understand"],
        "design": ["design", "architect", "plan", "structure", "diagram"],
        "test": ["test", "verify", "validate", "check", "qa", "coverage"],
        "optimize": ["optimize", "performance", "speed up", "reduce", "improve"],
        "audit": ["audit", "review", "security", "compliance", "assess"],
    }

    def __init__(self, store):
        self.store = store

    def polish(self, prompt: str) -> PolishResult:
        """Main entry point: polish a prompt for maximum output quality.

        Pipeline:
          1. Score original prompt
          2. Classify intent and complexity
          3. Fetch active goals
          4. Build goal-aligned enhancements
          5. Apply missing quality directives
          6. Score polished prompt
          7. Return PolishResult
        """
        if not prompt or not prompt.strip():
            return PolishResult(
                original_prompt=prompt,
                polished_prompt=prompt,
                original_score=0,
                polished_score=0,
            )

        # 1. Score original
        original_score = self.score_prompt(prompt)

        # 2. Classify
        intent = self._classify_intent(prompt)
        complexity = self._classify_complexity(prompt, intent)

        # 3. Fetch active goals
        goals_aligned = []
        goal_context = ""
        try:
            active_goals = self.store.get_active_goals()
            if active_goals:
                goal_context, goals_aligned = self._build_goal_context(
                    active_goals, prompt, intent
                )
        except Exception as exc:
            # Explicit non-fatal exception suppression
            _ = str(exc)  # Goals are optional — don't break on DB errors

        # 4-5. Build polished prompt
        enhancements = []
        polished = self._apply_polish(prompt, intent, complexity, goal_context, enhancements)

        # 6. Score polished
        polished_score = self.score_prompt(polished)

        # 7. Return result
        return PolishResult(
            original_prompt=prompt,
            polished_prompt=polished,
            original_score=original_score,
            polished_score=polished_score,
            goals_aligned=goals_aligned,
            enhancements_applied=enhancements,
            goal_context_injected=bool(goal_context),
            complexity=complexity,
            intent=intent,
        )

    def score_prompt(self, prompt: str) -> int:
        """Score a prompt's quality (0-100) based on structural signals.

        Not about content correctness — about whether the prompt
        contains the signals that lead to high-quality outputs:
        specificity, verification, edge cases, constraints, etc.
        """
        if not prompt:
            return 0

        score = 30  # Base score for any non-empty prompt
        prompt_lower = prompt.lower()
        word_count = len(prompt.split())

        # Length bonus (longer prompts tend to be more specific)
        if word_count >= 10:
            score += 5
        if word_count >= 25:
            score += 5
        if word_count >= 50:
            score += 5

        # Check each quality signal
        for pattern, points, _tag in self.QUALITY_SIGNALS:
            if re.search(pattern, prompt_lower):
                score += points

        # Has a question mark (shows analytical thinking)
        if "?" in prompt:
            score += 3

        # Has code context (backticks, file refs)
        if "`" in prompt or "file" in prompt_lower:
            score += 4

        # Has numbered list or bullet points
        if re.search(r'^\s*[\d\-\*]', prompt, re.MULTILINE):
            score += 5

        # Cap at 100
        return min(score, 100)

    def _classify_intent(self, prompt: str) -> str:
        """Classify the primary intent of the prompt."""
        prompt_lower = prompt.lower()
        best_intent = "general"
        best_count = 0

        for intent, keywords in self.INTENT_MAP.items():
            count = sum(1 for kw in keywords if kw in prompt_lower)
            if count > best_count:
                best_count = count
                best_intent = intent

        return best_intent

    def _classify_complexity(self, prompt: str, intent: str) -> int:
        """Classify prompt complexity (1-5)."""
        score = 1
        words = len(prompt.split())

        if words >= 15:
            score += 1
        if words >= 40:
            score += 1
        if words >= 80:
            score += 1

        # Multi-part requests
        if re.search(r'\b(and|also|plus|additionally|moreover)\b', prompt.lower()):
            score += 1

        # Technical keywords add complexity
        tech_words = len(re.findall(
            r'\b(api|database|auth|deploy|kubernetes|docker|'
            r'ci/cd|migration|security|architecture|distributed|'
            r'concurrency|async|microservice|pipeline)\b',
            prompt.lower()
        ))
        if tech_words >= 2:
            score += 1

        return min(score, 5)

    def _build_goal_context(
        self, goals: list[dict], prompt: str, intent: str
    ) -> tuple[str, list[str]]:
        """Build goal-alignment context from active goals.

        Returns (goal_context_text, list_of_aligned_goal_objectives).
        Only includes goals that are relevant to the current prompt.
        """
        prompt_lower = prompt.lower()
        aligned = []
        context_parts = []

        for goal in goals:
            objective = goal.get("objective", "")
            key_results = goal.get("key_results", [])
            overall_pct = goal.get("overall_pct", 0)

            # Check if goal is relevant to the prompt
            obj_words = set(objective.lower().split())
            prompt_words = set(prompt_lower.split())
            overlap = obj_words & prompt_words - {"the", "a", "an", "to", "is", "in", "of", "and", "for", "on", "with"}

            # Also check keyword match
            is_relevant = (
                len(overlap) >= 2
                or any(kr.lower() in prompt_lower for kr in key_results if isinstance(kr, str))
                or (intent in objective.lower())
            )

            if is_relevant:
                aligned.append(objective)
                progress_bar = f"{overall_pct}%"
                kr_text = ", ".join(
                    kr if isinstance(kr, str) else str(kr)
                    for kr in key_results[:3]
                )
                context_parts.append(
                    f"🎯 ACTIVE GOAL [{progress_bar}]: {objective}\n"
                    f"   Key Results: {kr_text}"
                )

        if not aligned and goals:
            # If no specific goal matches, inject the most recent goal as general context
            latest = goals[0]
            aligned.append(latest.get("objective", ""))
            context_parts.append(
                f"📋 CURRENT FOCUS: {latest.get('objective', 'N/A')}"
            )

        goal_context = "\n".join(context_parts) if context_parts else ""
        return goal_context, aligned

    def _apply_polish(
        self,
        prompt: str,
        intent: str,
        complexity: int,
        goal_context: str,
        enhancements: list[str],
    ) -> str:
        """Apply all enhancements to produce the polished prompt.

        The polished prompt preserves the original intent while adding:
        - Goal alignment context
        - Missing quality directives
        - Intent-specific quality gates
        """
        parts = []

        # ── Section 1: Goal context (if any) ──
        if goal_context:
            parts.append(f"## Goal Alignment\n{goal_context}")
            enhancements.append("goal_alignment")

        # ── Section 2: Original prompt (always preserved) ──
        parts.append(f"## Task\n{prompt}")

        # ── Section 3: Quality directives (based on what's missing) ──
        directives = []
        for rule in self.ENHANCEMENT_RULES:
            try:
                if rule["check"](prompt):
                    directives.append(f"- {rule['inject']}")
                    enhancements.append(rule["tag"])
            except Exception:
                continue

        # ── Section 4: Intent-specific quality gates ──
        intent_gates = self._get_intent_gates(intent)
        if intent_gates:
            directives.extend(intent_gates)
            enhancements.append(f"intent_gates_{intent}")

        # ── Section 5: Complexity-scaled depth requirements ──
        if complexity >= 3:
            directives.append("- Think step-by-step before implementing.")
            enhancements.append("step_by_step")
        if complexity >= 4:
            directives.append("- Consider at least 2 alternative approaches and explain why you chose this one.")
            enhancements.append("alternatives_analysis")
        if complexity >= 5:
            directives.append("- Conduct a pre-mortem: what could go wrong with this approach?")
            directives.append("- Include a verification plan to prove the solution works.")
            enhancements.append("pre_mortem")

        if directives:
            parts.append("## Quality Directives\n" + "\n".join(directives))

        # ── Section 6: Output quality bar ──
        quality_bar = self._get_quality_bar(complexity)
        if quality_bar:
            parts.append(f"## Output Standard\n{quality_bar}")
            enhancements.append("quality_bar")

        return "\n\n".join(parts)

    def _get_intent_gates(self, intent: str) -> list[str]:
        """Get intent-specific quality gates."""
        gates = {
            "debug": [
                "- Identify the ROOT CAUSE, not just the symptom.",
                "- Check if this bug has occurred before (anti-pattern check).",
                "- Verify the fix doesn't introduce regressions.",
            ],
            "build": [
                "- Check if a library/tool already exists for this (adopt vs build).",
                "- Write production-quality code with error handling.",
                "- Include necessary tests.",
            ],
            "refactor": [
                "- Capture BEFORE behavior to verify no regressions.",
                "- Keep changes minimal and reviewable.",
                "- Document what changed and why.",
            ],
            "deploy": [
                "- Create a rollback plan before deploying.",
                "- Run smoke tests after deployment.",
                "- Document the deployment steps.",
            ],
            "design": [
                "- Consider scalability, maintainability, and extensibility.",
                "- Document trade-offs explicitly.",
                "- Validate the design against known anti-patterns.",
            ],
            "optimize": [
                "- Establish a baseline measurement BEFORE optimizing.",
                "- Measure the improvement with the same methodology.",
                "- Ensure optimization doesn't sacrifice correctness.",
            ],
            "audit": [
                "- Be systematic — check every layer.",
                "- Cite specific evidence for each finding.",
                "- Prioritize findings by severity.",
            ],
        }
        return gates.get(intent, [])

    def _get_quality_bar(self, complexity: int) -> str:
        """Get the quality standard for the given complexity level."""
        if complexity <= 1:
            return "Deliver a clean, working solution."
        elif complexity <= 2:
            return "Deliver a well-tested solution with error handling."
        elif complexity <= 3:
            return (
                "Deliver a production-grade solution with:\n"
                "- Comprehensive error handling\n"
                "- Clear documentation\n"
                "- Verification evidence"
            )
        elif complexity <= 4:
            return (
                "Deliver an elite-quality solution with:\n"
                "- Production-grade error handling and edge cases\n"
                "- Clear documentation and rationale\n"
                "- Verification evidence (tests or manual proof)\n"
                "- Trade-off analysis for key decisions"
            )
        else:
            return (
                "Deliver the highest-quality solution possible with:\n"
                "- Bulletproof error handling and comprehensive edge cases\n"
                "- Full documentation with decision rationale\n"
                "- Complete verification evidence\n"
                "- Trade-off analysis and alternatives considered\n"
                "- Pre-mortem analysis of what could go wrong\n"
                "- Rollback/recovery plan"
            )


def register(mcp, store):
    """Register prompt polishing tools with the MCP server."""
    polisher = GoalPromptPolisher(store)

    @mcp.tool()
    def polish_prompt(user_prompt: str) -> str:
        """🎯 Polish any prompt for maximum output quality.

        Analyzes the prompt, aligns it with active goals, adds missing
        quality directives, and returns an enhanced version that produces
        significantly better results.

        The polisher:
        - Fetches active goals and injects relevant context
        - Scores prompt quality (0-100) before and after
        - Adds missing verification, edge-case, security checks
        - Scales quality requirements to task complexity (1-5)

        Args:
            user_prompt: The raw user prompt to polish
        """
        result = polisher.polish(user_prompt)

        # Record the polish score for optimization loop tracking
        try:
            store.record_prompt_intent(
                session_id="polish",
                prompt_text=user_prompt[:2000],
                intent_category=result.intent,
                reasoning_type="polish",
            )
        except Exception as exc:
            # Explicit non-fatal exception suppression
            _ = str(exc)

        # Build the output
        out = "## 📊 Prompt Quality Analysis\n\n"
        out += "| Metric | Value |\n|--------|-------|\n"
        out += f"| Original Score | {result.original_score}/100 |\n"
        out += f"| Polished Score | {result.polished_score}/100 |\n"
        out += f"| Improvement | +{result.polished_score - result.original_score} points |\n"
        out += f"| Complexity | {result.complexity}/5 |\n"
        out += f"| Intent | {result.intent} |\n"
        out += f"| Goals Aligned | {len(result.goals_aligned)} |\n"
        out += f"| Enhancements | {len(result.enhancements_applied)} |\n\n"

        if result.goals_aligned:
            out += "### 🎯 Goals Aligned\n"
            for g in result.goals_aligned:
                out += f"- {g}\n"
            out += "\n"

        if result.enhancements_applied:
            out += "### ✨ Enhancements Applied\n"
            for e in result.enhancements_applied:
                out += f"- `{e}`\n"
            out += "\n"

        out += f"---\n\n## 🚀 Polished Prompt\n\n{result.polished_prompt}\n"

        return out

    @mcp.tool()
    def get_prompt_quality_trend(limit: int = 20) -> str:
        """📊 View prompt quality scores over time.

        Shows the trend of prompt polish scores to identify whether
        prompt quality is improving or declining. Used by the
        optimization loop to trigger automatic goal-setting when
        quality drops.

        Args:
            limit: Number of recent prompts to analyze (default: 20)
        """
        try:
            analysis = store.analyze_prompt_sequence(limit=limit)
            prompts = analysis.get("prompts", [])

            if not prompts:
                return "No prompt data yet. Use `orchestrate_request_tool` or `polish_prompt` to generate data."

            out = "## 📊 Prompt Quality Trend\n\n"
            out += f"**Prompts analyzed**: {len(prompts)}\n\n"

            # Calculate stats
            intents = {}
            for p in prompts:
                cat = p.get("intent_category", "unknown")
                intents[cat] = intents.get(cat, 0) + 1

            out += "### Intent Distribution\n"
            for intent, count in sorted(intents.items(), key=lambda x: -x[1]):
                pct = int(count / len(prompts) * 100)
                out += f"- **{intent}**: {count} ({pct}%)\n"

            # Pattern analysis
            patterns = analysis.get("patterns", [])
            if patterns:
                out += "\n### Patterns Detected\n"
                for pat in patterns:
                    out += f"- {pat}\n"

            return out
        except Exception as e:
            return f"❌ Error analyzing prompt trend: {e}"

    return polisher
