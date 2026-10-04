"""Step 7 test: human gates and the hold-out path, on synthetic data only. Run: python tests/test_holdout.py

Always uses fresh temp SPARKLAB_ROOTs with synthetic J and a synthetic, sealed I. Never touches the real
ledger, data/sealed/ or data/holdout/.

    python tests/test_holdout.py           # full gate sequence, prints OK
    python tests/test_holdout.py --keep    # stop after registering a prereg (unapproved), keep the temp lab,
                                           # print its root and the prereg id for the approve rehearsal

The generator is copied from _scaffold/spark-lab/tests/smoke_test.py.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="sparklab_holdout_"))
os.environ["SPARKLAB_ROOT"] = str(TMP)  # before importing sparklab; always a fresh temp dir

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


def synth(cycle: str, seed: int, n: int = 6000) -> dict:
    r = np.random.default_rng(seed)
    seqn = np.arange(1, n + 1) + (100000 if cycle == "J" else 80000)
    sex = r.choice([1, 2], n)
    age = np.where(r.random(n) < 0.85, r.integers(20, 81, n), r.integers(1, 20, n)).astype(float)
    preg = np.where((sex == 2) & (age >= 20) & (age < 45), np.where(r.random(n) < 0.05, 1, 2), np.nan)
    strata = r.integers(134, 149, n)
    psu = r.choice([1, 2], n)
    demo = pd.DataFrame({"SEQN": seqn, "RIAGENDR": sex, "RIDAGEYR": age, "RIDEXPRG": preg,
                         "RIDRETH3": r.choice([1, 2, 3, 4, 6, 7], n), "INDFMPIR": r.uniform(0, 5, n),
                         "WTMEC2YR": r.uniform(5e3, 8e4, n), "SDMVSTRA": strata, "SDMVPSU": psu})
    diq010 = r.choice([1, 2, 3, 9], n, p=[0.10, 0.85, 0.03, 0.02])
    diq = pd.DataFrame({"SEQN": seqn, "DIQ010": diq010,
                        "DIQ050": np.where(diq010 == 1, r.choice([1, 2], n, p=[0.3, 0.7]), np.nan),
                        "DIQ070": np.where(diq010 == 1, r.choice([1, 2], n, p=[0.7, 0.3]), np.nan)})
    hiq011 = r.choice([1, 2, 9], n, p=[0.88, 0.11, 0.01])
    hiq = pd.DataFrame({"SEQN": seqn, "HIQ011": hiq011})
    huq = pd.DataFrame({"SEQN": seqn, "HUQ030": r.choice([1, 2, 3, 9], n, p=[0.75, 0.15, 0.09, 0.01])})
    a1c = r.normal(5.5, 0.45, n) + np.where(diq010 == 1, 1.5, 0) + np.where(hiq011 == 2, 0.35, 0)
    a1c = np.where(r.random(n) < 0.08, np.nan, np.round(a1c, 1))
    ghb = pd.DataFrame({"SEQN": seqn, "LBXGH": a1c})
    fast = r.random(n) < 0.45
    glu = pd.DataFrame({"SEQN": seqn, "LBXGLU": np.where(fast, 28.7 * np.nan_to_num(a1c, nan=5.5) - 46.7 + r.normal(0, 8, n), np.nan),
                        "WTSAF2YR": np.where(fast, r.uniform(1e4, 2e5, n), 0.0)})
    bmx = pd.DataFrame({"SEQN": seqn, "BMXBMI": r.normal(29, 6, n)})
    return {"DEMO": demo, "DIQ": diq, "GHB": ghb, "HIQ": hiq, "HUQ": huq, "BMX": bmx, "GLU": glu}


def write_raw(frames: dict, cycle: str, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    for comp, f in frames.items():
        f.to_csv(dest / f"{comp}_{cycle}.csv", index=False)



def j(s: str) -> dict:
    return json.loads(s)


EXP = "agent:experimenter"
PROTOCOL = {
    "title": "Undiagnosed diabetes: access vs recent onset vs measurement error",
    "question": "Among US adults reporting no diabetes diagnosis, who has HbA1c >= 6.5% and why?",
    "rivals": [{"id": "H_measurement_error", "origin": "human",
                "statement": "A single HbA1c misclassifies part of the cell", "floor": "declared in protocol text"}],
    "hypotheses": [
        {"id": "H_access", "origin": EXP,
         "statement": "Uninsured adults have a higher prevalence of HbA1c >= 6.5 without a reported diagnosis",
         "test": {"kind": "prevalence_ratio", "domain": "diag == 'no'", "outcome": "hba1c >= 6.5",
                  "group": "not insured"},
         "prediction": {"op": ">=", "value": 1.5}, "null": 1.0},
        {"id": "H_recent_onset", "origin": EXP,
         "statement": "Most of the undiagnosed cell sits just above the threshold",
         "test": {"kind": "proportion", "domain": "undiagnosed", "outcome": "hba1c < 7.0"},
         "prediction": {"op": ">=", "value": 0.60}, "null": 0.5}],
    "decision_rule": "sparklab.stats.verdict"}


def setup_lab(root: Path) -> str:
    """Board, empty ledger, git repo, synthetic J processed, synthetic I sealed, one registered prereg."""
    from sparklab import data, tools
    shutil.copytree(BACKEND / "board", root / "board")
    (root / "ledger").mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    write_raw(synth("J", 1), "J", root / "raw_J")
    write_raw(synth("I", 2), "I", root / "raw_I")
    data.main(["--cycle", "J", "--raw-dir", str(root / "raw_J")])
    data.main(["--cycle", "I", "--seal", "--raw-dir", str(root / "raw_I")])
    shutil.rmtree(root / "raw_I")  # only the sealed zip remains
    reg = j(tools.register_prereg(json.dumps(PROTOCOL), EXP))
    assert reg["ok"], reg
    return reg["prereg_id"]


def corrupt_case():
    """Step 5 of the plan, in its own temp root (a failed unseal blocks any later unseal)."""
    from sparklab import config as C
    from sparklab import ledger
    from sparklab import unseal as U
    pid = setup_lab(TMP)
    ledger.approve(pid, "test-human")
    with zipfile.ZipFile(C.SEALED_ZIP, "a") as z:
        z.writestr("extra.txt", "tampered")
    try:
        U.unseal(by="test-human")
    except RuntimeError as ex:
        assert "SHA-256 MISMATCH" in str(ex), ex
    else:
        raise AssertionError("unseal accepted a corrupted zip")
    last = ledger.read("unseal")[-1]["payload"]
    assert last["hash_verified"] is False and last["expected"] != last["actual"], last
    assert not (C.HOLDOUT_DIR / "nhanes_I.pkl").exists()
    shutil.rmtree(TMP, ignore_errors=True)
    print("CORRUPT CASE OK")


def main():
    from sparklab import config as C
    from sparklab import ledger, tools
    from sparklab import unseal as U
    assert C.ROOT == TMP and BACKEND not in C.LEDGER_PATH.parents and BACKEND not in C.SEALED_ZIP.parents

    pid = setup_lab(TMP)
    assert ledger.read("seal") and not C.HOLDOUT_DIR.exists()
    if "--keep" in sys.argv:
        print(f"\nkept temp lab, prereg registered and NOT approved\nSPARKLAB_ROOT={TMP}\nprereg_id={pid}")
        print(f"rehearse:  SPARKLAB_ROOT={TMP} python -m sparklab.approve {pid} --by <name>")
        return

    # 1. Hold-out refused before approval; no look consumed.
    r = j(tools.run_test(pid, EXP, cycle="I"))
    assert r["ok"] is False and "approval" in r["error"], r
    assert ledger.holdout_looks() == 0

    # 2. approve CLI refuses without an interactive terminal.
    env = {**os.environ, "SPARKLAB_ROOT": str(TMP)}
    p = subprocess.run([sys.executable, "-m", "sparklab.approve", pid, "--by", "x"], cwd=BACKEND, env=env,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert p.returncode != 0 and "interactive" in p.stderr, (p.returncode, p.stderr)
    assert not ledger.read("approval")
    p = subprocess.run([sys.executable, "-m", "sparklab.unseal"], cwd=BACKEND, env=env,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert p.returncode != 0 and not ledger.read("unseal"), (p.returncode, p.stderr)

    # 3. Human approval (stands in for the human typing the hash prefix).
    a = ledger.approve(pid, "test-human")
    reg = ledger.prereg_entry(pid)["payload"]
    assert a["origin"] == "human" and a["payload"]["protocol_hash"] == reg["protocol_hash"]
    assert ledger.approval_for(pid)["id"] == a["id"]

    # 4. Hold-out refused before unseal; still no look.
    r = j(tools.run_test(pid, EXP, cycle="I"))
    assert r["ok"] is False and "unseal" in r["error"], r
    assert ledger.holdout_looks() == 0

    # 5. Corrupted zip -> SHA-256 MISMATCH, hash_verified false (fresh temp root, separate process).
    p = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--corrupt-case"], cwd=BACKEND,
                       capture_output=True, text=True)
    assert p.returncode == 0 and "CORRUPT CASE OK" in p.stdout, (p.stdout[-2000:], p.stderr[-2000:])

    # 6. Unseal verifies the hash; a second unseal is refused.
    u = U.unseal(by="test-human")
    assert u["payload"]["hash_verified"] is True and u["payload"]["sha256"] == ledger.read("seal")[-1]["payload"]["sha256"]
    assert (C.HOLDOUT_DIR / "nhanes_I.pkl").exists()
    try:
        U.unseal(by="test-human")
    except RuntimeError as ex:
        assert "already unsealed" in str(ex)
    else:
        raise AssertionError("second unseal accepted")

    # 7. One confirmatory look.
    hold = j(tools.run_test(pid, EXP, cycle="I"))
    assert hold["ok"] and hold["confirmatory"] is True and hold["cycle"] == "I", hold
    assert all(x["verdict"] in ("supported", "incompatible", "inconclusive") for x in hold["results"])
    assert ledger.holdout_looks() == 1

    # 8. Budget spent: second look refused and logged.
    r = j(tools.run_test(pid, EXP, cycle="I"))
    assert r["ok"] is False and "budget" in r["error"], r
    assert ledger.holdout_looks() == 1
    assert ledger.read("gate")[-1]["payload"]["reason"] == "hold-out look budget spent"

    # 9. Chain intact.
    assert ledger.verify() == (True, "ledger chain intact")
    shutil.rmtree(TMP, ignore_errors=True)
    print("OK")


if __name__ == "__main__":
    if "--corrupt-case" in sys.argv:
        corrupt_case()
    else:
        main()
