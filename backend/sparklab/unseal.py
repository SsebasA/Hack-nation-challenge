"""Human-only: verify the sealed hold-out hash, process it once.

    python -m sparklab.unseal

Requires: a `seal` ledger entry, at least one human approval, no previous unseal.
Writes data/holdout/nhanes_I.pkl. It does not compute any statistic; only
sparklab.tools.run_test may compute on the hold-out.
"""
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from sparklab import config as C
from sparklab import data, ledger


def unseal(by: str = "human") -> dict:
    seals = ledger.read("seal")
    if not seals:
        raise RuntimeError("no seal entry in ledger")
    if ledger.read("unseal"):
        raise RuntimeError("hold-out already unsealed once")
    if not ledger.read("approval"):
        raise RuntimeError("no human approval yet; run `python -m sparklab.approve <prereg_id> --by <name>` first")
    expected = seals[-1]["payload"]["sha256"]
    actual = data.sha256_file(C.SEALED_ZIP)
    if actual != expected:
        ledger.append("unseal", "human", {"hash_verified": False, "expected": expected, "actual": actual, "by": by})
        raise RuntimeError("SHA-256 MISMATCH: sealed file changed since sealing. Not processed.")
    tmp = Path(tempfile.mkdtemp(prefix="sparklab_unseal_"))
    try:
        with zipfile.ZipFile(C.SEALED_ZIP) as z:
            z.extractall(tmp)
        df = data.build_from_dir(tmp, C.HOLDOUT)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    C.HOLDOUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_pickle(C.HOLDOUT_DIR / f"nhanes_{C.HOLDOUT}.pkl")
    return ledger.append("unseal", "human", {"hash_verified": True, "sha256": actual, "rows": len(df), "by": by})


def main():
    if not sys.stdin.isatty():
        sys.exit("Refusing: unseal requires an interactive human terminal.")
    by = input("Your name: ").strip() or "human"
    if input(f"Unseal NHANES {C.CYCLE_LABEL[C.HOLDOUT]} once, as {by}? [y/N] ").strip().lower() != "y":
        sys.exit("Cancelled.")
    e = unseal(by)
    print(f"Hash verified {e['payload']['sha256']}\nUnsealed: {e['id']} ({e['payload']['rows']} rows). "
          "Only run_test can compute on it now.")


if __name__ == "__main__":
    main()
