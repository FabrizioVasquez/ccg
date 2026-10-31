"""Limpieza mínima reproducible (espejo local de los pipelines de dominio)."""
import re
import numpy as np
import pandas as pd

D = "dataset_start/"
ALIAS = {"VF-A1": "VF_A01", "VFA03": "VF_A03", "VF_A6": "VF_A06", "VF-A6": "VF_A06", "VF-A4": "VF_A04", "ISS04": "ISS_04"}


def _canon(s: pd.Series) -> pd.Series:
    return s.replace(ALIAS)


def _date(s: pd.Series) -> pd.Series:
    iso = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    us = pd.to_datetime(s, format="%m/%d/%Y", errors="coerce")
    return iso.fillna(us)


def prices_daily() -> pd.DataFrame:
    p = pd.read_csv(D + "01_market_prices_raw.csv", encoding="utf-8-sig")
    p["asset_id"] = _canon(p.asset_id)
    p["date"] = _date(p.date)
    p["currency"] = p.currency.fillna("USD")
    p = p.drop_duplicates(["date", "asset_id"]).sort_values(["asset_id", "date"])
    # outlier: close fuera de [low, high] -> se reemplaza por el promedio (open+high+low)/3 y se marca
    bad = (p.close > p.high * 1.5) | (p.close < p.low / 1.5)
    p["close_outlier_flag"] = bad
    p.loc[bad, "close"] = p.loc[bad, ["open", "high", "low"]].mean(axis=1).round(2)
    return p.reset_index(drop=True)


def macro_daily() -> pd.DataFrame:
    m = pd.read_csv(D + "02_macro_raw.csv", encoding="utf-8-sig")
    m["date"] = _date(m.date)
    m = m.sort_values("date")
    m["us_inflation_yoy"] = m.us_inflation_yoy.ffill()
    return m.reset_index(drop=True)


def fundamentals() -> pd.DataFrame:
    f = pd.read_csv(D + "03_fundamentals_raw.csv", encoding="utf-8-sig")
    f["issuer_id"] = _canon(f.issuer_id)
    # "Q4-2024" de ISS_02 está entre 2025-03-31 y 2025-09-30 (orden de filas): es el trimestre faltante 2025-06-30.
    # Mapearlo a 2024-12-31 duplicaría ese trimestre y perdería el real.
    f["period_end"] = pd.to_datetime(f.period_end, format="%Y-%m-%d", errors="coerce")
    for i in f.index[f.period_end.isna()]:
        f.loc[i, "period_end"] = f.loc[i - 1, "period_end"] + pd.offsets.QuarterEnd(1)
    f["revenue_usd_m"] = pd.to_numeric(f.revenue_usd_m.astype(str).str.replace(",", ""), errors="coerce")
    f = f.sort_values(["issuer_id", "period_end"])
    f["cash_usd_m"] = f.groupby("issuer_id").cash_usd_m.ffill()
    # revenue fuera de patrón (>25% bajo la mediana del emisor): se marca y no se usa en ratios
    med = f.groupby("issuer_id").revenue_usd_m.transform("median")
    f["revenue_outlier_flag"] = f.revenue_usd_m < 0.75 * med
    return f.drop_duplicates(["issuer_id", "period_end"]).sort_values(["issuer_id", "period_end"]).reset_index(drop=True)


def ref() -> pd.DataFrame:
    return pd.read_csv(D + "04_asset_reference.csv", encoding="utf-8-sig")


def clients() -> pd.DataFrame:
    return pd.read_csv(D + "05_client_profiles.csv", encoding="utf-8-sig")


def events() -> pd.DataFrame:
    e = pd.read_csv(D + "06_events.csv", encoding="utf-8-sig")
    e["event_date"] = pd.to_datetime(e.event_date)
    return e


def prices_expanded_daily() -> pd.DataFrame:
    x = pd.read_csv(D + "01_market_prices_raw_expanded.csv", encoding="utf-8-sig")
    x["asset_id"] = _canon(x.asset_id)
    ts = pd.to_datetime(x.date, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    ts = ts.fillna(pd.to_datetime(x.date, format="%m/%d/%Y %H:%M:%S", errors="coerce"))
    x["ts"] = ts
    x = x.dropna(subset=["ts"]).drop_duplicates(["ts", "asset_id"]).sort_values(["asset_id", "ts"])
    x["day"] = x.ts.dt.normalize()
    return x.groupby(["asset_id", "day"]).agg(close=("close", "last"), volume=("volume", "sum")).reset_index()
