"""Step 6 test: pre-registration gates and discovery runs, on synthetic data. Run: python tests/test_prereg.py

Runs in a temp SPARKLAB_ROOT with its own git repo; never touches the real ledger, prereg/ or data/.
Set SPARKLAB_KEEP_TMP=1 to keep the temp lab and read the generated prereg/*.json afterwards.
The generator is copied from _scaffold/spark-lab/tests/smoke_test.py.
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="sparklab_prereg_"))
os.environ["SPARKLAB_ROOT"] = str(TMP)  # before importing sparklab

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
RIVALS = [{"id": "H_measurement_error", "origin": "human",
           "statement": "A single HbA1c misclassifies part of the cell",
           "floor": "declared in protocol text"}]
H_ACCESS = {"id": "H_access", "origin": EXP,
            "statement": "Uninsured adults have a higher prevalence of HbA1c >= 6.5 without a reported diagnosis",
            "test": {"kind": "prevalence_ratio", "domain": "diag == 'no'", "outcome": "hba1c >= 6.5",
                     "group": "not insured"},
            "prediction": {"op": ">=", "value": 1.5}, "null": 1.0}
H_ONSET = {"id": "H_recent_onset", "origin": EXP,
           "statement": "Most of the undiagnosed cell sits just above the threshold",
           "test": {"kind": "proportion", "domain": "undiagnosed", "outcome": "hba1c < 7.0"},
           "prediction": {"op": ">=", "value": 0.60}, "null": 0.5}
PROTOCOL = {"title": "Undiagnosed diabetes: access vs recent onset vs measurement error",
            "question": "Among US adults reporting no diabetes diagnosis, who has HbA1c >= 6.5% and why?",
            "rivals": RIVALS, "hypotheses": [H_ACCESS, H_ONSET],
            "decision_rule": "sparklab.stats.verdict"}


def refused(protocol: dict) -> dict:
    r = j(tools.register_prereg(json.dumps(protocol), EXP))
    assert r["ok"] is False, r
    return r


def main():
    global tools
    shutil.copytree(BACKEND / "board", TMP / "board")
    (TMP / "ledger").mkdir()
    subprocess.run(["git", "init", "-q"], cwd=TMP, check=True)

    from sparklab import config as C
    from sparklab import data, ledger
    from sparklab import tools as _tools
    tools = _tools
    assert C.ROOT == TMP and BACKEND not in C.PREREG_DIR.parents

    write_raw(synth("J", 1), "J", TMP / "raw_J")
    data.main(["--cycle", "J", "--raw-dir", str(TMP / "raw_J")])

    # Structural validation.
    r = refused({**PROTOCOL, "rivals": []})
    assert any("H_measurement_error" in d for d in r["details"]), r
    r = refused({**PROTOCOL, "rivals": [{"id": "H_measurement_error", "origin": "human"}]})
    assert any("floor" in d for d in r["details"]), r
    for empty in (None, "", "   "):  # an empty floor is not a declared floor (seen in the Step 10 live run)
        r = refused({**PROTOCOL, "rivals": [{"id": "H_measurement_error", "origin": "human", "floor": empty}]})
        assert any("floor" in d for d in r["details"]), (empty, r)
    r = refused({**PROTOCOL, "hypotheses": [H_ACCESS]})
    assert any(">= 2" in d for d in r["details"]), r
    # Malformed shapes (seen in the Step 10 live run) are refused cleanly, not crashed on.
    r = refused({**PROTOCOL, "rivals": ["H_measurement_error"]})
    assert any("'rivals' must be a list of objects" in d for d in r["details"]), r
    r = refused({**PROTOCOL, "hypotheses": ["H_access", "H_recent_onset"]})
    assert any("'hypotheses' must be a list of objects" in d for d in r["details"]), r
    r = refused({**PROTOCOL, "hypotheses": [{**H_ACCESS, "test": "x"}, H_ONSET]})
    assert any("'test' must be an object" in d for d in r["details"]), r
    r = refused({**PROTOCOL, "hypotheses": [{**H_ACCESS, "prediction": ">= 1.5"}, H_ONSET]})
    assert any("'prediction' must be an object" in d for d in r["details"]), r
    assert j(tools.register_prereg("[1, 2]", EXP))["error"] == "protocol invalid"
    assert not ledger.read("prereg") and not ledger.read("gate")  # structural refusals write nothing

    # Power gate: tiny cell refused and logged.
    tiny = {**H_ONSET, "id": "H_tiny", "test": {**H_ONSET["test"], "domain": "undiagnosed and age >= 79 and female"}}
    r = refused({**PROTOCOL, "hypotheses": [H_ACCESS, tiny]})
    assert [f["gate"] for f in r["failures"]] == ["power"] and r["failures"][0]["hypothesis"] == "H_tiny", r
    gates = ledger.read("gate")
    assert len(gates) == 1 and gates[0]["id"] == r["ledger_id"] and gates[0]["origin"] == EXP

    # Definitions gate: a non-ADA category definition is refused.
    bad_def = {**H_ONSET, "id": "H_bad_def", "test": {"kind": "proportion", "domain": "diag == 'no'",
                                                       "outcome": "hba1c >= 5.5 and hba1c < 6.5",
                                                       "category": "prediabetes"}}
    r = refused({**PROTOCOL, "hypotheses": [H_ACCESS, bad_def]})
    assert [f["gate"] for f in r["failures"]] == ["definitions"], r
    assert len(ledger.read("gate")) == 2 and not ledger.read("prereg")

    # Valid protocol: id, hash, commit, file, git history.
    reg = j(tools.register_prereg(json.dumps(PROTOCOL), EXP))
    assert reg["ok"], reg
    pid = reg["prereg_id"]
    assert pid.startswith("PR-") and len(pid) == 11
    assert len(reg["protocol_hash"]) == 64 and len(reg["git_commit"]) == 40
    path = C.PREREG_DIR / f"{pid}.json"
    assert path.exists() and json.loads(path.read_text()) == PROTOCOL
    log = subprocess.run(["git", "log", "--format=%H %s"], cwd=TMP, capture_output=True, text=True, check=True).stdout
    assert f"{reg['git_commit']} prereg {pid}" in log, log
    assert "sparklab.approve" in reg["next"]

    # Discovery run: not confirmatory, one allowed verdict per hypothesis, each with a calc_id.
    disc = j(tools.run_test(pid, EXP, cycle="J"))
    assert disc["ok"] and disc["confirmatory"] is False and disc["cycle"] == "J", disc
    assert [x["id"] for x in disc["results"]] == ["H_access", "H_recent_onset"]
    assert all(x["verdict"] in ("supported", "incompatible", "inconclusive") for x in disc["results"])
    calcs = {json.loads(l)["calc_id"] for l in open(C.CALCS_PATH) if l.strip()}
    assert all(x["calc_id"] in calcs for x in disc["results"])
    res = ledger.read("result")
    assert len(res) == 1 and res[0]["payload"]["confirmatory"] is False and res[0]["id"] == disc["ledger_id"]

    # Bad cycle refused; hold-out refused without approval and costs no look.
    assert j(tools.run_test(pid, EXP, cycle="X"))["ok"] is False
    assert j(tools.run_test(pid, EXP, cycle="I"))["ok"] is False
    assert ledger.holdout_looks() == 0

    # Editing a registered protocol: run_test refuses. Use a second protocol so the first stays readable.
    p2 = {**PROTOCOL, "title": "copy to tamper"}
    pid2 = j(tools.register_prereg(json.dumps(p2), EXP))["prereg_id"]
    f2 = C.PREREG_DIR / f"{pid2}.json"
    f2.write_text(f2.read_text().replace("1.5", "1.1"))
    r = j(tools.run_test(pid2, EXP, cycle="J"))
    assert r["ok"] is False and "modified after registration" in r["error"], r

    # Origin check on the new tools.
    assert j(tools.register_prereg(json.dumps(PROTOCOL), "human"))["ok"] is False
    assert j(tools.run_test(pid, "agent:nobody", cycle="J"))["ok"] is False

    assert ledger.verify()[0]
    if os.environ.get("SPARKLAB_KEEP_TMP"):
        print(f"kept temp lab: {TMP}\nprereg file: {path}")
    else:
        shutil.rmtree(TMP, ignore_errors=True)
    print("OK")


if __name__ == "__main__":
    main()
