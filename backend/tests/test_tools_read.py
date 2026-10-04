"""Step 5 test: read-only agent tools and the board, on synthetic data. Run: python tests/test_tools_read.py

Runs in a temp SPARKLAB_ROOT (copy of board/, synthetic discovery data, no hold-out). Never touches the
real ledger or data/. The generator is copied from _scaffold/spark-lab/tests/smoke_test.py.
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="sparklab_tools_"))
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


def calc_ids() -> set[str]:
    from sparklab import config as C
    return {json.loads(l)["calc_id"] for l in open(C.CALCS_PATH, encoding="utf-8") if l.strip()}


def main():
    shutil.copytree(BACKEND / "board", TMP / "board")

    # The real board now carries cited values; blank E02 in this temp copy to exercise the null branch.
    _b = json.loads((TMP / "board" / "expectations.json").read_text())
    next(e for e in _b["expectations"] if e["id"] == "E02")["expected"] = None
    (TMP / "board" / "expectations.json").write_text(json.dumps(_b))
    (TMP / "ledger").mkdir()
    subprocess.run(["git", "init", "-q"], cwd=TMP, check=True)

    from sparklab import config as C
    from sparklab import data, ledger, tools
    assert C.ROOT == TMP and BACKEND not in C.LEDGER_PATH.parents

    write_raw(synth("J", 1), "J", TMP / "raw_J")
    data.main(["--cycle", "J", "--raw-dir", str(TMP / "raw_J")])

    # read_board: E01-E04, control merged without revealing it.
    board = j(tools.read_board())
    ids = [e["id"] for e in board["expectations"]]
    assert ids == ["E01", "E02", "E03", "E04"], ids
    assert not any(k in e for e in board["expectations"] for k in ("seeded", "_comment", "control_purpose"))
    assert "seeded" not in tools.read_board()
    assert board["ada_thresholds"]["hba1c_prediabetes"] == C.HBA1C_PREDIABETES

    # check_definitions: seeded control caught, real items clean.
    e04 = j(tools.check_definitions("agent:skeptic", expectation_id="E04"))
    assert e04["ok"] and e04["clean"] is False, e04
    assert any("ADA" in i["issue"] for i in e04["issues"]), e04["issues"]
    for eid in ("E01", "E02", "E03"):
        r = j(tools.check_definitions("agent:skeptic", expectation_id=eid))
        assert r["ok"] and r["clean"] is True, (eid, r)

    # Labels and scope.
    bad = j(tools.check_definitions("agent:skeptic", outcome="no_meds_declared", label="untreated diabetics"))
    assert bad["clean"] is False and any(i["where"] == "label" for i in bad["issues"]), bad
    race = j(tools.check_definitions("agent:skeptic", domain="race_eth == 'nh_black'", outcome="hba1c >= 6.5"))
    assert race["clean"] is True and any(i["severity"] == "warning" and "race" in i["issue"] for i in race["issues"])

    # estimate: calc_id recorded in calcs.jsonl.
    est = j(tools.estimate("diag == 'no'", "hba1c >= 6.5", "agent:scout"))
    assert est["ok"] and est["calc_id"].startswith("calc_") and est["cycle"] == "J", est
    assert est["calc_id"] in calc_ids()
    assert C.CALCS_PATH.parent == TMP / "ledger"

    # Every tool refuses origin 'human' and unknown agents.
    for bad_origin in ("human", "agent:nobody"):
        calls = [
            lambda o: tools.estimate("", "hba1c >= 6.5", o),
            lambda o: tools.compute_surprise("E02", o),
            lambda o: tools.check_power("diag == 'no'", o, outcome="hba1c >= 6.5"),
            lambda o: tools.check_definitions(o, expectation_id="E01"),
            lambda o: tools.ledger_append("note", json.dumps({"text": "x"}), o),
        ]
        for call in calls:
            r = j(call(bad_origin))
            assert r["ok"] is False, (bad_origin, r)

    # check_power: a deliberately tiny cell fails the gate.
    tiny = j(tools.check_power("diag == 'no' and age >= 79 and female and not insured", "agent:skeptic",
                               outcome="hba1c >= 6.5"))
    assert tiny["ok"] and tiny["passes"] is False, tiny
    assert tiny["arms"]["cell"]["n_unweighted"] < C.MIN_CELL_N
    big = j(tools.check_power("diag == 'no'", "agent:skeptic", outcome="hba1c >= 6.5"))
    assert big["passes"] is True, big

    # compute_surprise with expected: null -> surprise null, with a reason.
    sur = j(tools.compute_surprise("E02", "agent:scout"))
    assert sur["ok"] and sur["expected"] is None and sur["surprise"] is None, sur
    assert "no cited expected value" in sur["message"]
    assert sur["calc_id"] in calc_ids()

    # ledger_append: approvals refused; numbers without calc_id warned.
    n_before = len(ledger.read())
    ap = j(tools.ledger_append("approval", "{}", "agent:supervisor"))
    assert ap["ok"] is False and len(ledger.read()) == n_before, ap
    an = j(tools.ledger_append("anomaly", '{"x": 1.2}', "agent:scout"))
    assert an["ok"] is True and "calc_id" in an.get("warning", ""), an
    cited = j(tools.ledger_append("anomaly", json.dumps({"x": 1.2, "calc_id": est["calc_id"]}), "agent:scout"))
    assert cited["ok"] and "warning" not in cited
    assert j(tools.ledger_append("note", "[1, 2]", "agent:scout"))["ok"] is False

    # ledger_read.
    lr = j(tools.ledger_read("anomaly"))
    assert lr["ok"] and len(lr["entries"]) == 2 and lr["holdout_looks"] == 0
    assert ledger.verify()[0]

    shutil.rmtree(TMP, ignore_errors=True)
    print("OK")


if __name__ == "__main__":
    main()
