from core.cli.noncoder import format_contract_card, format_verification_receipt


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
