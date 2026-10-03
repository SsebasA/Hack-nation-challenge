"""Human-only gate. Agents never get this command (CLAUDE.md rule 9).

    python -m sparklab.approve <prereg_id> --by <name>

Shows the frozen protocol, re-verifies its hash, and asks the human to type the first
8 characters of the hash. Refuses to run without an interactive terminal.
"""
import argparse
import json
import sys

from sparklab import ledger


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prereg_id")
    ap.add_argument("--by", required=True)
    a = ap.parse_args(argv)

    if not sys.stdin.isatty():
        sys.exit("Refusing: approval requires an interactive human terminal.")
    protocol = ledger.load_protocol(a.prereg_id)          # raises if missing or edited
    entry = ledger.prereg_entry(a.prereg_id)["payload"]
    print(json.dumps(protocol, indent=2, ensure_ascii=False))
    print(f"\nprereg   {a.prereg_id}\nsha256   {entry['protocol_hash']}\ncommit   {entry['git_commit']}")
    print(f"hold-out looks so far: {ledger.holdout_looks()}")
    typed = input("\nType the first 8 characters of the sha256 to approve: ").strip()
    if typed != entry["protocol_hash"][:8]:
        sys.exit("Hash mismatch. Not approved.")
    e = ledger.approve(a.prereg_id, a.by)
    print(f"Approved: {e['id']} by {a.by}")


if __name__ == "__main__":
    main()
