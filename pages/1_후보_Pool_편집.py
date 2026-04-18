"""
pages/1_후보_Pool_편집.py
원시 데이터 포맷 유지 + 끝에 추가 컬럼(절감유형·투자비·본사확정) 편집
"""

import sys
from pathlib import Path
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.data_loader import (
    load_raw, file_hash, apply_extra, load_extra, save_extra, log_change, load_log,
    MAIN_FILE,
)
from utils.calc import calc_savings, CONFIRMED

st.set_page_config(page_title="후보 Pool 편집", layout="wide")

# ── 사이드바 네비게이션 ──────────────────────────────────────
with st.sidebar:
    st.markdown("### 📡 폐국 관리 시스템")
    st.markdown("**04.중부 본부**")
    st.divider()
    st.markdown("**페이지**")
    st.markdown(
        '<div style="padding:5px 10px;margin:2px 0;font-size:12px">'
        '<a href="/" target="_self" '
        'style="text-decoration:none;color:var(--text-color)">📊 메인 현황</a></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="background:var(--secondary-background-color);border-radius:6px;'
        'padding:5px 10px;margin:2px 0;font-size:12px;font-weight:500">'
        '📋 후보 Pool 편집</div>',
        unsafe_allow_html=True,
    )

st.markdown("""
<style>
.block-container{padding-top:1rem}
[data-testid="stSidebar"]{min-width:190px;max-width:210px}
</style>
""", unsafe_allow_html=True)

# ── 옵션 목록 ────────────────────────────────────────────────
BIZ_OPTS    = ["단순폐국", "이설후폐국", "최적화후폐국"]
TOSI_OPTS   = ["단독", "통시", "아파트", "공용"]
SAV_OPTS    = ["임차+전기", "전기만", "절감없음"]
YN_OPTS     = ["반영", "미반영"]
REASON_OPTS = [
    "", "LOS 반경내 당사 Site 없음", "공용 사이트 임차 해지 불가",
    "아파트 일부 Sitekey", "잔여장비 있음", "이설 미완료", "본사 반려",
]
MONTH_OPTS  = ["", "1월", "2월", "3월", "4월", "5월", "6월"]

# ── 데이터 로드 ──────────────────────────────────────────────
@st.cache_data(show_spinner="데이터 로딩 중…")
def get_raw(fhash):
    return load_raw(fhash)

fhash  = file_hash(MAIN_FILE)
df_raw = get_raw(fhash)
extra  = load_extra()
df     = apply_extra(df_raw, extra)
df     = calc_savings(df)

# Pool 대상 (정상 + 반영)
df_pool = df[
    (df.get("site_err", pd.Series("정상", index=df.index)) == "정상") &
    (df.get("pool_yn",  pd.Series("반영",  index=df.index)) == "반영")
].copy()

# ── 헤더 ─────────────────────────────────────────────────────
st.markdown("## 후보 Pool 편집")
st.caption("원시 데이터 포맷 유지 · 끝 컬럼(절감유형·투자비·본사확정)만 추가 편집 가능")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("전체 Pool",    f"{len(df_pool)}건")
k2.metric("임차+전기",   f"{(df_pool['sav_type']=='임차+전기').sum()}건")
k3.metric("전기만",      f"{(df_pool['sav_type']=='전기만').sum()}건")
k4.metric("절감없음",    f"{(df_pool['sav_type']=='절감없음').sum()}건")
k5.metric("4월 후보",    f"{(df_pool['off_month']=='4월').sum()}건")

st.divider()

# ── 탭 ───────────────────────────────────────────────────────
tab_all, tab_submit, tab_nr, tab_log = st.tabs(
    ["전체 Pool", "후보 제출 목록 (4월)", "미반영", "변경 이력"]
)

# ── 컬럼 설정 ────────────────────────────────────────────────
# 원시 데이터 컬럼 (읽기 전용으로 표시)
RAW_COLS = {
    "sitekey":     "Sitekey",
    "site_name":   "국소명",
    "honbu":       "본부",
    "biz_type":    "사업유형",
    "tosi":        "통시구분",
    "off_month":   "Off 월",
    "rent_ann":    "연임차료(만)",
    "elec_ann":    "연전기료(만)",
    "pool_yn":     "반영여부",
    "pool_reason": "미반영사유",
    "voc":         "VoC",
}
# 추가 컬럼 (편집 가능) — 원시 데이터 끝에 붙음
ADD_COLS = {
    "sav_type":      "절감유형",
    "투자비_분기":    "투자비_분기(만)",
    "투자비_재배치":  "투자비_재배치(만)",
    "savings_ann":   "절감금액_자동(만)",
    "bep_months":    "BEP(개월)",
    "net_savings":   "순절감(만)",
    "폐국월_확정":    "폐국월_확정",
    "절감금액_확정":  "절감금액_확정(만)",
}
EDITABLE_COLS = {"sav_type", "투자비_분기", "투자비_재배치", "폐국월_확정", "절감금액_확정"}
ALL_COLS = {**RAW_COLS, **ADD_COLS}


def make_col_config():
    cfg = {}
    for key, label in ALL_COLS.items():
        if key == "sav_type":
            cfg[label] = st.column_config.SelectboxColumn(label, options=SAV_OPTS, width="medium")
        elif key == "pool_yn":
            cfg[label] = st.column_config.SelectboxColumn(label, options=YN_OPTS, width="small")
        elif key == "pool_reason":
            cfg[label] = st.column_config.SelectboxColumn(label, options=REASON_OPTS, width="large")
        elif key == "폐국월_확정":
            cfg[label] = st.column_config.SelectboxColumn(label, options=MONTH_OPTS, width="small")
        elif key in ("rent_ann","elec_ann","savings_ann","투자비_분기","투자비_재배치",
                     "net_savings","절감금액_확정"):
            cfg[label] = st.column_config.NumberColumn(label, format="%.0f", width="small")
        elif key == "bep_months":
            cfg[label] = st.column_config.NumberColumn(label, format="%d 개월", width="small")
    return cfg


def render_editor(df_in: pd.DataFrame, key: str, locked: bool = False):
    """공통 data_editor 렌더."""
    # 표시할 컬럼만 추출 + 레이블로 rename
    show = {k: v for k, v in ALL_COLS.items() if k in df_in.columns}
    disp = df_in[list(show.keys())].rename(columns=show).reset_index(drop=True)

    disabled = (
        list(ALL_COLS.values())          # 전체 잠금
        if locked
        else [ALL_COLS[k] for k in ALL_COLS if k not in EDITABLE_COLS and k in df_in.columns]
    )

    edited = st.data_editor(
        disp,
        column_config=make_col_config(),
        disabled=disabled,
        hide_index=True,
        num_rows="fixed",
        width="stretch",
        key=key,
    )
    return edited, df_in[list(show.keys())].reset_index(drop=True)


def save_changes(edited: pd.DataFrame, original: pd.DataFrame, df_src: pd.DataFrame):
    """변경사항을 extra JSON에 저장."""
    extra = load_extra()
    inv_label = {v: k for k, v in ALL_COLS.items()}
    changed = 0
    for idx in range(len(edited)):
        sk = df_src.iloc[idx]["sitekey"] if idx < len(df_src) else None
        if sk is None:
            continue
        if sk not in extra:
            extra[sk] = {}
        for label in edited.columns:
            col_key = inv_label.get(label)
            if col_key not in EDITABLE_COLS:
                continue
            new_val = edited.iloc[idx][label]
            old_val = original.iloc[idx][label] if label in original.columns else ""
            new_str = "" if (new_val is None or (isinstance(new_val, float) and pd.isna(new_val))) else str(new_val)
            old_str = "" if (old_val is None or (isinstance(old_val, float) and pd.isna(old_val))) else str(old_val)
            if new_str != old_str:
                extra[sk][col_key] = new_val if new_str else ""
                log_change(sk, col_key, old_str, new_str)
                changed += 1
    save_extra(extra)
    return changed


# ── 탭1: 전체 Pool ──────────────────────────────────────────
with tab_all:
    f1, f2, f3 = st.columns([2, 2, 6])
    with f1:
        f_month = st.multiselect("Off 월", ["1월","2월","3월","4월"], default=["1월","2월","3월","4월"])
    with f2:
        f_biz = st.multiselect("사업유형", BIZ_OPTS, default=BIZ_OPTS)

    df_show = df_pool.copy()
    if f_month:
        df_show = df_show[df_show["off_month"].isin(f_month)]
    if f_biz:
        df_show = df_show[df_show["biz_type"].isin(f_biz)]

    st.caption(
        "🟡 **노란 셀**: 절감유형·투자비(분기·재배치)·폐국월_확정·절감금액_확정 수정 가능  "
        f"| 표시 **{len(df_show)}건**"
    )

    edited_df, orig_df = render_editor(df_show, key="ed_all")

    sc1, sc2, sc3 = st.columns([1, 1, 8])
    if sc1.button("💾 저장", type="primary", key="save_all"):
        cnt = save_changes(edited_df, orig_df, df_show)
        st.cache_data.clear()
        st.success(f"저장 완료 — {cnt}건 변경")
        if cnt > 0:
            st.rerun()

    if sc2.button("📥 다운로드", key="dl_all"):
        csv = df_show.to_csv(index=False, encoding="utf-8-sig").encode()
        st.download_button("CSV 다운로드", csv, "pool_전체.csv", mime="text/csv", key="dlbtn_all")


# ── 탭2: 후보 제출 목록 (4월) ───────────────────────────────
with tab_submit:
    df_sub = df_pool[df_pool["off_month"] == "4월"].copy()
    st.markdown(f"**4월 본사 제출 후보 — {len(df_sub)}건** · 읽기 전용")
    st.caption("폐국월_확정·절감금액_확정은 본사 승인 후 전체 Pool 탭에서 입력")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("제출 건수",  f"{len(df_sub)}건")
    c2.metric("임차+전기", f"{(df_sub['sav_type']=='임차+전기').sum()}건")
    c3.metric("전기만",    f"{(df_sub['sav_type']=='전기만').sum()}건")
    c4.metric("절감없음",  f"{(df_sub['sav_type']=='절감없음').sum()}건")

    render_editor(df_sub, key="ed_sub", locked=True)

    if st.button("📥 제출 목록 다운로드"):
        csv = df_sub.to_csv(index=False, encoding="utf-8-sig").encode()
        st.download_button("CSV 다운로드", csv, "4월_제출목록.csv",
                           mime="text/csv", key="dlbtn_sub")


# ── 탭3: 미반영 ─────────────────────────────────────────────
with tab_nr:
    df_nr = df[df.get("pool_yn", pd.Series("반영", index=df.index)) == "미반영"].copy()
    st.markdown(f"**미반영 목록 — {len(df_nr)}건**")
    if df_nr.empty:
        st.info("미반영 항목이 없습니다.")
    else:
        render_editor(df_nr, key="ed_nr", locked=True)
        if st.button("📥 미반영 목록 다운로드"):
            csv = df_nr.to_csv(index=False, encoding="utf-8-sig").encode()
            st.download_button("CSV 다운로드", csv, "미반영목록.csv",
                               mime="text/csv", key="dlbtn_nr")


# ── 탭4: 변경 이력 ──────────────────────────────────────────
with tab_log:
    st.markdown("##### 변경 이력")
    df_log = load_log()
    if df_log.empty:
        st.info("아직 변경 이력이 없습니다.")
    else:
        st.dataframe(
            df_log[["ts","user","sitekey","col","old","new"]].sort_values("ts", ascending=False),
            width="stretch",
            hide_index=True,
        )