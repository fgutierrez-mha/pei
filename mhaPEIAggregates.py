"""Build identifier-free aggregate CSVs from the PEI Excel files (exact counts, no suppression).

Run locally:  python mhaPEIAggregates.py [data_folder] [output_folder]
Defaults:     Desktop/PEI  ->  ./aggregates
No names, IDs, DOBs or free text are written; every table is counts/sums by category.
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "OneDrive - Imperial Beach Community Clinic" / "Desktop" / "PEI"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent / "aggregates"
OUT.mkdir(exist_ok=True)

SEEN = ["complete", "chk :", "arr :"]  # completed / checked out / checked in
CANCEL, RESCHED = ["cancel", "canc"], ["resched", "r/s"]
NOSHOW = ["no show", "no-show", "noshow", "n/s", "left without", "lwbs"]
AGE_BINS, AGE_LABELS = [0, 18, 30, 45, 65, 200], ["0-17", "18-29", "30-44", "45-64", "65+"]
BASE = {"ERActivityID", "ActivityType", "Program", "ActivityDate", "Status", "PerformedBy", "Agency", "ERStaffID",
        "ParticipantsTotal", "ParticipantsNew", "ExportDate", "URL", "CreatedDate", "Screening_Gender", "Number of Par",
        "Date", "Month"}
BLOCK = re.compile(r"dob|initial|name|note|signature|lot|expir|time|temperature|date|roi|zip|age|comment|phone|address", re.I)
DIMS = ["Organization", "Event", "City", "Zip Code", "Distributed by CLSD?", "Select relevant Narcan kiosk if applicable.", "Dropdown"]


def save(df, name):
    df.to_csv(OUT / f"{name}.csv", index=False)
    print(f"{name}.csv  {len(df)} rows")


def has(s, words):
    pat = "|".join(re.escape(w) for w in words)
    return s.fillna("").astype(str).str.lower().str.contains(pat, regex=True)


def cat(s):
    return s.fillna("Unknown").astype(str).str.strip().replace("", "Unknown")


def tame(s, min_total=5, maxlen=45):
    """Collapse free-text values (rare or long) into one bucket; counts stay exact."""
    s = cat(s)
    vc = s.value_counts()
    ok = set(vc[(vc >= min_total) & (vc.index.str.len() <= maxlen)].index)
    return s.where(s.isin(ok), "Other (free text)")


def agegrp(a):
    return pd.cut(a, AGE_BINS, labels=AGE_LABELS, right=False).astype(object).fillna("Unknown")


def count(df, cols, name="Count"):
    return df.groupby(cols, dropna=False).size().reset_index(name=name)


def bp_cls(s, d):
    c = np.select([(s > 180) | (d > 120), (s >= 140) | (d >= 90), (s >= 130) | (d >= 80), (s >= 120) & (d < 80)],
                  ["Hypertensive Crisis", "Stage 2", "Stage 1", "Elevated"], "Normal")
    return pd.Series(c, index=s.index).where(s.notna() & d.notna())


def a1c_cls(x):
    return pd.Series(np.select([x >= 6.5, x >= 5.7], ["Diabetes (6.5+)", "Prediabetes (5.7-6.4)"], "Normal (<5.7)"),
                     index=x.index).where(x.notna())


def bmi_cls(x):
    return pd.Series(np.select([x >= 40, x >= 35, x >= 30], ["Class 3 (40+)", "Class 2 (35-39.9)", "Class 1 (30-34.9)"],
                               "Below 30"), index=x.index).where(x.notna())


def parse_bp(v):
    p = re.findall(r"(\d{2,3})\s*/\s*(\d{2,3})", str(v))
    return (float(p[-1][0]), float(p[-1][1])) if p else (np.nan, np.nan)


def latest(df):
    return df.sort_values("Date", kind="mergesort", na_position="first").drop_duplicates("Patient ID", keep="last")


# ------------------------------------------------------------------ EMR ----
def emr():
    enc = pd.read_excel(DATA / "Encounters.xlsx", dtype={"Patient ZIP Code": str})
    vit, labs = pd.read_excel(DATA / "Vitals.xlsx"), pd.read_excel(DATA / "Labs.xlsx")
    enc["Date"] = pd.to_datetime(enc["Appointment Date"], errors="coerce")
    enc = enc.dropna(subset=["Date"]).copy()
    enc["Month"] = enc["Date"].dt.to_period("M").astype(str)
    enc["is_cancel"], enc["is_resched"], enc["is_noshow"] = (has(enc["Visit Status"], w) for w in (CANCEL, RESCHED, NOSHOW))
    enc["is_seen"] = has(enc["Visit Status"], SEEN) & ~(enc["is_cancel"] | enc["is_resched"] | enc["is_noshow"])
    seen = enc[enc["is_seen"]]

    g = seen.groupby("Month")
    m = pd.DataFrame({"Visits": g.size(), "ClinicDays": g["Date"].nunique(), "PatientsSeen": g["Patient ID"].nunique()})
    m["AvgPerDay"] = (m["Visits"] / m["ClinicDays"]).round(2)
    m["MoMPct"] = (m["AvgPerDay"].pct_change(fill_method=None) * 100).round(1)
    save(m.reset_index(), "emr_monthly")

    last_kept = seen.groupby("Patient ID")["Date"].max()
    canc = enc[enc["is_cancel"] | enc["is_resched"]].copy()
    canc["Rescheduled"] = canc["is_resched"] | (canc["Patient ID"].map(last_kept) > canc["Date"])
    cm = canc.groupby("Month").agg(Cancelled=("Date", "size"), Rescheduled=("Rescheduled", "sum"))
    cm["NoShow"] = enc[enc["is_noshow"]].groupby("Month").size()
    save(cm.fillna(0).astype(int).reset_index(), "emr_cancellations_monthly")
    canc["Reason"] = cat(canc["Visit Status"])  # Visit Status carries the cancel type; the Reason column is free text
    save(count(canc, ["Month", "Reason", "Rescheduled"]), "emr_cancel_reasons")

    pts = enc.sort_values("Date").groupby("Patient ID").tail(1).copy()
    pts["Age"] = (enc["Date"].max() - pd.to_datetime(pts["Patient DOB"], errors="coerce")).dt.days / 365.25
    pts["Age Group"] = agegrp(pts["Age"])
    pts["Zip"] = pts["Patient ZIP Code"].astype(str).str.extract(r"(\d{5})")[0]
    demo = pd.concat([count(pts.assign(Value=cat(pts[c])), ["Value"], "Patients").assign(Dimension=d) for d, c in [
        ("Age group", "Age Group"), ("Ethnicity", "Patient Ethnicity"), ("Gender", "Patient Gender"),
        ("Payer", "Primary Insurance Name"), ("Language", "Patient Language"), ("Zip", "Zip")]])
    save(demo[["Dimension", "Value", "Patients"]], "emr_demographics")

    end = enc["Date"].max()
    save(pd.DataFrame({"Metric": ["Patients on record", "Seen in last 12 months", "Data through"],
                       "Value": [enc["Patient ID"].nunique(),
                                 seen[seen["Date"] > end - pd.DateOffset(years=1)]["Patient ID"].nunique(),
                                 str(end.date())]}), "emr_kpis")

    seen = seen.assign(Site=cat(seen["Appointment Facility Name"]))
    save(count(seen, ["Month", "Site"]), "emr_site_monthly")
    save(pd.concat([count(seen.assign(Value=tame(seen[f])), ["Month", "Value"]).assign(Field=f)
                    for f in ["Visit Type", "Reason"] if f in seen])[["Month", "Field", "Value", "Count"]],
         "emr_visit_type_monthly")

    # chronic conditions: latest reading per patient (by encounter date)
    edate = enc.drop_duplicates("Encounter ID").set_index("Encounter ID")["Date"]
    vt = vit["Standard Vital Type"].fillna("").astype(str) + " " + vit["Vitals"].fillna("").astype(str)
    vit["Date"] = vit["Encounter ID"].map(edate)
    bp = vit[has(vt, ["blood pressure", "systolic", "bp"])].copy()
    bp[["s", "d"]] = [parse_bp(x) for x in bp["Value"]]
    bp = latest(bp[bp["s"].notna() & bp["d"].notna()])
    bp["cls"] = bp_cls(bp["s"], bp["d"])
    bmi = vit[has(vt, ["bmi", "body mass"])].copy()
    bmi["v"] = pd.to_numeric(bmi["Value"], errors="coerce")
    bmi = latest(bmi[bmi["v"].between(10, 90)])
    bmi["cls"] = bmi_cls(bmi["v"])
    la = labs[has(labs["Lab Attribute"].fillna("") + " " + labs["Order Name"].fillna(""), ["a1c"])].copy()
    la["v"] = pd.to_numeric(la["Lab Attribute Value"].astype(str).str.extract(r"(\d+\.?\d*)")[0], errors="coerce")
    la["Date"] = pd.to_datetime(la["Collection / Performed Date"], errors="coerce").fillna(la["Encounter ID"].map(edate))
    la = latest(la[la["v"].between(3, 20)])
    la["cls"] = a1c_cls(la["v"])
    info = pts[["Patient ID", "Age Group", "Patient Gender"]]
    rows = []
    for cond, df in [("Hypertension", bp), ("Diabetes (A1c)", la), ("Obesity (BMI)", bmi)]:
        j = df[["Patient ID", "cls"]].merge(info, on="Patient ID")
        j["Gender"] = cat(j["Patient Gender"])
        rows.append(count(j, ["Age Group", "Gender", "cls"], "Patients").rename(columns={"cls": "Class"}).assign(Condition=cond))
    save(pd.concat(rows)[["Condition", "Class", "Age Group", "Gender", "Patients"]], "emr_conditions")


# ------------------------------------------------------ ExtendedReach ----
def gender(df):
    g = df["Gender"] if "Gender" in df else pd.Series(np.nan, index=df.index, dtype=object)
    if "Screening_Gender" in df:
        g = g.fillna(df["Screening_Gender"])
    t = g.fillna("").astype(str).str.strip().str.lower()
    return pd.Series(np.select([t.str.startswith(("f", "w")), t.str.startswith("m"), t == ""], ["Female", "Male", "Unknown"],
                               default=g.astype(str).str.strip().str.title()), index=df.index)


def er():
    x = pd.read_excel(DATA / "GeneralActivities_Split.xlsx", sheet_name=None, dtype=object)
    scr_m, scr_d, scr_r, scr_s, dist = [], [], [], [], []
    for sheet, df in x.items():
        if sheet.startswith("_") or df.empty or "ActivityType" not in df:
            continue
        t = str(df["ActivityType"].dropna().iloc[0])
        df = df.copy()
        df["Month"] = pd.to_datetime(df["ActivityDate"], errors="coerce").dt.to_period("M").astype(str)
        low = t.lower()
        if "screening" in low:
            scr_m.append(count(df, ["Month"]).assign(Type=t))
            age = pd.to_numeric(df["Age"], errors="coerce") if "Age" in df else pd.Series(np.nan, index=df.index)
            d = pd.DataFrame({"Age group": agegrp(age), "Gender": gender(df)})
            for c, n in [("Race", "Race"), ("Event Type", "Event type")]:
                d[n] = cat(df[c]) if c in df else "Unknown"
            d["Zip"] = df["Zip Code"].astype(str).str.extract(r"(\d{5})")[0].fillna("Unknown") if "Zip Code" in df else "Unknown"
            for n in d:
                scr_d.append(count(d.assign(Value=d[n]), ["Value"]).assign(Type=t, Dimension=n))
            num = lambda c: pd.to_numeric(df[c], errors="coerce")
            res = {}
            if {"Systolic", "Diastolic"} <= set(df):
                s, dd = num("Systolic"), num("Diastolic")
                res["BP category"] = bp_cls(s, dd)
                scr_s += [(t, "Avg systolic", s.mean()), (t, "Avg diastolic", dd.mean())]
            if "A1C %" in df:
                v = pd.to_numeric(df["A1C %"].astype(str).str.extract(r"(\d+\.?\d*)")[0], errors="coerce")
                res["A1c category"] = a1c_cls(v)
                scr_s.append((t, "Avg A1c", v.mean()))
            if "TC" in df:
                tc, ldl, hdl = num("TC"), num("LDL"), num("HDL")
                res["Total cholesterol"] = pd.Series(np.select([tc >= 240, tc >= 200], ["High (240+)", "Borderline (200-239)"],
                                                               "Desirable (<200)"), index=df.index).where(tc.notna())
                res["LDL"] = pd.Series(np.select([ldl >= 190, ldl >= 160, ldl >= 130, ldl >= 100],
                                                 ["Very high (190+)", "High (160-189)", "Borderline (130-159)",
                                                  "Near optimal (100-129)"], "Optimal (<100)"), index=df.index).where(ldl.notna())
                res["HDL"] = pd.Series(np.where(hdl < 40, "Low (<40)", "OK (40+)"), index=df.index).where(hdl.notna())
                scr_s += [(t, "Avg total cholesterol", tc.mean()), (t, "Avg LDL", ldl.mean()), (t, "Avg HDL", hdl.mean())]
            for c in df.columns:
                if c not in BASE and not BLOCK.search(c) and 2 <= df[c].dropna().astype(str).nunique() <= 15:
                    res[c] = df[c]
            for field, ser in res.items():
                scr_r.append(count(pd.DataFrame({"Value": cat(ser.dropna())}), ["Value"]).assign(Type=t, Field=field))
        elif "distribut" in low and "redistribut" not in low:
            qc = [c for c in df.columns if c not in BASE and not re.search(r"tests per|participants|lot|order", c, re.I)
                  and (c.startswith("#") or c.lower() in ("number", "quantity"))]
            q = (pd.concat([pd.to_numeric(df[c], errors="coerce") for c in qc], axis=1).sum(axis=1, min_count=1)
                 if qc else pd.Series(np.nan, index=df.index)).fillna(0)
            item = re.sub(r"\s*distribution\s*$", "", t, flags=re.I).strip()
            base = pd.DataFrame({"Month": df["Month"], "Qty": q})
            for dim in ["(all)"] + [c for c in DIMS if c in df]:
                b = base.assign(Value=cat(df[dim]) if dim != "(all)" else "(all)")
                g = b.groupby(["Month", "Value"]).agg(Events=("Qty", "size"), Units=("Qty", "sum")).reset_index()
                dist.append(g.assign(Item=item, Dimension=dim, MeasuredAs=", ".join(qc) or "rows"))
    save(pd.concat(scr_m)[["Month", "Type", "Count"]], "er_screenings_monthly")
    save(pd.concat(scr_d)[["Type", "Dimension", "Value", "Count"]], "er_screening_demographics")
    save(pd.concat(scr_r)[["Type", "Field", "Value", "Count"]], "er_screening_results")
    save(pd.DataFrame(scr_s, columns=["Type", "Metric", "Value"]).round(2), "er_screening_stats")
    save(pd.concat(dist)[["Month", "Item", "Dimension", "Value", "Events", "Units", "MeasuredAs"]], "er_distributions")


if __name__ == "__main__":
    emr()
    er()
    print("Wrote", OUT)
