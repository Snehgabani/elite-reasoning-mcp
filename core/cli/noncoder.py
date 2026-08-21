"""
Non-Coder AI Leverage CLI & Contract Verification Suite.
Translates technical AST, git diff, and verification receipts into
human-readable, non-technical cards for product managers and founders.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional
from core.contracts.compiler import ContractCompiler
from core.contracts.models import Requirement, RequirementKind
from core.search.branch_pruner import prune_candidate_branches
from core.verification.cegis import CEGISPropertyVerifier
from core.verification.diagnostics import extract_diagnostic_slice
from core.verification.models import VerificationStatus
from core.verification.registry import GLOBAL_VERIFIER_REGISTRY


def format_contract_card(prompt: str) -> str:
    """Compiles a user prompt into a high-visibility plain-English contract card."""
    compiler = ContractCompiler()
    contract = compiler.compile(prompt)

    lines = [
        "╔══════════════════════════════════════════════════════════════════════╗",
        "║            🎯 ELITE TASK CONTRACT (NON-CODER SUMMARY)                ║",
        "╚══════════════════════════════════════════════════════════════════════╝",
        f"📌 Goal        : {contract.goal[:60]}...",
        f"⚠️ Risk Level  : {contract.risk_tier.value.upper()}",
        f"🔍 Max Retries : {contract.max_repair_attempts}",
        "",
        "📋 CHECKABLE REQUIREMENTS EXTRACTED FROM YOUR PROMPT:",
    ]

    for idx, req in enumerate(contract.requirements, 1):
        sev_icon = "🔴" if req.severity.value == "critical" else "🟡"
        lines.append(f"  {idx}. {sev_icon} [{req.kind.value.upper()}] {req.interpretation}")
        if req.source_text:
            lines.append(f'     Source: "{req.source_text}" (chars {req.source_start}-{req.source_end})')

    lines.append("")
    lines.append("🛡️ HOW TO HOLD YOUR CODING AGENT ACCOUNTABLE:")
    lines.append("  1. Paste these exact bullet points to your AI coding assistant.")
    lines.append("  2. Tell the assistant: 'Do not mark DONE until all criteria PASS.'")
    lines.append("  3. Paste the assistant's final response back here to verify.")
    lines.append("══════════════════════════════════════════════════════════════════════")
    return "\n".join(lines)


def format_verification_receipt(prompt: str, draft: str) -> str:
    """Evaluates AI output against compiled contract and generates a plain-English receipt."""
    compiler = ContractCompiler()
    contract = compiler.compile(prompt)
    registry = GLOBAL_VERIFIER_REGISTRY

    passed = 0
    failed = 0
    not_checked = 0
    results_lines = []

    for req in contract.requirements:
        res = registry.verify_requirement(req, draft)
        if res.status == VerificationStatus.PASS:
            passed += 1
            results_lines.append(f"  ✅ PASS: {req.interpretation}")
        elif res.status == VerificationStatus.FAIL:
            failed += 1
            results_lines.append(f"  ❌ FAIL: {req.interpretation} -> Reason: {res.reason}")
        else:
            not_checked += 1
            results_lines.append(f"  ℹ️ UNCHECKED: {req.interpretation} ({res.reason})")

    is_acceptable = failed == 0 and passed > 0

    lines = [
        "╔══════════════════════════════════════════════════════════════════════╗",
        "║            🧾 ELITE AI VERIFICATION RECEIPT                          ║",
        "╚══════════════════════════════════════════════════════════════════════╝",
        f"📊 Overall Score : {passed}/{len(contract.requirements)} Criteria Passed",
        f"🏁 Status        : {'✅ ACCEPTABLE TO MERGE' if is_acceptable else '🚨 REJECT / REQUEST FIX'}",
        "",
        "📋 INDIVIDUAL REQUIREMENT VERDICTS:",
    ]
    lines.extend(results_lines)
    lines.append("")
    if failed > 0:
        lines.append("💡 RECOMMENDED ACTION FOR NON-CODER:")
        lines.append(
            "  Tell your AI agent: 'Your draft failed verification. Please fix the items marked ❌ FAIL above.'"
        )
    else:
        lines.append("🎉 All checkable constraints are fully satisfied! Safe to proceed.")
    lines.append("══════════════════════════════════════════════════════════════════════")
    return "\n".join(lines)


def format_fuzz_card(code: str) -> str:
    """Evaluates code draft with CEGIS property fuzzing and generates resilience scorecard."""
    verifier = CEGISPropertyVerifier()
    req = Requirement(
        id="REQ-NONCODER-FUZZ",
        kind=RequirementKind.ROBUSTNESS,
        source_text="CEGIS property check",
        interpretation="Handle boundary collections and empty input states",
    )
    res = verifier.verify(req, code)
    lines = [
        "╔══════════════════════════════════════════════════════════════════════╗",
        "║            🧬 ELITE CEGIS PROPERTY FUZZING SCORECARD                 ║",
        "╚══════════════════════════════════════════════════════════════════════╝",
        f"🏁 Resilience Status : {'✅ CERTIFIED ROBUST' if res.status == VerificationStatus.PASS else '🚨 EDGE CASE CRASH DETECTED'}",
        "",
        f"📋 FINDINGS: {res.reason}",
    ]
    if res.status != VerificationStatus.PASS:
        lines.append("")
        lines.append("💡 COPY-PASTE TO YOUR AI AGENT:")
        lines.append(f"  'Your code fails on boundary inputs. Reason: {res.reason}. Please add bounds guards.'")
    lines.append("══════════════════════════════════════════════════════════════════════")
    return "\n".join(lines)


def format_diagnostic_card(error_text: str, source_code: Optional[str] = None) -> str:
    """Parses a messy error traceback into a 1-line plain-English repair prompt."""
    diag = extract_diagnostic_slice(error_text, source_code)
    lines = [
        "╔══════════════════════════════════════════════════════════════════════╗",
        "║            🔍 ELITE ERROR DIAGNOSTIC SLICE (REFLEXION)               ║",
        "╚══════════════════════════════════════════════════════════════════════╝",
        f"📍 Location : {diag.failing_file or 'Unknown file'} (line {diag.failing_line_number or '?'})",
        f"⚠️ Error    : {diag.error_type} ({diag.error_message})",
        "",
        "💡 1-CLICK COPY-PASTE REPAIR PROMPT FOR YOUR AI AGENT:",
        f"  'Fix {diag.error_type} in {diag.failing_file or 'code'} around line {diag.failing_line_number or '?'}. {diag.suggested_invariant_fix}'",
        "══════════════════════════════════════════════════════════════════════",
    ]
    return "\n".join(lines)


def format_prune_card(prompt: str, candidates: List[str]) -> str:
    """Ranks multiple candidate AI code drafts and picks the winning champion."""
    compiler = ContractCompiler()
    contract = compiler.compile(prompt)
    result = prune_candidate_branches(contract, candidates)

    lines = [
        "╔══════════════════════════════════════════════════════════════════════╗",
        "║            🌲 ELITE SPECULATIVE DRAFT PRUNER                         ║",
        "╚══════════════════════════════════════════════════════════════════════╝",
        f"📊 Total Candidates Evaluated : {result.total_candidates}",
        f"✂️ Pruned Defective Branches  : {result.pruned_candidates}",
        f"🏆 Champion Candidate Branch   : {result.champion_branch.branch_id if result.champion_branch else 'None'}",
        "",
        "📋 CANDIDATE BRANCH BREAKDOWN:",
    ]
    for b in result.evaluated_branches:
        status_icon = "❌ PRUNED" if b.is_pruned else "✅ SURVIVED"
        champ_tag = (
            " 🏆 (CHAMPION)" if result.champion_branch and b.branch_id == result.champion_branch.branch_id else ""
        )
        lines.append(
            f"  • {b.branch_id}: {status_icon}{champ_tag} (Passed: {b.passed_count}, Failed: {b.failed_count})"
        )
        if b.prune_reason:
            lines.append(f"    Reason: {b.prune_reason}")

    lines.append("══════════════════════════════════════════════════════════════════════")
    return "\n".join(lines)


def format_outline_card(file_path: str) -> str:
    """Extracts typed interface outline and formats token reduction summary."""
    from pathlib import Path
    from core.search.symbol_indexer import extract_symbol_outline

    path = Path(file_path)
    if not path.exists():
        return f"❌ Error: File `{file_path}` does not exist."

    content = path.read_text(encoding="utf-8")
    res = extract_symbol_outline(content, filename=path.name)

    lines = [
        "╔══════════════════════════════════════════════════════════════════════╗",
        "║            ⚡ AST SYMBOL OUTLINE (TOKEN COMPRESSOR)                  ║",
        "╚══════════════════════════════════════════════════════════════════════╝",
        f"📄 File Path         : {file_path}",
        f"📊 Raw Lines         : {res.total_raw_lines}",
        f"✂️ Outline Lines     : {res.total_outline_lines}",
        f"📉 Token Reduction   : {res.token_reduction_pct}% savings",
        f"🏛️ Classes ({len(res.classes)}) / Functions ({len(res.functions)})",
        "",
        "📋 SKELETON INTERFACE (ZERO-BODY AST):",
        "----------------------------------------------------------------------",
        res.skeleton_code,
        "══════════════════════════════════════════════════════════════════════",
    ]
    return "\n".join(lines)


def format_callgraph_card(file_path: str, symbol: Optional[str] = None) -> str:
    """Builds directional call graph and calculates blast radius impact."""
    from pathlib import Path
    from core.search.symbol_indexer import extract_call_graph

    path = Path(file_path)
    if not path.exists():
        return f"❌ Error: File `{file_path}` does not exist."

    content = path.read_text(encoding="utf-8")
    cg = extract_call_graph(content, filename=path.name)

    lines = [
        "╔══════════════════════════════════════════════════════════════════════╗",
        "║            🔍 DIRECTIONAL CALL GRAPH & BLAST RADIUS                  ║",
        "╚══════════════════════════════════════════════════════════════════════╝",
        f"📄 File Path        : {file_path}",
        f"📊 Total Symbols    : {cg.total_symbols}",
    ]

    if symbol:
        blast = cg.get_blast_radius(symbol)
        node = cg.nodes.get(symbol)
        lines.append(f"🎯 Target Symbol    : {symbol}")
        lines.append(f"💥 Blast Radius ({len(blast)} callers) : {', '.join(blast) if blast else 'None (Leaf)'}")
        if node:
            lines.append(f"📞 Callees Called   : {', '.join(node.callees) if node.callees else 'None'}")
    else:
        lines.append("")
        lines.append("📋 SYMBOL CALL GRAPH MAPPING:")
        for sym_name, node in cg.nodes.items():
            lines.append(f"  • {sym_name} (L{node.defined_at_line}):")
            lines.append(f"      Calls   -> {', '.join(node.callees) if node.callees else '(none)'}")
            lines.append(f"      CalledBy<- {', '.join(node.callers) if node.callers else '(none)'}")

    lines.append("══════════════════════════════════════════════════════════════════════")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Elite Reasoning MCP Non-Coder Leverage Suite")
    subparsers = parser.add_subparsers(dest="command")

    # Contract command
    contract_p = subparsers.add_parser("contract", help="Compile a plain-English contract card from a prompt")
    contract_p.add_argument("prompt", help="Natural language request or business requirement")

    # Verify command
    verify_p = subparsers.add_parser("verify", help="Verify an AI draft against your prompt")
    verify_p.add_argument("--prompt", required=True, help="Original prompt or requirement")
    verify_p.add_argument("--draft", required=True, help="AI response or code draft")

    # Fuzz command
    fuzz_p = subparsers.add_parser("fuzz", help="Stress-test code with CEGIS property fuzzing")
    fuzz_p.add_argument("--code", required=True, help="Python code snippet to fuzz")

    # Diagnose command
    diag_p = subparsers.add_parser("diagnose", help="Slice an error traceback into a 1-line AI repair prompt")
    diag_p.add_argument("--error", required=True, help="Raw error or traceback text")
    diag_p.add_argument("--code", help="Optional source code snippet")

    # Prune command
    prune_p = subparsers.add_parser("prune", help="Evaluate multiple candidate drafts and pick the champion")
    prune_p.add_argument("--prompt", required=True, help="Original prompt or task requirement")
    prune_p.add_argument("--candidates", nargs="+", required=True, help="List of candidate draft codes or files")

    # Outline command
    outline_p = subparsers.add_parser(
        "outline", help="Extract typed interface outline from Python file (90%+ token saving)"
    )
    outline_p.add_argument("file", help="Path to Python source file")

    # Callgraph command
    cg_p = subparsers.add_parser("callgraph", help="Extract directional call-graph and calculate blast radius")
    cg_p.add_argument("file", help="Path to Python source file")
    cg_p.add_argument("--symbol", help="Optional symbol name to calculate blast radius impact")

    # Install hooks command
    subparsers.add_parser("install-hooks", help="Install physical Git pre-commit barrier and IDE rules")

    # Interactive mode
    subparsers.add_parser("interactive", help="Launch interactive step-by-step assistant")

    args = parser.parse_args()

    if args.command == "contract":
        print(format_contract_card(args.prompt))
    elif args.command == "verify":
        print(format_verification_receipt(args.prompt, args.draft))
    elif args.command == "fuzz":
        print(format_fuzz_card(args.code))
    elif args.command == "diagnose":
        print(format_diagnostic_card(args.error, args.code))
    elif args.command == "prune":
        print(format_prune_card(args.prompt, args.candidates))
    elif args.command == "outline":
        print(format_outline_card(args.file))
    elif args.command == "callgraph":
        print(format_callgraph_card(args.file, args.symbol))
    elif args.command == "install-hooks":
        from pathlib import Path
        from scripts.install_zero_escape_hooks import install_zero_escape_system

        root = Path.cwd()
        res = install_zero_escape_system(root)
        print("🔒 Zero-Escape Multi-IDE & Physical Git Hooks Installed Successfully:")
        for k, v in res.items():
            print(f"  ✅ {k}: {'ACTIVE' if v else 'SKIPPED'}")
    elif args.command == "interactive" or len(sys.argv) == 1:
        print("=" * 70)
        print("🌟 Welcome to Elite Assistant (Zero-Code AI Verification & Leverage)")
        print("=" * 70)
        try:
            prompt = input("Enter your task / requirement: ").strip()
            if not prompt:
                print("No prompt provided. Exiting.")
                return
            print("\n" + format_contract_card(prompt) + "\n")
            verify_now = input("Do you have an AI draft to test right now? (y/n): ").strip().lower()
            if verify_now == "y":
                print("Paste the AI draft below (press Ctrl+D or type EOF on a new line when done):")
                lines = []
                while True:
                    try:
                        line = input()
                        if line.strip() == "EOF":
                            break
                        lines.append(line)
                    except EOFError:
                        break
                draft = "\n".join(lines)
                print("\n" + format_verification_receipt(prompt, draft))
        except KeyboardInterrupt:
            print("\nExiting.")


if __name__ == "__main__":
    main()
