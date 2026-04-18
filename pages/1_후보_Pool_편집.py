"""
pages/1_후보_Pool_편집.py

구조:
- 원시 데이터 포맷 그대로 유지
- 오른쪽 끝 추가 컬럼: 절감유형 · 투자비 · BEP(자동) · 제출여부(4월/5월/6월...) · 본사확정 · 비고
- 탭: 전체 Pool | 변경 이력
- 미반영 탭 삭제
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
.stTabs [data-baseweb="tab-list"]{gap:0;border-bottom:1px solid rgba(128,128,128,0.15)}
.stTabs [data-baseweb="tab"]{padding:8px 18px;font-size:12px;font-weight:500;border-bottom:2px solid transparent}
.stTabs [aria-selected="true"]{border-bottom:2px solid #1A6FC4}
#MainMenu,footer,header{visibility:hidden}
</style>
""", unsafe_allow_html=True)

C = dict(blue="#1A6FC4", green="#2D7D46", amber="#B45309",
         red="#C0392B", purple="#5B4DA0", gray="#6B7280")
HONBU_COLOR = {"수도권":C["blue"],"04.중부":C["green"],"동부":C["amber"],"서부":C["purple"]}

BIZ_OPTS    = ["단순폐국", "이설후폐국", "최적화후폐국"]
SAV_OPTS    = ["임차+전기", "전기만", "절감없음"]
YN_OPTS     = ["반영", "미반영"]
REASON_OPTS = ["","LOS 반경내 당사 Site 없음","공용 사이트 임차 해지 불가",
               "아파트 일부 Sitekey","잔여장비 있음","이설 미완료","본사 반려"]
MONTH_OPTS  = [""] + MONTH_ORDER   # 폐국월 확정용 드롭다운

# 제출 여부 컬럼 (4월~6월 각각 독립 컬럼)
# 향후 7월~12월 추가 시 여기만 확장
SUBMIT_MONTHS = ["4월", "5월", "6월"]

# ── 편집 가능 추가 컬럼 정의 ─────────────────────────────────
# key: 내부 컬럼명 / value: 화면 표시 레이블
EXTRA_EDITABLE = {
    "sav_type":      "절감유형",
    "inv_bun":       "투자비_분기(만)",
    "inv_bae":       "투자비_재배치(만)",
    # 자동 계산 (읽기전용)
    "savings_ann":   "절감금액_자동(만)",
    "bep_months":    "BEP(개월)",
    "net_savings":   "순절감(만)",
    # 제출 여부 (월별)
    **{"submit_{}".format(m): "{}제출".format(m) for m in SUBMIT_MONTHS},
    # 본사 확정
    "confirm_month": "폐국월_확정",
    "savings_fix":   "절감금액_확정(만)",
    "note":          "비고",
}
# 실제로 사용자가 편집할 수 있는 키
EDITABLE_KEYS = {
    "sav_type", "inv_bun", "inv_bae",
    *["submit_{}".format(m) for m in SUBMIT_MONTHS],
    "confirm_month", "savings_fix", "note",
}

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
            .format(href, bg, fw, clr, label), unsafe_allow_html=True)

    st.divider()

    sel_honbu = st.selectbox(
        "본부 선택", options=HONBU_ORDER,
        index=HONBU_ORDER.index(DEFAULT_HONBU), key="sel_honbu")
    hcolor = HONBU_COLOR.get(sel_honbu, C["blue"])
    goal   = HONBU_GOAL.get(sel_honbu, ANNUAL_GOAL)

    st.divider()
    st.markdown('<div style="font-size:10px;font-weight:600;opacity:.4;text-transform:uppercase;letter-spacing:.06em;padding-bottom:6px">필터</div>', unsafe_allow_html=True)

    sel_months = st.multiselect(
        "Off 월", options=MONTH_ORDER,
        default=["1월","2월","3월","4월"], key="f_month")
    sel_biz = st.multiselect(
        "사업유형", options=BIZ_OPTS, default=BIZ_OPTS, key="f_biz")
    sel_sav = st.multiselect(
        "절감유형", options=SAV_OPTS, default=SAV_OPTS, key="f_sav")

    st.divider()
    main_path = MAIN_FILES.get(sel_honbu, MAIN_FILES[DEFAULT_HONBU])
    st.markdown('<div style="font-size:10px;font-weight:600;opacity:.4;text-transform:uppercase;letter-spacing:.06em;padding-bottom:6px">데이터 파일</div>', unsafe_allow_html=True)
    st.markdown(("🟢" if main_path.exists() else "🟡") + " 원시데이터.xlsx")
    st.markdown(("🟢" if RENT_FILE.exists() else "🟡") + " 임차_전기DB.xlsx")
    if not main_path.exists():
        st.caption("⚠️ 샘플 데이터 사용 중")
    if st.button("🔄 새로고침"):
        st.cache_data.clear()
        st.rerun()

# ── 데이터 로드 ──────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def get_all(honbu, mhash, rhash):
    df_raw  = load_raw(mhash, honbu)
    df_rent = get_rent_data(df_raw)
    extra   = load_extra()

    # 제출 여부 컬럼 extra_cols에 추가
    df      = apply_extra(df_rent, extra)

    # submit_4월 등 컬럼이 없으면 빈값으로 초기화
    for m in SUBMIT_MONTHS:
        col = "submit_{}".format(m)
        if col not in df.columns:
            df[col] = df["sitekey"].map(
                lambda sk, c=col: extra.get(sk, {}).get(c, ""))

    return calc_savings(df)

with st.spinner("{} 데이터 로딩 중…".format(sel_honbu)):
    df_all = get_all(
        sel_honbu,
        file_hash(MAIN_FILES.get(sel_honbu, MAIN_FILES[DEFAULT_HONBU])),
        file_hash(RENT_FILE),
    )

# Pool 대상 = 정상 + 반영
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

# 임차·전기 출처 표시
from utils.data_loader import query_rent_from_db
_db_test = query_rent_from_db([])
if isinstance(_db_test, pd.DataFrame) and not _db_test.empty:
    src_label, src_bg, src_fg = "1순위: DB 연결", "#D1FAE5", "#065F46"
elif RENT_FILE.exists():
    src_label, src_bg, src_fg = "2순위: 임차_전기DB.xlsx", "#FEF3C7", "#92400E"
else:
    src_label, src_bg, src_fg = "3순위: 원시파일 P·Q열", "#F3F4F6", "#6B7280"

st.markdown(
    '임차·전기 데이터 출처: '
    '<span class="src-tag" style="background:{};color:{}">{}</span>'.format(
        src_bg, src_fg, src_label),
    unsafe_allow_html=True)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ── 요약 KPI ─────────────────────────────────────────────────
df_conf = df_pool[df_pool["off_month"].isin(CONFIRMED)]
total_c = len(df_conf)
pct_c   = round(total_c / goal * 100, 1)

def kpi_sm(label, value, sub, color):
    return (
        '<div class="kpi-sm"><div class="kpi-sm-acc" style="background:{c}"></div>'
        '<div style="padding-left:8px">'
        '<div class="kpi-sm-lbl">{lbl}</div>'
        '<div class="kpi-sm-val" style="color:{c}">{val}</div>'
        '<div class="kpi-sm-sub">{sub}</div>'
        '</div></div>'
    ).format(c=color, lbl=label, val=value, sub=sub)

k1,k2,k3,k4,k5 = st.columns(5)
k1.markdown(kpi_sm("Pool 전체",  str(len(df_pool))+"건", "반영 대상", hcolor), unsafe_allow_html=True)
k2.markdown(kpi_sm("1~3월 실적", str(total_c)+"건", "달성률 {}%".format(pct_c), hcolor), unsafe_allow_html=True)
k3.markdown(kpi_sm("4월 후보",   str((df_pool["off_month"]=="4월").sum())+"건", "검토중", C["amber"]), unsafe_allow_html=True)
k4.markdown(kpi_sm("임차+전기",  str((df_pool["sav_type"]=="임차+전기").sum())+"건", "절감유형", C["green"]), unsafe_allow_html=True)
k5.markdown(kpi_sm("투자비 발생",str((df_pool["inv_total"]>0).sum())+"건", "최적화후폐국", C["red"]), unsafe_allow_html=True)

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# ── 탭 ───────────────────────────────────────────────────────
tab_pool, tab_log = st.tabs(["  전체 Pool  ", "  변경 이력  "])

# ────────────────────────────────────────────────────────────
# 컬럼 구성:
#   [원시 데이터 컬럼] + [임차·전기 조인] + [추가 편집 컬럼]
#
# 원시 데이터 컬럼은 읽기전용으로 표시
# 추가 컬럼에서 노란 셀(EDITABLE_KEYS)만 편집 가능
# ────────────────────────────────────────────────────────────

# 원시 컬럼 (실제 존재하는 것만)
RAW_COLS = {
    "sitekey":     "Sitekey",
    "site_name":   "국소명",
    "honbu":       "본부",
    "biz_type":    "사업유형",
    "tosi":        "통시구분",
    "off_month":   "Off 월",
    "close_month": "폐국 월",
    "pool_yn":     "반영여부",
    "voc":         "VoC",
    # 임차·전기 조인 결과 (읽기전용)
    "rent_ann":    "연임차료(만)",
    "elec_ann":    "연전기료(만)",
}

# 추가 컬럼 표시 순서 (원시 데이터 오른쪽 끝에 붙음)
EXTRA_COLS_ORDERED = [
    ("sav_type",      "절감유형",           "edit"),
    ("inv_bun",       "투자비_분기(만)",     "edit"),
    ("inv_bae",       "투자비_재배치(만)",   "edit"),
    ("savings_ann",   "절감금액_자동(만)",   "readonly"),
    ("bep_months",    "BEP(개월)",           "readonly"),
    ("net_savings",   "순절감(만)",          "readonly"),
] + [
    ("submit_{}".format(m), "{}제출".format(m), "edit") for m in SUBMIT_MONTHS
] + [
    ("confirm_month", "폐국월_확정",         "edit"),
    ("savings_fix",   "절감금액_확정(만)",   "edit"),
    ("note",          "비고",                "edit"),
]

# 전체 컬럼 라벨 맵
ALL_LABELS = {**RAW_COLS, **{k: v for k, v, _ in EXTRA_COLS_ORDERED}}
READONLY_SET = (
    set(RAW_COLS.keys()) |
    {k for k, _, mode in EXTRA_COLS_ORDERED if mode == "readonly"}
)


def build_col_config():
    L = ALL_LABELS
    cfg = {}

    # 제출 여부 — 체크박스
    for m in SUBMIT_MONTHS:
        k = "submit_{}".format(m)
        if k in L:
            cfg[L[k]] = st.column_config.CheckboxColumn(L[k], width="small")

    # 드롭다운
    cfg[L["sav_type"]]      = st.column_config.SelectboxColumn(
        L["sav_type"], options=SAV_OPTS, width="medium")
    cfg[L["pool_yn"]]       = st.column_config.SelectboxColumn(
        L["pool_yn"], options=YN_OPTS, width="small")
    cfg[L["confirm_month"]] = st.column_config.SelectboxColumn(
        L["confirm_month"], options=MONTH_OPTS, width="small")

    # 숫자
    for k in ("rent_ann","elec_ann","inv_bun","inv_bae",
              "savings_ann","net_savings","savings_fix"):
        if k in L:
            cfg[L[k]] = st.column_config.NumberColumn(L[k], format="%.0f", width="small")
    if "bep_months" in L:
        cfg[L["bep_months"]] = st.column_config.NumberColumn(
            L["bep_months"], format="%d 개월", width="small")

    # 텍스트
    if "note" in L:
        cfg[L["note"]] = st.column_config.TextColumn(L["note"], width="medium")

    return cfg


def make_display_df(df_in: pd.DataFrame) -> pd.DataFrame:
    """원시 컬럼 + 추가 컬럼 순서로 표시용 DataFrame 구성."""
    cols = []
    # 원시 컬럼
    for k in RAW_COLS:
        if k in df_in.columns:
            cols.append(k)
    # 추가 컬럼 (오른쪽 끝)
    for k, _, _ in EXTRA_COLS_ORDERED:
        if k in df_in.columns and k not in cols:
            cols.append(k)

    disp = df_in[cols].copy()

    # submit_* 컬럼을 bool로 변환 (체크박스용)
    for m in SUBMIT_MONTHS:
        col = "submit_{}".format(m)
        if col in disp.columns:
            disp[col] = disp[col].apply(
                lambda v: True if str(v).strip().lower() in ("true","1","y","yes","제출") else False
            )

    disp = disp.rename(columns=ALL_LABELS)
    return disp


def render_editor(df_in: pd.DataFrame, key: str, locked: bool = False):
    disp = make_display_df(df_in)
    disabled = (
        list(disp.columns)
        if locked
        else [ALL_LABELS[k] for k in READONLY_SET if k in ALL_LABELS and ALL_LABELS[k] in disp.columns]
    )
    edited = st.data_editor(
        disp,
        column_config=build_col_config(),
        disabled=disabled,
        hide_index=True,
        num_rows="fixed",
        width="stretch",
        key=key,
    )
    return edited, disp


def save_edits(edited: pd.DataFrame, original: pd.DataFrame, df_src: pd.DataFrame):
    """변경분만 _extra_cols.json에 저장."""
    extra   = load_extra()
    inv_lbl = {v: k for k, v in ALL_LABELS.items()}
    changed = 0

    for i in range(min(len(edited), len(df_src))):
        sk = df_src.iloc[i]["sitekey"]
        if sk not in extra:
            extra[sk] = {}

        for col_label in edited.columns:
            col_key = inv_lbl.get(col_label)
            if not col_key or col_key not in EDITABLE_KEYS:
                continue

            new_val = edited.iloc[i][col_label]
            old_val = original.iloc[i][col_label] if col_label in original.columns else ""

            # bool 처리 (submit_* 컬럼)
            if isinstance(new_val, bool):
                new_s = "제출" if new_val else ""
            else:
                new_s = "" if (new_val is None or (isinstance(new_val, float) and pd.isna(new_val))) else str(new_val)

            if isinstance(old_val, bool):
                old_s = "제출" if old_val else ""
            else:
                old_s = "" if (old_val is None or (isinstance(old_val, float) and pd.isna(old_val))) else str(old_val)

            if new_s != old_s:
                extra[sk][col_key] = new_s
                log_change(sk, col_key, old_s, new_s)
                changed += 1

    save_extra(extra)
    return changed


# ════════ TAB 1: 전체 Pool ════════════════════════════════════
with tab_pool:
    # 필터 적용
    df_show = df_pool.copy()
    if sel_months: df_show = df_show[df_show["off_month"].isin(sel_months)]
    if sel_biz:    df_show = df_show[df_show["biz_type"].isin(sel_biz)]
    if sel_sav:    df_show = df_show[df_show["sav_type"].isin(sel_sav)]

    st.markdown(
        '<div style="font-size:11px;opacity:.5;padding:4px 0 8px">'
        '🟡 <b>편집 가능 컬럼</b>: 절감유형 · 투자비(분기·재배치) · '
        '4~6월제출(체크박스) · 폐국월_확정 · 절감금액_확정 · 비고 &nbsp;|&nbsp; '
        '표시 <b>{}</b>건</div>'.format(len(df_show)),
        unsafe_allow_html=True)

    edited_df, orig_df = render_editor(df_show.reset_index(drop=True), "ed_pool")

    sc1, sc2, _ = st.columns([1, 1, 8])
    if sc1.button("💾 저장", type="primary", key="save_pool"):
        cnt = save_edits(edited_df, orig_df, df_show.reset_index(drop=True))
        st.cache_data.clear()
        if cnt:
            st.success("저장 완료 — {}건 변경".format(cnt))
            st.rerun()
        else:
            st.info("변경된 항목이 없습니다.")

    if sc2.button("📥 CSV 다운로드", key="dl_pool"):
        csv = df_show.to_csv(index=False, encoding="utf-8-sig").encode()
        st.download_button("다운로드", csv, "pool_{}.csv".format(sel_honbu),
                           mime="text/csv", key="dlbtn_pool")


# ════════ TAB 2: 변경 이력 ════════════════════════════════════
with tab_log:
    st.markdown("##### 변경 이력")
    df_log = load_log()
    if df_log.empty:
        st.info("아직 변경 이력이 없습니다.")
    else:
        st.dataframe(
            df_log[["ts","user","sitekey","col","old","new"]]
              .sort_values("ts", ascending=False)
              .head(200),
            width="stretch",
            hide_index=True,
        )