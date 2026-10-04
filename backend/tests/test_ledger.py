"""Step 2 test: append-only hash-chained ledger, prereg freeze, human approval. Run: python tests/test_ledger.py

Runs entirely in a temp SPARKLAB_ROOT with its own git repo; never touches the real ledger.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="sparklab_ledger_"))
os.environ["SPARKLAB_ROOT"] = str(TMP)  # before importing sparklab

from sparklab import config as C  # noqa: E402
from sparklab import ledger as L  # noqa: E402


def raises(exc, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc:
        return True
    raise AssertionError(f"{fn.__name__} did not raise {exc.__name__}")


def check_tamper(original: str, mutated: str, label: str):
    C.LEDGER_PATH.write_text(mutated, encoding="utf-8")
    ok, msg = L.verify()
    assert not ok, f"verify passed after {label}"
    C.LEDGER_PATH.write_text(original, encoding="utf-8")
    assert L.verify()[0], f"restore after {label} failed"


def main():
    assert C.LEDGER_PATH == TMP / "ledger" / "ledger.jsonl"
    assert BACKEND not in C.LEDGER_PATH.parents
    subprocess.run(["git", "init", "-q"], cwd=TMP, check=True)

    # Sequential ids, prev = previous hash.
    assert L.verify() == (True, "ledger chain intact")  # empty ledger
    e1 = L.append("note", "human", {"text": "first"})
    e2 = L.append("anomaly", "agent:scout", {"text": "second"})
    e3 = L.append("attack", "agent:skeptic", {"text": "third"})
    assert [e["id"] for e in (e1, e2, e3)] == ["L0001", "L0002", "L0003"]
    assert e1["prev"] == "0" * 64
    assert e2["prev"] == e1["hash"] and e3["prev"] == e2["hash"]
    assert L.verify() == (True, "ledger chain intact")

    # Tampering: edit one byte, delete a line, reorder lines.
    original = C.LEDGER_PATH.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    check_tamper(original, original.replace('"second"', '"secone"'), "one-byte edit")
    check_tamper(original, lines[0] + lines[2], "line deletion")
    check_tamper(original, lines[1] + lines[0] + lines[2], "reorder")

    # Type and origin validation.
    raises(ValueError, L.append, "gossip", "human", {})
    raises(ValueError, L.append, "note", "bot", {})
    assert L.append("note", "agent:scout", {"text": "ok"})["origin"] == "agent:scout"

    # Pre-registration: file, git commit, ledger entry; idempotent.
    protocol = {"title": "test protocol", "hypotheses": ["H_a", "H_b"]}
    p = L.register_prereg(protocol, "agent:experimenter")
    pid = p["payload"]["prereg_id"]
    assert pid.startswith("PR-") and len(pid) == 11 and all(c in "0123456789abcdef" for c in pid[3:])
    assert (TMP / "prereg" / f"{pid}.json").exists()
    assert len(p["payload"]["protocol_hash"]) == 64
    assert len(p["payload"]["git_commit"]) == 40
    committed = subprocess.run(["git", "show", "--name-only", "--format=", p["payload"]["git_commit"]],
                               cwd=TMP, capture_output=True, text=True, check=True).stdout.split()
    assert f"prereg/{pid}.json" in committed, committed
    n = len(L.read())
    assert L.register_prereg(protocol, "agent:experimenter") == p
    assert len(L.read()) == n
    assert L.load_protocol(pid) == protocol

    # Human approval: origin human, same hash; second approve raises.
    a = L.approve(pid, by="tester")
    assert a["type"] == "approval" and a["origin"] == "human"
    assert a["payload"]["protocol_hash"] == p["payload"]["protocol_hash"]
    raises(RuntimeError, L.approve, pid, by="tester")

    # Editing the prereg file after registration is detected.
    path = TMP / "prereg" / f"{pid}.json"
    path.write_text(path.read_text(encoding="utf-8").replace("H_b", "H_c"), encoding="utf-8")
    raises(PermissionError, L.load_protocol, pid)

    assert L.verify() == (True, "ledger chain intact")
    shutil.rmtree(TMP, ignore_errors=True)
    print("OK")


if __name__ == "__main__":
    main()
