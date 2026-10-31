"""Etapa 2 — Find the signal. Reproduce las cifras de docs/etapa2_resumen.md.

Uso (desde la raíz del repo, con dataset_start/ en local):
    .venv/bin/python src/analysis/etapa2_signal.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import clean  # noqa: E402

SEED, N = 7, 200_000
HIGH_VOL = ["VF_A02", "VF_A03", "VF_A06", "VF_A07"]  # vol anual > 30% (supuesto para CL_02)
CUT = pd.Timestamp("2026-04-10")  # 2/3 train, 1/3 test
CLIENTS = [("CL_01", "USD", 0.22), ("CL_02", "COP", 0.10), ("CL_03", "PEN", 0.15)]


def local_prices(px: pd.DataFrame, macro: pd.DataFrame, ccy: str) -> pd.DataFrame:
    fx = {"USD": 1.0, "COP": macro.usd_cop, "PEN": macro.usd_pen}[ccy]
    return px.mul(fx, axis=0)


def nav_stats(px: pd.DataFrame, W: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Buy & hold: retorno total y max drawdown por cartera (columnas de W.T)."""
    nav = (px / px.iloc[0]).values @ W.T
    dd = (nav / np.maximum.accumulate(nav, axis=0) - 1).min(axis=0)
    return nav[-1] - 1, dd


def constraint_mask(cid: str, W: np.ndarray, assets: list[str], ref: pd.DataFrame) -> np.ndarray:
    sec = ref.loc[assets, "sector"].values
    ctry = ref.loc[assets, "country"].values
    if cid == "CL_01":
        by_sector = pd.DataFrame(W, columns=sec).T.groupby(level=0).sum().T.values
        return by_sector.max(axis=1) <= 0.45
    if cid == "CL_02":
        return W[:, np.isin(assets, HIGH_VOL)].sum(axis=1) <= 0.25
    held = W > 0.05
    n_ctry = pd.DataFrame(held, columns=ctry).T.groupby(level=0).any().T.sum(axis=1).values
    n_sec = pd.DataFrame(held, columns=sec).T.groupby(level=0).any().T.sum(axis=1).values
    return (n_ctry >= 3) & (n_sec >= 3)


def main() -> None:
    p, macro = clean.prices_daily(), clean.macro_daily().set_index("date")
    ref = clean.ref().set_index("asset_id")
    px = p.pivot(index="date", columns="asset_id", values="close").sort_index()
    assets = list(px.columns)
    W = np.random.default_rng(SEED).dirichlet(np.full(len(assets), 0.6), N)
    ew = np.full((1, len(assets)), 1 / len(assets))

    print("== Selección de foco: factibilidad por cliente (in-sample, 200k carteras)")
    for cid, ccy, tol in CLIENTS:
        loc = local_prices(px, macro, ccy)
        ret, dd = nav_stats(loc, W)
        ok = constraint_mask(cid, W, assets, ref)
        feas = ok & (dd >= -tol)
        _, dd_ew = nav_stats(loc, ew)
        print(f"{cid} {ccy} tol {tol:.0%}: cumplen restricción {ok.mean():.1%} | "
              f"+ drawdown {feas.mean():.2%} | EW drawdown {dd_ew[0]:.1%}")

    print("\n== CL_02 fuera de muestra (train < 2026-04-10 <= test)")
    loc = local_prices(px, macro, "COP")
    Wc = W[constraint_mask("CL_02", W, assets, ref)]
    tr, te = loc[loc.index < CUT], loc[loc.index >= CUT]
    r_tr, d_tr = nav_stats(tr, Wc)
    r_te, d_te = nav_stats(te, Wc)
    i = int(np.argmax(d_tr))
    print(f"min-DD en train: train DD {d_tr[i]:.1%} -> test DD {d_te[i]:.1%} (ret test {r_te[i]:.1%})")
    print(f"carteras válidas con DD<=10% en test: {(d_te >= -0.10).mean():.1%}")


if __name__ == "__main__":
    main()
