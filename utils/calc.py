"""
calc.py  —  절감금액·BEP·집계 계산
"""

import pandas as pd
import numpy as np

ANNUAL_GOAL = 310   # 연간 폐국 목표 (개소)
CONFIRMED   = {"1월", "2월", "3월"}
REVIEW      = {"4월"}


# ── 절감유형 자동 판단 ───────────────────────────────────────
def infer_sav_type(row) -> str:
    """
    tosi(통시구분)와 biz_type(사업유형)으로 절감유형 초기값 추천.
    담당자가 수동으로 변경 가능.
    """
    tosi = str(row.get("tosi", ""))
    biz  = str(row.get("biz_type", ""))
    rent = float(row.get("rent_ann", 0) or 0)

    if tosi == "단독":
        return "임차+전기"
    if tosi in ("아파트", "공용"):
        return "절감없음"
    # 통시
    if biz == "최적화후폐국":
        return "전기만"
    if rent > 0:
        return "임차+전기"
    return "전기만"


# ── Sitekey 단위 절감·BEP 계산 ──────────────────────────────
def calc_savings(df: pd.DataFrame) -> pd.DataFrame:
    """
    df : apply_extra() 적용 후 DataFrame
    추가 컬럼: savings_ann, inv_total, net_savings, savings_mon, bep_months, roi_pct
    """
    df = df.copy()

    # 절감유형이 비어 있으면 자동 추천
    if "sav_type" in df.columns:
        mask_empty = df["sav_type"].isna() | (df["sav_type"] == "")
        df.loc[mask_empty, "sav_type"] = df[mask_empty].apply(infer_sav_type, axis=1)
    else:
        df["sav_type"] = df.apply(infer_sav_type, axis=1)

    rent  = df.get("rent_ann", pd.Series(0, index=df.index)).fillna(0)
    elec  = df.get("elec_ann", pd.Series(0, index=df.index)).fillna(0)
    sav   = df["sav_type"]
    inv_b = df.get("투자비_분기",    pd.Series(0, index=df.index)).fillna(0)
    inv_r = df.get("투자비_재배치",  pd.Series(0, index=df.index)).fillna(0)

    # 연 절감액 (만원)
    savings = pd.Series(0.0, index=df.index)
    savings[sav == "임차+전기"] = (rent + elec)[sav == "임차+전기"]
    savings[sav == "전기만"]   = elec[sav == "전기만"]
    df["savings_ann"] = savings

    df["inv_total"]   = (inv_b + inv_r).astype(float)
    df["net_savings"] = df["savings_ann"] - df["inv_total"]
    df["savings_mon"] = (df["savings_ann"] / 12).round(1)

    def _bep(row):
        if row["inv_total"] <= 0 or row["savings_mon"] <= 0:
            return None
        return int(np.ceil(row["inv_total"] / row["savings_mon"]))

    def _roi(row):
        if row["inv_total"] <= 0:
            return None
        return round(row["net_savings"] / row["inv_total"] * 100, 1)

    df["bep_months"] = df.apply(_bep, axis=1)
    df["roi_pct"]    = df.apply(_roi, axis=1)
    return df


# ── 월별 집계 ────────────────────────────────────────────────
def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    MONTHS = ["1월", "2월", "3월", "4월", "5월", "6월"]
    rows, cumul = [], 0
    for m in MONTHS:
        sub  = df[df["off_month"] == m]
        cnt  = len(sub)
        cumul += cnt
        confirmed = m in CONFIRMED
        rows.append({
            "월":         m,
            "실적":       cnt,
            "누계":       cumul if cnt > 0 else None,
            "누계달성률": round(cumul / ANNUAL_GOAL * 100, 1) if cnt > 0 else None,
            "임차+전기":  int((sub["sav_type"] == "임차+전기").sum()),
            "전기만":     int((sub["sav_type"] == "전기만").sum()),
            "절감없음":   int((sub["sav_type"] == "절감없음").sum()),
            "임차료절감": round(sub["savings_ann"].sum() * 0.85 / 10000, 2),
            "전기료절감": round(sub[sub["sav_type"].isin(["임차+전기","전기만"])]["elec_ann"].sum() / 10000, 2),
            "투자비":     round(sub["inv_total"].sum() / 10000, 2),
            "순절감":     round(sub["net_savings"].sum() / 10000, 2),
            "상태":       "확정" if confirmed else ("검토중" if m == "4월" else "예정"),
        })
    return pd.DataFrame(rows)


# ── 사업유형별 집계 ──────────────────────────────────────────
def biz_type_summary(df: pd.DataFrame) -> pd.DataFrame:
    groups = []
    for biz in ["단순폐국", "이설후폐국", "최적화후폐국"]:
        sub = df[df["biz_type"] == biz]
        avg_bep = sub["bep_months"].dropna().mean()
        groups.append({
            "사업유형":   biz,
            "건수":       len(sub),
            "임차+전기":  int((sub["sav_type"] == "임차+전기").sum()),
            "전기만":     int((sub["sav_type"] == "전기만").sum()),
            "절감없음":   int((sub["sav_type"] == "절감없음").sum()),
            "임차료절감": round(sub["savings_ann"].sum() * 0.85 / 10000, 2),
            "전기료절감": round(sub["elec_ann"].sum() / 10000, 2),
            "투자비":     round(sub["inv_total"].sum() / 10000, 2),
            "순절감":     round(sub["net_savings"].sum() / 10000, 2),
            "평균BEP":    round(avg_bep, 1) if not pd.isna(avg_bep) else None,
        })
    return pd.DataFrame(groups)


# ── 장비 수량 집계 ───────────────────────────────────────────
def equipment_summary(df: pd.DataFrame) -> dict:
    TYPES  = ["RRU", "BBU", "안테나", "기타"]
    RATIOS = [0.40, 0.20, 0.30, 0.10]
    result = {}
    for m in ["1월", "2월", "3월", "4월"]:
        cnt      = len(df[df["off_month"] == m])
        total_eq = cnt * 2.5
        result[m] = {t: int(total_eq * r) for t, r in zip(TYPES, RATIOS)}
    return result


# ── VoC 집계 ─────────────────────────────────────────────────
def voc_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows, remain = [], 0
    for m in ["1월", "2월", "3월"]:
        sub    = df[df["off_month"] == m]
        issued = int((sub.get("voc", pd.Series()).astype(str).str.upper() == "Y").sum())
        done   = int(issued * 0.75)
        remain += (issued - done)
        rows.append({"월": m, "발생": issued, "처리완료": done, "미처리누계": int(remain)})
    return pd.DataFrame(rows)