"""SPARK Lab configuration. Thresholds here are fixed (CLAUDE.md rule 8)."""
import os
from pathlib import Path

# Repo root. Overridable so the smoke test can run in a temp directory.
ROOT = Path(os.environ.get("SPARKLAB_ROOT", Path(__file__).resolve().parent.parent))

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"              # downloaded XPT (discovery only)
PROCESSED_DIR = DATA_DIR / "processed"  # discovery cycle, derived columns
SEALED_DIR = DATA_DIR / "sealed"        # hold-out zip, never processed except by unseal
HOLDOUT_DIR = DATA_DIR / "holdout"      # written only by `python -m sparklab.unseal`
SEALED_ZIP = SEALED_DIR / "nhanes_I.zip"

LEDGER_PATH = ROOT / "ledger" / "ledger.jsonl"
CALCS_PATH = ROOT / "ledger" / "calcs.jsonl"   # every number an agent sees has a calc_id here
PREREG_DIR = ROOT / "prereg"
BOARD_PATH = ROOT / "board" / "expectations.json"
CONTROL_PATH = ROOT / "board" / "control_seeded.json"

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
