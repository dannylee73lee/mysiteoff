"""
pages/1_후보_Pool_편집.py
- 원시 데이터 전체 컬럼 그대로 표시 (포맷 절대 유지)
- 편집 가능 컬럼을 오른쪽 끝에 추가
- 편집: 절감유형·투자비·4~6월제출·폐국월확정·절감금액확정·비고
"""
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.data_loader import (
    load_raw, enrich_rent, apply_extra,
    load_extra, save_extra, log_change, load_log,
    file_hash, MAIN_FILES, RENT_FILE,
    DEFAULT_HONBU, HONBU_ORDER, MONTH_ORDER,
    CONFIRMED, REVIEW, EXTRA_COLS, EDITABLE_EXTRA,
    SUBMIT_MONTHS, parse_off_month,
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
.src-tag{display:inline-block;border-radius:4px;padding:1px 6px;font-size:9px;font-weight:600;letter-spacing:.03em}
.stTabs [data-baseweb="tab-list"]{gap:0;border-bottom:1px solid rgba(128,128,128,0.15)}
.stTabs [data-baseweb="tab"]{padding:8px 18px;font-size:12px;font-weight:500;border-bottom:2px solid transparent}
.stTabs [aria-selected="true"]{border-bottom:2px solid #1A6FC4}
#MainMenu,footer,header{visibility:hidden}
</style>
""", unsafe_allow_html=True)

C = dict(blue="#1A6FC4", green="#2D7D46", amber="#B45309",
         red="#C0392B", purple="#5B4DA0", gray="#6B7280")
HONBU_COLOR = {"수도권":C["blue"],"04.중부":C["green"],"동부":C["amber"],"서부":C["purple"]}
BIZ_OPTS    = ["단순폐국","이설후폐국","최적화후폐국"]
SAV_OPTS    = ["임차+전기","전기만","절감없음"]
YN_OPTS     = ["반영","미반영"]
MONTH_OPTS  = [""] + MONTH_ORDER

# ── 사이드바 ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="padding:14px 4px 10px">'
        '<div style="font-size:13px;font-weight:700">📡 폐국 관리</div>'
        '</div>', unsafe_allow_html=True)
    st.divider()

    for label, href, active in [
        ("📊 메인 현황",      "/",   False),
        ("📋 후보 Pool 편집", "#",   True),
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
    sel_months = st.multiselect("Off 월", options=MONTH_ORDER,
                                 default=["1월","2월","3월","4월"], key="f_month")
    sel_biz    = st.multiselect("사업유형", options=BIZ_OPTS, default=BIZ_OPTS, key="f_biz")
    pool_only  = st.checkbox("반영 대상만 표시", value=True, key="pool_only")

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
    df_raw = load_raw(mhash, honbu)
    df     = enrich_rent(df_raw)          # 임차·전기 보강
    extra  = load_extra()
    df     = apply_extra(df, extra)       # 편집 컬럼 추가
    # 절감금액·BEP 자동 계산 (파생 컬럼 기반)
    df_calc = calc_savings(df, rent_col="_rent_ann", elec_col="_elec_ann",
                           sav_col="sav_type")
    return df_calc

with st.spinner("{} 데이터 로딩 중…".format(sel_honbu)):
    df_all = get_all(
        sel_honbu,
        file_hash(MAIN_FILES.get(sel_honbu, MAIN_FILES[DEFAULT_HONBU])),
        file_hash(RENT_FILE),
    )

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
    src_label, src_bg, src_fg = "3순위: 원시파일 AH·Q열", "#F3F4F6", "#6B7280"

st.markdown(
    '임차·전기 데이터 출처: '
    '<span class="src-tag" style="background:{};color:{}">{}</span>'.format(
        src_bg, src_fg, src_label),
    unsafe_allow_html=True)
st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ── KPI ──────────────────────────────────────────────────────
df_pool = df_all[
    (df_all["_site_err"] == "정상") &
    (df_all["_pool_yn"]  == "반영")
].copy()
df_conf = df_pool[df_pool["_off_month"].isin(CONFIRMED)]
total_c = len(df_conf)
pct_c   = round(total_c / goal * 100, 1) if goal else 0

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
k1.markdown(kpi_sm("Pool 전체",   str(len(df_pool))+"건",  "반영 대상", hcolor), unsafe_allow_html=True)
k2.markdown(kpi_sm("1~3월 실적",  str(total_c)+"건",       "달성률 {}%".format(pct_c), hcolor), unsafe_allow_html=True)
k3.markdown(kpi_sm("4월 후보",    str((df_pool["_off_month"]=="4월").sum())+"건", "검토중", C["amber"]), unsafe_allow_html=True)
k4.markdown(kpi_sm("임차+전기",   str((df_pool.get("sav_type","")=="임차+전기").sum())+"건", "절감유형", C["green"]), unsafe_allow_html=True)
k5.markdown(kpi_sm("투자비 발생", str((df_pool.get("_inv_total",pd.Series(0,index=df_pool.index))>0).sum())+"건", "최적화후폐국", C["red"]), unsafe_allow_html=True)

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# ── 탭 ───────────────────────────────────────────────────────
tab_pool, tab_log = st.tabs(["  전체 Pool  ", "  변경 이력  "])

# ════════ TAB 1: 전체 Pool ════════════════════════════════════
with tab_pool:

    # ── 필터 적용 ─────────────────────────────────────────────
    df_show = df_all.copy()

    if pool_only:
        df_show = df_show[df_show["_pool_yn"] == "반영"]
    if sel_months:
        df_show = df_show[df_show["_off_month"].isin(sel_months)]
    if sel_biz:
        df_show = df_show[df_show["_biz_type"].isin(sel_biz)]

    # ── 표시용 DataFrame 구성 ─────────────────────────────────
    # 원칙: 원시 파일 컬럼을 순서 그대로 앞에 배치
    #       파생 컬럼(_로 시작) 제외
    #       편집 컬럼을 오른쪽 끝에 추가

    # 원시 컬럼 (파생 컬럼 제외)
    raw_cols = [c for c in df_show.columns
                if not c.startswith("_")
                and c not in EXTRA_COLS
                and c not in ("savings_ann","inv_total","net_savings",
                               "savings_mon","bep_months","roi_pct")]

    # 편집 추가 컬럼 순서
    extra_cols_ordered = [
        "sav_type",       # 절감유형
        "inv_bun",        # 투자비_분기
        "inv_bae",        # 투자비_재배치
        "savings_ann",    # 절감금액_자동 (읽기전용)
        "bep_months",     # BEP (읽기전용)
        "net_savings",    # 순절감 (읽기전용)
    ] + ["submit_{}".format(m) for m in SUBMIT_MONTHS] + [
        "confirm_month",  # 폐국월_확정
        "savings_fix",    # 절감금액_확정
        "note",           # 비고
    ]
    extra_cols_exist = [c for c in extra_cols_ordered if c in df_show.columns]

    # 최종 표시 컬럼 = 원시 전체 + 편집 추가
    display_cols = raw_cols + extra_cols_exist
    df_disp = df_show[display_cols].reset_index(drop=True)

    # ── column_config 구성 ───────────────────────────────────
    col_config = {}

    # 편집 가능 컬럼 config
    sav_label     = "sav_type"      # 실제 컬럼명 (rename 안 함)
    col_config["sav_type"]      = st.column_config.SelectboxColumn(
        "절감유형", options=SAV_OPTS, width="medium")
    col_config["inv_bun"]       = st.column_config.NumberColumn(
        "투자비_분기(만)", format="%.0f", width="small")
    col_config["inv_bae"]       = st.column_config.NumberColumn(
        "투자비_재배치(만)", format="%.0f", width="small")
    col_config["savings_ann"]   = st.column_config.NumberColumn(
        "절감금액_자동(만)", format="%.0f", width="small")
    col_config["bep_months"]    = st.column_config.NumberColumn(
        "BEP(개월)", format="%d 개월", width="small")
    col_config["net_savings"]   = st.column_config.NumberColumn(
        "순절감(만)", format="%.0f", width="small")
    col_config["confirm_month"] = st.column_config.SelectboxColumn(
        "폐국월_확정", options=MONTH_OPTS, width="small")
    col_config["savings_fix"]   = st.column_config.NumberColumn(
        "절감금액_확정(만)", format="%.0f", width="small")
    col_config["note"]          = st.column_config.TextColumn(
        "비고", width="medium")
    for m in SUBMIT_MONTHS:
        col_config["submit_{}".format(m)] = st.column_config.CheckboxColumn(
            "{}제출".format(m), width="small")

    # 원시 컬럼 읽기전용 표시 (너비 자동)
    # 빈 열(헤더 None)은 숨기기
    hidden_cols = [c for c in raw_cols if c is None or str(c).strip() == "None"]

    # 편집 가능 키 집합
    EDITABLE_KEYS = {
        "sav_type","inv_bun","inv_bae",
        "confirm_month","savings_fix","note",
        *["submit_{}".format(m) for m in SUBMIT_MONTHS],
    }
    disabled_cols = [c for c in display_cols if c not in EDITABLE_KEYS]

    st.markdown(
        '<div style="font-size:11px;opacity:.5;padding:4px 0 8px">'
        '🟡 <b>편집 가능</b>: 절감유형 · 투자비(분기·재배치) · '
        '{}제출(체크박스) · 폐국월_확정 · 절감금액_확정 · 비고 &nbsp;|&nbsp; '
        '표시 <b>{}</b>건'.format('·'.join(SUBMIT_MONTHS), len(df_disp)) +
        '</div>',
        unsafe_allow_html=True)

    edited = st.data_editor(
        df_disp,
        column_config=col_config,
        disabled=disabled_cols,
        hide_index=True,
        num_rows="fixed",
        width="stretch",
        key="ed_pool",
        column_order=display_cols,
    )

    sc1, sc2, _ = st.columns([1, 1, 8])
    if sc1.button("💾 저장", type="primary", key="save_pool"):
        extra = load_extra()
        changed = 0
        for i in range(min(len(edited), len(df_show))):
            sk = df_show.iloc[i]["_sitekey"]
            if not sk:
                continue
            if sk not in extra:
                extra[sk] = {}
            for col_key in EDITABLE_KEYS:
                if col_key not in edited.columns:
                    continue
                new_val = edited.iloc[i][col_key]
                old_val = df_show.iloc[i].get(col_key, "")

                if col_key.startswith("submit_"):
                    new_s = "제출" if bool(new_val) else ""
                    old_s = "제출" if bool(old_val) else ""
                else:
                    new_s = "" if (new_val is None or (isinstance(new_val,float) and pd.isna(new_val))) else str(new_val)
                    old_s = "" if (old_val is None or (isinstance(old_val,float) and pd.isna(old_val))) else str(old_val)

                if new_s != old_s:
                    extra[sk][col_key] = new_s
                    log_change(sk, col_key, old_s, new_s)
                    changed += 1

        save_extra(extra)
        st.cache_data.clear()
        if changed:
            st.success("저장 완료 — {}건 변경".format(changed))
            st.rerun()
        else:
            st.info("변경된 항목이 없습니다.")

    if sc2.button("📥 CSV 다운로드", key="dl_pool"):
        csv = df_show[display_cols].to_csv(index=False, encoding="utf-8-sig").encode()
        st.download_button("다운로드", csv,
                           "pool_{}.csv".format(sel_honbu),
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
              .sort_values("ts", ascending=False).head(200),
            width="stretch", hide_index=True)