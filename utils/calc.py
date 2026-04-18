"""calc.py — 절감금액·BEP·집계 계산"""
import pandas as pd
import numpy as np

MONTH_ORDER = [f"{i}월" for i in range(1, 7)]   # 1~6월
CONFIRMED   = {"1월", "2월", "3월"}
REVIEW      = {"4월"}

HONBU_ORDER = ["수도권", "04.중부", "동부", "서부"]
HONBU_GOAL  = {"수도권": 420, "04.중부": 310, "동부": 280, "서부": 250}
ANNUAL_GOAL = 310   # 기본값 (04.중부)


def infer_sav_type(row) -> str:
    tosi = str(row.get("_tosi", row.get("tosi", "")))
    biz  = str(row.get("_biz_type", row.get("biz_type", "")))
    rent = float(row.get("_rent_ann", row.get("rent_ann", 0)) or 0)
    if tosi == "단독":                 return "임차+전기"
    if tosi in ("아파트","공용"):       return "절감없음"
    if biz  == "최적화후폐국":          return "전기만"
    return "임차+전기" if rent > 0 else "전기만"


def calc_savings(df: pd.DataFrame, rent_col: str = "_rent_ann", elec_col: str = "_elec_ann", sav_col: str = "sav_type") -> pd.DataFrame:
    df = df.copy()
    if "sav_type" in df.columns:
        mask = df["sav_type"].isna() | (df["sav_type"] == "")
        df.loc[mask, "sav_type"] = df[mask].apply(infer_sav_type, axis=1)
    else:
        df["sav_type"] = df.apply(infer_sav_type, axis=1)

    rent  = pd.to_numeric(df.get(rent_col, 0), errors="coerce").fillna(0)
    elec  = pd.to_numeric(df.get(elec_col, 0), errors="coerce").fillna(0)
    if sav_col not in df.columns:
        df = df.copy()
        df[sav_col] = df.apply(infer_sav_type, axis=1)
    sav = df[sav_col]
    inv_b = pd.to_numeric(df.get("inv_bun",   0), errors="coerce").fillna(0)
    inv_r = pd.to_numeric(df.get("inv_bae",   0), errors="coerce").fillna(0)

    savings = pd.Series(0.0, index=df.index)
    savings[sav == "임차+전기"] = (rent + elec)[sav == "임차+전기"]
    savings[sav == "전기만"]   = elec[sav == "전기만"]

    df["savings_ann"] = savings
    df["inv_total"]   = inv_b + inv_r
    df["_inv_total"]  = df["inv_total"]   # 계산용 별칭
    df["net_savings"] = df["savings_ann"] - df["inv_total"]
    df["savings_mon"] = (df["savings_ann"] / 12).round(1)

    def _bep(r):
        if r["inv_total"] <= 0 or r["savings_mon"] <= 0: return None
        return int(np.ceil(r["inv_total"] / r["savings_mon"]))

    def _roi(r):
        if r["inv_total"] <= 0: return None
        return round(r["net_savings"] / r["inv_total"] * 100, 1)

    df["bep_months"] = df.apply(_bep, axis=1)
    df["roi_pct"]    = df.apply(_roi, axis=1)
    return df


def monthly_summary(df: pd.DataFrame, goal: int = ANNUAL_GOAL) -> pd.DataFrame:
    rows, cumul = [], 0
    for m in MONTH_ORDER:
        off_col = "_off_month" if "_off_month" in df.columns else "off_month"
        sub  = df[df[off_col] == m]
        cnt  = len(sub)
        cumul += cnt
        rows.append({
            "월":          m,
            "실적":        cnt,
            "누계":        cumul if cnt > 0 else None,
            "누계달성률":  round(cumul / goal * 100, 1) if cnt > 0 else None,
            "임차+전기":   int((sub["sav_type"] == "임차+전기").sum()),
            "전기만":      int((sub["sav_type"] == "전기만").sum()),
            "절감없음":    int((sub["sav_type"] == "절감없음").sum()),
            "임차료절감":  round(sub["savings_ann"].sum() * 0.85 / 10000, 2),
            "전기료절감":  round(
                sub[sub["sav_type"].isin(["임차+전기","전기만"])].get("_elec_ann", sub["_elec_ann"] if "_elec_ann" in sub.columns else 0).sum() / 10000, 2),
            "투자비":      round(sub["inv_total"].sum() / 10000, 2),
            "순절감":      round(sub["net_savings"].sum() / 10000, 2),
            "상태":        "확정" if m in CONFIRMED else ("검토중" if m in REVIEW else "예정"),
        })
    return pd.DataFrame(rows)


def biz_type_summary(df: pd.DataFrame) -> pd.DataFrame:
    groups = []
    for biz in ["단순폐국","이설후폐국","최적화후폐국"]:
        sub = df[df["biz_type"] == biz]
        avg = sub["bep_months"].dropna().mean()
        groups.append({
            "사업유형":    biz,
            "건수":        len(sub),
            "임차+전기":   int((sub["sav_type"]=="임차+전기").sum()),
            "전기만":      int((sub["sav_type"]=="전기만").sum()),
            "절감없음":    int((sub["sav_type"]=="절감없음").sum()),
            "임차료절감":  round(sub["savings_ann"].sum()*0.85/10000, 2),
            "전기료절감":  round((sub["_elec_ann"].sum() if "_elec_ann" in sub.columns else 0)/10000, 2),
            "투자비":      round(sub["inv_total"].sum()/10000, 2),
            "순절감":      round(sub["net_savings"].sum()/10000, 2),
            "평균BEP":     round(avg, 1) if not pd.isna(avg) else None,
        })
    return pd.DataFrame(groups)


def equipment_summary(df: pd.DataFrame) -> dict:
    TYPES  = ["RRU","BBU","안테나","기타"]
    RATIOS = [0.40, 0.20, 0.30, 0.10]
    result = {}
    for m in MONTH_ORDER:
        off_col = "_off_month" if "_off_month" in df.columns else "off_month"
        cnt = len(df[df[off_col] == m])
        if cnt > 0:
            result[m] = {t: int(cnt*2.5*r) for t,r in zip(TYPES,RATIOS)}
    return result


def voc_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows, remain = [], 0
    for m in ["1월","2월","3월"]:
        off_col = "_off_month" if "_off_month" in df.columns else "off_month"
        sub    = df[df[off_col] == m]
        issued = int((sub.get("voc", pd.Series()).astype(str).str.upper()=="Y").sum())
        done   = int(issued * 0.75)
        remain += (issued - done)
        rows.append({"월":m,"발생":issued,"처리완료":done,"미처리누계":int(remain)})
    return pd.DataFrame(rows)