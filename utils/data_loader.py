"""
data_loader.py
==============
원시 데이터 포맷 절대 유지.
원시 파일을 있는 그대로 읽고, 편집 컬럼만 오른쪽 끝에 추가.

원시 파일 컬럼 (샘플.xlsx 기준, 60열):
  A  : id
  B  : [자료수합용] 2nd 순번(본부별 분리용)
  C  : [자료수합용] 최초 오름차순 순번
  D  : [Vlookup 순번]
  E  : [ERP]통합시설코드
  F  : 통시중복
  G  : [ERP] 국소명
  H  : [ERP] 사업망 구분
  I  : [ERP] 운용 상태
  J  : [ERP] 본부
  K  : [ERP] 공대, Sub구분
  L  : [ERP] 공용대표코드
  M  : [ERP] Sitekey          ← 주 키
  N  : [ERP] 임차물건번호
  O  : [ERP 전기물건] 전기료내역마스터
  P  : [통합Eng DB] 연_임차_료  (백만원 단위)
  Q  : [통합Eng DB] 연_전기_료  (백만원 단위)
  R  : [ERP] 상호정산비용
  S  : (빈 열)
  T  : 후보Pool
  U  : 본부
  V  : 사이트오류 제외대상
  W  : 후보Pool 반영여부
  X  : 후보Pool 미반영사유
  Y  : 사업유형
  Z  : Off 월                   ("1월_Off" 형식)
  AA : 폐국 월
  AB : VoC
  AC : 1월 Off 367
  AD : (최종) 유형분류
  AE : (빈 열)
  AF : (2월대상)연환산임차료
  AG : 임차번호(① 통시 ② 임차)
  AH : 연환산임차료(통시+임차+수기)  (원 단위, 실제 임차료 기준)
  AI : (작업중) 연환산임차료_통시
  AJ : (작업중) 연환산임차료_임차번호
  AK : RSRP Gp(S-N)
  AL : Neigh/Serv 비율
  AM : Cov. Outage Gap(S-N)
  AN : 상관계수
  AO : 반영내 판단 가능 인빌딩
  AP : LTE PCI 점유율
  AQ : 5G PCI 점유율
  AR~AT : (빈 열)
  AU : 시범클러스터(O,X)
  AV : 시범클러스터 미반영사유
  AW : 사업유형
  AX : 최경순
  AY : AFE반영대상 - 우선순위(이설후폐국)
  AZ : 통시
  BA : 활용구분
  BB : 시도
  BC : 시군구
  BD : 읍면동
  BE : 세부주소
  BF : 주소
  BG : 특이사항
  BH : 사이트증분 샘플 철거

임차·전기 조회 우선순위:
  1순위: DB 조회 (Athena 등 — query_rent_from_db 구현 시)
  2순위: 임차_전기DB.xlsx  (Sitekey 기준 조인)
  3순위: 원시파일 AH열(연환산임차료, 원단위) + Q열(연전기료, 백만원단위) 직접 참조
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

# ── 원시 파일에서 Sitekey·Pool 판단에 필요한 컬럼 ──────────
# 로직 처리용 내부 키 → 원시 헤더명 매핑 (최소한만)
KEY_COLS = {
    "sitekey":    "[ERP] Sitekey",
    "honbu":      "[ERP] 본부",
    "site_err":   "사이트오류\n제외대상",
    "pool_yn":    "후보Pool\n반영여부",
    "biz_type":   "사업유형",          # Y열
    "tosi":       "[ERP] 공대, Sub구분",
    "off_month_raw": "Off 월",
    "rent_ann_ah":   "연환산임차료\n(통시+임차+수기)",   # AH열 (원 단위)
    "rent_ann_p":    "[통합Eng DB] 연_임차_료",           # P열 (백만원)
    "elec_ann_q":    "[통합Eng DB] 연_전기_료",           # Q열 (백만원)
    "rent_no":       "[ERP] 임차물건번호",
    "elec_no":       "[ERP 전기물건] 전기료내역마스터",
}

# 임차_전기DB.xlsx 컬럼 매핑 (2순위)
RENT_COL_MAP = {
    "sitekey":  "[ERP] Sitekey",
    "rent_no":  "[ERP] 임차물건번호",
    "elec_no":  "[ERP 전기물건] 전기료내역마스터",
    "rent_ann": "[통합Eng DB] 연_임차_료",
    "elec_ann": "[통합Eng DB] 연_전기_료",
}

# 사용자 편집 추가 컬럼 (원시 데이터 오른쪽 끝에 추가)
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


def parse_off_month(raw) -> str:
    """'1월_Off' → '1월'"""
    if raw is None:
        return ""
    s = str(raw).strip()
    return s.split("_")[0] if "_Off" in s else s


def file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── 원시 데이터 로드 — 포맷 절대 유지 ───────────────────────
@st.cache_data(show_spinner=False)
def load_raw(fhash: str, honbu: str = DEFAULT_HONBU) -> pd.DataFrame:
    """
    원시 Excel을 있는 그대로 읽음.
    - 헤더(1행) 그대로 컬럼명으로 사용
    - 빈 열(S, AE, AR~AT) 포함 전체 컬럼 로드
    - 데이터 타입 변환 최소화 (표시 전용)
    - 로직 처리에 필요한 컬럼만 별도 파생 (_sitekey, _off_month 등)
    """
    main_path = MAIN_FILES.get(honbu, MAIN_FILE)
    if not main_path.exists():
        return _make_sample(honbu)

    try:
        # 헤더 1행, 전체 컬럼 그대로 읽기
        df = pd.read_excel(
            main_path,
            engine  = "openpyxl",
            header  = 0,       # 1행이 헤더
            dtype   = str,     # 모든 값 문자열로 유지 (표시용)
        )
    except Exception as e:
        st.error(f"원시 데이터 로딩 오류: {e}")
        return _make_sample(honbu)

    # Sitekey 컬럼 확인
    sitekey_col = "[ERP] Sitekey"
    if sitekey_col not in df.columns:
        st.warning(f"'{sitekey_col}' 컬럼을 찾을 수 없습니다. 헤더를 확인하세요.")
        return _make_sample(honbu)

    # Sitekey 중복 제거
    df = df.drop_duplicates(subset=sitekey_col, keep="first")

    # 로직 처리용 파생 컬럼 (언더스코어 prefix로 원본과 구분)
    df["_sitekey"]  = df[sitekey_col].fillna("")
    df["_honbu"]    = df.get("[ERP] 본부", "").fillna("")
    df["_site_err"] = df.get("사이트오류\n제외대상", "정상").fillna("정상")
    df["_pool_yn"]  = df.get("후보Pool\n반영여부", "반영").fillna("반영")
    df["_biz_type"] = df.get("사업유형", "").fillna("")
    df["_tosi"]     = df.get("[ERP] 공대, Sub구분", "").fillna("")

    # Off 월 파싱 ("1월_Off" → "1월")
    off_raw = df.get("Off 월", pd.Series("", index=df.index))
    df["_off_month"] = off_raw.apply(parse_off_month)

    # 임차·전기 금액 (만원 단위 파생 — 계산용)
    ah_col = "연환산임차료\n(통시+임차+수기)"
    p_col  = "[통합Eng DB] 연_임차_료"
    q_col  = "[통합Eng DB] 연_전기_료"

    if ah_col in df.columns:
        # AH열: 원 단위 → 만원 (÷10,000), '없음' 등 문자열은 0
        df["_rent_ann"] = pd.to_numeric(
            df[ah_col].replace({"없음": None, "": None}), errors="coerce"
        ).fillna(0) / 10000
    elif p_col in df.columns:
        # P열: 백만원 단위 → 만원 (×100)
        df["_rent_ann"] = pd.to_numeric(df[p_col], errors="coerce").fillna(0) * 100
    else:
        df["_rent_ann"] = 0.0

    if q_col in df.columns:
        # Q열: 백만원 단위 → 만원 (×100)
        df["_elec_ann"] = pd.to_numeric(df[q_col], errors="coerce").fillna(0) * 100
    else:
        df["_elec_ann"] = 0.0

    return df


# ── 1순위: DB 조회 ────────────────────────────────────────────
def query_rent_from_db(sitekeys: list) -> pd.DataFrame:
    """
    Athena/DB 구현 시 이 함수를 수정하세요.
    반환: DataFrame(sitekey, rent_ann, elec_ann) — 없으면 빈 DataFrame
    """
    try:
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
    for c in ("rent_ann", "elec_ann"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    if "sitekey" in df.columns:
        df = df.drop_duplicates(subset="sitekey", keep="first")
    return df


# ── 임차·전기 만원 금액 보강 (파생 컬럼 _rent_ann, _elec_ann 갱신) ──
def enrich_rent(df: pd.DataFrame) -> pd.DataFrame:
    """
    _rent_ann, _elec_ann 파생 컬럼을 우선순위에 따라 채움.
    원시 DataFrame의 나머지 컬럼은 절대 변경하지 않음.
    """
    df = df.copy()
    sitekeys = df["_sitekey"].tolist()

    # 1순위: DB
    db = query_rent_from_db(sitekeys)
    if not db.empty and "sitekey" in db.columns:
        db = db.set_index("sitekey")
        if "rent_ann" in db.columns:
            df["_rent_ann"] = df["_sitekey"].map(db["rent_ann"]).fillna(df["_rent_ann"])
        if "elec_ann" in db.columns:
            df["_elec_ann"] = df["_sitekey"].map(db["elec_ann"]).fillna(df["_elec_ann"])
        return df

    # 2순위: 임차_전기DB.xlsx
    excel = load_rent_excel(file_hash(RENT_FILE))
    if not excel.empty and "sitekey" in excel.columns:
        excel = excel.set_index("sitekey")
        if "rent_ann" in excel.columns:
            df["_rent_ann"] = df["_sitekey"].map(excel["rent_ann"]).fillna(df["_rent_ann"])
        if "elec_ann" in excel.columns:
            df["_elec_ann"] = df["_sitekey"].map(excel["elec_ann"]).fillna(df["_elec_ann"])

    # 3순위: 원시 파일 AH/P/Q열 → load_raw에서 이미 처리됨
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
    """
    원시 DataFrame 오른쪽 끝에 편집 컬럼 추가.
    원시 컬럼은 절대 변경하지 않음.
    """
    df = df.copy()
    for col_key, col_label in EXTRA_COLS.items():
        # submit_* 컬럼은 bool로
        val_default = False if col_key.startswith("submit_") else ""
        df[col_key] = df["_sitekey"].map(
            lambda sk, c=col_key, d=val_default: extra.get(sk, {}).get(c, d)
        )
        if col_key.startswith("submit_"):
            df[col_key] = df[col_key].apply(
                lambda v: True if str(v).lower() in ("true","1","y","제출") else False
            )
    for c in ("inv_bun", "inv_bae", "savings_fix"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


# ── 변경 이력 ────────────────────────────────────────────────
def log_change(sitekey, col, old, new, user="담당자"):
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
    실제 원시 파일 구조와 동일한 컬럼을 가진 샘플 DataFrame.
    헤더명은 실제 원시 파일과 100% 동일하게 유지.
    """
    import random
    random.seed(hash(honbu) % (2**32))

    BIZ   = ["단순폐국", "이설후폐국", "최적화후폐국"]
    TOSI  = ["단독", "통시", "아파트", "공용"]
    MONTHS_TARGET = {"1월":114,"2월":51,"3월":80,"4월":89,"5월":60,"6월":45}
    scale = {"수도권":1.35,"04.중부":1.0,"동부":0.90,"서부":0.80}.get(honbu,1.0)

    # 실제 샘플 5건 (샘플.xlsx 기반) — 원시 컬럼명 그대로
    real = []
    if honbu == "04.중부":
        real = [
            {
                "id": "171822",
                "[자료수합용] 2nd 순번\n(본부별 분리용)": None,
                "[자료수합용] 최초 오름차순 순번": "수합용_182329",
                "[Vlookup 순번]": "Row628595",
                "[ERP]통합시설코드": "200634189",
                "통시중복": "1",
                "[ERP] 국소명": "석계WMC.56.WCDMA.SF-W20",
                "[ERP] 사업망 구분": "WCDMA",
                "[ERP] 운용 상태": "운용",
                "[ERP] 본부": "04.중부",
                "[ERP] 공대, Sub구분": "단독",
                "[ERP] 공용대표코드": "200634189",
                "[ERP] Sitekey": "CB111114172007443",
                "[ERP] 임차물건번호": None,
                "[ERP 전기물건] 전기료내역마스터": None,
                "[통합Eng DB] 연_임차_료": None,
                "[통합Eng DB] 연_전기_료": None,
                "[ERP] 상호정산비용": None,
                "후보\nPool": "3G 단독",
                "본부": "04.중부",
                "사이트오류\n제외대상": "정상",
                "후보Pool\n반영여부": "반영",
                "후보Pool\n미반영사유": None,
                "사업유형": "단순폐국",
                "Off 월": "1월_Off",
                "폐국 월": None,
                "VoC": None,
                "1월 Off 367": "1월",
                "(최종)\n유형분류": "01.3G단독",
                "(2월대상)연환산임차료": "0",
                "임차번호\n(① 통시 ② 임차)": "0",
                "연환산임차료\n(통시+임차+수기)": "없음",
            },
            {
                "id": "171828",
                "[자료수합용] 2nd 순번\n(본부별 분리용)": None,
                "[자료수합용] 최초 오름차순 순번": "수합용_173656",
                "[Vlookup 순번]": "Row694708",
                "[ERP]통합시설코드": "200634529",
                "통시중복": "1",
                "[ERP] 국소명": "청주공단5거리WMC.56.WCDMA.SF-W20",
                "[ERP] 사업망 구분": "WCDMA",
                "[ERP] 운용 상태": "운용",
                "[ERP] 본부": "04.중부",
                "[ERP] 공대, Sub구분": "단독",
                "[ERP] 공용대표코드": "200634529",
                "[ERP] Sitekey": "CB111114342336093",
                "[ERP] 임차물건번호": "MC00018845",
                "[ERP 전기물건] 전기료내역마스터": "ME00020272",
                "[통합Eng DB] 연_임차_료": "1.5",
                "[통합Eng DB] 연_전기_료": "0.26",
                "[ERP] 상호정산비용": None,
                "후보\nPool": "3G 단독",
                "본부": "04.중부",
                "사이트오류\n제외대상": "정상",
                "후보Pool\n반영여부": "반영",
                "후보Pool\n미반영사유": None,
                "사업유형": "단순폐국",
                "Off 월": "1월_Off",
                "폐국 월": None,
                "VoC": None,
                "1월 Off 367": "1월",
                "(최종)\n유형분류": "01.3G단독",
                "(2월대상)연환산임차료": "0",
                "임차번호\n(① 통시 ② 임차)": "MC00018845",
                "연환산임차료\n(통시+임차+수기)": "1500000",
                "(작업중) 연환산임차료_통시": "1500000",
                "(작업중) 연환산임차료_임차번호": "1500000",
            },
            {
                "id": "171834",
                "[자료수합용] 2nd 순번\n(본부별 분리용)": None,
                "[자료수합용] 최초 오름차순 순번": "수합용_189593",
                "[Vlookup 순번]": "Row697145",
                "[ERP]통합시설코드": "200736452",
                "통시중복": "1",
                "[ERP] 국소명": "청주운천초교WMC.56.WCDMA.SF-W20",
                "[ERP] 사업망 구분": "WCDMA",
                "[ERP] 운용 상태": "운용",
                "[ERP] 본부": "04.중부",
                "[ERP] 공대, Sub구분": "단독",
                "[ERP] 공용대표코드": "200736452",
                "[ERP] Sitekey": "CB111114373997427",
                "[ERP] 임차물건번호": "MC00039585",
                "[ERP 전기물건] 전기료내역마스터": "ME00040521",
                "[통합Eng DB] 연_임차_료": "1.5",
                "[통합Eng DB] 연_전기_료": "0.29",
                "[ERP] 상호정산비용": None,
                "후보\nPool": "3G 단독",
                "본부": "04.중부",
                "사이트오류\n제외대상": "정상",
                "후보Pool\n반영여부": "반영",
                "후보Pool\n미반영사유": None,
                "사업유형": "단순폐국",
                "Off 월": "2월_Off",
                "폐국 월": None,
                "VoC": None,
                "1월 Off 367": "2월",
                "(최종)\n유형분류": "01.3G단독",
                "(2월대상)연환산임차료": "0",
                "임차번호\n(① 통시 ② 임차)": "MC00039585",
                "연환산임차료\n(통시+임차+수기)": "1500000",
                "(작업중) 연환산임차료_통시": "1500000",
                "(작업중) 연환산임차료_임차번호": "1500000",
            },
            {
                "id": "171836",
                "[자료수합용] 2nd 순번\n(본부별 분리용)": None,
                "[자료수합용] 최초 오름차순 순번": "수합용_198992",
                "[Vlookup 순번]": "Row647899",
                "[ERP]통합시설코드": "200736559",
                "통시중복": "1",
                "[ERP] 국소명": "팔봉천송펜션WMC.56.WCDMA.SF-W20",
                "[ERP] 사업망 구분": "WCDMA",
                "[ERP] 운용 상태": "운용",
                "[ERP] 본부": "04.중부",
                "[ERP] 공대, Sub구분": "단독",
                "[ERP] 공용대표코드": "200736559",
                "[ERP] Sitekey": "CN111114173921607",
                "[ERP] 임차물건번호": "MC00036907",
                "[ERP 전기물건] 전기료내역마스터": "ME00038627",
                "[통합Eng DB] 연_임차_료": "0.5",
                "[통합Eng DB] 연_전기_료": "0.33",
                "[ERP] 상호정산비용": None,
                "후보\nPool": "3G 단독",
                "본부": "04.중부",
                "사이트오류\n제외대상": "정상",
                "후보Pool\n반영여부": "반영",
                "후보Pool\n미반영사유": None,
                "사업유형": "단순폐국",
                "Off 월": "3월_Off",
                "폐국 월": None,
                "VoC": None,
                "1월 Off 367": "3월",
                "(최종)\n유형분류": "01.3G단독",
                "(2월대상)연환산임차료": "0",
                "임차번호\n(① 통시 ② 임차)": "MC00036907",
                "연환산임차료\n(통시+임차+수기)": None,
                "(작업중) 연환산임차료_통시": "500000",
                "(작업중) 연환산임차료_임차번호": "500000",
            },
            {
                "id": "171968",
                "[자료수합용] 2nd 순번\n(본부별 분리용)": None,
                "[자료수합용] 최초 오름차순 순번": "수합용_192181",
                "[Vlookup 순번]": "Row666479",
                "[ERP]통합시설코드": "200934163",
                "통시중복": "1",
                "[ERP] 국소명": "입장가산2DOR.56.WCDMA.OR-DUO2",
                "[ERP] 사업망 구분": "WCDMA",
                "[ERP] 운용 상태": "운용",
                "[ERP] 본부": "04.중부",
                "[ERP] 공대, Sub구분": "단독",
                "[ERP] 공용대표코드": "200934163",
                "[ERP] Sitekey": "CN111114100052041",
                "[ERP] 임차물건번호": None,
                "[ERP 전기물건] 전기료내역마스터": None,
                "[통합Eng DB] 연_임차_료": None,
                "[통합Eng DB] 연_전기_료": "0.01",
                "[ERP] 상호정산비용": None,
                "후보\nPool": "3G 단독",
                "본부": "04.중부",
                "사이트오류\n제외대상": "정상",
                "후보Pool\n반영여부": "미반영",
                "후보Pool\n미반영사유": "LOS 반경 400m .내 당사 Site 없음",
                "사업유형": None,
                "Off 월": "3월_Off",
                "폐국 월": None,
                "VoC": None,
                "1월 Off 367": "3월",
                "(최종)\n유형분류": "01.3G단독",
                "(2월대상)연환산임차료": "0",
                "임차번호\n(① 통시 ② 임차)": None,
                "연환산임차료\n(통시+임차+수기)": None,
            },
        ]

    rows = list(real)
    used = {r["[ERP] Sitekey"] for r in real}
    prefix = honbu[:2]

    for month, base_cnt in MONTHS_TARGET.items():
        target = int(base_cnt * scale)
        cur = sum(1 for r in rows
                  if parse_off_month(r.get("Off 월","")) == month)
        for i in range(max(0, target - cur)):
            biz  = random.choices(BIZ,  weights=[0.65,0.22,0.13])[0]
            tosi = random.choices(TOSI, weights=[0.55,0.25,0.12,0.08])[0]
            rent_ah = random.choice([0,500000,600000,800000,1000000,1500000,1800000,2400000])
            elec_q  = round(random.uniform(0.05, 0.60), 2)
            key = "{}{}".format(prefix, random.randint(10**13, 10**14-1))
            while key in used:
                key = "{}{}".format(prefix, random.randint(10**13, 10**14-1))
            used.add(key)
            is_pool = random.random() > 0.05
            rows.append({
                "id": str(random.randint(100000,999999)),
                "[ERP] 국소명": "샘플_{}_{}_{:03d}".format(honbu, month, i+1),
                "[ERP] 사업망 구분": random.choice(["WCDMA","LTE","5G"]),
                "[ERP] 운용 상태": "운용",
                "[ERP] 본부": honbu,
                "[ERP] 공대, Sub구분": tosi,
                "[ERP] Sitekey": key,
                "[ERP] 임차물건번호": "MC{:08d}".format(random.randint(0,99999999)) if rent_ah>0 else None,
                "[ERP 전기물건] 전기료내역마스터": "ME{:08d}".format(random.randint(0,99999999)),
                "[통합Eng DB] 연_임차_료": str(round(rent_ah/1000000, 2)) if rent_ah else None,
                "[통합Eng DB] 연_전기_료": str(elec_q),
                "사이트오류\n제외대상": "정상",
                "후보Pool\n반영여부": "반영" if is_pool else "미반영",
                "후보Pool\n미반영사유": None if is_pool else "LOS 반경내 당사 Site 없음",
                "사업유형": biz,
                "Off 월": "{}_Off".format(month),
                "폐국 월": None,
                "VoC": "Y" if random.random()<0.03 else None,
                "연환산임차료\n(통시+임차+수기)": str(rent_ah) if rent_ah else None,
            })

    df = pd.DataFrame(rows)

    # 파생 컬럼 추가
    df["_sitekey"]   = df["[ERP] Sitekey"].fillna("")
    df["_honbu"]     = df.get("[ERP] 본부", honbu)
    df["_site_err"]  = df.get("사이트오류\n제외대상", "정상").fillna("정상")
    df["_pool_yn"]   = df.get("후보Pool\n반영여부", "반영").fillna("반영")
    df["_biz_type"]  = df.get("사업유형", "").fillna("")
    df["_tosi"]      = df.get("[ERP] 공대, Sub구분", "").fillna("")
    df["_off_month"] = df.get("Off 월", "").apply(parse_off_month)

    ah_col = "연환산임차료\n(통시+임차+수기)"
    df["_rent_ann"] = pd.to_numeric(
        df[ah_col].replace({"없음": None}) if ah_col in df.columns else None,
        errors="coerce"
    ).fillna(0) / 10000

    q_col = "[통합Eng DB] 연_전기_료"
    df["_elec_ann"] = pd.to_numeric(
        df[q_col] if q_col in df.columns else None,
        errors="coerce"
    ).fillna(0) * 100

    return df