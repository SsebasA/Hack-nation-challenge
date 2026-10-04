"""Step 1 test: sparklab.config imports, fixed thresholds, SPARKLAB_ROOT / SPARKLAB_HOME. Run: python tests/test_config.py"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def config_in_subprocess(env_root, home=None):
    """Import sparklab.config in a fresh interpreter, so SPARKLAB_ROOT / SPARKLAB_HOME are read at import time."""
    env = dict(os.environ)
    for k in ("SPARKLAB_ROOT", "SPARKLAB_HOME", "SPARKLAB_STUDIES_DIR"):
        env.pop(k, None)
    if env_root is not None:
        env["SPARKLAB_ROOT"] = str(env_root)
    if home is not None:
        env["SPARKLAB_HOME"] = str(home)
    code = "from sparklab import config as C; print(C.ROOT); print(C.LEDGER_PATH); print(C.studies_dir())"
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True)
    root, ledger, studies = out.stdout.strip().splitlines()
    return Path(root), Path(ledger), Path(studies)


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
    root, ledger, _ = config_in_subprocess(None)
    assert root.resolve() == BACKEND, root
    assert ledger.resolve() == BACKEND / "ledger" / "ledger.jsonl", ledger

    # SPARKLAB_ROOT set before import moves the ledger under it.
    with tempfile.TemporaryDirectory() as tmp:
        root, ledger, _ = config_in_subprocess(tmp)
        assert root == Path(tmp), root
        assert ledger == Path(tmp) / "ledger" / "ledger.jsonl", ledger
        assert BACKEND not in ledger.parents

    # SPARKLAB_HOME (deployments: records on a volume) moves the root lab and its studies, code stays put.
    with tempfile.TemporaryDirectory() as tmp:
        root, ledger, studies = config_in_subprocess(None, home=tmp)
        assert root == Path(tmp) and ledger == Path(tmp) / "ledger" / "ledger.jsonl", (root, ledger)
        assert studies == Path(tmp) / "studies", studies
        # The ACTIVE pointer under the home still selects a study.
        (Path(tmp) / "studies" / "s1").mkdir(parents=True)
        (Path(tmp) / "studies" / "ACTIVE").write_text("s1")
        root, _, _ = config_in_subprocess(None, home=tmp)
        assert root == Path(tmp) / "studies" / "s1", root

    print("OK")


if __name__ == "__main__":
    main()
