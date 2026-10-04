"""Design-based estimates for NHANES.

taylor_prop: weighted proportion with Taylor-linearized variance (strata x PSU, with-replacement
approximation), proper domain estimation (all PSUs kept), t-based CI with df = #PSU - #strata.
prevalence_ratio: log-PR with independent-SE approximation (declared limitation).
verdict: supported / incompatible / inconclusive against a pre-registered numeric prediction.
"""
import math
import re

import numpy as np
import pandas as pd
from scipy import stats as st

from sparklab import config as C

_IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
_KEYWORDS = {"and", "or", "not", "in", "True", "False", "None"}


def referenced_columns(expr: str, df: pd.DataFrame) -> list[str]:
    if not expr:
        return []
    # drop quoted strings first so 'no' etc. are not read as identifiers
    stripped = re.sub(r"'[^']*'|\"[^\"]*\"", "", expr)
    return [t for t in dict.fromkeys(_IDENT.findall(stripped)) if t not in _KEYWORDS and t in df.columns]


def unknown_names(expr: str, df: pd.DataFrame) -> list[str]:
    stripped = re.sub(r"'[^']*'|\"[^\"]*\"", "", expr or "")
    names = [t for t in dict.fromkeys(_IDENT.findall(stripped)) if t not in _KEYWORDS]
    return [t for t in names if t not in df.columns]


def mask(df: pd.DataFrame, expr: str) -> pd.Series:
    if not expr or not expr.strip():
        return pd.Series(True, index=df.index)
    bad = unknown_names(expr, df)
    if bad:
        raise ValueError(f"unknown column(s) {bad}; allowed: {sorted(df.columns)}")
    m = df.eval(expr, engine="python")
    return pd.Series(m, index=df.index).astype("boolean").fillna(False).astype(bool)


def pick_weight(df: pd.DataFrame, *exprs: str, weight: str = "") -> str:
    uses_glucose = any(c in ("glucose", "glucose_cat") for e in exprs for c in referenced_columns(e, df))
    auto = "wt_fast" if uses_glucose else "wt_mec"
    if weight and weight != auto:
        raise ValueError(f"weight {weight!r} not allowed here: expressions "
                         f"{'use' if uses_glucose else 'do not use'} glucose, so the weight must be {auto!r}")
    return auto


def design_df(df: pd.DataFrame) -> int:
    return int(df.groupby("strata")["psu"].nunique().sum() - df["strata"].nunique())


def _linearized_se(z: np.ndarray, strata: np.ndarray, psu: np.ndarray) -> float:
    t = pd.DataFrame({"z": z, "h": strata, "i": psu}).groupby(["h", "i"])["z"].sum()
    var = 0.0
    for _, g in t.groupby(level=0):
        n_h = len(g)
        if n_h > 1:
            var += n_h / (n_h - 1) * float(((g - g.mean()) ** 2).sum())
    return math.sqrt(var)


def domain_mask(df: pd.DataFrame, domain: str, outcome: str, weight: str, extra: str = "") -> pd.Series:
    """Base domain AND user domain AND non-missing outcome variables AND positive weight."""
    d = mask(df, C.BASE_DOMAIN) & mask(df, domain) & (df[weight] > 0)
    if extra:
        d &= mask(df, extra)
    for c in referenced_columns(outcome, df):
        d &= df[c].notna()
    return d


def taylor_prop(df: pd.DataFrame, domain: str, outcome: str, weight: str = "", _extra: str = "") -> dict:
    weight = pick_weight(df, domain, outcome, _extra, weight=weight)
    d = domain_mask(df, domain, outcome, weight, _extra).to_numpy()
    y = mask(df, outcome).to_numpy() & d
    w = df[weight].to_numpy(dtype=float)
    n = int(d.sum())
    events = int(y.sum())
    dof = design_df(df)
    res = {"estimate": None, "se": None, "ci_low": None, "ci_high": None, "df": dof,
           "n_unweighted": n, "n_events": events, "weight": weight,
           "domain": f"({C.BASE_DOMAIN}) and ({domain or 'True'})", "outcome": outcome}
    if n == 0:
        res["warning"] = "empty domain"
        return res
    wd = w * d
    tot = wd.sum()
    p = float((wd * y).sum() / tot)
    z = wd * (y - p) / tot
    se = _linearized_se(z, df["strata"].to_numpy(), df["psu"].to_numpy())
    tcrit = st.t.ppf(0.5 + C.CONFIDENCE / 2, dof)
    res.update(estimate=p, se=se, ci_low=max(0.0, p - tcrit * se), ci_high=min(1.0, p + tcrit * se))
    warns = []
    if n < C.MIN_CELL_N:
        warns.append(f"unweighted n={n} < {C.MIN_CELL_N}: descriptive only, cannot enter confirmatory")
    if dof < C.MIN_DF_WARN:
        warns.append(f"design df={dof} < {C.MIN_DF_WARN}")
    if warns:
        res["warning"] = "; ".join(warns)
    return res


def prevalence_ratio(df: pd.DataFrame, domain: str, outcome: str, group: str, weight: str = "") -> dict:
    """PR of outcome in `group` vs `not group`, within domain. Rows with missing group vars excluded."""
    weight = pick_weight(df, domain, outcome, group, weight=weight)
    valid_group = " and ".join(f"{c} == {c}" for c in referenced_columns(group, df)) or "True"
    # `x == x` is False for NA, so this drops rows where the grouping variable is missing
    g1 = taylor_prop(df, domain, outcome, weight, _extra=f"({valid_group}) and ({group})")
    g0 = taylor_prop(df, domain, outcome, weight, _extra=f"({valid_group}) and not ({group})")
    res = {"group": group, "exposed": g1, "reference": g0, "weight": weight,
           "estimate": None, "ci_low": None, "ci_high": None, "df": g1["df"],
           "approximation": "independent-SE log-PR (declared limitation)"}
    p1, p0 = g1["estimate"], g0["estimate"]
    if not p1 or not p0:
        res["warning"] = "zero or empty arm; PR undefined"
        return res
    se_log = math.sqrt((g1["se"] / p1) ** 2 + (g0["se"] / p0) ** 2)
    tcrit = st.t.ppf(0.5 + C.CONFIDENCE / 2, g1["df"])
    pr = p1 / p0
    res.update(estimate=pr, se_log=se_log,
               ci_low=math.exp(math.log(pr) - tcrit * se_log), ci_high=math.exp(math.log(pr) + tcrit * se_log))
    return res


def verdict(estimate, ci_low, ci_high, prediction: dict, null: float) -> dict:
    """Three-way verdict. prediction = {"op": ">=" | "<=", "value": x}.

    incompatible: the CI excludes the predicted region.
    supported:    point estimate inside the predicted region AND CI excludes the null.
    inconclusive: anything else. (p >= 0.05 is not death.)
    """
    if estimate is None or ci_low is None:
        return {"verdict": "inconclusive", "reason": "no estimate"}
    op, v = prediction["op"], float(prediction["value"])
    if op == ">=":
        if ci_high < v:
            return {"verdict": "incompatible", "reason": f"CI upper {ci_high:.4g} < predicted {v}"}
        if estimate >= v and ci_low > null:
            return {"verdict": "supported", "reason": f"estimate {estimate:.4g} >= {v} and CI excludes null {null}"}
    elif op == "<=":
        if ci_low > v:
            return {"verdict": "incompatible", "reason": f"CI lower {ci_low:.4g} > predicted {v}"}
        if estimate <= v and ci_high < null:
            return {"verdict": "supported", "reason": f"estimate {estimate:.4g} <= {v} and CI excludes null {null}"}
    else:
        raise ValueError("prediction.op must be '>=' or '<='")
    return {"verdict": "inconclusive", "reason": "CI compatible with both prediction and null, or estimate short of prediction"}
