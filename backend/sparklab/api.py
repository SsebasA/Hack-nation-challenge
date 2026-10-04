"""SPARK Lab HTTP API for the web UI (frontend/).

    pip install -e "backend/[api]"
    python -m sparklab.api                       # http://127.0.0.1:8787 (docs at /docs)

Environment:
    SPARK_API_HOST / SPARK_API_PORT        bind address (default 127.0.0.1:8787)
    SPARK_OMNIGENT_URL                     local Omnigent server (default http://127.0.0.1:6767)
    SPARK_OMNIGENT_SESSION                 pin the default study's session id (otherwise matched by
                                           label / workspace, see Omni.pick_session_for)
    SPARK_UI_ORIGIN                        extra CORS origin (default allows localhost:3000)
    SPARK_LAB_MODE=fast                    new sessions run the fast-mode spec (sparklab.fastlab)
    SPARK_FAST_MODEL                       with fast mode: pin this model on every executor

Studies. The original lab (backend/) is the default study; more live in backend/studies/<id>/
(sparklab.studies). Every study-scoped route is under /studies/{study_id}/...; the unprefixed
routes are aliases for the default study.

What it exposes, and what it does not:
- Read endpoints over what a lab records: board, ledger, calcs, registered protocols, status.
- GET .../state and GET .../events (SSE): the lab folded into UI events (sparklab.bridge), including
  the Omnigent session that runs lab.yaml for that study (messages, tool calls, sub-agent status).
- Human writes, all with origin "human" through sparklab.ledger (the hash chain is never written by
  hand): POST .../human/ledger (twin of `python -m sparklab.ledger add`), POST .../pick (which
  discrepancy to pursue), POST .../approve and POST .../unseal. The last two keep the CLIs' friction:
  the human must type the first 8 characters of the protocol's / sealed file's SHA-256.
- Omnigent control for a study: POST .../session uploads lab.yaml as the agent, binds it to the local
  host and sends the objective; POST .../session/message talks to the Supervisor. Starting a study's
  session also makes it the *active* lab for the shared runner (sparklab.studies.set_active).
- Nothing here computes a statistic or reads the hold-out, and agents never get these endpoints:
  they have no network or shell tools (lab.yaml declares no os_env).
"""
import asyncio
import io
import json
import os
import tarfile
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from sparklab import bridge, fastlab, studies
from sparklab import config as C
from sparklab import ledger, tools
from sparklab import unseal as unseal_mod

OMNI_URL = os.environ.get("SPARK_OMNIGENT_URL", "http://127.0.0.1:6767").rstrip("/")
PINNED_SESSION = os.environ.get("SPARK_OMNIGENT_SESSION") or None
AGENT_NAME = "spark_lab"
STUDY_LABEL = "spark.study"
POLL_SECONDS = 0.7          # file change detection
OMNI_REFRESH_SECONDS = 8.0  # safety-net refetch when the Omnigent stream is quiet
HEARTBEAT_SECONDS = 15.0
HASH_PREFIX_LEN = 8         # same friction as the CLIs


# ---------- Omnigent access ----------

class Omni:
    def __init__(self, base: str):
        self.base = base
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=30.0))
        self.reachable: bool | None = None
        self.error: str | None = None

    async def close(self):
        await self.http.aclose()

    async def get(self, path: str, **params):
        r = await self.http.get(f"{self.base}/v1{path}", params=params or None)
        r.raise_for_status()
        return r.json()

    async def health(self) -> bool:
        try:
            r = await self.http.get(f"{self.base}/health", timeout=3.0)
            self.reachable = r.status_code == 200
            self.error = None
        except Exception as ex:  # server down is a normal state for the UI
            self.reachable, self.error = False, str(ex)
        return bool(self.reachable)

    async def list_sessions(self) -> list[dict]:
        data = await self.get("/sessions", agent_name=AGENT_NAME, limit=100, sort_by="updated_at", order="desc")
        return data.get("data", [])

    async def pick_session_for(self, study: dict) -> dict | None:
        """The study's session: by label (sessions the UI started), then by workspace (a CLI-started
        `omnigent run lab.yaml` in the study folder; the default study also accepts the repo root), or
        the pinned id for the default study. Never a session of another checkout: a message from the
        UI must not reach a Supervisor working on a different lab."""
        if study["is_default"] and PINNED_SESSION:
            return await self.get(f"/sessions/{PINNED_SESSION}")
        sessions = [s for s in await self.list_sessions() if not s.get("archived")]
        root = str(study["root"])
        for s in sessions:
            if (s.get("labels") or {}).get(STUDY_LABEL) == study["id"]:
                return s
        roots = {root} | ({str(Path(root).parent)} if study["is_default"] else set())
        for s in sessions:
            if s.get("workspace") in roots and not (s.get("labels") or {}).get(STUDY_LABEL):
                return s
        return None

    async def all_items(self, session_id: str, cap: int = 3000) -> list[dict]:
        out, after = [], None
        while len(out) < cap:
            params = {"limit": 500, "order": "asc"}
            if after:
                params["after"] = after
            page = await self.get(f"/sessions/{session_id}/items", **params)
            data = page.get("data", [])
            out.extend(data)
            if not page.get("has_more") or not data:
                break
            after = page.get("last_id") or data[-1].get("id")
        return out

    async def snapshot_for(self, study: dict) -> dict | None:
        session = await self.pick_session_for(study)
        if not session:
            return None
        sid = session["id"]
        session = await self.get(f"/sessions/{sid}")  # fresh status
        items = await self.all_items(sid)
        children = (await self.get(f"/sessions/{sid}/child_sessions")).get("data", [])
        child_items = {}
        for ch in children:
            if ch.get("tool") in bridge.AGENTS:
                try:
                    child_items[ch["id"]] = await self.all_items(ch["id"])
                except httpx.HTTPError:
                    child_items[ch["id"]] = []
        return {"session": session, "items": items, "children": children, "child_items": child_items}

    async def tail(self, session_id: str, on_event):
        """Live-tail one session's SSE stream; call on_event(type) for events that change the UI."""
        async with self.http.stream("GET", f"{self.base}/v1/sessions/{session_id}/stream",
                                    timeout=httpx.Timeout(10.0, read=None)) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw in ("", "[DONE]"):
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                t = ev.get("type", "")
                if t.startswith(("response.output_item.done", "session.status", "session.child_session",
                                 "turn.", "response.completed", "response.elicitation", "session.created")):
                    on_event(t)

    # -- control --
    async def pick_host_id(self, harness: str = "claude-sdk") -> str | None:
        """The local host that will run the session: online, preferably with the lab's harness configured."""
        try:
            body = await self.get("/hosts")
        except httpx.HTTPError:
            return None
        hosts = body.get("hosts") if isinstance(body, dict) else None
        if hosts is None:
            hosts = body.get("data", []) if isinstance(body, dict) else []
        online = [h for h in hosts if h.get("online") or h.get("status") in ("online", "connected")]
        ready = [h for h in online if (h.get("configured_harnesses") or {}).get(harness) is True]
        for pool in (ready, online, hosts):
            if pool:
                return pool[0].get("host_id") or pool[0].get("id")
        return None

    async def create_session(self, bundle: bytes, *, title: str, labels: dict, workspace: str, host_id: str | None) -> dict:
        metadata = {"title": title, "labels": labels, "workspace": workspace}
        if host_id:
            metadata["host_id"] = host_id
        r = await self.http.post(f"{self.base}/v1/sessions", data={"metadata": json.dumps(metadata)},
                                 files={"bundle": ("agent.tar.gz", bundle, "application/gzip")}, timeout=120.0)
        if r.status_code >= 400:
            msg = f"Omnigent refused the session: {r.status_code} {r.text[:500]}"
            if "resolved callable" in r.text or "could not be imported" in r.text:
                msg += (" — the Omnigent server imports `sparklab.tools` from its own Python environment, so it must run "
                        "from the same venv as this backend: `omnigent stop`, then `source .venv/bin/activate && "
                        "pip install -e backend && omnigent start`, and retry.")
            raise HTTPException(502, msg)
        sid = r.json().get("session_id") or r.json().get("id")
        return await self.get(f"/sessions/{sid}")

    async def send_message(self, session_id: str, text: str) -> dict:
        body = {"type": "message", "data": {"role": "user", "content": [{"type": "input_text", "text": text}]}}
        r = await self.http.post(f"{self.base}/v1/sessions/{session_id}/events", json=body, timeout=30.0)
        if r.status_code >= 400:
            raise HTTPException(502, f"Omnigent refused the message: {r.status_code} {r.text[:500]}")
        return r.json() if r.content else {"queued": True}


def build_agent_bundle() -> bytes:
    """lab.yaml -> gzipped agent tarball, the way `omnigent run lab.yaml` uploads it."""
    try:
        from omnigent.spec import materialize_bundle
    except ImportError as ex:  # pragma: no cover - depends on the venv
        raise HTTPException(503, "omnigent is not installed in the API's environment; "
                                 "`pip install omnigent` in the same venv (see RUNBOOK)") from ex
    with tempfile.TemporaryDirectory() as tmp:
        yaml_path = C.PACKAGE_ROOT / "lab.yaml"
        if fastlab.mode() == "fast":
            yaml_path = fastlab.write_fast_spec(Path(tmp) / "lab.yaml", os.environ.get("SPARK_FAST_MODEL") or None)
        bundle_dir = materialize_bundle(yaml_path, Path(tmp) / "bundle")
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            for fp in sorted(bundle_dir.rglob("*")):
                if fp.is_file():
                    tf.add(str(fp), arcname=str(fp.relative_to(bundle_dir)))
        return buf.getvalue()


# ---------- per-study watcher: one folded snapshot, shared by all SSE clients ----------

class LabWatcher:
    def __init__(self, study: dict, omni: Omni):
        self.study = study
        self.root = Path(study["root"])
        self.omni = omni
        self.version = 0
        self.snapshot: dict = {}
        self.changed = asyncio.Condition()
        self._dirty_files = True
        self._dirty_omni = True
        self._files_sig = None
        self._omni_snapshot: dict | None = None
        self._omni_fetched_at = 0.0
        self._last_omni_body = None
        self._tail_task: asyncio.Task | None = None
        self._tail_session: str | None = None
        self._task: asyncio.Task | None = None

    def mark_dirty(self, what: str = "files"):
        if what == "omni":
            self._dirty_omni = True
        else:
            self._dirty_files = True

    def _files_signature(self):
        sig = []
        with C.use_root(self.root):
            for p in (C.LEDGER_PATH, C.CALCS_PATH, C.BOARD_PATH, C.CONTROL_PATH):
                try:
                    st = p.stat()
                    sig.append((str(p), st.st_size, st.st_mtime_ns))
                except FileNotFoundError:
                    sig.append((str(p), None, None))
            try:
                sig.append(tuple(sorted(x.name for x in C.PREREG_DIR.iterdir())))
            except FileNotFoundError:
                sig.append(())
        sig.append(studies.active_id())
        return tuple(sig)

    async def _refresh_omni(self, force: bool = False):
        now = time.monotonic()
        if not force and not self._dirty_omni and now - self._omni_fetched_at < OMNI_REFRESH_SECONDS:
            return
        self._dirty_omni = False
        self._omni_fetched_at = now
        if not await self.omni.health():
            self._omni_snapshot = None
            return
        try:
            self._omni_snapshot = await self.omni.snapshot_for(self.study)
        except httpx.HTTPError as ex:
            self.omni.error = str(ex)
            self._omni_snapshot = None
        sid = (self._omni_snapshot or {}).get("session", {}).get("id") if self._omni_snapshot else None
        if sid != self._tail_session:
            if self._tail_task:
                self._tail_task.cancel()
                self._tail_task = None
            self._tail_session = sid
            if sid:
                self._tail_task = asyncio.create_task(self._tail_forever(sid))

    async def _tail_forever(self, sid: str):
        while True:
            try:
                await self.omni.tail(sid, lambda _t: self.mark_dirty("omni"))
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(2.0)

    def _omni_changed(self) -> bool:
        body = json.dumps(self._omni_snapshot, sort_keys=True, default=str) if self._omni_snapshot else None
        changed = body != self._last_omni_body
        self._last_omni_body = body
        return changed

    async def rebuild(self, force: bool = False):
        sig = self._files_signature()
        files_changed = sig != self._files_sig
        self._files_sig = sig
        await self._refresh_omni(force=force)
        if not (force or files_changed or self._dirty_files or self.version == 0 or self._omni_changed()):
            return
        self._dirty_files = False
        self.study = studies.get_study(self.study["id"]) or self.study
        snap = await asyncio.to_thread(bridge.snapshot, self._omni_snapshot, self.root)
        snap["study"] = self.study
        snap["omnigent"] = {"url": self.omni.base, "reachable": self.omni.reachable, "error": self.omni.error,
                            "agent_name": AGENT_NAME}
        body = json.dumps(snap, ensure_ascii=False, default=str, sort_keys=True)
        if body != json.dumps(self.snapshot, ensure_ascii=False, default=str, sort_keys=True):
            self.version += 1
            snap["version"] = self.version
            self.snapshot = snap
            async with self.changed:
                self.changed.notify_all()

    async def run(self):
        while True:
            try:
                await self.rebuild()
            except Exception as ex:  # keep serving the last good snapshot
                self.snapshot.setdefault("errors", []).append(str(ex))
            await asyncio.sleep(POLL_SECONDS)

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self.run())

    async def stop(self):
        for t in (self._task, self._tail_task):
            if t:
                t.cancel()


class Registry:
    def __init__(self, omni: Omni):
        self.omni = omni
        self.watchers: dict[str, LabWatcher] = {}

    def study(self, study_id: str) -> dict:
        s = studies.get_study(study_id)
        if s is None:
            raise HTTPException(404, f"no study {study_id!r}")
        return s

    async def watcher(self, study_id: str) -> LabWatcher:
        s = self.study(study_id)
        w = self.watchers.get(study_id)
        if w is None:
            w = LabWatcher(s, self.omni)
            self.watchers[study_id] = w
            await w.rebuild(force=True)
            w.start()
        return w

    async def stop(self):
        for w in self.watchers.values():
            await w.stop()
        await self.omni.close()


# ---------- app ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    reg = Registry(Omni(OMNI_URL))
    app.state.registry = reg
    await reg.watcher(C.DEFAULT_STUDY_ID)
    try:
        yield
    finally:
        await reg.stop()


app = FastAPI(title="SPARK Lab API", version="0.2.0", lifespan=lifespan,
              description="Read a lab (board, ledger, calcs, protocols), stream it as UI events, record human "
                          "gates (objective, pick, approve, unseal, decision) and drive its Omnigent session.")

_origins = {"http://localhost:3000", "http://127.0.0.1:3000"}
if os.environ.get("SPARK_UI_ORIGIN"):
    _origins.add(os.environ["SPARK_UI_ORIGIN"])
app.add_middleware(CORSMiddleware, allow_origins=sorted(_origins), allow_methods=["*"], allow_headers=["*"])


def _reg() -> Registry:
    return app.state.registry


def _summary(w: LabWatcher) -> dict:
    s = w.snapshot
    st = s.get("status", {})
    return {**w.study, "stage": s.get("stage"), "gate": s.get("gate"), "finished": s.get("finished"),
            "needs_confirmation": s.get("needs_confirmation"), "objective": s.get("objective"),
            "ledger_entries": st.get("ledger", {}).get("entries"), "calcs": st.get("ledger", {}).get("calcs"),
            "holdout_status": st.get("holdout"), "session": s.get("session"), "version": w.version}


# -- studies --

class NewStudy(BaseModel):
    title: str
    question: str = ""
    by: str | None = None
    copy_board: bool = Field(default=True, description="start from the cited expectation board of the root lab")


@app.get("/health")
async def health():
    reg = _reg()
    return {"status": "ok", "root": str(C.PACKAGE_ROOT), "studies": len(studies.list_studies()),
            "active_study": studies.active_id(), "omnigent": {"url": OMNI_URL, "reachable": reg.omni.reachable},
            "lab_mode": fastlab.mode()}


@app.get("/studies")
async def studies_list():
    reg = _reg()
    out = []
    for s in studies.list_studies():
        w = await reg.watcher(s["id"])
        out.append(_summary(w))
    return {"studies": out, "active": studies.active_id()}


@app.post("/studies", status_code=201)
async def studies_create(body: NewStudy):
    try:
        s = await asyncio.to_thread(studies.create_study, body.title, body.question, body.by or "human", body.copy_board)
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    w = await _reg().watcher(s["id"])
    return {"ok": True, "study": _summary(w)}


study = APIRouter(prefix="/studies/{study_id}")


@study.get("")
async def study_get(study_id: str):
    return _summary(await _reg().watcher(study_id))


@study.post("/activate")
async def study_activate(study_id: str):
    _reg().study(study_id)
    return {"ok": True, "active": studies.set_active(study_id)}


@study.get("/status")
async def study_status(study_id: str):
    w = await _reg().watcher(study_id)
    with C.use_root(w.root):
        st = bridge.lab_status()
    return {**st, "study": w.study, "omnigent": {"url": OMNI_URL, "reachable": w.omni.reachable, "error": w.omni.error},
            "session": w.snapshot.get("session"), "gate": w.snapshot.get("gate"), "finished": w.snapshot.get("finished"),
            "stage": w.snapshot.get("stage"), "objective": w.snapshot.get("objective"),
            "needs_confirmation": w.snapshot.get("needs_confirmation"), "version": w.version}


@study.get("/board")
async def study_board(study_id: str):
    w = await _reg().watcher(study_id)
    with C.use_root(w.root):
        return json.loads(tools.read_board())


@study.get("/ledger")
async def study_ledger(study_id: str, entry_type: str = Query("", alias="type"), last_n: int = Query(200, ge=1, le=5000)):
    w = await _reg().watcher(study_id)
    with C.use_root(w.root):
        rows = ledger.read(entry_type or None)[-last_n:]
        ok, msg = ledger.verify()
        return {"entries": rows, "intact": ok, "message": msg, "holdout_looks": ledger.holdout_looks()}


@study.get("/calcs")
async def study_calcs(study_id: str, last_n: int = Query(500, ge=1, le=10000)):
    w = await _reg().watcher(study_id)
    with C.use_root(w.root):
        return {"calcs": bridge.read_calcs()[-last_n:]}


@study.get("/prereg")
async def study_prereg_list(study_id: str):
    w = await _reg().watcher(study_id)
    with C.use_root(w.root):
        return {"preregs": bridge.lab_status()["preregs"]}


@study.get("/prereg/{prereg_id}")
async def study_prereg_detail(study_id: str, prereg_id: str):
    w = await _reg().watcher(study_id)
    with C.use_root(w.root):
        entry = ledger.prereg_entry(prereg_id)
        if entry is None:
            raise HTTPException(404, f"no prereg {prereg_id!r}")
        out = {"entry": entry, "approval": ledger.approval_for(prereg_id), "protocol": None, "integrity": "ok"}
        try:
            out["protocol"] = ledger.load_protocol(prereg_id)
        except PermissionError as ex:
            out["integrity"] = str(ex)
        except Exception as ex:
            out["integrity"] = f"unavailable: {ex}"
        return out


@study.get("/state")
async def study_state(study_id: str):
    w = await _reg().watcher(study_id)
    if not w.snapshot:
        await w.rebuild(force=True)
    return w.snapshot


@study.get("/events")
async def study_events(study_id: str):
    w = await _reg().watcher(study_id)

    async def gen():
        last = -1
        while True:
            if w.version != last:
                last = w.version
                yield f"event: snapshot\ndata: {json.dumps(w.snapshot, ensure_ascii=False, default=str)}\n\n"
            try:
                async with w.changed:
                    await asyncio.wait_for(w.changed.wait(), timeout=HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                yield f"event: heartbeat\ndata: {json.dumps({'version': w.version, 'ts': time.time()})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# -- human writes --

class HumanEntry(BaseModel):
    type: str = Field(description="one of " + ", ".join(sorted(C.AGENT_ENTRY_TYPES)))
    payload: dict = Field(default_factory=dict)
    by: str | None = Field(default=None, description="who is acting; recorded in the payload")


async def _append_human(w: LabWatcher, entry_type: str, payload: dict, by: str | None) -> dict:
    if entry_type not in C.AGENT_ENTRY_TYPES:
        raise HTTPException(400, f"humans may append {sorted(C.AGENT_ENTRY_TYPES)} here; "
                                 "approval/unseal/seal have their own gates")
    payload = dict(payload)
    if by:
        payload.setdefault("by", by)
    if not payload:
        raise HTTPException(400, "payload must be a non-empty JSON object")

    def _write():
        with C.use_root(w.root):
            return ledger.append(entry_type, "human", payload)

    row = await asyncio.to_thread(_write)
    w.mark_dirty("files")
    await w.rebuild(force=True)
    return row


@study.post("/human/ledger", status_code=201)
async def study_human_ledger(study_id: str, entry: HumanEntry):
    """HTTP twin of `python -m sparklab.ledger add`: a human appends a note/decision/... to the ledger."""
    w = await _reg().watcher(study_id)
    row = await _append_human(w, entry.type, entry.payload, entry.by)
    return {"ok": True, "entry": row}


class Pick(BaseModel):
    expectation_id: str
    text: str | None = None
    by: str | None = None
    notify: bool = Field(default=True, description="also tell the Supervisor ('Pursue E02')")


@study.post("/pick", status_code=201)
async def study_pick(study_id: str, body: Pick):
    """The humans choose which discrepancy to pursue: a human note in the ledger, and a message to the
    Supervisor when the study has a session."""
    w = await _reg().watcher(study_id)
    with C.use_root(w.root):
        ids = {e["id"] for e in json.loads(tools.read_board())["expectations"]}
    if body.expectation_id not in ids:
        raise HTTPException(400, f"unknown expectation {body.expectation_id!r}; board has {sorted(ids)}")
    payload = {"action": "pick_surprise", "expectation_id": body.expectation_id}
    if body.text:
        payload["text"] = body.text
    row = await _append_human(w, "note", payload, body.by)
    sent, warning = None, None
    session = (w.snapshot.get("session") or {})
    if body.notify and session.get("id"):
        text = f"Pursue {body.expectation_id}." + (f" {body.text}" if body.text else "")
        try:
            sent = await w.omni.send_message(session["id"], text)
        except HTTPException as ex:  # the pick is in the ledger either way
            warning = f"recorded, but the Supervisor could not be notified: {ex.detail}"
        w.mark_dirty("omni")
    return {"ok": True, "entry": row, "sent": sent, "warning": warning}


class Approve(BaseModel):
    prereg_id: str
    by: str
    hash_prefix: str = Field(description=f"first {HASH_PREFIX_LEN} characters of the protocol's SHA-256")


@study.post("/approve", status_code=201)
async def study_approve(study_id: str, body: Approve):
    """Web twin of `python -m sparklab.approve`: human-only, same typed-hash friction."""
    w = await _reg().watcher(study_id)
    by = body.by.strip()
    if not by:
        raise HTTPException(400, "by is required")

    def _do():
        with C.use_root(w.root):
            protocol_hash = None
            try:
                ledger.load_protocol(body.prereg_id)  # raises if missing or edited after registration
                protocol_hash = ledger.prereg_entry(body.prereg_id)["payload"]["protocol_hash"]
            except KeyError as ex:
                raise HTTPException(404, str(ex))
            except PermissionError as ex:
                raise HTTPException(409, str(ex))
            typed = body.hash_prefix.strip().lower()
            if len(typed) < HASH_PREFIX_LEN or protocol_hash[:len(typed)] != typed:
                raise HTTPException(400, "Hash mismatch. Not approved.")
            try:
                return ledger.approve(body.prereg_id, by)
            except RuntimeError as ex:
                raise HTTPException(409, str(ex))

    row = await asyncio.to_thread(_do)
    w.mark_dirty("files")
    await w.rebuild(force=True)
    return {"ok": True, "entry": row}


class Unseal(BaseModel):
    by: str
    sha256_prefix: str = Field(description=f"first {HASH_PREFIX_LEN} characters of the sealed file's SHA-256 (seal entry)")


@study.post("/unseal", status_code=201)
async def study_unseal(study_id: str, body: Unseal):
    """Web twin of `python -m sparklab.unseal`: verifies the sealed hash against the ledger, processes the
    hold-out once. The human must type the recorded SHA-256 prefix."""
    w = await _reg().watcher(study_id)
    by = body.by.strip()
    if not by:
        raise HTTPException(400, "by is required")

    def _do():
        with C.use_root(w.root):
            seals = ledger.read("seal")
            if not seals:
                raise HTTPException(409, "no seal entry in ledger")
            recorded = seals[-1]["payload"].get("sha256", "")
            typed = body.sha256_prefix.strip().lower()
            if len(typed) < HASH_PREFIX_LEN or recorded[:len(typed)] != typed:
                raise HTTPException(400, "Hash mismatch. Not unsealed.")
            try:
                return unseal_mod.unseal(by)
            except RuntimeError as ex:
                raise HTTPException(409, str(ex))

    row = await asyncio.to_thread(_do)
    w.mark_dirty("files")
    await w.rebuild(force=True)
    return {"ok": True, "entry": row}


# -- Omnigent control --

class StartSession(BaseModel):
    objective: str | None = Field(default=None, description="first message to the Supervisor; also recorded as a human plan_update")
    by: str | None = None
    title: str | None = None


@study.get("/session")
async def study_session(study_id: str):
    w = await _reg().watcher(study_id)
    if not await w.omni.health():
        return {"reachable": False, "error": w.omni.error, "session": None, "candidates": []}
    sessions = await w.omni.list_sessions()
    return {"reachable": True, "session": w.snapshot.get("session"), "active_study": studies.active_id(),
            "candidates": [{"id": s.get("id"), "title": s.get("title"), "status": s.get("status"),
                            "workspace": s.get("workspace"), "labels": s.get("labels"), "updated_at": s.get("updated_at"),
                            "archived": s.get("archived")} for s in sessions]}


@study.post("/session", status_code=201)
async def study_session_start(study_id: str, body: StartSession):
    """Start (or reuse) the study's Omnigent session from lab.yaml, make the study the active lab for
    the shared runner, and send the objective as the first message."""
    w = await _reg().watcher(study_id)
    if not await w.omni.health():
        raise HTTPException(503, f"Omnigent is not reachable at {w.omni.base}; start it with `omnigent start` "
                                 "(same venv as sparklab) and retry")
    studies.set_active(study_id)
    session = await w.omni.pick_session_for(w.study)
    created = False
    if session is None:
        bundle = await asyncio.to_thread(build_agent_bundle)
        host_id = await w.omni.pick_host_id()
        session = await w.omni.create_session(
            bundle, title=body.title or f"SPARK · {w.study['title']}", labels={STUDY_LABEL: study_id},
            workspace=str(w.root), host_id=host_id)
        created = True
    sent, warning = None, None
    if body.objective and body.objective.strip():
        text = body.objective.strip()
        await _append_human(w, "plan_update", {"action": "objective", "text": text}, body.by)
        try:
            sent = await w.omni.send_message(session["id"], text)
        except HTTPException as ex:  # the session exists; e.g. no runner bound yet on this host
            warning = f"session created but the objective could not be delivered yet: {ex.detail}"
    w.mark_dirty("omni")
    await w.rebuild(force=True)
    return {"ok": True, "created": created, "session": {"id": session.get("id"), "status": session.get("status"),
                                                        "title": session.get("title"), "runner_id": session.get("runner_id"),
                                                        "host_id": session.get("host_id")},
            "active_study": studies.active_id(), "sent": sent, "warning": warning,
            "note": "The runner's tools follow backend/studies/ACTIVE (unless the runner was started with "
                    "SPARKLAB_ROOT). Run Omnigent from the same venv as sparklab."}


class Message(BaseModel):
    text: str
    by: str | None = None
    record: bool = Field(default=False, description="also keep the message as a human note in the ledger")


@study.post("/session/message", status_code=202)
async def study_session_message(study_id: str, body: Message):
    """Talk to the Supervisor of this study's session."""
    w = await _reg().watcher(study_id)
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "text is required")
    session = w.snapshot.get("session") or {}
    if not session.get("id"):
        raise HTTPException(409, "this study has no Omnigent session yet; start one first")
    sent = await w.omni.send_message(session["id"], text)
    if body.record:
        await _append_human(w, "note", {"action": "message", "text": text}, body.by)
    w.mark_dirty("omni")
    return {"ok": True, "sent": sent}


app.include_router(study)


# -- legacy aliases: the default study at the root --

@app.get("/status")
async def status():
    return await study_status(C.DEFAULT_STUDY_ID)


@app.get("/board")
async def board():
    return await study_board(C.DEFAULT_STUDY_ID)


@app.get("/ledger")
async def ledger_read(entry_type: str = Query("", alias="type"), last_n: int = Query(200, ge=1, le=5000)):
    return await study_ledger(C.DEFAULT_STUDY_ID, entry_type, last_n)


@app.get("/calcs")
async def calcs(last_n: int = Query(500, ge=1, le=10000)):
    return await study_calcs(C.DEFAULT_STUDY_ID, last_n)


@app.get("/prereg")
async def prereg_list():
    return await study_prereg_list(C.DEFAULT_STUDY_ID)


@app.get("/prereg/{prereg_id}")
async def prereg_detail(prereg_id: str):
    return await study_prereg_detail(C.DEFAULT_STUDY_ID, prereg_id)


@app.get("/state")
async def state():
    return await study_state(C.DEFAULT_STUDY_ID)


@app.get("/events")
async def events():
    return await study_events(C.DEFAULT_STUDY_ID)


@app.post("/human/ledger", status_code=201)
async def human_ledger(entry: HumanEntry):
    return await study_human_ledger(C.DEFAULT_STUDY_ID, entry)


@app.get("/omnigent/sessions")
async def omnigent_sessions():
    return await study_session(C.DEFAULT_STUDY_ID)


def main():
    import uvicorn
    uvicorn.run("sparklab.api:app", host=os.environ.get("SPARK_API_HOST", "127.0.0.1"),
                port=int(os.environ.get("SPARK_API_PORT", "8787")), log_level="info")


if __name__ == "__main__":
    main()
