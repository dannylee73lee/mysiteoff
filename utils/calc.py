"""
calc.py
-------
절감금액·BEP·ROI 계산 헬퍼.
"""

import pandas as pd
import numpy as np


ANNUAL_GOAL = 310  # 연간 폐국 목표


def calc_savings(df: pd.DataFrame) -> pd.DataFrame:
    """
    절감금액, 투자비, 순절감, 월절감, BEP, ROI 컬럼 추가.
    입력 df 는 pool_df (반영 대상) 기준.
    """
    df = df.copy()

    rent = df.get("rent_ann", pd.Series(0, index=df.index)).fillna(0)
    elec = df.get("elec_ann", pd.Series(0, index=df.index)).fillna(0)
    sav  = df.get("sav_type", pd.Series("절감없음", index=df.index))
    inv_b = df.get("inv_bun", pd.Series(0, index=df.index)).fillna(0)
    inv_r = df.get("inv_bae", pd.Series(0, index=df.index)).fillna(0)

    # 연간 절감금액 (만원)
    savings = pd.Series(0.0, index=df.index)
    savings[sav == "임차+전기"] = (rent + elec)[sav == "임차+전기"]
    savings[sav == "전기만"]   = elec[sav == "전기만"]
    df["savings_ann"] = savings

    # 투자비 합계
    df["inv_total"] = inv_b + inv_r

    # 순절감 (연)
    df["net_savings"] = df["savings_ann"] - df["inv_total"]

    # 월절감
    df["savings_mon"] = (df["savings_ann"] / 12).round(1)

    # BEP (개월) — 투자비 있을 때만
    def _bep(row):
        if row["inv_total"] <= 0 or row["savings_mon"] <= 0:
            return None
        return int(np.ceil(row["inv_total"] / row["savings_mon"]))

    df["bep_months"] = df.apply(_bep, axis=1)

    # ROI (연, %) — 투자비 있을 때만
    def _roi(row):
        if row["inv_total"] <= 0:
            return None
        return round(row["net_savings"] / row["inv_total"] * 100, 1)

    df["roi_pct"] = df.apply(_roi, axis=1)

    return df


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    월별 집계: 실적수, 누계, 달성률, 임차·전기·투자비·순절감
    df : calc_savings() 적용된 pool_df
    """
    MONTHS = ["1월", "2월", "3월", "4월", "5월", "6월"]

    rows = []
    cumul = 0
    for m in MONTHS:
        sub = df[df["off_month"] == m]
        cnt = len(sub)
        cumul += cnt
        pct   = round(cumul / ANNUAL_GOAL * 100, 1)

        confirmed = m in ["1월", "2월", "3월"]

        rows.append({
            "월":          m,
            "실적":        cnt,
            "누계":        cumul if cnt > 0 else None,
            "누계달성률":   pct   if cnt > 0 else None,
            "임차+전기":   len(sub[sub["sav_type"] == "임차+전기"]),
            "전기만":      len(sub[sub["sav_type"] == "전기만"]),
            "절감없음":    len(sub[sub["sav_type"] == "절감없음"]),
            "임차료절감":  round(sub["savings_ann"].sum() * 0.85 / 10000, 2),  # 억원
            "전기료절감":  round(sub[sub["sav_type"].isin(["임차+전기","전기만"])]["elec_ann"].sum() / 10000, 2),
            "투자비":      round(sub["inv_total"].sum() / 10000, 2),
            "순절감":      round(sub["net_savings"].sum() / 10000, 2),
            "상태":        "확정" if confirmed else ("검토중" if m == "4월" else "예정"),
        })

    return pd.DataFrame(rows)


def biz_type_summary(df: pd.DataFrame) -> pd.DataFrame:
    """사업유형별 집계"""
    groups = []
    for biz in ["단순폐국", "이설후폐국", "최적화후폐국"]:
        sub = df[df["biz_type"] == biz]
        groups.append({
            "사업유형":    biz,
            "건수":        len(sub),
            "임차+전기":   len(sub[sub["sav_type"] == "임차+전기"]),
            "전기만":      len(sub[sub["sav_type"] == "전기만"]),
            "절감없음":    len(sub[sub["sav_type"] == "절감없음"]),
            "임차료절감":  round(sub["savings_ann"].sum() * 0.85 / 10000, 2),
            "전기료절감":  round(sub["elec_ann"].sum() / 10000, 2),
            "투자비":      round(sub["inv_total"].sum() / 10000, 2),
            "순절감":      round(sub["net_savings"].sum() / 10000, 2),
            "평균BEP":     sub["bep_months"].dropna().mean(),
        })
    return pd.DataFrame(groups)


def equipment_summary(df: pd.DataFrame) -> dict:
    """
    철거 장비 수량 집계 (월별 × 장비Type).
    실제 데이터에 장비 수량 컬럼이 없을 경우 사이트 수로 추정.
    """
    TYPES = ["RRU", "BBU", "안테나", "기타"]
    RATIOS = [0.40, 0.20, 0.30, 0.10]  # 장비 비율 추정
    result = {}
    for m in ["1월", "2월", "3월", "4월"]:
        cnt = len(df[df["off_month"] == m])
        total_eq = cnt * 2.5  # 사이트당 평균 2.5대 추정
        result[m] = {t: int(total_eq * r) for t, r in zip(TYPES, RATIOS)}
    return result


def voc_summary(df: pd.DataFrame) -> pd.DataFrame:
    """VoC 월별 현황"""
    rows = []
    remain = 0
    for m in ["1월", "2월", "3월"]:
        sub = df[df["off_month"] == m]
        issued = sub["voc"].notna().sum() if "voc" in df.columns else 0
        # 샘플: 발생의 80% 처리 완료 가정
        done = int(issued * 0.75)
        remain += (issued - done)
        rows.append({"월": m, "발생": issued, "처리완료": done, "미처리누계": remain})
    return pd.DataFrame(rows)