"""Synthetic end-to-end smoke test. No network. Runs in a temp directory.

    python tests/smoke_test.py      -> must print SMOKE TEST OK

Covers the demo spine: seeded error caught -> power gate rejects small cell -> prereg with hash +
commit -> human approval -> unseal with verified hash -> verdict -> decision, plus every guard.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="sparklab_smoke_"))
os.environ["SPARKLAB_ROOT"] = str(TMP)
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402


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


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print(f"  ok  {msg}")


def main():
    # --- static checks on the real repo ---
    spec = yaml.safe_load(open(REPO / "lab.yaml"))
    check(isinstance(spec, dict) and "tools" in spec, "lab.yaml parses")
    def callables(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "callable":
                    yield v
                else:
                    yield from callables(v)
        elif isinstance(node, list):
            for v in node:
                yield from callables(v)
    exposed = set(callables(spec))
    check(exposed and all(c.startswith("sparklab.tools.") for c in exposed)
          and not any(x in c for c in exposed for x in ("approve", "unseal", "seal")),
          f"agents get only sparklab.tools functions, no approve/unseal ({len(exposed)} callables)")
    check("os_env" not in spec and all("os_env" not in v for v in spec["tools"].values() if isinstance(v, dict)),
          "no agent has os_env (no shell / filesystem access)")
    check(not any(l.startswith("from __future__") for l in (REPO / "sparklab" / "tools.py").read_text().splitlines()),
          "tools.py keeps real annotations")
    check("spec_version" not in spec, "single-file Omnigent format (no spec_version)")
    try:
        from omnigent import spec as ospec
        errs = ospec.validate(ospec.load(REPO / "lab.yaml")).errors
        check(not errs, f"Omnigent loads and validates lab.yaml {errs or ''}")
    except ImportError:
        print("  --  omnigent not installed in this venv; skipped spec validation")

    # --- temp lab ---
    shutil.copytree(REPO / "board", TMP / "board")

    # The real board now carries cited values; blank E02 in this temp copy to exercise the null branch.
    _b = json.loads((TMP / "board" / "expectations.json").read_text())
    next(e for e in _b["expectations"] if e["id"] == "E02")["expected"] = None
    (TMP / "board" / "expectations.json").write_text(json.dumps(_b))
    (TMP / "ledger").mkdir()
    subprocess.run(["git", "init", "-q"], cwd=TMP, check=True)

    from sparklab import config as C
    from sparklab import data, ledger, tools
    from sparklab import stats as S
    from sparklab import unseal as U

    check((C.HBA1C_PREDIABETES, C.HBA1C_DIABETES, C.GLUCOSE_PREDIABETES, C.GLUCOSE_DIABETES) == (5.7, 6.5, 100.0, 126.0),
          "ADA thresholds fixed")

    write_raw(synth("J", 1), "J", TMP / "raw_J")
    write_raw(synth("I", 2), "I", TMP / "raw_I")
    data.main(["--cycle", "J", "--raw-dir", str(TMP / "raw_J")])
    data.main(["--cycle", "I", "--seal", "--raw-dir", str(TMP / "raw_I")])
    check(C.SEALED_ZIP.exists() and ledger.read("seal"), "hold-out sealed with SHA-256 in ledger")
    check(not (C.HOLDOUT_DIR / "nhanes_I.pkl").exists(), "hold-out not processed at seal time")

    try:
        data.load("I")
        check(False, "data.load('I') must refuse")
    except PermissionError:
        check(True, "data.load('I') refuses")

    O = "agent:scout"
    j = lambda s: json.loads(s)  # noqa: E731

    board = j(tools.read_board())["expectations"]
    check(all("seeded" not in e for e in board) and any(e["id"] == "E04" for e in board),
          "read_board merges control without revealing it")
    check(j(tools.read_board())["ada_thresholds"]["hba1c_prediabetes"] == 5.7, "board exposes ADA thresholds")

    # S: seeded error caught
    ctl = j(tools.check_definitions("agent:skeptic", expectation_id="E04"))
    check(ctl["clean"] is False, f"seeded control caught: {ctl['issues'][0]['issue'][:70]}...")
    for eid in ("E01", "E02", "E03"):
        check(j(tools.check_definitions("agent:skeptic", expectation_id=eid))["clean"], f"{eid} definitions clean")
    bad_label = j(tools.check_definitions("agent:skeptic", outcome="no_meds_declared", label="untreated diabetics"))
    check(not bad_label["clean"], "banned label 'untreated' flagged")
    wt = j(tools.check_definitions("agent:skeptic", outcome="glucose >= 126"))
    check(wt["clean"], "glucose auto-uses wt_fast")
    split = j(tools.check_definitions("agent:skeptic", domain="diag == 'no'", outcome="hba1c >= 6.5",
                                      category="undiagnosed_diabetes"))
    check(split["clean"], "undiagnosed definition split across domain/outcome accepted")

    est = j(tools.estimate("diag == 'no'", "hba1c >= 6.5", O))
    check(est["ok"] and est["calc_id"].startswith("calc_") and 0 <= est["result"]["estimate"] <= 1,
          "estimate returns calc_id and a proportion")
    pr = j(tools.estimate("diag == 'no'", "hba1c >= 6.5", O, group="not insured"))
    check(pr["ok"] and pr["result"]["estimate"] > 0, "prevalence ratio computed")
    sur = j(tools.compute_surprise("E02", O))
    check(sur["ok"] and sur["surprise"] is None, "surprise needs a cited expected value (null -> no surprise)")
    check(not j(tools.estimate("", "hba1c >= 6.5", "human"))["ok"], "tools refuse origin 'human'")

    # wrong weight is refused
    try:
        S.taylor_prop(tools._discovery(), "", "glucose >= 126", weight="wt_mec")
        check(False, "glucose with wt_mec must fail")
    except ValueError:
        check(True, "glucose with wt_mec refused")

    # A: power gate rejects small cell
    pw = j(tools.check_power("diag == 'no' and age >= 79 and female and not insured", "agent:skeptic",
                             outcome="hba1c >= 6.5"))
    check(pw["passes"] is False, f"power gate rejects small cell (n={pw['arms']['cell']['n_unweighted']})")

    hyp_access = {"id": "H_access", "origin": "agent:experimenter",
                  "statement": "Uninsured adults have a higher prevalence of undiagnosed HbA1c >= 6.5",
                  "test": {"kind": "prevalence_ratio", "domain": "diag == 'no'", "outcome": "hba1c >= 6.5",
                           "group": "not insured"},
                  "prediction": {"op": ">=", "value": 1.5}, "null": 1.0}
    hyp_onset = {"id": "H_recent_onset", "origin": "agent:experimenter",
                 "statement": "Most of the undiagnosed cell sits just above threshold",
                 "test": {"kind": "proportion", "domain": "undiagnosed", "outcome": "hba1c < 7.0"},
                 "prediction": {"op": ">=", "value": 0.60}, "null": 0.5}
    rivals = [{"id": "H_measurement_error", "floor": "declared in protocol text", "origin": "human"}]
    small = {"title": "too small", "question": "q", "rivals": rivals, "hypotheses": [
        hyp_access, {**hyp_onset, "id": "H_tiny", "test": {**hyp_onset["test"],
                                                            "domain": "undiagnosed and age >= 79 and female"}}]}
    rej = j(tools.register_prereg(json.dumps(small), "agent:experimenter"))
    check(not rej["ok"] and rej["failures"][0]["gate"] == "power" and ledger.read("gate"),
          "register_prereg rejects small cell and logs the gate")
    no_rival = {"title": "t", "question": "q", "rivals": [], "hypotheses": [hyp_access, hyp_onset]}
    check(not j(tools.register_prereg(json.dumps(no_rival), "agent:experimenter"))["ok"],
          "prereg without H_measurement_error refused")

    # R: prereg with hash + commit
    protocol = {"title": "Undiagnosed diabetes v1", "question": "Who are the adults with HbA1c >= 6.5 and no diagnosis?",
                "rivals": rivals, "hypotheses": [hyp_access, hyp_onset]}
    reg = j(tools.register_prereg(json.dumps(protocol), "agent:experimenter"))
    check(reg["ok"] and len(reg["protocol_hash"]) == 64 and len(reg["git_commit"]) == 40,
          f"prereg {reg['prereg_id']} with sha256 + git commit")
    pid = reg["prereg_id"]
    log = subprocess.run(["git", "log", "--oneline"], cwd=TMP, capture_output=True, text=True).stdout
    check(pid in log, "prereg commit in git history")

    disc = j(tools.run_test(pid, "agent:experimenter", cycle="J"))
    check(disc["ok"] and not disc["confirmatory"] and len(disc["results"]) == 2, "discovery run_test (not confirmatory)")
    check(all(r["verdict"] in ("supported", "incompatible", "inconclusive") for r in disc["results"]), "three-way verdicts")

    # hold-out guards
    check(not j(tools.run_test(pid, "agent:experimenter", cycle="I"))["ok"], "hold-out refused before approval")
    check(ledger.holdout_looks() == 0, "refused attempts do not consume a look")
    r = subprocess.run([sys.executable, "-m", "sparklab.approve", pid, "--by", "agent"], cwd=REPO,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, env=os.environ)
    check(r.returncode != 0 and not ledger.read("approval"), "approve CLI refuses non-interactive use")
    ledger.approve(pid, by="smoke-human")  # stands in for the human typing the hash prefix
    check(ledger.approval_for(pid) is not None, "human approval recorded with matching hash")
    check(not j(tools.run_test(pid, "agent:experimenter", cycle="I"))["ok"], "hold-out refused before unseal")

    # tamper detection on a second protocol
    p2 = {**protocol, "title": "copy to tamper"}
    pid2 = j(tools.register_prereg(json.dumps(p2), "agent:experimenter"))["prereg_id"]
    f2 = C.PREREG_DIR / f"{pid2}.json"
    f2.write_text(f2.read_text().replace("1.5", "1.1"))
    check(not j(tools.run_test(pid2, "agent:experimenter", cycle="J"))["ok"], "edited protocol refused")

    # K: unseal with verified hash, one look, verdict, decision
    U.unseal(by="smoke-human")
    check(ledger.read("unseal")[-1]["payload"]["hash_verified"], "unseal verified SHA-256")
    hold = j(tools.run_test(pid, "agent:experimenter", cycle="I"))
    check(hold["ok"] and hold["confirmatory"], "confirmatory run on hold-out")
    for res in hold["results"]:
        print(f"      {res['id']}: {res['verdict']} ({res['reason']})")
    check(ledger.holdout_looks() == 1, "hold-out looks = 1")
    check(not j(tools.run_test(pid, "agent:experimenter", cycle="I"))["ok"], "second hold-out look refused")
    dec = j(tools.ledger_append("decision", json.dumps({"text": "next: confirmatory re-measurement subgroup",
                                                        "evidence": [hold["ledger_id"]]}), "agent:supervisor"))
    check(dec["ok"], "decision appended")
    check(not j(tools.ledger_append("approval", "{}", "agent:supervisor"))["ok"], "agents cannot append approvals")

    ok, msg = ledger.verify()
    check(ok, f"ledger verify: {msg}")
    lines = C.LEDGER_PATH.read_text().splitlines()
    C.LEDGER_PATH.write_text("\n".join([lines[0].replace('"human"', '"agent:x"')] + lines[1:]) + "\n")
    check(not ledger.verify()[0], "hand edit of ledger detected")

    shutil.rmtree(TMP, ignore_errors=True)
    print("SMOKE TEST OK")


if __name__ == "__main__":
    main()
