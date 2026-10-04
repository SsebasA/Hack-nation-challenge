"""SPARK Lab configuration. Thresholds here are fixed (CLAUDE.md rule 8).

Lab root. Every path below hangs from one root and is resolved on each access (PEP 562 module
``__getattr__``), so one process can serve several labs ("studies"):

1. ``use_root(path)`` — a context-local override for the API, which reads many studies at once;
2. ``SPARKLAB_ROOT`` — environment variable (tests, rehearsals, CLIs run against a given lab);
3. ``studies/ACTIVE`` — pointer file naming the study the shared Omnigent runner works on
   (written by the API when a study's session starts, or by ``python -m sparklab.studies use``);
4. the package parent (the original single lab, ``backend/``).

Callers keep writing ``C.LEDGER_PATH`` etc.; nothing is frozen at import time.
"""
import contextlib
import contextvars
import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent   # backend/
DEFAULT_STUDY_ID = "undiagnosed-diabetes"                # the root lab itself

_ROOT_OVERRIDE: contextvars.ContextVar[Path | None] = contextvars.ContextVar("sparklab_root", default=None)


def default_root() -> Path:
    """The root lab: SPARKLAB_ROOT when set (tests, rehearsals), else backend/."""
    env = os.environ.get("SPARKLAB_ROOT")
    return Path(env) if env else PACKAGE_ROOT


def studies_dir() -> Path:
    """Where additional studies live (SPARKLAB_STUDIES_DIR overrides, for tests)."""
    env = os.environ.get("SPARKLAB_STUDIES_DIR")
    return Path(env) if env else PACKAGE_ROOT / "studies"


def active_pointer() -> Path:
    return studies_dir() / "ACTIVE"


def resolve_root() -> Path:
    override = _ROOT_OVERRIDE.get()
    if override is not None:
        return override
    env = os.environ.get("SPARKLAB_ROOT")
    if env:
        return Path(env)
    try:
        sid = active_pointer().read_text(encoding="utf-8").strip()
    except OSError:
        sid = ""
    if sid and sid != DEFAULT_STUDY_ID:
        candidate = studies_dir() / sid
        if candidate.is_dir():
            return candidate
    return PACKAGE_ROOT


@contextlib.contextmanager
def use_root(path: Path | str):
    """Resolve every path under `path` inside this block (context-local, async-safe)."""
    token = _ROOT_OVERRIDE.set(Path(path))
    try:
        yield Path(path)
    finally:
        _ROOT_OVERRIDE.reset(token)


_DERIVED = {
    "ROOT": lambda r: r,
    "DATA_DIR": lambda r: r / "data",
    "RAW_DIR": lambda r: r / "data" / "raw",              # downloaded XPT (discovery only)
    "PROCESSED_DIR": lambda r: r / "data" / "processed",  # discovery cycle, derived columns
    "SEALED_DIR": lambda r: r / "data" / "sealed",        # hold-out zip, never processed except by unseal
    "HOLDOUT_DIR": lambda r: r / "data" / "holdout",      # written only by `python -m sparklab.unseal`
    "SEALED_ZIP": lambda r: r / "data" / "sealed" / "nhanes_I.zip",
    "LEDGER_PATH": lambda r: r / "ledger" / "ledger.jsonl",
    "CALCS_PATH": lambda r: r / "ledger" / "calcs.jsonl",  # every number an agent sees has a calc_id here
    "PREREG_DIR": lambda r: r / "prereg",
    "BOARD_PATH": lambda r: r / "board" / "expectations.json",
    "CONTROL_PATH": lambda r: r / "board" / "control_seeded.json",
}


def __getattr__(name: str):
    try:
        return _DERIVED[name](resolve_root())
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None


# Cycles
DISCOVERY = "J"   # NHANES 2017-2018
HOLDOUT = "I"     # NHANES 2015-2016 (sealed)
CYCLE_LABEL = {"J": "2017-2018", "I": "2015-2016"}
CYCLE_YEAR = {"J": "2017", "I": "2015"}
COMPONENTS = ["DEMO", "DIQ", "GHB", "HIQ", "HUQ", "BMX", "GLU"]

# CDC moved NHANES files in 2024; try the current layout first, then the legacy one.
CDC_URL_PATTERNS = [
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{comp}_{cycle}.xpt",
    "https://wwwn.cdc.gov/Nchs/Nhanes/{label}/{comp}_{cycle}.XPT",
]

# ADA thresholds (fixed). Normal = HbA1c < 5.7, NOT < 6.5.
HBA1C_PREDIABETES = 5.7
HBA1C_DIABETES = 6.5
GLUCOSE_PREDIABETES = 100.0
GLUCOSE_DIABETES = 126.0

ADULT_AGE = 20
# Applied to every estimate, always (adults, not pregnant). Codes 7/9 on diag are NaN.
BASE_DOMAIN = "adult and not pregnant"

# Gates
MIN_CELL_N = 30           # unweighted denominator below this never enters confirmatory
MIN_DF_WARN = 8           # NCHS-style flag for too few design degrees of freedom
MAX_HOLDOUT_LOOKS = 1     # the hold-out is looked at once
CONFIDENCE = 0.95

AGENT_ORIGINS = {"agent:supervisor", "agent:scout", "agent:skeptic", "agent:experimenter"}
# Entry types agents may append directly. prereg/result/holdout_look come from tools;
# seal/unseal/approval come only from human CLIs.
AGENT_ENTRY_TYPES = {"anomaly", "attack", "hypothesis", "decision", "plan_update", "note"}
