import os
import sys
import argparse
from core.memory.persistent_store import EliteStore

def get_store() -> EliteStore:
    brain_dir = os.environ.get("ELITE_BRAIN_DIR", os.path.expanduser("~/.elite-reasoning/brain"))
    return EliteStore(brain_dir)

def cmd_check_anti_patterns(args):
    store = get_store()
    matches = store.check_anti_patterns(args.description)
    if not matches:
        print("✅ No matching anti-patterns found.")
        sys.exit(0)
    
    print(f"⚠️ Found {len(matches)} matching anti-patterns:\n")
    for r in matches:
        print(f"🚨 [{r['severity'].upper()}] {r['mistake']}")
        print(f"   Root Cause: {r['root_cause']}")
        print(f"   Fix: {r['fix']}\n")
    
    if any(r['severity'] in ['high', 'critical'] for r in matches):
        print("❌ CRITICAL/HIGH anti-patterns detected. Blocking execution.")
        sys.exit(1)
    
    sys.exit(0)

def cmd_audit(args):
    store = get_store()
    matches = store.check_anti_patterns(args.diff_summary)
    
    print("## 🔍 Pre-Commit Elite Audit\n")
    print(f"### Changes: {args.diff_summary}\n")
    
    print("### Pass 1: Security\n- [ ] No hardcoded secrets/keys  - [ ] No injection vulnerabilities  - [ ] Auth enforced  - [ ] Inputs validated\n")
    print("### Pass 2: Error Handling\n- [ ] Async try/catch  - [ ] Errors logged with context  - [ ] Edge cases handled\n")
    print("### Pass 3: Performance\n- [ ] No N+1 queries  - [ ] No memory leaks  - [ ] Large data paginated\n")
    print("### Pass 4: Tests\n- [ ] New logic tested  - [ ] Edge cases tested  - [ ] Error paths tested\n")
    print("### Pass 5: API Contract\n- [ ] No breaking changes  - [ ] New endpoints documented\n")
    
    print("### Pass 6: Anti-Pattern Cross-Reference")
    if matches:
        print(f"⚠️ **{len(matches)} matching anti-patterns!**\n")
        has_critical = False
        for ap in matches:
            print(f"- 🚨 [{ap['severity'].upper()}] {ap['mistake']} → Fix: {ap['fix']}")
            if ap['severity'] in ['high', 'critical']:
                has_critical = True
        
        if has_critical:
            print("\n### Verdict: ❌ BLOCK (Critical anti-patterns found)")
            sys.exit(1)
        else:
            print("\n### Verdict: ⚠️ CONDITIONAL PASS (Review anti-patterns)")
            sys.exit(0)
    else:
        print("✅ No matching anti-patterns.\n")
        print("### Verdict: ✅ PASS")
        sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Elite Reasoning Headless CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # check-anti-patterns
    parser_cap = subparsers.add_parser("check-anti-patterns", help="Check for past mistakes before building")
    parser_cap.add_argument("description", type=str, help="Description of what you are building")
    parser_cap.set_defaults(func=cmd_check_anti_patterns)
    
    # audit
    parser_audit = subparsers.add_parser("audit", help="Run a 6-pass pre-commit audit on changes")
    parser_audit.add_argument("diff_summary", type=str, help="Summary of code changes")
    parser_audit.set_defaults(func=cmd_audit)
    
    # export
    parser_export = subparsers.add_parser("export", help="Export the Elite memory database to JSON for team sync")
    parser_export.add_argument("--file", type=str, default="elite_memory_export.json", help="Output JSON file")
    def cmd_export(args):
        store = get_store()
        import json
        data = {
            "anti_patterns": store.get_all_anti_patterns(),
            "decisions": store.get_all_decisions()
        }
        with open(args.file, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Exported {len(data['anti_patterns'])} anti-patterns and {len(data['decisions'])} decisions to {args.file}")
    parser_export.set_defaults(func=cmd_export)

    # import
    parser_import = subparsers.add_parser("import", help="Import Elite memory database from JSON for team sync")
    parser_import.add_argument("file", type=str, help="Input JSON file")
    def cmd_import(args):
        store = get_store()
        import json
        with open(args.file, 'r') as f:
            data = json.load(f)
        
        # very simple merge: just record if not exact match (ignoring advanced deduplication for MVP)
        existing_aps = {ap['mistake'] for ap in store.get_all_anti_patterns()}
        added_aps = 0
        for ap in data.get("anti_patterns", []):
            if ap['mistake'] not in existing_aps:
                store.record_mistake(ap['mistake'], ap['root_cause'], ap['fix'], ap['severity'], ap['tags'])
                added_aps += 1
                
        existing_decs = {d['decision'] for d in store.get_all_decisions()}
        added_decs = 0
        for d in data.get("decisions", []):
            if d['decision'] not in existing_decs:
                store.record_decision(d['decision'], d['rationale'], d.get('alternatives_rejected', ''), d.get('context', ''))
                added_decs += 1
                
        print(f"✅ Imported {added_aps} new anti-patterns and {added_decs} new decisions from {args.file}")
    parser_import.set_defaults(func=cmd_import)
    
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
