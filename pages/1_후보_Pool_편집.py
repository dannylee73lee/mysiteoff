"""
pages/1_후보_Pool_편집.py
- 사이드바 본부 선택 → 해당 본부 데이터만 표시
- 임차·전기: 1순위 DB → 2순위 엑셀 → 3순위 원시 파일 P·Q열
- Off 월 1~6월
- T~AC열 화면 직접 편집 + 저장
"""
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.data_loader import (
    load_raw, get_rent_data, apply_extra, load_extra, save_extra,
    log_change, load_log, file_hash,
    MAIN_FILES, RENT_FILE, DEFAULT_HONBU,
    HONBU_ORDER, MONTH_ORDER, CONFIRMED, REVIEW,
    EXTRA_COLS, EDITABLE_EXTRA,
)
from utils.calc import calc_savings, HONBU_GOAL, ANNUAL_GOAL

st.set_page_config(page_title="후보 Pool 편집", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif}
.block-container{padding:0.75rem 1.5rem 1.5rem}
[data-testid="stSidebar"]{min-width:200px;max-width:215px}
.kpi-sm{background:var(--background-color);border:1px solid rgba(128,128,128,0.13);
    border-radius:10px;padding:12px 14px;position:relative;overflow:hidden}
.kpi-sm-acc{position:absolute;top:0;left:0;width:4px;height:100%;border-radius:10px 0 0 10px}
.kpi-sm-lbl{font-size:10px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;opacity:.4;margin-bottom:4px}
.kpi-sm-val{font-size:20px;font-weight:700;letter-spacing:-0.5px}
.kpi-sm-sub{font-size:10px;opacity:.4;margin-top:2px}
.badge{display:inline-block;border-radius:5px;padding:1px 7px;font-size:10px;font-weight:500}
.src-tag{display:inline-block;border-radius:4px;padding:1px 6px;font-size:9px;font-weight:600}
#MainMenu,footer,header{visibility:hidden}
</style>
""", unsafe_allow_html=True)

C = dict(blue="#1A6FC4",green="#2D7D46",amber="#B45309",red="#C0392B",purple="#5B4DA0",gray="#6B7280")
HONBU_COLOR = {"수도권":C["blue"],"04.중부":C["green"],"동부":C["amber"],"서부":C["purple"]}

BIZ_OPTS   = ["단순폐국","이설후폐국","최적화후폐국"]
SAV_OPTS   = ["임차+전기","전기만","절감없음"]
YN_OPTS    = ["반영","미반영"]
REASON_OPTS= ["","LOS 반경내 당사 Site 없음","공용 사이트 임차 해지 불가",
               "아파트 일부 Sitekey","잔여장비 있음","이설 미완료","본사 반려"]
MONTH_OPTS = [""] + MONTH_ORDER

# ── 사이드바 ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="padding:14px 4px 10px">'
        '<div style="font-size:13px;font-weight:700">📡 폐국 관리</div>'
        '</div>', unsafe_allow_html=True)
    st.divider()

    for label, href, active in [
        ("📊 메인 현황",      "/",  False),
        ("📋 후보 Pool 편집", "#",  True),
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

    sel_honbu = st.selectbox("본부 선택", options=HONBU_ORDER,
                              index=HONBU_ORDER.index(DEFAULT_HONBU), key="sel_honbu")
    hcolor = HONBU_COLOR.get(sel_honbu, C["blue"])
    goal   = HONBU_GOAL.get(sel_honbu, ANNUAL_GOAL)

    st.divider()
    st.markdown('<div style="font-size:10px;font-weight:600;opacity:.4;text-transform:uppercase;letter-spacing:.06em;padding-bottom:6px">필터</div>', unsafe_allow_html=True)

    MON_STATUS = {m:("✅" if m in CONFIRMED else ("🔄" if m in REVIEW else "⏳")) for m in MONTH_ORDER}
    sel_months = st.multiselect("Off 월", options=MONTH_ORDER,
                                 default=["1월","2월","3월","4월"], key="f_month")
    sel_biz    = st.multiselect("사업유형", options=BIZ_OPTS, default=BIZ_OPTS, key="f_biz")
    sel_sav    = st.multiselect("절감유형", options=SAV_OPTS, default=SAV_OPTS, key="f_sav")

    st.divider()
    main_path = MAIN_FILES.get(sel_honbu, MAIN_FILES[DEFAULT_HONBU])
    st.markdown('<div style="font-size:10px;font-weight:600;opacity:.4;text-transform:uppercase;letter-spacing:.06em;padding-bottom:6px">데이터 파일</div>', unsafe_allow_html=True)
    st.markdown(("🟢" if main_path.exists() else "🟡") + " 원시데이터.xlsx")
    st.markdown(("🟢" if RENT_FILE.exists() else "🟡") + " 임차_전기DB.xlsx")
    if not main_path.exists():
        st.caption("⚠️ 샘플 데이터 사용 중")
    if st.button("🔄 새로고침"):
        st.cache_data.clear(); st.rerun()

# ── 데이터 로드 ──────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def get_all(honbu, mhash, rhash):
    df_raw  = load_raw(mhash, honbu)
    df_rent = get_rent_data(df_raw)
    extra   = load_extra()
    df      = apply_extra(df_rent, extra)
    return calc_savings(df)

with st.spinner("{} 데이터 로딩 중…".format(sel_honbu)):
    df_all = get_all(sel_honbu,
                     file_hash(MAIN_FILES.get(sel_honbu, MAIN_FILES[DEFAULT_HONBU])),
                     file_hash(RENT_FILE))

df_pool = df_all[
    (df_all.get("site_err", pd.Series("정상", index=df_all.index)) == "정상") &
    (df_all.get("pool_yn",  pd.Series("반영",  index=df_all.index)) == "반영")
].copy()

# ── 헤더 ─────────────────────────────────────────────────────
st.markdown(
    '<div style="display:flex;align-items:center;gap:10px;padding:6px 0 10px">'
    '<span style="font-size:20px;font-weight:700;letter-spacing:-0.5px">후보 Pool 편집</span>'
    '<span class="badge" style="background:{hc}18;color:{hc}">{hb}</span>'
    '<span class="badge" style="background:#D1FAE5;color:#065F46">1~3월 확정</span>'
    '<span class="badge" style="background:#FEF3C7;color:#92400E">4월 검토중</span>'
    '</div>'.format(hc=hcolor, hb=sel_honbu), unsafe_allow_html=True)

# ── 임차·전기 데이터 출처 표시 ──────────────────────────────
from utils.data_loader import RENT_FILE, query_rent_from_db
_db_sample = query_rent_from_db([])
if not _db_sample.empty if hasattr(_db_sample, 'empty') else False:
    src_label, src_bg, src_fg = "1순위: DB 연결", "#D1FAE5", "#065F46"
elif RENT_FILE.exists():
    src_label, src_bg, src_fg = "2순위: 임차_전기DB.xlsx", "#FEF3C7", "#92400E"
else:
    src_label, src_bg, src_fg = "3순위: 원시파일 P·Q열", "#F3F4F6", "#6B7280"

st.markdown(
    '임차·전기 데이터 출처: '
    '<span class="src-tag" style="background:{};color:{}">{}</span>'.format(src_bg,src_fg,src_label),
    unsafe_allow_html=True)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ── 요약 KPI ─────────────────────────────────────────────────
df_conf = df_pool[df_pool["off_month"].isin(CONFIRMED)]
total_c = len(df_conf)
pct_c   = round(total_c / goal * 100, 1)

def kpi_sm(label, value, sub, color):
    return (
        '<div class="kpi-sm">'
        '<div class="kpi-sm-acc" style="background:{c}"></div>'
        '<div style="padding-left:8px">'
        '<div class="kpi-sm-lbl">{lbl}</div>'
        '<div class="kpi-sm-val" style="color:{c}">{val}</div>'
        '<div class="kpi-sm-sub">{sub}</div>'
        '</div></div>'
    ).format(c=color, lbl=label, val=value, sub=sub)

k1,k2,k3,k4,k5,k6 = st.columns(6)
k1.markdown(kpi_sm("Pool 전체",    str(len(df_pool))+"건",   "반영 대상", hcolor), unsafe_allow_html=True)
k2.markdown(kpi_sm("1~3월 실적",   str(total_c)+"건",        "달성률 {}%".format(pct_c), hcolor), unsafe_allow_html=True)
k3.markdown(kpi_sm("4월 후보",     str((df_pool["off_month"]=="4월").sum())+"건", "검토중", C["amber"]), unsafe_allow_html=True)
k4.markdown(kpi_sm("임차+전기",    str((df_pool["sav_type"]=="임차+전기").sum())+"건", "절감유형", C["green"]), unsafe_allow_html=True)
k5.markdown(kpi_sm("투자비 발생",  str((df_pool["inv_total"]>0).sum())+"건", "최적화후폐국", C["red"]), unsafe_allow_html=True)
k6.markdown(kpi_sm("미반영",       str(len(df_all[df_all.get("pool_yn",pd.Series("반영",index=df_all.index))=="미반영"]))+"건", "제외 대상", C["gray"]), unsafe_allow_html=True)

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# ── 탭 ───────────────────────────────────────────────────────
tab_all, tab_submit, tab_nr, tab_log = st.tabs([
    "  전체 Pool  ", "  4월 제출 목록  ", "  미반영  ", "  변경 이력  "
])

# ── 컬럼 정의 ─────────────────────────────────────────────────
# 원시 컬럼 (표시 전용, 엑셀 열 번호 제외)
RAW_SHOW = {
    "sitekey":     "Sitekey",
    "site_name":   "국소명",
    "biz_type":    "사업유형",
    "tosi":        "통시구분",
    "off_month":   "Off 월",
    "pool_yn":     "반영여부",
    "pool_reason": "미반영사유",
    "voc":         "VoC",
    # 임차·전기 (조인 결과, 읽기전용)
    "rent_ann":    "연임차료(만)",
    "elec_ann":    "연전기료(만)",
}
# 편집 가능 추가 컬럼
EDIT_SHOW = {
    "sav_type":      "절감유형",
    "inv_bun":       "투자비_분기(만)",
    "inv_bae":       "투자비_재배치(만)",
    "savings_ann":   "절감금액_자동(만)",   # 읽기전용
    "bep_months":    "BEP(개월)",            # 읽기전용
    "net_savings":   "순절감(만)",           # 읽기전용
    "confirm_month": "폐국월_확정",
    "savings_fix":   "절감금액_확정(만)",
    "note":          "비고",
}
ALL_LABELS  = {**RAW_SHOW, **EDIT_SHOW}
READONLY_KS = set(RAW_SHOW.keys()) | {"savings_ann","bep_months","net_savings"}


def build_cfg():
    L = ALL_LABELS
    cfg = {}
    cfg[L["sav_type"]]      = st.column_config.SelectboxColumn(L["sav_type"], options=SAV_OPTS, width="medium")
    cfg[L["pool_yn"]]       = st.column_config.SelectboxColumn(L["pool_yn"],  options=YN_OPTS,  width="small")
    cfg[L["pool_reason"]]   = st.column_config.SelectboxColumn(L["pool_reason"], options=REASON_OPTS, width="large")
    cfg[L["confirm_month"]] = st.column_config.SelectboxColumn(L["confirm_month"], options=MONTH_OPTS, width="small")
    for k in ("rent_ann","elec_ann","inv_bun","inv_bae","savings_ann","net_savings","savings_fix"):
        cfg[L[k]] = st.column_config.NumberColumn(L[k], format="%.0f", width="small")
    cfg[L["bep_months"]] = st.column_config.NumberColumn(L["bep_months"], format="%d 개월", width="small")
    cfg[L["note"]]        = st.column_config.TextColumn(L["note"], width="medium")
    return cfg


def render_editor(df_in, key, locked=False):
    show = [k for k in ALL_LABELS if k in df_in.columns]
    disp = df_in[show].rename(columns=ALL_LABELS).reset_index(drop=True)
    disabled = list(ALL_LABELS.values()) if locked else [ALL_LABELS[k] for k in show if k in READONLY_KS]
    edited = st.data_editor(
        disp, column_config=build_cfg(),
        disabled=disabled, hide_index=True,
        num_rows="fixed", width="stretch", key=key)
    return edited, df_in[show].reset_index(drop=True)


def save_edits(edited, original, df_src):
    extra   = load_extra()
    inv_lbl = {v:k for k,v in ALL_LABELS.items()}
    changed = 0
    for i in range(min(len(edited), len(df_src))):
        sk = df_src.iloc[i]["sitekey"]
        if sk not in extra: extra[sk] = {}
        for col_label in edited.columns:
            col_key = inv_lbl.get(col_label)
            if not col_key or col_key not in EDITABLE_EXTRA: continue
            new_val = edited.iloc[i][col_label]
            old_val = original.iloc[i][col_label] if col_label in original.columns else ""
            new_s = "" if (new_val is None or (isinstance(new_val,float) and pd.isna(new_val))) else str(new_val)
            old_s = "" if (old_val is None or (isinstance(old_val,float) and pd.isna(old_val))) else str(old_val)
            if new_s != old_s:
                extra[sk][col_key] = new_val if new_s else ""
                log_change(sk, col_key, old_s, new_s)
                changed += 1
    save_extra(extra)
    return changed


# ════════ TAB 1: 전체 Pool ════════════════════════════════════
with tab_all:
    df_show = df_pool.copy()
    if sel_months: df_show = df_show[df_show["off_month"].isin(sel_months)]
    if sel_biz:    df_show = df_show[df_show["biz_type"].isin(sel_biz)]
    if sel_sav:    df_show = df_show[df_show["sav_type"].isin(sel_sav)]

    st.markdown(
        '<div style="font-size:11px;opacity:.5;padding:4px 0 8px">'
        '🟡 <b>편집 가능</b>: 절감유형 · 투자비(분기·재배치) · 폐국월_확정 · 절감금액_확정 · 비고 &nbsp;|&nbsp; '
        '절감금액_자동 · BEP · 순절감은 투자비 입력 시 자동 계산 &nbsp;|&nbsp; '
        '표시 <b>{}</b>건</div>'.format(len(df_show)),
        unsafe_allow_html=True)

    edited_df, orig_df = render_editor(df_show.reset_index(drop=True), "ed_all")

    sc1, sc2, _ = st.columns([1,1,8])
    if sc1.button("💾 저장", type="primary", key="save_all"):
        cnt = save_edits(edited_df, orig_df, df_show.reset_index(drop=True))
        st.cache_data.clear()
        if cnt: st.success("저장 완료 — {}건 변경".format(cnt)); st.rerun()
        else:   st.info("변경된 항목이 없습니다.")
    if sc2.button("📥 CSV", key="dl_all"):
        csv = df_show.to_csv(index=False, encoding="utf-8-sig").encode()
        st.download_button("다운로드", csv, "pool_전체.csv", mime="text/csv", key="dlbtn_all")


# ════════ TAB 2: 4월 제출 목록 ═══════════════════════════════
with tab_submit:
    df_sub = df_pool[df_pool["off_month"]=="4월"].copy()
    st.markdown("**4월 본사 제출 후보 — {}건** · 읽기 전용".format(len(df_sub)))
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("제출 건수",  "{}건".format(len(df_sub)))
    c2.metric("임차+전기", "{}건".format((df_sub["sav_type"]=="임차+전기").sum()))
    c3.metric("전기만",    "{}건".format((df_sub["sav_type"]=="전기만").sum()))
    c4.metric("절감없음",  "{}건".format((df_sub["sav_type"]=="절감없음").sum()))
    render_editor(df_sub.reset_index(drop=True), "ed_sub", locked=True)
    if st.button("📥 제출 목록 다운로드"):
        csv = df_sub.to_csv(index=False, encoding="utf-8-sig").encode()
        st.download_button("다운로드", csv, "4월_제출목록.csv", mime="text/csv", key="dlbtn_sub")


# ════════ TAB 3: 미반영 ══════════════════════════════════════
with tab_nr:
    df_nr = df_all[df_all.get("pool_yn", pd.Series("반영", index=df_all.index))=="미반영"].copy()
    st.markdown("**미반영 목록 — {}건**".format(len(df_nr)))
    if df_nr.empty:
        st.info("미반영 항목이 없습니다.")
    else:
        render_editor(df_nr.reset_index(drop=True), "ed_nr", locked=True)
        if st.button("📥 미반영 목록 다운로드"):
            csv = df_nr.to_csv(index=False, encoding="utf-8-sig").encode()
            st.download_button("다운로드", csv, "미반영목록.csv", mime="text/csv", key="dlbtn_nr")


# ════════ TAB 4: 변경 이력 ═══════════════════════════════════
with tab_log:
    st.markdown("##### 변경 이력")
    df_log = load_log()
    if df_log.empty:
        st.info("아직 변경 이력이 없습니다.")
    else:
        st.dataframe(
            df_log[["ts","user","sitekey","col","old","new"]]
              .sort_values("ts", ascending=False).head(200),
            width="stretch", hide_index=True)