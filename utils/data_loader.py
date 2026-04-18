"""
data_loader.py
==============
실제 원시 데이터 포맷 기반 (샘플.xlsx 확인 완료)

컬럼 구조:
  A : id
  B : [자료수합용] 2nd 순번
  C : [자료수합용] 최초 오름차순 순번
  D : [Vlookup 순번]
  E : [ERP]통합시설코드
  F : 통시중복
  G : [ERP] 국소명
  H : [ERP] 사업망 구분
  I : [ERP] 운용 상태
  J : [ERP] 본부
  K : [ERP] 공대, Sub구분 (통시구분)
  L : [ERP] 공용대표코드
  M : [ERP] Sitekey         ← 주 키
  N : [ERP] 임차물건번호
  O : [ERP 전기물건] 전기료내역마스터
  P : [통합Eng DB] 연_임차_료   (억원 단위)
  Q : [통합Eng DB] 연_전기_료   (억원 단위)
  R : [ERP] 상호정산비용
  S : (비어있음)
  T : 후보\nPool
  U : 본부
  V : 사이트오류\n제외대상
  W : 후보Pool\n반영여부
  X : 후보Pool\n미반영사유
  Y : 사업유형
  Z : Off 월                    ← "1월_Off" 형식
  AA: 폐국 월
  AB: VoC
  AC: 1월 Off 367
  AD: (최종)\n유형분류
  AE: (비어있음)
  AF: (2월대상)연환산임차료
  AG: 임차번호\n(① 통시 ② 임차)
  AH: 연환산임차료\n(통시+임차+수기)  ← 원 단위, 실제 임차료 기준값
  AI: (작업중) 연환산임차료_통시
  AJ: (작업중) 연환산임차료_임차번호
  AK~BH: 분석/기타 컬럼

임차·전기 데이터 조회 우선순위:
  1순위: DB 조회 (Athena 등 — query_rent_from_db 구현 시 활성화)
  2순위: data_site/임차_전기DB.xlsx  (Sitekey 기준 조인)
  3순위: 원시파일 AH열(연환산임차료) + Q열(연전기료) 직접 참조

Off 월 파싱: "1월_Off" → "1월"
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

MAIN_FILES = {
    "수도권":  DATA_DIR / "수도권_원시데이터.xlsx",
    "04.중부": DATA_DIR / "중부_원시데이터.xlsx",
    "동부":    DATA_DIR / "동부_원시데이터.xlsx",
    "서부":    DATA_DIR / "서부_원시데이터.xlsx",
}
RENT_FILE     = DATA_DIR / "임차_전기DB.xlsx"
DEFAULT_HONBU = "04.중부"
MAIN_FILE     = MAIN_FILES[DEFAULT_HONBU]

HONBU_ORDER = ["수도권", "04.중부", "동부", "서부"]
MONTH_ORDER = [f"{i}월" for i in range(1, 7)]
CONFIRMED   = {"1월", "2월", "3월"}
REVIEW      = {"4월"}

SUBMIT_MONTHS = ["4월", "5월", "6월"]

# ── 원시 데이터 컬럼 매핑 (실제 헤더명 → 내부 키) ────────────
# 포맷 절대 유지: 원시 파일을 변형하지 않고 읽기만 함
COL_MAP = {
    # 기본 식별
    "id":            "id",
    "facility_code": "[ERP]통합시설코드",      # E열
    "sitekey":       "[ERP] Sitekey",           # M열 (주 키)
    "site_name":     "[ERP] 국소명",            # G열
    "network":       "[ERP] 사업망 구분",       # H열
    "status":        "[ERP] 운용 상태",         # I열
    "honbu":         "[ERP] 본부",              # J열
    "tosi":          "[ERP] 공대, Sub구분",     # K열 (통시구분)
    # 임차·전기 물건번호 (N, O열 — 원시파일에 이미 존재)
    "rent_no":       "[ERP] 임차물건번호",      # N열
    "elec_no":       "[ERP 전기물건] 전기료내역마스터",  # O열
    # P, Q열: 억원 단위 (참고용)
    "rent_ann_p":    "[통합Eng DB] 연_임차_료", # P열 (억원)
    "elec_ann_q":    "[통합Eng DB] 연_전기_료", # Q열 (억원)
    # 후보 Pool 관련
    "pool_type":     "후보\nPool",              # T열
    "site_err":      "사이트오류\n제외대상",    # V열
    "pool_yn":       "후보Pool\n반영여부",      # W열
    "pool_reason":   "후보Pool\n미반영사유",    # X열
    "biz_type":      "사업유형",                # Y열
    "off_month_raw": "Off 월",                  # Z열 ("1월_Off" 형식)
    "close_month":   "폐국 월",                 # AA열
    "voc":           "VoC",                     # AB열
    "type_cls":      "(최종)\n유형분류",        # AD열
    # AH열: 연환산임차료(원 단위) — 3순위 fallback 기준
    "rent_ann_ah":   "연환산임차료\n(통시+임차+수기)",  # AH열
}

# 임차·전기 DB 컬럼 매핑 (2순위)
RENT_COL_MAP = {
    "sitekey":  "[ERP] Sitekey",
    "rent_no":  "[ERP] 임차물건번호",
    "elec_no":  "[ERP 전기물건] 전기료내역마스터",
    "rent_ann": "[통합Eng DB] 연_임차_료",
    "elec_ann": " [통합Eng DB] 연_전기_료",
}

# 사용자 편집 컬럼 (원시 파일 오른쪽 끝에 추가)
EXTRA_COLS = {
    "sav_type":      "절감유형",
    "inv_bun":       "투자비_분기",
    "inv_bae":       "투자비_재배치",
    "confirm_month": "폐국월_확정",
    "savings_fix":   "절감금액_확정",
    "note":          "비고",
    **{"submit_{}".format(m): "{}제출".format(m) for m in SUBMIT_MONTHS},
}
EDITABLE_EXTRA = set(EXTRA_COLS.keys())


# ── Off 월 파싱 ──────────────────────────────────────────────
def parse_off_month(raw) -> str:
    """
    "1월_Off", "3월_Off" → "1월", "3월"
    이미 "1월" 형식이면 그대로 반환
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if "_Off" in s:
        return s.split("_")[0]   # "1월_Off" → "1월"
    return s


# ── 파일 해시 ────────────────────────────────────────────────
def file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── 1순위: DB 조회 ────────────────────────────────────────────
def query_rent_from_db(sitekeys: list) -> pd.DataFrame:
    """
    Athena/DB 연결 구현 시 이 함수를 수정하세요.
    반환: DataFrame(sitekey, rent_ann, elec_ann) — 없으면 빈 DataFrame
    """
    try:
        # 예시: Athena 쿼리
        # import boto3
        # ...
        return pd.DataFrame()   # 미구현 → 2순위 fallback
    except Exception:
        return pd.DataFrame()


# ── 2순위: 임차_전기DB.xlsx ──────────────────────────────────
@st.cache_data(show_spinner=False)
def load_rent_excel(fhash: str) -> pd.DataFrame:
    if not RENT_FILE.exists():
        return pd.DataFrame()
    target = list(RENT_COL_MAP.values())
    df = pd.read_excel(RENT_FILE, engine="openpyxl",
                       usecols=lambda c: c in target, dtype=str)
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


# ── 임차·전기 통합 조회 (3단계 Fallback) ─────────────────────
def get_rent_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    우선순위:
      1순위 DB → 2순위 엑셀 → 3순위 원시파일 AH열(임차) + Q열(전기)
    """
    sitekeys = df_raw["sitekey"].tolist() if "sitekey" in df_raw.columns else []

    # 1순위: DB
    df_db = query_rent_from_db(sitekeys)
    if isinstance(df_db, pd.DataFrame) and not df_db.empty and "sitekey" in df_db.columns:
        need = [c for c in ("rent_ann","elec_ann") if c in df_db.columns]
        if need:
            df = df_raw.merge(df_db[["sitekey"]+need].drop_duplicates("sitekey"),
                              on="sitekey", how="left")
            for c in ("rent_ann","elec_ann"):
                df[c] = pd.to_numeric(df.get(c,0), errors="coerce").fillna(0)
            return df

    # 2순위: 임차_전기DB.xlsx
    df_excel = load_rent_excel(file_hash(RENT_FILE))
    if not df_excel.empty and "sitekey" in df_excel.columns:
        need = [c for c in ("rent_ann","elec_ann","rent_no","elec_no") if c in df_excel.columns]
        df = df_raw.merge(df_excel[["sitekey"]+need].drop_duplicates("sitekey"),
                          on="sitekey", how="left",
                          suffixes=("_raw",""))
        for c in ("rent_ann","elec_ann"):
            df[c] = pd.to_numeric(df.get(c,0), errors="coerce").fillna(0)
        for c in ("rent_no","elec_no"):
            if c not in df.columns and c+"_raw" in df.columns:
                df[c] = df[c+"_raw"]
        return df

    # 3순위: 원시파일 AH열(연환산임차료, 원 단위) + Q열(전기, 억원)
    df_raw = df_raw.copy()
    if "rent_ann_ah" in df_raw.columns:
        # AH열: 원 단위 → 만원 단위
        df_raw["rent_ann"] = pd.to_numeric(df_raw["rent_ann_ah"], errors="coerce").fillna(0) / 10000
    elif "rent_ann_p" in df_raw.columns:
        # P열: 억원 단위 → 만원 단위
        df_raw["rent_ann"] = pd.to_numeric(df_raw["rent_ann_p"], errors="coerce").fillna(0) * 100
    else:
        df_raw["rent_ann"] = 0.0

    if "elec_ann_q" in df_raw.columns:
        # Q열: 억원 단위 → 만원 단위
        df_raw["elec_ann"] = pd.to_numeric(df_raw["elec_ann_q"], errors="coerce").fillna(0) * 100
    else:
        df_raw["elec_ann"] = 0.0

    return df_raw


# ── 원시 데이터 로드 ─────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_raw(fhash: str, honbu: str = DEFAULT_HONBU) -> pd.DataFrame:
    """
    원시 Excel 로드.
    - 포맷 절대 유지 (파일 수정 없음)
    - 필요한 열만 읽기 (성능 최적화)
    - Off 월 파싱: "1월_Off" → "1월"
    """
    main_path = MAIN_FILES.get(honbu, MAIN_FILE)
    if not main_path.exists():
        return _make_sample(honbu)

    # 필요한 헤더 목록 (빈 열, 분석 전용 열 제외)
    target = {v for v in COL_MAP.values() if v is not None}

    try:
        df = pd.read_excel(
            main_path,
            engine   = "openpyxl",
            header   = 0,          # 1행이 헤더
            usecols  = lambda c: c in target,
            dtype    = str,
        )
    except Exception as e:
        st.error(f"원시 데이터 로딩 오류: {e}")
        return _make_sample(honbu)

    # 내부 키로 rename
    inv = {v: k for k, v in COL_MAP.items() if v in df.columns}
    df  = df.rename(columns=inv)

    # Sitekey 기준 중복 제거
    if "sitekey" in df.columns:
        df = df.drop_duplicates(subset="sitekey", keep="first")
    else:
        st.warning("'[ERP] Sitekey' 컬럼을 찾을 수 없습니다. 헤더를 확인하세요.")
        return _make_sample(honbu)

    # Off 월 파싱: "1월_Off" → "1월"
    if "off_month_raw" in df.columns:
        df["off_month"] = df["off_month_raw"].apply(parse_off_month)
    else:
        df["off_month"] = ""

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
    """원시 DataFrame 오른쪽 끝에 추가 편집 컬럼 병합."""
    df = df.copy()
    all_extra = {
        **EXTRA_COLS,
        **{"submit_{}".format(m): "{}제출".format(m) for m in SUBMIT_MONTHS},
    }
    for col_key in all_extra:
        if col_key not in df.columns:
            df[col_key] = df["sitekey"].map(
                lambda sk, c=col_key: extra.get(sk, {}).get(c, "")
            )
    for c in ("inv_bun", "inv_bae", "savings_fix"):
        if c in df.columns:
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


# ── 샘플 데이터 (실제 파일 없을 때) ─────────────────────────
def _make_sample(honbu: str = DEFAULT_HONBU) -> pd.DataFrame:
    """
    실제 원시 파일 5개 행 기반 샘플 + 추가 임의 데이터.
    포맷은 실제 원시 데이터 구조와 동일하게 유지.
    """
    import random
    random.seed(hash(honbu) % (2**32))

    BIZ   = ["단순폐국","이설후폐국","최적화후폐국"]
    TOSI  = ["단독","통시","아파트","공용"]
    MONTHS_TARGET = {"1월":114,"2월":51,"3월":80,"4월":89,"5월":60,"6월":45}
    scale = {"수도권":1.35,"04.중부":1.0,"동부":0.90,"서부":0.80}.get(honbu, 1.0)

    # 실제 샘플 5건 (샘플.xlsx 기반)
    real = []
    if honbu == "04.중부":
        real = [
            dict(id="171822", sitekey="CB111114172007443",
                 site_name="석계WMC.56", honbu="04.중부", network="WCDMA",
                 status="운용", tosi="단독", rent_no="", elec_no="",
                 rent_ann_ah=0, elec_ann_q=0,
                 site_err="정상", pool_yn="반영", pool_reason="",
                 biz_type="단순폐국", off_month="1월", close_month="", voc="",
                 type_cls="01.3G단독"),
            dict(id="171828", sitekey="CB111114342336093",
                 site_name="청주공단5거리", honbu="04.중부", network="WCDMA",
                 status="운용", tosi="단독", rent_no="MC00018845", elec_no="ME00020272",
                 rent_ann_ah=1500000, elec_ann_q=0.26,
                 site_err="정상", pool_yn="반영", pool_reason="",
                 biz_type="단순폐국", off_month="1월", close_month="", voc="",
                 type_cls="01.3G단독"),
            dict(id="171834", sitekey="CB111114373997427",
                 site_name="청주운천초교", honbu="04.중부", network="WCDMA",
                 status="운용", tosi="단독", rent_no="MC00039585", elec_no="ME00040521",
                 rent_ann_ah=1500000, elec_ann_q=0.29,
                 site_err="정상", pool_yn="반영", pool_reason="",
                 biz_type="단순폐국", off_month="2월", close_month="", voc="",
                 type_cls="01.3G단독"),
            dict(id="171836", sitekey="CN111114173921607",
                 site_name="팔봉천송펜션", honbu="04.중부", network="WCDMA",
                 status="운용", tosi="단독", rent_no="MC00036907", elec_no="ME00038627",
                 rent_ann_ah=500000, elec_ann_q=0.33,
                 site_err="정상", pool_yn="반영", pool_reason="",
                 biz_type="단순폐국", off_month="3월", close_month="", voc="",
                 type_cls="01.3G단독"),
            dict(id="171837", sitekey="CN111114100052041",
                 site_name="입장가산2DOR", honbu="04.중부", network="WCDMA",
                 status="운용", tosi="통시", rent_no="", elec_no="",
                 rent_ann_ah=0, elec_ann_q=0.01,
                 site_err="정상", pool_yn="미반영",
                 pool_reason="LOS 반경 400m 내 당사 Site 없음",
                 biz_type="", off_month="3월", close_month="", voc="",
                 type_cls=""),
        ]

    rows = list(real)
    used = {r["sitekey"] for r in real}
    prefix = honbu[:2]

    for month, base_cnt in MONTHS_TARGET.items():
        target = int(base_cnt * scale)
        cur = sum(1 for r in rows if r.get("off_month") == month)
        for i in range(max(0, target - cur)):
            biz  = random.choices(BIZ,  weights=[0.65,0.22,0.13])[0]
            tosi = random.choices(TOSI, weights=[0.55,0.25,0.12,0.08])[0]
            # 원 단위 임차료 (AH열 기준)
            rent_ah = random.choice([0,500000,600000,800000,1000000,1500000,1800000,2400000])
            elec_q  = round(random.uniform(0.05, 0.60), 2)   # 억원 단위
            key = "{}{}".format(prefix, random.randint(10**13, 10**14-1))
            while key in used:
                key = "{}{}".format(prefix, random.randint(10**13, 10**14-1))
            used.add(key)
            rows.append(dict(
                id          = str(random.randint(100000, 999999)),
                sitekey     = key,
                site_name   = "샘플_{}_{}_{:03d}".format(honbu, month, i+1),
                honbu       = honbu,
                network     = random.choice(["WCDMA","LTE","5G"]),
                status      = "운용",
                tosi        = tosi,
                rent_no     = "MC{:08d}".format(random.randint(0,99999999)) if rent_ah>0 else "",
                elec_no     = "ME{:08d}".format(random.randint(0,99999999)),
                rent_ann_ah = rent_ah,
                elec_ann_q  = elec_q,
                site_err    = "정상",
                pool_yn     = "미반영" if random.random()<0.05 else "반영",
                pool_reason = "",
                biz_type    = biz,
                off_month   = month,
                close_month = "",
                voc         = "Y" if random.random()<0.03 else "",
                type_cls    = "",
            ))

    df = pd.DataFrame(rows)
    # pool_reason 채우기
    df.loc[df["pool_yn"]=="미반영","pool_reason"] = "LOS 반경 400m 내 당사 Site 없음"
    return df