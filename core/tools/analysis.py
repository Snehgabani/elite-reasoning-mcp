def register(mcp, store, orchestrator=None):
    @mcp.tool()
    def five_whys(symptom: str) -> str:
        """TRIGGER: Call this immediately when a bug is discovered. DO NOT fix the symptom until you call this.
            🔍 5 Whys Root Cause Analysis — Drill past symptoms to the systemic cause.
            Args:
                symptom: The visible problem or symptom to investigate
            """
        return f'## 🔍 Five Whys Root Cause Analysis\n### Symptom: {symptom}\n\nDrill down. Each "Why" must target the PREVIOUS answer, not the original symptom.\n\n| Level | Question | Answer | Evidence |\n|---|---|---|---|\n| **Why 1** | Why does [{symptom}] happen? | _answer_ | _data/logs/code_ |\n| **Why 2** | Why does [answer 1] happen? | _answer_ | _evidence_ |\n| **Why 3** | Why does [answer 2] happen? | _answer_ | _evidence_ |\n| **Why 4** | Why does [answer 3] happen? | _answer_ | _evidence_ |\n| **Why 5** | Why does [answer 4] happen? | **ROOT CAUSE** | _evidence_ |\n\n### Root Cause Classification\n- [ ] **Code defect** (fix the code)\n- [ ] **Missing test** (add test coverage)\n- [ ] **Process gap** (add checklist/gate)\n- [ ] **Design flaw** (architectural change needed)\n- [ ] **Knowledge gap** (training/documentation)\n\n### Systemic Fix\nThe fix should target the ROOT CAUSE (Why 5), not the symptom.\n- Immediate fix: _what to do now_\n- Permanent fix: _what prevents recurrence_ → use `record_mistake` to add to immune system\n\n### Validation\nHow will you VERIFY the root cause is correct? (reproduce, test, monitor)'

    @mcp.tool()
    def fmea_analysis(component: str) -> str:
        """TRIGGER: Call this when designing a new feature before writing any code.
            ⚙️ FMEA — Failure Mode & Effects Analysis. Proactively enumerate what CAN fail before it does.
            Args:
                component: The system/component/feature to analyze
            """
        return f'## ⚙️ FMEA — Failure Mode & Effects Analysis\n### Component: {component}\n\nEnumerate every way this component can fail. Score each on 1-10 scale:\n- **Severity**: How bad if it happens? (1=trivial, 10=data loss/security breach)\n- **Occurrence**: How likely? (1=nearly impossible, 10=happens frequently)\n- **Detection**: How hard to detect BEFORE reaching users? (1=obvious, 10=invisible)\n\n| # | Failure Mode | Effect | Severity | Occurrence | Detection | **RPN** | Recommended Action |\n|---|---|---|---|---|---|---|---|\n| 1 | _what can fail_ | _impact_ | /10 | /10 | /10 | S×O×D | _specific mitigation_ |\n| 2 | | | | | | | |\n| 3 | | | | | | | |\n| 4 | | | | | | | |\n| 5 | | | | | | | |\n\n### Risk Priority\nSort by RPN (highest first). Address any RPN > 100 immediately.\n\n### Action Plan\nFor top 3 RPNs, specify:\n1. What to fix (target highest contributor: Severity, Occurrence, or Detection)\n2. Who owns it\n3. Expected new RPN after fix'

    @mcp.tool()
    def after_action_review(intended: str, actual: str, went_well: str, improve: str) -> str:
        """TRIGGER: Call this after mitigating an incident or finishing a major project milestone.
            🎖️ After Action Review — Structured learning from US Army. Blameless, focused on systemic improvement.
            Args:
                intended: What was EXPECTED to happen
                actual: What ACTUALLY happened
                went_well: What went WELL and why
                improve: What should be done DIFFERENTLY next time
            """
        learnings = ''
        if intended != actual:
            learnings = f"Gap: intended '{intended}' but got '{actual}'. Improvement: {improve}"
            store.record_mistake(mistake=f'AAR Gap: {actual}', root_cause=f'Expected: {intended}', fix=improve, severity='medium', tags='aar,learning')
        row_id = store.record_aar(intended, actual, went_well, improve, learnings)
        return f"## 🎖️ After Action Review #{row_id}\n\n### 1. What was INTENDED?\n{intended}\n\n### 2. What ACTUALLY happened?\n{actual}\n\n### 3. What went WELL?\n{went_well}\n\n### 4. What to do DIFFERENTLY?\n{improve}\n\n{('### 🛡️ Auto-recorded as anti-pattern for future immunity.' if learnings else '### ✅ No gap detected — good execution.')}\n\n_Learning compounds. This is now searchable via check_anti_patterns._"

    @mcp.tool()
    def smoke_test_gate(description: str, before_state: str, after_state: str='', action: str='create') -> str:
        """TRIGGER: Call this EXACTLY ONCE before starting a refactor (create), and ONCE after finishing it (complete).
            🚦 Smoke Test Gate — Before/after validation checkpoint. Creates explicit proof that changes don't regress.
            Args:
                description: What change is being validated
                before_state: Measurable state BEFORE the change
                after_state: Measurable state AFTER the change (leave empty when creating)
                action: 'create' to start a gate, 'complete' to finish one
            """
        if action == 'create' or not after_state:
            test_id = store.create_smoke_test(description, before_state)
            return f"## 🚦 Smoke Test Gate #{test_id} — CREATED\n\n### Change: {description}\n\n### BEFORE State (captured)\n{before_state}\n\n---\n⏳ Make your changes, then call `smoke_test_gate` again with action='complete' and the after_state to close this gate.\nGate ID: {test_id}"
        else:
            return f'## 🚦 Smoke Test Gate — COMPLETED\n\n### Change: {description}\n\n### BEFORE State\n{before_state}\n\n### AFTER State\n{after_state}\n\n### Comparison\nCompare each metric line by line:\n- Improvements: ✅ (list metrics that got BETTER)\n- Regressions: ⚠️ (list metrics that got WORSE)\n- Unchanged: ➡️ (list metrics that stayed the same)\n\n### Verdict: PASS / CONDITIONAL PASS (minor regressions) / FAIL (critical regressions)\n\n_If FAIL: Revert changes and investigate with `five_whys`._'

    @mcp.tool()
    def simulate_future_regrets(proposed_action: str) -> str:
        """TRIGGER: Call this BEFORE a major architectural or strategic action to generate failure predictions.
            Runs a simulated MCTS (Monte Carlo Tree Search) prompt template for the LLM to imagine futures.
            Args:
                proposed_action: The action you are about to take.
            """
        return f'''## 🌳 Future Regret Simulation: "{proposed_action}"

Please simulate 5 independent Monte Carlo paths into the future (e.g., 6 months from now). 
For each path, assume the `{proposed_action}` was executed, but resulted in catastrophic FAILURE.

**Task for you (the AI):**
1. Generate 5 distinct failure narratives.
2. Identify the core "trigger condition" that caused the failure.
3. Once generated, call `record_prospective_failure` for each of the 5 scenarios.

### MCTS Generation Prompt Template (Execute this inline):
**Path 1**: [Failure Mode] -> Trigger: [Condition]
**Path 2**: [Failure Mode] -> Trigger: [Condition]
...
**Path 5**: [Failure Mode] -> Trigger: [Condition]

*Once you have generated the paths, use the auditing tool to record them!*'''

    # ── FMEA Risk Gate (computational, not template) ──────

    @mcp.tool()
    def fmea_risk_gate(action: str, severity: int, probability: int, detectability: int) -> str:
        """⚙️ FMEA Risk Gate — Computes Risk Priority Number and returns a go/no-go verdict.
        Call BEFORE any risky action to get a quantified risk assessment.
        
        Args:
            action: The action to evaluate
            severity: How bad if it fails (1-5, where 5=catastrophic)
            probability: How likely to fail (1-5, where 5=certain)
            detectability: How hard to detect failure (1-5, where 5=invisible)
        """
        # Clamp inputs to valid range
        s = max(1, min(5, severity))
        p = max(1, min(5, probability))
        d = max(1, min(5, detectability))
        rpn = s * p * d

        if rpn < 9:
            verdict = "✅ PROCEED silently"
            level = "LOW"
        elif rpn <= 27:
            verdict = "⚠️ PROCEED but announce intent first"
            level = "MEDIUM"
        elif rpn <= 64:
            verdict = "🛑 STOP — Await explicit user approval"
            level = "HIGH"
        else:
            verdict = "🚫 HARD STOP — Reject and require architectural redesign"
            level = "CRITICAL"

        return (
            f"## ⚙️ FMEA Risk Gate\n\n"
            f"**Action:** {action}\n\n"
            f"| Factor | Score | Max |\n|---|---|---|\n"
            f"| Severity | {s} | 5 |\n"
            f"| Probability | {p} | 5 |\n"
            f"| Detectability | {d} | 5 |\n\n"
            f"**RPN (Risk Priority Number):** {rpn} / 125\n\n"
            f"**Risk Level:** {level}\n\n"
            f"**Verdict:** {verdict}\n\n"
            f"---\n"
            f"_RPN thresholds: <9 proceed, 9-27 announce, 28-64 stop, >64 hard stop_"
        )

    # ── Math Engine Tools (quantitative reasoning) ────────

    @mcp.tool()
    def calculate_expected_value(scenarios: str) -> str:
        """📊 Expected Value Calculator — Objective decision-making via probability-weighted outcomes.
        
        Args:
            scenarios: Comma-separated 'probability:value' pairs. Example: '0.7:100, 0.2:-50, 0.1:0'
        """
        import json as _json
        pairs = []
        total_prob = 0.0
        ev = 0.0
        
        for pair in scenarios.split(","):
            pair = pair.strip()
            if ":" not in pair:
                continue
            prob_str, val_str = pair.split(":", 1)
            prob = float(prob_str.strip())
            val = float(val_str.strip())
            pairs.append((prob, val))
            total_prob += prob
            ev += prob * val

        rows = "\n".join(
            f"| {p:.0%} | {v:+,.2f} | {p*v:+,.2f} |"
            for p, v in pairs
        )
        warning = ""
        if abs(total_prob - 1.0) > 0.01:
            warning = f"\n\n> ⚠️ Probabilities sum to {total_prob:.2f}, not 1.0. Results may be misleading."

        return (
            f"## 📊 Expected Value Analysis\n\n"
            f"| Probability | Outcome | Weighted |\n|---|---|---|\n"
            f"{rows}\n\n"
            f"**Expected Value: {ev:+,.2f}**{warning}\n\n"
            f"{'✅ Positive EV — proceed.' if ev > 0 else '❌ Negative EV — reconsider.' if ev < 0 else '➡️ Neutral EV — other factors should decide.'}"
        )

    @mcp.tool()
    def bayesian_update(prior: float, sensitivity: float, specificity: float) -> str:
        """📐 Bayesian Probability Update — Update beliefs with new evidence.
        
        Args:
            prior: Prior probability (0-1), e.g. 0.01 for 1% base rate
            sensitivity: True positive rate (0-1), P(test+|condition+)
            specificity: True negative rate (0-1), P(test-|condition-)
        """
        p = max(0.001, min(0.999, prior))
        sens = max(0.001, min(0.999, sensitivity))
        spec = max(0.001, min(0.999, specificity))
        
        prob_b = (sens * p) + ((1 - spec) * (1 - p))
        posterior = (sens * p) / prob_b if prob_b > 0 else 0

        return (
            f"## 📐 Bayesian Update\n\n"
            f"| Parameter | Value |\n|---|---|\n"
            f"| Prior P(A) | {p:.4f} |\n"
            f"| Sensitivity P(B|A) | {sens:.4f} |\n"
            f"| Specificity P(¬B|¬A) | {spec:.4f} |\n"
            f"| P(B) | {prob_b:.4f} |\n\n"
            f"**Posterior P(A|B) = {posterior:.4f}** ({posterior:.1%})\n\n"
            f"Belief shifted from {p:.1%} → {posterior:.1%} "
            f"({'↑' if posterior > p else '↓'} {abs(posterior - p):.1%})"
        )

    @mcp.tool()
    def compound_growth(principal: float, rate: float, periods: int) -> str:
        """📈 Compound Growth Calculator — Project growth over time.
        
        Args:
            principal: Starting value (e.g. revenue, users, investment)
            rate: Growth rate per period as decimal (e.g. 0.1 for 10%)
            periods: Number of periods to project
        """
        results = []
        current = principal
        for i in range(1, periods + 1):
            current *= (1 + rate)
            results.append((i, current))

        rows = "\n".join(
            f"| {period} | {value:,.2f} | {((value/principal)-1)*100:+.1f}% |"
            for period, value in results
        )
        final = results[-1][1] if results else principal
        total_return = ((final / principal) - 1) * 100

        return (
            f"## 📈 Compound Growth Projection\n\n"
            f"**Start:** {principal:,.2f} | **Rate:** {rate:.1%}/period | **Periods:** {periods}\n\n"
            f"| Period | Value | Cumulative |\n|---|---|---|\n"
            f"{rows}\n\n"
            f"**Final Value: {final:,.2f}** ({total_return:+.1f}% total return)"
        )

