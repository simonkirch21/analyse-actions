"""
PARTIE 3 — Comparer l'action à son marché (CAPM)
================================================

Modèle CAPM (MEDAF en français) :

    R_action - Rf  =  α  +  β × (R_marché - Rf)  +  ε

  - β (bêta)  : sensibilité au marché. β = 1,5 => quand le marché fait +1 %,
                l'action fait en moyenne +1,5 %.
  - α (alpha) : rendement que le marché n'explique pas (la "surperformance").
  - R²        : part du risque de l'action expliquée par le marché
                (risque systématique) ; 1 - R² = risque spécifique,
                celui qu'on peut éliminer en diversifiant.

Lancer :  .venv/bin/python partie3_marche.py AAPL
          .venv/bin/python partie3_marche.py MC.PA ^STOXX50E   (indice choisi)
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats   # régression linéaire (R : lm)

from partie1_donnees import telecharger_prix
from partie2_performance import JOURS_PAR_AN, TAUX_SANS_RISQUE


def indice_par_defaut(ticker: str) -> str:
    """Choisit l'indice de référence d'après le suffixe de la place de cotation."""
    suffixes = {
        ".PA": "^FCHI",     # Paris      -> CAC 40
        ".DE": "^GDAXI",    # Francfort  -> DAX
        ".L": "^FTSE",      # Londres    -> FTSE 100
        ".AS": "^AEX",      # Amsterdam  -> AEX
        ".MI": "FTSEMIB.MI",# Milan      -> FTSE MIB
        ".SW": "^SSMI",     # Zurich     -> SMI
        ".T": "^N225",      # Tokyo      -> Nikkei 225
    }
    for suffixe, indice in suffixes.items():
        if ticker.endswith(suffixe):
            return indice
    return "^GSPC"          # par défaut : S&P 500 (actions américaines)


def aligner(prix_action: pd.Series, prix_indice: pd.Series) -> pd.DataFrame:
    """Rendements journaliers sur les SEULES dates communes aux deux séries.

    Indispensable : les jours fériés diffèrent selon les places (cf. partie 1).
    """
    df = pd.concat([prix_action, prix_indice], axis=1, join="inner")  # R : merge(..., all=FALSE)
    df.columns = ["action", "marche"]
    return df.pct_change().dropna()


def regression_capm(r: pd.DataFrame, rf: float = TAUX_SANS_RISQUE) -> dict:
    """Régression des rendements excédentaires de l'action sur ceux du marché."""
    rf_jour = (1 + rf) ** (1 / JOURS_PAR_AN) - 1
    y = r["action"] - rf_jour
    x = r["marche"] - rf_jour

    reg = stats.linregress(x, y)    # R : summary(lm(y ~ x))
    n = len(x)

    # Test de significativité de l'alpha : t = α / erreur-type, loi de Student
    t_alpha = reg.intercept / reg.intercept_stderr
    p_alpha = 2 * (1 - stats.t.cdf(abs(t_alpha), df=n - 2))

    return {
        "beta": reg.slope,
        "beta_ic95": (reg.slope - 1.96 * reg.stderr, reg.slope + 1.96 * reg.stderr),
        "alpha_jour": reg.intercept,
        "alpha_annuel": (1 + reg.intercept) ** JOURS_PAR_AN - 1,
        "t_alpha": t_alpha,
        "p_alpha": p_alpha,
        "r2": reg.rvalue ** 2,
        "correlation": reg.rvalue,
        "n": n,
    }


def autres_indicateurs(r: pd.DataFrame, beta: float, rf: float = TAUX_SANS_RISQUE) -> dict:
    """Indicateurs complémentaires de performance relative."""
    ecart = r["action"] - r["marche"]                     # rendement "actif"
    tracking_error = ecart.std() * np.sqrt(JOURS_PAR_AN)  # volatilité de l'écart

    rdt_action = (1 + r["action"]).prod() ** (JOURS_PAR_AN / len(r)) - 1
    rdt_marche = (1 + r["marche"]).prod() ** (JOURS_PAR_AN / len(r)) - 1

    # Captures : en moyenne, quelle part des hausses / baisses du marché l'action suit
    hausse = r["marche"] > 0
    capture_hausse = r.loc[hausse, "action"].mean() / r.loc[hausse, "marche"].mean()
    capture_baisse = r.loc[~hausse, "action"].mean() / r.loc[~hausse, "marche"].mean()

    return {
        "Rendement annualisé action": rdt_action,
        "Rendement annualisé marché": rdt_marche,
        "Tracking error": tracking_error,
        # Information ratio : surperformance par unité d'écart au marché
        "Information ratio": (rdt_action - rdt_marche) / tracking_error,
        # Treynor : comme Sharpe, mais le risque mesuré est le bêta (risque non diversifiable)
        "Treynor": (rdt_action - rf) / beta,
        "Capture hausse": capture_hausse,
        "Capture baisse": capture_baisse,
    }


def beta_glissant(r: pd.DataFrame, fenetre: int = JOURS_PAR_AN) -> pd.Series:
    """Bêta recalculé sur 1 an glissant : β = Cov(action, marché) / Var(marché)."""
    cov = r["action"].rolling(fenetre).cov(r["marche"])
    var = r["marche"].rolling(fenetre).var()
    return cov / var


def graphique(r: pd.DataFrame, capm: dict, ticker: str, indice: str, fichier: str) -> None:
    fig = plt.figure(figsize=(11, 9))
    grille = fig.add_gridspec(2, 2)

    # 1. Nuage de points + droite de régression
    ax1 = fig.add_subplot(grille[0, 0])
    ax1.scatter(r["marche"] * 100, r["action"] * 100, s=4, alpha=0.4)
    x = np.linspace(r["marche"].min(), r["marche"].max(), 50)
    ax1.plot(x * 100, (capm["alpha_jour"] + capm["beta"] * x) * 100, color="#FF6B5A",
             label=f"β = {capm['beta']:.2f}   R² = {capm['r2']:.2f}")
    ax1.axhline(0, color="#8D94A5", lw=0.5)
    ax1.axvline(0, color="#8D94A5", lw=0.5)
    ax1.set_xlabel(f"Rendement {indice} (%)")
    ax1.set_ylabel(f"Rendement {ticker} (%)")
    ax1.set_title("Droite caractéristique (CAPM)")
    ax1.legend()

    # 2. Décomposition du risque
    ax2 = fig.add_subplot(grille[0, 1])
    ax2.pie([capm["r2"], 1 - capm["r2"]],
            labels=["Systématique\n(marché)", "Spécifique\n(diversifiable)"],
            autopct="%1.0f%%", colors=["#6EA8FF", "#3A4560"])
    ax2.set_title("Décomposition de la variance")

    # 3. Base 100 action vs marché + bêta glissant
    ax3 = fig.add_subplot(grille[1, :])
    cumul = (1 + r).cumprod() * 100       # R : cumprod(1 + r) * 100
    ax3.plot(cumul["action"], label=ticker)
    ax3.plot(cumul["marche"], label=indice, color="#8D94A5")
    ax3.set_ylabel("Base 100")
    ax3.legend(loc="upper left")
    ax3.grid(alpha=0.3)
    ax3b = ax3.twinx()                    # 2e axe vertical à droite
    ax3b.plot(beta_glissant(r), color="#FF6B5A", lw=1, alpha=0.7, label="β glissant 1 an")
    ax3b.axhline(1, color="#FF6B5A", ls="--", lw=0.5)
    ax3b.set_ylabel("Bêta", color="#FF6B5A")
    ax3b.legend(loc="lower right")
    ax3.set_title(f"{ticker} vs {indice} et bêta glissant sur 1 an")

    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


def interpreter(capm: dict) -> list:
    """Quelques phrases de lecture automatique des résultats."""
    b, phrases = capm["beta"], []
    if b > 1.2:
        phrases.append(f"Action OFFENSIVE : elle amplifie les mouvements du marché (β = {b:.2f}).")
    elif b < 0.8:
        phrases.append(f"Action DÉFENSIVE : elle amortit les mouvements du marché (β = {b:.2f}).")
    else:
        phrases.append(f"Action NEUTRE : elle suit globalement le marché (β = {b:.2f}).")

    if capm["p_alpha"] < 0.05:
        signe = "positif" if capm["alpha_annuel"] > 0 else "négatif"
        phrases.append(f"Alpha {signe} et statistiquement significatif (p = {capm['p_alpha']:.3f}).")
    else:
        phrases.append(f"Alpha non significatif (p = {capm['p_alpha']:.2f}) : on ne peut pas "
                       "conclure à une sur- ou sous-performance réelle, au-delà du hasard.")

    phrases.append(f"{capm['r2']:.0%} du risque vient du marché, "
                   f"{1 - capm['r2']:.0%} est spécifique à l'entreprise.")
    return phrases


if __name__ == "__main__":
    ticker = sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL"
    indice = sys.argv[2].upper() if len(sys.argv) > 2 else indice_par_defaut(ticker)

    print(f"\n=== Partie 3 : {ticker} face à {indice} (Rf = {TAUX_SANS_RISQUE:.0%}) ===\n")

    r = aligner(telecharger_prix(ticker), telecharger_prix(indice))
    capm = regression_capm(r)
    autres = autres_indicateurs(r, capm["beta"])

    lo, hi = capm["beta_ic95"]
    print(f"Observations         : {capm['n']} jours communs")
    print(f"Bêta                 : {capm['beta']:.2f}   (IC 95 % : {lo:.2f} – {hi:.2f})")
    print(f"Alpha annualisé      : {capm['alpha_annuel']:.1%}   "
          f"(t = {capm['t_alpha']:.2f}, p = {capm['p_alpha']:.3f})")
    print(f"Corrélation          : {capm['correlation']:.2f}")
    print(f"R²                   : {capm['r2']:.2f}")
    print()
    pourcent = {"Rendement annualisé action", "Rendement annualisé marché", "Tracking error", "Treynor"}
    for nom, val in autres.items():
        print(f"{nom:<27}: {val:.1%}" if nom in pourcent else f"{nom:<27}: {val:.2f}")

    print("\nLecture :")
    for p in interpreter(capm):
        print(f"  • {p}")

    fichier = f"{ticker}_partie3.png"
    graphique(r, capm, ticker, indice, fichier)
    print(f"\nGraphique créé : {fichier}\n")
