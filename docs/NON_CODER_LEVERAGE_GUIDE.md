# 🌟 Non-Coder & Product Manager Leverage Guide

How to use **Elite Reasoning MCP** to supervise, verify, and hold AI coding agents (Cursor, Claude Code, ChatGPT, Gemini, Windsurf) 100% accountable — **without writing a single line of code**.

---

## 🎯 The Non-Coder AI Coding Problem

When non-technical founders, product managers, or domain experts use AI coding agents, they face 3 core risks:
1. **Scope Escape**: The AI changes 15 random files instead of the single button you asked for.
2. **Hidden Hallucination / Missed Requirements**: The AI claims "All done!", but silently omitted 3 key security or business requirements.
3. **Inability to Read Code/Diffs**: You cannot tell if the code is actually correct or broken until something crashes in production.

**Elite solves this by acting as your automated, deterministic referee.**

---

## 🚀 Two-Minute Quickstart (Zero-Code)

### Step 1: Run the Interactive Assistant
In your terminal (or double-click `./scripts/elite_noncoder_helper.sh`):

```bash
elite-audit interactive
# or
uv run elite-audit interactive
```

---

### Step 2: Compile a Bulletproof Task Contract
Type or paste your feature idea / user story:

```bash
elite-audit contract "Add stripe checkout button. Must include webhook signature verification and do not store raw card numbers. Modify only checkout.py."
```

**Elite Output (Contract Card):**
```text
╔══════════════════════════════════════════════════════════════════════╗
║            🎯 ELITE TASK CONTRACT (NON-CODER SUMMARY)                ║
╚══════════════════════════════════════════════════════════════════════╝
📌 Goal        : Add stripe checkout button...
⚠️ Risk Level  : CRITICAL

📋 CHECKABLE REQUIREMENTS EXTRACTED FROM YOUR PROMPT:
  1. 🔴 [REQUIRED_CONTENT] Draft must contain exact term: webhook signature verification
  2. 🔴 [FORBIDDEN_CONTENT] Draft must NOT contain term: raw card numbers
  3. 🔴 [ALLOWED_FILES] Git diff must modify only allowed files: ['checkout.py']

🛡️ HOW TO HOLD YOUR CODING AGENT ACCOUNTABLE:
  1. Paste these exact bullet points to your AI coding assistant.
  2. Tell the assistant: 'Do not mark DONE until all criteria PASS.'
  3. Paste the assistant's final response back here to verify.
```

---

### Step 3: Verify the AI's Output
When your AI coding assistant gives you code or says it's done, verify it instantly:

```bash
elite-audit verify --prompt "Add stripe checkout. Must include webhook signature verification. Modify only checkout.py." --draft "<PASTE_AI_CODE_HERE>"
```

**Elite Output (Verification Receipt):**
```text
╔══════════════════════════════════════════════════════════════════════╗
║            🧾 ELITE AI VERIFICATION RECEIPT                          ║
╚══════════════════════════════════════════════════════════════════════╝
📊 Overall Score : 3/3 Criteria Satisfied
🏁 Status        : ✅ ACCEPTABLE TO MERGE

📋 INDIVIDUAL REQUIREMENT VERDICTS:
  ✅ PASS: Draft must contain exact term: webhook signature verification
  ✅ PASS: Draft must NOT contain term: raw card numbers
  ✅ PASS: Git diff must modify only allowed files: ['checkout.py']

🎉 All checkable constraints are fully satisfied! Safe to proceed.
```

If the AI missed something, Elite gives you a clear rejection reason you can copy-paste back to the AI:
> *"Your draft failed verification. Reason: Missing required term 'webhook signature verification'. Please fix."*

---

## ⚡ Summary of Non-Coder Commands

| Command | What It Does | Who It's For |
| :--- | :--- | :--- |
| `elite-audit contract "<prompt>"` | Extracts yes/no checkable rules from your words. | Product Managers writing specs |
| `elite-audit verify --prompt "..." --draft "..."` | Grades the AI output and detects missed requirements. | Anyone reviewing AI code |
| `./scripts/elite_noncoder_helper.sh` | One-click interactive helper. | Non-technical founders |
