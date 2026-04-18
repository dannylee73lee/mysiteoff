"""
app.py  —  폐국 관리 시스템 · 메인 현황 (Professional BI Version)
실행: streamlit run app.py
"""
import sys
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# utils 경로 추가
sys.path.insert(0, str(Path(__file__).parent))
from utils.data_loader import (
    load_raw, file_hash, apply_extra, load_extra, MAIN_FILE, RENT_FILE,
)
from utils.calc import (
    calc_savings, monthly_summary, biz_type_summary,
    equipment_summary, voc_summary, ANNUAL_GOAL, CONFIRMED,
)

# 1. 페이지 설정
st.set_page_config(
    page_title="폐국 관리 BI — 04.중부",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. 전문적인 CSS 스타일링
st.markdown("""
<style>
    /* 전체 배경색 및 기본 폰트 */
    .stApp { background-color: #F4F7F9; }
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; padding-left: 3rem; padding-right: 3rem; }

    /* KPI 카드 스타일 */
    .kpi-card {
        background-color: #FFFFFF;
        border-radius: 12px;
        padding: 20px 24px;
        height: 100%;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: transform 0.2s ease-in-out;
    }
    .kpi-card:hover { transform: translateY(-3px); }
    .kpi-label { font-size: 13px; color: #64748B; font-weight: 500; margin-bottom: 6px; text-transform: uppercase; }
    .kpi-value { font-size: 32px; font-weight: 800; line-height: 1.1; color: #0F172A; margin-bottom: 4px; }
    .kpi-sub { font-size: 12px; color: #94A3B8; margin-bottom: 10px; }
    .kpi-bar { height: 6px; border-radius: 3px; background-color: #E2E8F0; }
    .kpi-bar-fill { height: 6px; border-radius: 3px; }

    /* 차트 타일 스타일 */
    .chart-card {
        background-color: #FFFFFF;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
    }
    .chart-title { font-size: 16px; font-weight: 700; color: #1E293B; margin-bottom: 2px; }
    .chart-sub { font-size: 13px; color: #94A3B8; margin-bottom: 16px; }

    /* 범례 스타일 */
    .leg-row { display:flex; gap:12px; flex-wrap:wrap; align-items:center; }
    .leg-item { display:flex; align-items:center; gap:5px; font-size:11px; color: #64748B; }
    .leg-dot { width:9px; height:9px; border-radius:50%; }
    
    /* 탭 디자인 */
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: transparent; border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 10px; }
</style>
""", unsafe_allow_html=True)

# 3. 색상 팔레트 (에러 수정됨: 파이썬 주석 사용)
C = dict(
    blue="#1D4ED8",   # 더 선명하고 신뢰감 있는 블루
    green="#10B981",  # 차분한 에메랄드 그린
    amber="#F59E0B",  # 따뜻한 앰버
    red="#EF4444",    # 선명한 레드
    purple="#8B5CF6",
    teal="#14B8A6",
    gray="#94A3B8",
    grid="#E2E8F0"    # 그리드 색상
)
BIZ_C = {"단순폐국": C["blue"], "이설후폐국": C["purple"], "최적화후폐국": C["teal"]}
SAV_C = {"임차+전기": C["green"], "전기만": C["amber"], "절감없음": C["gray"]}

# 4. 데이터 로드 함수
@st.cache_data(show_spinner="데이터를 분석 중입니다...")
def get_data(fhash):
    df_raw = load_raw(fhash)
    extra = load_extra()
    df = apply_extra(df_raw, extra)
    df_pool = df[
        (df.get("site_err", pd.Series("정상", index=df.index)) == "정상") &
        (df.get("pool_yn",  pd.Series("반영",  index=df.index)) == "반영")
    ].copy()
    return calc_savings(df_pool)

try:
    df_pool = get_data(file_hash(MAIN_FILE))
except Exception as e:
    st.error(f"데이터 로딩 중 오류 발생: {e}")
    st.stop()

df_conf = df_pool[df_pool["off_month"].isin(CONFIRMED)]

# ── 사이드바 ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📡 폐국 관리 시스템")
    st.markdown("**04.중부 본부**")
    st.divider()
    st.page_link("app.py", label="📊 메인 현황", icon="📈")
    st.page_link("pages/1_후보_Pool_편집.py", label="📋 후보 Pool 편집", icon="📝")
    st.divider()
    if st.button("🔄 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── KPI 계산 ─────────────────────────────────────────────────
total_conf = len(df_conf)
rent_conf  = round(df_conf["savings_ann"].sum() * 0.85 / 10000, 1)
elec_conf  = round(df_conf["elec_ann"].sum() / 10000, 1)
pct_conf   = round(total_conf / ANNUAL_GOAL * 100, 1)
voc_df     = voc_summary(df_pool)
voc_open   = int(voc_df["미처리누계"].iloc[-1]) if not voc_df.empty else 0

# ── 메인 화면 상단 ──────────────────────────────────────────
st.markdown(f'<div style="font-size:26px; font-weight:800; color:#1E293B; margin-bottom:15px;">중부 본부 폐국 운영 대시보드</div>', unsafe_allow_html=True)

# KPI 카드 렌더링 함수
def kpi_html(label, value, sub, bar_pct, color, unit=""):
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}<span style="font-size:18px; font-weight:600;">{unit}</span></div>
        <div class="kpi-sub">{sub}</div>
        <div class="kpi-bar"><div class="kpi-bar-fill" style="width:{min(bar_pct, 100)}%; background-color:{color}"></div></div>
    </div>
    """

k1, k2, k3, k4 = st.columns(4)
k1.markdown(kpi_html("누적 실적(1~3월)", str(total_conf), f"연 목표 {ANNUAL_GOAL}개비달성", pct_conf, C["blue"], "개소"), unsafe_allow_html=True)
k2.markdown(kpi_html("임차 절감액", str(rent_conf), "확정분 순절감 기준", 70, C["green"], "억"), unsafe_allow_html=True)
k3.markdown(kpi_html("전기 절감액", str(elec_conf), "확정분 순절감 기준", 45, C["amber"], "억"), unsafe_allow_html=True)
k4.markdown(kpi_html("VoC 미처리", str(voc_open), "현 시점 기준", 20, C["red"], "건"), unsafe_allow_html=True)

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

# ── 차트 레이아웃 ─────────────────────────────────────────────
tab1, tab2 = st.tabs(["📊 통합 대시보드", "📅 월별 상세 내역"])

def update_layout(fig):
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        font=dict(family="sans-serif", size=11, color="#64748B"),
        showlegend=False
    )
    fig.update_xaxes(gridcolor=C["grid"], zeroline=False)
    fig.update_yaxes(gridcolor=C["grid"], zeroline=False)

with tab1:
    c_left, c_right = st.columns(2)
    
    with c_left:
        st.markdown('<div class="chart-card"><div class="chart-title">목표 대비 실적 추이</div><div class="chart-sub">월별 폐국 수량 및 누계 달성률</div>', unsafe_allow_html=True)
        m_sum = monthly_summary(df_pool)
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Bar(x=m_sum["월"], y=m_sum["실적"], marker_color=C["blue"], name="실적"), secondary_y=False)
        fig1.add_trace(go.Scatter(
            x=m_sum["월"], y=m_sum["누계달성률"], 
            line=dict(color=C["green"], width=3), 
            marker=dict(size=8, color="white", line=dict(color=C["green"], width=2)),
            # 에러 수정됨: textfont 내부에 font=dict()를 쓰지 않음
            textfont=dict(size=10, color=C["green"], weight="bold"),
            name="달성률(%)"
        ), secondary_y=True)
        update_layout(fig1)
        st.plotly_chart(fig1, use_container_width=True, config={'displayModeBar': False})
        st.markdown('</div>', unsafe_allow_html=True)

    with c_right:
        st.markdown('<div class="chart-card"><div class="chart-title">사업유형별 분포</div><div class="chart-sub">확정 데이터 기준 구성비</div>', unsafe_allow_html=True)
        bs = biz_type_summary(df_conf)
        fig2 = go.Figure(data=[go.Pie(labels=bs["사업유형"], values=bs["건수"], hole=.4, marker_colors=[C["blue"], C["purple"], C["teal"]])])
        fig2.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=300)
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    # 데이터 테이블 디자인 최적화
    st.dataframe(
        monthly_summary(df_pool),
        use_container_width=True,
        hide_index=True,
        column_config={
            "월": st.column_config.TextColumn("월"),
            "실적": st.column_config.NumberColumn("실적(건)", format="%d"),
            "누계달성률": st.column_config.ProgressColumn("달성률", min_value=0, max_value=100, format="%d%%"),
            "순절감": st.column_config.NumberColumn("순절감(억)", format="%.2f 억"),
        }
    )
    st.markdown('</div>', unsafe_allow_html=True)