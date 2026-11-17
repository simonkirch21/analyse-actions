"""
PARTIE 1 — Télécharger les données d'une action
================================================

Objectif : à partir d'un ticker (ex. "AAPL", "MC.PA", "TTE.PA"),
récupérer l'historique des prix et calculer les rendements.

Lancer :  .venv/bin/python partie1_donnees.py AAPL
"""

import sys                      # pour lire l'argument passé en ligne de commande
import numpy as np              # calcul numérique      (R : fonctions de base)
import pandas as pd             # tableaux de données   (R : data.frame / tibble)
import yfinance as yf           # données Yahoo Finance (R : quantmod::getSymbols)
import matplotlib.pyplot as plt # graphiques            (R : plot / ggplot2)

# Style commun à tous les graphiques : thème « salle des marchés », fond sombre identique aux cartes du site
from cycler import cycler
FOND_GRAPHIQUE = "#10182A"
plt.rcParams.update({
    "figure.facecolor": FOND_GRAPHIQUE, "axes.facecolor": FOND_GRAPHIQUE, "savefig.facecolor": FOND_GRAPHIQUE,
    "axes.prop_cycle": cycler(color=["#D4AF6A", "#6EA8FF", "#3BC48F", "#FF6B5A", "#B48CFF", "#F2A65A", "#4FD1C5"]),
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#2A3550",
    "text.color": "#ECE8DF", "axes.labelcolor": "#C9CDD6", "axes.titlecolor": "#ECE8DF",
    "xtick.color": "#8D94A5", "ytick.color": "#8D94A5", "axes.titleweight": "semibold", "axes.titlesize": 12,
    "grid.color": "#1E2940", "grid.alpha": 1.0, "legend.frameon": False, "legend.labelcolor": "#C9CDD6",
    "patch.edgecolor": FOND_GRAPHIQUE, "hatch.color": "#2A3550",
})


def telecharger_prix(ticker: str, periode: str = "5y") -> pd.Series:
    """Télécharge les prix de clôture ajustés (dividendes et splits inclus).

    periode : "1y", "2y", "5y", "10y", "max"...
    Renvoie une Series pandas : un vecteur de prix indexé par date
    (R : un objet xts).
    """
    # auto_adjust=True => la colonne "Close" est déjà ajustée
    donnees = yf.download(ticker, period=periode, auto_adjust=True, progress=False)

    if donnees.empty:
        raise ValueError(f"Aucune donnée trouvée pour '{ticker}'. Vérifie le ticker.")

    # yfinance renvoie des colonnes à deux niveaux (Prix, Ticker) : on garde "Close"
    prix = donnees["Close"].squeeze()   # squeeze() : tableau 1 colonne -> vecteur
    prix.name = ticker
    return prix.dropna()                # R : na.omit()


def infos_entreprise(ticker: str) -> dict:
    """Quelques informations descriptives (peuvent manquer selon l'action)."""
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        return {}
    # dict.get(cle) renvoie None si la clé n'existe pas (pas d'erreur)
    return {
        "Nom": info.get("longName"),
        "Secteur": info.get("sector"),
        "Pays": info.get("country"),
        "Devise": info.get("currency"),
        "Capitalisation": info.get("marketCap"),
        "PER": info.get("trailingPE"),
    }


def calculer_rendements(prix: pd.Series) -> pd.DataFrame:
    """Rendements journaliers simples et logarithmiques.

    simple : R_t = P_t / P_{t-1} - 1
    log    : r_t = ln(P_t / P_{t-1})   (additifs dans le temps, utiles en modélisation)
    """
    rendements = pd.DataFrame({
        "simple": prix.pct_change(),                 # R : prix / lag(prix) - 1
        "log": np.log(prix / prix.shift(1)),         # R : diff(log(prix))
    })
    return rendements.dropna()                       # la 1re ligne est NA


def graphique(prix: pd.Series, rendements: pd.DataFrame, fichier: str) -> None:
    """Deux graphiques : l'évolution du prix et les rendements journaliers."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    ax1.plot(prix.index, prix.values, color="#6EA8FF")
    ax1.set_title(f"{prix.name} — prix de clôture ajusté")
    ax1.set_ylabel("Prix")
    ax1.grid(alpha=0.3)

    ax2.plot(rendements.index, rendements["simple"] * 100, color="#8D94A5", lw=0.6)
    ax2.set_title("Rendements journaliers (%)")
    ax2.set_ylabel("%")
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Programme principal : ne s'exécute que si on lance CE fichier directement
# (pas quand on l'importe depuis une autre partie du projet).
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # sys.argv = liste des mots tapés après "python" ; sinon AAPL par défaut
    ticker = sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL"

    print(f"\n=== Partie 1 : données pour {ticker} ===\n")

    infos = infos_entreprise(ticker)
    for cle, valeur in infos.items():
        print(f"{cle:<15}: {valeur}")

    prix = telecharger_prix(ticker)
    rendements = calculer_rendements(prix)

    print(f"\nPériode       : {prix.index[0].date()} -> {prix.index[-1].date()}")
    print(f"Nb de séances : {len(prix)}")
    print(f"Premier prix  : {prix.iloc[0]:.2f}")    # iloc[0] = 1er élément (R : prix[1])
    print(f"Dernier prix  : {prix.iloc[-1]:.2f}")   # iloc[-1] = dernier (R : tail(prix, 1))
    print(f"Performance   : {(prix.iloc[-1] / prix.iloc[0] - 1):.1%}")

    print("\nAperçu des rendements (5 dernières lignes) :")
    print(rendements.tail().round(4))               # R : tail(rendements, 5)

    # Sauvegarde pour les parties suivantes
    prix.to_csv(f"{ticker}_prix.csv")               # R : write.csv()
    graphique(prix, rendements, f"{ticker}_partie1.png")
    print(f"\nFichiers créés : {ticker}_prix.csv, {ticker}_partie1.png\n")
