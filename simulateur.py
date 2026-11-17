"""
SIMULATEUR — Investir chaque mois (« DCA », investissement programmé)
=====================================================================

« Si j'avais investi X € au départ puis Y € chaque mois dans tel indice ou telle action
depuis telle date, combien aurais-je aujourd'hui ? »

Compare trois stratégies avec exactement les mêmes sommes versées :
  - versements mensuels dans l'actif choisi ;
  - tout placer au début (même montant total, investi dès le premier jour) ;
  - versements mensuels sur un placement sans risque (livret à 3 %).

Les montants sont en euros : un actif coté dans une autre devise est converti chaque jour.

Lancer :  .venv/bin/python simulateur.py ^FCHI 1000 100 2010-01
"""

import sys
from datetime import date

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.optimize import brentq

import partie2_performance as p2

RF = p2.TAUX_SANS_RISQUE

# Actifs proposés par défaut (code Yahoo, nom, remarque)
PRESETS = [
    ("^FCHI", "CAC 40", "Indice de prix : sans les dividendes (environ 2 à 3 % par an de moins que la réalité)."),
    ("^GSPC", "S&P 500", "Indice de prix en dollars, converti en euros ; sans les dividendes."),
    ("URTH", "MSCI World (ETF)", "Fonds indiciel mondial (1 500 entreprises de 23 pays), dividendes réinvestis, converti en euros."),
    ("^STOXX50E", "Euro Stoxx 50", "Indice de prix : sans les dividendes."),
    ("^IXIC", "Nasdaq", "Indice de prix en dollars (technologie), converti en euros."),
    ("GC=F", "Or", "Prix de l'once d'or en dollars, converti en euros. L'or ne verse aucun revenu."),
]


def _devise(ticker: str) -> str:
    for code, dev in [("^FCHI", "EUR"), ("^STOXX50E", "EUR"), ("^GDAXI", "EUR"), ("^GSPC", "USD"),
                      ("^IXIC", "USD"), ("^DJI", "USD"), ("URTH", "USD"), ("GC=F", "USD"), ("BZ=F", "USD"),
                      ("^N225", "JPY"), ("^FTSE", "GBP")]:
        if ticker == code:
            return dev
    try:
        return yf.Ticker(ticker).fast_info.get("currency") or "EUR"
    except Exception:
        return "EUR"


def cours_en_euros(ticker: str, debut: pd.Timestamp) -> pd.Series:
    s = yf.download(ticker, start=debut - pd.Timedelta(days=7), auto_adjust=True, progress=False)["Close"].squeeze()
    if isinstance(s, pd.DataFrame) or s is None or s.dropna().empty:
        raise ValueError(f"Pas d'historique pour {ticker}.")
    s = s.dropna()
    dev = _devise(ticker)
    if dev == "GBp":                    # Londres cote parfois en pence
        s, dev = s / 100, "GBP"
    if dev != "EUR":
        fx = yf.download(f"{dev}EUR=X", start=debut - pd.Timedelta(days=7), auto_adjust=True,
                         progress=False)["Close"].squeeze().dropna()
        s = (s * fx.reindex(s.index).ffill().bfill()).dropna()
    return s[s.index >= debut]


def tri_annuel(flux: list) -> float:
    """Taux de rendement interne annualisé (XIRR) : flux = [(date, montant)], versements négatifs."""
    t0 = flux[0][0]
    ans = np.array([(d - t0).days / 365.25 for d, _ in flux])
    montants = np.array([m for _, m in flux])
    f = lambda r: np.sum(montants / (1 + r) ** ans)
    try:
        return brentq(f, -0.99, 10)
    except ValueError:
        return np.nan


def simuler(ticker: str, initial: float, mensuel: float, debut: str) -> dict:
    debut = pd.Timestamp(debut + "-01") if len(debut) == 7 else pd.Timestamp(debut)
    if debut >= pd.Timestamp.today() - pd.Timedelta(days=60):
        raise ValueError("Choisis une date de départ d'au moins deux mois dans le passé.")
    prix = cours_en_euros(ticker, debut)
    if len(prix) < 40:
        raise ValueError("Historique trop court pour cette date de départ.")

    # Jours de versement : première séance de chaque mois
    jours = prix.groupby(prix.index.to_period("M")).head(1).index
    versements = pd.Series(mensuel, index=jours)
    versements.iloc[0] += initial
    parts = (versements / prix.loc[jours]).reindex(prix.index).fillna(0).cumsum()
    verse = versements.reindex(prix.index).fillna(0).cumsum()
    valeur = parts * prix

    total = float(versements.sum())
    tout_au_debut = total * prix / prix.iloc[0]

    # Livret : mêmes versements, rémunérés au taux sans risque (intérêts composés quotidiens)
    taux_jour = (1 + RF) ** (1 / 365.25) - 1
    livret, solde, precedent = [], 0.0, prix.index[0]
    for d in prix.index:
        solde *= (1 + taux_jour) ** (d - precedent).days
        solde += versements.get(d, 0.0)
        livret.append(solde)
        precedent = d
    livret = pd.Series(livret, index=prix.index)

    flux = [(d, -m) for d, m in versements.items()] + [(prix.index[-1], float(valeur.iloc[-1]))]
    tri = tri_annuel(flux)
    # Pire moment pour l'investisseur : plus forte baisse de la valeur par rapport aux sommes versées
    ratio = valeur / verse
    pire = float((valeur - verse).min())
    date_pire = (valeur - verse).idxmin()

    def reduire(s, n=400):
        if len(s) > n:
            s = s.iloc[np.linspace(0, len(s) - 1, n).astype(int)]
        return [[d.strftime("%Y-%m-%d"), round(float(v), 2)] for d, v in s.items()]

    par_annee = valeur.groupby(valeur.index.year).last()
    verse_annee = verse.groupby(verse.index.year).last()
    return {
        "ticker": ticker, "debut": prix.index[0].strftime("%d/%m/%Y"), "fin": prix.index[-1].strftime("%d/%m/%Y"),
        "nb_versements": int(len(versements)), "total_verse": total,
        "valeur_finale": float(valeur.iloc[-1]), "plus_value": float(valeur.iloc[-1] - total),
        "multiple": float(valeur.iloc[-1] / total), "tri": tri,
        "valeur_tout_au_debut": float(tout_au_debut.iloc[-1]), "valeur_livret": float(livret.iloc[-1]),
        "pire_ecart": pire, "date_pire": date_pire.strftime("%d/%m/%Y"),
        "jours_sous_l_eau": float((ratio < 1).mean()),
        "series": {"Valeur de tes versements": reduire(valeur), "Sommes versées": reduire(verse),
                   "Tout investi au début": reduire(tout_au_debut), f"Livret à {RF:.0%}": reduire(livret)},
        "annees": [{"annee": int(a), "verse": float(verse_annee[a]), "valeur": float(v)} for a, v in par_annee.items()],
    }


if __name__ == "__main__":
    t, ini, men, deb = (sys.argv[1:] + ["^FCHI", "1000", "100", "2010-01"][len(sys.argv) - 1:])[:4]
    r = simuler(t, float(ini), float(men), deb)
    for k, v in r.items():
        if k not in ("series", "annees"):
            print(f"{k:<24}: {v}")
