"""
OPTIONS COTÉES — Les vrais prix d'options du marché (actions américaines)
========================================================================

Pour une action et une échéance : tous les calls et puts cotés (prix d'exercice, dernier prix,
achat/vente, volume, positions ouvertes) et leur VOLATILITÉ IMPLICITE, c'est-à-dire la volatilité
qu'il faut mettre dans Black-Scholes pour retrouver le prix du marché.

On la compare à la volatilité HISTORIQUE (passée) et au prix théorique Black-Scholes de la partie 6.
Le « sourire de volatilité » (la volatilité implicite plus forte loin de la monnaie) montre que le
marché anticipe plus de krachs que ne le prévoit la loi normale.

Yahoo Finance ne fournit pas les options d'Euronext : seules les actions américaines sont couvertes.
"""

import math

import numpy as np
import pandas as pd
import yfinance as yf

import partie6_simulation as p6
from partie2_performance import TAUX_SANS_RISQUE


def echeances(ticker: str) -> list:
    try:
        return list(yf.Ticker(ticker).options)
    except Exception:
        return []


def chaine(ticker: str, echeance: str = None) -> dict:
    k = yf.Ticker(ticker)
    toutes = list(k.options or [])
    if not toutes:
        raise ValueError(f"Pas d'options cotées pour {ticker} (Yahoo Finance ne couvre que les actions américaines).")
    if echeance not in toutes:
        # par défaut : la première échéance à plus de 20 jours (moins sensible au bruit)
        aujourd_hui = pd.Timestamp.today().normalize()
        echeance = next((e for e in toutes if (pd.Timestamp(e) - aujourd_hui).days >= 20), toutes[0])
    ch = k.option_chain(echeance)
    prix = p6.telecharger_prix(ticker, "1y")
    S = float(prix.iloc[-1])
    vol_hist = p6.volatilite_recente(prix)
    T = max((pd.Timestamp(echeance) - pd.Timestamp.today().normalize()).days, 1) / 365
    r = math.log(1 + TAUX_SANS_RISQUE)

    def lignes(df, type_):
        res = []
        for _, l in df.iterrows():
            K = float(l["strike"])
            if not (0.6 * S <= K <= 1.4 * S):        # on garde les prix d'exercice autour du cours
                continue
            iv = float(l["impliedVolatility"]) if not pd.isna(l["impliedVolatility"]) else None
            bs = p6.black_scholes(S, K, T, r, vol_hist, type_)["Prix"]
            res.append({"strike": K, "dernier": float(l["lastPrice"]), "achat": float(l["bid"] or 0),
                        "vente": float(l["ask"] or 0), "volume": int(l["volume"]) if not pd.isna(l["volume"]) else 0,
                        "positions": int(l["openInterest"]) if not pd.isna(l["openInterest"]) else 0,
                        "vol_implicite": iv if iv and iv > 0.01 else None, "dans_la_monnaie": bool(l["inTheMoney"]),
                        "prix_bs": float(bs)})
        return res
    calls, puts = lignes(ch.calls, "call"), lignes(ch.puts, "put")
    proche = lambda xs: min(xs, key=lambda x: abs(x["strike"] - S)) if xs else None
    atm_c, atm_p = proche(calls), proche(puts)
    iv_atm = np.nanmean([x["vol_implicite"] for x in (atm_c, atm_p) if x and x["vol_implicite"]] or [np.nan])
    pfr = lambda x: f"{x * 100:.1f} %".replace(".", ",")
    nfr = lambda x: f"{x:.2f}".replace(".", ",")
    lecture = []
    if not np.isnan(iv_atm):
        ecart = iv_atm - vol_hist
        lecture.append(f"Volatilité implicite à la monnaie : {pfr(iv_atm)} contre {pfr(vol_hist)} de volatilité historique "
                       "sur un an. " + ("Le marché s'attend à plus d'agitation que par le passé (résultats, événement à venir…)."
                                        if ecart > 0.03 else "Le marché s'attend à moins d'agitation que par le passé."
                                        if ecart < -0.03 else "Le marché anticipe une agitation proche de celle du passé."))
        lecture.append(f"D'ici l'échéance, le marché « prévoit » une variation typique de ±{nfr(S * iv_atm * math.sqrt(T))} $ "
                       f"(±{pfr(iv_atm * math.sqrt(T))}) autour du cours actuel de {nfr(S)} $.")
    return {"ticker": ticker, "echeance": echeance, "echeances": toutes, "cours": S, "jours": int(T * 365),
            "vol_historique": vol_hist, "vol_implicite_atm": None if np.isnan(iv_atm) else float(iv_atm),
            "calls": calls, "puts": puts, "lecture": lecture}


if __name__ == "__main__":
    c = chaine("AAPL")
    print(c["echeance"], c["jours"], "jours | cours", round(c["cours"], 2), "| vol hist", round(c["vol_historique"], 3),
          "| IV ATM", c["vol_implicite_atm"])
    for x in c["calls"][::6]:
        print("  call", x)
    print(c["lecture"])
