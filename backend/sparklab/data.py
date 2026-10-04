"""NHANES download, merge on SEQN, derived columns, sealing of the hold-out.

CLI:
    python -m sparklab.data --cycle J            # discovery: download + build
    python -m sparklab.data --cycle I --seal     # hold-out: download + zip + hash. NOT processed.
    python -m sparklab.data --cycle J --raw-dir path/   # use already-downloaded XPT files
"""
import argparse
import hashlib
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from sparklab import config as C

COLUMNS_DOC = {
    "seqn": "respondent id (SEQN)",
    "cycle": "NHANES cycle letter (J discovery, I hold-out)",
    "age": "age in years (RIDAGEYR)",
    "adult": "age >= 20",
    "female": "RIAGENDR == 2",
    "pregnant": "RIDEXPRG == 1",
    "race_eth": "RIDRETH3 label. Any analysis by race/ethnicity needs human review before publication",
    "pir": "family income to poverty ratio (INDFMPIR)",
    "bmi": "BMXBMI",
    "diag": "'yes' / 'no' / 'borderline' from DIQ010 (7/9 -> missing)",
    "insulin_now": "DIQ050 == 1",
    "pills_now": "DIQ070 == 1",
    "no_meds_declared": "no insulin or pills declared currently (never say 'untreated')",
    "hba1c": "LBXGH, %",
    "hba1c_cat": "'normal' (<5.7) / 'prediabetes' (5.7-<6.5) / 'diabetes' (>=6.5)",
    "glucose": "LBXGLU fasting plasma glucose, mg/dL (use only with wt_fast)",
    "glucose_cat": "'normal' (<100) / 'prediabetes' (100-<126) / 'diabetes' (>=126)",
    "undiagnosed": "diag == 'no' and hba1c >= 6.5",
    "insured": "HIQ011 == 1 (7/9 -> missing)",
    "routine_place": "HUQ030 in (1, 3) (7/9 -> missing)",
    "wt_mec": "WTMEC2YR, use with HbA1c",
    "wt_fast": "WTSAF2YR, use only with glucose (0 = did not fast)",
    "strata": "SDMVSTRA",
    "psu": "SDMVPSU",
}

RACE_LABELS = {1: "mexican_american", 2: "other_hispanic", 3: "nh_white",
               4: "nh_black", 6: "nh_asian", 7: "other_multi"}


# ---------- reading ----------

def _read_component(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".xpt":
        return pd.read_sas(path, format="xport", encoding="utf-8")
    if path.suffix.lower() == ".csv":  # synthetic test data
        return pd.read_csv(path)
    raise ValueError(f"unsupported file type: {path}")


def _find(raw_dir: Path, comp: str, cycle: str) -> Path:
    for p in raw_dir.iterdir():
        if p.stem.upper() == f"{comp}_{cycle}" and p.suffix.lower() in (".xpt", ".csv"):
            return p
    raise FileNotFoundError(f"{comp}_{cycle} not found in {raw_dir}")


def download(cycle: str, dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for comp in C.COMPONENTS:
        target = dest / f"{comp}_{cycle}.xpt"
        if target.exists():
            out.append(target)
            continue
        last_err = None
        for pattern in C.CDC_URL_PATTERNS:
            url = pattern.format(year=C.CYCLE_YEAR[cycle], label=C.CYCLE_LABEL[cycle], comp=comp, cycle=cycle)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "sparklab/0.1"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    body = r.read()
                if body[:6] != b"HEADER":  # CDC returns an HTML page instead of 404 sometimes
                    raise ValueError("not an XPT file")
                target.write_bytes(body)
                print(f"  {comp}_{cycle}: {url}")
                break
            except Exception as e:  # try next pattern
                last_err = e
        else:
            raise RuntimeError(f"could not download {comp}_{cycle}: {last_err}")
        out.append(target)
    return out


# ---------- deriving ----------

def _yn(series: pd.Series, yes=(1,), no=(2,)) -> pd.Series:
    out = pd.Series(pd.NA, index=series.index, dtype="boolean")
    out[series.isin(yes)] = True
    out[series.isin(no)] = False
    return out


def _cat(x: pd.Series, lo: float, hi: float) -> pd.Series:
    out = pd.Series(pd.NA, index=x.index, dtype="object")
    out[x < lo] = "normal"
    out[(x >= lo) & (x < hi)] = "prediabetes"
    out[x >= hi] = "diabetes"
    return out


def build_frame(frames: dict[str, pd.DataFrame], cycle: str) -> pd.DataFrame:
    """Merge components on SEQN (left join on DEMO) and derive analysis columns."""
    df = frames["DEMO"]
    for comp in C.COMPONENTS:
        if comp != "DEMO":
            df = df.merge(frames[comp], on="SEQN", how="left", suffixes=("", f"_{comp}"))

    def col(name):
        return df[name] if name in df else pd.Series(np.nan, index=df.index)

    out = pd.DataFrame(index=df.index)
    out["seqn"] = df["SEQN"].astype("int64")
    out["cycle"] = cycle
    out["age"] = col("RIDAGEYR")
    out["adult"] = (out["age"] >= C.ADULT_AGE).astype("boolean")
    out["female"] = (col("RIAGENDR") == 2).astype("boolean")
    out["pregnant"] = (col("RIDEXPRG") == 1).astype("boolean")
    out["race_eth"] = col("RIDRETH3").map(RACE_LABELS)
    out["pir"] = col("INDFMPIR")
    out["bmi"] = col("BMXBMI")
    out["diag"] = col("DIQ010").map({1: "yes", 2: "no", 3: "borderline"})  # 7/9 -> NaN
    out["insulin_now"] = (col("DIQ050") == 1).astype("boolean")
    out["pills_now"] = (col("DIQ070") == 1).astype("boolean")
    out["no_meds_declared"] = ~(out["insulin_now"] | out["pills_now"])
    out["hba1c"] = col("LBXGH")
    out["hba1c_cat"] = _cat(out["hba1c"], C.HBA1C_PREDIABETES, C.HBA1C_DIABETES)
    out["glucose"] = col("LBXGLU")
    out["glucose_cat"] = _cat(out["glucose"], C.GLUCOSE_PREDIABETES, C.GLUCOSE_DIABETES)
    und = pd.Series(pd.NA, index=df.index, dtype="boolean")
    known = out["diag"].notna() & out["hba1c"].notna()
    und[known] = (out.loc[known, "diag"] == "no") & (out.loc[known, "hba1c"] >= C.HBA1C_DIABETES)
    out["undiagnosed"] = und
    out["insured"] = _yn(col("HIQ011"))
    out["routine_place"] = _yn(col("HUQ030"), yes=(1, 3), no=(2,))
    out["wt_mec"] = col("WTMEC2YR").fillna(0.0)
    out["wt_fast"] = col("WTSAF2YR").fillna(0.0)
    out["strata"] = col("SDMVSTRA").astype("int64")
    out["psu"] = col("SDMVPSU").astype("int64")
    return out


def build_from_dir(raw_dir: Path, cycle: str) -> pd.DataFrame:
    frames = {comp: _read_component(_find(raw_dir, comp, cycle)) for comp in C.COMPONENTS}
    return build_frame(frames, cycle)


# ---------- hashing / sealing ----------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def seal(raw_dir: Path | None = None, by: str = "human") -> str:
    """Zip the hold-out raw files, hash, record in ledger. Never derives or reads contents."""
    from sparklab import ledger

    if C.SEALED_ZIP.exists() or ledger.read("seal"):
        raise RuntimeError("hold-out already sealed; refusing to reseal")
    C.SEALED_DIR.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="sparklab_seal_"))
    try:
        src = raw_dir if raw_dir else tmp
        if raw_dir is None:
            download(C.HOLDOUT, tmp)
        with zipfile.ZipFile(C.SEALED_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
            for comp in C.COMPONENTS:
                p = _find(src, comp, C.HOLDOUT)
                z.write(p, arcname=p.name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    digest = sha256_file(C.SEALED_ZIP)
    ledger.append("seal", "human", {"cycle": C.HOLDOUT, "path": str(C.SEALED_ZIP.relative_to(C.ROOT)),
                                    "sha256": digest, "by": by})
    return digest


# ---------- loading ----------

def processed_path(cycle: str) -> Path:
    return C.PROCESSED_DIR / f"nhanes_{cycle}.pkl"


def load(cycle: str = C.DISCOVERY) -> pd.DataFrame:
    """Load the discovery cycle. The hold-out cannot be loaded through this function."""
    if cycle != C.DISCOVERY:
        raise PermissionError(f"cycle {cycle!r} is sealed; only sparklab.tools.run_test may compute on it")
    p = processed_path(cycle)
    if not p.exists():
        raise FileNotFoundError(f"{p} missing; run `python -m sparklab.data --cycle {cycle}`")
    return pd.read_pickle(p)


def load_holdout(prereg_id: str) -> pd.DataFrame:
    """Internal: called only by tools.run_test after its gates. Re-checks gates (defense in depth)."""
    from sparklab import ledger

    ok, why = ledger.holdout_gate(prereg_id)
    if not ok:
        raise PermissionError(why)
    p = C.HOLDOUT_DIR / f"nhanes_{C.HOLDOUT}.pkl"
    if not p.exists():
        raise PermissionError("hold-out not unsealed; a human must run `python -m sparklab.unseal`")
    return pd.read_pickle(p)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycle", required=True, choices=["J", "I"])
    ap.add_argument("--seal", action="store_true", help="hold-out only: zip + hash, do not process")
    ap.add_argument("--raw-dir", type=Path, help="use local XPT files instead of downloading")
    ap.add_argument("--by", default="human")
    a = ap.parse_args(argv)

    if a.cycle == C.HOLDOUT:
        if not a.seal:
            sys.exit("Refusing: the hold-out is only sealed here. Processing happens in `python -m sparklab.unseal`.")
        digest = seal(a.raw_dir, by=a.by)
        print(f"Sealed {C.SEALED_ZIP}\nSHA-256 {digest} (recorded in ledger)")
        return
    if a.seal:
        sys.exit("--seal is only for the hold-out cycle I")

    raw = a.raw_dir or (C.RAW_DIR / a.cycle)
    if a.raw_dir is None:
        print(f"Downloading NHANES {C.CYCLE_LABEL[a.cycle]} ...")
        download(a.cycle, raw)
    df = build_from_dir(raw, a.cycle)
    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_pickle(processed_path(a.cycle))
    adults = df.query(C.BASE_DOMAIN)
    print(f"Wrote {processed_path(a.cycle)}")
    print(f"rows={len(df)}  adults_not_pregnant={len(adults)}  "
          f"with_hba1c={int(adults['hba1c'].notna().sum())}  fasting={int((adults['wt_fast'] > 0).sum())}")
    print("diag counts (adults, unweighted):", adults["diag"].value_counts(dropna=False).to_dict())


if __name__ == "__main__":
    main()
