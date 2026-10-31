"""Señales y viabilidad de cartera por cliente (serie diaria ago-2025 a ago-2026).

Uso: python src/senales.py
Reproduce las cifras de docs/encuadre_problema.md.
"""
import contextlib
import io

import numpy as np
import pandas as pd

import validacion as v


def precios():
    with contextlib.redirect_stdout(io.StringIO()):
        dia = v.mercado_diario()
    dia = dia.drop_duplicates(["date", "asset_id"]).copy()
    # error de ×100 documentado en docs/validacion_datos.md
    dia.loc[(dia.asset_id == "VF_A06") & (dia.date == "2026-03-23"), "close"] = 35.89
    return dia.pivot(index="date", columns="asset_id", values="close").sort_index()


def metricas(px):
    r = px.pct_change()
    return pd.DataFrame({
        "ret_total": px.iloc[-1] / px.iloc[0] - 1,
        "ret_3m": px.iloc[-1] / px.iloc[-64] - 1,
        "vol_anual": r.std() * np.sqrt(252),
        "max_dd": (px / px.cummax() - 1).min(),
        "dd_actual": px.iloc[-1] / px.cummax().iloc[-1] - 1,
    })


def viabilidad(px, ref, mac, n=60000, seed=0):
    # ponytail: búsqueda aleatoria de pesos (Dirichlet); optimizador real si hace falta precisión
    vol = px.pct_change().std() * np.sqrt(252)
    alta = (vol > 0.30).values
    rng = np.random.default_rng(seed)
    W = np.vstack([rng.dirichlet(np.ones(8) * 0.5, n), np.ones((1, 8)) / 8])
    ref = ref.set_index("asset_id").loc[px.columns]
    sec = pd.get_dummies(ref.sector).values.astype(float)
    ctry = pd.get_dummies(ref.country).values.astype(float)
    fx = {"USD": None, "COP": mac.usd_cop, "PEN": mac.usd_pen}
    clientes = (("CL_01", "USD", 0.22), ("CL_02", "COP", 0.10), ("CL_03", "PEN", 0.15))
    for cl, cur, dd in clientes:
        loc = px if fx[cur] is None else px.mul(fx[cur], axis=0)
        rl = loc.pct_change().fillna(0).values
        nav = np.cumprod(1 + rl @ W.T, axis=0)
        mdd = (nav / np.maximum.accumulate(nav, axis=0) - 1).min(0)
        ret = nav[-1] - 1
        ok = {
            "CL_01": (W @ sec).max(1) <= 0.45,
            "CL_02": W[:, alta].sum(1) <= 0.25,
            "CL_03": ((W @ sec >= 0.05).sum(1) >= 3) & ((W @ ctry >= 0.05).sum(1) >= 3),
        }[cl]
        feas = ok & (-mdd <= dd)
        print(f"\n{cl} ({cur}, DD máx {dd:.0%}): cumplen restricción {ok.sum()} | además DD {feas.sum()} | equiponderada ret {ret[-1]:.1%} dd {mdd[-1]:.1%}")
        if feas.any():
            for etiqueta, i in (("mejor retorno", np.where(feas)[0][ret[feas].argmax()]),
                                ("menor DD", np.where(feas)[0][(-mdd[feas]).argmin()])):
                pesos = {a: round(w, 2) for a, w in zip(px.columns, W[i]) if w > 0.03}
                print(f"  {etiqueta}: ret {ret[i]:.1%} dd {mdd[i]:.1%} {pesos}")
    print("\nactivos de alta volatilidad (>30%):", list(px.columns[alta]))


def main():
    px = precios()
    ref = v.leer("04_asset_reference.csv")
    mac = v.leer("02_macro_raw.csv")
    mac["date"] = pd.to_datetime(mac.date)
    mac = mac.set_index("date")
    print(metricas(px).join(ref.set_index("asset_id")[["name", "sector", "country"]]).round(3).to_string())
    for c in ("usd_cop", "usd_pen"):
        print(f"variación {c}: {mac[c].iloc[-1] / mac[c].iloc[0] - 1:.2%}")
    viabilidad(px, ref, mac)


if __name__ == "__main__":
    main()
