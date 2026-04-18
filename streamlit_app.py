"""
app.py  —  폐국 관리 시스템 · 메인 현황
실행: streamlit run app.py
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parent))
from utils.data_loader import (
    MAIN_FILE,
    RENT_FILE,
    apply_extra,
    file_hash,
    load_extra,
    load_raw,
)
from utils.calc import (
    ANNUAL_GOAL,
    CONFIRMED,
    biz_type_summary,
    calc_savings,
    equipment_summary,
    monthly_summary,
    voc_summary,
)

# ── 기본 설정 ───────────────────────────────────────────────
st.set_page_config(
    page_title="폐국 관리 — 04.중부",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 스타일 ─────────────────────────────────────────────────
st.markdown(
    """
<style>
.block-container{
    padding-top:0.65rem;
    padding-bottom:1rem;
}
[data-testid="stSidebar"]{
    min-width:190px;
    max-width:210px;
}
thead tr th{
    background:var(--secondary-background-color)!important;
    font-size:11px!important;
}
tbody tr td{
    font-size:11px!important;
}

/* KPI 카드 */
.kpi-card{
    background:var(--background-color);
    border:1px solid rgba(128,128,128,0.18);
    border-radius:12px;
    padding:13px 15px 11px 15px;
    height:100%;
    box-shadow:0 1px 2px rgba(0,0,0,0.03);
}
.kpi-label{
    font-size:11px;
    color:var(--text-color);
    opacity:.62;
    margin-bottom:4px;
}
.kpi-value{
    font-size:27px;
    font-weight:700;
    line-height:1.1;
    margin-bottom:2px;
}
.kpi-sub{
    font-size:10px;
    opacity:.58;
    margin-bottom:8px;
}
.kpi-bar{
    height:4px;
    border-radius:99px;
    background:rgba(128,128,128,0.12);
    overflow:hidden;
}
.kpi-bar-fill{
    height:4px;
    border-radius:99px;
}

/* 카드 공통 */
.chart-card{
    background:var(--background-color);
    border:1px solid rgba(128,128,128,0.18);
    border-radius:12px;
    padding:14px 16px 10px 16px;
    margin-bottom:12px;
    box-shadow:0 1px 2px rgba(0,0,0,0.03);
}
.chart-title{
    font-size:12px;
    font-weight:700;
    color:var(--text-color);
    margin-bottom:1px;
}
.chart-sub{
    font-size:10px;
    opacity:.52;
    margin-bottom:8px;
}

/* 범례 칩 */
.leg-row{
    display:flex;
    gap:10px;
    flex-wrap:wrap;
    align-items:center;
    margin-bottom:8px;
}
.leg-item{
    display:flex;
    align-items:center;
    gap:4px;
    font-size:10px;
    opacity:.74;
}
.leg-dot{
    width:8px;
    height:8px;
    border-radius:50%;
    flex-shrink:0;
}
.leg-line{
    width:14px;
    height:2px;
    flex-shrink:0;
}
.leg-dash{
    width:14px;
    height:0;
    border-top:2px dashed;
    flex-shrink:0;
}

/* 미니 스탯 칩 */
.stat-row{
    display:flex;
    gap:6px;
    flex-wrap:wrap;
    margin-bottom:8px;
}
.stat-chip{
    font-size:10px;
    padding:3px 9px;
    border-radius:20px;
    background:var(--secondary-background-color);
    border:1px solid rgba(128,128,128,0.16);
    color:var(--text-color);
}
.stat-chip b{
    font-weight:700;
}

/* 상단 배지 */
.head-badge{
    border-radius:999px;
    padding:3px 9px;
    font-size:11px;
    font-weight:600;
    display:inline-flex;
    align-items:center;
    gap:4px;
}
</style>
""",
    unsafe_allow_html=True,
)

# ── 색상 토큰 ───────────────────────────────────────────────
C = dict(
    blue="#185FA5",
    green="#3B6D11",
    amber="#854F0B",
    red="#A32D2D",
    purple="#534AB7",
    teal="#0F6E56",
    gray="#888780",
)
BIZ_C = {
    "단순폐국": C["blue"],
    "이설후폐국": C["purple"],
    "최적화후폐국": C["teal"],
}
SAV_C = {
    "임차+전기": C["green"],
    "전기만": C["amber"],
    "절감없음": C["gray"],
}
GC = "rgba(128,128,128,0.10)"


# ── 공통 함수 ───────────────────────────────────────────────
@st.cache_data(show_spinner="데이터 로딩 중…")
def get_data(fhash: str) -> pd.DataFrame:
    df_raw = load_raw(fhash)
    extra = load_extra()
    df = apply_extra(df_raw, extra)
    df_pool = df[
        (df.get("site_err", pd.Series("정상", index=df.index)) == "정상")
        & (df.get("pool_yn", pd.Series("반영", index=df.index)) == "반영")
    ].copy()
    return calc_savings(df_pool)


def apply_chart_theme(fig, height=240, showlegend=False):
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=8, t=4, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=showlegend,
        font=dict(size=11),
    )
    return fig


def kpi_html(label: str, value: str, sub: str, bar_pct: float, bar_color: str) -> str:
    fill = max(0, min(bar_pct, 100))
    return (
        '<div class="kpi-card">'
        '<div class="kpi-label">{}</div>'
        '<div class="kpi-value" style="color:{}">{}</div>'
        '<div class="kpi-sub">{}</div>'
        '<div class="kpi-bar"><div class="kpi-bar-fill" style="width:{}%;background:{}"></div></div>'
        "</div>"
    ).format(label, bar_color, value, sub, fill, bar_color)


def chart_card_start(title: str, sub: str, legend_html: str, stat_html: str):
    st.markdown(
        '<div class="chart-card">'
        '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px">'
        '<div><div class="chart-title">{}</div><div class="chart-sub">{}</div></div>'
        '<div class="leg-row">{}</div></div>'
        '<div class="stat-row">{}</div>'.format(title, sub, legend_html, stat_html),
        unsafe_allow_html=True,
    )


def chart_card_end():
    st.markdown("</div>", unsafe_allow_html=True)


def leg(color: str, label: str, style: str = "dot") -> str:
    if style == "line":
        shape = '<span class="leg-line" style="background:{}"></span>'.format(color)
    elif style == "dash":
        shape = '<span class="leg-dash" style="border-color:{}"></span>'.format(color)
    else:
        shape = '<span class="leg-dot" style="background:{}"></span>'.format(color)
    return '<span class="leg-item">{}{}</span>'.format(shape, label)


def chip(label: str, value: str, color: str | None = None) -> str:
    val_str = (
        '<b style="color:{}">{}</b>'.format(color, value)
        if color
        else "<b>{}</b>".format(value)
    )
    return '<span class="stat-chip">{} {}</span>'.format(label, val_str)


def badge(text: str, bg: str, fg: str) -> str:
    return (
        '<span class="head-badge" style="background:{};color:{};">{}</span>'.format(bg, fg, text)
    )


# ── 데이터 로드 ──────────────────────────────────────────────
df_pool = get_data(file_hash(MAIN_FILE))

# ── 사이드바 ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📡 폐국 관리 시스템")
    st.markdown("**04.중부 본부**")
    st.divider()

    st.markdown("**페이지**")
    st.markdown(
        '<div style="background:var(--secondary-background-color);border-radius:8px;'
        'padding:6px 10px;margin:2px 0;font-size:12px;font-weight:600">'
        "📊 메인 현황</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="padding:6px 10px;margin:2px 0;font-size:12px">'
        '<a href="/후보_Pool_편집" target="_self" '
        'style="text-decoration:none;color:var(--text-color)">📋 후보 Pool 편집</a></div>',
        unsafe_allow_html=True,
    )

    st.divider()
    st.markdown("**Off 월**")
    MONTH_ORDER = ["1월", "2월", "3월", "4월", "5월", "6월"]
    MON_STATUS = {
        m: ("✅" if m in CONFIRMED else ("🔄" if m == "4월" else "⏳"))
        for m in MONTH_ORDER
    }

    sel_months = []
    for m in MONTH_ORDER:
        cnt = len(df_pool[df_pool["off_month"] == m])
        label = "{} {}{}".format(MON_STATUS[m], m, "  `{}건`".format(cnt) if cnt else "")
        if st.checkbox(label, value=(m in CONFIRMED or m == "4월"), key=f"m_{m}"):
            sel_months.append(m)

    st.divider()
    st.markdown("**데이터 파일**")
    st.markdown(("🟢" if MAIN_FILE.exists() else "🟡") + " 중부_원시데이터.xlsx")
    st.markdown(("🟢" if RENT_FILE.exists() else "🟡") + " 임차_전기DB.xlsx")
    if not MAIN_FILE.exists():
        st.caption("⚠️ 샘플 데이터 사용 중")

    if st.button("🔄 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── 필터 반영 데이터 ─────────────────────────────────────────
df_view = df_pool.copy()
if sel_months:
    df_view = df_view[df_view["off_month"].isin(sel_months)].copy()

df_conf = df_view[df_view["off_month"].isin(CONFIRMED)].copy()

# ── KPI 계산 ─────────────────────────────────────────────────
total_conf = len(df_conf)
rent_conf = round(df_conf["savings_ann"].sum() * 0.85 / 10000, 1)
elec_conf = round(df_conf["elec_ann"].sum() / 10000, 1)
pct_conf = round(total_conf / ANNUAL_GOAL * 100, 1) if ANNUAL_GOAL else 0

voc_df = voc_summary(df_view)
voc_issued = int(voc_df["발생"].sum()) if len(voc_df) else 0
voc_open = int(voc_df["미처리누계"].iloc[-1]) if len(voc_df) else 0

eq_data = equipment_summary(df_view)
eq_total = sum(sum(v.values()) for v in eq_data.values())

# ── 상단 헤더 ───────────────────────────────────────────────
top_l, top_r = st.columns([6, 1.15])

with top_l:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:4px 0 8px 0">'
        '<span style="font-size:18px;font-weight:800">메인 현황</span>'
        '{}{}{}'
        "</div>".format(
            badge("04.중부", "#EEF4FF", C["blue"]),
            badge("1~3월 확정", "#EAF3DE", C["green"]),
            badge("4월 검토중", "#FAEEDA", C["amber"]),
        ),
        unsafe_allow_html=True,
    )

with top_r:
    if st.button("새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── KPI 카드 ─────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)

k1.markdown(
    kpi_html(
        "누적 실적 (1~3월)",
        f"{total_conf}",
        "목표 {} 대비 {}%".format(ANNUAL_GOAL, pct_conf),
        pct_conf,
        C["blue"],
    ),
    unsafe_allow_html=True,
)
k2.markdown(
    kpi_html(
        "임차료 절감(예상)",
        f"{rent_conf}억",
        "확정월 기준 추정",
        65,
        C["green"],
    ),
    unsafe_allow_html=True,
)
k3.markdown(
    kpi_html(
        "전기료 절감(예상)",
        f"{elec_conf}억",
        "확정월 기준 추정",
        40,
        C["green"],
    ),
    unsafe_allow_html=True,
)
k4.markdown(
    kpi_html(
        "VoC 현황",
        f"{voc_open}건",
        "미처리 기준 / 발생 {}건".format(voc_issued),
        (voc_open / voc_issued * 100) if voc_issued else 0,
        C["red"],
    ),
    unsafe_allow_html=True,
)
k5.markdown(
    kpi_html(
        "Off 장비 수량",
        f"{eq_total}대",
        "선택 월 합산",
        55,
        C["teal"],
    ),
    unsafe_allow_html=True,
)

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# ── 탭 ───────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["차트 현황", "월별 절감 상세", "사업유형 상세"])

# ════════ TAB 1 ═══════════════════════════════════════════════
with tab1:
    m_sum = monthly_summary(df_view)
    valid = m_sum[m_sum["실적"] > 0]

    # ── 상단 2열 ─────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        legend = (
            leg(C["blue"], "월 실적")
            + leg(C["green"], "누계 실적", "line")
            + leg(C["red"], "누계 목표", "dash")
        )
        stats = (
            chip("누계", str(total_conf), C["green"])
            + chip("목표", str(ANNUAL_GOAL))
            + chip("달성", f"{pct_conf}%", C["green"])
        )
        chart_card_start("목표 대비 실적", "월별 + 누계", legend, stats)

        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(
            go.Bar(
                x=m_sum["월"],
                y=m_sum["실적"],
                name="월 실적",
                marker_color=C["blue"],
                marker_line_width=0,
            ),
            secondary_y=False,
        )
        fig1.add_trace(
            go.Scatter(
                x=valid["월"],
                y=valid["누계달성률"],
                name="누계 달성률",
                mode="lines+markers+text",
                line=dict(color=C["green"], width=2.5),
                marker=dict(
                    size=7,
                    color=C["green"],
                    line=dict(color="white", width=1.5),
                ),
                text=[f"{v}%" for v in valid["누계달성률"]],
                textposition="top center",
                textfont=dict(size=10, color=C["green"]),
            ),
            secondary_y=True,
        )
        fig1.add_hline(
            y=100,
            line_dash="dash",
            line_color=C["red"],
            line_width=1.5,
            secondary_y=True,
            annotation_text="목표",
            annotation_font_size=9,
        )
        apply_chart_theme(fig1, height=240, showlegend=False)
        fig1.update_yaxes(
            title_text="개소",
            secondary_y=False,
            gridcolor=GC,
            tickfont=dict(size=10),
        )
        fig1.update_yaxes(
            title_text="달성률(%)",
            secondary_y=True,
            range=[0, 135],
            tickfont=dict(size=10),
        )
        fig1.update_xaxes(tickfont=dict(size=10))
        st.plotly_chart(fig1, width="stretch")
        chart_card_end()

    with col2:
        conf_m = [m for m in ["1월", "2월", "3월"] if m in df_view["off_month"].unique().tolist()]
        rent_m, elec_m, cumul_m, run = [], [], [], 0.0
        for m in conf_m:
            s = df_view[df_view["off_month"] == m]
            r = round(s["savings_ann"].sum() * 0.85 / 10000, 2)
            e = round(s["elec_ann"].sum() / 10000, 2)
            run = round(run + r + e, 2)
            rent_m.append(r)
            elec_m.append(e)
            cumul_m.append(run)

        legend2 = (
            leg(C["green"], "임차")
            + leg(C["amber"], "전기만")
            + leg(C["blue"], "누계", "line")
        )
        stats2 = (
            chip("임차", f"{rent_conf}억", C["green"])
            + chip("전기", f"{elec_conf}억", C["amber"])
            + chip("합계", f"{round(rent_conf + elec_conf, 1)}억", C["blue"])
        )
        chart_card_start("절감 실적", "임차·전기 월별 + 누계", legend2, stats2)

        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig2.add_trace(
            go.Bar(
                x=conf_m,
                y=rent_m,
                name="임차료",
                marker_color=C["green"],
                marker_line_width=0,
            ),
            secondary_y=False,
        )
        fig2.add_trace(
            go.Bar(
                x=conf_m,
                y=elec_m,
                name="전기료",
                marker_color=C["amber"],
                marker_line_width=0,
            ),
            secondary_y=False,
        )
        fig2.add_trace(
            go.Scatter(
                x=conf_m,
                y=cumul_m,
                name="누계",
                mode="lines+markers",
                line=dict(color=C["blue"], width=2),
                marker=dict(size=6, color=C["blue"]),
            ),
            secondary_y=True,
        )
        apply_chart_theme(fig2, height=240, showlegend=False)
        fig2.update_layout(barmode="stack")
        fig2.update_yaxes(title_text="억원", secondary_y=False, gridcolor=GC, tickfont=dict(size=10))
        fig2.update_yaxes(title_text="누계(억)", secondary_y=True, tickfont=dict(size=10))
        fig2.update_xaxes(tickfont=dict(size=10))
        st.plotly_chart(fig2, width="stretch")
        chart_card_end()

    # ── 하단 2열 ─────────────────────────────────────────────
    col3, col4 = st.columns(2)

    with col3:
        eq = equipment_summary(df_view)
        eq_m = [m for m in ["1월", "2월", "3월"] if m in eq]
        ETYPE = ["RRU", "BBU", "안테나", "기타"]
        ECOLOR = [C["blue"], C["green"], C["amber"], C["purple"]]
        eq_totals = [sum(eq[m].values()) for m in eq_m]

        legend3 = "".join(leg(c, t) for t, c in zip(ETYPE, ECOLOR))
        stats3 = "".join(chip(m, f"{t}대") for m, t in zip(eq_m, eq_totals))
        stats3 += chip("누계", f"{sum(eq_totals)}대", C["teal"])
        chart_card_start("장비Type 현황", "장비 Type별 / 월별", legend3, stats3)

        fig3 = go.Figure()
        for t, c in zip(ETYPE, ECOLOR):
            fig3.add_trace(
                go.Bar(
                    x=eq_m,
                    y=[eq[m][t] for m in eq_m],
                    name=t,
                    marker_color=c,
                    marker_line_width=0,
                )
            )
        apply_chart_theme(fig3, height=240, showlegend=False)
        fig3.update_layout(barmode="stack")
        fig3.update_yaxes(title_text="대", gridcolor=GC, tickfont=dict(size=10))
        fig3.update_xaxes(tickfont=dict(size=10))
        st.plotly_chart(fig3, width="stretch")
        chart_card_end()

    with col4:
        legend4 = (
            leg(C["red"], "발생")
            + leg(C["green"], "완료")
            + leg(C["amber"], "미처리 누계", "line")
        )
        stats4 = (
            chip("발생", f"{voc_issued}건", C["red"])
            + chip("완료", f"{int(voc_df['처리완료'].sum()) if len(voc_df) else 0}건", C["green"])
            + chip("미처리", f"{voc_open}건", C["amber"])
        )
        chart_card_start("VoC 현황", "월별 발생·처리·미처리 누계", legend4, stats4)

        if voc_df.empty:
            st.info("VoC 데이터가 없습니다.")
        else:
            fig4 = make_subplots(specs=[[{"secondary_y": True}]])
            fig4.add_trace(
                go.Bar(
                    x=voc_df["월"],
                    y=voc_df["발생"],
                    name="발생",
                    marker_color=C["red"],
                    marker_line_width=0,
                ),
                secondary_y=False,
            )
            fig4.add_trace(
                go.Bar(
                    x=voc_df["월"],
                    y=voc_df["처리완료"],
                    name="완료",
                    marker_color=C["green"],
                    marker_line_width=0,
                ),
                secondary_y=False,
            )
            fig4.add_trace(
                go.Scatter(
                    x=voc_df["월"],
                    y=voc_df["미처리누계"],
                    name="미처리 누계",
                    mode="lines+markers",
                    line=dict(color=C["amber"], width=2),
                    marker=dict(size=6, color=C["amber"]),
                ),
                secondary_y=True,
            )
            apply_chart_theme(fig4, height=240, showlegend=False)
            fig4.update_layout(barmode="group")
            fig4.update_yaxes(
                title_text="건",
                secondary_y=False,
                gridcolor=GC,
                tickfont=dict(size=10),
                dtick=1,
            )
            fig4.update_yaxes(
                title_text="미처리 누계",
                secondary_y=True,
                tickfont=dict(size=10),
                dtick=1,
            )
            fig4.update_xaxes(tickfont=dict(size=10))
            st.plotly_chart(fig4, width="stretch")
        chart_card_end()

# ════════ TAB 2: 월별 절감 상세 ══════════════════════════════
with tab2:
    st.markdown("##### 월별 절감 실적 상세")
    st.caption("투자비 차감 후 순절감 기준 · 1~3월 확정")

    m_sum2 = monthly_summary(df_view)
    STATUS_STYLE = {
        "확정": ("#EAF3DE", "#3B6D11"),
        "검토중": ("#FAEEDA", "#854F0B"),
        "예정": ("#F1EFE8", "#5F5E5A"),
    }

    def _badge(text, bg, fg):
        return '<span style="background:{};color:{};border-radius:4px;padding:1px 6px;font-size:10px;font-weight:500">{}</span>'.format(
            bg, fg, text
        )

    def _fmt(v, suffix="", color=None):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return '<span style="color:#888">—</span>'
        s = str(v) + suffix
        if color:
            return '<span style="color:{};font-weight:500">{}</span>'.format(color, s)
        return s

    rows_html = []
    for _, row in m_sum2.iterrows():
        mon = row["월"]
        actual = int(row["실적"]) if row["실적"] else 0
        cumul = row["누계"]
        pct = row["누계달성률"]
        c_ije = int(row["임차+전기"])
        c_elec = int(row["전기만"])
        c_none = int(row["절감없음"])
        r_rent = row["임차료절감"]
        r_elec = row["전기료절감"]
        r_inv = row["투자비"]
        r_net = row["순절감"]
        status = row["상태"]

        if pct is not None and not pd.isna(pct):
            pc = C["green"] if pct >= 100 else (C["amber"] if pct >= 50 else C["red"])
            pct_html = '<span style="color:{};font-weight:500">{}%</span>'.format(pc, pct)
        else:
            pct_html = '<span style="color:#888">—</span>'

        cumul_html = (
            _fmt(cumul, "건") if (cumul and not pd.isna(cumul)) else '<span style="color:#888">—</span>'
        )
        sbg, sfg = STATUS_STYLE.get(status, ("#F1EFE8", "#5F5E5A"))

        rows_html.append(
            "".join(
                [
                    "<tr>",
                    "<td><b>{}</b></td>".format(mon),
                    '<td style="text-align:right">{}</td>'.format(
                        _fmt(actual if actual else None, "건", C["green"])
                    ),
                    '<td style="text-align:right">{}</td>'.format(cumul_html),
                    '<td style="text-align:right">{}</td>'.format(pct_html),
                    '<td style="text-align:right">{}</td>'.format(_badge(c_ije, "#EAF3DE", "#3B6D11")),
                    '<td style="text-align:right">{}</td>'.format(_badge(c_elec, "#FAEEDA", "#854F0B")),
                    '<td style="text-align:right">{}</td>'.format(_badge(c_none, "#F1EFE8", "#5F5E5A")),
                    '<td style="text-align:right">{}</td>'.format(
                        _fmt(r_rent if r_rent else None, "억", C["green"])
                    ),
                    '<td style="text-align:right">{}</td>'.format(
                        _fmt(r_elec if r_elec else None, "억", C["amber"])
                    ),
                    '<td style="text-align:right">{}</td>'.format(
                        _fmt(r_inv if r_inv else None, "억", C["red"])
                    ),
                    '<td style="text-align:right">{}</td>'.format(
                        _fmt(r_net if r_net else None, "억", C["green"])
                    ),
                    "<td>{}</td>".format(_badge(status, sbg, sfg)),
                    "</tr>",
                ]
            )
        )

    HEADERS = [
        "월",
        "실적",
        "누계",
        "누계달성률",
        "임차+전기",
        "전기만",
        "절감없음",
        "임차료절감",
        "전기료절감",
        "투자비",
        "순절감",
        "상태",
    ]
    th = "padding:5px;border-bottom:1px solid rgba(128,128,128,0.15);"
    st.markdown(
        '<table style="width:100%;border-collapse:collapse;font-size:11px">'
        '<thead><tr style="background:var(--secondary-background-color)">'
        + "".join(
            '<th style="{}{}">{}</th>'.format(
                th, "text-align:left" if i == 0 else "text-align:right", h
            )
            for i, h in enumerate(HEADERS)
        )
        + "</tr></thead><tbody>"
        + "".join(rows_html)
        + "</tbody></table>",
        unsafe_allow_html=True,
    )

    st.divider()
    td1, td2 = st.columns(2)

    with td1:
        st.markdown("##### 누계 달성률 추이")
        valid2 = m_sum2[m_sum2["누계달성률"].notna()]
        fig_p = go.Figure()
        fig_p.add_trace(
            go.Scatter(
                x=valid2["월"],
                y=valid2["누계달성률"],
                mode="lines+markers+text",
                line=dict(color=C["blue"], width=2.5),
                marker=dict(size=8, color=C["blue"], line=dict(color="white", width=2)),
                fill="tozeroy",
                fillcolor="rgba(24,95,165,0.08)",
                text=[f"{v}%" for v in valid2["누계달성률"]],
                textposition="top center",
                textfont=dict(size=11),
            )
        )
        fig_p.add_hline(
            y=100,
            line_dash="dash",
            line_color=C["red"],
            annotation_text="목표 100%",
            annotation_font_size=10,
        )
        apply_chart_theme(fig_p, height=200, showlegend=False)
        fig_p.update_yaxes(range=[0, 120], ticksuffix="%", gridcolor=GC, tickfont=dict(size=10))
        fig_p.update_xaxes(tickfont=dict(size=10))
        st.plotly_chart(fig_p, width="stretch")

    with td2:
        st.markdown("##### 절감유형 비율")
        sav_cnt = df_conf["sav_type"].value_counts()
        fig_s = go.Figure(
            go.Pie(
                labels=sav_cnt.index.tolist(),
                values=sav_cnt.values.tolist(),
                marker=dict(colors=[SAV_C.get(l, C["gray"]) for l in sav_cnt.index]),
                hole=0.65,
                textinfo="none",
            )
        )
        apply_chart_theme(fig_s, height=200, showlegend=False)
        fig_s.update_layout(
            legend=dict(font=dict(size=10), orientation="v", x=0.72, y=0.5)
        )
        st.plotly_chart(fig_s, width="stretch")

# ════════ TAB 3: 사업유형 상세 ═══════════════════════════════
with tab3:
    bs = biz_type_summary(df_conf)
    ta1, ta2 = st.columns([3, 2])

    with ta1:
        st.markdown("##### 사업유형 × 절감유형")
        fig_a1 = go.Figure()
        for sav, color in SAV_C.items():
            fig_a1.add_trace(
                go.Bar(
                    name=sav,
                    x=bs["사업유형"],
                    y=bs[sav],
                    marker_color=color,
                    marker_line_width=0,
                )
            )
        apply_chart_theme(fig_a1, height=240, showlegend=True)
        fig_a1.update_layout(
            barmode="stack",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)),
        )
        fig_a1.update_yaxes(title_text="건수", gridcolor=GC, tickfont=dict(size=10))
        fig_a1.update_xaxes(tickfont=dict(size=11))
        st.plotly_chart(fig_a1, width="stretch")

    with ta2:
        st.markdown("##### 임차료 절감 (억원)")
        fig_a2 = go.Figure(
            go.Bar(
                x=bs["임차료절감"],
                y=bs["사업유형"],
                orientation="h",
                marker_color=[BIZ_C.get(b, C["gray"]) for b in bs["사업유형"]],
                marker_line_width=0,
                text=[f"{v}억" for v in bs["임차료절감"]],
                textposition="outside",
            )
        )
        apply_chart_theme(fig_a2, height=240, showlegend=False)
        fig_a2.update_xaxes(title_text="억원", tickfont=dict(size=10), gridcolor=GC)
        fig_a2.update_yaxes(tickfont=dict(size=11))
        st.plotly_chart(fig_a2, width="stretch")

    st.divider()
    st.markdown("##### 사업유형별 상세")

    def _bep_html(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "—"
        vi = int(v)
        c = C["green"] if vi <= 24 else (C["amber"] if vi <= 48 else C["red"])
        return '<span style="color:{};font-weight:500">{}개월</span>'.format(c, vi)

    rows_biz = []
    for _, row in bs.iterrows():
        biz = row["사업유형"]
        bc = BIZ_C.get(biz, C["gray"])
        nc = C["green"] if row["순절감"] >= 0 else C["red"]
        rows_biz.append(
            "".join(
                [
                    "<tr>",
                    '<td><span style="background:{}22;color:{};border-radius:4px;padding:1px 7px;font-size:10px;font-weight:500">{}</span></td>'.format(
                        bc, bc, biz
                    ),
                    '<td style="text-align:right;font-weight:500">{}</td>'.format(int(row["건수"])),
                    '<td style="text-align:right"><span style="background:#EAF3DE;color:#3B6D11;border-radius:3px;padding:0 5px;font-size:10px">{}</span></td>'.format(
                        int(row["임차+전기"])
                    ),
                    '<td style="text-align:right"><span style="background:#FAEEDA;color:#854F0B;border-radius:3px;padding:0 5px;font-size:10px">{}</span></td>'.format(
                        int(row["전기만"])
                    ),
                    '<td style="text-align:right"><span style="background:#F1EFE8;color:#5F5E5A;border-radius:3px;padding:0 5px;font-size:10px">{}</span></td>'.format(
                        int(row["절감없음"])
                    ),
                    '<td style="text-align:right;color:{};font-weight:500">{}억</td>'.format(
                        C["green"], row["임차료절감"]
                    ),
                    '<td style="text-align:right;color:{}">{}억</td>'.format(
                        C["amber"], row["전기료절감"]
                    ),
                    '<td style="text-align:right;color:{}">{}</td>'.format(
                        C["red"], "{}억".format(row["투자비"]) if row["투자비"] else "—"
                    ),
                    '<td style="text-align:right;color:{};font-weight:500">{}억</td>'.format(
                        nc, row["순절감"]
                    ),
                    '<td style="text-align:right">{}</td>'.format(_bep_html(row["평균BEP"])),
                    "</tr>",
                ]
            )
        )

    BIZ_H = [
        "사업유형",
        "건수",
        "임차+전기",
        "전기만",
        "절감없음",
        "임차료절감",
        "전기료절감",
        "투자비",
        "순절감",
        "평균BEP",
    ]
    st.markdown(
        '<table style="width:100%;border-collapse:collapse;font-size:11px">'
        '<thead><tr style="background:var(--secondary-background-color)">'
        + "".join(
            '<th style="padding:5px;border-bottom:1px solid rgba(128,128,128,0.15);text-align:{}">{}</th>'.format(
                "left" if i == 0 else "right", h
            )
            for i, h in enumerate(BIZ_H)
        )
        + "</tr></thead><tbody>"
        + "".join(rows_biz)
        + "</tbody></table>",
        unsafe_allow_html=True,
    )

    opt = df_conf[df_conf["biz_type"] == "최적화후폐국"]
    opt_inv = opt[opt["inv_total"] > 0]
    if not opt_inv.empty:
        avg_bep = opt_inv["bep_months"].dropna().mean()
        inv_sum = round(opt_inv["inv_total"].sum() / 10000, 2)
        net_sum = round(opt_inv["net_savings"].sum() / 10000, 2)
        bep_str = "{}개월".format(int(avg_bep)) if not pd.isna(avg_bep) else "—"
        st.info(
            "📌 **최적화후폐국** 투자비 발생 {}건 / 평균 BEP **{}**  \n순절감 합계: {}억원 (투자비 {}억 차감 후)".format(
                len(opt_inv), bep_str, net_sum, inv_sum
            )
        )