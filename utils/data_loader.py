"""
data_loader.py
--------------
원시 데이터 로딩 유틸리티.

data_site/ 폴더에 아래 파일을 위치시키세요:
    - 중부_원시데이터.xlsx  (원시 데이터, 포맷 그대로 유지)
    - 임차_전기DB.xlsx      (임차·전기료 DB, Sitekey 기준 조인)

파일이 없으면 샘플 데이터로 자동 실행됩니다.

원시 데이터 컬럼 끝에 추가되는 컬럼 (별도 저장):
    - 투자비_분기, 투자비_재배치  : 최적화후폐국 공중선 작업 투자비
    - 폐국월_확정, 절감금액_확정  : 본사 확정 후 입력
"""

import hashlib
import json
import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime

# ── 경로 설정 ───────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent
DATA_DIR    = BASE_DIR / "data_site"          # ← 원시 데이터 폴더
EXTRA_FILE  = DATA_DIR / "_extra_cols.json"   # 추가 컬럼 저장소
LOG_FILE    = DATA_DIR / "_change_log.json"   # 변경 이력

MAIN_FILE   = DATA_DIR / "중부_원시데이터.xlsx"
RENT_FILE   = DATA_DIR / "임차_전기DB.xlsx"

# ── 실제 엑셀 컬럼명 매핑 ──────────────────────────────────
# 키: 앱 내부 이름 / 값: 실제 엑셀 헤더
COL_MAP = {
    "sitekey":      "[ERP] Sitekey",
    "site_name":    "[ERP] 국소명",
    "honbu":        "[ERP] 본부",
    "network":      "[ERP] 사업망 구분",
    "status":       "[ERP] 운용 상태",
    "tosi":         "[ERP] 공대, Sub구분",
    "rent_no":      "[ERP] 임차물건번호",
    "elec_no":      "[ERP 전기물건] 전기료내역마스터",
    "rent_ann":     "[통합Eng DB] 연_임차_료",
    "elec_ann":     "[통합Eng DB] 연_전기_료",
    "site_err":     "사이트오류\n제외대상",
    "pool_yn":      "후보Pool\n반영여부",
    "pool_reason":  "후보Pool\n미반영사유",
    "biz_type":     "사업유형",
    "off_month":    "Off 월",
    "close_month":  "폐국 월",
    "voc":          "VoC",
    "type_cls":     "(최종)\n유형분류",
    "sav_type":     "절감유형",   # 앱에서 입력하는 컬럼
}


# ── 파일 해시 ───────────────────────────────────────────────
def file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── 원시 데이터 로드 ─────────────────────────────────────────
@st.cache_data(show_spinner="원시 데이터 로딩 중…")
def load_raw(fhash: str) -> pd.DataFrame:
    """원시 Excel을 로드. 포맷 그대로 유지하고 내부 컬럼명으로 rename."""
    if not MAIN_FILE.exists():
        return _make_sample()

    # 필요한 열만 로딩 (48MB 성능 최적화)
    target_cols = list(COL_MAP.values())
    df = pd.read_excel(
        MAIN_FILE,
        engine="openpyxl",
        usecols=lambda c: c in target_cols or c == "id",
        dtype=str,
    )
    # 내부 이름으로 rename
    inv_map = {v: k for k, v in COL_MAP.items() if v in df.columns}
    df = df.rename(columns=inv_map)

    # 수치 변환
    for c in ("rent_ann", "elec_ann"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # sitekey 중복 제거 (유니크 기준)
    if "sitekey" in df.columns:
        df = df.drop_duplicates(subset="sitekey", keep="first")

    return df


# ── 추가 컬럼 로드/저장 ─────────────────────────────────────
def load_extra() -> dict:
    """
    추가 컬럼 데이터 로드.
    구조: { sitekey: { "투자비_분기": 0, "투자비_재배치": 0,
                       "폐국월_확정": "", "절감금액_확정": "",
                       "sav_type": "" } }
    """
    if EXTRA_FILE.exists():
        with open(EXTRA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_extra(data: dict):
    """추가 컬럼 데이터 저장."""
    DATA_DIR.mkdir(exist_ok=True)
    with open(EXTRA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def apply_extra(df: pd.DataFrame, extra: dict) -> pd.DataFrame:
    """원시 DataFrame 끝에 추가 컬럼을 병합."""
    df = df.copy()
    add_cols = ["sav_type", "투자비_분기", "투자비_재배치", "폐국월_확정", "절감금액_확정"]
    for col in add_cols:
        df[col] = df["sitekey"].map(
            lambda sk, c=col: extra.get(sk, {}).get(c, "")
        )
    # 수치 컬럼 변환
    for c in ("투자비_분기", "투자비_재배치"):
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
        "user": user,
        "sitekey": sitekey,
        "col": col,
        "old": str(old),
        "new": str(new),
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
def _make_sample() -> pd.DataFrame:
    import random
    random.seed(42)

    BIZ    = ["단순폐국", "이설후폐국", "최적화후폐국"]
    TOSI   = ["단독", "통시", "아파트", "공용"]
    MONTHS = {"1월": 114, "2월": 51, "3월": 80, "4월": 89}

    # 실제 샘플 5건 (제공된 원시 데이터)
    real = [
        dict(sitekey="CB111114172007443", site_name="석계WMC.56",    biz_type="단순폐국",    tosi="단독",  off_month="1월", rent_ann=0,    elec_ann=0,  voc=""),
        dict(sitekey="CB111114342336093", site_name="청주공단5거리",  biz_type="단순폐국",    tosi="단독",  off_month="1월", rent_ann=1500, elec_ann=26, voc=""),
        dict(sitekey="CB111114373997427", site_name="청주운천초교",   biz_type="단순폐국",    tosi="단독",  off_month="1월", rent_ann=1500, elec_ann=29, voc=""),
        dict(sitekey="CN111114173921607", site_name="팔봉천송펜션",  biz_type="단순폐국",    tosi="통시",  off_month="3월", rent_ann=500,  elec_ann=33, voc=""),
        dict(sitekey="CN111114100052041", site_name="입장가산2DOR",  biz_type="최적화후폐국", tosi="통시",  off_month="3월", rent_ann=0,    elec_ann=1,  voc=""),
    ]

    rows = list(real)
    used_keys = {r["sitekey"] for r in real}

    for month, target in MONTHS.items():
        need = target - sum(1 for r in rows if r.get("off_month") == month)
        for i in range(max(0, need)):
            biz  = random.choices(BIZ, weights=[0.65, 0.22, 0.13])[0]
            tosi = random.choices(TOSI, weights=[0.55, 0.25, 0.12, 0.08])[0]
            rent = random.choice([0, 500, 600, 800, 1000, 1200, 1500, 1800, 2400])
            elec = random.randint(5, 60)
            has_voc = random.random() < 0.03
            key = f"CB{random.randint(100000000000000,999999999999999)}"
            while key in used_keys:
                key = f"CB{random.randint(100000000000000,999999999999999)}"
            used_keys.add(key)
            rows.append(dict(
                sitekey    = key,
                site_name  = f"샘플사이트_{month}_{i+1}",
                biz_type   = biz,
                tosi       = tosi,
                off_month  = month,
                rent_ann   = rent,
                elec_ann   = elec,
                voc        = "Y" if has_voc else "",
            ))

    df = pd.DataFrame(rows)
    df["honbu"]       = "04.중부"
    df["network"]     = "WCDMA"
    df["status"]      = "운용"
    df["site_err"]    = "정상"
    df["pool_yn"]     = df.apply(
        lambda r: "반영" if r["sitekey"] != "CN111114100052041" else "미반영", axis=1
    )
    df["pool_reason"] = df.apply(
        lambda r: "LOS 반경내 당사 Site 없음" if r["pool_yn"] == "미반영" else "", axis=1
    )
    df["close_month"] = ""
    df["type_cls"]    = df["biz_type"].map({
        "단순폐국": "01.3G단독", "이설후폐국": "02.LTE단독", "최적화후폐국": "03.기타"
    })
    return df