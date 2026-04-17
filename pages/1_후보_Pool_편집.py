"""
pages/1_후보_Pool_편집.py
"""

import streamlit as st
import pandas as pd
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.data_loader import (
    load_main, _file_hash, MAIN_FILE, _make_sample_main, save_change_log, CHANGES_FILE
)
from utils.calc import calc_savings, ANNUAL_GOAL

st.set_page_config(page_title="후보 Pool 편집", layout="wide")

st.markdown("""
<style>
.block-container{padding-top:1rem}
[data-testid="stSidebar"]{min-width:200px;max-width:220px}
</style>
""", unsafe_allow_html=True)

# ── 데이터 ────────────────────────────────────────────────────
@st.cache_data(show_spinner="데이터 로딩 중…")
def get_pool():
    mh = _file_hash(MAIN_FILE)
    df = load_main(mh) if MAIN_FILE.exists() else _make_sample_main()
    return calc_savings(df[df["is_pool"]].copy())

df = get_pool()

CONFIRMED = {"1월","2월","3월"}
BIZ_OPTS  = ["단순폐국","이설후폐국","최적화후폐국"]
TOSI_OPTS = ["단독","통시","아파트","공용"]
SAV_OPTS  = ["임차+전기","전기만","절감없음"]
YN_OPTS   = ["반영","미반영"]
REASON_OPTS = ["","LOS 반경내 당사 Site 없음","공용 사이트 임차 해지 불가",
               "아파트 일부 Sitekey","잔여장비 있음","이설 미완료","본사 반려"]

# ── 헤더 ─────────────────────────────────────────────────────
st.markdown("## 후보 Pool 편집")

col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns(5)
col_h1.metric("전체", f"{len(df)}건")
col_h2.metric("임차+전기", f"{len(df[df['sav_type']=='임차+전기'])}건")
col_h3.metric("전기만",    f"{len(df[df['sav_type']=='전기만'])}건")
col_h4.metric("절감없음",  f"{len(df[df['sav_type']=='절감없음'])}건")
col_h5.metric("4월 후보 제출", f"{len(df[df['off_month']=='4월'])}건")

st.divider()

# ── 탭 ───────────────────────────────────────────────────────
tab_all, tab_submit, tab_nr = st.tabs(["전체 Pool", "후보 제출 목록 (4월)", "미반영"])

# ────────────────────────────────────────────────────────────
# 공통: st.data_editor 기반 편집 테이블
# ────────────────────────────────────────────────────────────
DISPLAY_COLS = {
    "sitekey":    "Sitekey",
    "site_name":  "국소명",
    "biz_type":   "사업유형",
    "tosi":       "통시구분",
    "off_month":  "Off 월",
    "close_month":"폐국월",
    "sav_type":   "절감유형",
    "rent_ann":   "연임차료(만)",
    "elec_ann":   "연전기료(만)",
    "savings_ann":"절감금액(자동)",
    "inv_bun":    "투자비(분기)",
    "inv_bae":    "투자비(재배치)",
    "inv_total":  "총투자비",
    "savings_mon":"월절감(만)",
    "bep_months": "BEP(개월)",
    "net_savings":"순절감(만)",
    "pool_yn":    "반영여부",
    "pool_reason":"미반영사유",
}

EDITABLE = {"biz_type","tosi","close_month","sav_type","inv_bun","inv_bae","pool_yn","pool_reason"}
READONLY  = set(DISPLAY_COLS.keys()) - EDITABLE

def make_editor(df_in: pd.DataFrame, key: str, locked: bool = False):
    disp = df_in.rename(columns=DISPLAY_COLS)
    show_cols = [c for c in DISPLAY_COLS.values() if c in disp.columns]
    disp = disp[show_cols]

    col_config = {}
    for orig, label in DISPLAY_COLS.items():
        if orig in ("biz_type",):
            col_config[label] = st.column_config.SelectboxColumn(label, options=BIZ_OPTS, width="medium")
        elif orig == "tosi":
            col_config[label] = st.column_config.SelectboxColumn(label, options=TOSI_OPTS, width="small")
        elif orig == "sav_type":
            col_config[label] = st.column_config.SelectboxColumn(label, options=SAV_OPTS, width="medium")
        elif orig == "pool_yn":
            col_config[label] = st.column_config.SelectboxColumn(label, options=YN_OPTS, width="small")
        elif orig == "pool_reason":
            col_config[label] = st.column_config.SelectboxColumn(label, options=REASON_OPTS, width="large")
        elif orig in ("rent_ann","elec_ann","savings_ann","inv_bun","inv_bae","inv_total",
                      "savings_mon","net_savings"):
            col_config[label] = st.column_config.NumberColumn(label, format="%.0f")
        elif orig == "bep_months":
            col_config[label] = st.column_config.NumberColumn(label, format="%d 개월")

    disabled = [DISPLAY_COLS[c] for c in READONLY if c in DISPLAY_COLS] if not locked else list(DISPLAY_COLS.values())

    edited = st.data_editor(
        disp,
        column_config=col_config,
        disabled=disabled,
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        key=key,
    )
    return edited


# ── 탭 1: 전체 Pool ──────────────────────────────────────────
with tab_all:
    # 필터 바
    f1, f2, f3, f4 = st.columns([2, 2, 2, 4])
    with f1:
        f_month = st.multiselect("Off 월", ["1월","2월","3월","4월","5월","6월"],
                                  default=["1월","2월","3월","4월"], key="f_mon")
    with f2:
        f_sav = st.multiselect("절감유형", SAV_OPTS, default=SAV_OPTS, key="f_sav")
    with f3:
        f_biz = st.multiselect("사업유형", BIZ_OPTS, default=BIZ_OPTS, key="f_biz")
    with f4:
        st.markdown("")  # 공간

    df_show = df.copy()
    if f_month: df_show = df_show[df_show["off_month"].isin(f_month)]
    if f_sav:   df_show = df_show[df_show["sav_type"].isin(f_sav)]
    if f_biz:   df_show = df_show[df_show["biz_type"].isin(f_biz)]

    st.caption(f"📌 노란 셀 수정 가능 · 총 **{len(df_show)}건** 표시 중")

    edited_df = make_editor(df_show.reset_index(drop=True), key="editor_all")

    col_s1, col_s2, col_s3 = st.columns([1, 1, 8])
    if col_s1.button("💾 저장", type="primary"):
        st.success("저장 완료! (실제 파일 연결 시 반영됩니다)")
    if col_s2.button("📥 엑셀 다운로드"):
        csv = df_show.to_csv(index=False, encoding="utf-8-sig").encode()
        st.download_button("다운로드", csv, "pool_전체.csv", mime="text/csv")


# ── 탭 2: 후보 제출 목록 (4월) ──────────────────────────────
with tab_submit:
    df_sub = df[
        (df["off_month"] == "4월") &
        (df["pool_yn"] == "반영")
    ].copy()

    st.markdown(f"**4월 본사 제출 후보 — {len(df_sub)}건** · 읽기 전용")
    st.caption("본사 제출 후 수정 불가 · 폐국월·절감금액은 본사 확정 후 반영")

    # 요약 KPI
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("제출 건수",   f"{len(df_sub)}건")
    c2.metric("임차+전기",  f"{len(df_sub[df_sub['sav_type']=='임차+전기'])}건")
    c3.metric("전기만",     f"{len(df_sub[df_sub['sav_type']=='전기만'])}건")
    c4.metric("절감없음",   f"{len(df_sub[df_sub['sav_type']=='절감없음'])}건")

    make_editor(df_sub.reset_index(drop=True), key="editor_sub", locked=True)

    if st.button("📥 제출 목록 다운로드"):
        csv = df_sub.to_csv(index=False, encoding="utf-8-sig").encode()
        st.download_button("다운로드", csv, "4월_제출목록.csv", mime="text/csv")


# ── 탭 3: 미반영 ─────────────────────────────────────────────
with tab_nr:
    df_nr = df[df["pool_yn"] == "미반영"].copy()
    st.markdown(f"**미반영 목록 — {len(df_nr)}건**")

    if df_nr.empty:
        st.info("미반영 항목이 없습니다.")
    else:
        make_editor(df_nr.reset_index(drop=True), key="editor_nr", locked=True)

    if st.button("📥 미반영 목록 다운로드"):
        csv = df_nr.to_csv(index=False, encoding="utf-8-sig").encode()
        st.download_button("다운로드", csv, "미반영목록.csv", mime="text/csv")