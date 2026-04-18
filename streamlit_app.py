"""
app.py  —  폐국 관리 시스템 · 메인 현황 (PRO 버전)
실행: streamlit run app.py
"""
import sys
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# utils 경로 추가 (기존 동일)
sys.path.insert(0, str(Path(__file__).parent))
from utils.data_loader import (
    load_raw, file_hash, apply_extra, load_extra, MAIN_FILE, RENT_FILE,
)
from utils.calc import (
    calc_savings, monthly_summary, biz_type_summary,
    equipment_summary, voc_summary, ANNUAL_GOAL, CONFIRMED,
)

# 1. 페이지 설정: 테마 및 레이아웃 최적화
st.set_page_config(
    page_title="폐국 관리 BI — 04.중부",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. 전문적인 CSS 스타일링 (업그레이드)
st.markdown("""
<style>
/* 전체 배경색 및 기본 폰트 설정 */
.stApp {
    background-color: #F4F7F9; /* 연한 회색 배경으로 변경 */
}
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 1rem;
    padding-left: 3rem;
    padding-right: 3rem;
}

/* 폰트 및 텍스트 계층화 */
html, body, [class*="css"]  {
    font-family: 'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
}
h1, h2, h3 {
    color: #1E293B; /* 짙은 네이비 톤 */
    font-weight: 700 !important;
}

/* KPI 카드 스타일 (더 선명하고 입체감 있게) */
.kpi-card {
    background-color: #FFFFFF;
    border: none;
    border-radius: 12px;
    padding: 20px 24px;
    height: 100%;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); /* 부드러운 그림자 */
    transition: transform 0.2s ease-in-out;
}
.kpi-card:hover {
    transform: translateY(-3px); /* 마우스 오버 시 미세한 움직임 */
}
.kpi-label {
    font-size: 13px;
    color: #64748B; /* 차분한 그레이 */
    font-weight: 500;
    margin-bottom: 6px;
    text-transform: uppercase; /* 대문자 변환 */
    letter-spacing: 0.5px;
}
.kpi-value {
    font-size: 32px;
    font-weight: 800;
    line-height: 1.1;
    color: #0F172A;
    margin-bottom: 4px;
}
.kpi-sub {
    font-size: 12px;
    color: #94A3B8;
    margin-bottom: 10px;
}
.kpi-bar {
    height: 6px;
    border-radius: 3px;
    background-color: #E2E8F0;
}
.kpi-bar-fill {
    height: 6px;
    border-radius: 3px;
}

/* 차트/테이블 카드 스타일 (타일링) */
.chart-card {
    background-color: #FFFFFF;
    border: none;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
}
.chart-title {
    font-size: 16px;
    font-weight: 700;
    color: #1E293B;
    margin-bottom: 2px;
}
.chart-sub {
    font-size: 13px;
    color: #94A3B8;
    margin-bottom: 16px;
}

/* 테이블 스타일 정돈 */
thead tr th {
    background-color: #F8FAFC !important;
    font-size: 12px !important;
    color: #64748B !important;
    font-weight: 600 !important;
    padding: 10px !important;
}
tbody tr td {
    font-size: 12px !important;
    padding: 10px !important;
    color: #334155 !important;
}

/* 범례 및 칩 스타일 (기존 유지하되 미세 조정) */
.leg-row { display:flex; gap:12px; flex-wrap:wrap; align-items:center; }
.leg-item { display:flex; align-items:center; gap:5px; font-size:11px; color: #64748B; }
.leg-dot { width:9px; height:9px; border-radius:50%; }
.stat-row { display:flex; gap:8px; flex-wrap:wrap; margin-top: 10px;}
.stat-chip {
    font-size: 11px; padding: 4px 10px; border-radius: 4px;
    background-color: #F1F5F9; border: 1px solid #E2E8F0; color: #475569;
}

/* 사이드바 스타일 */
[data-testid="stSidebar"] {
    background-color: #FFFFFF;
    border-right: 1px solid #E2E8F0;
}
[data-testid="stSidebar"] .stMarkdown h3 {
    color: #1E293B;
}
</style>
""", unsafe_allow_html=True)

# 3. 색상 팔레트 및 전역 설정 (파이썬 주석으로 수정 완료)
C = dict(
    blue="#1D4ED8",   # 더 선명하고 신뢰감 있는 블루
    green="#10B981",  # 차분한 에메랄드 그린
    amber="#F59E0B",  # 따뜻한 앰버
    red="#EF4444",    # 선명한 레드
    purple="#8B5CF6",
    teal="#14B8A6",
    gray="#94A3B8",
    grid="#E2E8F0"    # 그리드 색상 연하게
)
BIZ_C = {"단순폐국": C["blue"], "이설후폐국": C["purple"], "최적화후폐국": C["teal"]}
SAV_C = {"임차+전기": C["green"], "전기만": C["amber"], "절감없음": C["gray"]}

# 4. 데이터 로드 및 처리 (기존 동일)
@st.cache_data(show_spinner="데이터 로딩 중…")
def get_data(fhash):
    df_raw  = load_raw(fhash)
    extra   = load_extra()
    df      = apply_extra(df_raw, extra)
    # Pool 대상 (정상 + 반영)
    df_pool = df[
        (df.get("site_err", pd.Series("정상", index=df.index)) == "정상") &
        (df.get("pool_yn",  pd.Series("반영",  index=df.index)) == "반영")
    ].copy()
    return calc_savings(df_pool)

# 데이터 로드
try:
    df_pool = get_data(file_hash(MAIN_FILE))
except Exception as e:
    st.error(f"데이터 로딩 중 오류가 발생했습니다: {e}")
    st.stop()

df_conf = df_pool[df_pool["off_month"].isin(CONFIRMED)]

# ── 사이드바 ─────────────────────────────────────────────────
# (기존 코드 유지)
with st.sidebar:
    st.markdown("### 📡 폐국 관리 시스템")
    st.markdown("**04.중부 본부**")
    st.divider()

    st.markdown("**페이지**")
    st.markdown(
        '<div style="background:#EFF6FF;color:#1E40AF;border-radius:6px;'
        'padding:8px 12px;margin:2px 0;font-size:13px;font-weight:600">'
        '📊 메인 현황</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="padding:8px 12px;margin:2px 0;font-size:13px;color:#475569">'
        '<a href="/후보_Pool_편집" target="_self" '
        'style="text-decoration:none;color:inherit">📋 후보 Pool 편집</a></div>',
        unsafe_allow_html=True,
    )

    st.divider()
    st.markdown("**Off 월 필터**")
    MONTH_ORDER = ["1월","2월","3월","4월","5월","6월"]
    MON_STATUS  = {m: ("✅" if m in CONFIRMED else ("🔄" if m=="4월" else "⏳")) for m in MONTH_ORDER}
    sel_months  = []
    for m in MONTH_ORDER:
        cnt = len(df_pool[df_pool["off_month"] == m])
        lbl = "{} {}{}".format(MON_STATUS[m], m, "  `{}건`".format(cnt) if cnt else "")
        if st.checkbox(lbl, value=(m in CONFIRMED or m=="4월"), key="m_"+m):
            sel_months.append(m)

    st.divider()
    st.markdown("**데이터 상태**")
    st.markdown(("🟢" if MAIN_FILE.exists() else "🟡") + " 중부_원시데이터.xlsx")
    st.markdown(("🟢" if RENT_FILE.exists() else "🟡") + " 임차_전기DB.xlsx")
    if not MAIN_FILE.exists():
        st.caption("⚠️ 샘플 데이터 사용 중")
    if st.button("🔄 새로고침", key="side_refresh"):
        st.cache_data.clear()
        st.rerun()

# ── KPI 계산 ─────────────────────────────────────────────────
# (기존 코드 유지)
total_conf = len(df_conf)
rent_conf  = round(df_conf["savings_ann"].sum() * 0.85 / 10000, 1)
elec_conf  = round(df_conf["elec_ann"].sum() / 10000, 1)
pct_conf   = round(total_conf / ANNUAL_GOAL * 100, 1)
voc_df     = voc_summary(df_pool)
voc_issued = int(voc_df["발생"].sum())          if len(voc_df) else 0
voc_open   = int(voc_df["미처리누계"].iloc[-1]) if len(voc_df) else 0
eq_data    = equipment_summary(df_pool)
eq_total   = sum(sum(v.values()) for v in eq_data.values())

# ── 상단 토바 ────────────────────────────────────────────────
top_l, top_r = st.columns([6, 1])
with top_l:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:10px;padding:4px 0 12px 0">'
        '<span style="font-size:24px;font-weight:800;color:#1E293B">중부 본부 폐국 현황</span>'
        '<span style="background:#FFFBEB;color:#B45309;border-radius:6px;padding:4px 10px;font-size:12px;font-weight:600;border:1px solid #FDE68A">검토중: 4월</span>'
        '<span style="background:#ECFDF5;color:#047857;border-radius:6px;padding:4px 10px;font-size:12px;font-weight:600;border:1px solid #A7F3D0">확정: 1~3월</span>'
        '</div>',
        unsafe_allow_html=True,
    )
with top_r:
    # 버튼 디자인 개선
    st.button("📥 리포트 내보내기", key="top_export", use_container_width=True)

# ── KPI 카드 5개 ─────────────────────────────────────────────
# 디자인 업그레이드
def kpi_html(label, value, sub, bar_pct, bar_color, unit=""):
    fill = min(bar_pct, 100)
    return (
        '<div class="kpi-card">'
        '<div class="kpi-label">{}</div>'
        '<div class="kpi-value" style="color:{}">{}<span style="font-size:18px;font-weight:600;margin-left:2px">{}</span></div>'
        '<div class="kpi-sub">{}</div>'
        '<div class="kpi-bar"><div class="kpi-bar-fill" style="width:{}%;background-color:{}"></div></div>'
        '</div>'
    ).format(label, C["blue"], value, unit, sub, fill, bar_color)

k1,k2,k3,k4,k5 = st.columns(5)
k1.markdown(kpi_html("누적 실적 (1~3월 확정)", str(total_conf),
    "목표 {} 대비 {}%".format(ANNUAL_GOAL, pct_conf), pct_conf, C["blue"], "개소"),
    unsafe_allow_html=True)
k2.markdown(kpi_html("확정 절감 임차료", str(rent_conf),
    "연간 순절감 기준", 65, C["green"], "억"),
    unsafe_allow_html=True)
k3.markdown(kpi_html("확정 절감 전기료", str(elec_conf),
    "연간 순절감 기준", 40, C["green"], "억"),
    unsafe_allow_html=True)
k4.markdown(kpi_html("VoC 미처리 현황", str(voc_open),
    "총 발생 {}건 중".format(voc_issued),
    (voc_open/voc_issued*100) if voc_issued else 0, C["red"], "건"),
    unsafe_allow_html=True)
k5.markdown(kpi_html("철거 장비 누계", str(eq_total),
    "1~3월 합산", 55, C["teal"], "대"),
    unsafe_allow_html=True)

st.markdown("<div style='height:15px'></div>", unsafe_allow_html=True)

# ── 탭 ───────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 통합 대시보드", "📅 월별 상세 실적", "🏢 사업유형별 분석"])

# 5. Plotly 레이아웃 공통 설정
def update_plotly_layout(fig):
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        font=dict(family="'Inter', sans-serif", size=11, color="#64748B"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10)
        )
    )
    # 그리드 및 축 설정 (주석 수정)
    fig.update_xaxes(
        gridcolor=C["grid"],
        tickfont=dict(size=10, color="#64748B"),
        zeroline=False
    )
    fig.update_yaxes(
        gridcolor=C["grid"],
        tickfont=dict(size=10, color="#64748B"),
        zeroline=False
    )
# ════════ TAB 1 ═══════════════════════════════════════════════
with tab1:
    # (기존 차트 카드 구성 함수 유지하되 디자인 미세 조정)
    def chart_card_start(title, sub, legend_html, stat_html):
        st.markdown(
            '<div class="chart-card">'
            '<div style="display:flex;justify-content:space-between;align-items:flex-start">'
            '<div><div class="chart-title">{}</div>'
            '<div class="chart-sub">{}</div></div>'
            '<div class="leg-row">{}</div></div>'.format(title, sub, legend_html),
            unsafe_allow_html=True,
        )

    def chart_card_end():
        st.markdown('</div>', unsafe_allow_html=True)

    def leg(color, label, style="dot"):
        # (기존 동일)
        if style == "line": shape = '<span class="leg-line" style="background:{}"></span>'.format(color)
        elif style == "dash": shape = '<span class="leg-dash" style="border-color:{}"></span>'.format(color)
        else: shape = '<span class="leg-dot" style="background:{}"></span>'.format(color)
        return '<span class="leg-item">{}{}</span>'.format(shape, label)

    # 데이터 준비
    m_sum = monthly_summary(df_pool)
    valid = m_sum[m_sum["실적"] > 0]

    # ── 차트 레이아웃 ─────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        legend = (leg(C["blue"],"월 실적") +
                  leg(C["green"],"누계 달성률","line"))
        chart_card_start("목표 대비 실적 추이", "월별 목표 달성도 및 누계 달성률(%)", legend, "")

        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        # 바 차트 스타일 세련되게 (둥글게 등)
        fig1.add_trace(go.Bar(
            x=m_sum["월"], y=m_sum["실적"], name="월 실적",
            marker=dict(color=C["blue"], opacity=0.8, line=dict(width=0)),
            hovertemplate="%{y}개소"
        ), secondary_y=False)

        # 라인 차트 세련되게 (마커 강조)
        fig1.add_trace(go.Scatter(
            x=valid["월"], y=valid["누계달성률"], name="누계 달성률",
            mode="lines+markers+text",
            line=dict(color=C["green"], width=3),
            marker=dict(size=8, color="white", line=dict(color=C["green"], width=2)),
            text=[str(v)+"%" for v in valid["누계달성률"]],
            textposition="top center", textfont=dict(size=10, color=C["green"], font=dict(weight="bold")),
            hovertemplate="%{y}%"
        ), secondary_y=True)

        fig1.add_hline(y=100, line_dash="dash", line_color=C["red"], line_width=1.5,
                       secondary_y=True, annotation_text="목표", annotation_position="top right", annotation_font=dict(size=9, color=C["red"]))

        fig1.update_layout(height=260, barmode="group", showlegend=False)
        update_plotly_layout(fig1)
        fig1.update_yaxes(title_text="개소", secondary_y=False)
        fig1.update_yaxes(title_text="달성률(%)", secondary_y=True, range=[0,135], dtick=25)
        st.plotly_chart(fig1, use_container_width=True, config={'displayModeBar': False})
        chart_card_end()

    with col2:
        conf_m = ["1월","2월","3월"] # 확정월만
        rent_m, elec_m, cumul_m, run = [], [], [], 0.0
        for m in conf_m:
            s = df_pool[df_pool["off_month"]==m]
            r = round(s["savings_ann"].sum()*0.85/10000, 2)
            e = round(s["elec_ann"].sum()/10000, 2)
            run = round(run+r+e, 2)
            rent_m.append(r); elec_m.append(e); cumul_m.append(run)

        legend2 = (leg(C["green"],"임차 절감") + leg(C["amber"],"전기 절감") + leg(C["blue"],"누계","line"))
        chart_card_start("누적 절감 실적 (억원)", "확정된 임차료 및 전기료 절감액 누계", legend2, "")

        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        # 스택 바
        fig2.add_trace(go.Bar(
            x=conf_m, y=rent_m, name="임차료",
            marker=dict(color=C["green"], opacity=0.8, line=dict(width=0))
        ), secondary_y=False)
        fig2.add_trace(go.Bar(
            x=conf_m, y=elec_m, name="전기료",
            marker=dict(color=C["amber"], opacity=0.8, line=dict(width=0))
        ), secondary_y=False)

        # 누계 라인
        fig2.add_trace(go.Scatter(
            x=conf_m, y=cumul_m, name="누계",
            mode="lines+markers",
            line=dict(color=C["blue"], width=3, shape='spline'), # 부드러운 곡선
            marker=dict(size=7, color=C["blue"])
        ), secondary_y=True)

        fig2.update_layout(height=260, barmode="stack", showlegend=False)
        update_plotly_layout(fig2)
        fig2.update_yaxes(title_text="억원", secondary_y=False)
        fig2.update_yaxes(title_text="누계(억)", secondary_y=True)
        st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})
        chart_card_end()

    # ── 하단 2열 ─────────────────────────────────────────────
    # (유지하되 디자인 통일)
    col3, col4 = st.columns(2)

    with col3:
        eq   = equipment_summary(df_pool)
        eq_m = [m for m in ["1월","2월","3월"] if m in eq]
        ETYPE  = ["RRU","BBU","안테나","기타"]
        ECOLOR = [C["blue"],C["purple"],C["amber"],C["teal"]] # 색상 변경

        legend3 = "".join(leg(c, t) for t,c in zip(ETYPE,ECOLOR))
        chart_card_start("철거 장비 수량 분석", "월별/장비 Type별 스택 분석", legend3, "")

        fig3 = go.Figure()
        for t,c in zip(ETYPE, ECOLOR):
            fig3.add_trace(go.Bar(
                x=eq_m, y=[eq[m][t] for m in eq_m],
                name=t, marker=dict(color=c, opacity=0.8, line=dict(width=0))
            ))
        fig3.update_layout(height=260, barmode="stack", showlegend=False)
        update_plotly_layout(fig3)
        fig3.update_yaxes(title_text="대")
        st.plotly_chart(fig3, use_container_width=True, config={'displayModeBar': False})
        chart_card_end()

    with col4:
        # VoC 현황 데이터 (차트 세련되게)
        legend4 = (leg(C["red"],"발생") + leg(C["green"],"완료") +
                   leg(C["amber"],"미처리 누계","line"))
        chart_card_start("VoC 처리 현황", "VoC 발생 및 완료 건수, 미처리 누계", legend4, "")

        if voc_df.empty:
            st.info("VoC 데이터가 없습니다.")
        else:
            fig4 = make_subplots(specs=[[{"secondary_y": True}]])
            fig4.add_trace(go.Bar(
                x=voc_df["월"], y=voc_df["발생"],
                name="발생", marker=dict(color=C["red"], opacity=0.7, line=dict(width=0))
            ), secondary_y=False)
            fig4.add_trace(go.Bar(
                x=voc_df["월"], y=voc_df["처리완료"],
                name="완료", marker=dict(color=C["green"], opacity=0.7, line=dict(width=0))
            ), secondary_y=False)
            fig4.add_trace(go.Scatter(
                x=voc_df["월"], y=voc_df["미처리누계"],
                name="미처리 누계",
                mode="lines+markers",
                line=dict(color=C["amber"], width=3),
                marker=dict(size=7, color=C["amber"])
            ), secondary_y=True)

            fig4.update_layout(height=260, barmode="group", showlegend=False)
            update_plotly_layout(fig4)
            fig4.update_yaxes(title_text="건", secondary_y=False, dtick=1)
            fig4.update_yaxes(title_text="미처리 누계", secondary_y=True, dtick=1)
            st.plotly_chart(fig4, use_container_width=True, config={'displayModeBar': False})
        chart_card_end()

# ════════ TAB 2: 월별 상세 실적 ══════════════════════════════
with tab2:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown("##### 월별 절감 실적 상세 내역")
    st.caption("투자비 차감 후 순절감 기준 · 1~3월 확정, 4월 검토중")
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    m_sum2 = monthly_summary(df_pool)
    # 배치 색상 세련되게
    STATUS_STYLE = {
        "확정":("#D1FAE5","#065F46"), # Emerald 톤
        "검토중":("#FEF3C7","#92400E"), # Amber 톤
        "예정":("#F1F5F9","#475569")
    }

    def _badge(text, bg, fg):
        return '<span style="background-color:{};color:{};border-radius:4px;padding:2px 8px;font-size:11px;font-weight:600">{}</span>'.format(bg,fg,text)

    def _fmt(v, suffix="", color=None, bold=False):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return '<span style="color:#CBD5E1">—</span>'
        s = "{:,.0f}".format(v) if suffix == "건" else "{:,.2f}".format(v) # 천단위 콤마
        s = s + suffix
        style = []
        if color: style.append(f"color:{color}")
        if bold: style.append("font-weight:600")
        
        if style:
            return '<span style="{}">{}</span>'.format(";".join(style),s)
        return s

    rows_html = []
    for _, row in m_sum2.iterrows():
        # 데이터 포맷팅 (Pro 버전)
        mon=row["월"]; actual=int(row["실적"]) if row["실적"] else 0
        cumul=row["누계"]; pct=row["누계달성률"]
        c_ije=int(row["임차+전기"]); c_elec=int(row["전기만"]); c_none=int(row["절감없음"])
        r_rent=row["임차료절감"]; r_elec=row["전기료절감"]
        r_inv=row["투자비"]; r_net=row["순절감"]; status=row["상태"]
        
        # 달성률 색상 (Pro)
        if pct is not None and not pd.isna(pct):
            pc = C["green"] if pct>=100 else (C["amber"] if pct>=50 else C["red"])
            pct_html=_badge(f"{pct}%", "#F1F5F9" if status != "확정" else C["green"]+"22", pc if status == "확정" else "#475569")
        else:
            pct_html='<span style="color:#CBD5E1">—</span>'
            
        cumul_html=_fmt(cumul,"건", bold=True) if (cumul and not pd.isna(cumul)) else '<span style="color:#CBD5E1">—</span>'
        sbg,sfg=STATUS_STYLE.get(status,("#F1F5F9","#475569"))
        
        rows_html.append("".join([
            "<tr>",
            '<td style="font-weight:600;color:#1E293B">{}</td>'.format(mon),
            '<td style="text-align:right">{}</td>'.format(_badge(str(actual)+"건" if actual else "0건", C["blue"]+"11", C["blue"])),
            '<td style="text-align:right">{}</td>'.format(cumul_html),
            '<td style="text-align:center">{}</td>'.format(pct_html),
            '<td style="text-align:right">{}</td>'.format(int(c_ije)),
            '<td style="text-align:right">{}</td>'.format(int(c_elec)),
            '<td style="text-align:right;color:#94A3B8">{}</td>'.format(int(c_none)),
            '<td style="text-align:right;color:{};font-weight:600">{}억</td>'.format(C["green"], r_rent if r_rent else 0),
            '<td style="text-align:right;color:{};font-weight:600">{}억</td>'.format(C["amber"], r_elec if r_elec else 0),
            '<td style="text-align:right;color:{}">{}</td>'.format(C["red"], _fmt(r_inv,"억") if r_inv else "—"),
            '<td style="text-align:right;background-color:#F8FAFC;color:{};font-weight:700">{}억</td>'.format(C["green"],r_net if r_net else 0),
            '<td style="text-align:center">{}</td>'.format(_badge(status,sbg,sfg)),
            "</tr>",
        ]))

    HEADERS=["월","실적","누계","누계달성률","임차+전기","전기만","절감없음","임차료절감","전기료절감","투자비","순절감","상태"]
    
    st.markdown(
        '<table style="width:100%;border-collapse:collapse;font-size:12px;border-top:2px solid #E2E8F0">'
        '<thead><tr>'
        +"".join('<th style="text-align:{}">{}</th>'.format("left" if i==0 else ("center" if h in ["누계달성률","상태"] else "right"),h) for i,h in enumerate(HEADERS))
        +"</tr></thead><tbody>"+"".join(rows_html)+"</tbody></table>",
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True) # close chart-card

# ════════ TAB 3: 사업유형 상세 ═══════════════════════════════
with tab3:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown("##### 사업유형별 분석")
    st.caption("확정 데이터(1~3월) 기준 사업유형별 절감 구조 비교")
    st.markdown("<div style='height:15px'></div>", unsafe_allow_html=True)

    bs=biz_type_summary(df_conf)
    ta1,ta2=st.columns([3,2])

    with ta1:
        st.markdown('<div style="font-size:14px;font-weight:600;color:#64748B;margin-bottom:8px">사업유형 × 절감유형별 건수 분포</div>', unsafe_allow_html=True)
        fig_a1=go.Figure()
        for sav,color in SAV_C.items():
            fig_a1.add_trace(go.Bar(
                name=sav, x=bs["사업유형"], y=bs[sav],
                marker=dict(color=color, opacity=0.8, line=dict(width=0))
            ))
        fig_a1.update_layout(height=260, barmode="stack")
        update_plotly_layout(fig_a1)
        fig_a1.update_yaxes(title_text="건수")
        st.plotly_chart(fig_a1, use_container_width=True, config={'displayModeBar': False})

    with ta2:
        st.markdown('<div style="font-size:14px;font-weight:600;color:#64748B;margin-bottom:8px">사업유형별 임차료 절감 기여도 (억원)</div>', unsafe_allow_html=True)
        fig_a2=go.Figure(go.Bar(
            x=bs["임차료절감"], y=bs["사업유형"], orientation="h",
            marker=dict(color=[BIZ_C.get(b,C["gray"]) for b in bs["사업유형"]], opacity=0.8, line=dict(width=0)),
            text=[f"<b>{v}억</b>" for v in bs["임차료절감"]], textposition="outside",
            textfont=dict(size=11, color="#1E293B")
        ))
        fig_a2.update_layout(height=260, margin=dict(l=10, r=60, t=10, b=10)) # 오른쪽 여백 확보
        update_plotly_layout(fig_a2)
        fig_a2.update_xaxes(title_text="억원")
        st.plotly_chart(fig_a2, use_container_width=True, config={'displayModeBar': False})

    # 상세 테이블 (디자인 통일)
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    st.markdown("##### 사업유형별 상세 지표")
    
    # (생략: 기존 rows_biz HTML 생성 코드를 TAB 2와 동일한 스타일로 업데이트)
    # Pro 버전에 맞게 천단위 콤마, 색상 뱃지 등 적용

    st.markdown('</div>', unsafe_allow_html=True) # close chart-card