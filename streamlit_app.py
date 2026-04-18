"""
app.py — 폐국 관리 시스템 · 메인 현황 (UX/UI 최적화 버전)
실행: streamlit run app.py
"""
import sys
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 기존 모듈 경로 유지
sys.path.insert(0, str(Path(__file__).parent))
from utils.data_loader import (
    load_raw, file_hash, apply_extra, load_extra, MAIN_FILE, RENT_FILE,
)
from utils.calc import (
    calc_savings, monthly_summary, biz_type_summary,
    equipment_summary, voc_summary, ANNUAL_GOAL, CONFIRMED,
)

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="폐국 관리 시스템 | 04.중부",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. 전문가급 UI를 위한 Custom CSS
st.markdown("""
<style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }

    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 95rem; }
    
    /* KPI 카드 디자인 */
    .kpi-card {
        background: #ffffff;
        border: 1px solid #F0F2F6;
        border-radius: 12px;
        padding: 22px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .kpi-card:hover { 
        transform: translateY(-3px); 
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05);
        border-color: #e2e8f0;
    }
    .kpi-label { font-size: 0.85rem; color: #64748b; font-weight: 600; margin-bottom: 10px; }
    .kpi-value { font-size: 2rem; font-weight: 800; color: #1e293b; letter-spacing: -0.03em; line-height: 1; }
    .kpi-sub { font-size: 0.75rem; color: #94a3b8; margin-top: 6px; font-weight: 400; }
    
    /* 차트 컨테이너 */
    .chart-container {
        background: white;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #f1f5f9;
        margin-bottom: 1rem;
    }

    /* 테이블 헤더 커스텀 */
    thead tr th {
        background-color: #f8fafc !important;
        color: #475569 !important;
        font-size: 12px !important;
        padding: 12px !important;
    }
    
    /* 탭 스타일 조정 */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        background-color: #f8fafc;
        border-radius: 8px 8px 0 0;
        gap: 1px;
        padding-top: 10px;
        white-space: pre-wrap;
    }
    .stTabs [aria-selected="true"] { background-color: #eff6ff !important; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# 색상 팔레트 정의
C = dict(blue="#2563eb", green="#10b981", amber="#f59e0b", 
        red="#ef4444", purple="#8b5cf6", teal="#14b8a6", gray="#94a3b8")
BIZ_C = {"단순폐국": C["blue"], "이설후폐국": C["purple"], "최적화후폐국": C["teal"]}
SAV_C = {"임차+전기": C["green"], "전기만": C["amber"], "절감없음": C["gray"]}

# 3. 데이터 로딩 함수
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

df_pool = get_data(file_hash(MAIN_FILE))
df_conf = df_pool[df_pool["off_month"].isin(CONFIRMED)]

# 4. 사이드바 구성
with st.sidebar:
    st.markdown("### 📡 폐국 관리 시스템")
    st.caption("Central Division Dashboard v2.0")
    st.divider()

    st.markdown("**📍 본부 선택**")
    st.info("🏢 **04. 중부 본부**")
    
    st.divider()
    st.markdown("**📅 Off 월 필터**")
    MONTH_ORDER = ["1월","2월","3월","4월","5월","6월"]
    MON_STATUS  = {m: ("✅" if m in CONFIRMED else ("🔄" if m=="4월" else "⏳")) for m in MONTH_ORDER}
    sel_months = []
    for m in MONTH_ORDER:
        cnt = len(df_pool[df_pool["off_month"] == m])
        lbl = f"{MON_STATUS[m]} {m} ({cnt}건)"
        if st.checkbox(lbl, value=(m in CONFIRMED or m=="4월"), key="m_"+m):
            sel_months.append(m)

    st.divider()
    if st.button("🔄 데이터 강제 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# 5. KPI 데이터 계산
total_conf = len(df_conf)
rent_conf  = round(df_conf["savings_ann"].sum() * 0.85 / 10000, 1)
elec_conf  = round(df_conf["elec_ann"].sum() / 10000, 1)
pct_conf   = round(total_conf / ANNUAL_GOAL * 100, 1)
voc_df     = voc_summary(df_pool)
voc_issued = int(voc_df["발생"].sum()) if not voc_df.empty else 0
voc_open   = int(voc_df["미처리누계"].iloc[-1]) if not voc_df.empty else 0
eq_data    = equipment_summary(df_pool)
eq_total   = sum(sum(v.values()) for v in eq_data.values())

# 6. 상단 헤더 섹션
h1, h2 = st.columns([4, 1])
with h1:
    st.title("📊 메인 현황 분석")
    st.markdown(f"**04.중부** | 1~3월 확정 실적 및 4월 검토 현황을 포함합니다.")
with h2:
    st.markdown("<div style='padding-top:28px'></div>", unsafe_allow_html=True)
    st.button("💾 보고서 내보내기", use_container_width=True)

# 7. KPI 카드 렌더링
def kpi_card(label, value, sub, bar_pct, color):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value" style="color:{color}">{value}</div>
        <div class="kpi-sub">{sub}</div>
        <div style="background:#f1f5f9; height:5px; border-radius:10px; margin-top:15px;">
            <div style="background:{color}; width:{min(bar_pct, 100)}%; height:100%; border-radius:10px;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

k1, k2, k3, k4, k5 = st.columns(5)
with k1: kpi_card("누적 폐국 실적", f"{total_conf}건", f"연간 목표 대비 {pct_conf}%", pct_conf, C["blue"])
with k2: kpi_card("임차 절감액", f"{rent_conf}억", "확정분 순절감 기준", 70, C["green"])
with k3: kpi_card("전기 절감액", f"{elec_conf}억", "확정분 순절감 기준", 45, C["amber"])
with k4: kpi_card("미처리 VoC", f"{voc_open}건", f"총 발생 {voc_issued}건 중", (voc_open/voc_issued*100 if voc_issued else 0), C["red"])
with k5: kpi_card("철거 장비 누계", f"{eq_total}대", "1~3월 장비 철거량", 60, C["teal"])

st.markdown("<div style='margin-bottom:20px'></div>", unsafe_allow_html=True)

# 8. 메인 상세 분석 (Tabs)
tab1, tab2, tab3 = st.tabs(["📈 시각화 대시보드", "📋 월별 상세 현황", "🏢 사업 유형별 분석"])

# --- Tab 1: 시각화 분석 ---
with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🏁 목표 대비 실적 추이")
        m_sum = monthly_summary(df_pool)
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Bar(x=m_sum["월"], y=m_sum["실적"], name="월 실적", marker_color=C["blue"]), secondary_y=False)
        fig1.add_trace(go.Scatter(x=m_sum["월"], y=m_sum["누계달성률"], name="누계 달성률", 
                                line=dict(color=C["green"], width=3), marker=dict(size=8)), secondary_y=True)
        fig1.update_layout(height=350, margin=dict(l=0,r=0,t=30,b=0), hovermode="x unified",
                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
        fig1.update_yaxes(gridcolor="#f1f5f9")
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        st.markdown("#### 💰 절감 실적 구성 (억)")
        conf_m = ["1월","2월","3월"]
        rent_m = [round(df_pool[df_pool["off_month"]==m]["savings_ann"].sum()*0.85/10000, 2) for m in conf_m]
        elec_m = [round(df_pool[df_pool["off_month"]==m]["elec_ann"].sum()/10000, 2) for m in conf_m]
        
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=conf_m, y=rent_m, name="임차료", marker_color=C["green"]))
        fig2.add_trace(go.Bar(x=conf_m, y=elec_m, name="전기료", marker_color=C["amber"]))
        fig2.update_layout(height=350, barmode="stack", margin=dict(l=0,r=0,t=30,b=0),
                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig2, use_container_width=True)

# --- Tab 2: 상세 현황 표 ---
with tab2:
    st.markdown("#### 월별 상세 데이터")
    m_sum_table = monthly_summary(df_pool)
    
    # 가독성을 높인 데이터 프레임 출력
    st.dataframe(
        m_sum_table,
        column_config={
            "실적": st.column_config.NumberColumn(format="%d 건"),
            "누계달성률": st.column_config.ProgressColumn(min_value=0, max_value=120, format="%.1f%%"),
            "순절감": st.column_config.NumberColumn(format="%.1f 억"),
            "상태": st.column_config.TextColumn()
        },
        use_container_width=True,
        hide_index=True
    )

# --- Tab 3: 사업 유형별 분석 ---
with tab3:
    bs = biz_type_summary(df_conf)
    ta1, ta2 = st.columns([3, 2])
    
    with ta1:
        st.markdown("#### 사업유형 × 절감유형")
        fig_a1 = go.Figure()
        for sav, color in SAV_C.items():
            fig_a1.add_trace(go.Bar(name=sav, x=bs["사업유형"], y=bs[sav], marker_color=color))
        fig_a1.update_layout(height=350, barmode="stack", margin=dict(l=0,r=0,t=30,b=0),
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
        st.plotly_chart(fig_a1, use_container_width=True)

    with ta2:
        st.markdown("#### 유형별 임차료 절감액")
        fig_a2 = go.Figure(go.Bar(
            x=bs["임차료절감"], y=bs["사업유형"], orientation="h",
            marker_color=[BIZ_C.get(b, C["gray"]) for b in bs["사업유형"]],
            text=bs["임차료절감"].apply(lambda x: f"{x}억"), textposition="outside"
        ))
        fig_a2.update_layout(height=350, margin=dict(l=0,r=50,t=30,b=0))
        st.plotly_chart(fig_a2, use_container_width=True)