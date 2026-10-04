"""Step 4 test: design-based estimates and verdicts on a toy design. Run: python tests/test_stats.py

The toy design (2 strata x 2 PSUs) is checked against an independent plain-loop implementation
written here, not against sparklab. Runs in a temp SPARKLAB_ROOT; never reads data/.
"""
import math
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="sparklab_stats_"))
os.environ["SPARKLAB_ROOT"] = str(TMP)  # before importing sparklab

from sparklab import config as C  # noqa: E402
from sparklab import stats as S  # noqa: E402

NA = np.nan


def toy() -> pd.DataFrame:
    """12 adults, 2 strata x 2 PSUs x 3 rows. Row 11 has missing HbA1c, row 5 missing insurance."""
    return pd.DataFrame({
        "strata":   [1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2],
        "psu":      [1, 1, 1, 2, 2, 2, 1, 1, 1, 2, 2, 2],
        "wt_mec":   [1.0, 2.0, 3.0, 1.5, 2.5, 0.5, 4.0, 1.0, 2.0, 3.0, 1.0, 2.0],
        "wt_fast":  [1.0, 0.0, 2.0, 1.0, 0.0, 1.0, 3.0, 0.0, 1.0, 2.0, 0.0, 1.0],
        "hba1c":    [5.0, 6.6, 7.0, 5.5, 6.5, 5.9, 6.8, 5.2, 5.6, 7.2, NA, 6.0],
        "glucose":  [90., NA, 130., 99., NA, 101., 127., NA, 95., 140., NA, 99.],
        "diag":     ["no", "no", "yes", "no", "no", "no", "no", "yes", "no", "no", "no", "no"],
        "insured":  pd.array([True, False, True, True, pd.NA, False, False, True, True, False, True, True],
                             dtype="boolean"),
        "female":   pd.array([True, False] * 6, dtype="boolean"),
        "adult":    pd.array([True] * 12, dtype="boolean"),
        "pregnant": pd.array([False] * 12, dtype="boolean"),
    })


def reference(rows: list[dict], in_domain, is_event, weight: str) -> tuple[float, float]:
    """Independent plain-loop Taylor linearization. Every PSU of the full design is kept."""
    dom = [r for r in rows if in_domain(r) and r[weight] > 0]
    W = sum(r[weight] for r in dom)
    p = sum(r[weight] for r in dom if is_event(r)) / W
    totals = {}
    for r in rows:  # all rows, so PSUs with no domain members contribute a zero total
        key = (r["strata"], r["psu"])
        z = 0.0
        if in_domain(r) and r[weight] > 0:
            z = r[weight] * ((1.0 if is_event(r) else 0.0) - p) / W
        totals[key] = totals.get(key, 0.0) + z
    var = 0.0
    for h in sorted({k[0] for k in totals}):
        zs = [v for k, v in totals.items() if k[0] == h]
        n_h = len(zs)
        mean = sum(zs) / n_h
        var += n_h / (n_h - 1) * sum((z - mean) ** 2 for z in zs)
    return p, math.sqrt(var)


def raises(exc, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc:
        return
    raise AssertionError(f"{fn.__name__} did not raise {exc.__name__}")


def main():
    assert C.ROOT == TMP and BACKEND not in C.ROOT.parents
    df = toy()
    rows = df.to_dict("records")
    has_a1c = lambda r: not math.isnan(r["hba1c"])  # noqa: E731

    # 1. taylor_prop matches the plain-loop reference to 1e-12 (whole sample).
    res = S.taylor_prop(df, "", "hba1c >= 6.5")
    p_ref, se_ref = reference(rows, has_a1c, lambda r: r["hba1c"] >= 6.5, "wt_mec")
    assert abs(res["estimate"] - p_ref) < 1e-12, (res["estimate"], p_ref)
    assert abs(res["se"] - se_ref) < 1e-12, (res["se"], se_ref)
    assert res["df"] == 2 and res["weight"] == "wt_mec"

    # 2. Domain estimation keeps all PSUs: df unchanged, SE matches the full-design reference.
    #    "female" leaves every PSU populated; "strata == 1 and psu == 1" empties three PSUs.
    for dom, fn in [("female", lambda r: bool(r["female"])),
                    ("diag == 'no'", lambda r: r["diag"] == "no"),
                    ("strata == 1 and psu == 1", lambda r: r["strata"] == 1 and r["psu"] == 1)]:
        r_ = S.taylor_prop(df, dom, "hba1c >= 6.5")
        p_ref, se_ref = reference(rows, lambda r, fn=fn: fn(r) and has_a1c(r), lambda r: r["hba1c"] >= 6.5, "wt_mec")
        assert r_["df"] == res["df"] == S.design_df(df), (dom, r_["df"])
        assert abs(r_["estimate"] - p_ref) < 1e-12 and abs(r_["se"] - se_ref) < 1e-12, dom

    # 3. pick_weight: HbA1c -> wt_mec, glucose -> wt_fast, glucose with wt_mec -> ValueError.
    assert S.pick_weight(df, "", "hba1c >= 6.5") == "wt_mec"
    assert S.pick_weight(df, "", "glucose >= 126") == "wt_fast"
    assert S.pick_weight(df, "glucose >= 100", "hba1c >= 6.5") == "wt_fast"
    raises(ValueError, S.pick_weight, df, "", "glucose >= 126", weight="wt_mec")
    raises(ValueError, S.taylor_prop, df, "", "glucose >= 126", weight="wt_mec")
    g = S.taylor_prop(df, "", "glucose >= 126")
    p_ref, se_ref = reference(rows, lambda r: not math.isnan(r["glucose"]), lambda r: r["glucose"] >= 126, "wt_fast")
    assert g["weight"] == "wt_fast" and abs(g["estimate"] - p_ref) < 1e-12 and abs(g["se"] - se_ref) < 1e-12

    # 4. Missing outcome is excluded from the denominator, not counted as a non-event.
    assert res["n_unweighted"] == 11 and res["n_events"] == 5
    wrong = sum(r["wt_mec"] for r in rows if has_a1c(r) and r["hba1c"] >= 6.5) / sum(r["wt_mec"] for r in rows)
    assert abs(res["estimate"] - wrong) > 1e-6

    # 5. prevalence_ratio: rows with missing group variable are in neither arm.
    pr = S.prevalence_ratio(df, "", "hba1c >= 6.5", "insured")
    n1, n0 = pr["exposed"]["n_unweighted"], pr["reference"]["n_unweighted"]
    expected_n = sum(1 for r in rows if has_a1c(r) and pd.notna(r["insured"]))
    assert n1 + n0 == expected_n == 10, (n1, n0, expected_n)
    p1, _ = reference(rows, lambda r: has_a1c(r) and pd.notna(r["insured"]) and bool(r["insured"]), lambda r: r["hba1c"] >= 6.5, "wt_mec")
    p0, _ = reference(rows, lambda r: has_a1c(r) and pd.notna(r["insured"]) and not r["insured"], lambda r: r["hba1c"] >= 6.5, "wt_mec")
    assert abs(pr["estimate"] - p1 / p0) < 1e-12
    assert pr["ci_low"] < pr["estimate"] < pr["ci_high"]

    # 6. verdict truth table, ">=" (prediction 1.5, null 1.0) and the mirror "<=" (prediction 0.67, null 1.0).
    ge, le = {"op": ">=", "value": 1.5}, {"op": "<=", "value": 0.67}
    cases = [
        (1.8, 1.2, 2.4, ge, "supported"),      # estimate in region, CI excludes null
        (1.1, 0.9, 1.3, ge, "incompatible"),   # CI upper below prediction
        (1.6, 0.9, 2.5, ge, "inconclusive"),   # CI includes null
        (1.3, 1.1, 1.7, ge, "inconclusive"),   # estimate short of prediction, CI reaches it
        (0.5, 0.3, 0.8, le, "supported"),
        (0.9, 0.8, 1.1, le, "incompatible"),   # CI lower above prediction
        (0.6, 0.4, 1.2, le, "inconclusive"),
    ]
    for est, lo, hi, pred, want in cases:
        got = S.verdict(est, lo, hi, pred, null=1.0)["verdict"]
        assert got == want, (est, lo, hi, pred, got, want)
    assert S.verdict(None, None, None, ge, null=1.0)["verdict"] == "inconclusive"
    raises(ValueError, S.verdict, 1.0, 0.5, 1.5, {"op": ">", "value": 1.0}, 1.0)

    # 7. Unknown column names in filter expressions are rejected.
    raises(ValueError, S.taylor_prop, df, "nonexistent == 1", "hba1c >= 6.5")

    shutil.rmtree(TMP, ignore_errors=True)
    print("OK")


if __name__ == "__main__":
    main()
