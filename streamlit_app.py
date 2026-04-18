"""
app.py  —  폐국 관리 시스템 · 메인 현황
실행: streamlit run app.py
"""

import sys
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parent))
from utils.data_loader import (
    load_raw, file_hash, apply_extra, load_extra, MAIN_FILE, RENT_FILE,
)
from utils.calc import (
    calc_savings, monthly_summary, biz_type_summary,
    equipment_summary, voc_summary, ANNUAL_GOAL, CONFIRMED,
)

st.set_page_config(
    page_title="폐국 관리 — 04.중부",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown("""
<style>
.block-container{padding-top:1rem;padding-bottom:1rem}
[data-testid="metric-container"]{background:var(--secondary-background-color);border-radius:8px;padding:.6rem .8rem}
[data-testid="stSidebar"]{min-width:180px;max-width:200px}
thead tr th{background:var(--secondary-background-color)!important;font-size:11px!important}
tbody tr td{font-size:11px!important}
</style>
""", unsafe_allow_html=True)

C = dict(blue="#185FA5", green="#3B6D11", amber="#854F0B",
         red="#A32D2D", purple="#534AB7", teal="#0F6E56", gray="#888780")
BIZ_C = {"단순폐국": C["blue"], "이설후폐국": C["purple"], "최적화후폐국": C["teal"]}
SAV_C = {"임차+전기": C["green"], "전기만": C["amber"], "절감없음": C["gray"]}
GC = "rgba(128,128,128,0.12)"

@st.cache_data(show_spinner="데이터 로딩 중…")
def get_data(fhash):
    df_raw  = load_raw(fhash)
    extra   = load_extra()
    df      = apply_extra(df_raw, extra)
    df_pool = df[
        (df.get("site_err", pd.Series("정상", index=df.index)) == "정상") &
        (df.get("pool_yn",  pd.Series("반영",  index=df.index)) == "반영")
    ].copy()
    return calc_savings(df_pool)

df_pool = get_data(file_hash(MAIN_FILE))
df_conf = df_pool[df_pool["off_month"].isin(CONFIRMED)]

# ── 사이드바 ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📡 폐국 관리 시스템")
    st.markdown("**04.중부 본부**")
    st.divider()

    st.markdown("**페이지**")
    st.page_link("app.py",                        label="📊 메인 현황")
    st.page_link("pages/1_후보_Pool_편집.py",      label="📋 후보 Pool 편집")

    st.divider()
    st.markdown("**Off 월**")
    MONTH_ORDER = ["1월","2월","3월","4월","5월","6월"]
    MON_STATUS  = {m: ("✅" if m in CONFIRMED else ("🔄" if m=="4월" else "⏳")) for m in MONTH_ORDER}
    sel_months  = []
    for m in MONTH_ORDER:
        cnt = len(df_pool[df_pool["off_month"] == m])
        lbl = "{} {}{}".format(MON_STATUS[m], m, "  `{}건`".format(cnt) if cnt else "")
        if st.checkbox(lbl, value=(m in CONFIRMED or m == "4월"), key="m_"+m):
            sel_months.append(m)

    st.divider()
    st.markdown("**데이터 파일**")
    st.markdown(("🟢" if MAIN_FILE.exists() else "🟡") + " 중부_원시데이터.xlsx")
    st.markdown(("🟢" if RENT_FILE.exists() else "🟡") + " 임차_전기DB.xlsx")
    if not MAIN_FILE.exists():
        st.caption("⚠️ 샘플 데이터 사용 중")
    if st.button("🔄 새로고침"):
        st.cache_data.clear()
        st.rerun()

# ── KPI ──────────────────────────────────────────────────────
total_conf = len(df_conf)
rent_conf  = round(df_conf["savings_ann"].sum() * 0.85 / 10000, 1)
elec_conf  = round(df_conf["elec_ann"].sum() / 10000, 1)
pct_conf   = round(total_conf / ANNUAL_GOAL * 100, 1)
voc_df     = voc_summary(df_pool)
voc_issued = int(voc_df["발생"].sum())          if len(voc_df) else 0
voc_open   = int(voc_df["미처리누계"].iloc[-1]) if len(voc_df) else 0
eq_data    = equipment_summary(df_pool)
eq_total   = sum(sum(v.values()) for v in eq_data.values())

c_h1, c_h2 = st.columns([5, 1])
with c_h1:
    st.markdown("## 메인 현황")
with c_h2:
    st.markdown(
        '<div style="text-align:right;padding-top:10px">'
        '<span style="background:#EAF3DE;color:#3B6D11;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:500">1~3월 확정</span>&nbsp;'
        '<span style="background:#FAEEDA;color:#854F0B;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:500">4월 검토중</span>'
        '</div>', unsafe_allow_html=True)

k1,k2,k3,k4,k5 = st.columns(5)
k1.metric("누적 실적 (1~3월)", str(total_conf)+"개소", "목표 {} 대비 {}%".format(ANNUAL_GOAL, pct_conf))
k2.metric("확정 절감 임차료",  str(rent_conf)+"억",    "순절감 기준")
k3.metric("확정 절감 전기료",  str(elec_conf)+"억",    "순절감 기준")
k4.metric("VoC 미처리",       str(voc_open)+"건",     "발생 {}건 중".format(voc_issued))
k5.metric("철거 장비 누계",    str(eq_total)+"대",     "1~3월 합산")

# ── 탭 ───────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 차트 현황", "📋 월별 절감 상세", "🔍 사업유형"])

# ════════ TAB 1: 차트 현황 ══════════════════════════════════
with tab1:
    m_sum = monthly_summary(df_pool)
    valid = m_sum[m_sum["실적"] > 0]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### 목표 대비 실적")
        st.caption("월 단위 실적 + 누계 달성률")
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Bar(x=m_sum["월"], y=m_sum["실적"], name="월 실적",
                              marker_color=C["blue"], marker_line_width=0), secondary_y=False)
        fig1.add_trace(go.Scatter(
            x=valid["월"], y=valid["누계달성률"], name="누계 달성률",
            mode="lines+markers+text",
            line=dict(color=C["green"], width=2.5),
            marker=dict(size=7, color=C["green"], line=dict(color="white", width=1.5)),
            text=[str(v)+"%" for v in valid["누계달성률"]],
            textposition="top center", textfont=dict(size=10, color=C["green"]),
        ), secondary_y=True)
        fig1.add_hline(y=100, line_dash="dash", line_color=C["red"], line_width=1.5,
                       secondary_y=True, annotation_text="목표 100%", annotation_font_size=9)
        fig1.update_layout(height=250, barmode="group",
                           margin=dict(l=0,r=10,t=10,b=0),
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)))
        fig1.update_yaxes(title_text="개소", secondary_y=False, gridcolor=GC, tickfont=dict(size=10))
        fig1.update_yaxes(title_text="달성률(%)", secondary_y=True, range=[0,135], tickfont=dict(size=10))
        fig1.update_xaxes(tickfont=dict(size=10))
        st.plotly_chart(fig1, width="stretch")
        mc1,mc2,mc3 = st.columns(3)
        mc1.metric("누계 실적", str(total_conf)+"건")
        mc2.metric("연간 목표", str(ANNUAL_GOAL)+"건")
        mc3.metric("달성률",    str(pct_conf)+"%")

    with col2:
        st.markdown("##### 절감 실적")
        st.caption("임차·전기 월 단위 + 누계 (억원)")
        conf_m = ["1월","2월","3월"]
        rent_m, elec_m, cumul_m, run = [], [], [], 0.0
        for m in conf_m:
            s = df_pool[df_pool["off_month"] == m]
            r = round(s["savings_ann"].sum() * 0.85 / 10000, 2)
            e = round(s["elec_ann"].sum() / 10000, 2)
            run = round(run + r + e, 2)
            rent_m.append(r); elec_m.append(e); cumul_m.append(run)
        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig2.add_trace(go.Bar(x=conf_m, y=rent_m, name="임차료",
                              marker_color=C["green"], marker_line_width=0), secondary_y=False)
        fig2.add_trace(go.Bar(x=conf_m, y=elec_m, name="전기료",
                              marker_color=C["amber"], marker_line_width=0), secondary_y=False)
        fig2.add_trace(go.Scatter(x=conf_m, y=cumul_m, name="누계",
                                   mode="lines+markers",
                                   line=dict(color=C["blue"], width=2),
                                   marker=dict(size=6, color=C["blue"])), secondary_y=True)
        fig2.update_layout(height=250, barmode="stack",
                           margin=dict(l=0,r=10,t=10,b=0),
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)))
        fig2.update_yaxes(title_text="억원", secondary_y=False, gridcolor=GC, tickfont=dict(size=10))
        fig2.update_yaxes(title_text="누계(억)", secondary_y=True, tickfont=dict(size=10))
        fig2.update_xaxes(tickfont=dict(size=10))
        st.plotly_chart(fig2, width="stretch")
        mc4,mc5,mc6 = st.columns(3)
        mc4.metric("임차 절감", str(rent_conf)+"억")
        mc5.metric("전기 절감", str(elec_conf)+"억")
        mc6.metric("합계", str(round(rent_conf+elec_conf,1))+"억")

    st.divider()
    col3, col4 = st.columns(2)

    with col3:
        st.markdown("##### 철거 장비 수량")
        st.caption("장비 Type별 · 월별")
        eq   = equipment_summary(df_pool)
        eq_m = [m for m in ["1월","2월","3월"] if m in eq]
        ETYPE  = ["RRU","BBU","안테나","기타"]
        ECOLOR = [C["blue"],C["green"],C["amber"],C["purple"]]
        fig3 = go.Figure()
        for t,c in zip(ETYPE, ECOLOR):
            fig3.add_trace(go.Bar(x=eq_m, y=[eq[m][t] for m in eq_m],
                                   name=t, marker_color=c, marker_line_width=0))
        fig3.update_layout(height=250, barmode="stack",
                           margin=dict(l=0,r=0,t=10,b=0),
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)))
        fig3.update_yaxes(title_text="대", gridcolor=GC, tickfont=dict(size=10))
        fig3.update_xaxes(tickfont=dict(size=10))
        st.plotly_chart(fig3, width="stretch")
        eq_totals = [sum(eq[m].values()) for m in eq_m]
        cols_e = st.columns(len(eq_m)+1)
        for ce,m,tot in zip(cols_e, eq_m, eq_totals):
            ce.metric(m, str(tot)+"대")
        cols_e[-1].metric("누계", str(sum(eq_totals))+"대")

    with col4:
        st.markdown("##### VoC 현황")
        st.caption("월별 발생·처리·미처리 누계")
        if voc_df.empty:
            st.info("VoC 데이터가 없습니다.")
        else:
            fig4 = make_subplots(specs=[[{"secondary_y": True}]])
            fig4.add_trace(go.Bar(x=voc_df["월"], y=voc_df["발생"],
                                   name="발생", marker_color=C["red"], marker_line_width=0),
                           secondary_y=False)
            fig4.add_trace(go.Bar(x=voc_df["월"], y=voc_df["처리완료"],
                                   name="처리완료", marker_color=C["green"], marker_line_width=0),
                           secondary_y=False)
            fig4.add_trace(go.Scatter(x=voc_df["월"], y=voc_df["미처리누계"],
                                       name="미처리 누계",
                                       mode="lines+markers",
                                       line=dict(color=C["amber"], width=2),
                                       marker=dict(size=6, color=C["amber"])),
                           secondary_y=True)
            fig4.update_layout(height=250, barmode="group",
                               margin=dict(l=0,r=10,t=10,b=0),
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                               legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)))
            fig4.update_yaxes(title_text="건", secondary_y=False,
                               gridcolor=GC, tickfont=dict(size=10), dtick=1)
            fig4.update_yaxes(title_text="미처리 누계", secondary_y=True,
                               tickfont=dict(size=10), dtick=1)
            fig4.update_xaxes(tickfont=dict(size=10))
            st.plotly_chart(fig4, width="stretch")
            cv1,cv2,cv3 = st.columns(3)
            cv1.metric("발생",    str(voc_issued)+"건")
            cv2.metric("처리완료", str(int(voc_df["처리완료"].sum()))+"건")
            cv3.metric("미처리",  str(voc_open)+"건")

# ════════ TAB 2: 월별 절감 상세 ═════════════════════════════
with tab2:
    st.markdown("##### 월별 절감 실적 상세")
    st.caption("투자비 차감 후 순절감 기준 · 1~3월 확정")

    m_sum = monthly_summary(df_pool)
    STATUS_STYLE = {"확정":("#EAF3DE","#3B6D11"), "검토중":("#FAEEDA","#854F0B"), "예정":("#F1EFE8","#5F5E5A")}

    def _badge(text, bg, fg):
        return '<span style="background:{};color:{};border-radius:4px;padding:1px 6px;font-size:10px;font-weight:500">{}</span>'.format(bg, fg, text)

    def _fmt(v, suffix="", color=None):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return '<span style="color:#888">—</span>'
        s = str(v) + suffix
        if color:
            return '<span style="color:{};font-weight:500">{}</span>'.format(color, s)
        return s

    rows_html = []
    for _, row in m_sum.iterrows():
        mon    = row["월"];    actual = int(row["실적"]) if row["실적"] else 0
        cumul  = row["누계"]; pct    = row["누계달성률"]
        c_ije  = int(row["임차+전기"]); c_elec = int(row["전기만"]); c_none = int(row["절감없음"])
        r_rent = row["임차료절감"]; r_elec = row["전기료절감"]
        r_inv  = row["투자비"];     r_net  = row["순절감"]; status = row["상태"]
        if pct is not None and not pd.isna(pct):
            pc = C["green"] if pct>=100 else (C["amber"] if pct>=50 else C["red"])
            pct_html = '<span style="color:{};font-weight:500">{}%</span>'.format(pc, pct)
        else:
            pct_html = '<span style="color:#888">—</span>'
        cumul_html = _fmt(cumul,"건") if (cumul and not pd.isna(cumul)) else '<span style="color:#888">—</span>'
        sbg,sfg = STATUS_STYLE.get(status, ("#F1EFE8","#5F5E5A"))
        rows_html.append("".join([
            "<tr>",
            "<td><b>{}</b></td>".format(mon),
            '<td style="text-align:right">{}</td>'.format(_fmt(actual if actual else None,"건",C["green"])),
            '<td style="text-align:right">{}</td>'.format(cumul_html),
            '<td style="text-align:right">{}</td>'.format(pct_html),
            '<td style="text-align:right">{}</td>'.format(_badge(c_ije,"#EAF3DE","#3B6D11")),
            '<td style="text-align:right">{}</td>'.format(_badge(c_elec,"#FAEEDA","#854F0B")),
            '<td style="text-align:right">{}</td>'.format(_badge(c_none,"#F1EFE8","#5F5E5A")),
            '<td style="text-align:right">{}</td>'.format(_fmt(r_rent if r_rent else None,"억",C["green"])),
            '<td style="text-align:right">{}</td>'.format(_fmt(r_elec if r_elec else None,"억",C["amber"])),
            '<td style="text-align:right">{}</td>'.format(_fmt(r_inv  if r_inv  else None,"억",C["red"])),
            '<td style="text-align:right">{}</td>'.format(_fmt(r_net  if r_net  else None,"억",C["green"])),
            "<td>{}</td>".format(_badge(status,sbg,sfg)),
            "</tr>",
        ]))

    HEADERS = ["월","실적","누계","누계달성률","임차+전기","전기만","절감없음","임차료절감","전기료절감","투자비","순절감","상태"]
    th = "padding:5px;border-bottom:1px solid #ddd;"
    st.markdown(
        '<table style="width:100%;border-collapse:collapse;font-size:11px">'
        '<thead><tr style="background:var(--secondary-background-color)">'
        + "".join('<th style="{}{}">{}</th>'.format(th,"text-align:left" if i==0 else "text-align:right",h) for i,h in enumerate(HEADERS))
        + "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table>",
        unsafe_allow_html=True,
    )

    st.divider()
    td1, td2 = st.columns(2)

    with td1:
        st.markdown("##### 누계 달성률 추이")
        valid2 = m_sum[m_sum["누계달성률"].notna()]
        fig_p  = go.Figure()
        fig_p.add_trace(go.Scatter(
            x=valid2["월"], y=valid2["누계달성률"],
            mode="lines+markers+text",
            line=dict(color=C["blue"], width=2.5),
            marker=dict(size=8, color=C["blue"], line=dict(color="white", width=2)),
            fill="tozeroy", fillcolor="rgba(24,95,165,0.08)",
            text=[str(v)+"%" for v in valid2["누계달성률"]],
            textposition="top center", textfont=dict(size=11),
        ))
        fig_p.add_hline(y=100, line_dash="dash", line_color=C["red"],
                        annotation_text="목표 100%", annotation_font_size=10)
        fig_p.update_layout(height=200, margin=dict(l=0,r=0,t=10,b=0),
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            showlegend=False,
                            yaxis=dict(range=[0,120], ticksuffix="%", gridcolor=GC, tickfont=dict(size=10)),
                            xaxis=dict(tickfont=dict(size=10)))
        st.plotly_chart(fig_p, width="stretch")

    with td2:
        st.markdown("##### 절감유형 비율")
        sav_cnt = df_conf["sav_type"].value_counts()
        fig_s   = go.Figure(go.Pie(
            labels=sav_cnt.index.tolist(), values=sav_cnt.values.tolist(),
            marker=dict(colors=[SAV_C.get(l, C["gray"]) for l in sav_cnt.index]),
            hole=0.65, textinfo="none",
        ))
        fig_s.update_layout(height=200, margin=dict(l=0,r=0,t=10,b=0),
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            legend=dict(font=dict(size=10), orientation="v", x=0.72, y=0.5))
        st.plotly_chart(fig_s, width="stretch")

# ════════ TAB 3: 사업유형 ═══════════════════════════════════
with tab3:
    bs = biz_type_summary(df_conf)
    ta1, ta2 = st.columns([3,2])

    with ta1:
        st.markdown("##### 사업유형 × 절감유형")
        fig_a1 = go.Figure()
        for sav,color in SAV_C.items():
            fig_a1.add_trace(go.Bar(name=sav, x=bs["사업유형"], y=bs[sav],
                                    marker_color=color, marker_line_width=0))
        fig_a1.update_layout(height=240, barmode="stack",
                             margin=dict(l=0,r=0,t=10,b=0),
                             plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                             legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)))
        fig_a1.update_yaxes(title_text="건수", gridcolor=GC, tickfont=dict(size=10))
        fig_a1.update_xaxes(tickfont=dict(size=11))
        st.plotly_chart(fig_a1, width="stretch")

    with ta2:
        st.markdown("##### 임차료 절감 (억원)")
        fig_a2 = go.Figure(go.Bar(
            x=bs["임차료절감"], y=bs["사업유형"], orientation="h",
            marker_color=[BIZ_C.get(b,C["gray"]) for b in bs["사업유형"]],
            marker_line_width=0,
            text=[str(v)+"억" for v in bs["임차료절감"]], textposition="outside",
        ))
        fig_a2.update_layout(height=240, margin=dict(l=0,r=45,t=10,b=0),
                             plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                             showlegend=False)
        fig_a2.update_xaxes(title_text="억원", tickfont=dict(size=10), gridcolor=GC)
        fig_a2.update_yaxes(tickfont=dict(size=11))
        st.plotly_chart(fig_a2, width="stretch")

    st.divider()
    st.markdown("##### 사업유형별 상세")

    def _bep_html(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "—"
        vi = int(v)
        c  = C["green"] if vi<=24 else (C["amber"] if vi<=48 else C["red"])
        return '<span style="color:{};font-weight:500">{}개월</span>'.format(c, vi)

    rows_biz = []
    for _, row in bs.iterrows():
        biz = row["사업유형"]; bc = BIZ_C.get(biz, C["gray"])
        nc  = C["green"] if row["순절감"]>=0 else C["red"]
        rows_biz.append("".join([
            "<tr>",
            '<td><span style="background:{}22;color:{};border-radius:4px;padding:1px 7px;font-size:10px;font-weight:500">{}</span></td>'.format(bc,bc,biz),
            '<td style="text-align:right;font-weight:500">{}</td>'.format(int(row["건수"])),
            '<td style="text-align:right"><span style="background:#EAF3DE;color:#3B6D11;border-radius:3px;padding:0 5px;font-size:10px">{}</span></td>'.format(int(row["임차+전기"])),
            '<td style="text-align:right"><span style="background:#FAEEDA;color:#854F0B;border-radius:3px;padding:0 5px;font-size:10px">{}</span></td>'.format(int(row["전기만"])),
            '<td style="text-align:right"><span style="background:#F1EFE8;color:#5F5E5A;border-radius:3px;padding:0 5px;font-size:10px">{}</span></td>'.format(int(row["절감없음"])),
            '<td style="text-align:right;color:{};font-weight:500">{}억</td>'.format(C["green"],row["임차료절감"]),
            '<td style="text-align:right;color:{}">{}억</td>'.format(C["amber"],row["전기료절감"]),
            '<td style="text-align:right;color:{}">{}</td>'.format(C["red"],"{}억".format(row["투자비"]) if row["투자비"] else "—"),
            '<td style="text-align:right;color:{};font-weight:500">{}억</td>'.format(nc,row["순절감"]),
            '<td style="text-align:right">{}</td>'.format(_bep_html(row["평균BEP"])),
            "</tr>",
        ]))

    BIZ_H = ["사업유형","건수","임차+전기","전기만","절감없음","임차료절감","전기료절감","투자비","순절감","평균BEP"]
    st.markdown(
        '<table style="width:100%;border-collapse:collapse;font-size:11px">'
        '<thead><tr style="background:var(--secondary-background-color)">'
        + "".join('<th style="padding:5px;border-bottom:1px solid #ddd;text-align:{}">{}</th>'.format("left" if i==0 else "right",h) for i,h in enumerate(BIZ_H))
        + "</tr></thead><tbody>" + "".join(rows_biz) + "</tbody></table>",
        unsafe_allow_html=True,
    )

    opt     = df_conf[df_conf["biz_type"]=="최적화후폐국"]
    opt_inv = opt[opt["inv_total"]>0]
    if not opt_inv.empty:
        avg_bep = opt_inv["bep_months"].dropna().mean()
        inv_sum = round(opt_inv["inv_total"].sum()/10000, 2)
        net_sum = round(opt_inv["net_savings"].sum()/10000, 2)
        bep_str = "{}개월".format(int(avg_bep)) if not pd.isna(avg_bep) else "—"
        st.info("📌 **최적화후폐국** 투자비 발생 {}건 / 평균 BEP **{}**  \n순절감 합계: {}억원 (투자비 {}억 차감 후)".format(len(opt_inv), bep_str, net_sum, inv_sum))