"""
streamlit_app.py  —  폐국 관리 시스템 · 메인 현황
최종 업데이트: 2026-04-18 (Streamlit 최신 문법 반영)
"""
import sys
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── 1. 경로 및 데이터 로더 설정 ──────────────────────────────────
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from utils.data_loader import (
    load_raw, file_hash, apply_extra, load_extra, MAIN_FILE, RENT_FILE,
)
from utils.calc import (
    calc_savings, monthly_summary, biz_type_summary,
    equipment_summary, voc_summary, ANNUAL_GOAL, CONFIRMED,
)

# ── 2. 페이지 기본 설정 ────────────────────────────────────────
st.set_page_config(
    page_title="폐국 관리 BI — 04.중부",
    page_icon="📊",
    layout="wide",
)

# ── 3. 전문적인 BI 스타일링 (CSS) ──────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #F4F7F9; }
    .kpi-card {
        background-color: #FFFFFF;
        border-radius: 12px;
        padding: 22px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border: 1px solid #E2E8F0;
    }
    .kpi-label { font-size: 13px; color: #64748B; font-weight: 600; margin-bottom: 8px; }
    .kpi-value { font-size: 28px; font-weight: 800; color: #0F172A; }
    .kpi-bar-bg { height: 6px; border-radius: 3px; background-color: #F1F5F9; margin-top: 10px;}
    .kpi-bar-fill { height: 6px; border-radius: 3px; }
    .chart-card {
        background-color: #FFFFFF;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #E2E8F0;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

C = {"blue": "#1D4ED8", "green": "#10B981", "amber": "#F59E0B", "red": "#EF4444", "purple": "#8B5CF6", "teal": "#14B8A6", "grid": "#F1F5F9"}

# ── 4. 데이터 로딩 ─────────────────────────────────────
@st.cache_data(show_spinner="데이터 로딩 중...")
def get_processed_data(fhash):
    df_raw = load_raw(fhash)
    extra = load_extra()
    df = apply_extra(df_raw, extra)
    df_pool = df[(df.get("site_err", pd.Series("정상", index=df.index)) == "정상") & 
                 (df.get("pool_yn", pd.Series("반영", index=df.index)) == "반영")].copy()
    return calc_savings(df_pool)

try:
    df_pool = get_processed_data(file_hash(MAIN_FILE))
    df_conf = df_pool[df_pool["off_month"].isin(CONFIRMED)]
except Exception as e:
    st.error("데이터 로딩 실패: utils 폴더와 데이터 파일을 확인하세요.")
    st.stop()

# ── 5. 사이드바 (최신 width 문법 반영) ─────────────────────
with st.sidebar:
    st.markdown("### 📡 폐국 관리 시스템")
    st.caption("04.중부 본부")
    st.divider()
    
    # 메인 페이지 링크
    st.page_link("streamlit_app.py", label="📊 실적 대시보드", icon="📈")
    
    pool_page = "pages/1_후보_Pool_편집.py"
    if Path(pool_page).exists():
        st.page_link(pool_page, label="📋 후보 Pool 편집", icon="📝")
        
    st.divider()
    # use_container_width=True 대신 width='stretch' 사용
    if st.button("🔄 데이터 새로고침", width="stretch"):
        st.cache_data.clear()
        st.rerun()

# ── 6. KPI 카드 ──────────────────────────────────────────
st.title("📊 폐국 운영 현황")

total_conf = len(df_conf)
rent_conf  = round(df_conf["savings_ann"].sum() * 0.85 / 10000, 1)
elec_conf  = round(df_conf["elec_ann"].sum() / 10000, 1)
pct_conf   = round(total_conf / ANNUAL_GOAL * 100, 1)

def draw_kpi(label, value, unit, progress, color):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}<span style="font-size:16px">{unit}</span></div>
        <div class="kpi-bar-bg"><div class="kpi-bar-fill" style="width:{min(progress, 100)}%; background-color:{color}"></div></div>
    </div>
    """, unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
with k1: draw_kpi("누계 실적", str(total_conf), "건", pct_conf, C["blue"])
with k2: draw_kpi("임차 절감", str(rent_conf), "억", 80, C["green"])
with k3: draw_kpi("전기 절감", str(elec_conf), "억", 45, C["amber"])
with k4: draw_kpi("목표 달성률", str(pct_conf), "%", pct_conf, C["purple"])

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# ── 7. 메인 차트 ─────────────────────────────────────────
tab1, tab2 = st.tabs(["📈 트렌드 분석", "📑 상세 데이터"])

with tab1:
    col_l, col_r = st.columns(2)
    m_sum = monthly_summary(df_pool)
    
    with col_l:
        st.markdown('<div class="chart-card"><b>월별 실적 및 누계 달성률</b>', unsafe_allow_html=True)
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Bar(x=m_sum["월"], y=m_sum["실적"], name="실적", marker_color=C["blue"]), secondary_y=False)
        fig1.add_trace(go.Scatter(x=m_sum["월"], y=m_sum["누계달성률"], name="달성률", line=dict(color=C["green"], width=3)), secondary_y=True)
        fig1.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0), showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        # plotly_chart는 기존 use_container_width 방식을 유지하거나 설정을 따름
        st.plotly_chart(fig1, width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_r:
        st.markdown('<div class="chart-card"><b>사업유형별 비중</b>', unsafe_allow_html=True)
        bs = biz_type_summary(df_conf)
        fig2 = go.Figure(data=[go.Pie(labels=bs["사업유형"], values=bs["건수"], hole=.4, marker=dict(colors=[C["blue"], C["purple"], C["teal"]]))])
        fig2.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig2, width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    # 데이터프레임 최신 width 문법 반영
    st.dataframe(
        m_sum,
        width="stretch",
        hide_index=True,
        column_config={
            "누계달성률": st.column_config.ProgressColumn("달성률(%)", min_value=0, max_value=100, format="%d%%"),
            "순절감": st.column_config.NumberColumn("순절감(억)", format="%.2f")
        }
    )
    st.markdown('</div>', unsafe_allow_html=True)