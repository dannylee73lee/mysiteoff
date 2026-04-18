"""
streamlit_app.py  —  폐국 관리 시스템 · 메인 실적 현황 (Professional BI Version)
담당 부서: 04.중부 본부
최종 수정: 2026-04-18
"""
import sys
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── 1. 시스템 환경 설정 ──────────────────────────────────────────
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

# ── 2. 페이지 레이아웃 정의 ──────────────────────────────────────
st.set_page_config(
    page_title="폐국 관리 BI 시스템",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── 3. 커스텀 디자인 시스템 (Professional CSS) ──────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
    
    /* KPI Dashboard Card */
    .kpi-wrapper {
        background: white;
        padding: 24px;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .kpi-label { color: #64748B; font-size: 0.85rem; font-weight: 600; letter-spacing: -0.01em; margin-bottom: 8px; }
    .kpi-value { color: #0F172A; font-size: 1.85rem; font-weight: 800; line-height: 1; }
    .kpi-unit { font-size: 1rem; font-weight: 600; color: #94A3B8; margin-left: 4px; }
    .kpi-delta { font-size: 0.8rem; margin-top: 10px; display: flex; align-items: center; }
    
    /* Chart Tiles */
    .tile-container {
        background: white;
        padding: 24px;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        margin-bottom: 20px;
    }
    .tile-title { font-size: 1rem; font-weight: 700; color: #1E293B; margin-bottom: 4px; }
    .tile-subtitle { font-size: 0.8rem; color: #94A3B8; margin-bottom: 20px; }

    /* Data Table Styling */
    .stDataFrame { border: 1px solid #E2E8F0; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ── 4. 데이터 엔진 가동 ─────────────────────────────────────────
@st.cache_data(show_spinner="전사 실적 데이터를 집계 중입니다...")
def fetch_analytics_data(fhash):
    df_raw = load_raw(fhash)
    extra = load_extra()
    df = apply_extra(df_raw, extra)
    # 필터링: 정상 데이터 및 Pool 반영 데이터
    mask = (df.get("site_err", "정상") == "정상") & (df.get("pool_yn", "반영") == "반영")
    df_filtered = df[mask].copy()
    return calc_savings(df_filtered)

try:
    df_main = fetch_analytics_data(file_hash(MAIN_FILE))
    df_conf = df_main[df_main["off_month"].isin(CONFIRMED)]
except Exception as e:
    st.error(f"데이터 파이프라인 연결 오류: {e}")
    st.stop()

# ── 5. 사이드바 내비게이션 ──────────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='font-size:1.2rem;'>Asset Retirement BI</h2>", unsafe_allow_html=True)
    st.caption("Central Division Operations")
    st.divider()
    
    st.page_link("streamlit_app.py", label="실적 요약 대시보드", icon="📊")
    
    pool_path = "pages/1_후보_Pool_편집.py"
    if Path(pool_path).exists():
        st.page_link(pool_path, label="후보 Pool 관리", icon="⚙️")
        
    st.divider()
    if st.button("🔄 리프레시 데이터", width="stretch"):
        st.cache_data.clear()
        st.rerun()

# ── 6. KPI 섹션: 핵심 성과 지표 ────────────────────────────────
st.markdown("<h1 style='font-size:1.75rem; font-weight:800; color:#0F172A; margin-bottom:1.5rem;'>운영 실적 통합 리포트</h1>", unsafe_allow_html=True)

# 주요 지표 계산
total_count = len(df_conf)
rent_sav = round(df_conf["savings_ann"].sum() * 0.85 / 10000, 2)
elec_sav = round(df_conf["elec_ann"].sum() / 10000, 2)
achieve_rate = round(total_count / ANNUAL_GOAL * 100, 1)

k1, k2, k3, k4 = st.columns(4)

def render_kpi(col, label, value, unit, sub_text, color):
    with col:
        st.markdown(f"""
        <div class="kpi-wrapper">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}<span class="kpi-unit">{unit}</span></div>
            <div class="kpi-delta" style="color:{color}">● <span style="color:#64748B; margin-left:6px;">{sub_text}</span></div>
        </div>
        """, unsafe_allow_html=True)

render_kpi(k1, "누적 폐국 실적", str(total_count), "개소", f"연 목표 {ANNUAL_GOAL} 대비", "#1D4ED8")
render_kpi(k2, "임차 비용 절감", str(rent_sav), "억", "순절감(Net) 기준", "#10B981")
render_kpi(k3, "전력 비용 절감", str(elec_sav), "억", "연간 환산치", "#F59E0B")
render_kpi(k4, "종합 달성률", str(achieve_rate), "%", "연간 목표 이행도", "#8B5CF6")

st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)

# ── 7. 시각화 섹션 ───────────────────────────────────────────
t1, t2 = st.tabs(["📈 성과 분석 데이터", "📋 상세 현황 시트"])

with t1:
    c_left, c_right = st.columns([1.5, 1])
    
    with c_left:
        st.markdown('<div class="tile-container"><div class="tile-title">월별 목표 이행 트렌드</div><div class="tile-subtitle">실적 개소 및 누적 달성률 추이</div>', unsafe_allow_html=True)
        m_data = monthly_summary(df_main)
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        # 실적 Bar
        fig.add_trace(go.Bar(
            x=m_data["월"], y=m_data["실적"], 
            name="월별 실적", marker_color="#1D4ED8", opacity=0.7
        ), secondary_y=False)
        # 달성률 Line
        fig.add_trace(go.Scatter(
            x=m_data["월"], y=m_data["누계달성률"], 
            name="누계 달성률", line=dict(color="#10B981", width=3, shape='spline'),
            mode='lines+markers+text', text=[f"{v}%" for v in m_data["누계달성률"]],
            textposition="top center"
        ), secondary_y=True)
        
        fig.update_layout(
            height=320, margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            hovermode="x unified"
        )
        fig.update_yaxes(gridcolor="#F1F5F9", secondary_y=False)
        fig.update_yaxes(showgrid=False, range=[0, 100], secondary_y=True)
        
        st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        st.markdown('</div>', unsafe_allow_html=True)

    with c_right:
        st.markdown('<div class="tile-container"><div class="tile-title">사업 유형별 구성비</div><div class="tile-subtitle">사업 목적에 따른 폐국 분류</div>', unsafe_allow_html=True)
        biz_data = biz_type_summary(df_conf)
        
        fig_pie = go.Figure(data=[go.Pie(
            labels=biz_data["사업유형"], values=biz_data["건수"],
            hole=0.45, marker=dict(colors=["#1D4ED8", "#8B5CF6", "#14B8A6"]),
            textinfo='label+percent'
        )])
        fig_pie.update_layout(height=320, margin=dict(l=10, r=10, t=0, b=0), showlegend=False)
        st.plotly_chart(fig_pie, width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)

# ── 8. 상세 요약 데이터 테이블 ────────────────────────────────
with t2:
    st.markdown('<div class="tile-container"><div class="tile-title">월별 세부 분석 데이터</div><div style="height:10px"></div>', unsafe_allow_html=True)
    
    # calc.py에서 생성하는 요약 데이터 프레임 로드
    summary_df = monthly_summary(df_main)
    
    st.dataframe(
        summary_df,
        width="stretch",
        hide_index=True,
        column_config={
            "월": st.column_config.TextColumn("분석 월", width="small"),
            "실적": st.column_config.NumberColumn("폐국 건수", format="%d 건"),
            "누계달성률": st.column_config.ProgressColumn("연간 목표 달성률", min_value=0, max_value=100, format="%d%%"),
            "순절감": st.column_config.NumberColumn("순절감액(억)", format="%.2f 억"),
        }
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 추가적인 사업유형별 테이블 현황 (기존 app.py 로직 보완)
    st.markdown("##### 사업유형별 상세 지표")
    detailed_biz = biz_type_summary(df_conf)
    st.table(detailed_biz) # BI 스타일을 위해 깔끔한 기본 테이블 사용
    st.markdown('</div>', unsafe_allow_html=True)