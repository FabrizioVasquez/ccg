"""Validación de confiabilidad de dataset_start/. Solo lectura: imprime hallazgos.

Uso: python src/validacion.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(__file__).resolve().parent.parent / "dataset_start"


def leer(nombre):
    # utf-8-sig: los CSV traen BOM en la cabecera
    return pd.read_csv(D / nombre, encoding="utf-8-sig")


def fecha(serie, etiqueta):
    """Parsea ISO y MM/DD/YYYY (hay filas con ese formato mezclado). Reporta cuántas no son ISO."""
    iso = pd.to_datetime(serie, format="ISO8601", errors="coerce")
    resto = iso.isna() & serie.notna()
    if resto.any():
        us = pd.to_datetime(serie[resto], format="%m/%d/%Y %H:%M:%S", errors="coerce")
        us = us.fillna(pd.to_datetime(serie[resto], format="%m/%d/%Y", errors="coerce"))
        iso[resto] = us
    print(f"[{etiqueta}] fechas no ISO: {resto.sum()} | sin parsear: {iso.isna().sum()}")
    return iso


def normalizar_mercado(df, etiqueta):
    """Corrige variantes de asset_id y volumen con sufijo K. Reporta cuántas filas toca."""
    ids = df["asset_id"].str.extract(r"^VF[-_]?A0?(\d)$")[0]
    nuevo = "VF_A0" + ids
    malos_id = df["asset_id"].ne(nuevo) & ids.notna()
    sin_id = ids.isna()
    df["asset_id"] = nuevo.where(ids.notna(), df["asset_id"])
    vol = df["volume"].astype(str)
    k = vol.str.endswith("K")
    num = pd.to_numeric(vol.str.rstrip("K"), errors="coerce")
    df["volume"] = num.where(~k, num * 1000)
    print(f"[{etiqueta}] asset_id corregido: {malos_id.sum()} ({df.loc[malos_id, 'asset_id'].value_counts().to_dict()}) | asset_id irreconocible: {sin_id.sum()} | volumen con 'K': {k.sum()}")
    return df


def titulo(t):
    print(f"\n{'=' * 8} {t} {'=' * 8}")


def generales(nombre, df):
    nulos = df.isna().sum()
    nulos = nulos[nulos > 0].to_dict()
    print(f"{nombre}: {df.shape[0]} filas x {df.shape[1]} cols | duplicados exactos: {df.duplicated().sum()} | nulos: {nulos or 'ninguno'}")


def ohlc(df, etiqueta):
    o, h, l, c, v = (df[x] for x in ("open", "high", "low", "close", "volume"))
    malos_hl = (h < np.maximum(o, c)) | (l > np.minimum(o, c)) | (h < l)
    print(f"[{etiqueta}] OHLC incoherente: {malos_hl.sum()} | precio<=0: {((df[['open','high','low','close']] <= 0).any(axis=1)).sum()} | volumen<=0: {(v <= 0).sum()}")
    return malos_hl


def mercado_diario():
    titulo("01_market_prices_raw (diario)")
    df = leer("01_market_prices_raw.csv")
    generales("diario", df)
    df = normalizar_mercado(df, "diario")
    print("dups (date, asset_id) tras normalizar:", df.duplicated(["date", "asset_id"]).sum(), "| duplicados exactos tras normalizar:", df.duplicated().sum())
    df["date"] = fecha(df["date"], "diario")
    print("rango:", df["date"].min().date(), "->", df["date"].max().date(), "| activos:", df["asset_id"].nunique())
    print("dups (date, asset_id):", df.duplicated(["date", "asset_id"]).sum())
    print("filas por activo:", df.groupby("asset_id").size().to_dict())
    print("mercado/moneda:", df.groupby("asset_id")[["market", "currency"]].nunique().max().to_dict())
    ohlc(df, "diario")
    fds = df["date"].dt.dayofweek >= 5
    print("filas en fin de semana:", fds.sum())
    df = df.sort_values(["asset_id", "date"])
    df["ret"] = df.groupby("asset_id")["close"].pct_change()
    print("retornos |r|>10%:", (df["ret"].abs() > 0.10).sum(), "| max |r|:", round(df["ret"].abs().max(), 4))
    print("retorno diario std por activo:", df.groupby("asset_id")["ret"].std().round(4).to_dict())
    return df


def mercado_expandido():
    titulo("01_market_prices_raw_expanded (10 min)")
    df = leer("01_market_prices_raw_expanded.csv")
    generales("expanded", df)
    df = normalizar_mercado(df, "expanded")
    df["date"] = fecha(df["date"], "expanded")
    print("rango:", df["date"].min(), "->", df["date"].max(), "| activos:", df["asset_id"].nunique())
    print("dups (date, asset_id):", df.duplicated(["date", "asset_id"]).sum())
    print("filas por activo:", df.groupby("asset_id").size().to_dict())
    ohlc(df, "expanded")
    print("horas distintas en el día:", sorted(df["date"].dt.strftime("%H:%M").unique())[:3], "...", sorted(df["date"].dt.strftime("%H:%M").unique())[-1])
    print("filas en fin de semana:", (df["date"].dt.dayofweek >= 5).sum())
    df = df.sort_values(["asset_id", "date"])
    r = df.groupby("asset_id")["close"].pct_change()
    print("retornos intradía |r|>5%:", (r.abs() > 0.05).sum(), "| max |r|:", round(r.abs().max(), 4))
    return df


def diario_vs_expandido(dia, exp):
    titulo("Diario vs expanded (cierre del día)")
    exp = exp.copy()
    exp["d"] = exp["date"].dt.normalize()
    cierre = exp.sort_values("date").groupby(["asset_id", "d"])["close"].last().rename("close_exp").reset_index()
    j = dia.rename(columns={"date": "d"}).merge(cierre, on=["asset_id", "d"], how="outer", indicator=True)
    print("combinación activo-día:", j["_merge"].value_counts().to_dict())
    both = j[j["_merge"] == "both"].copy()
    if both.empty:
        print("sin solape de fechas")
        return
    both["dif"] = (both["close"] / both["close_exp"] - 1).abs()
    print("solape:", len(both), "| dif relativa mediana:", round(both["dif"].median(), 5), "| p99:", round(both["dif"].quantile(0.99), 5), "| max:", round(both["dif"].max(), 5))
    print("filas con dif>1%:", (both["dif"] > 0.01).sum())


def macro():
    titulo("02_macro_raw")
    df = leer("02_macro_raw.csv")
    generales("macro", df)
    df["date"] = pd.to_datetime(df["date"])
    print("rango:", df["date"].min().date(), "->", df["date"].max().date(), "| dups fecha:", df["date"].duplicated().sum())
    print("fines de semana:", (df["date"].dt.dayofweek >= 5).sum(), "| huecos >4 días:", (df["date"].diff().dt.days > 4).sum())
    print("risk_regime:", df["risk_regime"].value_counts(dropna=False).to_dict())
    print(df.describe().round(3).T[["min", "mean", "max"]].to_string())
    for c in ("usd_cop", "usd_pen", "usd_mxn", "usd_clp", "us_10y_yield"):
        saltos = df[c].pct_change().abs()
        print(f"saltos diarios >3% en {c}:", (saltos > 0.03).sum())
    print("inflación valores distintos:", df["us_inflation_yoy"].dropna().unique()[:8])
    return df


def fundamentales(ref):
    titulo("03_fundamentals_raw")
    df = leer("03_fundamentals_raw.csv")
    generales("fundamentals", df)
    raros = df[~df["period_end"].astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}")]
    print("period_end con formato raro:", raros["period_end"].tolist())
    df["revenue_usd_m"] = pd.to_numeric(df["revenue_usd_m"].astype(str).str.replace(",", ""), errors="coerce")
    print("periodos por emisor:", df.groupby("issuer_id").size().to_dict())
    print("dups (issuer, periodo):", df.duplicated(["issuer_id", "period_end"]).sum())
    print("rango:", df["period_end"].min(), "->", df["period_end"].max())
    num = df.select_dtypes("number")
    print("valores negativos por columna:", (num < 0).sum().to_dict())
    print("EBITDA > ingresos:", (df["ebitda_usd_m"] > df["revenue_usd_m"]).sum(), "| utilidad > EBITDA:", (df["net_income_usd_m"] > df["ebitda_usd_m"]).sum())
    df = df.sort_values(["issuer_id", "period_end"])
    sal = df.groupby("issuer_id")[["revenue_usd_m", "debt_usd_m"]].pct_change().abs()
    print("saltos trimestrales >30% (ingresos/deuda):", (sal > 0.30).sum().to_dict())
    print("emisores sin referencia:", set(df["issuer_id"]) - set(ref["issuer_id"]), "| referencia sin fundamentales:", set(ref["issuer_id"]) - set(df["issuer_id"]))


def integridad(dia, exp, ref, cli, ev):
    titulo("Integridad entre tablas")
    print("activos en referencia:", ref["asset_id"].nunique(), "| dups:", ref["asset_id"].duplicated().sum())
    print("activos en diario sin referencia:", set(dia["asset_id"]) - set(ref["asset_id"]))
    print("activos en expanded sin referencia:", set(exp["asset_id"]) - set(ref["asset_id"]))
    print("activos en referencia sin precios:", set(ref["asset_id"]) - set(dia["asset_id"]))
    m = dia.drop_duplicates("asset_id").merge(ref, on="asset_id", suffixes=("_px", "_ref"))
    print("mercado distinto px vs ref:", (m["market_px"] != m["market_ref"]).sum(), "| moneda distinta:", (m["currency_px"] != m["currency_ref"]).sum())
    sectores = set(ref["sector"])
    ids = set(ref["asset_id"])
    inval = ev[~ev["scope"].isin(ids | sectores)]
    print("eventos con scope inválido:", len(inval))
    ev["event_date"] = pd.to_datetime(ev["event_date"])
    print("eventos fuera del rango del diario:", ((ev["event_date"] < dia["date"].min()) | (ev["event_date"] > dia["date"].max())).sum())
    print("distribución del universo -> sectores:", ref["sector"].nunique(), "| países:", ref["country"].nunique(), ref["country"].value_counts().to_dict())
    print("CL_03 requiere >=3 países y >=3 sectores: universo OK" if ref["country"].nunique() >= 3 and ref["sector"].nunique() >= 3 else "CL_03 inviable con este universo")


def main():
    ref = leer("04_asset_reference.csv")
    cli = leer("05_client_profiles.csv")
    ev = leer("06_events.csv")
    titulo("Tablas pequeñas")
    for n, d in (("reference", ref), ("clients", cli), ("events", ev)):
        generales(n, d)
    dia = mercado_diario()
    exp = mercado_expandido()
    diario_vs_expandido(dia, exp)
    macro()
    fundamentales(ref)
    integridad(dia, exp, ref, cli, ev)


if __name__ == "__main__":
    main()
