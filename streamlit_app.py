"""
streamlit_app.py — 폐국 관리 시스템 v2 (Professional BI Edition)
작성일: 2026-04-18
"""
import sys
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── 1. 시스템 환경 및 유틸리티 로드 ────────────────────────────────
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

# ── 2. 페이지 구성 및 디자인 시스템 ───────────────────────────────
st.set_page_config(
    page_title="Asset Retirement BI — 04.중부",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 전문적인 UI 스타일링 (Slate & Indigo 테마)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
    
    /* Global Container */
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

    /* KPI Cards */
    .kpi-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        height: 100%;
    }
    .kpi-label { font-size: 0.75rem; color: #64748B; font-weight: 600; text-transform: uppercase; letter-spacing: 0.025em; margin-bottom: 8px; }
    .kpi-value { font-size: 1.75rem; color: #0F172A; font-weight: 700; line-height: 1; margin-bottom: 12px; }
    .kpi-sub { font-size: 0.8rem; color: #94A3B8; display: flex; align-items: center; gap: 4px; }
    .kpi-progress-bg { background: #F1F5F9; height: 6px; border-radius: 3px; margin-top: 12px; overflow: hidden; }
    .kpi-progress-fill { height: 100%; border-radius: 3px; transition: width 0.5s ease-in-out; }

    /* Chart & Table Cards */
    .content-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 1.5rem;
    }
    .card-title { font-size: 1rem; font-weight: 700; color: #1E293B; margin-bottom: 4px; }
    .card-subtitle { font-size: 0.8rem; color: #64748B; margin-bottom: 20px; }

    /* Custom Table */
    .bi-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    .bi-table thead th { background: #F8FAFC; padding: 12px 8px; border-bottom: 2px solid #E2E8F0; color: #475569; font-weight: 600; text-align: right; }
    .bi-table thead th:first-child { text-align: left; }
    .bi-table tbody td { padding: 12px 8px; border-bottom: 1px solid #F1F5F9; color: #334155; text-align: right; }
    .bi-table tbody td:first-child { text-align: left; font-weight: 600; }
    
    /* Badges */
    .badge { padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
    .badge-blue { background: #E0F2FE; color: #0369A1; }
    .badge-green { background: #DCFCE7; color: #15803D; }
    .badge-amber { background: #FEF3C7; color: #B45309; }
</style>
""", unsafe_allow_html=True)

# BI 컬러 팔레트 정의
COLORS = {
    "primary": "#2563EB", "success": "#10B981", "warning": "#F59E0B",
    "danger": "#EF4444", "slate": "#64748B", "grid": "rgba(226, 232, 240, 0.5)"
}

# ── 3. 데이터 엔진 ──────────────────────────────────────────────
@st.cache_data(show_spinner="분석 데이터를 연산 중입니다...")
def fetch_and_process_data(fhash):
    df_raw = load_raw(fhash)
    extra = load_extra()
    df = apply_extra(df_raw, extra)
    # 데이터 정제 (정상 사이트 & Pool 반영 건)
    mask = (df.get("site_err", "정상") == "정상") & (df.get("pool_yn", "반영") == "반영")
    df_pool = df[mask].copy()
    return calc_savings(df_pool)

try:
    df_pool = fetch_and_process_data(file_hash(MAIN_FILE))
    df_conf = df_pool[df_pool["off_month"].isin(CONFIRMED)]
except Exception as e:
    st.error(f"데이터 파이프라인 연동 실패: {e}")
    st.stop()

# ── 4. 사이드바 (내비게이션 및 필터) ──────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='font-size:1.2rem; color:#1E293B;'>Asset Management</h2>", unsafe_allow_html=True)
    st.caption("04.중부 본부 통합 관제")
    st.divider()
    
    st.markdown("**Navigation**")
    st.page_link("streamlit_app.py", label="실적 요약 대시보드", icon="📊")
    
    pool_file = "pages/1_후보_Pool_편집.py"
    if Path(pool_file).exists():
        st.page_link(pool_file, label="후보 Pool 관리", icon="⚙️")
        
    st.divider()
    st.markdown("**Analysis Scope**")
    MONTHS = ["1월", "2월", "3월", "4월", "5월", "6월"]
    selected_months = []
    for m in MONTHS:
        is_checked = (m in CONFIRMED or m == "4월")
        count = len(df_pool[df_pool["off_month"] == m])
        label = f"{m} ({count}건)" if count > 0 else m
        if st.checkbox(label, value=is_checked, key=f"filter_{m}"):
            selected_months.append(m)
            
    st.divider()
    if st.button("🔄 데이터 새로고침", width="stretch"):
        st.cache_data.clear()
        st.rerun()

# ── 5. 헤더 섹션 ────────────────────────────────────────────────
h_left, h_right = st.columns([3, 1])
with h_left:
    st.markdown("<h1 style='font-size:1.8rem; font-weight:800; color:#0F172A; margin-bottom:0.3rem;'>폐국 운영 실적 리포트</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#64748B;'>분석 대상: {', '.join(selected_months)} | 확정 상태: 1~3월 완료</p>", unsafe_allow_html=True)

# ── 6. KPI Dashboard ───────────────────────────────────────────
# 주요 지표 계산
total_count = len(df_conf)
rent_savings = round(df_conf["savings_ann"].sum() * 0.85 / 10000, 1)
elec_savings = round(df_conf["elec_ann"].sum() / 10000, 1)
achieve_rate = round(total_count / ANNUAL_GOAL * 100, 1)
voc_data = voc_summary(df_pool)
voc_pending = int(voc_data["미처리누계"].iloc[-1]) if not voc_data.empty else 0

def render_kpi_card(label, value, unit, sub_text, progress, color):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}<span style="font-size:1rem; color:#94A3B8; margin-left:4px;">{unit}</span></div>
        <div class="kpi-sub"><span>{sub_text}</span></div>
        <div class="kpi-progress-bg">
            <div class="kpi-progress-fill" style="width:{min(progress, 100)}%; background:{color};"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

k_cols = st.columns(5)
with k_cols[0]: render_kpi_card("누적 폐국 실적", str(total_count), "개소", f"목표 {ANNUAL_GOAL}개 대비", achieve_rate, COLORS["primary"])
with k_cols[1]: render_kpi_card("임차 비용 절감", str(rent_savings), "억", "연간 순절감액", 75, COLORS["success"])
with k_cols[2]: render_kpi_card("전력 비용 절감", str(elec_savings), "억", "연간 순절감액", 45, COLORS["success"])
with k_cols[3]: render_kpi_card("VoC 미처리 현황", str(voc_pending), "건", "실시간 대응 필요", (voc_pending*10) if voc_pending < 10 else 100, COLORS["danger"])
with k_cols[4]: render_kpi_card("목표 달성률", str(achieve_rate), "%", "연간 목표 이행도", achieve_rate, COLORS["warning"])

st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)

# ── 7. Main Analytics (Charts) ─────────────────────────────────
tab_summary, tab_detail = st.tabs(["📊 성과 분석 차트", "📋 세부 데이터 시트"])

with tab_summary:
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown('<div class="content-card"><div class="card-title">월별 목표 이행 트렌드</div><div class="card-subtitle">실적 및 누적 달성률 추이</div>', unsafe_allow_html=True)
        m_sum = monthly_summary(df_pool)
        
        fig_trend = make_subplots(specs=[[{"secondary_y": True}]])
        fig_trend.add_trace(go.Bar(x=m_sum["월"], y=m_sum["실적"], name="월 실적", marker_color=COLORS["primary"], opacity=0.8), secondary_y=False)
        fig_trend.add_trace(go.Scatter(x=m_sum["월"], y=m_sum["누계달성률"], name="누계 달성률", line=dict(color=COLORS["success"], width=3, shape='spline'), mode='lines+markers+text', text=[f"{v}%" for v in m_sum["누계달성률"]], textposition="top center"), secondary_y=True)
        
        fig_trend.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        fig_trend.update_yaxes(gridcolor=COLORS["grid"], secondary_y=False)
        fig_trend.update_yaxes(showgrid=False, range=[0, 120], secondary_y=True)
        st.plotly_chart(fig_trend, width="stretch", config={'displayModeBar': False})
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="content-card"><div class="card-title">사업 유형별 비중</div><div class="card-subtitle">사업 유형 및 절감 방식 분포</div>', unsafe_allow_html=True)
        biz_data = biz_type_summary(df_conf)
        
        fig_pie = go.Figure(data=[go.Pie(labels=biz_data["사업유형"], values=biz_data["건수"], hole=0.5, marker=dict(colors=[COLORS["primary"], "#8B5CF6", "#14B8A6"]))])
        fig_pie.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5))
        st.plotly_chart(fig_pie, width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)

# ── 8. Detailed Report (Table) ──────────────────────────────────
with tab_detail:
    st.markdown('<div class="content-card"><div class="card-title">월별 실적 상세 현황</div><div style="height:15px"></div>', unsafe_allow_html=True)
    
    # 데이터 전처리: 테이블용 포맷팅
    m_report = m_sum.copy()
    
    # HTML 테이블 생성
    headers = ["월", "실적(건)", "누계(건)", "달성률", "임차+전기", "전기만", "순절감(억)", "상태"]
    rows_html = ""
    for _, row in m_report.iterrows():
        status_cls = "badge-green" if row["상태"] == "확정" else "badge-amber"
        rows_html += f"""
        <tr>
            <td>{row['월']}</td>
            <td>{row['실적']}</td>
            <td>{row['누계']}</td>
            <td style="color:{COLORS['primary']}; font-weight:700;">{row['누계달성률']}%</td>
            <td>{row['임차+전기']}</td>
            <td>{row['전기만']}</td>
            <td style="color:{COLORS['success']}; font-weight:700;">{row['순절감']}억</td>
            <td><span class="badge {status_cls}">{row['상태']}</span></td>
        </tr>
        """
    
    st.markdown(f"""
    <table class="bi-table">
        <thead><tr>{"".join([f"<th>{h}</th>" for h in headers])}</tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 사업유형별 BEP 분석 섹션 추가
    st.markdown("##### 📌 사업유형별 투자 수익성(BEP) 분석")
    st.dataframe(
        biz_data[['사업유형', '건수', '임차료절감', '순절감', '평균BEP']],
        width="stretch",
        hide_index=True,
        column_config={
            "평균BEP": st.column_config.NumberColumn("평균 BEP (개월)", format="%d 개월"),
            "순절감": st.column_config.NumberColumn("순절감 (억)", format="%.2f 억")
        }
    )