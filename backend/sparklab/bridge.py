"""Bridge: lab records -> SPARK UI events.

Translates what the lab already produces (ledger entries, calc records, the board, registered
protocols, and the Omnigent session that runs lab.yaml) into the event vocabulary the UI folds
(frontend/src/lib/spark/types.ts), and derives which human gate, if any, is open.

Rules kept here, in code:
- It never computes a statistic. Every number it emits is copied from a calc record or a ledger
  entry and carries its calc_id / ledger id. Formatting a proportion as a percentage is display only;
  the raw value travels alongside.
- It is read-only with respect to the lab: nothing here writes the ledger, the board or the data,
  and nothing here can see the hold-out (it only reads ledger/, prereg/ and board/ through sparklab).
- It reveals nothing about the seeded control beyond what `tools.read_board` already shows agents.

Mapping is deliberately conservative: ledger payloads written by agents are free-form JSON, so where
a UI field has no exact source (hypothesis status, attack kind) the rule is stated next to the code
and the raw payload is kept in the activity detail.
"""
import datetime as dt
import json
import re

from sparklab import config as C
from sparklab import ledger, tools

STAGES = ["surprise", "propose", "attack", "run", "keepkill"]
AGENTS = ("supervisor", "scout", "skeptic", "experimenter")
SPARKLAB_TOOLS = {"read_board", "estimate", "compute_surprise", "check_power", "check_definitions",
                  "register_prereg", "run_test", "ledger_append", "ledger_read"}
HUMAN_DECISIONS = ("keep", "kill", "revise")
GATE_ORDER = ["objective", "approve", "unseal", "decision"]

_EXP_ID = re.compile(r"\bE\d{1,3}\b|\bE_[A-Z_]+\b")


# ---------- small helpers ----------

def iso_to_ms(s: str) -> int:
    return int(dt.datetime.fromisoformat(s).timestamp() * 1000)


def actor_of(origin: str) -> str:
    if origin == "human":
        return "human"
    name = origin.split(":", 1)[1] if ":" in origin else origin
    return name if name in AGENTS else "supervisor"


def fmt_prop(x) -> str | None:
    return None if x is None else f"{100 * float(x):.1f}%"


def fmt_ratio(x) -> str | None:
    return None if x is None else f"{float(x):.2f}"


def fmt_value(x, kind: str) -> str | None:
    return fmt_ratio(x) if kind == "prevalence_ratio" else fmt_prop(x)


def short_hash(h: str | None) -> str:
    h = h or ""
    return f"{h[:4]}…{h[-4:]}" if len(h) > 12 else h


def compact(obj, limit: int = 600) -> str:
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, default=str)
    return s if len(s) <= limit else s[: limit - 1] + "…"


def payload_text(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str).lower()


def pick(payload: dict, *keys, default=None):
    for k in keys:
        v = payload.get(k)
        if v not in (None, "", [], {}):
            return v
    return default


def weight_for(*exprs: str) -> str:
    text = " ".join(e or "" for e in exprs)
    return "wt_fast" if re.search(r"\bglucose(_cat)?\b", text) else "wt_mec"


def prediction_text(pred) -> str:
    if isinstance(pred, dict) and "op" in pred:
        return f"{pred.get('op')} {pred.get('value')}"
    return str(pred) if pred is not None else ""


def read_calcs() -> list[dict]:
    if not C.CALCS_PATH.exists():
        return []
    with open(C.CALCS_PATH, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def call_code(name: str, inputs: dict) -> str:
    args = ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in inputs.items()
                     if v not in (None, "") and k not in ("cycle",))
    return f"{name}({args})"


def strip_tool_name(name: str) -> str:
    return re.sub(r"^mcp__\w+?__", "", name or "")


# ---------- the fold ----------

class Fold:
    """Walks lab records in time order and emits UI events with timestamps (epoch ms)."""

    def __init__(self):
        self.log: list[dict] = []
        self.stage_idx = 0
        self.hypotheses: dict[str, dict] = {}
        self.expectations: dict[str, dict] = {}
        self.prereg_id: str | None = None
        self.protocol: dict | None = None
        self.prereg_ts: int | None = None
        self.approved = False
        self.unsealed = False
        self.confirmatory_ts: int | None = None
        self.human_decision_ts: int | None = None
        self.human_objective: str | None = None
        self.human_pick: str | None = None   # expectation id the humans chose to pursue
        self.surprise_calcs = 0
        self.last_ts = 0

    # -- emit --
    def emit(self, at: int, event: dict):
        if event.get("kind") == "chat" and event.get("from") == "human":
            # The same human message can reach us twice: as a ledger entry (objective, pick) and as the
            # Omnigent user message that carried it. Show it once.
            key = " ".join(str(event.get("text", "")).split()).lower()
            seen = self.__dict__.setdefault("_human_chat_seen", set())
            if key in seen:
                return
            seen.add(key)
        self.last_ts = max(self.last_ts, at)
        self.log.append({"at": at, "event": event})

    def stage(self, at: int, stage: str):
        idx = STAGES.index(stage)
        if idx > self.stage_idx:
            self.stage_idx = idx
            self.emit(at, {"kind": "stage", "stage": stage})

    @property
    def current_stage(self) -> str:
        return STAGES[self.stage_idx]

    def activity(self, at: int, actor: str, type_: str, title: str, detail: str | None = None,
                 code: str | None = None, stage: str | None = None):
        ev = {"kind": "activity", "actor": actor, "stage": stage or self.current_stage,
              "type": type_, "title": title}
        if detail:
            ev["detail"] = detail
        if code:
            ev["code"] = code
        self.emit(at, ev)

    # -- board --
    def add_board(self, at: int):
        board = json.loads(tools.read_board())
        for e in board["expectations"]:
            q = e.get("query", {})
            src = e.get("source") or {}
            citation = src.get("citation") if isinstance(src, dict) else str(src)
            item = {
                "id": e["id"],
                "label": e.get("statement") or e.get("label") or e["id"],
                "domain": q.get("domain") or C.BASE_DOMAIN,
                "outcome": q.get("outcome", ""),
                "weight": weight_for(q.get("domain", ""), q.get("outcome", ""), q.get("group", "")),
                "source": (citation or "no citation yet") + (f" · {e['note']}" if e.get("note") else ""),
                "expected": fmt_value(e.get("expected"), q.get("kind", "proportion")),
                "status": "pending",
                "comparability": e.get("comparability"),
            }
            self.expectations[e["id"]] = item
            self.emit(at, {"kind": "expectation", "item": item})

    # -- ledger --
    def apply_ledger(self, e: dict):
        at = iso_to_ms(e["ts"])
        t, origin, p = e["type"], e["origin"], e.get("payload") or {}
        actor = actor_of(origin)
        summary = self._summary(t, p)
        self.emit(at, {"kind": "ledger", "id": e["id"], "type": t, "origin": origin,
                       "summary": summary, "hash": short_hash(e.get("hash"))})
        handler = getattr(self, f"_ledger_{t}", None)
        if handler:
            handler(at, actor, origin, p, e)
        else:
            self.activity(at, actor, "thought", f"{t}: {summary}", detail=compact(p))

    def _summary(self, t: str, p: dict) -> str:
        text = pick(p, "summary", "text", "title", "statement", "point", "reason", "action")
        if t == "prereg":
            return f"{p.get('prereg_id')} registered (sha256 {short_hash(p.get('protocol_hash'))})"
        if t == "approval":
            return f"{p.get('prereg_id')} approved by {p.get('by', 'human')}"
        if t == "unseal":
            return ("hold-out unsealed; SHA-256 verified" if p.get("hash_verified")
                    else "unseal refused: SHA-256 mismatch")
        if t == "seal":
            return f"hold-out cycle {p.get('cycle', C.HOLDOUT)} sealed (sha256 {short_hash(p.get('sha256'))})"
        if t == "holdout_look":
            return f"hold-out look {p.get('look')} for {p.get('prereg_id')}"
        if t == "result":
            cyc = p.get("cycle")
            return f"{'confirmatory' if p.get('confirmatory') else 'discovery'} run of {p.get('prereg_id')} (cycle {cyc})"
        if t == "gate":
            return str(p.get("action") or "gate")
        if t == "decision" and p.get("decision"):
            note = pick(p, "note", "text")
            return compact(f"decision: {p['decision']}" + (f" — {note}" if note else ""), 140)
        return compact(text if text else p, 140)

    def _ledger_seal(self, at, actor, origin, p, e):
        self.activity(at, "human", "human", "Hold-out sealed: SHA-256 recorded in the ledger",
                      detail=f"{p.get('path')} · sha256 {p.get('sha256')}", stage="surprise")

    def _ledger_note(self, at, actor, origin, p, e):
        action = p.get("action") if origin == "human" else None
        if action == "objective" and p.get("text"):
            self.human_objective = p["text"]
            self.emit(at, {"kind": "objective", "text": p["text"]})
            self.emit(at, {"kind": "chat", "from": "human", "text": p["text"]})
            self.activity(at, "human", "human", "Objective set", stage="surprise")
            return
        if action == "pick_surprise" and p.get("expectation_id"):
            self.human_pick = str(p["expectation_id"])
            text = f"Pursue {self.human_pick}." + (f" {p['text']}" if p.get("text") else "")
            self.emit(at, {"kind": "chat", "from": "human", "text": text})
            self.activity(at, "human", "human", f"Chose to pursue {self.human_pick}", detail=p.get("text"), stage="surprise")
            return
        if action == "study_created":
            self.activity(at, "human", "human", f"Study created: {p.get('title', '')}", detail=p.get("question"), stage="surprise")
            return
        if action == "message" and p.get("text"):
            self.emit(at, {"kind": "chat", "from": "human", "text": p["text"]})
            self.activity(at, "human", "human", compact(p["text"], 160))
            return
        self.activity(at, actor, "human" if actor == "human" else "thought",
                      compact(pick(p, "text", "summary", "title", default="note"), 160), detail=compact(p))

    _ledger_plan_update = _ledger_note

    def _ledger_anomaly(self, at, actor, origin, p, e):
        self.stage(at, "surprise")
        title = compact(pick(p, "title", "summary", "text", "anomaly", default="anomaly"), 160)
        self.activity(at, actor, "flag", f"Anomaly: {title}", detail=compact(p))
        # An anomaly that names board items marks them as discrepancies unless they already have a status.
        for eid in set(_EXP_ID.findall(json.dumps(p, ensure_ascii=False))):
            if eid in self.expectations and self.expectations[eid]["status"] == "pending":
                self._patch_expectation(at, eid, {"status": "discrepancy"})

    def _ledger_hypothesis(self, at, actor, origin, p, e):
        self.stage(at, "propose")
        hid = str(pick(p, "id", "hypothesis", "hypothesis_id", default=f"H-{e['id']}"))
        item = {"id": hid,
                "kind": "artifact" if "measurement" in hid.lower() else "substantive",
                "title": compact(pick(p, "title", "statement", "text", default=hid), 90),
                "statement": compact(pick(p, "statement", "text", "title", default=""), 400),
                "prediction": prediction_text(pick(p, "prediction", "predicts")),
                "origin": pick(p, "origin", default=origin)}
        self._upsert_hypothesis(at, item)
        self.activity(at, actor, "thought", f"Hypothesis {hid} proposed", detail=compact(p))

    def _ledger_attack(self, at, actor, origin, p, e):
        text = compact(pick(p, "text", "summary", "attack", "point", "issue", "title", default=""), 300)
        call = str(pick(p, "call", "verdict", "stance", "severity", default="")).lower()
        check = str(pick(p, "check", "kind", "type", default="")).lower()
        blob = payload_text(p)
        kind = ("power" if "power" in check or "power" in blob[:400] else
                "definition" if "defin" in check or "defin" in blob[:400] else
                "confound" if "confound" in check or "confound" in blob[:400] else "alternative")
        # The skeptic's call describes the TARGET: holds -> the target survives this check.
        passed = call in ("holds", "withdraw", "withdrawn", "refuted", "pass", "passed")
        targets = [h for h in self.hypotheses if h.lower() in blob]
        exp_ids = [x for x in set(_EXP_ID.findall(json.dumps(p, ensure_ascii=False))) if x in self.expectations]
        if targets:
            self.stage(at, "attack")
            for hid in targets:
                self.emit(at, {"kind": "attack", "hypothesisId": hid,
                               "attack": {"kind": kind, "text": text or f"{check or kind} check", "passed": passed}})
                if self.hypotheses[hid].get("status") in (None, "proposed"):
                    self._upsert_hypothesis(at, {"id": hid, "status": "under_attack"})
        for eid in exp_ids:
            if kind == "definition" and (call in ("fatal", "error") or re.search(r"wrong|error|disagree|mix", blob)):
                self._patch_expectation(at, eid, {"status": "definition_error",
                                                  "note": text or "definition error (Skeptic)"})
        title = f"Attack: {text}" if text else f"Attack ({kind})"
        self.activity(at, actor, "flag", compact(title, 160), detail=compact(p))

    def _ledger_gate(self, at, actor, origin, p, e):
        self.stage(at, "attack" if self.hypotheses else "surprise")
        failures = p.get("failures") or []
        for f in failures:
            hid = f.get("hypothesis")
            arms = f.get("arms") or {}
            n = min((a.get("n_unweighted", 0) for a in arms.values()), default=None) if arms else None
            if hid:
                self._upsert_hypothesis(at, {"id": hid, "status": "blocked",
                                             "cellN": str(n) if n is not None else None,
                                             "outcomeNote": f"Rejected by the {f.get('gate')} gate (ledger {e['id']})."})
                self.emit(at, {"kind": "attack", "hypothesisId": hid, "attack": {
                    "kind": "power" if f.get("gate") == "power" else "definition",
                    "text": f"{f.get('gate')} gate failed" + (f": min unweighted n = {n} < {C.MIN_CELL_N}" if n is not None else ""),
                    "passed": False}})
        self.activity(at, actor, "flag", compact(p.get("action") or "gate", 160), detail=compact(p))

    def _ledger_prereg(self, at, actor, origin, p, e):
        self.stage(at, "run")
        pid = p["prereg_id"]
        self.prereg_id, self.prereg_ts, self.approved = pid, at, False
        protocol = None
        try:
            protocol = ledger.load_protocol(pid)
        except Exception:
            protocol = None
        self.protocol = protocol
        patch = {"id": pid, "status": "registered", "hash": f"sha256:{p.get('protocol_hash', '')}",
                 "commit": (p.get("git_commit") or "")[:12], "path": p.get("path"), "ledgerId": e["id"],
                 "approvedBy": None, "holdoutHash": None}
        if protocol:
            hyps = protocol.get("hypotheses", [])
            rivals = protocol.get("rivals", [])
            first = hyps[0] if hyps else {}
            t = first.get("test", {})
            patch.update({
                "title": protocol.get("title"),
                "question": protocol.get("question"),
                "hypothesisId": " / ".join(h.get("id", "?") for h in hyps),
                "rivalId": " / ".join(r.get("id", "?") for r in rivals) or "—",
                "domain": f"({C.BASE_DOMAIN}) and ({t.get('domain') or 'True'})",
                "outcome": t.get("outcome", ""),
                "comparison": t.get("group") and f"{t['group']}  vs  not ({t['group']})" or "proportion within domain",
                "weight": weight_for(t.get("domain", ""), t.get("outcome", ""), t.get("group", "")),
                "estimator": ("prevalence_ratio (log-PR, independent-SE approximation)" if t.get("kind") == "prevalence_ratio"
                              else "taylor_prop (weighted proportion, Taylor linearization over SDMVSTRA/SDMVPSU)"),
                "decisionRule": "sparklab.stats.verdict: supported / incompatible / inconclusive against each pre-registered prediction and null",
                "tests": [{"id": h.get("id"), "kind": h.get("test", {}).get("kind"),
                           "domain": h.get("test", {}).get("domain", ""), "outcome": h.get("test", {}).get("outcome", ""),
                           "group": h.get("test", {}).get("group", ""), "prediction": prediction_text(h.get("prediction")),
                           "null": h.get("null"), "origin": h.get("origin")} for h in hyps],
                "rivals": [{"id": r.get("id"), "statement": r.get("statement"), "floor": r.get("floor")} for r in rivals],
            })
            for h in hyps:
                hid = h.get("id", "?")
                self._upsert_hypothesis(at, {
                    "id": hid, "kind": "artifact" if "measurement" in hid.lower() else "substantive",
                    "title": compact(h.get("statement") or hid, 90), "statement": compact(h.get("statement", ""), 400),
                    "prediction": prediction_text(h.get("prediction")) + (f" (null {h.get('null')})" if h.get("null") is not None else ""),
                    "origin": h.get("origin"), "status": "survives",
                    "outcomeNote": f"Pre-registered in {pid}."})
            for r in rivals:
                rid = r.get("id", "H_measurement_error")
                self._upsert_hypothesis(at, {
                    "id": rid, "kind": "artifact", "title": compact(r.get("statement") or rid, 90),
                    "statement": compact(r.get("statement", ""), 400),
                    "prediction": compact(f"floor: {r.get('floor')}" if r.get("floor") else "", 300),
                    "origin": r.get("origin"), "status": "rival", "outcomeNote": f"Declared rival in {pid}."})
        self.emit(at, {"kind": "prereg", "patch": patch})
        self.activity(at, actor, "tool_result", f"{pid} registered: protocol hash + git commit",
                      detail=f"sha256 {p.get('protocol_hash')} · commit {p.get('git_commit')}", code=f"register_prereg(...) -> {pid}")

    def _ledger_approval(self, at, actor, origin, p, e):
        self.stage(at, "run")
        if p.get("prereg_id") == self.prereg_id and origin == "human":
            self.approved = True
            self.emit(at, {"kind": "prereg", "patch": {"status": "approved", "approvedBy": p.get("by", "human")}})
        self.activity(at, "human", "human", f"Approved {p.get('prereg_id')} ({p.get('by', 'human')})",
                      detail=f"protocol hash {p.get('protocol_hash')}")

    def _ledger_unseal(self, at, actor, origin, p, e):
        self.stage(at, "run")
        if p.get("hash_verified"):
            self.unsealed = True
            if self.prereg_id:
                self.emit(at, {"kind": "prereg", "patch": {"status": "unsealed",
                                                           "holdoutHash": f"sha256:{p.get('sha256')} ✓ verified"}})
            self.activity(at, "human", "human", f"Unsealed hold-out cycle {C.HOLDOUT}: SHA-256 verified",
                          detail=f"sha256 {p.get('sha256')} · {p.get('rows')} rows · by {p.get('by', 'human')}")
        else:
            self.activity(at, "human", "flag", "Unseal refused: SHA-256 mismatch",
                          detail=f"expected {p.get('expected')} · actual {p.get('actual')}")

    def _ledger_holdout_look(self, at, actor, origin, p, e):
        self.stage(at, "run")
        self.activity(at, actor, "tool_call", f"Hold-out look {p.get('look')} of {C.MAX_HOLDOUT_LOOKS}",
                      code=f"run_test({p.get('prereg_id')!r}, cycle={C.HOLDOUT!r})")

    def _ledger_result(self, at, actor, origin, p, e):
        self.stage(at, "run")
        results = p.get("results") or []
        pid = p.get("prereg_id")
        kinds = {h.get("id"): h.get("test", {}).get("kind", "proportion")
                 for h in (self.protocol or {}).get("hypotheses", []) if isinstance(h, dict)}
        lines = [f"{r.get('id')}: {r.get('verdict')} ({r.get('reason')}) · {r.get('calc_id')}" for r in results]
        if p.get("confirmatory"):
            self.confirmatory_ts = at
            if pid == self.prereg_id:
                self.emit(at, {"kind": "prereg", "patch": {"status": "tested"}})
            for r in results:
                k = kinds.get(r.get("id"), "proportion")
                ci = r.get("ci") or [None, None]
                self.emit(at, {"kind": "verdict", "item": {
                    "preregId": pid, "hypothesisId": r.get("id"), "label": r.get("verdict", "inconclusive"),
                    "estimate": fmt_value(r.get("estimate"), k) or "—",
                    "ci": [fmt_value(ci[0], k) or "—", fmt_value(ci[1], k) or "—"],
                    "raw": {"estimate": r.get("estimate"), "ci": ci, "null": r.get("null"),
                            "prediction": r.get("prediction"), "kind": k},
                    "calcId": r.get("calc_id"), "ledgerId": e["id"],
                    "prediction": prediction_text(r.get("prediction")), "null": r.get("null"),
                    "interpretation": r.get("reason", ""),
                }})
            self.activity(at, actor, "tool_result", f"Confirmatory run of {pid} on the hold-out (one look)",
                          detail="\n".join(lines), code=f"run_test({pid!r}, cycle={C.HOLDOUT!r})")
            self.stage(at, "keepkill")
        else:
            self.activity(at, actor, "tool_result", f"Discovery run of {pid} (cycle {C.DISCOVERY}, not confirmatory)",
                          detail="\n".join(lines), code=f"run_test({pid!r}, cycle={C.DISCOVERY!r})")

    def _ledger_decision(self, at, actor, origin, p, e):
        d = str(p.get("decision", "")).lower()
        if origin == "human" and d in HUMAN_DECISIONS:
            self.stage(at, "keepkill")
            self.human_decision_ts = at
            note = pick(p, "note", "text")
            self.emit(at, {"kind": "decision", "decision": d, "note": note})
            self.emit(at, {"kind": "chat", "from": "human", "text": f"{d.capitalize()}." + (f" {note}" if note else "")})
            self.activity(at, "human", "human", f"Decision: {d}", detail=note)
            return
        title = compact(pick(p, "point", "text", "summary", "title", "ruling", default="decision"), 160)
        self.activity(at, actor, "human" if actor == "human" else "thought", f"Ruling: {title}", detail=compact(p))

    # -- calcs --
    def apply_calc(self, c: dict):
        at = iso_to_ms(c["ts"])
        kind, origin, inputs, res = c["kind"], c.get("origin", "agent:supervisor"), c.get("inputs", {}), c.get("result", {})
        actor = actor_of(origin)
        cid = c["calc_id"]
        if kind == "surprise":
            self.stage(at, "surprise")
            self.surprise_calcs += 1
            eid = inputs.get("expectation_id") or res.get("expectation_id")
            est_kind = "prevalence_ratio" if inputs.get("group") or inputs.get("kind") == "prevalence_ratio" else "proportion"
            obs = fmt_value(res.get("estimate"), est_kind)
            sur = res.get("surprise")
            status = "discrepancy" if sur else ("consistent" if sur is False else "pending")
            if eid:
                patch = {"observed": obs, "calcId": cid, "status": status}
                ci = res.get("ci") or [res.get("ci_low"), res.get("ci_high")]
                if ci and ci[0] is not None:
                    patch["observedCi"] = [fmt_value(ci[0], est_kind), fmt_value(ci[1], est_kind)]
                if res.get("message"):
                    patch["note"] = res["message"]
                self._patch_expectation(at, eid, patch)
            title = (f"compute_surprise({eid}) → {obs or 'no estimate'}"
                     + (" · surprise" if sur else " · consistent" if sur is False else "")
                     + f" · {cid}")
            self.activity(at, actor, "flag" if sur else "tool_result", title,
                          detail=res.get("message") or (f"95% CI {patch.get('observedCi')}" if eid and patch.get("observedCi") else None),
                          code=call_code("compute_surprise", {"expectation_id": eid}))
            return
        if kind == "estimate":
            est_kind = "prevalence_ratio" if inputs.get("group") else "proportion"
            lo, hi = fmt_value(res.get("ci_low"), est_kind), fmt_value(res.get("ci_high"), est_kind)
            label = "PR" if est_kind == "prevalence_ratio" else "share"
            title = f"estimate → {label} {fmt_value(res.get('estimate'), est_kind) or '—'}"
            if lo and hi:
                title += f" (95% CI {lo}–{hi})"
            title += f" · {cid}"
            detail = f"unweighted n = {res.get('n_unweighted')}, events = {res.get('n_events')}, weight {res.get('weight')}" \
                if est_kind == "proportion" and res.get("n_unweighted") is not None else res.get("warning")
            self.activity(at, actor, "tool_result", title, detail=detail, code=call_code("estimate", inputs))
            return
        if kind == "power":
            arms = res.get("arms", {})
            ns = ", ".join(f"{k} n={v.get('n_unweighted')}" for k, v in arms.items())
            ok = res.get("passes")
            self.activity(at, actor, "flag" if ok is False else "tool_result",
                          f"check_power → {'passes' if ok else 'REJECTED'} ({ns}; MIN_CELL_N = {res.get('min_cell_n', C.MIN_CELL_N)}) · {cid}",
                          detail=res.get("warning"), code=call_code("check_power", inputs))
            return
        if kind == "run_test":
            k = "prevalence_ratio" if inputs.get("group") or inputs.get("kind") == "prevalence_ratio" else "proportion"
            lo, hi = fmt_value(res.get("ci_low"), k), fmt_value(res.get("ci_high"), k)
            self.activity(at, actor, "tool_result",
                          f"run_test {inputs.get('hypothesis')} (cycle {inputs.get('cycle')}) → {res.get('verdict')}: "
                          f"{fmt_value(res.get('estimate'), k) or '—'}" + (f" (95% CI {lo}–{hi})" if lo and hi else "") + f" · {cid}",
                          detail=res.get("reason"), code=call_code("run_test", {"prereg_id": inputs.get("prereg_id"), "cycle": inputs.get("cycle")}))
            return
        self.activity(at, actor, "tool_result", f"{kind} · {cid}", detail=compact(res), code=call_code(kind, inputs))

    # -- omnigent items --
    def apply_omnigent_item(self, item: dict, actor: str):
        at = int(float(item.get("created_at", 0)) * 1000)
        t = item.get("type")
        if t == "message":
            text = " ".join(part.get("text", "") for part in item.get("content", []) if isinstance(part, dict)).strip()
            if not text:
                return
            role = item.get("role")
            if role == "user":
                if actor == "supervisor":  # a human talking to the Supervisor
                    if self.human_objective is None:
                        self.human_objective = text
                        self.emit(at, {"kind": "objective", "text": text})
                        self.activity(at, "human", "human", "Objective sent to the Supervisor", detail=compact(text, 300))
                    else:
                        self.activity(at, "human", "human", compact(text, 160))
                    self.emit(at, {"kind": "chat", "from": "human", "text": text})
                else:  # the Supervisor briefing a sub-agent
                    self.activity(at, "supervisor", "handoff", f"Brief to {actor}: {compact(text, 120)}", detail=compact(text, 600))
                return
            self.emit(at, {"kind": "chat", "from": actor, "text": text})
            self.activity(at, actor, "thought", compact(text.splitlines()[0] if text else "", 160),
                          detail=compact(text, 600) if len(text) > 160 else None)
            return
        if t == "function_call":
            name = strip_tool_name(item.get("name", ""))
            try:
                args = json.loads(item.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {"raw": item.get("arguments")}
            if name in ("sys_session_send", "sys_call_async", "sys_call"):
                # Omnigent system calls: a message to a sub-agent is a handoff; an async call of one of
                # our tools is just that tool call.
                target = str(pick(args, "agent", "session", "name", "tool", "target", default="sub-agent"))
                inner = pick(args, "args", "arguments", "params", "input", default={})
                if isinstance(inner, str):
                    try:
                        inner = json.loads(inner)
                    except json.JSONDecodeError:
                        inner = {"raw": inner}
                if target in AGENTS:
                    task = compact(pick(args, "message", "prompt", "text", "task", default=""), 200)
                    self.activity(at, actor, "handoff", f"Delegated to {target}" + (f": {task}" if task else ""),
                                  detail=compact(args, 600))
                    return
                name, args = strip_tool_name(target), (inner if isinstance(inner, dict) else {"input": inner})
            if name in SPARKLAB_TOOLS or name.startswith(("compute_", "check_", "estimate", "register_", "run_")):
                args = {k: v for k, v in args.items() if k != "origin"}
                self.activity(at, actor, "tool_call", f"{name}(…)", code=call_code(name, args))
            return
        if t == "function_call_output":
            name = strip_tool_name(item.get("name", "") or item.get("tool_name", ""))
            out = item.get("output")
            if isinstance(out, list):
                out = " ".join(p.get("text", "") for p in out if isinstance(p, dict))
            if not isinstance(out, str):
                return
            if "check_definitions" in (name or "") or '"clean"' in out[:200]:
                try:
                    d = json.loads(out)
                except json.JSONDecodeError:
                    d = None
                if isinstance(d, dict) and "clean" in d:
                    eid = d.get("expectation_id")
                    issues = d.get("issues") or []
                    errors = [i for i in issues if i.get("severity") == "error"]
                    if eid and eid in self.expectations:
                        if errors:
                            self._patch_expectation(at, eid, {"status": "definition_error",
                                                              "note": compact(errors[0].get("issue", "definition error"), 200)})
                        elif self.expectations[eid].get("status") == "definition_error":
                            pass
                    self.activity(at, actor, "flag" if errors else "tool_result",
                                  f"check_definitions({eid or '…'}) → {'issues found' if errors else 'clean'}",
                                  detail=compact("; ".join(i.get("issue", "") for i in issues), 400) or None)
            return

    def apply_omnigent_children(self, children: list[dict], parent_status: str | None, gate: str | None):
        at = self.last_ts or int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
        seen = {}
        for ch in sorted(children, key=lambda c: c.get("updated_at") or c.get("created_at") or 0):
            agent = ch.get("tool") or ch.get("agent_name") or ""
            if agent not in AGENTS:
                continue
            seen[agent] = ch
        for agent, ch in seen.items():
            busy = bool(ch.get("busy")) or ch.get("current_task_status") in ("running", "waiting", "launching")
            status = "working" if busy else ("done" if ch.get("current_task_status") == "completed" else "idle")
            self.emit(at, {"kind": "agent", "agent": agent, "status": status,
                           "task": ch.get("session_name") or ch.get("title")})
        if parent_status:
            sup = ("working" if parent_status in ("running", "waiting", "launching", "streaming")
                   else "waiting" if gate else "idle")
            self.emit(at, {"kind": "agent", "agent": "supervisor", "status": sup,
                           "task": {"working": "Coordinating the loop", "waiting": "Waiting for a human gate",
                                    "idle": "Idle"}[sup]})

    # -- state helpers --
    def _upsert_hypothesis(self, at: int, item: dict):
        new = item["id"] not in self.hypotheses
        cur = self.hypotheses.setdefault(item["id"], {"id": item["id"]})
        patch = {k: v for k, v in item.items() if v is not None}
        if new and "status" not in patch:
            patch["status"] = "proposed"
        cur.update(patch)
        self.emit(at, {"kind": "hypothesis", "item": patch})

    def _patch_expectation(self, at: int, eid: str, patch: dict):
        cur = self.expectations.setdefault(eid, {"id": eid})
        cur.update(patch)
        self.emit(at, {"kind": "expectation", "item": {"id": eid, **patch}})

    # -- gates --
    def derive_gate(self, has_session_input: bool, session_idle: bool | None = None) -> str | None:
        """Which human action the lab is waiting for, from the ledger (plus whether the Supervisor
        has received any instruction and whether its session is idle)."""
        if self.prereg_id is None:
            if not (self.human_objective or has_session_input):
                return "objective"
            # The board has been evaluated, no hypothesis exists yet and the Supervisor is not busy:
            # the humans choose which discrepancy to pursue.
            if (self.surprise_calcs > 0 and not self.hypotheses and self.human_pick is None
                    and (session_idle is None or session_idle)):
                return "pick-surprise"
            return None
        if not self.approved:
            return "approve"
        if not self.unsealed:
            return "unseal"
        if self.confirmatory_ts is None:
            return None
        if self.human_decision_ts is None or self.human_decision_ts < self.confirmatory_ts:
            return "decision"
        return None

    @property
    def needs_confirmation(self) -> bool:
        """Approved and unsealed, but the single hold-out run has not happened: the humans tell the
        Supervisor to go ahead."""
        return self.prereg_id is not None and self.approved and self.unsealed and self.confirmatory_ts is None

    @property
    def finished(self) -> bool:
        return (self.confirmatory_ts is not None and self.human_decision_ts is not None
                and self.human_decision_ts >= self.confirmatory_ts)


# ---------- assembling a snapshot ----------

def dedupe_items(items: list[dict]) -> list[dict]:
    """Drop exact repeats of a persisted tool call/output (same call_id, tool, arguments and second).
    Distinct parallel calls of the same tool keep their own call_id and are all kept."""
    seen, out = set(), []
    for it in items:
        if it.get("type") in ("function_call", "function_call_output"):
            key = (it.get("type"), it.get("call_id"), it.get("name"), it.get("created_at"),
                   str(it.get("arguments") or it.get("output"))[:200])
            if key in seen:
                continue
            seen.add(key)
        out.append(it)
    return out


def lab_status() -> dict:
    ok, msg = ledger.verify()
    seals = ledger.read("seal")
    unseals = [u for u in ledger.read("unseal") if u["payload"].get("hash_verified")]
    pre = ledger.read("prereg")
    return {
        "root": str(C.ROOT),
        "discovery": {"cycle": C.DISCOVERY, "label": C.CYCLE_LABEL[C.DISCOVERY],
                      "processed": (C.PROCESSED_DIR / f"nhanes_{C.DISCOVERY}.pkl").exists()},
        "holdout": {"cycle": C.HOLDOUT, "label": C.CYCLE_LABEL[C.HOLDOUT], "sealed": bool(seals),
                    "sealed_sha256": seals[-1]["payload"].get("sha256") if seals else None,
                    "unsealed": bool(unseals), "looks": ledger.holdout_looks(), "max_looks": C.MAX_HOLDOUT_LOOKS},
        "ledger": {"entries": len(ledger.read()), "intact": ok, "message": msg,
                   "calcs": len(read_calcs())},
        "preregs": [{"prereg_id": p["payload"]["prereg_id"], "ledger_id": p["id"], "ts": p["ts"],
                     "approved": ledger.approval_for(p["payload"]["prereg_id"]) is not None} for p in pre],
        "thresholds": {"hba1c": [C.HBA1C_PREDIABETES, C.HBA1C_DIABETES],
                       "glucose": [C.GLUCOSE_PREDIABETES, C.GLUCOSE_DIABETES], "min_cell_n": C.MIN_CELL_N},
    }


def snapshot(omni: dict | None = None, root=None) -> dict:
    """Fold ledger + calcs (+ an Omnigent session snapshot, if given) into UI events.

    omni = {"session": {...}, "items": [...], "children": [...], "child_items": {child_id: [...]}}
    root: lab root to read (default: the one sparklab.config resolves).
    """
    if root is not None:
        with C.use_root(root):
            return snapshot(omni)
    f = Fold()
    rows = ledger.read()
    calcs = read_calcs()
    first_ts = min([iso_to_ms(r["ts"]) for r in rows] + [iso_to_ms(c["ts"]) for c in calcs]
                   + [int(float(i.get("created_at", 0)) * 1000) for i in (omni or {}).get("items", []) if i.get("created_at")]
                   or [int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)])
    f.add_board(first_ts)
    records: list[tuple[int, int, str, object]] = []
    for r in rows:
        records.append((iso_to_ms(r["ts"]), 1, "ledger", r))
    for c in calcs:
        records.append((iso_to_ms(c["ts"]), 0, "calc", c))
    has_input = False
    if omni:
        for it in dedupe_items(omni.get("items", [])):
            if it.get("type") == "message" and it.get("role") == "user":
                has_input = True
            records.append((int(float(it.get("created_at", 0)) * 1000), 2, "omni", ("supervisor", it)))
        child_actor = {ch["id"]: ch.get("tool") for ch in omni.get("children", [])}
        for cid, items in (omni.get("child_items") or {}).items():
            actor = child_actor.get(cid)
            if actor not in AGENTS:
                continue
            for it in dedupe_items(items):
                records.append((int(float(it.get("created_at", 0)) * 1000), 2, "omni", (actor, it)))
    records.sort(key=lambda r: (r[0], r[1]))
    for ts, _, kind, obj in records:
        if kind == "ledger":
            f.apply_ledger(obj)
        elif kind == "calc":
            f.apply_calc(obj)
        else:
            f.apply_omnigent_item(obj[1], obj[0])
    session_status = (omni.get("session") or {}).get("status") if omni else None
    session_idle = None if session_status is None else session_status in ("idle", "failed")
    gate = f.derive_gate(has_input, session_idle)
    if omni:
        f.apply_omnigent_children(omni.get("children", []), session_status, gate)
    return {
        "events": f.log,
        "gate": gate,
        "finished": f.finished,
        "stage": f.current_stage,
        "prereg_id": f.prereg_id,
        "objective": f.human_objective,
        "pick": f.human_pick,
        "needs_confirmation": f.needs_confirmation,
        "status": lab_status(),
        "session": _session_summary(omni),
    }


def _session_summary(omni: dict | None) -> dict | None:
    if not omni or not omni.get("session"):
        return None
    s = omni["session"]
    return {"id": s.get("id"), "agent_name": s.get("agent_name"), "status": s.get("status"),
            "title": s.get("title"), "workspace": s.get("workspace"), "updated_at": s.get("updated_at"),
            "children": [{"id": c.get("id"), "agent": c.get("tool"), "busy": c.get("busy"),
                          "task_status": c.get("current_task_status"), "name": c.get("session_name")}
                         for c in omni.get("children", [])]}
