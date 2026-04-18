"""
data_loader.py
==============
임차·전기 데이터 조회 우선순위:
  1순위: DB 연결 (Athena/SQLite — db_query.py 구현 시 활성화)
  2순위: data_site/임차_전기DB.xlsx  (Sitekey 기준 조인)
  3순위: 원시 데이터 내 P열([통합Eng DB] 연_임차_료), Q열([통합Eng DB] 연_전기_료) 직접 참조

본부 목록: 수도권 / 04.중부 / 동부 / 서부
Off 월 범위: 1~6월
"""

import hashlib, json
import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime

# ── 경로 ─────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent
DATA_DIR   = BASE_DIR / "data_site"
EXTRA_FILE = DATA_DIR / "_extra_cols.json"
LOG_FILE   = DATA_DIR / "_change_log.json"

# 원시 데이터 — 본부별 파일 경로 매핑
# 단일 파일인 경우 모두 같은 파일을 가리켜도 됨
MAIN_FILES = {
    "수도권":  DATA_DIR / "수도권_원시데이터.xlsx",
    "04.중부": DATA_DIR / "중부_원시데이터.xlsx",
    "동부":    DATA_DIR / "동부_원시데이터.xlsx",
    "서부":    DATA_DIR / "서부_원시데이터.xlsx",
}
RENT_FILE = DATA_DIR / "임차_전기DB.xlsx"

# 편의용: 기본 본부
DEFAULT_HONBU = "04.중부"
MAIN_FILE     = MAIN_FILES[DEFAULT_HONBU]   # 기존 코드 호환용

HONBU_ORDER = ["수도권", "04.중부", "동부", "서부"]
MONTH_ORDER = [f"{i}월" for i in range(1, 7)]   # 1~6월
CONFIRMED   = {"1월", "2월", "3월"}
REVIEW      = {"4월"}

# ── 원시 데이터 컬럼 매핑 ────────────────────────────────────
COL_MAP = {
    "facility_code": "[ERP]통합시설코드",      # E열 (조인 보조키)
    "sitekey":       "[ERP] Sitekey",           # M열 (주 키)
    "site_name":     "[ERP] 국소명",
    "honbu":         "[ERP] 본부",
    "network":       "[ERP] 사업망 구분",
    "status":        "[ERP] 운용 상태",
    "tosi":          "[ERP] 공대, Sub구분",
    "site_err":      "사이트오류\n제외대상",
    "pool_yn":       "후보Pool\n반영여부",
    "pool_reason":   "후보Pool\n미반영사유",
    "biz_type":      "사업유형",
    "off_month":     "Off 월",
    "close_month":   "폐국 월",
    "voc":           "VoC",
    "type_cls":      "(최종)\n유형분류",
    # 3순위 fallback — 원시 파일 내 임차·전기 컬럼
    "rent_ann_raw":  "[통합Eng DB] 연_임차_료",   # P열
    "elec_ann_raw":  " [통합Eng DB] 연_전기_료",  # Q열 (앞 공백 주의)
}

# 임차·전기 DB 컬럼 매핑 (2순위)
RENT_COL_MAP = {
    "sitekey":    "[ERP] Sitekey",
    "rent_no":    "[ERP] 임차물건번호",
    "elec_no":    "[ERP 전기물건] 전기료내역마스터",
    "rent_ann":   "[통합Eng DB] 연_임차_료",
    "elec_ann":   " [통합Eng DB] 연_전기_료",
}

# 사용자 편집 컬럼 (T~AC열)
EXTRA_COLS = {
    "sav_type":      "절감유형",
    "inv_bun":       "투자비_분기",
    "inv_bae":       "투자비_재배치",
    "confirm_month": "폐국월_확정",
    "savings_fix":   "절감금액_확정",
    "note":          "비고",
}
EDITABLE_EXTRA = set(EXTRA_COLS.keys())


# ── 파일 해시 ────────────────────────────────────────────────
def file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── 1순위: DB 조회 (Athena / 내부 DB) ───────────────────────
def query_rent_from_db(sitekeys: list) -> pd.DataFrame:
    """
    1순위 임차·전기 데이터 조회.
    실제 DB 연결 구현 시 이 함수를 수정하세요.
    예) Athena, SQLite, PostgreSQL 등

    Returns:
        DataFrame with columns: sitekey, rent_ann, elec_ann
        (조회 실패 또는 미구현 시 빈 DataFrame 반환 → 2순위로 fallback)
    """
    try:
        # ── Athena 예시 (boto3 설치 필요) ──
        # import boto3
        # client = boto3.client('athena', region_name='ap-northeast-2')
        # query  = "SELECT sitekey, rent_ann, elec_ann FROM rent_db WHERE sitekey IN ({})".format(
        #     ",".join(["'{}'".format(k) for k in sitekeys])
        # )
        # ... (Athena 쿼리 실행 로직)
        # return df_result

        # ── SQLite 예시 ──
        # import sqlite3
        # conn = sqlite3.connect(DATA_DIR / "rent.db")
        # df   = pd.read_sql("SELECT ...", conn, params=[...])
        # return df

        return pd.DataFrame()   # 미구현: 빈 DataFrame → 2순위 fallback
    except Exception:
        return pd.DataFrame()


# ── 2순위: 임차_전기DB.xlsx 로드 ─────────────────────────────
@st.cache_data(show_spinner=False)
def load_rent_excel(fhash: str) -> pd.DataFrame:
    """2순위 — 임차_전기DB.xlsx 로드."""
    if not RENT_FILE.exists():
        return pd.DataFrame()

    target = list(RENT_COL_MAP.values())
    df = pd.read_excel(
        RENT_FILE, engine="openpyxl",
        usecols=lambda c: c in target,
        dtype=str,
    )
    inv = {v: k for k, v in RENT_COL_MAP.items() if v in df.columns}
    df  = df.rename(columns=inv)

    # Q열 앞 공백 대응
    for alt in (" [통합Eng DB] 연_전기_료", "[통합Eng DB] 연_전기_료"):
        if alt in df.columns and "elec_ann" not in df.columns:
            df = df.rename(columns={alt: "elec_ann"})

    for c in ("rent_ann", "elec_ann"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    if "sitekey" in df.columns:
        df = df.drop_duplicates(subset="sitekey", keep="first")
    return df


# ── 임차·전기 데이터 통합 조회 ───────────────────────────────
def get_rent_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    우선순위에 따라 임차·전기 데이터를 조회하고 원시 데이터에 병합.

    1순위: DB 조회 → sitekey 기준 merge
    2순위: 임차_전기DB.xlsx → sitekey 기준 merge
    3순위: 원시 데이터 P·Q열 직접 사용
    """
    sitekeys = df_raw["sitekey"].tolist() if "sitekey" in df_raw.columns else []

    # ── 1순위: DB ───────────────────────────────────────────
    df_db = query_rent_from_db(sitekeys)
    if not df_db.empty and "sitekey" in df_db.columns:
        need = [c for c in ("rent_ann","elec_ann") if c in df_db.columns]
        if need:
            df_merged = df_raw.merge(
                df_db[["sitekey"] + need].drop_duplicates("sitekey"),
                on="sitekey", how="left",
            )
            for c in ("rent_ann","elec_ann"):
                df_merged[c] = pd.to_numeric(df_merged.get(c, 0), errors="coerce").fillna(0)
            return df_merged

    # ── 2순위: 임차_전기DB.xlsx ─────────────────────────────
    df_excel = load_rent_excel(file_hash(RENT_FILE))
    if not df_excel.empty and "sitekey" in df_excel.columns:
        need = [c for c in ("rent_ann","elec_ann","rent_no","elec_no") if c in df_excel.columns]
        df_merged = df_raw.merge(
            df_excel[["sitekey"] + need].drop_duplicates("sitekey"),
            on="sitekey", how="left",
        )
        for c in ("rent_ann","elec_ann"):
            df_merged[c] = pd.to_numeric(df_merged.get(c, 0), errors="coerce").fillna(0)
        for c in ("rent_no","elec_no"):
            if c not in df_merged.columns:
                df_merged[c] = ""
        return df_merged

    # ── 3순위: 원시 파일 P·Q열 직접 참조 ───────────────────
    df_raw = df_raw.copy()
    if "rent_ann_raw" in df_raw.columns:
        df_raw["rent_ann"] = pd.to_numeric(df_raw["rent_ann_raw"], errors="coerce").fillna(0)
    else:
        df_raw["rent_ann"] = 0.0
    if "elec_ann_raw" in df_raw.columns:
        df_raw["elec_ann"] = pd.to_numeric(df_raw["elec_ann_raw"], errors="coerce").fillna(0)
    else:
        df_raw["elec_ann"] = 0.0
    df_raw["rent_no"] = ""
    df_raw["elec_no"] = ""
    return df_raw


# ── 원시 데이터 로드 ─────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_raw(fhash: str, honbu: str = DEFAULT_HONBU) -> pd.DataFrame:
    """본부별 원시 Excel 로드."""
    main_path = MAIN_FILES.get(honbu, MAIN_FILE)
    if not main_path.exists():
        return _make_sample(honbu)

    target = list(COL_MAP.values())
    df = pd.read_excel(
        main_path, engine="openpyxl",
        usecols=lambda c: c in target,
        dtype=str,
    )
    inv = {v: k for k, v in COL_MAP.items() if v in df.columns}
    df  = df.rename(columns=inv)
    if "sitekey" in df.columns:
        df = df.drop_duplicates(subset="sitekey", keep="first")
    return df


# ── 추가 컬럼 로드/저장 ─────────────────────────────────────
def load_extra() -> dict:
    if EXTRA_FILE.exists():
        with open(EXTRA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_extra(data: dict):
    DATA_DIR.mkdir(exist_ok=True)
    with open(EXTRA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def apply_extra(df: pd.DataFrame, extra: dict) -> pd.DataFrame:
    """원시 DataFrame 끝에 편집 컬럼 병합."""
    df = df.copy()
    for col_key in EXTRA_COLS:
        df[col_key] = df["sitekey"].map(
            lambda sk, c=col_key: extra.get(sk, {}).get(c, "")
        )
    for c in ("inv_bun", "inv_bae", "savings_fix"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


# ── 변경 이력 ────────────────────────────────────────────────
def log_change(sitekey: str, col: str, old, new, user: str = "담당자"):
    logs = []
    if LOG_FILE.exists():
        with open(LOG_FILE, encoding="utf-8") as f:
            logs = json.load(f)
    logs.append({
        "ts": datetime.now().isoformat(timespec="seconds"),
        "user": user, "sitekey": sitekey,
        "col": col, "old": str(old), "new": str(new),
    })
    DATA_DIR.mkdir(exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def load_log() -> pd.DataFrame:
    if not LOG_FILE.exists():
        return pd.DataFrame()
    with open(LOG_FILE, encoding="utf-8") as f:
        return pd.DataFrame(json.load(f))


# ── 샘플 데이터 ─────────────────────────────────────────────
def _make_sample(honbu: str = DEFAULT_HONBU) -> pd.DataFrame:
    import random
    random.seed(hash(honbu) % (2**32))

    BIZ   = ["단순폐국", "이설후폐국", "최적화후폐국"]
    TOSI  = ["단독", "통시", "아파트", "공용"]
    MONTHS = {"1월":114,"2월":51,"3월":80,"4월":89,"5월":60,"6월":45}

    scale = {"수도권":1.35, "04.중부":1.0, "동부":0.90, "서부":0.80}.get(honbu, 1.0)

    real = []
    if honbu == "04.중부":
        real = [
            dict(sitekey="CB111114172007443", site_name="석계WMC.56",
                 biz_type="단순폐국", tosi="단독", off_month="1월",
                 rent_ann=0, elec_ann=0, voc=""),
            dict(sitekey="CB111114342336093", site_name="청주공단5거리",
                 biz_type="단순폐국", tosi="단독", off_month="1월",
                 rent_ann=1500, elec_ann=26, voc=""),
            dict(sitekey="CB111114373997427", site_name="청주운천초교",
                 biz_type="단순폐국", tosi="단독", off_month="2월",
                 rent_ann=1500, elec_ann=29, voc=""),
            dict(sitekey="CN111114173921607", site_name="팔봉천송펜션",
                 biz_type="단순폐국", tosi="통시", off_month="3월",
                 rent_ann=500, elec_ann=33, voc=""),
            dict(sitekey="CN111114100052041", site_name="입장가산2DOR",
                 biz_type="최적화후폐국", tosi="통시", off_month="3월",
                 rent_ann=0, elec_ann=1, voc=""),
        ]

    rows = list(real)
    used = {r["sitekey"] for r in real}
    prefix = honbu[:2]

    for month, base_cnt in MONTHS.items():
        target = int(base_cnt * scale)
        cur = sum(1 for r in rows if r.get("off_month") == month)
        for i in range(max(0, target - cur)):
            biz  = random.choices(BIZ,  weights=[0.65,0.22,0.13])[0]
            tosi = random.choices(TOSI, weights=[0.55,0.25,0.12,0.08])[0]
            rent = random.choice([0,500,600,800,1000,1200,1500,1800,2400])
            elec = random.randint(5, 60)
            key  = "{}{}".format(prefix, random.randint(10**13, 10**14-1))
            while key in used:
                key = "{}{}".format(prefix, random.randint(10**13, 10**14-1))
            used.add(key)
            rows.append(dict(
                sitekey=key,
                site_name="샘플_{}_{}_{:03d}".format(honbu, month, i+1),
                biz_type=biz, tosi=tosi, off_month=month,
                rent_ann=rent, elec_ann=elec,
                voc="Y" if random.random() < 0.03 else "",
            ))

    df = pd.DataFrame(rows)
    df["honbu"]       = honbu
    df["network"]     = "LTE"
    df["status"]      = "운용"
    df["site_err"]    = "정상"
    df["pool_yn"]     = df["sitekey"].apply(
        lambda sk: "미반영" if sk == "CN111114100052041" else "반영")
    df["pool_reason"] = df.apply(
        lambda r: "LOS 반경내 당사 Site 없음" if r["pool_yn"]=="미반영" else "", axis=1)
    df["close_month"] = ""
    df["type_cls"]    = ""
    df["rent_no"]     = ""
    df["elec_no"]     = ""
    return df