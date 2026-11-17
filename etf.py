"""
ETF — Analyse et comparaison de fonds indiciels
===============================================

Un ETF (« tracker ») réplique un indice : en une seule ligne, on achète des centaines d'entreprises.
Pour un débutant, c'est souvent le premier placement. Ce qui compte :

  - les FRAIS annuels (TER) : ils sont prélevés chaque année, l'effet se cumule sur 20 ou 30 ans
  - ce qu'il contient : principales lignes, secteurs, concentration (poids des 10 premières lignes)
  - le mode de réplication (physique ou synthétique par swap) et la politique de dividendes
    (capitalisant : réinvestis ; distribuant : versés)
  - l'éligibilité au PEA (fiscalité avantageuse après 5 ans)
  - performance, volatilité et perte maximale passées
"""

import math

import numpy as np
import pandas as pd
import yfinance as yf

POPULAIRES = [
    ("CW8.PA", "Amundi MSCI World (capitalisant)"), ("WPEA.PA", "iShares MSCI World PEA"),
    ("PE500.PA", "Amundi PEA S&P 500"), ("ESE.PA", "BNP Paribas Easy S&P 500"), ("PUST.PA", "Amundi PEA Nasdaq-100"),
    ("C40.PA", "Amundi CAC 40"), ("MEUD.PA", "Amundi Stoxx Europe 600"), ("PAEEM.PA", "Amundi PEA Émergents"),
    ("IWDA.AS", "iShares Core MSCI World"), ("VWCE.DE", "Vanguard FTSE All-World"),
    ("SPY", "SPDR S&P 500 (États-Unis)"), ("QQQ", "Invesco QQQ Nasdaq-100 (États-Unis)"),
]
SECTEURS = {"realestate": "Immobilier", "consumer_cyclical": "Consommation cyclique", "basic_materials": "Matériaux",
            "consumer_defensive": "Consommation de base", "technology": "Technologie", "communication_services": "Communication",
            "financial_services": "Finance", "utilities": "Services aux collectivités", "industrials": "Industrie",
            "energy": "Énergie", "healthcare": "Santé"}
PLACES_UE = (".PA", ".AS", ".DE", ".MI", ".BR", ".LS", ".MC", ".F", ".DU")


def _f(x):
    try:
        x = float(x)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def analyser(ticker: str) -> dict:
    k = yf.Ticker(ticker)
    info = k.info or {}
    if info.get("quoteType") not in ("ETF", "MUTUALFUND"):
        raise ValueError(f"{ticker} n'est pas un ETF d'après Yahoo Finance (type : {info.get('quoteType') or 'inconnu'}).")
    nom = info.get("longName") or info.get("shortName") or ticker
    n = nom.lower()
    ter = _f(info.get("netExpenseRatio"))
    ter = ter / 100 if ter is not None else None
    fd = None
    try:
        fd = k.funds_data
        if ter is None:
            ops = fd.fund_operations
            ter = _f(ops.loc["Annual Report Expense Ratio"].iloc[0]) if ops is not None and "Annual Report Expense Ratio" in ops.index else None
    except Exception:
        pass
    lignes, secteurs = [], []
    try:
        th = fd.top_holdings
        if th is not None and not th.empty:
            lignes = [{"ticker": t, "nom": r["Name"], "poids": float(r["Holding Percent"])} for t, r in th.head(10).iterrows()]
        secteurs = sorted([{"secteur": SECTEURS.get(s, s), "poids": float(p)} for s, p in (fd.sector_weightings or {}).items() if p],
                          key=lambda x: -x["poids"])
    except Exception:
        pass
    px = k.history(period="10y", auto_adjust=True)["Close"].dropna()
    if len(px) < 30:
        raise ValueError("Historique de cours insuffisant pour cet ETF.")
    r = px.pct_change().dropna()
    perf = {}
    for an in (1, 3, 5, 10):
        sous = px[px.index >= px.index[-1] - pd.DateOffset(years=an)]
        if len(sous) and (sous.index[0] - (px.index[-1] - pd.DateOffset(years=an))).days < 15:
            perf[f"{an} an" + ("s" if an > 1 else "")] = float((sous.iloc[-1] / sous.iloc[0]) ** (1 / an) - 1)
    dd = float((px / px.cummax() - 1).min())
    ue = ticker.endswith(PLACES_UE)
    if "pea" in n:
        pea = "Oui (indiqué dans le nom du fonds)"
    elif not ue:
        pea = "Non : coté hors de l'Union européenne"
    else:
        pea = "À vérifier dans le document d'information (DIC) du fonds"
    replication = ("Synthétique (swap) : l'ETF détient d'autres actions et échange leur performance contre celle de l'indice "
                   "avec une banque ; c'est ce qui permet de loger le monde ou les États-Unis dans un PEA." if "swap" in n else
                   "Synthétique (swap) : c'est toujours le cas d'un ETF PEA sur un indice hors d'Europe, car le PEA impose de "
                   "détenir des actions européennes." if ("pea" in n and not any(x in n for x in ("cac", "euro", "europe"))) else
                   "Physique : l'ETF détient réellement les actions de l'indice." if (" dr" in n or "physical" in n or "core" in n) else
                   "Non précisé dans le nom")
    dividendes = ("Capitalisant : les dividendes sont réinvestis automatiquement (pas d'impôt tant qu'on ne vend pas)." if any(x in n for x in (" acc", "(c)", " c", "accumulation", "capitalis")) else
                  "Distribuant : les dividendes sont versés (imposables hors PEA)." if any(x in n for x in ("dist", "(d)", " d ")) else "Non précisé")
    return {"ticker": ticker, "nom": nom, "devise": info.get("currency") or "", "famille": info.get("fundFamily") or "",
            "categorie": info.get("category"), "ter": ter, "encours": _f(info.get("totalAssets")), "cours": float(px.iloc[-1]),
            "perf": perf, "volatilite": float(r.std() * np.sqrt(252)), "perte_max": dd, "lignes": lignes,
            "concentration": sum(x["poids"] for x in lignes) if lignes else None, "secteurs": secteurs, "pea": pea,
            "replication": replication, "dividendes": dividendes, "debut": str(px.index[0].date()),
            "cout_frais": cout_frais(ter), "serie": [[str(d.date()), float(v)] for d, v in px.resample("W").last().dropna().items()]}


def cout_frais(ter, capital=10000.0, rendement=0.07, annees=20):
    """Ce que coûtent les frais : 10 000 sur 20 ans à 7 % brut par an."""
    if ter is None:
        return None
    sans = capital * (1 + rendement) ** annees
    avec = capital * (1 + rendement - ter) ** annees
    return {"capital": capital, "annees": annees, "rendement": rendement, "sans_frais": sans, "avec_frais": avec, "cout": sans - avec}


def comparer(t1: str, t2: str) -> dict:
    a, b = analyser(t1), analyser(t2)
    s1 = pd.Series({d: v for d, v in a["serie"]})
    s2 = pd.Series({d: v for d, v in b["serie"]})
    d = pd.concat([s1, s2], axis=1, join="inner").pct_change().dropna()
    corr = float(d.corr().iloc[0, 1]) if len(d) > 20 else None
    communs = {x["ticker"] for x in a["lignes"]} & {x["ticker"] for x in b["lignes"]}
    return {"a": a, "b": b, "correlation": corr, "lignes_communes": sorted(communs), "lecture": lecture_comparaison(a, b, corr, communs)}


def lecture_comparaison(a, b, corr, communs) -> list:
    p = lambda x: "—" if x is None else f"{x * 100:.2f} %".replace(".", ",")
    ph = []
    if a["ter"] is not None and b["ter"] is not None and a["ter"] != b["ter"]:
        moins = a if a["ter"] < b["ter"] else b
        plus = b if moins is a else a
        ecart = (plus["cout_frais"]["cout"] - moins["cout_frais"]["cout"]) if plus["cout_frais"] and moins["cout_frais"] else None
        ph.append(f"{moins['ticker']} est le moins cher ({p(moins['ter'])} par an contre {p(plus['ter'])})"
                  + (f" : sur 10 000 placés 20 ans, la différence de frais représente environ {ecart:,.0f} €.".replace(",", " ") if ecart else "."))
    if corr is not None:
        ph.append(f"Corrélation des rendements hebdomadaires : {corr:.2f}".replace(".", ",") + ". "
                  + ("Les deux ETF évoluent presque à l'identique : les détenir ensemble n'apporte quasiment aucune diversification."
                     if corr > 0.95 else "Ils sont liés mais différents : les associer diversifie un peu." if corr > 0.75 else
                     "Ils évoluent assez différemment : les associer diversifie réellement."))
    if communs:
        ph.append(f"{len(communs)} de leurs 10 premières lignes sont communes ({', '.join(sorted(communs)[:6])}).")
    return ph


if __name__ == "__main__":
    for t in ("CW8.PA", "PE500.PA", "SPY"):
        e = analyser(t)
        print(t, e["nom"], "| TER", e["ter"], "| perf", {k: round(v, 3) for k, v in e["perf"].items()}, "| vol", round(e["volatilite"], 3),
              "| lignes", len(e["lignes"]), "| secteurs", e["secteurs"][:2], "| PEA", e["pea"][:20], "|", e["dividendes"][:12], "|", e["replication"][:12])
    c = comparer("CW8.PA", "PE500.PA")
    print(c["correlation"], c["lecture"])
