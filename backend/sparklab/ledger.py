"""Append-only, hash-chained ledger. Never edit ledger/ledger.jsonl by hand.

Each line: {id, ts, type, origin, payload, prev, hash}. `prev` is the previous line's hash,
so any hand edit, deletion or reordering breaks `verify()`.

CLI:
    python -m sparklab.ledger verify
    python -m sparklab.ledger show [--type prereg] [--last 20]
    python -m sparklab.ledger add --type hypothesis --by Brau --text "lived observation ..."
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys

import config as C

ORIGIN_RE = re.compile(r"^(human|agent:[a-z_]+)$")
ENTRY_TYPES = {"seal", "unseal", "anomaly", "attack", "hypothesis", "prereg", "approval",
               "holdout_look", "result", "gate", "decision", "plan_update", "note"}


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def protocol_hash(protocol: dict) -> str:
    return hashlib.sha256(canonical(protocol)).hexdigest()


def _lines() -> list[dict]:
    if not C.LEDGER_PATH.exists():
        return []
    with open(C.LEDGER_PATH, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def read(entry_type: str | None = None) -> list[dict]:
    rows = _lines()
    return [r for r in rows if entry_type is None or r["type"] == entry_type]


def append(entry_type: str, origin: str, payload: dict) -> dict:
    if entry_type not in ENTRY_TYPES:
        raise ValueError(f"unknown entry type {entry_type!r}")
    if not ORIGIN_RE.match(origin):
        raise ValueError("origin must be 'human' or 'agent:<name>'")
    rows = _lines()
    prev = rows[-1]["hash"] if rows else "0" * 64
    entry = {"id": f"L{len(rows) + 1:04d}",
             "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
             "type": entry_type, "origin": origin, "payload": payload, "prev": prev}
    entry["hash"] = hashlib.sha256(canonical(entry)).hexdigest()
    C.LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(C.LEDGER_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    return entry


def verify() -> tuple[bool, str]:
    prev = "0" * 64
    for i, r in enumerate(_lines(), 1):
        body = {k: v for k, v in r.items() if k != "hash"}
        if r.get("prev") != prev or hashlib.sha256(canonical(body)).hexdigest() != r.get("hash"):
            return False, f"chain broken at line {i} ({r.get('id')})"
        if r.get("id") != f"L{i:04d}":
            return False, f"id out of sequence at line {i}"
        prev = r["hash"]
    return True, "ledger chain intact"


# ---------- pre-registration ----------

def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "user.name=sparklab", "-c", "user.email=sparklab@localhost", *args],
                          cwd=C.ROOT, capture_output=True, text=True)


def prereg_entry(prereg_id: str) -> dict | None:
    for r in read("prereg"):
        if r["payload"]["prereg_id"] == prereg_id:
            return r
    return None


def prereg_file(prereg_id: str):
    return C.PREREG_DIR / f"{prereg_id}.json"


def load_protocol(prereg_id: str) -> dict:
    """Load a registered protocol and verify it was not edited after registration."""
    e = prereg_entry(prereg_id)
    if e is None:
        raise KeyError(f"no prereg {prereg_id!r} in ledger")
    path = prereg_file(prereg_id)
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol_hash(protocol) != e["payload"]["protocol_hash"]:
        raise PermissionError(f"{path.name} was modified after registration; register a new protocol instead")
    return protocol


def register_prereg(protocol: dict, origin: str) -> dict:
    """Freeze protocol: write prereg/<id>.json, git commit it, append ledger entry. Idempotent per hash."""
    h = protocol_hash(protocol)
    prereg_id = f"PR-{h[:8]}"
    existing = prereg_entry(prereg_id)
    if existing:
        return existing
    path = prereg_file(prereg_id)
    C.PREREG_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(protocol))
    rel = str(path.relative_to(C.ROOT))
    add = _git("add", "--", rel)
    com = _git("commit", "-m", f"prereg {prereg_id} sha256={h}", "--", rel)
    if add.returncode or com.returncode:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"git commit failed; prereg not registered: {add.stderr or com.stderr or com.stdout}")
    commit = _git("rev-parse", "HEAD").stdout.strip()
    return append("prereg", origin, {"prereg_id": prereg_id, "protocol_hash": h, "git_commit": commit, "path": rel})


# ---------- human gates ----------

def approval_for(prereg_id: str) -> dict | None:
    e = prereg_entry(prereg_id)
    if e is None:
        return None
    for r in read("approval"):
        p = r["payload"]
        if r["origin"] == "human" and p["prereg_id"] == prereg_id and p["protocol_hash"] == e["payload"]["protocol_hash"]:
            return r
    return None


def approve(prereg_id: str, by: str) -> dict:
    """Called only by the human CLI `python -m sparklab.approve`."""
    load_protocol(prereg_id)  # raises if missing or tampered
    if approval_for(prereg_id):
        raise RuntimeError(f"{prereg_id} already approved")
    h = prereg_entry(prereg_id)["payload"]["protocol_hash"]
    return append("approval", "human", {"prereg_id": prereg_id, "protocol_hash": h, "by": by})


def holdout_looks() -> int:
    return len(read("holdout_look"))


def holdout_gate(prereg_id: str) -> tuple[bool, str]:
    try:
        load_protocol(prereg_id)
    except Exception as e:
        return False, str(e)
    if not approval_for(prereg_id):
        return False, f"{prereg_id} has no human approval with matching hash (python -m sparklab.approve)"
    unseals = read("unseal")
    if not unseals or not unseals[-1]["payload"].get("hash_verified"):
        return False, "hold-out not unsealed with a verified hash (python -m sparklab.unseal)"
    return True, "ok"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify")
    s = sub.add_parser("show")
    s.add_argument("--type")
    s.add_argument("--last", type=int, default=20)
    a_ = sub.add_parser("add", help="human entry (hypothesis, anomaly, note, decision)")
    a_.add_argument("--type", required=True, choices=sorted(C.AGENT_ENTRY_TYPES))
    a_.add_argument("--by", required=True)
    a_.add_argument("--text", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "verify":
        ok, msg = verify()
        print(msg)
        sys.exit(0 if ok else 1)
    if a.cmd == "show":
        for r in read(a.type)[-a.last:]:
            print(json.dumps(r, ensure_ascii=False))
    if a.cmd == "add":
        print(append(a.type, "human", {"by": a.by, "text": a.text})["id"])


if __name__ == "__main__":
    main()
