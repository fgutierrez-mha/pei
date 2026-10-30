"""PEI dashboard: EMR + ExtendedReach, built only from the aggregate CSVs in ./aggregates.

Run:  streamlit run mhaPEI.py        (folder override: PEI_AGG_DIR)
Refresh the CSVs locally with mhaPEIAggregates.py; this app never reads patient-level files.
"""
import base64
import itertools
import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="PEI Dashboard", page_icon=":bar_chart:", layout="wide")

NAVY, BLUE, SKY, PALE, INK = "#1F3B7A", "#2F6DB5", "#7DB4E6", "#CFE3F7", "#12254D"
LOGO = Path(__file__).parent / "assets" / "mha_logo.png"
logo_html = ""
if LOGO.exists():
    logo_html = f'<img src="data:image/png;base64,{base64.b64encode(LOGO.read_bytes()).decode()}" alt="Mendonoma Health Alliance">'
st.markdown(
    f"""
<style>
.block-container{{padding-top:1.2rem;max-width:1400px}}
h1,h2,h3,h4{{color:{NAVY}}}
.hero{{display:flex;align-items:center;flex-wrap:wrap;gap:12px 28px;background:#fff;border:1px solid #DCE7F3;
  border-bottom:4px solid {BLUE};border-radius:14px;padding:14px 24px;margin-bottom:16px;box-shadow:0 2px 8px rgba(31,59,122,.07)}}
.hero img{{height:46px}}
.hero .t{{border-left:2px solid #DCE7F3;padding-left:24px}}
.hero h1{{margin:0;font-size:1.55rem;line-height:1.2}}.hero p{{margin:2px 0 0;color:#5B7090}}
[data-testid="stMetric"]{{background:#fff;border:1px solid #DCE7F3;border-top:4px solid {BLUE};border-radius:14px;
  padding:14px 18px;box-shadow:0 2px 8px rgba(31,59,122,.06)}}
[data-testid="stMetricValue"]{{color:{NAVY};font-weight:700;font-size:1.9rem}}
[data-testid="stMetricLabel"]{{color:#5B7090}}
[class*="st-key-card"]{{background:#fff;border:1px solid #DCE7F3;border-radius:14px;padding:6px 10px;
  box-shadow:0 2px 8px rgba(31,59,122,.06)}}
.stTabs [data-baseweb="tab-list"]{{gap:4px}}
.stTabs [data-baseweb="tab"]{{font-weight:600;color:#5B7090;padding:8px 16px}}
.stTabs [aria-selected="true"]{{color:{BLUE}}}
.period{{color:#5B7090;font-size:.9rem;margin:2px 0 10px}}
</style>
<div class="hero">{logo_html}<div class="t"><h1>PEI Dashboard</h1><p>EMR and ExtendedReach Aggregate Data</p></div></div>
""",
    unsafe_allow_html=True,
)

AGG = Path(os.environ.get("PEI_AGG_DIR") or Path(__file__).parent / "aggregates")
AGE_ORDER = ["0-17", "18-29", "30-44", "45-64", "65+", "Unknown"]
BP_ORDER = ["Normal", "Elevated", "Stage 1", "Stage 2", "Hypertensive Crisis"]
A1C_ORDER = ["Normal (<5.7)", "Prediabetes (5.7-6.4)", "Diabetes (6.5+)"]
BMI_ORDER = ["Below 30", "Class 1 (30-34.9)", "Class 2 (35-39.9)", "Class 3 (40+)"]
SMALL = {"a", "an", "the", "of", "per", "by", "and", "or", "in", "to", "vs", "for", "on", "at", "with", "from"}
COLS = {"AvgPerDay": "Avg per Day", "MoMPct": "MoM %", "ClinicDays": "Clinic Days", "PatientsSeen": "Patients Seen",
        "MeasuredAs": "Measured As"}
_keys = itertools.count()


def T(text):
    """Title-case a label: keep acronyms and numbers, lowercase small words."""
    out = []
    for i, w in enumerate(str(text).split(" ")):
        pre = len(w) - len(w.lstrip("("))
        core = w[pre:]
        if i > 0 and core.lower() in SMALL:
            out.append(w[:pre] + core.lower())
        elif not core[:1].isalpha() or any(c.isupper() for c in core[1:]):
            out.append(w)
        else:
            out.append(w[:pre] + core[:1].upper() + core[1:])
    return " ".join(out)


def ml(s):
    """'2026-03' -> 'Mar 2026'."""
    return list(pd.PeriodIndex(list(s), freq="M").strftime("%b %Y"))


def kpi(col, label, value, delta=None):
    col.metric(T(label), value, delta)


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
    bars = [t for t in fig.data if t.type == "bar"]
    fig.update_layout(
        template="plotly_white", height=height, margin=dict(l=8, r=8, t=50, b=8),
        font=dict(family="Segoe UI, Inter, sans-serif", color=INK, size=12), plot_bgcolor="#fff", paper_bgcolor="#fff",
        legend=dict(orientation="h", y=-0.2, x=0, title=None), hoverlabel=dict(bgcolor="#fff"),
        title=dict(text=T(fig.layout.title.text or ""), x=0, font=dict(size=15, color=NAVY)))
    fig.update_xaxes(showgrid=False, linecolor="#CBD8E6")
    fig.update_yaxes(gridcolor="#EAF0F7", zeroline=False)
    fig.update_traces(selector=dict(type="bar"), marker_cornerradius=6)
    fig.update_traces(selector=dict(type="pie"), marker=dict(line=dict(color="#fff", width=2)))
    if len(bars) == 1:
        fig.update_traces(selector=dict(type="bar"), textposition="outside", cliponaxis=False)
    else:
        fig.update_traces(selector=dict(type="bar"), text=None)
    with st.container(key=f"card{next(_keys)}"):
        st.plotly_chart(fig, width="stretch", key=f"c{next(_keys)}")


def table(df):
    df = df.rename(columns=lambda c: COLS.get(c, T(c)))
    with st.container(key=f"card{next(_keys)}"):
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
    fig.update_xaxes(title=None, range=[0, d[val].max() * 1.18], showticklabels=False)
    show(fig, max(260, 34 * len(d) + 90))


def donut(df, cat, val, title, top=8):
    d = top_other(df, cat, val, top)
    if d.empty:
        return
    fig = px.pie(d, names=cat, values=val, hole=0.6, title=title, color_discrete_sequence=ramp(len(d))[::-1])
    fig.update_traces(textinfo="percent", sort=False)
    show(fig)


def age_bar(df, cat, val, title):
    d = df.groupby(cat, as_index=False)[val].sum()
    d["o"] = d[cat].map({v: i for i, v in enumerate(AGE_ORDER)}).fillna(99)
    d = d.sort_values("o")
    fig = px.bar(d, x=cat, y=val, text=val, title=title, color_discrete_sequence=[BLUE])
    fig.update_xaxes(title=None)
    fig.update_yaxes(title=None, range=[0, d[val].max() * 1.18], showticklabels=False)
    show(fig)


def col_bar(x, y, title, color=BLUE):
    fig = px.bar(x=ml(x), y=list(y), title=title, text=list(y), color_discrete_sequence=[color])
    fig.update_xaxes(title=None, type="category")
    fig.update_yaxes(title=None, range=[0, max(list(y) + [1]) * 1.18], showticklabels=False)
    show(fig)


def stack_month(df, cat, val, title, top=8, pct=False):
    keep = df.groupby(cat)[val].sum().nlargest(top).index
    d = df.assign(**{cat: df[cat].where(df[cat].isin(keep), "Other")}).groupby(["Month", cat], as_index=False)[val].sum()
    d = d.sort_values("Month")
    d["Month"] = ml(d["Month"])
    cats = list(d.groupby(cat)[val].sum().sort_values(ascending=False).index)
    fig = px.bar(d, x="Month", y=val, color=cat, title=title, category_orders={cat: cats},
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
    """Preset buttons (All Time, Last 12 Months, ...) plus a Custom From/To picker."""
    months = sorted(set(months))
    if len(months) < 2:
        return (months[0], months[0]) if months else ("", "")
    last = pd.Period(months[-1])
    presets = {"All Time": None, "Last 12 Months": 12, "Last 6 Months": 6, "Last 3 Months": 3,
               "Year to Date": "ytd", "Custom": "custom"}
    c = st.columns([5, 1.4, 1.4])
    pick = c[0].segmented_control("Time Period", list(presets), default="All Time", key=f"{key}_p",
                                  label_visibility="collapsed") or "All Time"
    lo, hi = months[0], months[-1]
    kind = presets[pick]
    if kind == "custom":
        lo = c[1].selectbox("From", months, 0, format_func=lambda m: ml([m])[0], key=f"{key}_lo")
        hi = c[2].selectbox("To", months, len(months) - 1, format_func=lambda m: ml([m])[0], key=f"{key}_hi")
        lo, hi = min(lo, hi), max(lo, hi)
    elif kind == "ytd":
        lo = max(months[0], f"{last.year}-01")
    elif kind:
        lo = max(months[0], str(last - (kind - 1)))
    st.markdown(f"<div class='period'>Showing {ml([lo])[0]} to {ml([hi])[0]}</div>", unsafe_allow_html=True)
    return lo, hi


# --------------------------------------------------------------------------- #
# EMR
# --------------------------------------------------------------------------- #
def render_emr():
    mon, canc, reasons = rd("emr_monthly"), rd("emr_cancellations_monthly"), rd("emr_cancel_reasons")
    demo, kp, sites = rd("emr_demographics"), rd("emr_kpis").set_index("Metric")["Value"], rd("emr_site_monthly")
    vtm, cond = rd("emr_visit_type_monthly"), rd("emr_conditions")

    lo, hi = month_filter(list(mon["Month"]) + list(canc["Month"]), "emr_months")
    inr = lambda d: d[(d["Month"] >= lo) & (d["Month"] <= hi)]
    st.caption(f"Data through {kp.get('Data through', 'n/a')}. 'Seen' means completed, checked-in or checked-out visits; "
               "pending, cancelled, rescheduled, no-show and phone-contact statuses are excluded. "
               "Demographics and chronic conditions cover all patients, not the selected period.")
    tabs = st.tabs(["Overview", "Cancellations", "Patients", "Visits & Sites", "Chronic Conditions"])

    with tabs[0]:
        m = inr(mon)
        if m.empty:
            st.warning("No visits in this period.")
        else:
            full = mon.set_index("Month")
            cur = full.loc[m["Month"].iloc[-1]]
            i = list(full.index).index(m["Month"].iloc[-1])
            prev = full.iloc[i - 1] if i > 0 else None
            d = lambda c: None if prev is None or pd.isna(prev[c]) else round(float(cur[c] - prev[c]), 2)
            mlab = ml([m["Month"].iloc[-1]])[0]
            k = st.columns(5)
            kpi(k[0], f"Avg Visits per Day ({mlab})", cur["AvgPerDay"], d("AvgPerDay"))
            kpi(k[1], f"Patients Seen ({mlab})", int(cur["PatientsSeen"]), d("PatientsSeen"))
            kpi(k[2], f"Clinic Days ({mlab})", int(cur["ClinicDays"]), d("ClinicDays"))
            kpi(k[3], "Patients on Record", f"{int(kp.get('Patients on record', 0)):,}")
            kpi(k[4], "Seen in Last 12 Months", f"{int(kp.get('Seen in last 12 months', 0)):,}")
            st.caption("'Patients on record' is the number of unique patient IDs in Encounters, used as the enrolled count. "
                       "Deltas compare with the prior month; the latest month may be partial.")
            a, b = st.columns(2)
            with a:
                col_bar(m["Month"], m["AvgPerDay"], "Average Appointments per Clinic Day")
            with b:
                col_bar(m["Month"], m["PatientsSeen"], "Unique Patients Seen per Month", SKY)
            a, b = st.columns(2)
            with a:
                col_bar(m["Month"], m["ClinicDays"], "Days Clinic Was in Service", NAVY)
            with b:
                t = m.iloc[::-1][["Month", "AvgPerDay", "MoMPct", "Visits", "ClinicDays", "PatientsSeen"]].copy()
                t["Month"] = ml(t["Month"])
                st.markdown("**Month-over-Month Change in Average Visits per Day**")
                table(t)

    with tabs[1]:
        c, r = inr(canc), inr(reasons)
        if c.empty:
            st.info("No cancelled or rescheduled visits in this period.")
        else:
            tot, rs = int(c["Cancelled"].sum()), int(c["Rescheduled"].sum())
            k = st.columns(4)
            kpi(k[0], "Cancelled", f"{tot:,}")
            kpi(k[1], "Rescheduled", f"{rs:,}")
            kpi(k[2], "Reschedule Rate", f"{rs / tot:.0%}" if tot else "n/a")
            kpi(k[3], "No-Shows", f"{int(c['NoShow'].sum()):,}")
            long = c.assign(**{"Not Rescheduled": c["Cancelled"] - c["Rescheduled"]}).melt(
                "Month", ["Rescheduled", "Not Rescheduled"], "Outcome", "Count")
            long["Month"] = ml(long["Month"])
            fig = px.bar(long, x="Month", y="Count", color="Outcome", title="Cancellations per Month",
                         color_discrete_map={"Rescheduled": BLUE, "Not Rescheduled": PALE})
            fig.update_xaxes(title=None, type="category")
            fig.update_yaxes(title=None)
            show(fig)
            a, b = st.columns(2)
            with a:
                bar_h(r, "Reason", "Count", "Cancellation Type (Visit Status)")
            with b:
                stack_month(r, "Reason", "Count", "Cancellation Type by Month")
            st.markdown("**Rescheduled vs. Not Rescheduled, by Cancellation Type**")
            table(r.pivot_table(index="Reason", columns="Rescheduled", values="Count", aggfunc="sum", fill_value=0)
                  .rename(columns={True: "Rescheduled", False: "Not Rescheduled"}).reset_index()
                  .rename(columns={"Reason": "Cancellation Type"}))

    with tabs[2]:
        g = lambda dim: demo[demo["Dimension"] == dim]
        k = st.columns(3)
        kpi(k[0], "Patients on Record", f"{int(kp.get('Patients on record', 0)):,}")
        kpi(k[1], "Languages", len(g("Language")))
        kpi(k[2], "Payers", len(g("Payer")))
        a, b, c = st.columns(3)
        with a:
            age_bar(g("Age group"), "Value", "Patients", "Age")
        with b:
            donut(g("Ethnicity"), "Value", "Patients", "Ethnicity")
        with c:
            donut(g("Gender"), "Value", "Patients", "Gender")
        a, b, c = st.columns(3)
        with a:
            bar_h(g("Payer"), "Value", "Patients", "Payer Make-Up", 10)
        with b:
            bar_h(g("Language"), "Value", "Patients", "Language", 10)
        with c:
            bar_h(g("Zip"), "Value", "Patients", "Zip Code", 15)

    with tabs[3]:
        field = st.radio("Break Encounters Down by", sorted(vtm["Field"].unique()), horizontal=True)
        v = inr(vtm[vtm["Field"] == field])
        a, b = st.columns(2)
        with a:
            d = top_other(v, "Value", "Count", 15)
            d["Share"] = (d["Count"] / d["Count"].sum() * 100).round(1)
            fig = px.bar(d, x="Share", y="Value", orientation="h", text=d["Share"].map("{:.1f}%".format),
                         title=f"% of Kept Visits by {field}", color_discrete_sequence=[BLUE])
            fig.update_yaxes(autorange="reversed", title=None)
            fig.update_xaxes(title=None, range=[0, d["Share"].max() * 1.2], showticklabels=False)
            show(fig, max(260, 34 * len(d) + 90))
        with b:
            stack_month(v, "Value", "Count", f"{field} Mix by Month (%)", pct=True)
        table(d.rename(columns={"Value": field, "Share": "Share %"}))
        s = inr(sites)
        a, b = st.columns(2)
        with a:
            stack_month(s, "Site", "Count", "Visits by Site per Month")
        with b:
            pv = s.pivot_table(index="Month", columns="Site", values="Count", aggfunc="sum", fill_value=0)
            pv["Total"] = pv.sum(axis=1)
            pv = pv.iloc[::-1].reset_index()
            pv["Month"] = ml(pv["Month"])
            table(pv)

    with tabs[4]:
        st.caption("Each patient's most recent reading (by encounter date). Only patients with a reading are counted.")
        for name, label, order, positive in [
            ("Hypertension", "Hypertension (Blood Pressure)", BP_ORDER, ["Stage 1", "Stage 2", "Hypertensive Crisis"]),
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
            kpi(kk[0], "Patients with Reading", f"{tot:,}")
            for i, cl in enumerate(order):
                kpi(kk[i + 1], cl, f"{int(j.loc[j['Class'] == cl, 'Patients'].sum()):,}")
            pos = int(j.loc[j["Class"].isin(positive), "Patients"].sum())
            st.markdown(f"**{pos:,} patients ({pos / tot:.0%}) fall in a positive category: {', '.join(positive)}**")
            a, b = st.columns(2)
            with a:
                class_stack(j, "Age Group", order, "By Age Group")
            with b:
                class_stack(j, "Gender", order, "By Gender")


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
        kpi(k[0], "Screenings", f"{int(sm['Count'].sum()):,}")
        kpi(k[1], "Screening Types", sm["Type"].nunique())
        kpi(k[2], "Units Distributed", f"{int(da['Units'].sum()):,}")
        kpi(k[3], "Distribution Events", f"{int(da['Events'].sum()):,}")
        a, b = st.columns(2)
        with a:
            if len(sm):
                stack_month(sm, "Type", "Count", "Screenings per Month")
        with b:
            if len(da):
                stack_month(da, "Item", "Units", "Units Distributed per Month")

    with tabs[1]:
        if sm.empty:
            st.info("No screenings in this period.")
        else:
            k = st.columns(4)
            kpi(k[0], "Total Screenings", f"{int(sm['Count'].sum()):,}")
            for i, (t, n) in enumerate(sm.groupby("Type")["Count"].sum().nlargest(3).items()):
                kpi(k[i + 1], t, f"{int(n):,}")
            a, b = st.columns(2)
            with a:
                bar_h(sm, "Type", "Count", "Screenings by Type", 15)
            with b:
                stack_month(sm, "Type", "Count", "Screenings by Month and Type")
            types = ["All Screening Types"] + sorted(sd["Type"].unique())
            pick = st.selectbox("Screening Type", types)
            d = sd if pick == types[0] else sd[sd["Type"] == pick]
            g = lambda dim: d[d["Dimension"] == dim]
            st.markdown("#### Who We Screened")
            a, b, c = st.columns(3)
            with a:
                age_bar(g("Age group"), "Value", "Count", "Age")
            with b:
                donut(g("Gender"), "Value", "Count", "Gender")
            with c:
                bar_h(g("Race"), "Value", "Count", "Race", 8)
            a, b = st.columns(2)
            with a:
                bar_h(g("Zip"), "Value", "Count", "Zip Code", 15)
            with b:
                bar_h(g("Event type"), "Value", "Count", "Event Type", 10)
            if pick != types[0]:
                st.markdown("#### Results and Follow-Up")
                stt = ss[ss["Type"] == pick]
                if len(stt):
                    kk = st.columns(len(stt))
                    for c, (_, r) in zip(kk, stt.iterrows()):
                        kpi(c, r["Metric"], r["Value"])
                r = sr[sr["Type"] == pick]
                cols = st.columns(2)
                for i, f in enumerate(list(r["Field"].unique())):
                    with cols[i % 2]:
                        bar_h(r[r["Field"] == f], "Value", "Count", f, 10)

    with tabs[2]:
        if da.empty:
            st.info("No distributions in this period.")
        else:
            items = da.groupby("Item").agg(Events=("Events", "sum"), Units=("Units", "sum"),
                                           MeasuredAs=("MeasuredAs", "first")).sort_values("Units", ascending=False)
            k = st.columns(4)
            kpi(k[0], "Total Units", f"{int(items['Units'].sum()):,}")
            kpi(k[1], "Events", f"{int(items['Events'].sum()):,}")
            kpi(k[2], "Item Types", len(items))
            kpi(k[3], "Top Item", items.index[0], f"{int(items['Units'].iloc[0]):,} units")
            a, b = st.columns(2)
            with a:
                fig = px.bar(items.reset_index(), x="Units", y="Item", orientation="h", text="Units",
                             title="Units Distributed by Item", color_discrete_sequence=[BLUE])
                fig.update_yaxes(autorange="reversed", title=None)
                fig.update_xaxes(title=None, range=[0, items["Units"].max() * 1.18], showticklabels=False)
                show(fig, max(300, 32 * len(items) + 90))
            with b:
                stack_month(da, "Item", "Units", "Units per Month by Item")
            table(items.reset_index())
            st.markdown("#### Drill into One Item")
            it = st.selectbox("Item", list(items.index))
            sub = da[da["Item"] == it].groupby("Month", as_index=False)["Units"].sum()
            col_bar(sub["Month"], sub["Units"], f"{it}: Units per Month")
            dd = ds[(ds["Item"] == it) & (ds["Dimension"] != "(all)")]
            if len(dd):
                dim = st.selectbox("Break Down by", sorted(dd["Dimension"].unique()))
                bar_h(dd[dd["Dimension"] == dim], "Value", "Units", f"Units by {dim}", 15)


tab_emr, tab_er = st.tabs(["EMR Data", "ExtendedReach Data"])
with tab_emr:
    render_emr()
with tab_er:
    render_er()
