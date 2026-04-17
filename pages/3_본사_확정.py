"""
pages/3_본사_확정.py
"""

import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.data_loader import load_main, _file_hash, MAIN_FILE, _make_sample_main, CHANGES_FILE
from utils.calc import calc_savings

st.set_page_config(page_title="본사 확정 처리", layout="wide")
st.markdown("<style>.block-container{padding-top:1rem}[data-testid='stSidebar']{min-width:200px;max-width:220px}</style>",
            unsafe_allow_html=True)

CONFIRMED_MON = {"1월","2월","3월"}

@st.cache_data(show_spinner="데이터 로딩 중…")
def get_data():
    mh = _file_hash(MAIN_FILE)
    df = load_main(mh) if MAIN_FILE.exists() else _make_sample_main()
    return calc_savings(df[df["is_pool"]].copy())

df = get_data()

# ── 확정 상태 세션 관리 ──────────────────────────────────────
if "confirmed_set" not in st.session_state:
    # 1~3월은 이미 확정된 것으로 초기화
    st.session_state.confirmed_set = set(
        df[df["off_month"].isin(CONFIRMED_MON)]["sitekey"].tolist()
    )
if "close_month_map" not in st.session_state:
    st.session_state.close_month_map = {
        sk: m for sk, m in
        zip(df[df["off_month"].isin(CONFIRMED_MON)]["sitekey"],
            df[df["off_month"].isin(CONFIRMED_MON)]["off_month"])
    }
if "final_amt_map" not in st.session_state:
    st.session_state.final_amt_map = {}

# ── 헤더 ─────────────────────────────────────────────────────
st.markdown("## 본사 확정 처리")

# 4월 제출 대상
df_4 = df[(df["off_month"] == "4월") & (df["pool_yn"] == "반영")].copy()
n_total    = len(df_4)
n_confirmed = len([sk for sk in df_4["sitekey"] if sk in st.session_state.confirmed_set])
n_wait     = n_total - n_confirmed

k1, k2, k3 = st.columns(3)
k1.metric("4월 제출 건수",  f"{n_total}건")
k2.metric("확정 완료",     f"{n_confirmed}건", f"{round(n_confirmed/n_total*100) if n_total else 0}%")
k3.metric("대기 중",       f"{n_wait}건")

st.info(
    "⚡ **진행 흐름:** 본사 승인 → 폐국월 입력 → 절감금액 확인 → **확정** 클릭 → 잠금  \n"
    "확정 후 수정은 사유 입력 후 **잠금 해제** 버튼을 사용하세요."
)

# ── 확정 처리 테이블 ─────────────────────────────────────────
st.divider()
st.markdown("##### 4월 제출 후보 — 확정 처리")

for _, row in df_4.iterrows():
    sk        = row["sitekey"]
    site_name = row.get("site_name", sk)
    biz       = row.get("biz_type","—")
    sav       = row.get("sav_type","—")
    est_amt   = round(row.get("savings_ann",0) / 10000, 2)
    is_done   = sk in st.session_state.confirmed_set

    BIZ_COLORS = {"단순폐국":"#E6F1FB,#185FA5","이설후폐국":"#EEEDFE,#534AB7","최적화후폐국":"#E1F5EE,#085041"}
    SAV_COLORS = {"임차+전기":"#EAF3DE,#3B6D11","전기만":"#FAEEDA,#854F0B","절감없음":"#F1EFE8,#5F5E5A"}
    biz_bg, biz_fg = BIZ_COLORS.get(biz,"#F1EFE8,#888").split(",")
    sav_bg, sav_fg = SAV_COLORS.get(sav,"#F1EFE8,#888").split(",")

    row_bg = "#F8F6FF" if is_done else "var(--background-color)"
    with st.container():
        st.markdown(f'<div style="background:{row_bg};border-radius:8px;padding:10px 14px;margin-bottom:6px;border:0.5px solid var(--secondary-background-color)">', unsafe_allow_html=True)
        c1, c2, c3, c4, c5, c6, c7 = st.columns([2.5, 1.5, 1, 1, 1.2, 1.2, 1])

        with c1:
            st.markdown(
                f'<div style="font-size:12px;font-weight:500">{site_name}</div>'
                f'<div style="font-size:9px;color:#888;margin-top:1px">{sk}</div>',
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f'<span style="background:{biz_bg};color:{biz_fg};border-radius:4px;padding:1px 6px;font-size:10px;font-weight:500">{biz}</span> '
                f'<span style="background:{sav_bg};color:{sav_fg};border-radius:4px;padding:1px 6px;font-size:10px;font-weight:500">{sav}</span>',
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(f'<div style="font-size:10px;color:#888">예상 절감</div><div style="font-size:12px;font-weight:500;color:#185FA5">{est_amt}억</div>', unsafe_allow_html=True)
        with c4:
            if is_done:
                close = st.session_state.close_month_map.get(sk, "4월")
                st.markdown(f'<div style="font-size:10px;color:#888">폐국월</div><div style="font-size:12px;color:#534AB7;font-weight:500">{close}</div>', unsafe_allow_html=True)
            else:
                close_input = st.selectbox("폐국월", ["","4월","5월","6월"],
                                           key=f"close_{sk}", label_visibility="collapsed")
        with c5:
            if is_done:
                final = st.session_state.final_amt_map.get(sk, est_amt)
                st.markdown(f'<div style="font-size:10px;color:#888">확정 절감금액</div><div style="font-size:12px;color:#3B6D11;font-weight:500">{final}억</div>', unsafe_allow_html=True)
            else:
                final_input = st.number_input("확정 절감(억)", min_value=0.0, value=est_amt,
                                              step=0.1, format="%.2f",
                                              key=f"amt_{sk}", label_visibility="collapsed")
        with c6:
            if is_done:
                st.markdown('<span style="background:#EEEDFE;color:#534AB7;border-radius:4px;padding:2px 8px;font-size:10px;font-weight:500">✓ 확정 완료</span>',
                            unsafe_allow_html=True)
            else:
                if st.button("✅ 확정", key=f"conf_{sk}", type="primary"):
                    ci = st.session_state.get(f"close_{sk}", "")
                    if not ci:
                        st.error("폐국월을 먼저 선택하세요.")
                    else:
                        st.session_state.confirmed_set.add(sk)
                        st.session_state.close_month_map[sk] = ci
                        st.session_state.final_amt_map[sk]   = st.session_state.get(f"amt_{sk}", est_amt)
                        st.rerun()
        with c7:
            if is_done and sk not in {s for s in df[df["off_month"].isin(CONFIRMED_MON)]["sitekey"]}:
                if st.button("🔓", key=f"unlock_{sk}", help="잠금 해제"):
                    st.session_state.confirmed_set.discard(sk)
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

st.divider()

# ── 변경 이력 ────────────────────────────────────────────────
st.markdown("##### 변경 이력")
if CHANGES_FILE.exists():
    with open(CHANGES_FILE, encoding="utf-8") as f:
        logs = json.load(f)
    df_log = pd.DataFrame(logs)
    if not df_log.empty:
        st.dataframe(df_log[["ts","user","sitekey","col","old","new"]].tail(50),
                     width="stretch", hide_index=True)
    else:
        st.info("변경 이력이 없습니다.")
else:
    st.info("아직 변경 이력이 없습니다.")