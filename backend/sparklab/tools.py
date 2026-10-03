"""Functions exposed to Omnigent agents (type: function in lab.yaml).

Rules enforced here, in code, not prompts:
- No tool reads the hold-out except run_test(cycle="I"), and only after prereg + human approval
  with matching hash + verified unseal, and at most MAX_HOLDOUT_LOOKS times.
- No tool can approve or unseal.
- Every computed number gets a calc_id in ledger/calcs.jsonl, so "no number without a tool" is auditable.
- Power gate: unweighted cells < MIN_CELL_N cannot be pre-registered.

Note: do NOT add `from __future__ import annotations` here; Omnigent builds tool schemas
from real type annotations. All tools take simple args and return a JSON string.
"""
import datetime as dt
import json

import numpy as np
import pandas as pd

from sparklab import config as C
from sparklab import data, ledger
from sparklab import stats as S

_CACHE = {}


def _discovery() -> pd.DataFrame:
    if "J" not in _CACHE:
        _CACHE["J"] = data.load(C.DISCOVERY)
    return _CACHE["J"]


def _json(obj) -> str:
    def conv(o):
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.integer,)):
            return int(o)
        return str(o)
    return json.dumps(obj, ensure_ascii=False, default=conv, indent=1)


def _err(msg: str, **extra) -> str:
    return _json({"ok": False, "error": msg, **extra})


def _check_origin(origin: str) -> str | None:
    if origin not in C.AGENT_ORIGINS:
        return f"origin must be one of {sorted(C.AGENT_ORIGINS)}"
    return None


def _calc(kind: str, origin: str, inputs: dict, result: dict) -> str:
    C.CALCS_PATH.parent.mkdir(parents=True, exist_ok=True)
    n = sum(1 for _ in open(C.CALCS_PATH, encoding="utf-8")) if C.CALCS_PATH.exists() else 0
    cid = f"calc_{n + 1:05d}"
    row = {"calc_id": cid, "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "kind": kind, "origin": origin, "cycle": inputs.get("cycle", C.DISCOVERY), "inputs": inputs, "result": result}
    with open(C.CALCS_PATH, "a", encoding="utf-8") as f:
        f.write(_json(row).replace("\n", "") + "\n")
    return cid


def _board() -> list[dict]:
    items = json.loads(C.BOARD_PATH.read_text(encoding="utf-8"))["expectations"]
    if C.CONTROL_PATH.exists():
        items = items + json.loads(C.CONTROL_PATH.read_text(encoding="utf-8"))["expectations"]
    # The seeded control must look like any other expectation to the agents.
    hidden = {"seeded", "_comment", "control_purpose"}
    return sorted(({k: v for k, v in e.items() if k not in hidden} for e in items), key=lambda e: e["id"])


def _find_expectation(eid: str) -> dict | None:
    return next((e for e in _board() if e["id"] == eid), None)


def _run_query(df: pd.DataFrame, q: dict) -> dict:
    if q.get("kind", "proportion") == "prevalence_ratio" or q.get("group"):
        return S.prevalence_ratio(df, q.get("domain", ""), q["outcome"], q["group"], q.get("weight", ""))
    return S.taylor_prop(df, q.get("domain", ""), q["outcome"], q.get("weight", ""))


def _power(df: pd.DataFrame, domain: str, outcome: str, group: str) -> dict:
    weight = S.pick_weight(df, domain, outcome, group)
    if group:
        valid = " and ".join(f"{c} == {c}" for c in S.referenced_columns(group, df)) or "True"
        arms = {"exposed": f"({valid}) and ({group})", "reference": f"({valid}) and not ({group})"}
    else:
        arms = {"cell": ""}
    out = {}
    for name, extra in arms.items():
        d = S.domain_mask(df, domain, outcome, weight, extra)
        events = int((S.mask(df, outcome) & d).sum()) if outcome else None
        out[name] = {"n_unweighted": int(d.sum()), "n_events": events}
    passed = all(a["n_unweighted"] >= C.MIN_CELL_N for a in out.values())
    res = {"passes": passed, "min_cell_n": C.MIN_CELL_N, "arms": out, "weight": weight}
    low_events = [k for k, a in out.items() if a["n_events"] is not None and a["n_events"] < C.MIN_CELL_N]
    if low_events:
        res["warning"] = f"fewer than {C.MIN_CELL_N} unweighted events in {low_events}: estimates will be unstable"
    return res


# ======================= tools =======================

def read_board() -> str:
    """Return the expectation board: priors with citation, comparability label and query spec."""
    return _json({"ok": True, "expectations": _board(), "ada_thresholds": {
        "hba1c_prediabetes": C.HBA1C_PREDIABETES, "hba1c_diabetes": C.HBA1C_DIABETES,
        "glucose_prediabetes": C.GLUCOSE_PREDIABETES, "glucose_diabetes": C.GLUCOSE_DIABETES},
        "columns": data.COLUMNS_DOC, "base_domain": C.BASE_DOMAIN})


def estimate(domain: str, outcome: str, origin: str, group: str = "") -> str:
    """Design-based estimate on the DISCOVERY cycle only. Without group: weighted proportion of
    outcome within domain. With group: prevalence ratio of outcome in group vs not group.
    domain/outcome/group are pandas.eval expressions over the derived columns."""
    if (e := _check_origin(origin)):
        return _err(e)
    try:
        df = _discovery()
        q = {"domain": domain, "outcome": outcome, "group": group}
        res = _run_query(df, q)
    except Exception as ex:
        return _err(str(ex))
    cid = _calc("estimate", origin, q, res)
    return _json({"ok": True, "calc_id": cid, "cycle": C.DISCOVERY, "result": res})


def compute_surprise(expectation_id: str, origin: str) -> str:
    """Compare one board expectation against the discovery data. Surprise = expected value outside the 95% CI."""
    if (e := _check_origin(origin)):
        return _err(e)
    exp = _find_expectation(expectation_id)
    if exp is None:
        return _err(f"no expectation {expectation_id!r}")
    try:
        res = _run_query(_discovery(), exp["query"])
    except Exception as ex:
        return _err(str(ex))
    expected = exp.get("expected")
    out = {"expectation_id": expectation_id, "estimate": res.get("estimate"), "ci": [res.get("ci_low"), res.get("ci_high")],
           "expected": expected, "comparability": exp.get("comparability"), "note": exp.get("note")}
    if expected is None:
        out["surprise"] = None
        out["message"] = "expectation has no cited expected value yet; cannot compute surprise"
    elif res.get("estimate") is None:
        out["surprise"] = None
        out["message"] = res.get("warning", "no estimate")
    else:
        inside = res["ci_low"] <= expected <= res["ci_high"]
        out["surprise"] = not inside
        se = res.get("se") or res.get("se_log")
        if res.get("se"):
            out["distance_in_se"] = (res["estimate"] - expected) / se if se else None
    cid = _calc("surprise", origin, {"expectation_id": expectation_id, **exp["query"]}, {**res, **out})
    return _json({"ok": True, "calc_id": cid, **out, "detail": res})


def check_power(domain: str, origin: str, outcome: str = "", group: str = "") -> str:
    """Power gate on the discovery cycle: unweighted n per cell (and per arm if group given).
    Cells below MIN_CELL_N cannot enter confirmatory testing."""
    if (e := _check_origin(origin)):
        return _err(e)
    try:
        res = _power(_discovery(), domain, outcome, group)
    except Exception as ex:
        return _err(str(ex))
    cid = _calc("power", origin, {"domain": domain, "outcome": outcome, "group": group}, res)
    return _json({"ok": True, "calc_id": cid, **res})


# ---- definitions ----

_GRID = np.round(np.arange(4.0, 12.01, 0.05), 2)
_GLU_GRID = np.arange(60.0, 300.0, 1.0)
_CANON = {
    "normal": ("hba1c", lambda x: x < C.HBA1C_PREDIABETES),
    "prediabetes": ("hba1c", lambda x: (x >= C.HBA1C_PREDIABETES) & (x < C.HBA1C_DIABETES)),
    "diabetes_lab": ("hba1c", lambda x: x >= C.HBA1C_DIABETES),
    "undiagnosed_diabetes": ("hba1c", lambda x: x >= C.HBA1C_DIABETES),
    "normal_glucose": ("glucose", lambda x: x < C.GLUCOSE_PREDIABETES),
    "prediabetes_glucose": ("glucose", lambda x: (x >= C.GLUCOSE_PREDIABETES) & (x < C.GLUCOSE_DIABETES)),
    "diabetes_glucose": ("glucose", lambda x: x >= C.GLUCOSE_DIABETES),
}
_BANNED_LABELS = ["untreated", "never medicated", "never-medicated", "unmedicated"]
_CAUSAL = ["causes", "caused by", "because of", "effect of", "leads to", "due to"]


def _probe(var: str, diag: str) -> pd.DataFrame:
    grid = _GRID if var == "hba1c" else _GLU_GRID
    n = len(grid)
    df = _discovery().head(0).reindex(range(n))
    # neutral defaults; only the probed variable varies
    for c in ["adult", "insured", "routine_place", "no_meds_declared"]:
        df[c] = pd.array([True] * n, dtype="boolean")
    for c in ["female", "pregnant", "insulin_now", "pills_now"]:
        df[c] = pd.array([False] * n, dtype="boolean")
    df["diag"] = diag
    df["age"] = 50.0
    df["hba1c"] = grid if var == "hba1c" else 5.0
    df["glucose"] = grid if var == "glucose" else 90.0
    from sparklab.data import _cat
    df["hba1c_cat"] = _cat(df["hba1c"], C.HBA1C_PREDIABETES, C.HBA1C_DIABETES)
    df["glucose_cat"] = _cat(df["glucose"], C.GLUCOSE_PREDIABETES, C.GLUCOSE_DIABETES)
    und = (df["diag"] == "no") & (df["hba1c"] >= C.HBA1C_DIABETES)
    df["undiagnosed"] = und.astype("boolean")
    return df


def _definition_issues(domain: str, outcome: str, category: str, text: str, group: str = "") -> list[dict]:
    issues = []
    df0 = _discovery()
    for name, expr in (("domain", domain), ("outcome", outcome), ("group", group)):
        bad = S.unknown_names(expr, df0)
        if bad:
            issues.append({"severity": "error", "where": name, "issue": f"unknown columns {bad}"})
    if any(i["severity"] == "error" for i in issues):
        return issues
    try:
        S.pick_weight(df0, domain, outcome, group)
    except ValueError as ex:
        issues.append({"severity": "error", "where": "weight", "issue": str(ex)})
    if category:
        if category not in _CANON:
            issues.append({"severity": "error", "where": "category", "issue": f"unknown category; use {sorted(_CANON)}"})
        else:
            var, canon = _CANON[category]
            diag = "no" if category == "undiagnosed_diabetes" else "yes"
            probe = _probe(var, diag)
            # undiagnosed: the definition may be split between domain and outcome; others: outcome only
            both = category == "undiagnosed_diabetes"

            def sel(pr):
                m = S.mask(pr, outcome)
                return (m & S.mask(pr, domain)) if both else m

            got = sel(probe).to_numpy()
            want = canon(probe[var]).to_numpy()
            if both:
                # must also exclude people who report a diagnosis
                if sel(_probe(var, "yes")).to_numpy().any():
                    issues.append({"severity": "error", "where": "outcome",
                                   "issue": "undiagnosed definition counts people who report a diagnosis (needs diag == 'no')"})
            wrong = probe[var].to_numpy()[got != want]
            if len(wrong):
                issues.append({"severity": "error", "where": "outcome",
                               "issue": f"'{category}' definition disagrees with ADA thresholds for {var} in "
                                        f"[{wrong.min()}, {wrong.max()}] (ADA: normal < {C.HBA1C_PREDIABETES}, "
                                        f"diabetes >= {C.HBA1C_DIABETES} for HbA1c; {C.GLUCOSE_PREDIABETES}/"
                                        f"{C.GLUCOSE_DIABETES} mg/dL for glucose)"})
    exprs = " ".join([domain or "", outcome or "", group or ""])
    if "race_eth" in exprs:
        issues.append({"severity": "warning", "where": "query",
                       "issue": "race/ethnicity analysis requires human review before publication"})
    if "diag != 'yes'" in exprs.replace('"', "'") or "diag != \"yes\"" in exprs:
        issues.append({"severity": "warning", "where": "query",
                       "issue": "diag != 'yes' mixes borderline (code 3) with 'no'; keep borderline apart"})
    low = (text or "").lower()
    for w in _BANNED_LABELS:
        if w in low:
            issues.append({"severity": "error", "where": "label",
                           "issue": f"label uses {w!r}; say 'no insulin or pills declared currently'"})
    for w in _CAUSAL:
        if w in low:
            issues.append({"severity": "warning", "where": "label",
                           "issue": f"causal wording {w!r}; data are cross-sectional (no causal claims)"})
    return issues


def check_definitions(origin: str, expectation_id: str = "", domain: str = "", outcome: str = "",
                      category: str = "", label: str = "", group: str = "") -> str:
    """Attack definitions. Either pass expectation_id (checks that board item) or an explicit
    domain/outcome/category/label. Categories: normal, prediabetes, diabetes_lab, undiagnosed_diabetes,
    normal_glucose, prediabetes_glucose, diabetes_glucose. Checks ADA thresholds, weights, labels, scope."""
    if (e := _check_origin(origin)):
        return _err(e)
    if expectation_id:
        exp = _find_expectation(expectation_id)
        if exp is None:
            return _err(f"no expectation {expectation_id!r}")
        q = exp["query"]
        domain, outcome, group = q.get("domain", ""), q["outcome"], q.get("group", "")
        category = q.get("category", "")
        label = " ".join([exp.get("statement", ""), exp.get("label", "")])
    try:
        issues = _definition_issues(domain, outcome, category, label, group)
    except Exception as ex:
        return _err(str(ex))
    return _json({"ok": True, "expectation_id": expectation_id or None, "clean": not any(
        i["severity"] == "error" for i in issues), "issues": issues})


# ---- pre-registration and tests ----

def _validate_protocol(p: dict) -> list[str]:
    if not isinstance(p, dict):
        return ["protocol must be a JSON object"]
    errs = []
    for k in ("title", "question", "hypotheses", "rivals"):
        if k not in p:
            errs.append(f"missing '{k}'")
    if errs:
        return errs
    # Shape check first, so malformed agent input is refused instead of crashing the gates below.
    for k in ("hypotheses", "rivals"):
        if not isinstance(p[k], list) or not all(isinstance(x, dict) for x in p[k]):
            errs.append(f"'{k}' must be a list of objects (see docs/PREREG_TEMPLATE.md)")
    for h in p["hypotheses"] if isinstance(p["hypotheses"], list) else []:
        for k in ("test", "prediction"):
            if isinstance(h, dict) and not isinstance(h.get(k, {}), dict):
                errs.append(f"{h.get('id', '?')}: '{k}' must be an object")
    if errs:
        return errs
    hyps = p["hypotheses"]
    if not isinstance(hyps, list) or len(hyps) < 2:
        errs.append("need >= 2 rival hypotheses with tests")
    ids = [h.get("id", "") for h in hyps] + [r.get("id", "") for r in p.get("rivals", [])]
    if not any(i.startswith("H_measurement_error") for i in ids):
        errs.append("mandatory rival H_measurement_error (with declared floor) missing")
    for r in p.get("rivals", []):
        if r.get("id", "").startswith("H_measurement_error") and "floor" not in r:
            errs.append("H_measurement_error needs a declared 'floor'")
    for h in hyps:
        hid = h.get("id", "?")
        if not ledger.ORIGIN_RE.match(h.get("origin", "")):
            errs.append(f"{hid}: origin must be 'human' or 'agent:<name>'")
        t = h.get("test", {})
        if t.get("kind") not in ("proportion", "prevalence_ratio"):
            errs.append(f"{hid}: test.kind must be proportion or prevalence_ratio")
        if t.get("kind") == "prevalence_ratio" and not t.get("group"):
            errs.append(f"{hid}: prevalence_ratio needs test.group")
        if "outcome" not in t:
            errs.append(f"{hid}: test.outcome missing")
        pred = h.get("prediction", {})
        if pred.get("op") not in (">=", "<=") or not isinstance(pred.get("value"), (int, float)):
            errs.append(f"{hid}: prediction must be {{op: '>=' or '<=', value: number}}")
        if not isinstance(h.get("null"), (int, float)):
            errs.append(f"{hid}: numeric 'null' required")
    return errs


def register_prereg(protocol_json: str, origin: str) -> str:
    """Freeze a protocol (JSON string; see docs/PREREG_TEMPLATE.md): validates it, runs the definition
    check and the power gate on every test, then writes prereg/<id>.json, git-commits it and records
    the SHA-256 in the ledger. Registered protocols are immutable; to change one, register a new one."""
    if (e := _check_origin(origin)):
        return _err(e)
    try:
        protocol = json.loads(protocol_json)
    except json.JSONDecodeError as ex:
        return _err(f"protocol_json is not valid JSON: {ex}")
    errs = _validate_protocol(protocol)
    if errs:
        return _err("protocol invalid", details=errs)
    df = _discovery()
    gate_failures = []
    for h in protocol["hypotheses"]:
        t = h["test"]
        defs = _definition_issues(t.get("domain", ""), t["outcome"], t.get("category", ""),
                                  h.get("statement", ""), t.get("group", ""))
        if any(i["severity"] == "error" for i in defs):
            gate_failures.append({"hypothesis": h["id"], "gate": "definitions", "issues": defs})
            continue
        pw = _power(df, t.get("domain", ""), t["outcome"], t.get("group", ""))
        if not pw["passes"]:
            gate_failures.append({"hypothesis": h["id"], "gate": "power", "arms": pw["arms"]})
    if gate_failures:
        entry = ledger.append("gate", origin, {"action": "register_prereg rejected", "title": protocol["title"],
                                               "failures": gate_failures})
        return _err("rejected by gates; nothing registered", ledger_id=entry["id"], failures=gate_failures)
    try:
        entry = ledger.register_prereg(protocol, origin)
    except Exception as ex:
        return _err(str(ex))
    return _json({"ok": True, "ledger_id": entry["id"], **entry["payload"],
                  "next": "Ask a human to run: python -m sparklab.approve "
                          f"{entry['payload']['prereg_id']} --by <name>"})


def run_test(prereg_id: str, origin: str, cycle: str = "J") -> str:
    """Run every test in a registered protocol. cycle='J' (discovery) needs only the prereg.
    cycle='I' (hold-out) needs human approval with matching hash + verified unseal, and is
    counted as a hold-out look (max MAX_HOLDOUT_LOOKS)."""
    if (e := _check_origin(origin)):
        return _err(e)
    try:
        protocol = ledger.load_protocol(prereg_id)  # raises if missing or edited after registration
    except Exception as ex:
        return _err(str(ex))
    if cycle == C.DISCOVERY:
        df = _discovery()
    elif cycle == C.HOLDOUT:
        ok, why = ledger.holdout_gate(prereg_id)
        if not ok:
            ledger.append("gate", origin, {"action": "run_test hold-out refused", "prereg_id": prereg_id, "reason": why})
            return _err(f"hold-out refused: {why}")
        if ledger.holdout_looks() >= C.MAX_HOLDOUT_LOOKS:
            ledger.append("gate", origin, {"action": "run_test hold-out refused", "prereg_id": prereg_id,
                                           "reason": "hold-out look budget spent"})
            return _err(f"hold-out already looked at {ledger.holdout_looks()} time(s); budget is {C.MAX_HOLDOUT_LOOKS}")
        look = ledger.append("holdout_look", origin, {"prereg_id": prereg_id, "look": ledger.holdout_looks() + 1})
        try:
            df = data.load_holdout(prereg_id)
        except Exception as ex:
            return _err(str(ex), look_ledger_id=look["id"])
    else:
        return _err(f"cycle must be {C.DISCOVERY!r} or {C.HOLDOUT!r}")

    results = []
    for h in protocol["hypotheses"]:
        t = h["test"]
        try:
            res = _run_query(df, t)
            pw = _power(df, t.get("domain", ""), t["outcome"], t.get("group", ""))
        except Exception as ex:
            results.append({"id": h["id"], "verdict": "inconclusive", "reason": f"error: {ex}"})
            continue
        if not pw["passes"]:
            v = {"verdict": "inconclusive", "reason": f"power gate failed in cycle {cycle}: {pw['arms']}"}
        else:
            v = S.verdict(res.get("estimate"), res.get("ci_low"), res.get("ci_high"), h["prediction"], h["null"])
        cid = _calc("run_test", origin, {"cycle": cycle, "prereg_id": prereg_id, "hypothesis": h["id"], **t},
                    {**res, **v})
        results.append({"id": h["id"], "calc_id": cid, "estimate": res.get("estimate"),
                        "ci": [res.get("ci_low"), res.get("ci_high")], "prediction": h["prediction"],
                        "null": h["null"], **v})
    entry = ledger.append("result", origin, {"prereg_id": prereg_id, "cycle": cycle,
                                             "confirmatory": cycle == C.HOLDOUT, "results": results})
    return _json({"ok": True, "ledger_id": entry["id"], "cycle": cycle, "confirmatory": cycle == C.HOLDOUT,
                  "results": results})


# ---- ledger ----

def ledger_append(entry_type: str, payload_json: str, origin: str) -> str:
    """Append to the lab notebook. entry_type: anomaly, attack, hypothesis, decision, plan_update, note.
    payload_json: JSON object. Cite calc_ids for every number you mention."""
    if (e := _check_origin(origin)):
        return _err(e)
    if entry_type not in C.AGENT_ENTRY_TYPES:
        return _err(f"agents may only append {sorted(C.AGENT_ENTRY_TYPES)}")
    try:
        payload = json.loads(payload_json)
        assert isinstance(payload, dict)
    except Exception:
        return _err("payload_json must be a JSON object")
    entry = ledger.append(entry_type, origin, payload)
    out = {"ok": True, "ledger_id": entry["id"]}
    text = json.dumps(payload)
    if any(ch.isdigit() for ch in text) and "calc_" not in text:
        out["warning"] = "payload contains numbers but no calc_id; every number must come from a tool"
    return _json(out)


def ledger_read(entry_type: str = "", last_n: int = 20) -> str:
    """Read recent ledger entries, optionally filtered by type."""
    rows = ledger.read(entry_type or None)[-max(1, min(last_n, 200)):]
    return _json({"ok": True, "entries": rows, "holdout_looks": ledger.holdout_looks()})
