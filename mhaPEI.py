"""PEI dashboard: EMR + ExtendedReach, built only from the aggregate CSVs in ./aggregates.

Run:  streamlit run mhaPEI.py        (folder override: PEI_AGG_DIR)
Refresh the CSVs locally with mhaPEIAggregates.py; this app never reads patient-level files.
"""
import itertools
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="PEI Dashboard", page_icon=":bar_chart:", layout="wide")

NAVY, BLUE, SKY, PALE, INK = "#0B3C5D", "#1D6FA5", "#6BB3E6", "#C7E3F8", "#0B2239"
st.markdown(
    f"""
<style>
.block-container{{padding-top:1.4rem;max-width:1400px}}
h1,h2,h3{{color:{NAVY}}}
[data-testid="stMetric"]{{background:#fff;border:1px solid #D6E4F2;border-left:5px solid {BLUE};
  border-radius:10px;padding:12px 16px;box-shadow:0 1px 3px rgba(11,60,93,.08)}}
[data-testid="stMetricValue"]{{color:{NAVY};font-weight:700}}
[data-testid="stMetricLabel"]{{color:#4A6A86}}
button[data-baseweb="tab"]{{font-weight:600}}
.hero{{background:linear-gradient(90deg,{NAVY},{BLUE});color:#fff;padding:18px 24px;border-radius:12px;margin-bottom:14px}}
.hero h1{{color:#fff;margin:0;font-size:1.7rem}}.hero p{{margin:2px 0 0;opacity:.85}}
</style>
<div class="hero"><h1>PEI Dashboard</h1><p>EMR and ExtendedReach aggregate data</p></div>
""",
    unsafe_allow_html=True,
)

AGG = Path(os.environ.get("PEI_AGG_DIR") or Path(__file__).parent / "aggregates")
AGE_ORDER = ["0-17", "18-29", "30-44", "45-64", "65+", "Unknown"]
BP_ORDER = ["Normal", "Elevated", "Stage 1", "Stage 2", "Hypertensive Crisis"]
A1C_ORDER = ["Normal (<5.7)", "Prediabetes (5.7-6.4)", "Diabetes (6.5+)"]
BMI_ORDER = ["Below 30", "Class 1 (30-34.9)", "Class 2 (35-39.9)", "Class 3 (40+)"]
_keys = itertools.count()


@st.cache_data
def _read(name, mtime):
    return pd.read_csv(AGG / f"{name}.csv")


def rd(name):
    p = AGG / f"{name}.csv"
    if not p.exists():
        st.error(f"Missing {p}. Run mhaPEIAggregates.py first.")
        st.stop()
    df = _read(name, p.stat().st_mtime)
    if "Month" in df:
        df = df[df["Month"].astype(str).str.fullmatch(r"\d{4}-\d{2}")]
    return df


def ramp(n):
    return [BLUE] if n <= 1 else px.colors.sample_colorscale("Blues", list(np.linspace(0.3, 0.95, n)))


def show(fig, height=340):
    fig.update_layout(
        template="plotly_white", height=height, margin=dict(l=8, r=8, t=44, b=8), font=dict(color=INK),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", y=-0.22, title=None),
        title=dict(font=dict(size=15, color=NAVY)))
    st.plotly_chart(fig, width="stretch", key=f"c{next(_keys)}")


def table(df):
    st.dataframe(df, width="stretch", hide_index=True, key=f"t{next(_keys)}")


def top_other(df, cat, val, top):
    d = df.groupby(cat, as_index=False)[val].sum().sort_values(val, ascending=False)
    if top and len(d) > top:
        d = pd.concat([d.iloc[:top], pd.DataFrame({cat: ["Other"], val: [d[val].iloc[top:].sum()]})])
    return d


def bar_h(df, cat, val, title, top=12):
    d = top_other(df, cat, val, top)
    if d.empty:
        return
    fig = px.bar(d, x=val, y=cat, orientation="h", text=val, title=title, color_discrete_sequence=[BLUE])
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(title=None)
    show(fig, max(260, 34 * len(d) + 90))


def donut(df, cat, val, title, top=8):
    d = top_other(df, cat, val, top)
    if d.empty:
        return
    fig = px.pie(d, names=cat, values=val, hole=0.55, title=title, color_discrete_sequence=ramp(len(d))[::-1])
    fig.update_traces(textinfo="percent", sort=False)
    show(fig)


def age_bar(df, cat, val, title):
    d = df.groupby(cat, as_index=False)[val].sum()
    d["o"] = d[cat].map({v: i for i, v in enumerate(AGE_ORDER)}).fillna(99)
    fig = px.bar(d.sort_values("o"), x=cat, y=val, text=val, title=title, color_discrete_sequence=[BLUE])
    fig.update_xaxes(title=None)
    fig.update_yaxes(title=None)
    show(fig)


def col_bar(x, y, title, color=BLUE):
    fig = px.bar(x=list(x), y=list(y), title=title, text=list(y), color_discrete_sequence=[color])
    fig.update_xaxes(title=None, type="category")
    fig.update_yaxes(title=None)
    show(fig)


def stack_month(df, cat, val, title, top=8, pct=False):
    keep = df.groupby(cat)[val].sum().nlargest(top).index
    d = df.assign(**{cat: df[cat].where(df[cat].isin(keep), "Other")}).groupby(["Month", cat], as_index=False)[val].sum()
    cats = list(d.groupby(cat)[val].sum().sort_values(ascending=False).index)
    fig = px.bar(d.sort_values("Month"), x="Month", y=val, color=cat, title=title, category_orders={cat: cats},
                 color_discrete_sequence=ramp(len(cats))[::-1])
    if pct:
        fig.update_layout(barnorm="percent")
    fig.update_xaxes(title=None, type="category")
    fig.update_yaxes(title=None)
    show(fig)


def class_stack(df, group, order, title):
    d = df.groupby([group, "Class"], as_index=False)["Patients"].sum()
    fig = px.bar(d, x=group, y="Patients", color="Class", title=title, category_orders={"Class": order},
                 color_discrete_sequence=ramp(len(order)))
    fig.update_xaxes(title=None)
    fig.update_yaxes(title=None)
    show(fig)


def month_filter(months, key):
    months = sorted(set(months))
    if len(months) < 2:
        return months[0] if months else "", months[-1] if months else ""
    return st.select_slider("Month range", months, (months[0], months[-1]), key=key)


# --------------------------------------------------------------------------- #
# EMR
# --------------------------------------------------------------------------- #
def render_emr():
    mon, canc, reasons = rd("emr_monthly"), rd("emr_cancellations_monthly"), rd("emr_cancel_reasons")
    demo, kpi, sites = rd("emr_demographics"), rd("emr_kpis").set_index("Metric")["Value"], rd("emr_site_monthly")
    vtm, cond = rd("emr_visit_type_monthly"), rd("emr_conditions")

    lo, hi = month_filter(list(mon["Month"]) + list(canc["Month"]), "emr_months")
    inr = lambda d: d[(d["Month"] >= lo) & (d["Month"] <= hi)]
    st.caption(f"Data through {kpi.get('Data through', 'n/a')}. 'Seen' = visits that were not cancelled, "
               "rescheduled or no-show. Demographics and chronic conditions cover all patients, not the month range.")
    tabs = st.tabs(["Overview", "Cancellations", "Patients", "Visits & sites", "Chronic conditions"])

    with tabs[0]:
        m = inr(mon)
        if m.empty:
            st.warning("No visits in this range.")
        else:
            full = mon.set_index("Month")
            cur = full.loc[m["Month"].iloc[-1]]
            i = list(full.index).index(m["Month"].iloc[-1])
            prev = full.iloc[i - 1] if i > 0 else None
            d = lambda c: None if prev is None or pd.isna(prev[c]) else round(float(cur[c] - prev[c]), 2)
            k = st.columns(5)
            k[0].metric(f"Avg visits / day ({m['Month'].iloc[-1]})", cur["AvgPerDay"], d("AvgPerDay"))
            k[1].metric("Patients seen (that month)", int(cur["PatientsSeen"]), d("PatientsSeen"))
            k[2].metric("Clinic days (that month)", int(cur["ClinicDays"]), d("ClinicDays"))
            k[3].metric("Patients on record", f"{int(kpi.get('Patients on record', 0)):,}")
            k[4].metric("Seen in last 12 months", f"{int(kpi.get('Seen in last 12 months', 0)):,}")
            st.caption("'Patients on record' = unique patient IDs in Encounters, used as the enrolled count. "
                       "Deltas compare to the prior month; the latest month may be partial.")
            a, b = st.columns(2)
            with a:
                col_bar(m["Month"], m["AvgPerDay"], "Average appointments per clinic day")
            with b:
                col_bar(m["Month"], m["PatientsSeen"], "Unique patients seen per month", SKY)
            a, b = st.columns(2)
            with a:
                col_bar(m["Month"], m["ClinicDays"], "Days clinic was in service", NAVY)
            with b:
                st.markdown("**Month-over-month change in average visits per day**")
                table(m.iloc[::-1][["Month", "AvgPerDay", "MoMPct", "Visits", "ClinicDays", "PatientsSeen"]])

    with tabs[1]:
        c, r = inr(canc), inr(reasons)
        if c.empty:
            st.info("No cancelled or rescheduled visits in this range.")
        else:
            tot, rs = int(c["Cancelled"].sum()), int(c["Rescheduled"].sum())
            k = st.columns(4)
            k[0].metric("Cancelled", f"{tot:,}")
            k[1].metric("Rescheduled", f"{rs:,}")
            k[2].metric("Reschedule rate", f"{rs / tot:.0%}" if tot else "n/a")
            k[3].metric("No-shows", f"{int(c['NoShow'].sum()):,}")
            long = c.assign(**{"Not rescheduled": c["Cancelled"] - c["Rescheduled"]}).melt(
                "Month", ["Rescheduled", "Not rescheduled"], "Outcome", "Count")
            fig = px.bar(long, x="Month", y="Count", color="Outcome", title="Cancellations per month",
                         color_discrete_map={"Rescheduled": BLUE, "Not rescheduled": PALE})
            fig.update_xaxes(title=None, type="category")
            show(fig)
            a, b = st.columns(2)
            with a:
                bar_h(r, "Reason", "Count", "Cancellation reasons")
            with b:
                stack_month(r, "Reason", "Count", "Reasons by month")
            st.markdown("**Rescheduled vs not, by reason**")
            table(r.pivot_table(index="Reason", columns="Rescheduled", values="Count", aggfunc="sum", fill_value=0)
                  .rename(columns={True: "Rescheduled", False: "Not rescheduled"}).reset_index())

    with tabs[2]:
        g = lambda dim: demo[demo["Dimension"] == dim]
        k = st.columns(3)
        k[0].metric("Patients on record", f"{int(kpi.get('Patients on record', 0)):,}")
        k[1].metric("Languages", len(g("Language")))
        k[2].metric("Payers", len(g("Payer")))
        a, b, c = st.columns(3)
        with a:
            age_bar(g("Age group"), "Value", "Patients", "Age")
        with b:
            donut(g("Ethnicity"), "Value", "Patients", "Ethnicity")
        with c:
            donut(g("Gender"), "Value", "Patients", "Gender")
        a, b, c = st.columns(3)
        with a:
            bar_h(g("Payer"), "Value", "Patients", "Payer make-up", 10)
        with b:
            bar_h(g("Language"), "Value", "Patients", "Language", 10)
        with c:
            bar_h(g("Zip"), "Value", "Patients", "Zip code", 15)

    with tabs[3]:
        field = st.radio("Break encounters down by", sorted(vtm["Field"].unique()), horizontal=True)
        v = inr(vtm[vtm["Field"] == field])
        a, b = st.columns(2)
        with a:
            d = top_other(v, "Value", "Count", 15)
            d["Share"] = (d["Count"] / d["Count"].sum() * 100).round(1)
            fig = px.bar(d, x="Share", y="Value", orientation="h", text=d["Share"].map("{:.1f}%".format),
                         title=f"% of kept visits by {field.lower()}", color_discrete_sequence=[BLUE])
            fig.update_yaxes(autorange="reversed", title=None)
            fig.update_xaxes(title=None)
            show(fig, max(260, 34 * len(d) + 90))
        with b:
            stack_month(v, "Value", "Count", f"{field} mix by month (%)", pct=True)
        table(d.rename(columns={"Value": field, "Share": "Share %"}))
        s = inr(sites)
        a, b = st.columns(2)
        with a:
            stack_month(s, "Site", "Count", "Visits by site per month")
        with b:
            pv = s.pivot_table(index="Month", columns="Site", values="Count", aggfunc="sum", fill_value=0)
            pv["Total"] = pv.sum(axis=1)
            table(pv.iloc[::-1].reset_index())

    with tabs[4]:
        st.caption("Each patient's most recent reading (by encounter date). Only patients with a reading are counted.")
        for name, label, order, positive in [
            ("Hypertension", "Hypertension (blood pressure)", BP_ORDER, ["Stage 1", "Stage 2", "Hypertensive Crisis"]),
            ("Diabetes (A1c)", "Diabetes (A1c)", A1C_ORDER, ["Diabetes (6.5+)"]),
            ("Obesity (BMI)", "Obesity (BMI)", BMI_ORDER, ["Class 1 (30-34.9)", "Class 2 (35-39.9)", "Class 3 (40+)"]),
        ]:
            st.subheader(label)
            j = cond[cond["Condition"] == name]
            if j.empty:
                st.info("No readings found.")
                continue
            tot = int(j["Patients"].sum())
            kk = st.columns(len(order) + 1)
            kk[0].metric("Patients with reading", f"{tot:,}")
            for i, cl in enumerate(order):
                kk[i + 1].metric(cl, f"{int(j.loc[j['Class'] == cl, 'Patients'].sum()):,}")
            pos = int(j.loc[j["Class"].isin(positive), "Patients"].sum())
            st.markdown(f"**{pos:,} patients ({pos / tot:.0%}) in a positive category: {', '.join(positive)}**")
            a, b = st.columns(2)
            with a:
                class_stack(j, "Age Group", order, "By age group")
            with b:
                class_stack(j, "Gender", order, "By gender")


# --------------------------------------------------------------------------- #
# ExtendedReach
# --------------------------------------------------------------------------- #
def render_er():
    sm, sd, sr, ss, ds = (rd("er_screenings_monthly"), rd("er_screening_demographics"), rd("er_screening_results"),
                          rd("er_screening_stats"), rd("er_distributions"))
    lo, hi = month_filter(list(sm["Month"]) + list(ds["Month"]), "er_months")
    inr = lambda d: d[(d["Month"] >= lo) & (d["Month"] <= hi)]
    sm, ds = inr(sm), inr(ds)
    da = ds[ds["Dimension"] == "(all)"]
    st.caption("Distribution units mix boxes, bags and single items; the item table shows what each is measured in. "
               "Demographics and screening results cover all dates.")
    tabs = st.tabs(["Overview", "Screenings", "Distributions"])

    with tabs[0]:
        k = st.columns(4)
        k[0].metric("Screenings", f"{int(sm['Count'].sum()):,}")
        k[1].metric("Screening types", sm["Type"].nunique())
        k[2].metric("Units distributed", f"{int(da['Units'].sum()):,}")
        k[3].metric("Distribution events", f"{int(da['Events'].sum()):,}")
        a, b = st.columns(2)
        with a:
            if len(sm):
                stack_month(sm, "Type", "Count", "Screenings per month")
        with b:
            if len(da):
                stack_month(da, "Item", "Units", "Units distributed per month")

    with tabs[1]:
        if sm.empty:
            st.info("No screenings in this range.")
        else:
            k = st.columns(4)
            k[0].metric("Total screenings", f"{int(sm['Count'].sum()):,}")
            for i, (t, n) in enumerate(sm.groupby("Type")["Count"].sum().nlargest(3).items()):
                k[i + 1].metric(t, f"{int(n):,}")
            a, b = st.columns(2)
            with a:
                bar_h(sm, "Type", "Count", "Screenings by type", 15)
            with b:
                stack_month(sm, "Type", "Count", "Screenings by month and type")
            types = ["All screening types"] + sorted(sd["Type"].unique())
            pick = st.selectbox("Screening type", types)
            d = sd if pick == types[0] else sd[sd["Type"] == pick]
            g = lambda dim: d[d["Dimension"] == dim]
            st.markdown("#### Who we screened")
            a, b, c = st.columns(3)
            with a:
                age_bar(g("Age group"), "Value", "Count", "Age")
            with b:
                donut(g("Gender"), "Value", "Count", "Gender")
            with c:
                bar_h(g("Race"), "Value", "Count", "Race", 8)
            a, b = st.columns(2)
            with a:
                bar_h(g("Zip"), "Value", "Count", "Zip code", 15)
            with b:
                bar_h(g("Event type"), "Value", "Count", "Event type", 10)
            if pick != types[0]:
                st.markdown("#### Results and follow-up")
                stt = ss[ss["Type"] == pick]
                if len(stt):
                    kk = st.columns(len(stt))
                    for c, (_, r) in zip(kk, stt.iterrows()):
                        c.metric(r["Metric"], r["Value"])
                r = sr[sr["Type"] == pick]
                fields = list(r["Field"].unique())
                cols = st.columns(2)
                for i, f in enumerate(fields):
                    with cols[i % 2]:
                        bar_h(r[r["Field"] == f], "Value", "Count", f, 10)

    with tabs[2]:
        if da.empty:
            st.info("No distributions in this range.")
        else:
            items = da.groupby("Item").agg(Events=("Events", "sum"), Units=("Units", "sum"),
                                           MeasuredAs=("MeasuredAs", "first")).sort_values("Units", ascending=False)
            k = st.columns(4)
            k[0].metric("Total units", f"{int(items['Units'].sum()):,}")
            k[1].metric("Events", f"{int(items['Events'].sum()):,}")
            k[2].metric("Item types", len(items))
            k[3].metric("Top item", items.index[0], f"{int(items['Units'].iloc[0]):,} units")
            a, b = st.columns(2)
            with a:
                fig = px.bar(items.reset_index(), x="Units", y="Item", orientation="h", text="Units",
                             title="Units distributed by item", color_discrete_sequence=[BLUE])
                fig.update_yaxes(autorange="reversed", title=None)
                fig.update_xaxes(title=None)
                show(fig, max(300, 32 * len(items) + 90))
            with b:
                stack_month(da, "Item", "Units", "Units per month by item")
            table(items.reset_index().rename(columns={"MeasuredAs": "Measured as"}))
            st.markdown("#### Drill into one item")
            it = st.selectbox("Item", list(items.index))
            sub = da[da["Item"] == it].groupby("Month", as_index=False)["Units"].sum()
            col_bar(sub["Month"], sub["Units"], f"{it}: units per month")
            dd = ds[(ds["Item"] == it) & (ds["Dimension"] != "(all)")]
            if len(dd):
                dim = st.selectbox("Break down by", sorted(dd["Dimension"].unique()))
                bar_h(dd[dd["Dimension"] == dim], "Value", "Units", f"Units by {dim}", 15)


tab_emr, tab_er = st.tabs(["EMR data", "ExtendedReach data"])
with tab_emr:
    render_emr()
with tab_er:
    render_er()
