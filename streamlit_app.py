"""
app.py — 폐국 관리 시스템 · 메인 현황  (UI v3)
실행: streamlit run app.py
"""
import sys
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parent))
from utils.data_loader import (
    load_raw, enrich_rent, apply_extra, load_extra,
    file_hash, MAIN_FILES, RENT_FILE,
    HONBU_ORDER, MONTH_ORDER, CONFIRMED, REVIEW,
    DEFAULT_HONBU, _make_sample,
)
from utils.calc import (
    calc_savings, monthly_summary, biz_type_summary,
    equipment_summary, voc_summary,
    HONBU_GOAL, ANNUAL_GOAL, CONFIRMED,
)

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="폐국 관리",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif}
.block-container{padding:0.75rem 1.5rem 1.5rem;max-width:100%}
[data-testid="stSidebar"]{min-width:200px;max-width:215px}
[data-testid="stSidebar"]>div:first-child{
    background:var(--background-color);
    border-right:1px solid rgba(128,128,128,0.12)}
.kpi-tile{
    background:var(--background-color);
    border:1px solid rgba(128,128,128,0.13);
    border-radius:12px;padding:16px 18px 14px;
    position:relative;overflow:hidden;transition:box-shadow 0.2s}
.kpi-tile:hover{box-shadow:0 4px 16px rgba(0,0,0,0.07)}
.kpi-accent{position:absolute;top:0;left:0;width:4px;height:100%;border-radius:12px 0 0 12px}
.kpi-label{font-size:10px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;opacity:.45;margin-bottom:6px}
.kpi-value{font-size:28px;font-weight:700;line-height:1;margin-bottom:4px;letter-spacing:-0.5px}
.kpi-sub{font-size:10px;opacity:.4;margin-bottom:10px}
.kpi-track{height:3px;border-radius:2px;background:rgba(128,128,128,0.12);overflow:hidden}
.kpi-fill{height:3px;border-radius:2px}
.chart-tile{
    background:var(--background-color);
    border:1px solid rgba(128,128,128,0.13);
    border-radius:12px;padding:18px 20px 12px;margin-bottom:14px}
.tile-title{font-size:13px;font-weight:600;letter-spacing:-0.1px}
.tile-sub{font-size:11px;opacity:.4;margin-top:1px}
.tile-legend{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.leg{display:flex;align-items:center;gap:5px;font-size:10px;opacity:.6}
.leg-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.leg-line{width:16px;height:2.5px;border-radius:2px;flex-shrink:0}
.leg-dash{width:16px;height:0;border-top:2px dashed;flex-shrink:0}
.stat-row{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 6px}
.stat-chip{
    display:inline-flex;align-items:center;gap:4px;
    font-size:11px;padding:4px 10px;border-radius:20px;
    background:rgba(128,128,128,0.07);
    border:1px solid rgba(128,128,128,0.10);white-space:nowrap}
.stat-chip .lbl{opacity:.5;font-weight:400}
.stat-chip .val{font-weight:600}
.badge{display:inline-block;border-radius:5px;padding:2px 9px;font-size:11px;font-weight:500}
.bi-table{width:100%;border-collapse:collapse;font-size:11px}
.bi-table th{
    font-size:10px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;
    opacity:.45;padding:8px 10px;border-bottom:1px solid rgba(128,128,128,0.12);
    background:rgba(128,128,128,0.04)}
.bi-table td{padding:8px 10px;border-bottom:1px solid rgba(128,128,128,0.07);vertical-align:middle}
.bi-table tr:last-child td{border-bottom:none}
.bi-table tr:hover td{background:rgba(128,128,128,0.03)}
.stTabs [data-baseweb="tab-list"]{gap:0;border-bottom:1px solid rgba(128,128,128,0.15)}
.stTabs [data-baseweb="tab"]{padding:8px 18px;font-size:12px;font-weight:500;border-bottom:2px solid transparent}
.stTabs [aria-selected="true"]{border-bottom:2px solid #1A6FC4}
#MainMenu,footer,header{visibility:hidden}
</style>
""", unsafe_allow_html=True)

# ── 색상 팔레트 ──────────────────────────────────────────────
C = dict(
    blue="#1A6FC4", green="#2D7D46", amber="#B45309",
    red="#C0392B",  purple="#5B4DA0", teal="#0E7490", gray="#6B7280",
    blue_l="#EFF6FF", green_l="#F0FDF4", red_l="#FEF2F2",
    amber_l="#FFFBEB", teal_l="#F0FDFA",
)
HONBU_COLOR = {
    "수도권":  C["blue"],  "04.중부": C["green"],
    "동부":    C["amber"], "서부":    C["purple"],
}
BIZ_C = {"단순폐국":C["blue"],"이설후폐국":C["purple"],"최적화후폐국":C["teal"]}
SAV_C = {"임차+전기":C["green"],"전기만":C["amber"],"절감없음":C["gray"]}
def hex_rgba(hex_color: str, alpha: float = 0.08) -> str:
    """#RRGGBB → rgba(r,g,b,a)"""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    return "rgba({},{},{},{})".format(r, g, b, alpha)

GC    = "rgba(128,128,128,0.07)"

# ── 공통 Plotly 설정 ─────────────────────────────────────────
def base_layout(**kw):
    d = dict(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
             showlegend=False, margin=dict(l=2,r=8,t=6,b=2),
             font=dict(family="Inter,sans-serif",size=10),
             hoverlabel=dict(bgcolor="white",bordercolor=GC,font=dict(size=11,family="Inter")))
    d.update(kw); return d

def sx(**kw):
    d = dict(tickfont=dict(size=10,color="#9CA3AF"),gridcolor=GC,
             linecolor="rgba(128,128,128,0.15)",showline=True,zeroline=False)
    d.update(kw); return d

def sy(**kw):
    d = dict(tickfont=dict(size=10,color="#9CA3AF"),gridcolor=GC,zeroline=False)
    d.update(kw); return d

# ── HTML 헬퍼 ────────────────────────────────────────────────
def kpi_tile(label, value, sub, pct, color, color_l="transparent"):
    pct = min(max(float(pct),0),100)
    return (
        '<div class="kpi-tile" style="background:{bg}">'
        '<div class="kpi-accent" style="background:{c}"></div>'
        '<div style="padding-left:6px">'
        '<div class="kpi-label">{lbl}</div>'
        '<div class="kpi-value" style="color:{c}">{val}</div>'
        '<div class="kpi-sub">{sub}</div>'
        '<div class="kpi-track"><div class="kpi-fill" style="width:{pct}%;background:{c}"></div></div>'
        '</div></div>'
    ).format(bg=color_l, c=color, lbl=label, val=value, sub=sub, pct=pct)

def leg(color, label, style="dot"):
    if style=="line":  shape='<span class="leg-line" style="background:{}"></span>'.format(color)
    elif style=="dash":shape='<span class="leg-dash" style="border-color:{}"></span>'.format(color)
    else:              shape='<span class="leg-dot"  style="background:{}"></span>'.format(color)
    return '<div class="leg">{}<span>{}</span></div>'.format(shape, label)

def chip(label, value, color=None):
    v = '<span class="val" style="color:{}">{}</span>'.format(color,value) if color else '<span class="val">{}</span>'.format(value)
    return '<span class="stat-chip"><span class="lbl">{}</span>{}</span>'.format(label, v)

def tile_open(title, sub, legend_html="", stat_html=""):
    st.markdown(
        '<div class="chart-tile">'
        '<div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:4px">'
        '<div><div class="tile-title">{}</div><div class="tile-sub">{}</div></div>'
        '<div class="tile-legend">{}</div></div>'
        '<div class="stat-row">{}</div>'.format(title, sub, legend_html, stat_html),
        unsafe_allow_html=True)

def tile_close():
    st.markdown('</div>', unsafe_allow_html=True)

def fmt(v, suffix="", color=None):
    if v is None or (isinstance(v,float) and pd.isna(v)):
        return '<span style="opacity:.3">—</span>'
    s = str(v)+suffix
    return '<span style="color:{};font-weight:600">{}</span>'.format(color,s) if color else s

# ── 사이드바 — 본부 선택 + 필터 ─────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="padding:14px 4px 10px">'
        '<div style="font-size:13px;font-weight:700;letter-spacing:-0.2px">📡 폐국 관리</div>'
        '</div>', unsafe_allow_html=True)
    st.divider()

    # 네비
    for label, href, active in [
        ("📊 메인 현황",      "#",               True),
        ("📋 후보 Pool 편집", "/후보_Pool_편집", False),
    ]:
        bg  = "rgba(26,111,196,0.08)" if active else "transparent"
        fw  = "600" if active else "400"
        clr = C["blue"] if active else "inherit"
        st.markdown(
            '<a href="{}" target="_self" style="text-decoration:none">'
            '<div style="padding:7px 10px;border-radius:7px;margin:1px 0;'
            'background:{};font-size:12px;font-weight:{};color:{}">{}</div></a>'
            .format(href,bg,fw,clr,label), unsafe_allow_html=True)

    st.divider()

    # ── 본부 선택 ────────────────────────────────────────────
    sel_honbu = st.selectbox(
        "본부 선택",
        options=HONBU_ORDER,
        index=HONBU_ORDER.index(DEFAULT_HONBU),
        key="sel_honbu",
    )
    honbu_color = HONBU_COLOR.get(sel_honbu, C["blue"])
    goal        = HONBU_GOAL.get(sel_honbu, ANNUAL_GOAL)

    st.divider()

    # ── Off 월 필터 ──────────────────────────────────────────
    st.markdown('<div style="font-size:10px;font-weight:600;letter-spacing:.06em;opacity:.4;text-transform:uppercase;padding-bottom:6px">Off 월</div>', unsafe_allow_html=True)
    MON_STATUS = {m: ("✅" if m in CONFIRMED else ("🔄" if m in REVIEW else "⏳")) for m in MONTH_ORDER}
    sel_months = []
    for m in MONTH_ORDER:
        # 데이터 로드 전이라 건수는 표시 안 함 (로드 후 재계산)
        lbl = "{} {}".format(MON_STATUS[m], m)
        if st.checkbox(lbl, value=(m in CONFIRMED or m in REVIEW), key="m_"+m):
            sel_months.append(m)

    st.divider()

    # ── 데이터 파일 상태 ─────────────────────────────────────
    main_path = MAIN_FILES.get(sel_honbu, MAIN_FILES[DEFAULT_HONBU])
    st.markdown('<div style="font-size:10px;font-weight:600;letter-spacing:.06em;opacity:.4;text-transform:uppercase;padding-bottom:6px">데이터 파일</div>', unsafe_allow_html=True)
    st.markdown(("🟢" if main_path.exists() else "🟡") + " 원시데이터.xlsx")
    st.markdown(("🟢" if RENT_FILE.exists() else "🟡") + " 임차_전기DB.xlsx")
    if not main_path.exists():
        st.caption("⚠️ 샘플 데이터 사용 중")

    if st.button("🔄 새로고침"):
        st.cache_data.clear()
        st.rerun()

# ── 데이터 로드 (선택된 본부 기준) ──────────────────────────
@st.cache_data(show_spinner=False)
def get_data(honbu, fhash_main, fhash_rent):
    df_raw  = load_raw(fhash_main, honbu)
    df_rent = enrich_rent(df_raw)
    extra   = load_extra()
    df      = apply_extra(df_rent, extra)
    df_pool = df[
        (df.get("_site_err", pd.Series("정상", index=df.index)) == "정상") &
        (df.get("_pool_yn",  pd.Series("반영",  index=df.index)) == "반영")
    ].copy()
    return calc_savings(df_pool)

with st.spinner("{}  데이터 로딩 중…".format(sel_honbu)):
    df_pool = get_data(
        sel_honbu,
        file_hash(MAIN_FILES.get(sel_honbu, MAIN_FILES[DEFAULT_HONBU])),
        file_hash(RENT_FILE),
    )
df_conf = df_pool[df_pool["_off_month"].isin(CONFIRMED)]

# ── KPI 계산 ─────────────────────────────────────────────────
total_conf = len(df_conf)
rent_conf  = round(df_conf["savings_ann"].sum() * 0.85 / 10000, 1)
elec_conf  = round(df_conf["_elec_ann"].sum() / 10000, 1)
pct_conf   = round(total_conf / goal * 100, 1)
voc_df     = voc_summary(df_pool)
voc_issued = int(voc_df["발생"].sum())          if len(voc_df) else 0
voc_open   = int(voc_df["미처리누계"].iloc[-1]) if len(voc_df) else 0
voc_done   = int(voc_df["처리완료"].sum())       if len(voc_df) else 0
eq_data    = equipment_summary(df_pool)
eq_total   = sum(sum(v.values()) for v in eq_data.values())

# ── 헤더 ─────────────────────────────────────────────────────
h_l, h_r = st.columns([6,2])
with h_l:
    hc = honbu_color
    st.markdown(
        '<div style="display:flex;align-items:center;gap:10px;padding:6px 0 12px">'
        '<span style="font-size:20px;font-weight:700;letter-spacing:-0.5px">메인 현황</span>'
        '<span class="badge" style="background:{hc}18;color:{hc}">{hb}</span>'
        '<span class="badge" style="background:#D1FAE5;color:#065F46">1~3월 확정</span>'
        '<span class="badge" style="background:#FEF3C7;color:#92400E">4월 검토중</span>'
        '</div>'.format(hc=hc, hb=sel_honbu),
        unsafe_allow_html=True)
with h_r:
    r1,r2 = st.columns(2)
    with r1:
        if st.button("🔄 새로고침", key="hdr_ref"):
            st.cache_data.clear(); st.rerun()
    with r2:
        st.button("📥 내보내기")

# ── KPI 카드 ─────────────────────────────────────────────────
k1,k2,k3,k4,k5 = st.columns(5)
kpi_data = [
    (k1,"누적 실적 (1~3월)", str(total_conf)+"개소",
     "연간 목표 {} 대비".format(goal), pct_conf, honbu_color, honbu_color+"18"),
    (k2,"임차료 절감(예상)",  str(rent_conf)+"억",  "순절감 기준 (억원)", 65,  C["green"],  C["green_l"]),
    (k3,"전기료 절감(예상)",  str(elec_conf)+"억",  "순절감 기준 (억원)", 40,  C["green"],  C["green_l"]),
    (k4,"VoC 현황",          str(voc_issued)+"건",
     "처리완료 {} · 미처리 {}건".format(voc_done, voc_open),
     (voc_open/voc_issued*100) if voc_issued else 0, C["red"], C["red_l"]),
    (k5,"Off 장비 수량",      str(eq_total)+"대",   "1~3월 합산", 55, C["teal"], C["teal_l"]),
]
for col,lbl,val,sub,pct,color,color_l in kpi_data:
    col.markdown(kpi_tile(lbl,val,sub,pct,color,color_l), unsafe_allow_html=True)

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ── 탭 ───────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["  차트 현황  ", "  월별 절감 상세  ", "  사업유형 상세  "])

# ════════ TAB 1 ═══════════════════════════════════════════════
with tab1:
    m_sum = monthly_summary(df_pool, goal=goal)
    valid = m_sum[m_sum["실적"] > 0]

    col1, col2 = st.columns(2, gap="medium")

    with col1:
        legend1 = (leg(honbu_color,"월 실적") +
                   leg(C["green"],"누계 달성률","line") +
                   leg(C["red"],"목표 100%","dash"))
        stats1  = (chip("누계", str(total_conf)+"건", honbu_color) +
                   chip("목표", str(goal)+"건") +
                   chip("달성률", str(pct_conf)+"%", C["green"]))
        tile_open("목표 대비 실적", "월별 실적 · 누계 달성률", legend1, stats1)

        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Bar(
            x=m_sum["월"], y=m_sum["실적"], name="월 실적",
            marker=dict(color=honbu_color, opacity=0.85, line=dict(width=0)),
            hovertemplate="%{x}: %{y}건<extra></extra>",
        ), secondary_y=False)
        fig1.add_trace(go.Scatter(
            x=valid["월"], y=valid["누계달성률"], name="누계 달성률",
            mode="lines+markers+text",
            line=dict(color=C["green"], width=2.5, shape="spline"),
            marker=dict(size=8, color="white", line=dict(color=C["green"], width=2.5)),
            text=["{}%".format(v) for v in valid["누계달성률"]],
            textposition="top center", textfont=dict(size=10, color=C["green"]),
            hovertemplate="%{x} 달성률: %{y}%<extra></extra>",
        ), secondary_y=True)
        fig1.add_hline(y=100, line_dash="dot", line_color=C["red"], line_width=1.5,
                       secondary_y=True, annotation_text="100%",
                       annotation_font=dict(size=9,color=C["red"]))
        fig1.update_layout(**base_layout(height=240, barmode="group"))
        fig1.update_xaxes(**sx()); fig1.update_yaxes(title_text="개소", secondary_y=False, **sy())
        fig1.update_yaxes(title_text="달성률", secondary_y=True, range=[0,135],
                          ticksuffix="%", **sy(showgrid=False))
        st.plotly_chart(fig1, width="stretch")
        tile_close()

    with col2:
        conf_m = ["1월","2월","3월"]
        rent_m, elec_m, cumul_m, run = [], [], [], 0.0
        for m in conf_m:
            s = df_pool[df_pool["_off_month"]==m]
            r = round(s["savings_ann"].sum()*0.85/10000, 2)
            e = round(s["_elec_ann"].sum()/10000, 2)
            run = round(run+r+e, 2)
            rent_m.append(r); elec_m.append(e); cumul_m.append(run)

        legend2 = leg(C["green"],"임차료")+leg(C["amber"],"전기료")+leg(C["blue"],"누계","line")
        stats2  = (chip("임차",str(rent_conf)+"억",C["green"]) +
                   chip("전기",str(elec_conf)+"억",C["amber"]) +
                   chip("합계",str(round(rent_conf+elec_conf,1))+"억",C["blue"]))
        tile_open("절감 실적","임차·전기 월별 + 누계 (억원)",legend2,stats2)

        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig2.add_trace(go.Bar(x=conf_m,y=rent_m,name="임차료",
                              marker=dict(color=C["green"],opacity=0.85,line=dict(width=0)),
                              hovertemplate="%{x} 임차: %{y}억<extra></extra>"),
                       secondary_y=False)
        fig2.add_trace(go.Bar(x=conf_m,y=elec_m,name="전기료",
                              marker=dict(color=C["amber"],opacity=0.85,line=dict(width=0)),
                              hovertemplate="%{x} 전기: %{y}억<extra></extra>"),
                       secondary_y=False)
        fig2.add_trace(go.Scatter(x=conf_m,y=cumul_m,name="누계",
                                   mode="lines+markers",
                                   line=dict(color=C["blue"],width=2.5,shape="spline"),
                                   marker=dict(size=8,color="white",line=dict(color=C["blue"],width=2.5)),
                                   hovertemplate="%{x} 누계: %{y}억<extra></extra>"),
                       secondary_y=True)
        fig2.update_layout(**base_layout(height=240,barmode="stack"))
        fig2.update_xaxes(**sx())
        fig2.update_yaxes(title_text="억원",secondary_y=False,**sy())
        fig2.update_yaxes(title_text="누계",secondary_y=True,ticksuffix="억",**sy(showgrid=False))
        st.plotly_chart(fig2, width="stretch")
        tile_close()

    col3, col4 = st.columns(2, gap="medium")

    with col3:
        eq   = equipment_summary(df_pool)
        eq_m = [m for m in ["1월","2월","3월"] if m in eq]
        ETYPE  = ["RRU","BBU","안테나","기타"]
        ECOLOR = [C["blue"],C["teal"],C["amber"],C["purple"]]
        eq_totals = [sum(eq[m].values()) for m in eq_m]
        legend3 = "".join(leg(c,t) for t,c in zip(ETYPE,ECOLOR))
        stats3  = "".join(chip(m,str(t)+"대") for m,t in zip(eq_m,eq_totals))
        stats3 += chip("누계",str(sum(eq_totals))+"대",C["teal"])
        tile_open("장비Type 현황","Type별 · 월별 철거 수량",legend3,stats3)

        fig3 = go.Figure()
        for t,c in zip(ETYPE,ECOLOR):
            fig3.add_trace(go.Bar(
                x=eq_m, y=[eq[m][t] for m in eq_m], name=t,
                marker=dict(color=c,opacity=0.85,line=dict(width=0)),
                hovertemplate="%{{x}} {}: %{{y}}대<extra></extra>".format(t),
            ))
        fig3.update_layout(**base_layout(height=240,barmode="stack"))
        fig3.update_xaxes(**sx()); fig3.update_yaxes(title_text="대",**sy())
        st.plotly_chart(fig3, width="stretch")
        tile_close()

    with col4:
        legend4 = leg(C["red"],"발생")+leg(C["green"],"처리완료")+leg(C["amber"],"미처리 누계","line")
        stats4  = (chip("발생",str(voc_issued)+"건",C["red"]) +
                   chip("완료",str(voc_done)+"건",C["green"]) +
                   chip("미처리",str(voc_open)+"건",C["amber"]))
        tile_open("VoC 현황","월별 발생·처리·미처리 누계",legend4,stats4)

        if voc_df.empty:
            st.info("VoC 데이터가 없습니다.")
        else:
            fig4 = make_subplots(specs=[[{"secondary_y": True}]])
            fig4.add_trace(go.Bar(x=voc_df["월"],y=voc_df["발생"],name="발생",
                                   marker=dict(color=C["red"],opacity=0.8,line=dict(width=0)),
                                   hovertemplate="%{x} 발생: %{y}건<extra></extra>"),
                           secondary_y=False)
            fig4.add_trace(go.Bar(x=voc_df["월"],y=voc_df["처리완료"],name="처리완료",
                                   marker=dict(color=C["green"],opacity=0.8,line=dict(width=0)),
                                   hovertemplate="%{x} 완료: %{y}건<extra></extra>"),
                           secondary_y=False)
            fig4.add_trace(go.Scatter(x=voc_df["월"],y=voc_df["미처리누계"],name="미처리 누계",
                                       mode="lines+markers",
                                       line=dict(color=C["amber"],width=2.5,shape="spline"),
                                       marker=dict(size=8,color="white",line=dict(color=C["amber"],width=2.5)),
                                       hovertemplate="%{x} 미처리: %{y}건<extra></extra>"),
                           secondary_y=True)
            fig4.update_layout(**base_layout(height=240,barmode="group"))
            fig4.update_xaxes(**sx())
            fig4.update_yaxes(title_text="건",secondary_y=False,dtick=1,**sy())
            fig4.update_yaxes(title_text="미처리 누계",secondary_y=True,dtick=1,**sy(showgrid=False))
            st.plotly_chart(fig4, width="stretch")
        tile_close()

# ════════ TAB 2: 월별 절감 상세 ══════════════════════════════
with tab2:
    m_sum2 = monthly_summary(df_pool, goal=goal)
    STATUS_MAP = {"확정":("#D1FAE5","#065F46"),"검토중":("#FEF3C7","#92400E"),"예정":("#F3F4F6","#6B7280")}

    def _badge(text,bg,fg):
        return '<span style="background:{};color:{};border-radius:4px;padding:1px 7px;font-size:10px;font-weight:500">{}</span>'.format(bg,fg,text)
    def _fmt(v,suffix="",color=None):
        if v is None or (isinstance(v,float) and pd.isna(v)): return '<span style="opacity:.3">—</span>'
        s=str(v)+suffix
        return '<span style="color:{};font-weight:600">{}</span>'.format(color,s) if color else s

    rows_html=[]
    for _,row in m_sum2.iterrows():
        mon=row["월"]; actual=int(row["실적"]) if row["실적"] else 0
        cumul=row["누계"]; pct=row["누계달성률"]
        c_ije=int(row["임차+전기"]); c_elec=int(row["전기만"]); c_none=int(row["절감없음"])
        r_rent=row["임차료절감"]; r_elec=row["전기료절감"]
        r_inv=row["투자비"]; r_net=row["순절감"]; status=row["상태"]
        if pct is not None and not pd.isna(pct):
            pc=C["green"] if pct>=100 else (C["amber"] if pct>=50 else C["red"])
            pct_html='<span style="color:{};font-weight:600">{}%</span>'.format(pc,pct)
        else:
            pct_html='<span style="opacity:.3">—</span>'
        cumul_disp=_fmt(cumul,"건") if (cumul and not pd.isna(cumul)) else '<span style="opacity:.3">—</span>'
        sbg,sfg=STATUS_MAP.get(status,("#F3F4F6","#6B7280"))
        rows_html.append("".join([
            "<tr>",
            "<td><b>{}</b></td>".format(mon),
            '<td style="text-align:right">{}</td>'.format(_fmt(actual if actual else None,"건",honbu_color)),
            '<td style="text-align:right">{}</td>'.format(cumul_disp),
            '<td style="text-align:right">{}</td>'.format(pct_html),
            '<td style="text-align:right">{}</td>'.format(_badge(c_ije,"#D1FAE5","#065F46")),
            '<td style="text-align:right">{}</td>'.format(_badge(c_elec,"#FEF3C7","#92400E")),
            '<td style="text-align:right">{}</td>'.format(_badge(c_none,"#F3F4F6","#6B7280")),
            '<td style="text-align:right">{}</td>'.format(_fmt(r_rent if r_rent else None,"억",C["green"])),
            '<td style="text-align:right">{}</td>'.format(_fmt(r_elec if r_elec else None,"억",C["amber"])),
            '<td style="text-align:right">{}</td>'.format(_fmt(r_inv  if r_inv  else None,"억",C["red"])),
            '<td style="text-align:right">{}</td>'.format(_fmt(r_net  if r_net  else None,"억",C["green"])),
            '<td><span class="badge" style="background:{};color:{}">{}</span></td>'.format(sbg,sfg,status),
            "</tr>",
        ]))

    HEADERS=["월","실적","누계","누계달성률","임차+전기","전기만","절감없음","임차료절감","전기료절감","투자비","순절감","상태"]
    th="padding:8px 10px;border-bottom:1px solid rgba(128,128,128,0.12);"
    st.markdown(
        '<table class="bi-table"><thead><tr style="background:rgba(128,128,128,0.04)">'
        +"".join('<th style="{}text-align:{}">{}</th>'.format(th,"left" if i==0 else "right",h) for i,h in enumerate(HEADERS))
        +"</tr></thead><tbody>"+"".join(rows_html)+"</tbody></table>",
        unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    td1,td2=st.columns(2,gap="medium")

    with td1:
        tile_open("누계 달성률 추이","월별 누계 ÷ 연간 목표 {}".format(goal),
                  leg(honbu_color,"달성률","line")+leg(C["red"],"목표 100%","dash"),"")
        valid2=m_sum2[m_sum2["누계달성률"].notna()]
        fig_p=go.Figure()
        fig_p.add_trace(go.Scatter(
            x=valid2["월"],y=valid2["누계달성률"],mode="lines+markers+text",
            line=dict(color=honbu_color,width=2.5,shape="spline"),
            fill="tozeroy", fillcolor=hex_rgba(honbu_color, 0.08),
            marker=dict(size=9,color="white",line=dict(color=honbu_color,width=2.5)),
            text=["{}%".format(v) for v in valid2["누계달성률"]],
            textposition="top center",textfont=dict(size=11,color=honbu_color),
            hovertemplate="%{x}: %{y}%<extra></extra>"))
        fig_p.add_hline(y=100,line_dash="dot",line_color=C["red"],line_width=1.5,
                        annotation_text="100%",annotation_font=dict(size=9,color=C["red"]))
        fig_p.update_layout(**base_layout(height=200))
        fig_p.update_xaxes(**sx())
        fig_p.update_yaxes(range=[0,125],ticksuffix="%",**sy())
        st.plotly_chart(fig_p, width="stretch")
        tile_close()

    with td2:
        tile_open("절감유형 비율","1~3월 확정 기준","","")
        sav_cnt=df_conf["sav_type"].value_counts()
        fig_s=go.Figure(go.Pie(
            labels=sav_cnt.index.tolist(),values=sav_cnt.values.tolist(),
            marker=dict(colors=[SAV_C.get(l,C["gray"]) for l in sav_cnt.index],
                        line=dict(color="white",width=2)),
            hole=0.68,textinfo="none",
            hovertemplate="%{label}: %{value}건 (%{percent})<extra></extra>"))
        fig_s.update_layout(**base_layout(height=200,
                            legend=dict(orientation="v",x=0.72,y=0.5,
                                        font=dict(size=11),bgcolor="rgba(0,0,0,0)")))
        fig_s.update_layout(showlegend=True)
        st.plotly_chart(fig_s, width="stretch")
        tile_close()

# ════════ TAB 3: 사업유형 상세 ═══════════════════════════════
with tab3:
    bs=biz_type_summary(df_conf)
    ta1,ta2=st.columns([3,2],gap="medium")

    with ta1:
        legend_a="".join(leg(c,s) for s,c in SAV_C.items())
        tile_open("사업유형 × 절감유형","건수 누적 기준",legend_a,"")
        fig_a1=go.Figure()
        for sav,color in SAV_C.items():
            fig_a1.add_trace(go.Bar(
                name=sav,x=bs["사업유형"],y=bs[sav],
                marker=dict(color=color,opacity=0.85,line=dict(width=0)),
                hovertemplate="%{{x}} {}: %{{y}}건<extra></extra>".format(sav)))
        fig_a1.update_layout(**base_layout(height=240,barmode="stack"))
        fig_a1.update_xaxes(**sx()); fig_a1.update_yaxes(title_text="건수",**sy())
        st.plotly_chart(fig_a1, width="stretch"); tile_close()

    with ta2:
        tile_open("임차료 절감","사업유형별 (억원)","","")
        fig_a2=go.Figure(go.Bar(
            x=bs["임차료절감"],y=bs["사업유형"],orientation="h",
            marker=dict(color=[BIZ_C.get(b,C["gray"]) for b in bs["사업유형"]],
                        opacity=0.85,line=dict(width=0)),
            text=["{}억".format(v) for v in bs["임차료절감"]],textposition="outside",
            textfont=dict(size=11),
            hovertemplate="%{y}: %{x}억<extra></extra>"))
        fig_a2.update_layout(**base_layout(height=240,margin=dict(l=2,r=50,t=6,b=2)))
        fig_a2.update_xaxes(title_text="억원",**sx()); fig_a2.update_yaxes(**sy())
        st.plotly_chart(fig_a2, width="stretch"); tile_close()

    tile_open("사업유형별 상세","1~3월 확정 기준","","")

    def bep_html(v):
        if v is None or (isinstance(v,float) and pd.isna(v)): return '<span style="opacity:.3">—</span>'
        vi=int(v); c=C["green"] if vi<=24 else (C["amber"] if vi<=48 else C["red"])
        return '<span style="color:{};font-weight:600">{}개월</span>'.format(c,vi)

    rows_biz=[]
    for _,row in bs.iterrows():
        biz=row["사업유형"]; bc=BIZ_C.get(biz,C["gray"]); nc=C["green"] if row["순절감"]>=0 else C["red"]
        rows_biz.append("".join([
            "<tr>",
            '<td><span style="background:{}18;color:{};border-radius:5px;padding:2px 8px;font-size:11px;font-weight:600">{}</span></td>'.format(bc,bc,biz),
            '<td style="text-align:right;font-weight:600">{}</td>'.format(int(row["건수"])),
            '<td style="text-align:right"><span style="background:#D1FAE5;color:#065F46;border-radius:4px;padding:1px 7px;font-size:10px;font-weight:500">{}</span></td>'.format(int(row["임차+전기"])),
            '<td style="text-align:right"><span style="background:#FEF3C7;color:#92400E;border-radius:4px;padding:1px 7px;font-size:10px;font-weight:500">{}</span></td>'.format(int(row["전기만"])),
            '<td style="text-align:right"><span style="background:#F3F4F6;color:#6B7280;border-radius:4px;padding:1px 7px;font-size:10px;font-weight:500">{}</span></td>'.format(int(row["절감없음"])),
            '<td style="text-align:right;color:{};font-weight:600">{}억</td>'.format(C["green"],row["임차료절감"]),
            '<td style="text-align:right;color:{};opacity:.8">{}억</td>'.format(C["amber"],row["전기료절감"]),
            '<td style="text-align:right;color:{}">{}</td>'.format(C["red"],"{}억".format(row["투자비"]) if row["투자비"] else "—"),
            '<td style="text-align:right;color:{};font-weight:600">{}억</td>'.format(nc,row["순절감"]),
            '<td style="text-align:right">{}</td>'.format(bep_html(row["평균BEP"])),
            "</tr>",
        ]))

    BIZ_H=["사업유형","건수","임차+전기","전기만","절감없음","임차료절감","전기료절감","투자비","순절감","평균BEP"]
    st.markdown(
        '<table class="bi-table"><thead><tr>'
        +"".join('<th style="text-align:{}">{}</th>'.format("left" if i==0 else "right",h) for i,h in enumerate(BIZ_H))
        +"</tr></thead><tbody>"+"".join(rows_biz)+"</tbody></table>",
        unsafe_allow_html=True)
    tile_close()

    opt=df_conf[df_conf["_biz_type"]=="최적화후폐국"]
    opt_inv=opt[opt["_inv_total"]>0]
    if not opt_inv.empty:
        avg_bep=opt_inv["bep_months"].dropna().mean()
        bep_s="{}개월".format(int(avg_bep)) if not pd.isna(avg_bep) else "—"
        st.info("📌 **최적화후폐국** — 투자비 발생 {}건 · 평균 BEP **{}** · 순절감 {}억원 (투자비 {}억 차감 후)".format(
            len(opt_inv), bep_s,
            round(opt_inv["net_savings"].sum()/10000,2),
            round(opt_inv["_inv_total"].sum()/10000,2)))