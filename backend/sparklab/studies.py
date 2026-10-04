"""Studies: several labs under one backend.

The original lab (``backend/`` itself) is the default study. Additional studies live in
``backend/studies/<id>/`` with the same layout (board/, ledger/, prereg/, data/) plus a
``study.json``. The shared Omnigent runner works on the *active* study (``studies/ACTIVE``); the
CLIs and the agents' tools follow the same resolution (see ``sparklab.config``).

    python -m sparklab.studies list
    python -m sparklab.studies create "Title" --question "..." --by <name> [--no-board]
    python -m sparklab.studies use <id>          # the lab the agents' tools work on
    python -m sparklab.studies use --default     # back to backend/ itself

A new study starts with: a copy of the cited expectation board (and the seeded control) unless
``--no-board``; the discovery data and the sealed hold-out *linked* from the root lab when they exist
(the zip's SHA-256 is recomputed and recorded as the study's own ``seal`` entry); a ledger whose
first entry is a human note. No number is produced here.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
from pathlib import Path

from sparklab import config as C

DEFAULT_STUDY = {
    "id": C.DEFAULT_STUDY_ID,
    "title": "Undiagnosed diabetes among US adults",
    "question": "Where does the share of adults with diabetes-range HbA1c and no diagnosis differ from what "
                "published priors lead us to expect?",
    "dataset": f"NHANES {C.CYCLE_LABEL[C.DISCOVERY]} (cycle {C.DISCOVERY}, discovery)",
    "holdout": f"NHANES {C.CYCLE_LABEL[C.HOLDOUT]} (cycle {C.HOLDOUT}, sealed)",
}

_SLUG = re.compile(r"[^a-z0-9]+")


def studies_dir() -> Path:
    return C.studies_dir()


def slugify(title: str) -> str:
    s = _SLUG.sub("-", title.lower()).strip("-")
    return s[:48] or "study"


def active_id() -> str:
    try:
        sid = C.active_pointer().read_text(encoding="utf-8").strip()
    except OSError:
        return C.DEFAULT_STUDY_ID
    return sid if sid and (studies_dir() / sid).is_dir() else C.DEFAULT_STUDY_ID


def set_active(sid: str) -> str:
    if sid != C.DEFAULT_STUDY_ID and not (studies_dir() / sid / "study.json").exists():
        raise KeyError(f"no study {sid!r}")
    studies_dir().mkdir(parents=True, exist_ok=True)
    C.active_pointer().write_text(sid + "\n", encoding="utf-8")
    return sid


def study_root(sid: str) -> Path:
    if sid == C.DEFAULT_STUDY_ID:
        return C.default_root()
    return studies_dir() / sid


def get_study(sid: str) -> dict | None:
    if sid == C.DEFAULT_STUDY_ID:
        meta = dict(DEFAULT_STUDY)
    else:
        p = studies_dir() / sid / "study.json"
        if not p.exists():
            return None
        meta = json.loads(p.read_text(encoding="utf-8"))
    meta["root"] = str(study_root(sid))
    meta["is_default"] = sid == C.DEFAULT_STUDY_ID
    meta["active"] = active_id() == sid
    return meta


def list_studies() -> list[dict]:
    out = [get_study(C.DEFAULT_STUDY_ID)]
    if studies_dir().is_dir():
        for d in sorted(studies_dir().iterdir()):
            if d.is_dir() and (d / "study.json").exists():
                out.append(get_study(d.name))
    return [s for s in out if s]


def _link_or_copy(src: Path, dst: Path) -> str | None:
    """Link a data file from the root lab into a study (copy if linking fails). Returns how."""
    if not src.exists():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(src, dst)
        return "linked"
    except OSError:
        shutil.copy2(src, dst)
        return "copied"


def create_study(title: str, question: str = "", by: str = "human", copy_board: bool = True) -> dict:
    from sparklab import data, ledger  # local import: ledger resolves paths through config at call time

    title = title.strip()
    if not title:
        raise ValueError("title is required")
    # A study without discovery data or a sealed hold-out cannot finish the loop (it would stop at the
    # unseal gate with no seal entry), so refuse up front and say how to prepare the root lab.
    root_lab = C.default_root()
    missing = [cmd for path, cmd in (
        (root_lab / "data" / "processed" / f"nhanes_{C.DISCOVERY}.pkl", f"python -m sparklab.data --cycle {C.DISCOVERY}"),
        (root_lab / "data" / "sealed" / "nhanes_I.zip", f"python -m sparklab.data --cycle {C.HOLDOUT} --seal"),
    ) if not path.exists()]
    if missing:
        raise ValueError(f"the root lab ({root_lab}) is not ready: run, from backend/, " + " and ".join(missing)
                         + " (or restore data/sealed/nhanes_I.zip from whoever sealed it)")
    base = slugify(title)
    sid, n = base, 2
    while sid == C.DEFAULT_STUDY_ID or (studies_dir() / sid).exists():
        sid = f"{base}-{n}"
        n += 1
    root = studies_dir() / sid
    for sub in ("board", "ledger", "prereg", "data/processed", "data/sealed"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "prereg" / ".gitkeep").touch()

    if copy_board and (root_lab / "board" / "expectations.json").exists():
        shutil.copy2(root_lab / "board" / "expectations.json", root / "board" / "expectations.json")
        if (root_lab / "board" / "control_seeded.json").exists():
            shutil.copy2(root_lab / "board" / "control_seeded.json", root / "board" / "control_seeded.json")
    else:
        (root / "board" / "expectations.json").write_text(json.dumps({
            "version": 1,
            "_comment": "Priors for the Surprise step. expected = proportion (0-1). Every expected value needs a "
                        "citation (PMID/DOI/URL) and a comparability label (CLAUDE.md rule 6). Leave null until cited.",
            "expectations": []}, indent=2) + "\n", encoding="utf-8")

    linked = {
        "discovery": _link_or_copy(root_lab / "data" / "processed" / f"nhanes_{C.DISCOVERY}.pkl",
                                   root / "data" / "processed" / f"nhanes_{C.DISCOVERY}.pkl"),
        "holdout_zip": _link_or_copy(root_lab / "data" / "sealed" / "nhanes_I.zip",
                                     root / "data" / "sealed" / "nhanes_I.zip"),
    }
    meta = {"id": sid, "title": title, "question": question.strip(),
            "dataset": DEFAULT_STUDY["dataset"], "holdout": DEFAULT_STUDY["holdout"],
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "created_by": by, "copied_board": bool(copy_board), "data": linked}
    (root / "study.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    with C.use_root(root):
        ledger.append("note", "human", {"action": "study_created", "title": title, "question": meta["question"], "by": by})
        if linked["holdout_zip"]:
            digest = data.sha256_file(C.SEALED_ZIP)
            ledger.append("seal", "human", {"cycle": C.HOLDOUT, "path": str(C.SEALED_ZIP.relative_to(C.ROOT)),
                                            "sha256": digest, "by": by, "linked_from": str(root_lab)})
    return get_study(sid)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    c = sub.add_parser("create")
    c.add_argument("title")
    c.add_argument("--question", default="")
    c.add_argument("--by", default="human")
    c.add_argument("--no-board", action="store_true", help="start with an empty expectation board")
    u = sub.add_parser("use")
    u.add_argument("study_id", nargs="?")
    u.add_argument("--default", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        for s in list_studies():
            print(f"{'*' if s['active'] else ' '} {s['id']:<40} {s['title']}  ({s['root']})")
    elif a.cmd == "create":
        s = create_study(a.title, a.question, by=a.by, copy_board=not a.no_board)
        print(json.dumps(s, indent=2, ensure_ascii=False))
    elif a.cmd == "use":
        sid = C.DEFAULT_STUDY_ID if a.default or not a.study_id else a.study_id
        print(f"active study: {set_active(sid)}")


if __name__ == "__main__":
    sys.exit(main())
