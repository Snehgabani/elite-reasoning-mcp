"""
Reasoning Amplification Tools — The active quality layer.

Unlike recording/template tools (which PASSIVELY document),
these tools ACTIVELY improve reasoning quality in-flight:

1. assess_confidence: Self-critique → confidence score → trigger deeper analysis if low
2. socratic_challenge: Generate adversarial counter-questions → force model to defend answer
3. decompose_with_steps: Structured step-by-step decomposition (wraps sequential-thinking concepts)
"""
import time
import json
from core.memory.persistent_store import EliteStore
from core.logging_config import get_logger

logger = get_logger(__name__)


def register(mcp, store: EliteStore):
    """Register reasoning amplification tools on the MCP server."""

    @mcp.tool()
    def assess_confidence(
        claim: str,
        evidence: str = "",
        alternatives_considered: str = "",
        domain: str = "general",
    ) -> str:
        """
        TRIGGER: Call this BEFORE delivering any important answer, recommendation,
        or architectural decision to the user.

        🎯 Confidence Scorer — Self-critique framework that forces structured
        evaluation of answer quality. Returns a 0-100 confidence score with
        specific uncertainty flags.

        If confidence < 60%, the system recommends deeper analysis via
        sequential thinking or socratic challenge.

        Args:
            claim: The proposed answer, recommendation, or decision
            evidence: Supporting evidence or reasoning (what makes you believe this?)
            alternatives_considered: Other options that were rejected (and why)
            domain: The domain of expertise (code, architecture, security, performance, general)
        """
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

        # ── Structured self-critique scoring ──
        score_components = {}
        flags = []

        # 1. Evidence quality (0-25)
        evidence_text = (evidence or "").strip()
        if not evidence_text:
            score_components["evidence_quality"] = 5
            flags.append("🔴 NO EVIDENCE PROVIDED — answer may be based on assumption")
        elif len(evidence_text) < 50:
            score_components["evidence_quality"] = 10
            flags.append("🟡 Thin evidence — consider adding specific examples or data")
        elif len(evidence_text) < 200:
            score_components["evidence_quality"] = 18
        else:
            score_components["evidence_quality"] = 25

        # 2. Alternatives considered (0-25)
        alts_text = (alternatives_considered or "").strip()
        if not alts_text:
            score_components["alternatives"] = 5
            flags.append("🔴 NO ALTERNATIVES CONSIDERED — high risk of anchoring bias")
        elif len(alts_text.split(",")) < 2 and len(alts_text.split("\n")) < 2:
            score_components["alternatives"] = 12
            flags.append("🟡 Only 1 alternative considered — risk of confirmation bias")
        else:
            score_components["alternatives"] = 25

        # 3. Domain specificity (0-25)
        valid_domains = {"code", "architecture", "security", "performance", "general",
                        "database", "api", "deployment", "testing"}
        if domain.lower() in valid_domains and domain.lower() != "general":
            score_components["domain_specificity"] = 25
        elif domain.lower() == "general":
            score_components["domain_specificity"] = 15
            flags.append("🟡 Generic domain — consider specifying (code, architecture, security, etc.)")
        else:
            score_components["domain_specificity"] = 10
            flags.append(f"⚠️ Unknown domain '{domain}' — confidence may be miscalibrated")

        # 4. Claim clarity (0-25)
        claim_text = (claim or "").strip()
        if not claim_text:
            score_components["claim_clarity"] = 0
            flags.append("🔴 EMPTY CLAIM — nothing to evaluate")
        elif len(claim_text) < 20:
            score_components["claim_clarity"] = 10
            flags.append("🟡 Very short claim — may be oversimplified")
        elif "?" in claim_text:
            score_components["claim_clarity"] = 15
            flags.append("🟡 Claim contains questions — is this a question or an answer?")
        else:
            score_components["claim_clarity"] = 25

        # ── Cross-check against anti-patterns ──
        try:
            relevant = store.check_anti_patterns(claim_text[:200], limit=3)
            if relevant:
                score_components["anti_pattern_check"] = -10
                for m in relevant[:2]:
                    flags.append(
                        f"⚠️ RELATED PAST MISTAKE: {m['mistake'][:80]}… → Fix: {m['fix'][:80]}…"
                    )
        except Exception:
            pass  # Don't let anti-pattern check failure block scoring

        # ── Calculate total ──
        total = max(0, min(100, sum(score_components.values())))

        # ── Determine verdict ──
        if total >= 80:
            verdict = "🟢 HIGH CONFIDENCE — Proceed with delivery"
            recommendation = "Deliver as-is. Consider recording the decision for audit trail."
        elif total >= 60:
            verdict = "🟡 MODERATE CONFIDENCE — Acceptable but verify"
            recommendation = "Proceed but flag uncertainties to the user. Consider using `socratic_challenge` for stress-testing."
        elif total >= 40:
            verdict = "🟠 LOW CONFIDENCE — Deeper analysis recommended"
            recommendation = "Use `socratic_challenge` to stress-test. Consider `sequentialthinking` for step-by-step decomposition before delivering."
        else:
            verdict = "🔴 VERY LOW CONFIDENCE — Do NOT deliver without more work"
            recommendation = "STOP. Use `sequentialthinking` to decompose the problem from scratch. Gather more evidence. Consider `fmea_analysis` to enumerate what could go wrong."

        # ── Record quality score ──
        try:
            store.record_quality_score(
                score=total,
                dimension="confidence",
                notes=f"Domain: {domain} | Flags: {len(flags)} | Claim: {claim_text[:100]}"
            )
        except Exception:
            pass

        # ── Format output ──
        out = f"""╔══════════════════════════════════════════════╗
║        🎯 CONFIDENCE ASSESSMENT              ║
╚══════════════════════════════════════════════╝

**Claim**: {claim_text[:200]}
**Domain**: {domain}
**Timestamp**: {now}

## Score Breakdown

| Component | Score |
|---|---|
| Evidence Quality | {score_components.get('evidence_quality', 0)}/25 |
| Alternatives Considered | {score_components.get('alternatives', 0)}/25 |
| Domain Specificity | {score_components.get('domain_specificity', 0)}/25 |
| Claim Clarity | {score_components.get('claim_clarity', 0)}/25 |
{f'| Anti-Pattern Penalty | {score_components.get("anti_pattern_check", 0)} |' if 'anti_pattern_check' in score_components else ''}

## **TOTAL: {total}/100**
## **{verdict}**

"""
        if flags:
            out += "## ⚡ Flags\n\n"
            for f in flags:
                out += f"- {f}\n"
            out += "\n"

        out += f"## 💡 Recommendation\n\n{recommendation}\n"

        return out

    @mcp.tool()
    def socratic_challenge(
        proposed_answer: str,
        context: str = "",
        challenge_depth: int = 3,
    ) -> str:
        """
        TRIGGER: Call this when confidence score is < 80%, when making
        architectural decisions, or when the user asks to "stress test" an answer.

        🏛️ Socratic Challenger — Generates adversarial counter-questions
        that force the model to defend, revise, or strengthen its answer.

        This is the single most effective technique for making ANY model
        (even weak/open-source) produce better answers. It turns a single-pass
        response into a multi-pass stress-tested response.

        Args:
            proposed_answer: The answer/plan/recommendation to challenge
            context: Additional context about the problem being solved
            challenge_depth: Number of adversarial questions (1-5, default 3)
        """
        depth = max(1, min(5, challenge_depth))
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        answer_text = (proposed_answer or "").strip()

        if not answer_text:
            return "❌ No proposed answer provided. Cannot challenge empty claims."

        # ── Generate structured challenges based on universal failure modes ──
        challenge_templates = [
            {
                "category": "🔴 Failure Mode",
                "question": f"What is the SINGLE most likely way this fails catastrophically?\n\n   Proposed: {answer_text[:200]}…\n\n   Specifically: What assumption does this make that could be wrong? What happens when it IS wrong?",
                "why": "Forces enumeration of failure modes BEFORE they happen (proactive FMEA)"
            },
            {
                "category": "🟠 Alternative",
                "question": f"Why is this the BEST approach, not just A working approach?\n\n   Proposed: {answer_text[:200]}…\n\n   Name a specific alternative that was rejected and explain WHY this is strictly better.",
                "why": "Guards against anchoring bias — the first solution isn't always the best"
            },
            {
                "category": "🟡 Hidden Dependency",
                "question": f"What does this SILENTLY depend on that isn't explicitly stated?\n\n   Proposed: {answer_text[:200]}…\n\n   List every implicit assumption: environment, data, permissions, timing, state.",
                "why": "Most production failures come from unstated dependencies, not bugs in stated logic"
            },
            {
                "category": "🔵 Scale / Edge Case",
                "question": f"Does this still work at 10x the current scale? What about edge cases?\n\n   Proposed: {answer_text[:200]}…\n\n   What happens with: empty input, huge input, concurrent access, network failure, partial failure?",
                "why": "Demo-quality solutions often fail at production scale"
            },
            {
                "category": "🟣 Second-Order Effects",
                "question": f"What SECOND-ORDER consequences does this create?\n\n   Proposed: {answer_text[:200]}…\n\n   What does this make harder in the future? What doors does it close? What maintenance burden does it add?",
                "why": "First-order benefits often hide second-order costs (technical debt, lock-in, complexity)"
            },
        ]

        # Select challenges based on depth
        selected = challenge_templates[:depth]

        # ── Cross-reference against known anti-patterns ──
        anti_pattern_context = ""
        try:
            relevant = store.check_anti_patterns(answer_text[:200], limit=2)
            if relevant:
                anti_pattern_context = "\n\n## ⚠️ Related Past Mistakes\n\n"
                for m in relevant:
                    anti_pattern_context += (
                        f"- **{m['mistake'][:100]}**\n"
                        f"  Root cause: {m['root_cause'][:100]}\n"
                        f"  Fix: {m['fix'][:100]}\n\n"
                    )
        except Exception:
            pass

        # ── Format output ──
        out = f"""╔══════════════════════════════════════════════╗
║     🏛️ SOCRATIC CHALLENGE ({depth} questions)     ║
╚══════════════════════════════════════════════╝

**Proposed Answer**: {answer_text[:300]}…
**Context**: {(context or 'None provided')[:200]}
**Timestamp**: {now}

---

## You MUST answer each challenge below before delivering your response.

"""
        for i, ch in enumerate(selected, 1):
            out += f"""### Challenge {i}: {ch['category']}

**{ch['question']}**

_Why this matters: {ch['why']}_

**Your response**: _(fill this in before delivering)_

---

"""

        out += anti_pattern_context

        out += """
## 📋 After answering all challenges:

1. If ANY challenge revealed a flaw → **REVISE** your original answer
2. If ALL challenges were satisfactorily answered → **DELIVER** with increased confidence
3. Run `assess_confidence` on the revised answer to verify improvement

"""

        # ── Record quality event ──
        try:
            store.record_quality_score(
                score=50,  # Midpoint — will be updated by confidence scorer after revision
                dimension="reasoning_depth",
                notes=f"Socratic challenge initiated | Depth: {depth} | Answer: {answer_text[:100]}"
            )
        except Exception:
            pass

        return out

    @mcp.tool()
    def reasoning_preflight(
        task_description: str,
        intent: str = "",
        complexity: int = 0,
    ) -> str:
        """
        TRIGGER: Called AUTOMATICALLY by the orchestration interceptor before
        complex tasks. Can also be called manually.

        🛫 Reasoning Pre-Flight — Determines what reasoning tools should be
        activated based on task complexity and intent. Returns a checklist
        of tools to invoke before execution.

        Args:
            task_description: What the user wants to do
            intent: Classified intent (build, debug, audit, deploy, etc.)
            complexity: Pre-computed complexity score (1-5), or 0 for auto-detect
        """
        desc = (task_description or "").strip()
        if not desc:
            return "❌ No task description. Cannot compute pre-flight."

        # ── Auto-detect complexity if not provided ──
        if complexity <= 0:
            complexity = _compute_complexity(desc, intent)

        # ── Build pre-flight checklist based on complexity + intent ──
        checklist = []
        tools_to_invoke = []

        if complexity >= 2:
            checklist.append("✅ Record intent and reasoning type")

        if complexity >= 3:
            checklist.append("📝 Use `sequentialthinking` to decompose into steps")
            tools_to_invoke.append("sequentialthinking")
            checklist.append("📚 Use `context7/query-docs` to ground in current documentation")

        if complexity >= 4:
            if intent in ("build", "improve"):
                checklist.append("🔍 Run `fmea_analysis` — what can fail?")
                tools_to_invoke.append("fmea_analysis")
                checklist.append("🧠 Run `bias_scan` — am I anchored on the wrong approach?")
                tools_to_invoke.append("bias_scan")
            if intent == "deploy":
                checklist.append("🚦 Create `smoke_test_gate` — measurable before state")
                tools_to_invoke.append("smoke_test_gate")
                checklist.append("🔮 Run `simulate_future_regrets` — what could go wrong?")
                tools_to_invoke.append("simulate_future_regrets")
            if intent in ("debug", "investigate"):
                checklist.append("❓ Run `five_whys` — drill to root cause")
                tools_to_invoke.append("five_whys")
            if intent == "audit":
                checklist.append("🧀 Run `swiss_cheese_audit` — are defenses layered?")
                tools_to_invoke.append("swiss_cheese_audit")
                checklist.append("🧠 Run `bias_scan` — am I missing something?")
                tools_to_invoke.append("bias_scan")

        if complexity >= 5:
            checklist.append("🏛️ MANDATORY: Run `socratic_challenge` on the plan before executing")
            tools_to_invoke.append("socratic_challenge")
            checklist.append("🎯 MANDATORY: Run `assess_confidence` on the final deliverable")
            tools_to_invoke.append("assess_confidence")
            checklist.append("📋 MANDATORY: After completion, run `after_action_review`")
            tools_to_invoke.append("after_action_review")

        # ── Check anti-patterns for the task ──
        anti_pattern_warnings = []
        try:
            relevant = store.check_anti_patterns(desc[:200], limit=3)
            for m in relevant:
                anti_pattern_warnings.append(
                    f"⚠️ RELATED PAST MISTAKE: {m['mistake'][:80]}… → Fix: {m['fix'][:80]}"
                )
        except Exception:
            pass

        # ── Format output ──
        complexity_labels = {
            1: "Trivial (direct execution)",
            2: "Simple (basic tools only)",
            3: "Moderate (decomposition + grounding)",
            4: "Complex (full pre-flight: FMEA + bias scan + future regrets)",
            5: "Critical (everything: decomposition + review + gates + confidence)",
        }

        out = f"""╔══════════════════════════════════════════════╗
║          🛫 REASONING PRE-FLIGHT              ║
╚══════════════════════════════════════════════╝

**Task**: {desc[:300]}
**Intent**: {intent or 'auto'}
**Complexity**: {complexity}/5 — {complexity_labels.get(complexity, 'Unknown')}

## Pre-Flight Checklist

"""
        if complexity <= 1:
            out += "✅ **CLEAR FOR DIRECT EXECUTION** — No pre-flight needed for trivial tasks.\n"
        else:
            for item in checklist:
                out += f"- [ ] {item}\n"

        if anti_pattern_warnings:
            out += "\n## ⚠️ Past Mistakes Related to This Task\n\n"
            for w in anti_pattern_warnings:
                out += f"- {w}\n"

        if tools_to_invoke:
            out += f"\n## 🔧 Tools to Invoke\n\n`{'`, `'.join(tools_to_invoke)}`\n"

        return out

    # Register hidden store tools (P1)
    _register_hidden_tools(mcp, store)

    # ══════════════════════════════════════════════════════════
    # P3: CALIBRATION SCORING
    # ══════════════════════════════════════════════════════════

    @mcp.tool()
    def calibration_predict(
        claim: str,
        confidence: float,
        domain: str = "general",
    ) -> str:
        """
        TRIGGER: Call this AFTER assess_confidence when you make a prediction
        or recommendation. Logs the confidence level so it can be compared
        against actual outcomes later for Brier score calibration.

        Args:
            claim: The specific prediction or recommendation
            confidence: Your confidence as 0.0-1.0 (e.g., 0.85 = 85% confident)
            domain: Domain category (code, architecture, security, performance, general)
        """
        import hashlib
        pred_id = hashlib.sha256(
            f"{claim}:{time.strftime('%Y-%m-%d %H:%M', time.gmtime())}".encode()
        ).hexdigest()[:16]

        store.log_calibration(pred_id, claim, confidence, domain)

        return (
            f"## 📊 Calibration Prediction Logged\n\n"
            f"**Prediction ID:** `{pred_id}`\n"
            f"**Claim:** {claim[:200]}\n"
            f"**Confidence:** {confidence*100:.0f}%\n"
            f"**Domain:** {domain}\n\n"
            f"*Save this prediction ID. When the outcome is known, call "
            f"`calibration_resolve` with this ID to track accuracy.*"
        )

    @mcp.tool()
    def calibration_resolve(
        prediction_id: str,
        outcome: str,
        correct: bool,
    ) -> str:
        """
        Resolve a calibration prediction with the actual outcome.
        This feeds the Brier score calculation.

        Args:
            prediction_id: The prediction ID from calibration_predict
            outcome: What actually happened
            correct: Was the prediction correct? True/False
        """
        updated = store.resolve_calibration(prediction_id, outcome, correct)
        if not updated:
            return f"⚠️ No unresolved prediction found with ID `{prediction_id}`"

        return (
            f"## ✅ Calibration Resolved\n\n"
            f"**Prediction ID:** `{prediction_id}`\n"
            f"**Outcome:** {outcome}\n"
            f"**Correct:** {'Yes ✅' if correct else 'No ❌'}\n\n"
            f"*Run `calibration_score` to see updated Brier score.*"
        )

    @mcp.tool()
    def calibration_score(
        domain: str = "",
        days: int = 30,
    ) -> str:
        """
        Get the calibration report — Brier score, accuracy, and
        confidence-vs-outcome breakdown. Lower Brier score = better calibrated.

        Perfect calibration: Brier = 0.0
        Random guessing: Brier = 0.25
        Always wrong at 100%: Brier = 1.0

        Args:
            domain: Filter by domain (empty = all domains)
            days: Look back period in days
        """
        result = store.get_calibration_score(
            domain=domain if domain else None,
            days=max(1, days)
        )

        if result.get("total_predictions", 0) == 0:
            return (
                "## 📊 Calibration Score\n\n"
                "No resolved predictions yet. Use `calibration_predict` to log "
                "predictions and `calibration_resolve` to mark outcomes."
            )

        lines = [
            "## 📊 Calibration Score\n",
            f"**Brier Score:** {result['brier_score']} "
            f"({'🟢 Good' if result['brier_score'] < 0.15 else '🟡 Fair' if result['brier_score'] < 0.25 else '🔴 Poor'})",
            f"**Status:** {result['calibration_status'].upper()}",
            f"**Total Predictions:** {result['total_predictions']}",
            f"**Accuracy:** {result['accuracy']*100:.1f}%",
            f"**Avg Confidence:** {result['avg_confidence']*100:.1f}%",
            "",
            "### Calibration Table",
            "| Bucket | Count | Expected | Actual | Gap |",
            "|--------|-------|----------|--------|-----|",
        ]
        for b in result.get("calibration_table", []):
            lines.append(
                f"| {b['bucket']} | {b['count']} | {b['expected']} | "
                f"{b['actual']} | {b['gap']} |"
            )

        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════
    # P3: DECISION COUNCIL (Multi-Perspective Adversarial Review)
    # ══════════════════════════════════════════════════════════

    COUNCIL_PERSPECTIVES = [
        {"name": "Security Adversary", "lens": "Attack vectors, data exposure, permission scope",
         "focus": ["injection", "auth", "permission", "token", "secret", "credential", "bypass"]},
        {"name": "Scalability Critic", "lens": "Bottlenecks at 10x/100x, O(n²) hiding, resource limits",
         "focus": ["query", "loop", "memory", "connection", "lock", "timeout", "unbounded"]},
        {"name": "Simplicity Advocate", "lens": "Over-engineering, maintenance cost, simpler alternatives",
         "focus": ["abstraction", "pattern", "layer", "framework", "complex", "wrapper"]},
        {"name": "User Impact Analyst", "lens": "Breaking changes, UX regression, migration path",
         "focus": ["breaking", "migration", "backward", "deprecat", "rename", "remove"]},
        {"name": "Future Self Reviewer", "lens": "6-month regret, assumption fragility, reversal cost",
         "focus": ["lock-in", "vendor", "irreversible", "assumption", "debt", "coupling"]},
    ]

    @mcp.tool()
    def decision_council_review(
        decision: str,
        context: str = "",
        complexity: int = 3,
    ) -> str:
        """
        TRIGGER: Call this for any HIGH-STAKES decision (architecture, security,
        data model, deployment strategy). Runs the decision through 5 adversarial
        perspectives that challenge it from different angles.

        Args:
            decision: The decision or plan to review
            context: Additional context (codebase, constraints, requirements)
            complexity: Complexity level 1-5 (higher = more perspectives activated)
        """
        num_perspectives = min(5, max(2, complexity))
        active = COUNCIL_PERSPECTIVES[:num_perspectives]

        reviews = []
        all_flags = []
        decision_lower = (decision + ' ' + context).lower()

        for p in active:
            matches = [f for f in p["focus"] if f in decision_lower]
            if matches:
                critique = (f"**{p['name']}** flags: {', '.join(matches)}. "
                            f"Review: {p['lens']}")
                risk = min(1.0, 0.3 + len(matches) * 0.15)
            else:
                critique = (f"**{p['name']}** — no immediate flags. "
                            f"Still review: {p['lens']}")
                risk = 0.2

            flags = [f"{p['name']}: {f}" for f in matches]
            all_flags.extend(flags)

            store.add_council_review(
                decision_id=0, decision_text=decision,
                perspective=p["name"], critique=critique,
                risk_flags=flags,
                recommendation="caution" if matches else "proceed",
                confidence=1.0 - risk
            )
            reviews.append({"name": p["name"], "critique": critique,
                            "flags": flags, "risk": risk})

        avg_risk = sum(r["risk"] for r in reviews) / len(reviews)
        verdict = ("🔴 HIGH RISK" if avg_risk > 0.6 else
                   "🟡 MODERATE RISK" if avg_risk > 0.35 else "🟢 LOW RISK")

        lines = [
            "## 🏛️ Decision Council Review\n",
            f"**Decision:** {decision[:200]}",
            f"**Verdict:** {verdict} (risk: {avg_risk:.2f})",
            f"**Perspectives:** {len(reviews)}\n",
        ]
        for r in reviews:
            e = "🔴" if r["risk"] > 0.5 else "🟡" if r["risk"] > 0.3 else "🟢"
            lines.append(f"### {e} {r['name']}")
            lines.append(r["critique"])
            if r["flags"]:
                lines.append(f"*Flags: {', '.join(r['flags'])}*")
            lines.append("")

        if all_flags:
            lines.append("### All Risk Flags")
            for f in all_flags:
                lines.append(f"- ⚠️ {f}")

        return "\n".join(lines)

    logger.info("Reasoning amplification tools registered",
                extra={"tools": ["assess_confidence", "socratic_challenge", "reasoning_preflight",
                                  "record_missed_detection", "browse_tool_usage", "search_thinking_patterns",
                                  "calibration_predict", "calibration_resolve", "calibration_score",
                                  "decision_council_review"]})


def _compute_complexity(task: str, intent: str) -> int:
    """
    Compute task complexity on a 1-5 scale based on task description and intent.
    Uses keyword signals, length heuristics, and intent category.
    """
    t = task.lower()
    score = 1  # Start at trivial

    # Length-based: longer descriptions = more complex
    if len(t) > 500:
        score += 2
    elif len(t) > 200:
        score += 1

    # Intent-based escalation
    high_complexity_intents = {"deploy", "audit"}
    medium_complexity_intents = {"build", "improve", "debug"}
    if intent in high_complexity_intents:
        score += 2
    elif intent in medium_complexity_intents:
        score += 1

    # Keyword escalation signals
    critical_kws = [
        "production", "security", "authentication", "migration",
        "database schema", "breaking change", "backwards compat",
        "scale", "concurrent", "distributed", "microservice",
    ]
    moderate_kws = [
        "refactor", "redesign", "architecture", "integrate",
        "api design", "data model", "performance", "optimize",
        "end to end", "full stack", "comprehensive",
    ]
    trivial_kws = [
        "typo", "rename", "comment", "format", "lint",
        "simple", "quick", "minor", "small fix",
    ]

    # Check critical keywords
    for kw in critical_kws:
        if kw in t:
            score += 2
            break  # One critical keyword is enough

    # Check moderate keywords
    for kw in moderate_kws:
        if kw in t:
            score += 1
            break

    # Trivial keyword dampening
    for kw in trivial_kws:
        if kw in t:
            score = max(1, score - 2)
            break

    return min(5, max(1, score))


# ── P1: Thinking Mode Classifier ──────────────────────────────

def _classify_thinking_mode(prompt: str) -> str:
    """Classify the cognitive mode required for this task.
    Returns one of: convergent, divergent, analytical, critical, systems, creative."""
    p = prompt.lower()

    modes = {
        'convergent': ['fix', 'choose', 'pick', 'select', 'decide between', 'which one',
                        'solve', 'correct', 'resolve', 'answer'],
        'divergent': ['brainstorm', 'explore', 'what if', 'ideas', 'possibilities',
                       'imagine', 'alternatives', 'creative', 'innovate'],
        'analytical': ['analyze', 'audit', 'benchmark', 'measure', 'statistics',
                        'data', 'metrics', 'quantify', 'profile', 'diagnose'],
        'critical': ['review', 'stress-test', 'verify', 'validate', 'challenge',
                      'critique', 'weakness', 'flaw', 'risk', 'security'],
        'systems': ['architecture', 'design system', 'scale', 'distributed',
                     'end to end', 'pipeline', 'integration', 'infrastructure'],
        'creative': ['design', 'ui', 'ux', 'visual', 'brand', 'aesthetic',
                      'landing page', 'mockup', 'prototype'],
    }

    scores = {mode: 0 for mode in modes}
    for mode, keywords in modes.items():
        for kw in keywords:
            if kw in p:
                scores[mode] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'convergent'  # default


def _classify_zoom_level(prompt: str) -> str:
    """Classify the zoom level: satellite, architecture, module, function, line.
    Determines how much detail the response should provide."""
    p = prompt.lower()

    levels = {
        'satellite': ['overview', 'strategy', 'vision', 'roadmap', 'big picture',
                        'high level', 'macro', 'direction', 'goals'],
        'architecture': ['system design', 'architecture', 'component', 'service',
                          'module layout', 'data flow', 'infrastructure'],
        'module': ['module', 'class', 'package', 'feature', 'component',
                    'service', 'controller', 'middleware'],
        'function': ['function', 'method', 'implement', 'algorithm', 'logic',
                      'handler', 'endpoint', 'callback'],
        'line': ['fix line', 'typo', 'rename', 'format', 'lint', 'indent',
                  'spacing', 'syntax', 'comma', 'semicolon'],
    }

    # Check from most zoomed-in to most zoomed-out
    for level in ['line', 'function', 'module', 'architecture', 'satellite']:
        for kw in levels[level]:
            if kw in p:
                return level
    return 'function'  # default


# ── P1: Expose Hidden Store Methods as MCP Tools ──────────────

def _register_hidden_tools(mcp, store):
    """Register tools for store methods that had no MCP exposure."""

    @mcp.tool()
    def record_missed_detection(
        detection_type: str,
        what_was_missed: str,
        how_found: str = "",
        suggested_rule: str = "",
    ) -> str:
        """Record something the system missed detecting — feeds the autonomous improvement loop.

        Args:
            detection_type: Category of what was missed (e.g., 'security_flaw', 'performance_bug', 'anti_pattern')
            what_was_missed: Description of what should have been caught
            how_found: How it was eventually discovered
            suggested_rule: Optional suggestion for a prevention rule
        """
        try:
            store.record_missed_detection(detection_type, what_was_missed, how_found, suggested_rule)
            return (
                f"✅ Missed detection recorded: {detection_type}\n"
                f"What was missed: {what_was_missed}\n"
                f"This will be used to improve autonomous scanning."
            )
        except Exception as e:
            return f"❌ Failed to record: {e}"

    @mcp.tool()
    def browse_tool_usage(days: int = 7, tool_name: str = "") -> str:
        """Browse detailed tool usage logs — see when and how tools were used.

        Args:
            days: Number of days to look back (1-30)
            tool_name: Optional filter for a specific tool name
        """
        import time as _t
        try:
            days = max(1, min(30, days))
            conn = store._connect()
            c = conn.cursor()
            cutoff = _t.strftime("%Y-%m-%d %H:%M:%S",
                                  _t.gmtime(_t.time() - days * 86400))
            if tool_name:
                c.execute(
                    "SELECT tool_name, args_summary, result_summary, duration_ms, created_at "
                    "FROM tool_usage_log WHERE created_at > ? AND tool_name = ? "
                    "ORDER BY created_at DESC LIMIT 50",
                    (cutoff, tool_name)
                )
            else:
                c.execute(
                    "SELECT tool_name, args_summary, result_summary, duration_ms, created_at "
                    "FROM tool_usage_log WHERE created_at > ? "
                    "ORDER BY created_at DESC LIMIT 50",
                    (cutoff,)
                )
            rows = c.fetchall()
            store._close(conn)

            if not rows:
                return f"No tool usage in the last {days} days" + (f" for '{tool_name}'" if tool_name else "") + "."

            out = f"## Tool Usage Log ({len(rows)} entries, last {days} days)\n\n"
            out += "| Tool | Duration | Time | Args |\n|---|---|---|---|\n"
            for r in rows:
                out += f"| `{r[0]}` | {r[3] or 0}ms | {r[4]} | {(r[1] or '')[:60]} |\n"
            return out
        except Exception as e:
            return f"❌ Failed to browse: {e}"

    @mcp.tool()
    def search_thinking_patterns(pattern_name: str = "") -> str:
        """Search and display user thinking patterns learned over time.

        Args:
            pattern_name: Optional filter — search for a specific pattern by name
        """
        try:
            patterns = store.get_user_thinking_model()
            if not patterns:
                return "No thinking patterns recorded yet."

            if pattern_name:
                patterns = [p for p in patterns if pattern_name.lower() in p.get('pattern_name', '').lower()]

            if not patterns:
                return f"No patterns matching '{pattern_name}'."

            out = f"## User Thinking Patterns ({len(patterns)} found)\n\n"
            for p in patterns:
                out += f"### {p.get('pattern_name', 'Unknown')}\n"
                out += f"- **System adaptation:** {p.get('system_adaptation', 'none')}\n"
                out += f"- **Confidence:** {p.get('confidence', 0):.0%}\n"
                out += f"- **Occurrences:** {p.get('occurrence_count', 0)}\n\n"
            return out
        except Exception as e:
            return f"❌ Failed to search: {e}"


# ── P2: Contradiction Detector ────────────────────────────────

def _check_decision_contradictions(store, new_decision: str) -> list[str]:
    """Check if a new decision contradicts existing ones using semantic search.
    Returns list of warning strings if contradictions are found."""
    warnings = []
    try:
        # Search for similar past decisions
        similar = store.search_decisions(new_decision, limit=5)
        if not similar:
            return warnings

        # Check for potential contradictions
        new_lower = new_decision.lower()
        contradiction_signals = [
            ('use ', 'don\'t use '), ('adopt ', 'avoid '),
            ('enable', 'disable'), ('add ', 'remove '),
            ('postgresql', 'mongodb'), ('postgresql', 'mysql'),
            ('mongodb', 'sql'), ('rest', 'graphql'),
            ('monolith', 'microservice'), ('sync', 'async'),
        ]

        for past in similar:
            past_text = (past.get('decision', '') + ' ' + past.get('rationale', '')).lower()
            similarity = past.get('score', 0)

            # High similarity but opposite conclusions = contradiction
            if similarity > 0.6:
                for pos, neg in contradiction_signals:
                    if (pos in new_lower and neg in past_text) or \
                       (neg in new_lower and pos in past_text):
                        warnings.append(
                            f"⚠️ POTENTIAL CONTRADICTION with Decision #{past.get('id', '?')}:\n"
                            f"   Past: {past['decision'][:100]}\n"
                            f"   New:  {new_decision[:100]}\n"
                            f"   Similarity: {similarity:.0%}"
                        )
                        break
    except Exception:
        pass  # Never block decision recording
    return warnings


# ── P2: Mistake Taxonomy Classifier ───────────────────────────

MISTAKE_TAXONOMY = {
    'knowledge_gap': ['didn\'t know', 'unaware', 'new to', 'first time', 'unfamiliar'],
    'assumption_failure': ['assumed', 'expected', 'thought it would', 'turned out'],
    'edge_case_blindness': ['edge case', 'boundary', 'null', 'empty', 'zero', 'overflow'],
    'premature_commitment': ['too early', 'premature', 'should have waited', 'rushed'],
    'wrong_abstraction': ['abstraction', 'over-engineered', 'wrong pattern', 'wrong level'],
    'scope_creep': ['scope', 'grew', 'bloated', 'too much', 'feature creep'],
    'optimization_trap': ['premature optimization', 'unnecessary optimization', 'over-optimized'],
    'cargo_culting': ['cargo cult', 'copied', 'blindly', 'without understanding'],
    'recency_anchoring': ['latest', 'trending', 'hype', 'shiny', 'new framework'],
    'complexity_creep': ['too complex', 'over-complicated', 'simpler', 'unnecessary complexity'],
    'security_amnesia': ['security', 'vulnerability', 'injection', 'auth', 'permission'],
    'data_integrity': ['data loss', 'corruption', 'inconsistent', 'race condition', 'concurrency'],
}


def _classify_mistake_type(mistake: str, root_cause: str) -> str:
    """Auto-classify a mistake into one of 12 taxonomy categories."""
    text = (mistake + ' ' + root_cause).lower()
    scores = {cat: 0 for cat in MISTAKE_TAXONOMY}
    for cat, keywords in MISTAKE_TAXONOMY.items():
        for kw in keywords:
            if kw in text:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'knowledge_gap'  # default
