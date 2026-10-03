"""Step 1 test: sparklab.config imports, fixed thresholds, SPARKLAB_ROOT override. Run: python tests/test_config.py"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def config_in_subprocess(env_root):
    """Import sparklab.config in a fresh interpreter, so SPARKLAB_ROOT is read at import time."""
    env = dict(os.environ)
    env.pop("SPARKLAB_ROOT", None)
    if env_root is not None:
        env["SPARKLAB_ROOT"] = str(env_root)
    code = "from sparklab import config as C; print(C.ROOT); print(C.LEDGER_PATH)"
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True)
    root, ledger = out.stdout.strip().splitlines()
    return Path(root), Path(ledger)


def main():
    os.environ.pop("SPARKLAB_ROOT", None)
    from sparklab import config as C

    # Fixed thresholds (CLAUDE.md rule 8) and gates.
    assert C.HBA1C_PREDIABETES == 5.7
    assert C.HBA1C_DIABETES == 6.5
    assert C.GLUCOSE_PREDIABETES == 100.0
    assert C.GLUCOSE_DIABETES == 126.0
    assert C.MIN_CELL_N == 30
    assert C.MAX_HOLDOUT_LOOKS == 1
    assert C.DISCOVERY == "J"
    assert C.HOLDOUT == "I"

    # Default root is backend/ (the directory holding the sparklab package).
    root, ledger = config_in_subprocess(None)
    assert root.resolve() == BACKEND, root
    assert ledger.resolve() == BACKEND / "ledger" / "ledger.jsonl", ledger

    # SPARKLAB_ROOT set before import moves the ledger under it.
    with tempfile.TemporaryDirectory() as tmp:
        root, ledger = config_in_subprocess(tmp)
        assert root == Path(tmp), root
        assert ledger == Path(tmp) / "ledger" / "ledger.jsonl", ledger
        assert BACKEND not in ledger.parents

    print("OK")


if __name__ == "__main__":
    main()
