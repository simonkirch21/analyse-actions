"""
PARTIE 2 — Performance et risque d'une action
=============================================

Indicateurs calculés :
  - rendement annualisé (CAGR)
  - volatilité annualisée
  - ratio de Sharpe et ratio de Sortino
  - perte maximale (max drawdown) et ratio de Calmar
  - rendements par année civile

Lancer :  .venv/bin/python partie2_performance.py AAPL
          .venv/bin/python partie2_performance.py AAPL MC.PA TTE.PA   (comparaison)
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# On réutilise les fonctions de la partie 1 (R : source("partie1.R"))
from partie1_donnees import telecharger_prix, calculer_rendements

JOURS_PAR_AN = 252     # nombre moyen de séances de bourse dans une année
TAUX_SANS_RISQUE = 0.03  # 3 % par an, hypothèse (à adapter : taux €STR, T-bill...)


# ---------------------------------------------------------------------------
# 1. Rendement et volatilité
# ---------------------------------------------------------------------------
def rendement_annualise(prix: pd.Series) -> float:
    """CAGR : taux de croissance annuel composé.

    CAGR = (P_fin / P_début) ^ (1 / nb_années) - 1
    C'est le taux constant qui, chaque année, mènerait du 1er au dernier prix.
    """
    nb_annees = (prix.index[-1] - prix.index[0]).days / 365.25
    return (prix.iloc[-1] / prix.iloc[0]) ** (1 / nb_annees) - 1   # ** = puissance (R : ^)


def volatilite_annualisee(rendements: pd.Series) -> float:
    """Écart-type des rendements journaliers × √252.

    Pourquoi √252 ? Si les rendements sont indépendants, les variances
    s'additionnent : Var_an = 252 × Var_jour, donc σ_an = σ_jour × √252.
    """
    return rendements.std() * np.sqrt(JOURS_PAR_AN)   # R : sd(r) * sqrt(252)


# ---------------------------------------------------------------------------
# 2. Ratios rendement / risque
# ---------------------------------------------------------------------------
def ratio_sharpe(rendements: pd.Series, rf: float = TAUX_SANS_RISQUE) -> float:
    """Sharpe = (rendement moyen - taux sans risque) / volatilité, le tout annualisé.

    Lecture : combien de rendement "en plus" je gagne par unité de risque.
    > 1 : très bon ; 0,5-1 : correct ; < 0 : pire que le placement sans risque.
    """
    rf_jour = (1 + rf) ** (1 / JOURS_PAR_AN) - 1
    exces = rendements - rf_jour
    return exces.mean() / exces.std() * np.sqrt(JOURS_PAR_AN)


def ratio_sortino(rendements: pd.Series, rf: float = TAUX_SANS_RISQUE) -> float:
    """Comme Sharpe, mais ne pénalise que la volatilité "à la baisse".

    Un investisseur ne se plaint pas des fortes hausses : on ne garde
    donc que les rendements négatifs pour mesurer le risque.
    """
    rf_jour = (1 + rf) ** (1 / JOURS_PAR_AN) - 1
    exces = rendements - rf_jour
    baisse = np.minimum(exces, 0)                         # R : pmin(exces, 0)
    ecart_baisse = np.sqrt((baisse ** 2).mean())
    return exces.mean() / ecart_baisse * np.sqrt(JOURS_PAR_AN)


# ---------------------------------------------------------------------------
# 3. Drawdown (perte depuis le plus haut)
# ---------------------------------------------------------------------------
def serie_drawdown(prix: pd.Series) -> pd.Series:
    """À chaque date : de combien le prix est sous son plus haut historique."""
    plus_haut = prix.cummax()            # maximum cumulé (R : cummax(prix))
    return prix / plus_haut - 1          # 0 au sommet, négatif ensuite


def max_drawdown(prix: pd.Series) -> dict:
    """Pire perte entre un sommet et le creux qui suit."""
    dd = serie_drawdown(prix)
    date_creux = dd.idxmin()                         # date du pire point (R : which.min)
    date_sommet = prix.loc[:date_creux].idxmax()     # sommet atteint AVANT le creux
    # Récupération : 1re date après le creux où le prix repasse le sommet
    apres = prix.loc[date_creux:]
    recup = apres[apres >= prix.loc[date_sommet]]
    date_recup = recup.index[0] if len(recup) > 0 else None
    return {
        "max_drawdown": dd.min(),
        "sommet": date_sommet,
        "creux": date_creux,
        "recuperation": date_recup,
    }


# ---------------------------------------------------------------------------
# 4. Rendements par année
# ---------------------------------------------------------------------------
def rendements_annuels(prix: pd.Series) -> pd.Series:
    """Performance de chaque année civile (dernier prix de l'année / précédent - 1).

    La 1re et la dernière année peuvent être partielles.
    """
    fin_annee = prix.groupby(prix.index.year).last()   # R : aggregate(..., by=year, last)
    debut = prix.iloc[0]
    precedent = fin_annee.shift(1).fillna(debut)
    return fin_annee / precedent - 1


# ---------------------------------------------------------------------------
# 5. Tableau récapitulatif
# ---------------------------------------------------------------------------
def analyse_performance(prix: pd.Series, rf: float = TAUX_SANS_RISQUE) -> dict:
    """Calcule tous les indicateurs et les renvoie dans un dictionnaire."""
    r = calculer_rendements(prix)["simple"]
    cagr = rendement_annualise(prix)
    mdd = max_drawdown(prix)
    return {
        "Rendement annualisé": cagr,
        "Volatilité annualisée": volatilite_annualisee(r),
        "Sharpe": ratio_sharpe(r, rf),
        "Sortino": ratio_sortino(r, rf),
        "Max drawdown": mdd["max_drawdown"],
        "Calmar": cagr / abs(mdd["max_drawdown"]),   # rendement / pire perte
        "Meilleur jour": r.max(),
        "Pire jour": r.min(),
        "% jours positifs": (r > 0).mean(),          # moyenne de TRUE/FALSE = proportion
        "_drawdown": mdd,                            # détail (dates), usage interne
    }


def afficher(ticker: str, res: dict) -> None:
    pourcent = {"Rendement annualisé", "Volatilité annualisée", "Max drawdown",
                "Meilleur jour", "Pire jour", "% jours positifs"}
    print(f"\n--- {ticker} ---")
    for nom, val in res.items():
        if nom.startswith("_"):
            continue
        texte = f"{val:.1%}" if nom in pourcent else f"{val:.2f}"
        print(f"{nom:<24}: {texte:>8}")
    d = res["_drawdown"]
    recup = d["recuperation"].date() if d["recuperation"] is not None else "pas encore"
    print(f"{'  sommet -> creux':<24}: {d['sommet'].date()} -> {d['creux'].date()}")
    print(f"{'  récupération':<24}: {recup}")


def graphique(tous_les_prix: dict, fichier: str) -> None:
    """Base 100, drawdown et volatilité glissante pour chaque action."""
    fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True)
    for ticker, prix in tous_les_prix.items():
        r = prix.pct_change()
        axes[0].plot(prix / prix.iloc[0] * 100, label=ticker)
        axes[1].plot(serie_drawdown(prix) * 100, label=ticker)
        # Volatilité sur 3 mois glissants (63 séances), annualisée
        axes[2].plot(r.rolling(63).std() * np.sqrt(JOURS_PAR_AN) * 100, label=ticker)

    axes[0].set_title("Évolution base 100")
    axes[1].set_title("Drawdown (% sous le plus haut)")
    axes[2].set_title("Volatilité annualisée glissante sur 3 mois (%)")
    for ax in axes:
        ax.grid(alpha=0.3)
        ax.legend()
    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    tickers = [t.upper() for t in sys.argv[1:]] or ["AAPL"]
    print(f"\n=== Partie 2 : performance (taux sans risque = {TAUX_SANS_RISQUE:.0%}) ===")

    tous_les_prix = {}
    tableau = {}
    for t in tickers:
        prix = telecharger_prix(t)
        tous_les_prix[t] = prix
        res = analyse_performance(prix)
        afficher(t, res)
        tableau[t] = rendements_annuels(prix)

    print("\nRendements par année civile :")
    # DataFrame : une colonne par action (R : cbind / data.frame)
    print((pd.DataFrame(tableau) * 100).round(1).astype(str).add(" %").to_string())

    nom = "_".join(tickers)
    graphique(tous_les_prix, f"{nom}_partie2.png")
    print(f"\nGraphique créé : {nom}_partie2.png\n")
