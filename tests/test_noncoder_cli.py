from core.cli.noncoder import (
    format_contract_card,
    format_verification_receipt,
    format_fuzz_card,
    format_diagnostic_card,
    format_prune_card,
)


def test_format_contract_card():
    prompt = "Build user onboarding endpoint. Must include OAuth2 and avoid md5. Modify only auth.py."
    card = format_contract_card(prompt)

    assert "ELITE TASK CONTRACT (NON-CODER SUMMARY)" in card
    assert "OAuth2" in card
    assert "md5" in card
    assert "auth.py" in card
    assert "HOW TO HOLD YOUR CODING AGENT ACCOUNTABLE" in card


def test_format_verification_receipt():
    prompt = "Refactor auth logic. Must include OAuth2 and do not use bcrypt. Modify only auth.py."

    # 1. Defective draft
    bad_draft = "def login(): return 'ok'"
    receipt_bad = format_verification_receipt(prompt, bad_draft)
    assert "ELITE AI VERIFICATION RECEIPT" in receipt_bad
    assert "🚨 REJECT / REQUEST FIX" in receipt_bad
    assert "❌ FAIL" in receipt_bad

    # 2. Compliant draft
    good_draft = "def login():\n    # Using OAuth2\n    return 'auth_token'"
    receipt_good = format_verification_receipt(prompt, good_draft)
    assert "✅ ACCEPTABLE TO MERGE" in receipt_good
    assert "🎉 All checkable constraints are fully satisfied!" in receipt_good


def test_format_fuzz_card():
    unsafe_code = "def get(items): return items[0]"
    fuzz_res = format_fuzz_card(unsafe_code)
    assert "ELITE CEGIS PROPERTY FUZZING SCORECARD" in fuzz_res
    assert "🚨 EDGE CASE CRASH DETECTED" in fuzz_res
    assert "items = []" in fuzz_res

    safe_code = "def get(items):\n    if not items: return None\n    return items[0]"
    safe_res = format_fuzz_card(safe_code)
    assert "✅ CERTIFIED ROBUST" in safe_res


def test_format_diagnostic_card():
    tb = 'Traceback (most recent call last):\n  File "server.py", line 88, in handle\nKeyError: "session_id"'
    diag_res = format_diagnostic_card(tb)
    assert "ELITE ERROR DIAGNOSTIC SLICE" in diag_res
    assert "KeyError" in diag_res
    assert "88" in diag_res
    assert "1-CLICK COPY-PASTE REPAIR PROMPT" in diag_res


def test_format_prune_card():
    prompt = "Build auth. Must include OAuth2 and avoid md5. Modify only auth.py."
    candidates = [
        "def login():\n    # md5\n    return 'no'",
        "def login():\n    # OAuth2\n    return 'yes'",
    ]
    prune_res = format_prune_card(prompt, candidates)
    assert "ELITE SPECULATIVE DRAFT PRUNER" in prune_res
    assert "Champion Candidate Branch" in prune_res
    assert "BRANCH-02" in prune_res
