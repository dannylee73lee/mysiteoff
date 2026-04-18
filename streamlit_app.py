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

# ── 1. 경로 및 데이터 로더 설정 ──────────────────────────────────
# 현재 파일의 위치를 기준으로 시스템 경로 추가
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
    initial_sidebar_state="expanded",
)

# ── 3. 전문적인 BI 스타일링 (CSS) ──────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #F4F7F9; }
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }

    /* KPI 카드 디자인 */
    .kpi-card {
        background-color: #FFFFFF;
        border-radius: 12px;
        padding: 22px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border: 1px solid #E2E8F0;
        transition: transform 0.2s;
    }
    .kpi-card:hover { transform: translateY(-3px); }
    .kpi-label { font-size: 13px; color: #64748B; font-weight: 600; margin-bottom: 8px; }
    .kpi-value { font-size: 30px; font-weight: 800; color: #0F172A; margin-bottom: 4px; }
    .kpi-unit { font-size: 16px; font-weight: 600; margin-left: 2px; }
    .kpi-sub { font-size: 12px; color: #94A3B8; margin-bottom: 12px; }
    
    .kpi-bar-bg { height: 6px; border-radius: 3px; background-color: #F1F5F9; }
    .kpi-bar-fill { height: 6px; border-radius: 3px; }

    /* 차트 컨테이너 */
    .chart-card {
        background-color: #FFFFFF;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .chart-title { font-size: 16px; font-weight: 700; color: #1E293B; margin-bottom: 4px; }
    .chart-sub { font-size: 13px; color: #94A3B8; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# ── 4. 전역 색상 설정 ─────────────────────────────────────────
C = {
    "blue": "#1D4ED8",
    "green": "#10B981",
    "amber": "#F59E0B",
    "red": "#EF4444",
    "purple": "#8B5CF6",
    "teal": "#14B8A6",
    "gray": "#94A3B8",
    "grid": "#F1F5F9"
}

# ── 5. 데이터 로딩 및 처리 ─────────────────────────────────────
@st.cache_data(show_spinner="데이터를 구성 중입니다...")
def get_processed_data(fhash):
    df_raw = load_raw(fhash)
    extra = load_extra()
    df = apply_extra(df_raw, extra)
    df_pool = df[
        (df.get("site_err", pd.Series("정상", index=df.index)) == "정상") &
        (df.get("pool_yn",  pd.Series("반영",  index=df.index)) == "반영")
    ].copy()
    return calc_savings(df_pool)

try:
    df_pool = get_processed_data(file_hash(MAIN_FILE))
except Exception as e:
    st.error(f"데이터 로딩 실패: {e}")
    st.stop()

df_conf = df_pool[df_pool["off_month"].isin(CONFIRMED)]

# ── 6. 사이드바 구성 (에러 수정됨) ───────────────────────────────
with st.sidebar:
    st.markdown("### 📡 폐국 관리 시스템")
    st.markdown("**04.중부 본부**")
    st.divider()
    
    # st.page_link 오류 수정: 메인 페이지는 "app.py" 대신 "app.py"의 파일 이름이나 "/" 경로를 사용
    st.page_link("app.py", label="📊 실적 대시보드", icon="📈")
    
    # pages 폴더 내 파일 경로 확인 필요 (파일명이 다르면 수정하세요)
    try:
        st.page_link("pages/1_후보_Pool_편집.py", label="📋 후보 Pool 편집", icon="📝")
    except:
        st.caption("⚠️ 후보 Pool 편집 페이지를 찾을 수 없습니다.")
        
    st.divider()
    if st.button("🔄 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── 7. KPI 카드 영역 ──────────────────────────────────────────
st.markdown('<div style="font-size:24px; font-weight:800; color:#0F172A; margin-bottom:20px;">중부 본부 폐국 운영 현황</div>', unsafe_allow_html=True)

total_conf = len(df_conf)
rent_conf  = round(df_conf["savings_ann"].sum() * 0.85 / 10000, 1)
elec_conf  = round(df_conf["elec_ann"].sum() / 10000, 1)
pct_conf   = round(total_conf / ANNUAL_GOAL * 100, 1)
voc_df     = voc_summary(df_pool)
voc_open   = int(voc_df["미처리누계"].iloc[-1]) if not voc_df.empty else 0

def draw_kpi(label, value, unit, sub, progress, color):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}<span class="kpi-unit">{unit}</span></div>
        <div class="kpi-sub">{sub}</div>
        <div class="kpi-bar-bg">
            <div class="kpi-bar-fill" style="width:{min(progress, 100)}%; background-color:{color}"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
with k1: draw_kpi("누계 실적 (1~3월)", str(total_conf), "개소", f"목표 대비 {pct_conf}% 달성", pct_conf, C["blue"])
with k2: draw_kpi("임차료 절감", str(rent_conf), "억", "연간 순절감액 기준", 75, C["green"])
with k3: draw_kpi("전기료 절감", str(elec_conf), "억", "연간 순절감액 기준", 40, C["amber"])
with k4: draw_kpi("VoC 미처리", str(voc_open), "건", "발생 건수 대비 관리", 20, C["red"])

st.markdown("<div style='height:15px'></div>", unsafe_allow_html=True)

# ── 8. 메인 차트 영역 ─────────────────────────────────────────
tab1, tab2 = st.tabs(["📊 통합 리포트", "📅 월별 데이터 시트"])

with tab1:
    col_l, col_r = st.columns(2)
    
    with col_l:
        st.markdown('<div class="chart-card"><div class="chart-title">목표 대비 실적 추이</div><div class="chart-sub">월별 폐국 실적 및 목표 달성률(%)</div>', unsafe_allow_html=True)
        m_sum = monthly_summary(df_pool)
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig1.add_trace(go.Bar(
            x=m_sum["월"], y=m_sum["실적"], 
            name="실적", marker_color=C["blue"], opacity=0.8
        ), secondary_y=False)
        
        fig1.add_trace(go.Scatter(
            x=m_sum["월"], y=m_sum["누계달성률"],
            name="달성률", mode="lines+markers+text",
            line=dict(color=C["green"], width=3),
            marker=dict(size=8, color="white", line=dict(color=C["green"], width=2)),
            text=[f"{int(v)}%" if v > 0 else "" for v in m_sum["누계달성률"]],
            textposition="top center",
            textfont=dict(size=11, color=C["green"]) # weight 속성 제거 (Plotly 하위버전 호환성)
        ), secondary_y=True)

        fig1.update_layout(
            height=300, margin=dict(l=0, r=0, t=20, b=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            hovermode="x unified", showlegend=False
        )
        fig1.update_xaxes(gridcolor=C["grid"])
        fig1.update_yaxes(gridcolor=C["grid"], secondary_y=False)
        fig1.update_yaxes(showgrid=False, range=[0, 150], secondary_y=True)
        
        st.plotly_chart(fig1, use_container_width=True, config={'displayModeBar': False})
        st.markdown('</div>', unsafe_allow_html=True)

    with col_r:
        st.markdown('<div class="chart-card"><div class="chart-title">사업유형별 비중</div><div class="chart-sub">확정 폐국(1~3월) 기준 사업유형 분포</div>', unsafe_allow_html=True)
        bs = biz_type_summary(df_conf)
        fig2 = go.Figure(data=[go.Pie(
            labels=bs["사업유형"], values=bs["건수"], 
            hole=.5,
            marker=dict(colors=[C["blue"], C["purple"], C["teal"]]),
            textinfo='percent+label'
        )])
        fig2.update_layout(height=300, margin=dict(l=10, r=10, t=20, b=10), showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-title">월별 세부 실적 지표</div><div style="height:10px"></div>', unsafe_allow_html=True)
    
    st.dataframe(
        monthly_summary(df_pool),
        use_container_width=True,
        hide_index=True,
        column_config={
            "월": st.column_config.TextColumn("분석 월"),
            "실적": st.column_config.NumberColumn("폐국 실적", format="%d 건"),
            "누계달성률": st.column_config.ProgressColumn("달성률", min_value=0, max_value=100, format="%d%%"),
            "순절감": st.column_config.NumberColumn("연 순절감", format="%.2f 억"),
            "상태": st.column_config.SelectboxColumn("진행 상태", options=["확정", "검토중", "예정"])
        }
    )
    st.markdown('</div>', unsafe_allow_html=True)