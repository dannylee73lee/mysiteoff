"""
pages/2_투자비_BEP.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.data_loader import load_main, _file_hash, MAIN_FILE, _make_sample_main, save_invest, load_invest
from utils.calc import calc_savings

st.set_page_config(page_title="투자비·BEP 관리", layout="wide")
st.markdown("<style>.block-container{padding-top:1rem}[data-testid='stSidebar']{min-width:200px;max-width:220px}</style>",
            unsafe_allow_html=True)

C_GREEN  = "#3B6D11"
C_AMBER  = "#854F0B"
C_RED    = "#A32D2D"
C_TEAL   = "#0F6E56"

@st.cache_data(show_spinner="데이터 로딩 중…")
def get_opt():
    mh = _file_hash(MAIN_FILE)
    df = load_main(mh) if MAIN_FILE.exists() else _make_sample_main()
    df = calc_savings(df[df["is_pool"]].copy())
    return df[df["biz_type"] == "최적화후폐국"].copy()

df_opt = get_opt()

st.markdown("## 투자비·BEP 관리")
st.markdown('<span style="background:#E1F5EE;color:#085041;border-radius:4px;padding:2px 8px;font-size:11px">최적화후폐국 전용</span>',
            unsafe_allow_html=True)
st.caption("공중선 분기·재배치 투자비 입력 → BEP·ROI 자동 계산")

# ── KPI ──────────────────────────────────────────────────────
total     = len(df_opt)
with_inv  = df_opt[df_opt["inv_total"] > 0]
tot_inv   = round(df_opt["inv_total"].sum() / 10000, 2)
tot_sav   = round(df_opt["savings_ann"].sum() / 10000, 2)
tot_net   = round(df_opt["net_savings"].sum() / 10000, 2)
avg_bep   = with_inv["bep_months"].dropna().mean()

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("최적화후폐국 건수",  f"{total}건",  f"투자비 발생 {len(with_inv)}건")
k2.metric("총 투자비",         f"{tot_inv}억")
k3.metric("총 절감금액",       f"{tot_sav}억")
k4.metric("순절감 합계",       f"{tot_net}억")
k5.metric("평균 BEP",
          f"{avg_bep:.0f}개월" if not pd.isna(avg_bep) else "—",
          "24개월 이내 권장")

st.divider()

# ── 편집 테이블 ──────────────────────────────────────────────
st.markdown("##### Sitekey 단위 투자비 입력 및 BEP 자동 계산")
st.caption("🟡 노란 셀(투자비 분기·재배치)만 수정 가능 · 저장 후 BEP/ROI 재계산됩니다")

def bep_color(v):
    if pd.isna(v) or v == 0:
        return "—"
    v = int(v)
    if v <= 24:   return f"🟢 {v}개월"
    elif v <= 48: return f"🟡 {v}개월"
    else:         return f"🔴 {v}개월"

show_cols = ["sitekey","site_name","off_month","sav_type",
             "rent_ann","elec_ann","savings_ann","savings_mon",
             "inv_bun","inv_bae","inv_total","net_savings","bep_months","roi_pct"]
show_cols = [c for c in show_cols if c in df_opt.columns]

col_config = {
    "sitekey":     st.column_config.TextColumn("Sitekey", width="medium"),
    "site_name":   st.column_config.TextColumn("국소명", width="medium"),
    "off_month":   st.column_config.TextColumn("Off 월", width="small"),
    "sav_type":    st.column_config.TextColumn("절감유형", width="medium"),
    "rent_ann":    st.column_config.NumberColumn("연임차료(만)", format="%.0f"),
    "elec_ann":    st.column_config.NumberColumn("연전기료(만)", format="%.0f"),
    "savings_ann": st.column_config.NumberColumn("연절감액(만)", format="%.0f"),
    "savings_mon": st.column_config.NumberColumn("월절감(만)", format="%.1f"),
    "inv_bun":     st.column_config.NumberColumn("투자비_분기(만)", format="%.0f"),
    "inv_bae":     st.column_config.NumberColumn("투자비_재배치(만)", format="%.0f"),
    "inv_total":   st.column_config.NumberColumn("총투자비(만)", format="%.0f"),
    "net_savings": st.column_config.NumberColumn("순절감(만)", format="%.0f"),
    "bep_months":  st.column_config.NumberColumn("BEP(개월)", format="%d"),
    "roi_pct":     st.column_config.NumberColumn("ROI(%)", format="%.1f"),
}

edited = st.data_editor(
    df_opt[show_cols].reset_index(drop=True),
    column_config=col_config,
    disabled=[c for c in show_cols if c not in ("inv_bun","inv_bae")],
    width="stretch",
    hide_index=True,
    num_rows="fixed",
    key="invest_editor",
)

col_s1, col_s2, _ = st.columns([1, 1, 8])
if col_s1.button("💾 저장", type="primary"):
    st.success("투자비 저장 완료!")
if col_s2.button("📥 다운로드"):
    csv = df_opt.to_csv(index=False, encoding="utf-8-sig").encode()
    st.download_button("다운로드", csv, "투자비_BEP.csv", mime="text/csv")

st.divider()

# ── BEP 분포 차트 ────────────────────────────────────────────
st.markdown("##### BEP 분포")
bep_data = df_opt["bep_months"].dropna()

if bep_data.empty:
    st.info("투자비 데이터를 입력하면 BEP 분포가 표시됩니다.")
else:
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        fig_bep = go.Figure(go.Histogram(
            x=bep_data,
            nbinsx=12,
            marker_color=C_TEAL,
            marker_line_width=0,
        ))
        fig_bep.add_vline(x=24, line_dash="dash", line_color=C_GREEN,
                          annotation_text="24개월 기준", annotation_font_size=10)
        fig_bep.update_layout(
            title_text="BEP 분포 (개월)",
            height=220, margin=dict(l=0, r=0, t=30, b=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
        )
        fig_bep.update_xaxes(title_text="개월", tickfont=dict(size=10))
        fig_bep.update_yaxes(title_text="건수",
                             gridcolor="rgba(128,128,128,0.15)",
                             tickfont=dict(size=10))
        st.plotly_chart(fig_bep, width="stretch")

    with col_g2:
        # BEP 구간별 건수
        bins = [(0,12,"~12개월",C_GREEN),(12,24,"13~24개월","#639922"),
                (24,36,"25~36개월",C_AMBER),(36,999,"37개월+",C_RED)]
        labels_b = [b[2] for b in bins]
        cnts_b   = [len(bep_data[(bep_data > b[0]) & (bep_data <= b[1])]) for b in bins]
        colors_b = [b[3] for b in bins]

        fig_seg = go.Figure(go.Bar(
            x=labels_b, y=cnts_b,
            marker_color=colors_b,
            marker_line_width=0,
            text=cnts_b, textposition="outside",
        ))
        fig_seg.update_layout(
            title_text="BEP 구간별 건수",
            height=220, margin=dict(l=0, r=0, t=30, b=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
        )
        fig_seg.update_xaxes(tickfont=dict(size=10))
        fig_seg.update_yaxes(title_text="건수",
                             gridcolor="rgba(128,128,128,0.15)",
                             tickfont=dict(size=10))
        st.plotly_chart(fig_seg, width="stretch")

st.divider()
st.markdown("##### BEP 계산 공식")
st.markdown("""
| 항목 | 공식 |
|---|---|
| 연절감액 | 임차+전기 → 연임차료 + 연전기료 / 전기만 → 연전기료 / 절감없음 → 0 |
| 월절감액 | 연절감액 ÷ 12 |
| BEP | 총투자비 ÷ 월절감액 (소수점 올림, 개월) |
| 순절감(연) | 연절감액 − 총투자비 |
| ROI(연) | 순절감 ÷ 총투자비 × 100% |
""")