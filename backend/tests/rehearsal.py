"""Fast UI rehearsal: the whole SPARK spine in a couple of minutes, no LLM, synthetic data.

    python tests/rehearsal.py                 # API on :8787; you click the human gates in the UI
    python tests/rehearsal.py --auto-gates    # fully unattended (gates through the API, as tests/test_bridge.py does)
    python tests/rehearsal.py --delay 0.5     # faster pacing between agent steps

Builds a throwaway lab in --root (default /tmp/spark-ui-rehearsal; wiped and rebuilt on every run) with a
synthetic discovery cycle and a synthetic sealed hold-out, starts `sparklab.api` on it with Omnigent
deliberately unreachable, and plays the agents' part with the real tools (every number comes from
sparklab.tools). Never touches the real ledger, data/, data/sealed/ or studies/.
Then: cd frontend && npm run dev, and open http://localhost:3000/?mode=live
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
MARKER = ".spark-rehearsal"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import smoke_test  # noqa: E402  (synthetic NHANES generator; sets SPARKLAB_ROOT to its own temp dir on import)

shutil.rmtree(smoke_test.TMP, ignore_errors=True)


def http(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def prepare_root(root: Path):
    root = root.resolve()
    if root == BACKEND or BACKEND in root.parents:
        sys.exit(f"refusing: {root} is inside the real lab ({BACKEND})")
    if root.exists():
        if not (root / MARKER).exists():
            sys.exit(f"refusing to wipe {root}: not a rehearsal directory (no {MARKER})")
        shutil.rmtree(root)
    root.mkdir(parents=True)
    (root / MARKER).write_text("throwaway lab created by tests/rehearsal.py\n")
    shutil.copytree(BACKEND / "board", root / "board")
    (root / "ledger").mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="/tmp/spark-ui-rehearsal")
    ap.add_argument("--port", type=int, default=8787, help="API port (the UI expects 8787)")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between agent steps")
    ap.add_argument("--auto-gates", action="store_true", help="answer the human gates through the API too")
    ap.add_argument("--keep-running", action="store_true", help="keep the API up after the loop finishes")
    a = ap.parse_args(argv)

    root = prepare_root(Path(a.root))
    os.environ["SPARKLAB_ROOT"] = str(root)  # before importing sparklab
    os.environ["SPARKLAB_STUDIES_DIR"] = str(root / "studies")
    sys.path.insert(0, str(BACKEND))
    from sparklab import config as C
    from sparklab import data, ledger, tools

    print(f"== building synthetic lab in {root}")
    smoke_test.write_raw(smoke_test.synth("J", 1), "J", root / "raw_J")
    smoke_test.write_raw(smoke_test.synth("I", 2), "I", root / "raw_I")
    data.main(["--cycle", "J", "--raw-dir", str(root / "raw_J")])
    data.main(["--cycle", "I", "--seal", "--raw-dir", str(root / "raw_I")])

    env = {**os.environ, "SPARK_API_PORT": str(a.port), "SPARK_OMNIGENT_URL": f"http://127.0.0.1:{free_port()}"}
    proc = subprocess.Popen([sys.executable, "-m", "sparklab.api"], cwd=BACKEND, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{a.port}"
    S = f"{base}/studies/{C.DEFAULT_STUDY_ID}"
    try:
        for _ in range(80):
            try:
                if http("GET", f"{base}/health")[0] == 200:
                    break
            except Exception:
                time.sleep(0.25)
        else:
            sys.exit(f"API did not start on :{a.port} (is another sparklab.api running? stop it first)")
        print(f"== API up on {base} (Omnigent unreachable on purpose)")
        print("== open http://localhost:3000/?mode=live   (cd frontend && npm run dev)\n")

        def j(s):
            out = json.loads(s)
            if isinstance(out, dict) and out.get("ok") is False and not out.get("expected_failure"):
                print(f"   tool said: {str(out)[:200]}")
            return out

        def step(label, fn=None):
            print(f"-- {label}")
            out = fn() if fn else None
            time.sleep(a.delay)
            return out

        def wait_gate(label, done, auto):
            if a.auto_gates:
                print(f"-- [auto] {label}")
                code, r = auto()
                if code >= 300:
                    sys.exit(f"auto gate failed: {code} {r}")
            else:
                print(f">> waiting for you in the UI: {label}")
            while not done():
                time.sleep(0.5)
            time.sleep(a.delay)

        # ---- objective (in the live lab the UI's "Start the lab" does this through Omnigent) ----
        step("objective recorded", lambda: http("POST", f"{S}/human/ledger", {
            "type": "plan_update", "by": "rehearsal",
            "payload": {"action": "objective", "text": "Find which discrepancy between self-reported diagnosis "
                                                       "and HbA1c to investigate next among US adults."}}))

        # ---- S: scout ----
        for eid in ("E01", "E02", "E03", "E04"):
            step(f"S  scout compute_surprise({eid})", lambda eid=eid: j(tools.compute_surprise(eid, "agent:scout")))
        step("S  scout logs an anomaly", lambda: j(tools.ledger_append("anomaly", json.dumps({
            "title": "self-report vs HbA1c discordance", "expectations": ["E02"]}), "agent:scout")))

        wait_gate("Pick a discrepancy (e.g. E02)",
                  lambda: any(n["payload"].get("action") == "pick_surprise" for n in ledger.read("note")),
                  lambda: http("POST", f"{S}/pick", {"expectation_id": "E02", "by": "rehearsal"}))

        # ---- P: experimenter ----
        hyp_access = {"id": "H_access", "origin": "agent:experimenter",
                      "statement": "Uninsured adults have a higher prevalence of undiagnosed HbA1c >= 6.5",
                      "test": {"kind": "prevalence_ratio", "domain": "diag == 'no'", "outcome": "hba1c >= 6.5", "group": "not insured"},
                      "prediction": {"op": ">=", "value": 1.5}, "null": 1.0}
        hyp_onset = {"id": "H_recent_onset", "origin": "agent:experimenter",
                     "statement": "Most of the undiagnosed cell sits just above threshold",
                     "test": {"kind": "proportion", "domain": "undiagnosed", "outcome": "hba1c < 7.0"},
                     "prediction": {"op": ">=", "value": 0.60}, "null": 0.5}
        rivals = [{"id": "H_measurement_error", "origin": "agent:experimenter", "statement": "assay error or misreport",
                   "floor": "declared from discovery agreement HbA1c vs glucose"}]
        step("P  experimenter estimate", lambda: j(tools.estimate("diag == 'no'", "hba1c >= 6.5", "agent:experimenter")))
        for h in (hyp_access, hyp_onset):
            step(f"P  experimenter proposes {h['id']}", lambda h=h: j(tools.ledger_append("hypothesis", json.dumps({
                "id": h["id"], "statement": h["statement"], "prediction": h["prediction"], "origin": h["origin"]}),
                "agent:experimenter")))

        # ---- A: the skeptic checks every board definition first (it does not take part in S) ----
        for eid in ("E01", "E02", "E03", "E04"):
            ctl = step(f"A  skeptic check_definitions({eid})",
                       lambda eid=eid: j(tools.check_definitions("agent:skeptic", expectation_id=eid)))
            errors = [i for i in ctl.get("issues") or [] if i.get("severity") == "error"]
            if errors:
                step(f"A  skeptic attacks {eid} (fatal definition error)", lambda eid=eid, errors=errors: j(tools.ledger_append(
                    "attack", json.dumps({"target": eid, "check": "check_definitions", "call": "fatal",
                                          "text": errors[0]["issue"]}), "agent:skeptic")))

        def last_pick():
            picks = [n["payload"]["expectation_id"] for n in ledger.read("note") if n["payload"].get("action") == "pick_surprise"]
            return picks[-1] if picks else None

        bad = {a["payload"]["target"] for a in ledger.read("attack") if a["payload"].get("call") == "fatal"}
        if last_pick() in bad:
            wait_gate(f"{last_pick()} is a definition error: pick another discrepancy",
                      lambda: last_pick() not in bad,
                      lambda: http("POST", f"{S}/pick", {"expectation_id": "E02", "by": "rehearsal"}))

        # ---- A: debate + a protocol the power gate rejects ----
        step("A  skeptic check_power on H_access", lambda: j(tools.check_power("diag == 'no'", "agent:skeptic",
                                                                             outcome="hba1c >= 6.5", group="not insured")))
        att = step("A  skeptic attacks H_access (confounding)", lambda: j(tools.ledger_append("attack", json.dumps({
            "target": "H_access", "check": "confounding", "call": "weak",
            "text": "H_access: age may confound insurance status"}), "agent:skeptic")))
        step("A  experimenter answers", lambda: j(tools.ledger_append("note", json.dumps({
            "responds_to": att.get("id") or att.get("entry", {}).get("id"), "stance": "accept",
            "text": "keep H_access exploratory-sized; prediction unchanged"}), "agent:experimenter")))
        small = {"title": "too small", "question": "q", "rivals": rivals, "hypotheses": [
            hyp_access, {**hyp_onset, "id": "H_tiny", "test": {**hyp_onset["test"], "domain": "undiagnosed and age >= 79 and female"}}]}
        step("A  experimenter tries a small-cell protocol (power gate should reject it)",
             lambda: j(tools.register_prereg(json.dumps(small), "agent:experimenter")))

        # ---- R: register + discovery run ----
        reg = step("R  experimenter registers the protocol", lambda: j(tools.register_prereg(json.dumps({
            "title": "Undiagnosed diabetes (rehearsal)", "question": "Who are the adults with HbA1c >= 6.5 and no diagnosis?",
            "rivals": rivals, "hypotheses": [hyp_access, hyp_onset]}), "agent:experimenter")))
        pid = reg["prereg_id"]
        step(f"R  discovery run_test({pid}, J)", lambda: j(tools.run_test(pid, "agent:experimenter", cycle="J")))

        wait_gate(f"Approve {pid} (hash prefix {reg['protocol_hash'][:8]})",
                  lambda: ledger.approval_for(pid) is not None,
                  lambda: http("POST", f"{S}/approve", {"prereg_id": pid, "by": "rehearsal",
                                                        "hash_prefix": reg["protocol_hash"][:8]}))
        sealed = ledger.read("seal")[-1]["payload"]["sha256"]
        wait_gate(f"Unseal the synthetic hold-out (hash prefix {sealed[:8]})",
                  lambda: any(u["payload"].get("hash_verified") for u in ledger.read("unseal")),
                  lambda: http("POST", f"{S}/unseal", {"by": "rehearsal", "sha256_prefix": sealed[:8]}))

        # ---- K: the single hold-out run ----
        step(f"K  experimenter run_test({pid}, I): the one look", lambda: j(tools.run_test(pid, "agent:experimenter", cycle="I")))
        wait_gate("Record the decision (keep / kill / revise)",
                  lambda: any(d["origin"] == "human" for d in ledger.read("decision")),
                  lambda: http("POST", f"{S}/human/ledger", {"type": "decision", "by": "rehearsal",
                                                             "payload": {"decision": "keep", "note": "rehearsal"}}))
        ok, msg = ledger.verify()
        print(f"\n== REHEARSAL DONE · ledger intact: {ok} ({msg})")
        if a.keep_running:
            print("== API still up; Ctrl-C to stop")
            proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
