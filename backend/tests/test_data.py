"""Step 3a test: derived columns on a handcrafted frame (no network). Run: python tests/test_data.py

Each row is designed to hit one derivation rule. Runs in a temp SPARKLAB_ROOT; never reads data/.
"""
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="sparklab_data_"))
os.environ["SPARKLAB_ROOT"] = str(TMP)  # before importing sparklab

from sparklab import config as C  # noqa: E402
from sparklab import data as D  # noqa: E402

NA = np.nan
SEQN = list(range(1, 11))


def frames() -> dict[str, pd.DataFrame]:
    demo = pd.DataFrame({
        "SEQN": SEQN,
        "RIAGENDR": [1, 2, 2, 1, 2, 1, 2, 1, 2, 1],
        "RIDAGEYR": [45, 30, 28, 60, 19, 55, 70, 40, 35, 20],
        "RIDEXPRG": [NA, 1, 2, NA, NA, NA, NA, NA, 3, NA],
        "RIDRETH3": [3, 1, 4, 6, 2, 7, 3, 4, 1, 6],
        "INDFMPIR": [1.0, 2.0, 3.0, 4.0, 5.0, 0.5, 1.5, 2.5, NA, 3.5],
        "WTMEC2YR": [1e4, 2e4, 3e4, 4e4, 5e4, 6e4, 7e4, 8e4, 9e4, 1e5],
        "SDMVSTRA": [134, 134, 135, 135, 136, 136, 137, 137, 138, 138],
        "SDMVPSU": [1, 2, 1, 2, 1, 2, 1, 2, 1, 2],
    })
    diq = pd.DataFrame({
        "SEQN": SEQN,
        "DIQ010": [1, 2, 3, 7, 9, 2, 2, 2, 2, 2],
        "DIQ050": [1, NA, NA, NA, NA, NA, NA, NA, NA, NA],
        "DIQ070": [2, NA, NA, NA, NA, NA, NA, NA, NA, NA],
    })
    ghb = pd.DataFrame({"SEQN": SEQN, "LBXGH": [7.0, 5.6, 5.7, 6.4, 6.5, 6.5, NA, 6.4, 8.0, 5.0]})
    hiq = pd.DataFrame({"SEQN": SEQN, "HIQ011": [1, 2, 9, 7, 1, 1, 2, 1, 1, 2]})
    huq = pd.DataFrame({"SEQN": SEQN, "HUQ030": [1, 2, 3, 7, 9, 1, 1, 2, 3, 1]})
    bmx = pd.DataFrame({"SEQN": SEQN, "BMXBMI": [25.0, 30.0, 22.0, 28.0, NA, 31.0, 24.0, 27.0, 35.0, 21.0]})
    # Fasting subsample: only 4 respondents, so the left join leaves the rest missing.
    glu = pd.DataFrame({"SEQN": [1, 2, 3, 4], "LBXGLU": [99.9, 100.0, 125.9, 126.0],
                        "WTSAF2YR": [5e4, 0.0, 6e4, NA]})
    return {"DEMO": demo, "DIQ": diq, "GHB": ghb, "HIQ": hiq, "HUQ": huq, "BMX": bmx, "GLU": glu}


def col(df, name):
    """seqn -> plain Python value (None for missing), so checks are exact: True, False or None."""
    s = df.set_index("seqn")[name]
    return {k: (None if pd.isna(v) else v.item() if hasattr(v, "item") else v) for k, v in s.items()}


def is_na(v):
    return v is None


def main():
    assert BACKEND not in C.ROOT.parents and C.ROOT == TMP
    df = D.build_frame(frames(), "J")
    assert len(df) == 10 and list(df["seqn"]) == SEQN
    assert set(D.COLUMNS_DOC) == set(df.columns), set(D.COLUMNS_DOC) ^ set(df.columns)

    # DIQ010 1/2/3 -> yes/no/borderline; 7 and 9 -> missing.
    diag = col(df, "diag")
    assert (diag[1], diag[2], diag[3]) == ("yes", "no", "borderline")
    assert is_na(diag[4]) and is_na(diag[5])

    # Pregnancy: RIDEXPRG 1 -> True; 2 and 3 -> False; male (missing) -> False.
    preg = col(df, "pregnant")
    assert preg[2] is True and preg[3] is False and preg[9] is False and preg[1] is False

    # Adult: age >= 20.
    adult = col(df, "adult")
    assert adult[10] is True and adult[5] is False

    # HUQ030 1/3 -> True, 2 -> False, 7/9 -> missing.
    rp = col(df, "routine_place")
    assert rp[1] is True and rp[2] is False and rp[3] is True and rp[4] is None and rp[5] is None

    # HIQ011 1 -> True, 2 -> False, 7/9 -> missing.
    ins = col(df, "insured")
    assert ins[1] is True and ins[2] is False and ins[3] is None and ins[4] is None

    # HbA1c categories at the ADA cut points (normal is < 5.7, not < 6.5).
    cat = col(df, "hba1c_cat")
    assert (cat[2], cat[3], cat[4], cat[5]) == ("normal", "prediabetes", "prediabetes", "diabetes")
    assert is_na(cat[7])

    # Glucose categories at 100 / 126; respondents outside the fasting file are missing.
    gcat = col(df, "glucose_cat")
    assert (gcat[1], gcat[2], gcat[3], gcat[4]) == ("normal", "prediabetes", "prediabetes", "diabetes")
    assert is_na(gcat[5])

    # undiagnosed: diag == 'no' and hba1c >= 6.5; missing when either input is missing.
    und = col(df, "undiagnosed")
    assert und[6] is True and und[9] is True          # no, 6.5 / no, 8.0
    assert und[1] is False                            # yes, 7.0
    assert und[2] is False and und[8] is False        # no, 5.6 / no, 6.4
    assert und[3] is False                            # borderline, 5.7
    assert und[4] is None and und[5] is None        # diag missing
    assert und[7] is None                            # hba1c missing

    # Weights: missing fasting weight -> 0; wt_mec carried through.
    wf = col(df, "wt_fast")
    assert wf[1] == 5e4 and wf[2] == 0.0 and wf[4] == 0.0 and wf[5] == 0.0
    assert not df["wt_fast"].isna().any() and col(df, "wt_mec")[10] == 1e5

    # Medication flags: no_meds_declared true when neither insulin nor pills is declared.
    assert col(df, "insulin_now")[1] is True and col(df, "pills_now")[1] is False
    nm = col(df, "no_meds_declared")
    assert nm[1] is False and nm[2] is True

    # Booleans used in pandas.eval domain filters work.
    assert len(df.query(C.BASE_DOMAIN)) == 8  # drops age 19 and the pregnant respondent
    assert len(df.query("adult and diag == 'no' and hba1c >= 6.5")) == 2

    # The hold-out cannot be loaded through data.load.
    try:
        D.load("I")
    except PermissionError:
        pass
    else:
        raise AssertionError("load('I') did not raise PermissionError")

    shutil.rmtree(TMP, ignore_errors=True)
    print("OK")


if __name__ == "__main__":
    main()
