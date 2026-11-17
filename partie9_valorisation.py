"""
PARTIE 9 — Valorisation (l'action est-elle chère ?) et scores de santé financière
==================================================================================

A. Multiples de marché : PER, VE/EBE, VE/CA, cours / valeur comptable, rendement du FCF
B. Coût du capital (CMPC / WACC) : ce que coûtent ensemble les capitaux propres et la dette
C. DCF (Discounted Cash Flows) : valeur de l'entreprise = somme des flux de trésorerie
   disponibles futurs, actualisés au CMPC, + une valeur terminale
D. Consensus des analystes
E. Scores : Z-score d'Altman (risque de faillite) et F-score de Piotroski (santé financière)

S'appuie sur les comptes déjà chargés par la partie 8.

Lancer :  .venv/bin/python partie9_valorisation.py MC.PA
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf

import partie8_analyse_financiere as p8
from partie8_analyse_financiere import _ligne, div, TAUX_IS, TAUX_SANS_RISQUE, PRIME_RISQUE

CROISSANCE_PERPETUELLE = 0.02   # croissance à l'infini (proche de l'inflation de long terme)
HORIZON = 5                     # années de prévision explicite

SECTEURS_INDUSTRIELS = {"Industrials", "Basic Materials", "Energy", "Consumer Cyclical",
                        "Consumer Defensive", "Healthcare", "Utilities"}


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------
def dernier(s: pd.Series):
    s = s.dropna()
    return s.iloc[-1] if len(s) else np.nan


def taux_change(de: str, vers: str) -> float:
    """Taux pour convertir les comptes (devise de publication) dans la devise de cotation."""
    if not de or not vers or de == vers:
        return 1.0
    try:
        h = yf.download(f"{de}{vers}=X", period="5d", progress=False, auto_adjust=True)["Close"]
        return float(h.squeeze().dropna().iloc[-1])
    except Exception:
        return np.nan


# ---------------------------------------------------------------------------
# DCF
# ---------------------------------------------------------------------------
def dcf(fcf0: float, g: float, g_inf: float, cmpc: float, dfn: float, actions: float,
        horizon: int = HORIZON) -> dict:
    """Valeur par action par actualisation des flux de trésorerie disponibles.

    Flux de l'année t : FCF0 × (1 + g)^t pendant `horizon` ans, puis croissance g_inf à l'infini.
    Valeur terminale (formule de Gordon-Shapiro) : FCF_{n+1} / (CMPC − g_inf).
    """
    if cmpc <= g_inf:
        return {"valeur_action": np.nan}
    flux = [fcf0 * (1 + g) ** t for t in range(1, horizon + 1)]
    actualises = [f / (1 + cmpc) ** t for t, f in enumerate(flux, start=1)]
    vt = flux[-1] * (1 + g_inf) / (cmpc - g_inf)
    vt_actualisee = vt / (1 + cmpc) ** horizon
    ve = sum(actualises) + vt_actualisee           # valeur d'entreprise
    vcp = ve - dfn                                  # valeur des capitaux propres
    return {
        "flux": flux, "flux_actualises": actualises, "valeur_terminale": vt,
        "vt_actualisee": vt_actualisee, "valeur_entreprise": ve, "valeur_capitaux_propres": vcp,
        "valeur_action": vcp / actions if actions else np.nan,
        "part_vt": vt_actualisee / ve if ve else np.nan,
    }


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------
def altman(f: dict, capitalisation: float) -> dict:
    """Z-score d'Altman (1968). Version d'origine pour les entreprises industrielles cotées,
    version Z'' (1995) pour les autres secteurs (services, technologie)."""
    b, cr = f["brut"]["bilan"], f["brut"]["cr"]
    an = f["annees"][-1]
    ta = _ligne(b, "Total Assets").get(an)
    tl = _ligne(b, "Total Liabilities Net Minority Interest").get(an)
    fr = (_ligne(b, "Current Assets") - _ligne(b, "Current Liabilities")).get(an)
    reserves = _ligne(b, "Retained Earnings").get(an)
    ebit = _ligne(cr, "EBIT", "Operating Income").get(an)
    ca = _ligne(cr, "Total Revenue").get(an)
    cp = _ligne(b, "Stockholders Equity").get(an)
    x1, x2, x3 = div(fr, ta), div(reserves, ta), div(ebit, ta)
    if f["secteur"] in SECTEURS_INDUSTRIELS:
        x4, x5 = div(capitalisation, tl), div(ca, ta)
        z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
        bornes, version = (1.81, 2.99), "Z (entreprises industrielles)"
        details = [("Fonds de roulement / actif", x1, 1.2), ("Réserves / actif", x2, 1.4),
                   ("EBIT / actif", x3, 3.3), ("Capitalisation / dettes", x4, 0.6), ("CA / actif", x5, 1.0)]
    else:
        x4 = div(cp, tl)
        z = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
        bornes, version = (1.1, 2.6), "Z'' (services et technologie)"
        details = [("Fonds de roulement / actif", x1, 6.56), ("Réserves / actif", x2, 3.26),
                   ("EBIT / actif", x3, 6.72), ("Capitaux propres / dettes", x4, 1.05)]
    if pd.isna(z):
        zone = "non calculable"
    elif z < bornes[0]:
        zone = "détresse"
    elif z < bornes[1]:
        zone = "zone grise"
    else:
        zone = "sécurité"
    return {"z": z, "zone": zone, "bornes": bornes, "version": version, "details": details}


def piotroski(f: dict) -> dict:
    """F-score de Piotroski (2000) : 9 tests notés 0 ou 1 entre les deux derniers exercices."""
    b, cr, fl = f["brut"]["bilan"], f["brut"]["cr"], f["brut"]["flux"]
    if len(f["annees"]) < 3:
        return {"score": np.nan, "tests": []}
    n, n1, n2 = f["annees"][-1], f["annees"][-2], f["annees"][-3]
    ta = _ligne(b, "Total Assets")
    rn = _ligne(cr, "Net Income")
    cfo = _ligne(fl, "Operating Cash Flow")
    dlt = _ligne(b, "Long Term Debt", "Long Term Debt And Capital Lease Obligation").fillna(0)
    ac, pc = _ligne(b, "Current Assets"), _ligne(b, "Current Liabilities")
    actions = _ligne(b, "Ordinary Shares Number", "Share Issued")
    ca = _ligne(cr, "Total Revenue")
    mb = _ligne(cr, "Gross Profit")

    roa = lambda a, prec: div(rn.get(a), ta.get(prec))
    rot = lambda a, prec: div(ca.get(a), ta.get(prec))
    tests = [
        ("Rentabilité", "Résultat net positif (ROA > 0)", roa(n, n1) > 0),
        ("Rentabilité", "Flux d'exploitation positif", cfo.get(n, np.nan) > 0),
        ("Rentabilité", "ROA en hausse", roa(n, n1) > roa(n1, n2)),
        ("Rentabilité", "Flux d'exploitation > résultat net (bénéfice de qualité)",
         cfo.get(n, np.nan) > rn.get(n, np.nan)),
        ("Structure", "Dette à long terme / actif en baisse",
         div(dlt.get(n), ta.get(n)) <= div(dlt.get(n1), ta.get(n1))),
        ("Structure", "Liquidité générale en hausse", div(ac.get(n), pc.get(n)) > div(ac.get(n1), pc.get(n1))),
        ("Structure", "Pas de nouvelles actions émises", actions.get(n, np.nan) <= actions.get(n1, np.nan) * 1.005),
        ("Efficacité", "Taux de marge brute en hausse", div(mb.get(n), ca.get(n)) > div(mb.get(n1), ca.get(n1))),
        ("Efficacité", "Rotation de l'actif en hausse", rot(n, n1) > rot(n1, n2)),
    ]
    tests = [(c, t, bool(ok) if not pd.isna(ok) else False) for c, t, ok in tests]
    return {"score": sum(ok for _, _, ok in tests), "tests": tests}


# ---------------------------------------------------------------------------
# Analyse complète
# ---------------------------------------------------------------------------
def analyser(f: dict, cours: float, beta: float) -> dict:
    """f : résultat de partie8.analyser. cours : dernier cours de bourse."""
    if not f.get("applicable"):
        return {"applicable": False, "raison": f.get("raison", "")}
    info = f["info"]
    devise_compta = info.get("financialCurrency") or f["devise"]
    devise_cours = info.get("currency") or devise_compta
    fx = taux_change(devise_compta, devise_cours)      # 1 unité de compta = fx unités de cotation

    b = f["brut"]["bilan"]
    an = f["annees"][-1]
    actions = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding") or \
        _ligne(b, "Ordinary Shares Number").get(an)
    capi = cours * actions if actions else info.get("marketCap", np.nan)
    capi_compta = capi / fx                            # capitalisation dans la devise des comptes

    so, sig, fl = f["solvabilite"], f["sig"], f["flux"]
    dfn = dernier(so["Dette financière nette (DFN)"])
    dettes = dernier(so["Dettes financières"])
    minoritaires = _ligne(b, "Minority Interest").fillna(0).get(an, 0)
    ve = capi_compta + dfn + (minoritaires if pd.notna(minoritaires) else 0)
    rn, ebe, ca = dernier(sig["Résultat net"]), dernier(sig["EBE (EBITDA)"]), dernier(sig["Chiffre d'affaires (CA)"])
    cp = dernier(so["Capitaux propres"])
    ftd_serie = fl["= Flux de trésorerie disponible (FTD)"].dropna()
    ftd = dernier(ftd_serie)

    multiples = {
        "Capitalisation boursière": capi_compta,
        "Valeur d'entreprise (VE = capitalisation + DFN)": ve,
        "PER (capitalisation / résultat net)": div(capi_compta, rn),
        "PER prévisionnel (consensus)": info.get("forwardPE", np.nan),
        "VE / EBE": div(ve, ebe),
        "VE / CA": div(ve, ca),
        "Cours / valeur comptable (P/B)": div(capi_compta, cp),
        "Rendement du FCF (FTD / capitalisation)": div(ftd, capi_compta),
        "Rendement du dividende": f["rendement_div"],
    }

    # Coût du capital
    kcp = TAUX_SANS_RISQUE + beta * PRIME_RISQUE
    ff = dernier(sig["Frais financiers"])
    kd = div(ff, dettes)
    kd = float(np.clip(kd, 0.02, 0.12)) if pd.notna(kd) else 0.04
    poids_cp = div(capi_compta, capi_compta + max(dettes, 0)) if pd.notna(dettes) else 1.0
    cmpc = poids_cp * kcp + (1 - poids_cp) * kd * (1 - TAUX_IS)
    cmpc = max(cmpc, CROISSANCE_PERPETUELLE + 0.03)    # garde-fou : le CMPC doit dépasser g

    # DCF : flux de départ = moyenne des 3 derniers FTD (lisse les années exceptionnelles)
    fcf0 = ftd_serie.iloc[-3:].mean() if len(ftd_serie) else np.nan
    g = float(np.clip(f["tcam_ca"], 0.0, 0.12)) if pd.notna(f["tcam_ca"]) else 0.03
    base = dcf(fcf0, g, CROISSANCE_PERPETUELLE, cmpc, dfn, actions) if pd.notna(fcf0) and fcf0 > 0 else None
    valeur_action = base["valeur_action"] * fx if base else np.nan

    # Sensibilité : CMPC ± 1 point, croissance perpétuelle de 1 % à 3 %
    sens = None
    if base:
        lignes_cmpc = [cmpc - 0.01, cmpc - 0.005, cmpc, cmpc + 0.005, cmpc + 0.01]
        colonnes_g = [0.01, 0.015, 0.02, 0.025, 0.03]
        sens = pd.DataFrame(
            [[dcf(fcf0, g, gi, w, dfn, actions)["valeur_action"] * fx for gi in colonnes_g] for w in lignes_cmpc],
            index=[f"{w:.1%}" for w in lignes_cmpc], columns=[f"{gi:.1%}" for gi in colonnes_g])

    consensus = {
        "Objectif de cours moyen": info.get("targetMeanPrice"),
        "Objectif bas": info.get("targetLowPrice"),
        "Objectif haut": info.get("targetHighPrice"),
        "Nombre d'analystes": info.get("numberOfAnalystOpinions"),
        "Recommandation": info.get("recommendationKey"),
    }

    return {
        "applicable": True, "cours": cours, "devise_cours": devise_cours, "devise_compta": devise_compta,
        "fx": fx, "actions": actions, "multiples": multiples,
        "kcp": kcp, "kd": kd, "poids_cp": poids_cp, "cmpc": cmpc, "beta": beta,
        "fcf0": fcf0, "g": g, "g_inf": CROISSANCE_PERPETUELLE, "dfn": dfn,
        "dcf": base, "valeur_action": valeur_action,
        "potentiel": div(valeur_action, cours) - 1 if pd.notna(valeur_action) else np.nan,
        "sensibilite": sens, "consensus": consensus,
        "altman": altman(f, capi_compta), "piotroski": piotroski(f),
    }


# ---------------------------------------------------------------------------
# Graphique : composition de la valeur DCF et comparaison des valeurs
# ---------------------------------------------------------------------------
def graphique(v: dict, ticker: str, fichier: str) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))
    d = v["dcf"]
    if d:
        noms = [f"An {t}" for t in range(1, HORIZON + 1)] + ["Valeur\nterminale"]
        vals = [x / 1e9 for x in d["flux_actualises"]] + [d["vt_actualisee"] / 1e9]
        couleurs = ["#6EA8FF"] * HORIZON + ["#6B7FA8"]
        ax1.bar(noms, vals, color=couleurs)
        ax1.set_ylabel(f"Md {v['devise_compta']} (actualisés)")
        ax1.set_title(f"D'où vient la valeur DCF ? (valeur terminale = {d['part_vt']:.0%})")
        ax1.grid(alpha=0.3, axis="y")
    else:
        ax1.text(0.5, 0.5, "DCF non calculable\n(flux de trésorerie négatifs)", ha="center", va="center")
        ax1.axis("off")

    c = v["consensus"]
    barres = [("Cours actuel", v["cours"], "#ECE8DF"), ("Valeur DCF", v["valeur_action"], "#6EA8FF"),
              ("Objectif bas analystes", c["Objectif bas"], "#2A3A5C"),
              ("Objectif moyen analystes", c["Objectif de cours moyen"], "#6EA8FF"),
              ("Objectif haut analystes", c["Objectif haut"], "#2A3A5C")]
    barres = [(n, x, col) for n, x, col in barres if x is not None and pd.notna(x)]
    ax2.barh([n for n, _, _ in barres], [x for _, x, _ in barres], color=[col for _, _, col in barres])
    ax2.axvline(v["cours"], color="#ECE8DF", ls="--", lw=0.8)
    for i, (_, x, _) in enumerate(barres):
        ax2.text(x, i, f" {x:,.2f}".replace(",", " "), va="center", fontsize=9)
    ax2.invert_yaxis()
    ax2.set_title(f"Cours actuel vs estimations de valeur ({v['devise_cours']})")
    ax2.grid(alpha=0.3, axis="x")
    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    ticker = sys.argv[1].upper() if len(sys.argv) > 1 else "MC.PA"
    import partie1_donnees as p1
    cours = p1.telecharger_prix(ticker, "1y").iloc[-1]
    f = p8.analyser(ticker, beta=1.0, cours=cours)
    v = analyser(f, cours, beta=1.0)
    if not v["applicable"]:
        sys.exit(v["raison"])
    print(f"\n=== Partie 9 : valorisation de {ticker} (cours {cours:.2f} {v['devise_cours']}) ===\n")
    for k, x in v["multiples"].items():
        print(f"  {k:<45}: {x:,.2f}")
    print(f"\n  CMPC {v['cmpc']:.2%} (kcp {v['kcp']:.2%}, kd {v['kd']:.2%}, poids CP {v['poids_cp']:.0%})")
    print(f"  FCF0 {v['fcf0'] / 1e6:,.0f} M, g {v['g']:.1%}, g∞ {v['g_inf']:.1%}")
    print(f"  Valeur DCF par action : {v['valeur_action']:.2f}  (potentiel {v['potentiel']:+.1%})")
    print(v["sensibilite"].round(1) if v["sensibilite"] is not None else "")
    print("\n  Consensus :", v["consensus"])
    a = v["altman"]
    print(f"\n  Altman {a['version']} : {a['z']:.2f} -> {a['zone']}")
    p = v["piotroski"]
    print(f"  Piotroski : {p['score']}/9")
    for c, t, ok in p["tests"]:
        print(f"     [{'x' if ok else ' '}] {c} — {t}")
    graphique(v, ticker, f"{ticker}_p9.png")
