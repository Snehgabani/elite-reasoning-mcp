# Compiled Exemplars: architecture

_Source: 6 real traces (2 passed / 4 failed). Compiled 2026-08-19T18:42._

## Exemplar 1 — python-dataclass-refactor (audit_test)
TASK: /Users/snehgabani/.gemini/antigravity/scratch/mix-mcp/.ai/metrics/runs/20260808_221625/python-dataclass-refactor.json
WINNING EVIDENCE: score=1.0 tokens=1500 time=0.572s backtracks=0 human_edit=False
VERIFIER: .                                                                        [100%] | 1 passed in 0.06s

## Exemplar 2 — python-loop-optimization (audit_test)
TASK: /Users/snehgabani/.gemini/antigravity/scratch/mix-mcp/.ai/metrics/runs/20260808_221625/python-loop-optimization.json
WINNING EVIDENCE: score=1.0 tokens=1500 time=0.731s backtracks=0 human_edit=False
VERIFIER: .                                                                        [100%] | 1 passed in 0.06s

## NON-WINNING TRACE (lesson material) — python-dataclass-refactor (baseline)
TASK: /Users/snehgabani/.gemini/antigravity/scratch/mix-mcp/.ai/metrics/runs/20260808_220324/python-dataclass-refactor.json
STATE: passed=False score=0.0
VERIFIER: ==================================== ERRORS ==================================== | _____________ ERROR collecting tests/golden/test_user_dataclass.py _____________ | ImportError while importing test module '/Users/snehgabani/.gemini/antigravity/scratch/elite-reasoning-ide/tests/golden/test_user_datacla

## NON-WINNING TRACE (lesson material) — python-loop-optimization (baseline)
TASK: /Users/snehgabani/.gemini/antigravity/scratch/mix-mcp/.ai/metrics/runs/20260808_220324/python-loop-optimization.json
STATE: passed=False score=0.0
VERIFIER: ==================================== ERRORS ==================================== | __________ ERROR collecting tests/golden/test_filter_optimization.py ___________ | ImportError while importing test module '/Users/snehgabani/.gemini/antigravity/scratch/elite-reasoning-ide/tests/golden/test_filter_optim

## NON-WINNING TRACE (lesson material) — python-dataclass-refactor (audit_test)
TASK: /Users/snehgabani/.gemini/antigravity/scratch/mix-mcp/.ai/metrics/runs/20260808_221621/python-dataclass-refactor.json
STATE: passed=False score=0.0
VERIFIER: [Errno 2] No such file or directory: 'pytest'

## NON-WINNING TRACE (lesson material) — python-loop-optimization (audit_test)
TASK: /Users/snehgabani/.gemini/antigravity/scratch/mix-mcp/.ai/metrics/runs/20260808_221621/python-loop-optimization.json
STATE: passed=False score=0.0
VERIFIER: [Errno 2] No such file or directory: 'pytest'
