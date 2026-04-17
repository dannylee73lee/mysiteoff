"""
data_loader.py
--------------
Excel → DataFrame 로딩 및 Parquet 캐싱 유틸리티.

서버 파일 경로 설정:
    DATA_DIR : 원시 Excel 파일이 위치한 디렉터리
    MAIN_FILE : 중부 원시 데이터 파일명
    RENT_FILE : 임차·전기 DB 파일명
    INVEST_FILE: 투자비 수기 입력 파일명 (없으면 자동 생성)
    CHANGES_FILE: 사용자 편집 이력 저장 파일
"""

import os
import hashlib
import json
import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime

# ── 경로 설정 ──────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent
DATA_DIR   = BASE_DIR / "data"          # 서버 배포 시 실제 경로로 변경
CACHE_DIR  = DATA_DIR / "_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MAIN_FILE    = DATA_DIR / "중부_원시데이터.xlsx"
RENT_FILE    = DATA_DIR / "임차_전기DB.xlsx"
INVEST_FILE  = DATA_DIR / "투자비_입력.xlsx"
CHANGES_FILE = DATA_DIR / "변경이력.json"

# ── 사용하는 열 정의 ────────────────────────────────────────
MAIN_COLS = {
    "id":         "id",
    "sitekey":    "[ERP] Sitekey",
    "site_name":  "[ERP] 국소명",
    "honbu":      "[ERP] 본부",
    "network":    "[ERP] 사업망 구분",
    "status":     "[ERP] 운용 상태",
    "tosi":       "[ERP] 공대, Sub구분",
    "rent_no":    "[ERP] 임차물건번호",
    "elec_no":    "[ERP 전기물건] 전기료내역마스터",
    "rent_ann":   "[통합Eng DB] 연_임차_료",
    "elec_ann":   "[통합Eng DB] 연_전기_료",
    "site_err":   "사이트오류\n제외대상",
    "pool_yn":    "후보Pool\n반영여부",
    "pool_reason":"후보Pool\n미반영사유",
    "biz_type":   "사업유형",
    "off_month":  "Off 월",
    "close_month":"폐국 월",
    "voc":        "VoC",
    "type_cls":   "(최종)\n유형분류",
}

RENT_COLS = {
    "sitekey":   "[ERP] Sitekey",
    "rent_no":   "[ERP] 임차물건번호",
    "rent_ann":  "연환산임차료\n(통시+임차+수기)",
}

ELEC_COLS = {
    "sitekey":  "[ERP] Sitekey",
    "elec_no":  "[ERP 전기물건] 전기료내역마스터",
    "elec_ann": "[통합Eng DB] 연_전기_료",
}


# ── 파일 해시 (변경 감지용) ─────────────────────────────────
def _file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── 메인 원시 데이터 로드 ────────────────────────────────────
@st.cache_data(show_spinner="원시 데이터 로딩 중…")
def load_main(file_hash: str) -> pd.DataFrame:
    """
    중부 원시 Excel을 로드하고 필요한 열만 추출.
    file_hash 인자는 캐시 키용(변경 시 자동 재로딩).
    """
    if not MAIN_FILE.exists():
        return _make_sample_main()

    col_map = MAIN_COLS
    use_cols = list(col_map.values())

    df = pd.read_excel(
        MAIN_FILE,
        engine="openpyxl",
        usecols=lambda c: c in use_cols,
        dtype=str,
    )
    df = df.rename(columns={v: k for k, v in col_map.items() if v in df.columns})

    # 수치 변환
    for num_col in ("rent_ann", "elec_ann"):
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)

    # 기본 필터: 정상 + 반영
    df["is_pool"] = (
        (df.get("site_err", pd.Series(["정상"] * len(df))) == "정상") &
        (df.get("pool_yn",  pd.Series(["반영"]  * len(df))) == "반영")
    )
    return df


# ── 임차·전기 DB 로드 ────────────────────────────────────────
@st.cache_data(show_spinner="임차·전기 DB 로딩 중…")
def load_rent_elec(file_hash: str) -> pd.DataFrame:
    if not RENT_FILE.exists():
        return pd.DataFrame()

    df = pd.read_excel(
        RENT_FILE,
        engine="openpyxl",
        dtype=str,
    )
    for col in ("rent_ann", "elec_ann"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


# ── 투자비 데이터 로드/저장 ───────────────────────────────────
def load_invest() -> pd.DataFrame:
    cols = ["sitekey", "site_name", "off_month", "inv_bun", "inv_bae", "note"]
    if INVEST_FILE.exists():
        df = pd.read_excel(INVEST_FILE, engine="openpyxl", dtype=str)
        for c in ("inv_bun", "inv_bae"):
            df[c] = pd.to_numeric(df.get(c, 0), errors="coerce").fillna(0)
        return df
    return pd.DataFrame(columns=cols)


def save_invest(df: pd.DataFrame):
    df.to_excel(INVEST_FILE, index=False, engine="openpyxl")


# ── 변경 이력 저장 ───────────────────────────────────────────
def save_change_log(sitekey: str, col: str, old_val, new_val, user: str = "담당자"):
    log = []
    if CHANGES_FILE.exists():
        with open(CHANGES_FILE, encoding="utf-8") as f:
            log = json.load(f)
    log.append({
        "ts":      datetime.now().isoformat(timespec="seconds"),
        "user":    user,
        "sitekey": sitekey,
        "col":     col,
        "old":     str(old_val),
        "new":     str(new_val),
    })
    with open(CHANGES_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def load_change_log() -> pd.DataFrame:
    if not CHANGES_FILE.exists():
        return pd.DataFrame()
    with open(CHANGES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return pd.DataFrame(data)


# ── 샘플 데이터 (실제 파일 없을 때) ─────────────────────────
def _make_sample_main() -> pd.DataFrame:
    import random
    random.seed(42)

    HONBU    = "04.중부"
    BIZ      = ["단순폐국", "이설후폐국", "최적화후폐국"]
    SAV      = ["임차+전기", "전기만", "절감없음"]
    MONTHS   = ["1월", "2월", "3월", "4월"]
    NETWORKS = ["WCDMA", "LTE", "5G"]
    TOSI     = ["단독", "통시", "아파트", "공용"]

    # 실제 샘플 5건
    real = [
        dict(sitekey="CB111114172007443", site_name="석계WMC.56",      biz_type="단순폐국",    tosi="단독",  off_month="1월", rent_ann=0,    elec_ann=0,   sav_type="임차+전기", pool_yn="반영",   voc=""),
        dict(sitekey="CB111114342336093", site_name="청주공단5거리",    biz_type="단순폐국",    tosi="단독",  off_month="1월", rent_ann=1500, elec_ann=26,  sav_type="임차+전기", pool_yn="반영",   voc=""),
        dict(sitekey="CB111114373997427", site_name="청주운천초교",     biz_type="단순폐국",    tosi="단독",  off_month="1월", rent_ann=1500, elec_ann=29,  sav_type="임차+전기", pool_yn="반영",   voc=""),
        dict(sitekey="CN111114173921607", site_name="팔봉천송펜션",    biz_type="단순폐국",    tosi="통시",  off_month="3월", rent_ann=500,  elec_ann=33,  sav_type="전기만",   pool_yn="반영",   voc=""),
        dict(sitekey="CN111114100052041", site_name="입장가산2DOR",    biz_type="최적화후폐국", tosi="통시",  off_month="3월", rent_ann=0,    elec_ann=1,   sav_type="절감없음", pool_yn="미반영", voc=""),
    ]

    rows = list(real)
    # 추가 임의 데이터 생성
    targets = {"1월": 109, "2월": 48, "3월": 77, "4월": 84}
    for month, cnt in targets.items():
        for i in range(cnt):
            biz = random.choices(BIZ, weights=[0.65, 0.22, 0.13])[0]
            tosi_v = random.choices(TOSI, weights=[0.55, 0.25, 0.12, 0.08])[0]
            if tosi_v == "단독":
                sav = random.choices(SAV, weights=[0.75, 0.15, 0.10])[0]
            elif tosi_v in ("통시", "공용"):
                sav = random.choices(SAV, weights=[0.20, 0.50, 0.30])[0]
            else:
                sav = random.choices(SAV, weights=[0.05, 0.25, 0.70])[0]

            rent = random.choice([0, 500, 600, 800, 1000, 1200, 1500, 1800, 2400, 3600]) if sav != "절감없음" else 0
            elec = random.randint(5, 60)
            has_voc = random.random() < 0.03
            rows.append(dict(
                sitekey     = f"CB{random.randint(100000000000000,999999999999999)}",
                site_name   = f"임의사이트_{month}_{i+1}",
                biz_type    = biz,
                tosi        = tosi_v,
                off_month   = month,
                rent_ann    = rent,
                elec_ann    = elec,
                sav_type    = sav,
                pool_yn     = "반영" if random.random() > 0.12 else "미반영",
                voc         = "Y" if has_voc else "",
            ))

    df = pd.DataFrame(rows)
    df["honbu"]       = HONBU
    df["site_err"]    = "정상"
    df["close_month"] = ""
    df["is_pool"]     = df["pool_yn"] == "반영"
    df["inv_bun"]     = 0
    df["inv_bae"]     = 0

    # 최적화후폐국 일부에 투자비 부여
    mask_opt = (df["biz_type"] == "최적화후폐국") & (df["sav_type"] != "절감없음")
    df.loc[mask_opt & (df.index % 2 == 0), "inv_bun"] = \
        df.loc[mask_opt & (df.index % 2 == 0), "rent_ann"].apply(
            lambda x: round(x * random.uniform(0.2, 0.6) / 100) * 100 if x else 0
        )
    return df