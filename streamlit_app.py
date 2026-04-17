"""
app.py  —  폐국 관리 시스템 메인
=============================
실행:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── 경로 설정 ────────────────────────────────────────────────
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils.data_loader import (
    load_main, load_rent_elec, _file_hash,
    MAIN_FILE, RENT_FILE, _make_sample_main,
)
from utils.calc import (
    calc_savings, monthly_summary, biz_type_summary,
    equipment_summary, voc_summary, ANNUAL_GOAL,
)

# ── 페이지 기본 설정 ─────────────────────────────────────────
st.set_page_config(
    page_title="폐국 관리 시스템 — 04.중부",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ─────────────────────────────────────────────────────
st.markdown("""
<style>
    /* 전체 여백 축소 */
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    /* KPI 카드 */
    [data-testid="metric-container"] {
        background: var(--secondary-background-color);
        border-radius: 8px;
        padding: 0.6rem 0.8rem;
    }
    /* 탭 */
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] { padding: 6px 16px; font-size: 13px; }
    /* 테이블 헤더 */
    thead tr th { background: var(--secondary-background-color) !important; font-size: 12px !important; }
    tbody tr td { font-size: 12px !important; }
    /* 사이드바 */
    [data-testid="stSidebar"] { min-width: 200px; max-width: 220px; }
</style>
""", unsafe_allow_html=True)


# ── 색상 팔레트 ──────────────────────────────────────────────
C_BLUE   = "#185FA5"
C_GREEN  = "#3B6D11"
C_AMBER  = "#854F0B"
C_RED    = "#A32D2D"
C_PURPLE = "#534AB7"
C_TEAL   = "#0F6E56"
C_GRAY   = "#888780"

MONTH_ORDER   = ["1월","2월","3월","4월","5월","6월"]
CONFIRMED_MON = {"1월","2월","3월"}
REVIEW_MON    = {"4월"}

SAV_COLORS = {
    "임차+전기": C_GREEN,
    "전기만":   C_AMBER,
    "절감없음": C_GRAY,
}
BIZ_COLORS = {
    "단순폐국":    C_BLUE,
    "이설후폐국":  C_PURPLE,
    "최적화후폐국": C_TEAL,
}


# ── 데이터 로드 ──────────────────────────────────────────────
@st.cache_data(show_spinner="데이터 준비 중…")
def get_data():
    mh = _file_hash(MAIN_FILE)
    rh = _file_hash(RENT_FILE)
    if MAIN_FILE.exists():
        df_raw = load_main(mh)
    else:
        df_raw = _make_sample_main()
    df = calc_savings(df_raw[df_raw["is_pool"]].copy())
    return df, df_raw

df_pool, df_raw = get_data()


# ── 사이드바 ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📡 폐국 관리")
    st.markdown("**04.중부 본부**")
    st.divider()

    st.markdown("**Off 월 필터**")
    sel_months = []
    for m in MONTH_ORDER:
        status = "✅" if m in CONFIRMED_MON else ("🔄" if m in REVIEW_MON else "⏳")
        cnt = len(df_pool[df_pool["off_month"] == m])
        label = f"{status} {m}" + (f"  `{cnt}건`" if cnt > 0 else "")
        if st.checkbox(label, value=(m in CONFIRMED_MON | REVIEW_MON), key=f"mon_{m}"):
            sel_months.append(m)

    st.divider()
    st.markdown("**절감유형 필터**")
    sel_sav = []
    for s, c in SAV_COLORS.items():
        if st.checkbox(s, value=True, key=f"sav_{s}"):
            sel_sav.append(s)

    st.divider()
    st.markdown("**사업유형 필터**")
    sel_biz = []
    for b in BIZ_COLORS:
        if st.checkbox(b, value=True, key=f"biz_{b}"):
            sel_biz.append(b)

    st.divider()
    # 데이터 파일 상태
    st.markdown("**데이터 파일**")
    main_icon = "🟢" if MAIN_FILE.exists() else "🟡"
    rent_icon = "🟢" if RENT_FILE.exists() else "🟡"
    st.markdown(
        main_icon + " 중부_원시데이터.xlsx  \n"
        + rent_icon + " 임차_전기DB.xlsx"
    )
    if not MAIN_FILE.exists():
        st.caption("⚠️ 샘플 데이터로 표시 중")

    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()


# ── 필터 적용 ────────────────────────────────────────────────
mask = (
    df_pool["off_month"].isin(sel_months) &
    df_pool["sav_type"].isin(sel_sav) &
    df_pool["biz_type"].isin(sel_biz)
)
df_filtered = df_pool[mask].copy()
df_all_months = df_pool.copy()  # 월별 누계용 (필터 미적용)


# ── 헤더 ─────────────────────────────────────────────────────
col_h1, col_h2 = st.columns([4, 1])
with col_h1:
    st.markdown("## 메인 현황")
with col_h2:
    st.markdown(
        '<div style="text-align:right;padding-top:8px">'
        '<span style="background:#FAEEDA;color:#854F0B;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:500">04.중부</span> '
        '<span style="background:#EAF3DE;color:#3B6D11;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:500">1~3월 확정</span> '
        '<span style="background:#FAEEDA;color:#854F0B;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:500">4월 검토중</span>'
        '</div>',
        unsafe_allow_html=True,
    )


# ── KPI 카드 ─────────────────────────────────────────────────
df_confirmed = df_all_months[df_all_months["off_month"].isin(CONFIRMED_MON)]
total_conf   = len(df_confirmed)
rent_conf    = round(df_confirmed["savings_ann"].sum() * 0.85 / 10000, 1)
elec_conf    = round(df_confirmed["elec_ann"].sum() / 10000, 1)
inv_conf     = round(df_confirmed["inv_total"].sum() / 10000, 1)
net_conf     = round(df_confirmed["net_savings"].sum() / 10000, 1)
voc_df       = voc_summary(df_all_months)
voc_issued   = int(voc_df["발생"].sum()) if len(voc_df) > 0 else 0
voc_open     = int(voc_df["미처리누계"].iloc[-1]) if len(voc_df) > 0 else 0
eq_data      = equipment_summary(df_all_months)
eq_total     = sum(sum(v.values()) for v in eq_data.values())
pct_conf     = round(total_conf / ANNUAL_GOAL * 100, 1)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("누적 실적 (1~3월)", f"{total_conf}개소", f"목표 {ANNUAL_GOAL} 대비 {pct_conf}%")
k2.metric("확정 절감 임차료", f"{rent_conf}억", "순절감 기준")
k3.metric("확정 절감 전기료", f"{elec_conf}억", "순절감 기준")
k4.metric("VoC 미처리", f"{voc_open}건", f"발생 {voc_issued}건 중")
k5.metric("철거 장비 누계", f"{eq_total}대", "1~3월 합산")


# ── 탭 ───────────────────────────────────────────────────────
tab_chart, tab_detail, tab_analysis = st.tabs(["📊 차트 현황", "📋 세부 data", "🔍 분석 (사업유형)"])


# ════════════════════════════════════════════════════════════
# TAB 1 — 차트 현황
# ════════════════════════════════════════════════════════════
with tab_chart:

    # ── 행 1: 목표실적 / 절감실적 / 사업유형 분포 ─────────
    col1, col2, col3 = st.columns(3)

    # ① 목표 대비 실적
    with col1:
        st.markdown("##### 목표 대비 실적")
        st.caption("월별 실적 + 누계 달성률")

        m_sum = monthly_summary(df_all_months)
        labels = m_sum["월"].tolist()
        actual = m_sum["실적"].tolist()
        cumul_pct = m_sum["누계달성률"].tolist()

        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(
            go.Bar(
                x=labels,
                y=actual,
                name="월 실적",
                marker_color=C_BLUE,
                marker_line_width=0,
            ),
            secondary_y=False,
        )
        fig1.add_trace(
            go.Scatter(
                x=[labels[i] for i, v in enumerate(cumul_pct) if v is not None],
                y=[v for v in cumul_pct if v is not None],
                name="누계 달성률",
                mode="lines+markers+text",
                line=dict(color=C_GREEN, width=2.5),
                marker=dict(size=7, color=C_GREEN,
                            line=dict(color="white", width=1.5)),
                text=[f"{v}%" for v in cumul_pct if v is not None],
                textposition="top center",
                textfont=dict(size=10, color=C_GREEN),
            ),
            secondary_y=True,
        )
        fig1.add_hline(
            y=100, line_dash="dash", line_color=C_RED,
            line_width=1.5, secondary_y=True,
            annotation_text="목표 100%",
            annotation_font_size=10,
        )
        fig1.update_layout(
            height=220, margin=dict(l=0, r=10, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                        font=dict(size=10)),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            barmode="group",
        )
        fig1.update_yaxes(title_text="개소", secondary_y=False,
                          gridcolor="rgba(128,128,128,0.15)", tickfont=dict(size=10))
        fig1.update_yaxes(title_text="달성률(%)", secondary_y=True,
                          range=[0, 130], tickfont=dict(size=10))
        fig1.update_xaxes(tickfont=dict(size=10))
        st.plotly_chart(fig1, use_container_width=True)

        # 미니 스탯
        c1a, c1b, c1c = st.columns(3)
        c1a.metric("누계", f"{total_conf}건")
        c1b.metric("목표", f"{ANNUAL_GOAL}건")
        c1c.metric("달성률", f"{pct_conf}%")

    # ② 절감 실적
    with col2:
        st.markdown("##### 절감 실적")
        st.caption("임차·전기 월별 + 누계 (억원)")

        conf_months = ["1월", "2월", "3월"]
        rent_by_m = []
        elec_by_m = []
        cumul_sav = []
        running = 0.0
        for m in conf_months:
            sub = df_all_months[df_all_months["off_month"] == m]
            r = round(sub["savings_ann"].sum() * 0.85 / 10000, 2)
            e = round(sub["elec_ann"].sum() / 10000, 2)
            running = round(running + r + e, 2)
            rent_by_m.append(r)
            elec_by_m.append(e)
            cumul_sav.append(running)

        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig2.add_trace(go.Bar(x=conf_months, y=rent_by_m, name="임차료",
                              marker_color=C_GREEN, marker_line_width=0), secondary_y=False)
        fig2.add_trace(go.Bar(x=conf_months, y=elec_by_m, name="전기료",
                              marker_color=C_AMBER, marker_line_width=0), secondary_y=False)
        fig2.add_trace(go.Scatter(x=conf_months, y=cumul_sav, name="누계",
                                   mode="lines+markers",
                                   line=dict(color=C_BLUE, width=2),
                                   marker=dict(size=6, color=C_BLUE)), secondary_y=True)
        fig2.update_layout(
            height=220, margin=dict(l=0, r=10, t=10, b=0),
            barmode="stack",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        fig2.update_yaxes(title_text="억원", secondary_y=False,
                          gridcolor="rgba(128,128,128,0.15)", tickfont=dict(size=10))
        fig2.update_yaxes(title_text="누계(억)", secondary_y=True, tickfont=dict(size=10))
        fig2.update_xaxes(tickfont=dict(size=10))
        st.plotly_chart(fig2, use_container_width=True)

        c2a, c2b, c2c = st.columns(3)
        c2a.metric("임차", f"{rent_conf}억")
        c2b.metric("전기", f"{elec_conf}억")
        c2c.metric("합계", f"{round(rent_conf+elec_conf,1)}억")

    # ③ 사업유형 분포
    with col3:
        st.markdown("##### 사업유형별 분포")
        st.caption("1~3월 누계 기준")

        biz_sum = biz_type_summary(df_all_months[df_all_months["off_month"].isin(CONFIRMED_MON)])
        labels_biz  = biz_sum["사업유형"].tolist()
        values_biz  = biz_sum["건수"].tolist()
        colors_biz  = [BIZ_COLORS.get(b, C_GRAY) for b in labels_biz]

        fig3 = go.Figure(go.Pie(
            labels=labels_biz,
            values=values_biz,
            marker=dict(colors=colors_biz),
            hole=0.68,
            textinfo="none",
            hovertemplate="%{label}: %{value}건 (%{percent})<extra></extra>",
        ))
        fig3.update_layout(
            height=180, margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(font=dict(size=10), orientation="h",
                        yanchor="bottom", y=-0.3),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            showlegend=True,
        )
        st.plotly_chart(fig3, use_container_width=True)

        for _, row in biz_sum.iterrows():
            pct = round(row["건수"] / total_conf * 100, 0) if total_conf else 0
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:6px;margin:3px 0;font-size:11px">'
                f'<span style="width:9px;height:9px;border-radius:50%;background:{BIZ_COLORS.get(row["사업유형"],C_GRAY)};flex-shrink:0"></span>'
                f'<span style="min-width:88px;color:var(--text-color)">{row["사업유형"]}</span>'
                f'<span style="color:#888;font-size:10px">{row["건수"]}건 ({int(pct)}%)</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # ── 행 2: 철거 장비 / VoC ──────────────────────────────
    col4, col5 = st.columns(2)

    # ④ 철거 장비 수량
    with col4:
        st.markdown("##### 철거 장비 수량")
        st.caption("장비 Type별 / 월별")

        eq = equipment_summary(df_all_months)
        eq_months = [m for m in ["1월","2월","3월"] if m in eq]
        eq_types  = ["RRU", "BBU", "안테나", "기타"]
        eq_colors = [C_BLUE, C_GREEN, C_AMBER, C_PURPLE]

        fig4 = go.Figure()
        for t, c in zip(eq_types, eq_colors):
            fig4.add_trace(go.Bar(
                x=eq_months,
                y=[eq[m][t] for m in eq_months],
                name=t,
                marker_color=c,
                marker_line_width=0,
            ))
        fig4.update_layout(
            height=220, barmode="stack",
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        fig4.update_yaxes(title_text="대", gridcolor="rgba(128,128,128,0.15)",
                          tickfont=dict(size=10))
        fig4.update_xaxes(tickfont=dict(size=10))
        st.plotly_chart(fig4, use_container_width=True)

        eq_totals = [sum(eq[m].values()) for m in eq_months]
        c4a, c4b, c4c, c4d = st.columns(4)
        for col_e, m, tot in zip([c4a, c4b, c4c], eq_months, eq_totals):
            col_e.metric(m, f"{tot}대")
        c4d.metric("누계", f"{sum(eq_totals)}대")

    # ⑤ VoC 현황
    with col5:
        st.markdown("##### VoC 현황")
        st.caption("월별 발생·처리·미처리 누계")

        voc_df2 = voc_summary(df_all_months)
        if voc_df2.empty:
            st.info("VoC 데이터가 없습니다.")
        else:
            fig5 = make_subplots(specs=[[{"secondary_y": True}]])
            fig5.add_trace(go.Bar(x=voc_df2["월"], y=voc_df2["발생"],
                                   name="발생", marker_color=C_RED, marker_line_width=0),
                           secondary_y=False)
            fig5.add_trace(go.Bar(x=voc_df2["월"], y=voc_df2["처리완료"],
                                   name="처리완료", marker_color=C_GREEN, marker_line_width=0),
                           secondary_y=False)
            fig5.add_trace(go.Scatter(x=voc_df2["월"], y=voc_df2["미처리누계"],
                                       name="미처리 누계", mode="lines+markers",
                                       line=dict(color=C_AMBER, width=2),
                                       marker=dict(size=6, color=C_AMBER)),
                           secondary_y=True)
            fig5.update_layout(
                height=220, barmode="group",
                margin=dict(l=0, r=10, t=10, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            fig5.update_yaxes(title_text="건", secondary_y=False,
                               gridcolor="rgba(128,128,128,0.15)",
                               tickfont=dict(size=10), dtick=1)
            fig5.update_yaxes(title_text="미처리 누계", secondary_y=True,
                               tickfont=dict(size=10), dtick=1)
            fig5.update_xaxes(tickfont=dict(size=10))
            st.plotly_chart(fig5, use_container_width=True)

            c5a, c5b, c5c = st.columns(3)
            c5a.metric("발생",    f"{voc_df2['발생'].sum()}건")
            c5b.metric("처리완료", f"{voc_df2['처리완료'].sum()}건")
            c5c.metric("미처리",  f"{int(voc_df2['미처리누계'].iloc[-1])}건")


# ════════════════════════════════════════════════════════════
# TAB 2 — 세부 data
# ════════════════════════════════════════════════════════════
with tab_detail:
    st.markdown("##### 월별 절감 실적 상세")
    st.caption("투자비 차감 후 순절감 기준 · 1~3월 확정")

    m_sum = monthly_summary(df_all_months)

    # 상태별 색 표시
    def _status_badge(s):
        colors = {"확정": ("#EAF3DE","#3B6D11"),
                  "검토중": ("#FAEEDA","#854F0B"),
                  "예정": ("#F1EFE8","#5F5E5A")}
        bg, fg = colors.get(s, ("#F1EFE8","#5F5E5A"))
        return f'<span style="background:{bg};color:{fg};border-radius:4px;padding:1px 7px;font-size:10px;font-weight:500">{s}</span>'

    def fmt(v, suffix="", color=None):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return '<span style="color:#888">—</span>'
        s = str(v) + suffix
        if color:
            return '<span style="color:{};font-weight:500">{}</span>'.format(color, s)
        return s

    def badge_sav(val, bg, fg):
        return '<span style="background:{};color:{};border-radius:3px;padding:0 5px;font-size:10px">{}</span>'.format(bg, fg, val)

    rows_html = []
    for _, row in m_sum.iterrows():
        mon         = row["월"]
        actual      = row["실적"]
        cumul       = row["누계"]
        pct_val     = row["누계달성률"]
        c_ije       = int(row["임차+전기"])
        c_elec      = int(row["전기만"])
        c_none      = int(row["절감없음"])
        r_rent      = row["임차료절감"]
        r_elec      = row["전기료절감"]
        r_inv       = row["투자비"]
        r_net       = row["순절감"]
        status      = row["상태"]

        # 누계 달성률 색
        if pct_val is not None and not pd.isna(pct_val):
            pct_color = C_GREEN if pct_val >= 100 else (C_AMBER if pct_val >= 50 else C_RED)
            pct_disp  = '<span style="color:{};font-weight:500">{}%</span>'.format(pct_color, pct_val)
        else:
            pct_disp = '<span style="color:#888">—</span>'

        # 누계
        cumul_disp = fmt(cumul, "건") if (cumul and not pd.isna(cumul)) else '<span style="color:#888">—</span>'

        parts = [
            "<tr>",
            "<td><b>{}</b></td>".format(mon),
            '<td style="text-align:right">{}</td>'.format(fmt(actual if actual else None, "건", C_GREEN)),
            '<td style="text-align:right">{}</td>'.format(cumul_disp),
            '<td style="text-align:right">{}</td>'.format(pct_disp),
            '<td style="text-align:right">{}</td>'.format(badge_sav(c_ije, "#EAF3DE", "#3B6D11")),
            '<td style="text-align:right">{}</td>'.format(badge_sav(c_elec, "#FAEEDA", "#854F0B")),
            '<td style="text-align:right">{}</td>'.format(badge_sav(c_none, "#F1EFE8", "#5F5E5A")),
            '<td style="text-align:right">{}</td>'.format(fmt(r_rent if r_rent else None, "억", C_GREEN)),
            '<td style="text-align:right">{}</td>'.format(fmt(r_elec if r_elec else None, "억", C_AMBER)),
            '<td style="text-align:right">{}</td>'.format(fmt(r_inv  if r_inv  else None, "억", C_RED)),
            '<td style="text-align:right">{}</td>'.format(fmt(r_net  if r_net  else None, "억", C_GREEN)),
            "<td>{}</td>".format(_status_badge(status)),
            "</tr>",
        ]
        rows_html.append("".join(parts))

    table_html = f"""
    <table style="width:100%;border-collapse:collapse;font-size:11px">
    <thead><tr style="background:var(--secondary-background-color)">
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:left">월</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">실적</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">누계</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">누계달성률</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">임차+전기</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">전기만</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">절감없음</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">임차료절감</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">전기료절감</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">투자비</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">순절감</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:left">상태</th>
    </tr></thead>
    <tbody>{''.join(rows_html)}</tbody>
    </table>
    """
    st.markdown(table_html, unsafe_allow_html=True)

    st.divider()
    col_d1, col_d2 = st.columns(2)

    # 누계 달성률 추이
    with col_d1:
        st.markdown("##### 누계 달성률 추이")
        valid = m_sum[m_sum["누계달성률"].notna()]
        fig_pct = go.Figure()
        fig_pct.add_trace(go.Scatter(
            x=valid["월"], y=valid["누계달성률"],
            mode="lines+markers+text",
            line=dict(color=C_BLUE, width=2.5),
            marker=dict(size=8, color=C_BLUE,
                        line=dict(color="white", width=2)),
            fill="tozeroy",
            fillcolor="rgba(24,95,165,0.08)",
            text=[f"{v}%" for v in valid["누계달성률"]],
            textposition="top center",
            textfont=dict(size=11),
        ))
        fig_pct.add_hline(y=100, line_dash="dash", line_color=C_RED,
                          annotation_text="목표 100%", annotation_font_size=10)
        fig_pct.update_layout(
            height=200, margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(range=[0,120], ticksuffix="%",
                       gridcolor="rgba(128,128,128,0.15)",
                       tickfont=dict(size=10)),
            xaxis=dict(tickfont=dict(size=10)),
            showlegend=False,
        )
        st.plotly_chart(fig_pct, use_container_width=True)

    # 절감유형 비율
    with col_d2:
        st.markdown("##### 절감유형 비율")
        df_c = df_all_months[df_all_months["off_month"].isin(CONFIRMED_MON)]
        sav_cnt = df_c["sav_type"].value_counts()
        fig_sav = go.Figure(go.Pie(
            labels=sav_cnt.index.tolist(),
            values=sav_cnt.values.tolist(),
            marker=dict(colors=[SAV_COLORS.get(l, C_GRAY) for l in sav_cnt.index]),
            hole=0.65,
            textinfo="none",
        ))
        fig_sav.update_layout(
            height=200, margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(font=dict(size=11), orientation="v",
                        x=0.75, y=0.5),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_sav, use_container_width=True)


# ════════════════════════════════════════════════════════════
# TAB 3 — 분석 (사업유형)
# ════════════════════════════════════════════════════════════
with tab_analysis:
    df_c = df_all_months[df_all_months["off_month"].isin(CONFIRMED_MON)]
    biz_sum = biz_type_summary(df_c)

    col_a1, col_a2 = st.columns([3, 2])

    # 사업유형 × 절감유형 누적 막대
    with col_a1:
        st.markdown("##### 사업유형 × 절감유형")
        st.caption("건수 누적 막대")
        fig_a1 = go.Figure()
        for sav, color in SAV_COLORS.items():
            fig_a1.add_trace(go.Bar(
                name=sav,
                x=biz_sum["사업유형"],
                y=biz_sum[sav],
                marker_color=color,
                marker_line_width=0,
            ))
        fig_a1.update_layout(
            height=220, barmode="stack",
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        fig_a1.update_yaxes(title_text="건수",
                             gridcolor="rgba(128,128,128,0.15)",
                             tickfont=dict(size=10))
        fig_a1.update_xaxes(tickfont=dict(size=11))
        st.plotly_chart(fig_a1, use_container_width=True)

    # 사업유형별 임차료 절감 수평 막대
    with col_a2:
        st.markdown("##### 사업유형별 임차료 절감")
        st.caption("억원 기준")
        fig_a2 = go.Figure(go.Bar(
            x=biz_sum["임차료절감"],
            y=biz_sum["사업유형"],
            orientation="h",
            marker_color=[BIZ_COLORS.get(b, C_GRAY) for b in biz_sum["사업유형"]],
            marker_line_width=0,
            text=[f"{v}억" for v in biz_sum["임차료절감"]],
            textposition="outside",
        ))
        fig_a2.update_layout(
            height=220, margin=dict(l=0, r=40, t=10, b=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
        )
        fig_a2.update_xaxes(title_text="억원", tickfont=dict(size=10),
                             gridcolor="rgba(128,128,128,0.15)")
        fig_a2.update_yaxes(tickfont=dict(size=11))
        st.plotly_chart(fig_a2, use_container_width=True)

    st.divider()
    st.markdown("##### 사업유형별 상세 현황")

    def _bep_str(v):
        if pd.isna(v) or v == 0:
            return "—"
        v = int(v)
        color = C_GREEN if v <= 24 else (C_AMBER if v <= 48 else C_RED)
        return f'<span style="color:{color};font-weight:500">{v}개월</span>'

    rows_biz = []
    for _, row in biz_sum.iterrows():
        biz       = row["사업유형"]
        biz_color = BIZ_COLORS.get(biz, C_GRAY)
        cnt       = int(row["건수"])
        c_ije     = int(row["임차+전기"])
        c_elec    = int(row["전기만"])
        c_none    = int(row["절감없음"])
        r_rent    = row["임차료절감"]
        r_elec    = row["전기료절감"]
        r_inv     = row["투자비"]
        r_net     = row["순절감"]
        bep_v     = row["평균BEP"]
        net_color = C_GREEN if r_net >= 0 else C_RED

        parts = [
            "<tr>",
            '<td><span style="background:{0}22;color:{0};border-radius:4px;padding:1px 7px;font-size:10px;font-weight:500">{1}</span></td>'.format(biz_color, biz),
            '<td style="text-align:right;font-weight:500">{}</td>'.format(cnt),
            '<td style="text-align:right"><span style="background:#EAF3DE;color:#3B6D11;border-radius:3px;padding:0 5px;font-size:10px">{}</span></td>'.format(c_ije),
            '<td style="text-align:right"><span style="background:#FAEEDA;color:#854F0B;border-radius:3px;padding:0 5px;font-size:10px">{}</span></td>'.format(c_elec),
            '<td style="text-align:right"><span style="background:#F1EFE8;color:#5F5E5A;border-radius:3px;padding:0 5px;font-size:10px">{}</span></td>'.format(c_none),
            '<td style="text-align:right;color:{};font-weight:500">{}억</td>'.format(C_GREEN, r_rent),
            '<td style="text-align:right;color:{}">{}억</td>'.format(C_AMBER, r_elec),
            '<td style="text-align:right;color:{}">{}억</td>'.format(C_RED, r_inv if r_inv else "—"),
            '<td style="text-align:right;color:{};font-weight:500">{}억</td>'.format(net_color, r_net),
            '<td style="text-align:right">{}</td>'.format(_bep_str(bep_v)),
            "</tr>",
        ]
        rows_biz.append("".join(parts))

    biz_html = f"""
    <table style="width:100%;border-collapse:collapse;font-size:11px">
    <thead><tr style="background:var(--secondary-background-color)">
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:left">사업유형</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">건수</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">임차+전기</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">전기만</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">절감없음</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">임차료절감</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">전기료절감</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">투자비</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">순절감</th>
        <th style="padding:5px;border-bottom:1px solid #ddd;text-align:right">평균 BEP</th>
    </tr></thead>
    <tbody>{''.join(rows_biz)}</tbody>
    </table>
    """
    st.markdown(biz_html, unsafe_allow_html=True)

    # 최적화후폐국 BEP 인사이트
    opt_df = df_c[df_c["biz_type"] == "최적화후폐국"]
    opt_with_inv = opt_df[opt_df["inv_total"] > 0]
    if not opt_with_inv.empty:
        st.divider()
        avg_bep = opt_with_inv["bep_months"].dropna().mean()
        inv_sum = round(opt_with_inv["inv_total"].sum() / 10000, 2)
        net_sum = round(opt_with_inv["net_savings"].sum() / 10000, 2)
        bep_str = f"{avg_bep:.0f}개월"
        msg = (
            f"📌 **최적화후폐국** — 투자비 발생 {len(opt_with_inv)}건 / 평균 BEP **{bep_str}**  \n"
            f"순절감 합계: {net_sum}억원 (투자비 {inv_sum}억 차감 후)"
        )
        st.info(msg)