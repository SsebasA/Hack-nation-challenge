"""Bridge + API test: the lab folded into UI events, on synthetic data. Run: python tests/test_bridge.py

Runs in a temp SPARKLAB_ROOT (copy of board/, synthetic discovery data, synthetic sealed hold-out,
`git init`) with a temp SPARKLAB_STUDIES_DIR. Never touches the real ledger, data/ or studies/.
Walks the demo spine with the real tools and checks, after each human gate, what the bridge derives;
the human gates themselves (approve, unseal, pick, decision) go through the HTTP API, Omnigent is
deliberately unreachable. The generator is copied from tests/smoke_test.py.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="sparklab_bridge_"))
os.environ["SPARKLAB_ROOT"] = str(TMP)  # before importing sparklab
os.environ["SPARKLAB_STUDIES_DIR"] = str(TMP / "studies")
sys.path.insert(0, str(BACKEND))

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


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print(f"  ok  {msg}")


def j(s):
    return json.loads(s)


def events_of(snap, kind):
    return [x["event"] for x in snap["events"] if x["event"]["kind"] == kind]


def folded(snap, kind):
    """Replay upserts the way the UI does: last patch wins per id."""
    out = {}
    for ev in events_of(snap, kind):
        item = ev["item"]
        out.setdefault(item["id"], {}).update(item)
    return out


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def http(method, url, body=None, timeout=15):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def main():
    shutil.copytree(BACKEND / "board", TMP / "board")
    (TMP / "ledger").mkdir()
    subprocess.run(["git", "init", "-q"], cwd=TMP, check=True)

    from sparklab import bridge, data, ledger, studies, tools
    from sparklab import config as C

    write_raw(synth("J", 1), "J", TMP / "raw_J")
    write_raw(synth("I", 2), "I", TMP / "raw_I")
    data.main(["--cycle", "J", "--raw-dir", str(TMP / "raw_J")])
    data.main(["--cycle", "I", "--seal", "--raw-dir", str(TMP / "raw_I")])

    # ---- the HTTP API on the temp lab, Omnigent deliberately unreachable ----
    port = free_port()
    env = {**os.environ, "SPARK_API_PORT": str(port), "SPARK_OMNIGENT_URL": f"http://127.0.0.1:{free_port()}"}
    proc = subprocess.Popen([sys.executable, "-m", "sparklab.api"], cwd=BACKEND, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    S = f"{base}/studies/{C.DEFAULT_STUDY_ID}"
    try:
        for _ in range(80):
            try:
                if http("GET", f"{base}/health")[0] == 200:
                    break
            except Exception:
                time.sleep(0.25)
        else:
            raise AssertionError(f"API did not start:\n{proc.stdout.read().decode(errors='replace')[-2000:]}")

        def state():
            """The API polls the lab's files; wait until its snapshot has caught up with what this
            process just wrote (ledger lines and calc records), then return it."""
            want_l, want_c = len(ledger.read()), len(bridge.read_calcs())
            deadline = time.time() + 10
            while True:
                code, s = http("GET", f"{S}/state")
                assert code == 200, s
                got = s["status"]["ledger"]
                if (got["entries"] >= want_l and got["calcs"] >= want_c) or time.time() > deadline:
                    return s
                time.sleep(0.2)

        # ---- empty lab: board visible, objective gate open ----
        snap = bridge.snapshot()
        exps = folded(snap, "expectation")
        check({"E01", "E02", "E03", "E04"} <= set(exps), "board expectations folded")
        check(all(e["status"] == "pending" for e in exps.values()), "board items start pending")
        check(not any("seeded" in json.dumps(x).lower() for x in snap["events"]), "seeded control not revealed")
        check(snap["gate"] == "objective" and not snap["finished"], "empty lab waits for an objective")
        check(any(e["type"] == "seal" for e in events_of(snap, "ledger")), "seal entry appears in the ledger feed")
        code, h = http("GET", f"{base}/health")
        check(code == 200 and h["omnigent"]["reachable"] is False and h["active_study"] == C.DEFAULT_STUDY_ID,
              "API up; Omnigent marked unreachable; default study active")
        check(http("POST", f"{S}/session", {"objective": "x"})[0] == 503, "starting a session without Omnigent -> 503")
        check(http("POST", f"{S}/session/message", {"text": "hi"})[0] == 409, "message without a session -> 409")

        # ---- human objective via the API (HTTP twin of `ledger add`) ----
        code, w = http("POST", f"{S}/human/ledger", {"type": "plan_update", "by": "ui-human",
                                                     "payload": {"action": "objective", "text": "Find which discrepancy to investigate next."}})
        check(code == 201 and w["entry"]["origin"] == "human", "objective recorded through the API")
        s = state()
        check(s["gate"] is None and s["objective"].startswith("Find which"), "objective closes the gate")
        check(events_of(s, "objective"), "objective event emitted")

        # ---- S: scout surprise calcs; A0: skeptic finds the seeded definition error ----
        for eid in ("E01", "E02", "E03", "E04"):
            j(tools.compute_surprise(eid, "agent:scout"))
        ctl = j(tools.check_definitions("agent:skeptic", expectation_id="E04"))
        j(tools.ledger_append("attack", json.dumps({"target": "E04", "check": "check_definitions", "call": "fatal",
                                                     "text": ctl["issues"][0]["issue"]}), "agent:skeptic"))
        j(tools.ledger_append("anomaly", json.dumps({"title": "self-report vs HbA1c discordance", "expectations": ["E02"],
                                                      "calc_ids": ["calc_00002"]}), "agent:scout"))
        snap = bridge.snapshot()
        exps = folded(snap, "expectation")
        check(exps["E04"]["status"] == "definition_error" and "5.7" in (exps["E04"].get("note") or ""),
              f"E04 marked definition_error from the Skeptic's attack: {exps['E04'].get('note', '')[:60]}…")
        check(all(exps[e]["status"] in ("consistent", "discrepancy") and exps[e].get("observed") and exps[e].get("calcId")
                  for e in ("E01", "E02", "E03")), "E01-E03 carry observed value + calc_id from surprise calcs")
        check(snap["gate"] == "pick-surprise", "board evaluated, no hypotheses, no Supervisor session -> humans pick")
        check(snap["events"][-1]["at"] >= snap["events"][0]["at"], "events are time-ordered")

        # ---- humans pick which discrepancy to pursue (API) ----
        check(http("POST", f"{S}/pick", {"expectation_id": "E99"})[0] == 400, "pick refuses unknown expectation ids")
        code, p = http("POST", f"{S}/pick", {"expectation_id": "E02", "text": "largest gap", "by": "ui-human"})
        check(code == 201 and p["entry"]["payload"]["action"] == "pick_surprise" and p["sent"] is None,
              "pick recorded as a human note; nothing sent (no session)")
        s = state()
        check(s["gate"] is None and s["pick"] == "E02", "pick closes the gate")
        check(any(c["from"] == "human" and c["text"].startswith("Pursue E02") for c in events_of(s, "chat")), "pick shows as chat")

        # ---- P: hypotheses; A: a protocol rejected by the power gate ----
        hyp_access = {"id": "H_access", "origin": "agent:experimenter",
                      "statement": "Uninsured adults have a higher prevalence of undiagnosed HbA1c >= 6.5",
                      "test": {"kind": "prevalence_ratio", "domain": "diag == 'no'", "outcome": "hba1c >= 6.5", "group": "not insured"},
                      "prediction": {"op": ">=", "value": 1.5}, "null": 1.0}
        hyp_onset = {"id": "H_recent_onset", "origin": "agent:experimenter",
                     "statement": "Most of the undiagnosed cell sits just above threshold",
                     "test": {"kind": "proportion", "domain": "undiagnosed", "outcome": "hba1c < 7.0"},
                     "prediction": {"op": ">=", "value": 0.60}, "null": 0.5}
        rivals = [{"id": "H_measurement_error", "origin": "agent:experimenter", "statement": "assay error or misreport",
                   "floor": "declared from discovery agreement HbA1c vs glucose (calc_00005)"}]
        for h in (hyp_access, hyp_onset):
            j(tools.ledger_append("hypothesis", json.dumps({"id": h["id"], "statement": h["statement"],
                                                             "prediction": h["prediction"], "origin": h["origin"]}), "agent:experimenter"))
        small = {"title": "too small", "question": "q", "rivals": rivals, "hypotheses": [
            hyp_access, {**hyp_onset, "id": "H_tiny", "test": {**hyp_onset["test"], "domain": "undiagnosed and age >= 79 and female"}}]}
        rej = j(tools.register_prereg(json.dumps(small), "agent:experimenter"))
        check(not rej["ok"], "small-cell protocol rejected by the power gate")
        snap = bridge.snapshot()
        hyps = folded(snap, "hypothesis")
        check(hyps["H_tiny"]["status"] == "blocked" and hyps["H_tiny"].get("cellN"), f"H_tiny blocked with cell n = {hyps['H_tiny'].get('cellN')}")
        check(any(e["hypothesisId"] == "H_tiny" and e["attack"]["kind"] == "power" and not e["attack"]["passed"]
                  for e in events_of(snap, "attack")), "power-gate failure shown as a failed attack on H_tiny")
        check(hyps["H_access"]["status"] in ("proposed", "under_attack") and snap["gate"] is None, "no prereg yet -> no gate")
        stages = [e["stage"] for e in events_of(snap, "stage")]
        check(stages == ["propose", "attack"], f"stages advance forward only: {stages}")

        # ---- R: valid prereg -> approve gate ----
        protocol = {"title": "Undiagnosed diabetes v1", "question": "Who are the adults with HbA1c >= 6.5 and no diagnosis?",
                    "rivals": rivals, "hypotheses": [hyp_access, hyp_onset]}
        reg = j(tools.register_prereg(json.dumps(protocol), "agent:experimenter"))
        pid = reg["prereg_id"]
        j(tools.run_test(pid, "agent:experimenter", cycle="J"))
        s = state()
        pre = {}
        for ev in events_of(s, "prereg"):
            pre.update(ev["patch"])
        check(pre["id"] == pid and pre["status"] == "registered" and pre["hash"].endswith(reg["protocol_hash"])
              and pre["commit"] == reg["git_commit"][:12], "prereg card carries id, sha256 and commit")
        check(len(pre["tests"]) == 2 and pre["rivals"][0]["id"] == "H_measurement_error", "prereg card lists tests and rivals")
        hyps_now = folded(s, "hypothesis")
        check(hyps_now["H_access"]["status"] == "survives" and hyps_now["H_measurement_error"]["status"] == "rival",
              "registered hypotheses survive; measurement error is the rival")
        check(s["gate"] == "approve" and s["prereg_id"] == pid, "registered + discovery run -> waiting for human approval")
        check(not events_of(s, "verdict"), "discovery run produces no verdict card")
        code, pd_ = http("GET", f"{S}/prereg/{pid}")
        check(code == 200 and pd_["protocol"]["title"] == protocol["title"] and pd_["approval"] is None, "/prereg/{id} returns the frozen protocol")
        check(http("GET", f"{S}/prereg/PR-nope")[0] == 404, "/prereg/{id} 404 for unknown ids")

        # ---- web approve: same friction as the CLI (typed hash prefix) ----
        code, r = http("POST", f"{S}/approve", {"prereg_id": pid, "by": "Brau", "hash_prefix": "deadbeef"})
        check(code == 400 and "mismatch" in r["detail"].lower() and ledger.approval_for(pid) is None, "wrong hash prefix -> not approved")
        check(http("POST", f"{S}/approve", {"prereg_id": pid, "by": "Brau", "hash_prefix": reg["protocol_hash"][:4]})[0] == 400,
              "a short prefix is refused")
        check(http("POST", f"{S}/approve", {"prereg_id": "PR-nope", "by": "Brau", "hash_prefix": reg["protocol_hash"][:8]})[0] == 404,
              "unknown prereg -> 404")
        code, r = http("POST", f"{S}/approve", {"prereg_id": pid, "by": "Brau", "hash_prefix": reg["protocol_hash"][:8].upper()})
        check(code == 201 and r["entry"]["type"] == "approval" and r["entry"]["origin"] == "human"
              and r["entry"]["payload"]["by"] == "Brau", "correct prefix -> human approval entry")
        check(http("POST", f"{S}/approve", {"prereg_id": pid, "by": "Brau", "hash_prefix": reg["protocol_hash"][:8]})[0] == 409,
              "second approval refused")
        s = state()
        check(s["gate"] == "unseal", "approval -> waiting for unseal")
        pre = {}
        for ev in events_of(s, "prereg"):
            pre.update(ev["patch"])
        check(pre["status"] == "approved" and pre["approvedBy"] == "Brau", "prereg card shows approver")

        # ---- web unseal: typed prefix of the sealed file's recorded SHA-256 ----
        sealed_sha = ledger.read("seal")[-1]["payload"]["sha256"]
        code, r = http("POST", f"{S}/unseal", {"by": "Jose", "sha256_prefix": "00000000"})
        check(code == 400 and not ledger.read("unseal"), "wrong sealed-hash prefix -> not unsealed, nothing written")
        code, r = http("POST", f"{S}/unseal", {"by": "Jose", "sha256_prefix": sealed_sha[:8]})
        check(code == 201 and r["entry"]["payload"]["hash_verified"] and r["entry"]["payload"]["by"] == "Jose",
              "correct prefix -> hold-out unsealed with verified hash")
        check(http("POST", f"{S}/unseal", {"by": "Jose", "sha256_prefix": sealed_sha[:8]})[0] == 409, "second unseal refused")
        s = state()
        check(s["gate"] is None and s["needs_confirmation"] is True, "unsealed, waiting for the agents' single run -> tell the Supervisor")

        hold = j(tools.run_test(pid, "agent:experimenter", cycle="I"))
        s = state()
        verdicts = events_of(s, "verdict")
        check(len(verdicts) == 2 and all(v["item"]["calcId"].startswith("calc_") for v in verdicts),
              "one verdict per hypothesis, each with its calc_id")
        check({v["item"]["label"] for v in verdicts} <= {"supported", "incompatible", "inconclusive"}, "three-way labels")
        byid = {v["item"]["hypothesisId"]: v["item"] for v in verdicts}
        r_access = next(r for r in hold["results"] if r["id"] == "H_access")
        check(byid["H_access"]["raw"]["estimate"] == r_access["estimate"] and byid["H_access"]["raw"]["kind"] == "prevalence_ratio",
              "verdict numbers are copied from run_test, not recomputed")
        check(s["gate"] == "decision" and s["needs_confirmation"] is False, "confirmatory result -> waiting for the human decision")
        check([e["stage"] for e in events_of(s, "stage")][-1] == "keepkill", "stage reaches keep/kill")

        code, w = http("POST", f"{S}/human/ledger", {"type": "decision", "by": "Brau",
                                                     "payload": {"decision": "keep", "note": "flag subgroup for re-measurement"}})
        check(code == 201, "decision recorded through the API")
        s = state()
        check(s["gate"] is None and s["finished"], "human decision closes the loop")
        check(events_of(s, "decision")[-1]["decision"] == "keep", "decision event emitted")
        st = s["status"]
        check(st["holdout"]["looks"] == 1 and st["holdout"]["unsealed"] and st["ledger"]["intact"], "status summarises looks/unseal/chain")
        check(http("POST", f"{S}/human/ledger", {"type": "approval", "payload": {"prereg_id": pid}})[0] == 400,
              "generic ledger write refuses approval entries")
        check(ledger.verify()[0], "ledger chain intact after all API writes")

        # ---- legacy aliases + SSE ----
        code, b = http("GET", f"{base}/board")
        check(code == 200 and "seeded" not in json.dumps(b), "/board alias = read_board, seeded flag stripped")
        code, l = http("GET", f"{base}/ledger?type=prereg")
        check(code == 200 and l["entries"][0]["payload"]["prereg_id"] == pid and l["intact"], "/ledger alias filters and verifies")
        req = urllib.request.Request(f"{S}/events", headers={"Accept": "text/event-stream"})
        with urllib.request.urlopen(req, timeout=10) as r:
            head = r.readline().decode()
            payload = r.readline().decode()
        check(head.strip() == "event: snapshot" and json.loads(payload[len("data:"):])["version"] >= 1, "/events streams a snapshot first")

        # ---- Omnigent session snapshot folded into the same log (pure function) ----
        t0 = time.time()
        omni = {
            "session": {"id": "s1", "agent_name": "spark_lab", "status": "running", "title": "t", "workspace": str(TMP)},
            "items": [
                {"id": "i1", "type": "message", "role": "user", "created_at": t0 - 100,
                 "content": [{"type": "input_text", "text": "Find which discrepancy to investigate next."}]},
                {"id": "i2", "type": "function_call", "created_at": t0 - 90, "name": "mcp__omnigent__sys_session_send",
                 "arguments": json.dumps({"agent": "scout", "message": "Survey the board."})},
                {"id": "i3", "type": "function_call", "created_at": t0 - 85, "name": "mcp__omnigent__sys_call_async",
                 "arguments": json.dumps({"tool": "compute_surprise", "args": json.dumps({"expectation_id": "E01"})})},
                {"id": "i4", "type": "message", "role": "assistant", "created_at": t0 - 80,
                 "content": [{"type": "output_text", "text": "Scout dispatched.\nWaiting for the inbox."}]},
            ],
            "children": [{"id": "c1", "tool": "scout", "busy": True, "current_task_status": "running", "session_name": "survey"},
                         {"id": "c2", "tool": "skeptic", "busy": False, "current_task_status": "completed", "session_name": "attack"}],
            "child_items": {"c1": [
                {"id": "k1", "type": "function_call", "created_at": t0 - 70, "name": "mcp__omnigent__estimate",
                 "arguments": json.dumps({"domain": "diag == 'no'", "outcome": "hba1c >= 6.5", "origin": "agent:scout"})},
            ]},
        }
        snap = bridge.snapshot(omni)
        agents = {e["agent"]: e for e in events_of(snap, "agent")}
        check(agents["scout"]["status"] == "working" and agents["skeptic"]["status"] == "done" and agents["supervisor"]["status"] == "working",
              "sub-agent and supervisor status from Omnigent child sessions")
        human_chats = [c for c in events_of(snap, "chat") if c["from"] == "human" and c["text"].startswith("Find which")]
        check(len(human_chats) == 1, "the objective is shown once even though ledger and session both carry it")
        acts = [a["event"] for a in snap["events"] if a["event"]["kind"] == "activity"]
        check(any(a["type"] == "handoff" and "scout" in a["title"] for a in acts), "sys_session_send to a sub-agent is a handoff")
        check(any(a["type"] == "tool_call" and "compute_surprise(" in (a.get("code") or "") for a in acts),
              "sys_call_async of a tool is shown as that tool call")
        check(any(a["actor"] == "scout" and a["type"] == "tool_call" and "origin" not in (a.get("code") or "") for a in acts),
              "child-session tool calls attributed to the sub-agent, origin arg hidden")

        # ---- studies: list, create, read, activate ----
        code, ls = http("GET", f"{base}/studies")
        check(code == 200 and [x["id"] for x in ls["studies"]] == [C.DEFAULT_STUDY_ID] and ls["studies"][0]["finished"],
              "/studies lists the default study with its summary")
        check(http("POST", f"{base}/studies", {"title": "   "})[0] == 400, "a study needs a title")
        n_root = len(ledger.read())
        code, cr = http("POST", f"{base}/studies", {"title": "Hypertension awareness gap", "question": "Which subgroups?", "by": "Brau"})
        check(code == 201 and cr["study"]["id"] == "hypertension-awareness-gap" and cr["study"]["gate"] == "objective",
              f"study created: {cr['study']['id']} (waits for an objective)")
        sid2 = cr["study"]["id"]
        root2 = TMP / "studies" / sid2
        check(root2.is_dir() and str(root2) == cr["study"]["root"] and (root2 / "study.json").exists(), "study directory under SPARKLAB_STUDIES_DIR")
        code, b2 = http("GET", f"{base}/studies/{sid2}/board")
        check(code == 200 and {e["id"] for e in b2["expectations"]} == {"E01", "E02", "E03", "E04"}, "new study starts from a copy of the board")
        code, st2 = http("GET", f"{base}/studies/{sid2}/status")
        check(code == 200 and st2["holdout"]["sealed"] and st2["holdout"]["sealed_sha256"] == sealed_sha and st2["discovery"]["processed"],
              "hold-out zip and discovery data linked from the root lab; seal recorded in the study's ledger")
        code, l2 = http("GET", f"{base}/studies/{sid2}/ledger")
        check(code == 200 and [e["type"] for e in l2["entries"]] == ["note", "seal"] and l2["intact"], "new ledger: creation note + seal, chain intact")
        check(len(ledger.read()) == n_root and ledger.verify()[0], "root ledger untouched by the new study")
        code, ls = http("GET", f"{base}/studies")
        check([x["id"] for x in ls["studies"]] == [C.DEFAULT_STUDY_ID, sid2], "/studies lists both")
        code, act = http("POST", f"{base}/studies/{sid2}/activate")
        check(code == 200 and act["active"] == sid2 and studies.active_id() == sid2 and (TMP / "studies" / "ACTIVE").exists(),
              "activate writes the ACTIVE pointer for the shared runner")
        check(str(C.ROOT) == str(TMP), "SPARKLAB_ROOT still wins over the pointer in this process")
        check(http("GET", f"{base}/studies/nope")[0] == 404, "unknown study -> 404")
        code, cr2 = http("POST", f"{base}/studies", {"title": "Hypertension awareness gap", "copy_board": False})
        check(code == 201 and cr2["study"]["id"] == f"{sid2}-2", "duplicate titles get a numbered id")
        code, b3 = http("GET", f"{base}/studies/{cr2['study']['id']}/board")
        check(code == 200 and b3["expectations"] == [], "copy_board=false starts with an empty board")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    real_studies = BACKEND / "studies"
    check(str(C.LEDGER_PATH).startswith(str(TMP)) and (not real_studies.exists() or
          not any(p.name.startswith("hypertension") for p in real_studies.iterdir())),
          "nothing was created under the real backend/studies")
    shutil.rmtree(TMP, ignore_errors=True)
    print("OK")


if __name__ == "__main__":
    main()
