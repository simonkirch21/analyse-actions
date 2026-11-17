"""
PARTIE 5 — Analyse technique et backtest de stratégies
======================================================

Indicateurs :
  - Moyennes mobiles 50 et 200 jours (tendance)
  - RSI 14 jours (surachat / survente)
  - Bandes de Bollinger 20 jours (volatilité autour de la moyenne)
  - MACD (momentum)

Backtest : on teste trois stratégies sur l'historique et on les compare
au simple "acheter et conserver" (buy & hold), frais de transaction inclus.

Règle d'or du backtest : un signal calculé avec le prix de clôture du jour J
ne peut être exécuté qu'au jour J+1 -> .shift(1). Sinon on "triche"
en utilisant une information qu'on n'avait pas encore (biais d'anticipation).

Lancer :  .venv/bin/python partie5_technique.py AAPL
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from partie1_donnees import telecharger_prix
from partie2_performance import (rendement_annualise, volatilite_annualisee,
                                 ratio_sharpe, max_drawdown, TAUX_SANS_RISQUE)

FRAIS = 0.001   # 0,1 % du montant à chaque achat ou vente


# ---------------------------------------------------------------------------
# 1. Indicateurs techniques
# ---------------------------------------------------------------------------
def rsi(prix: pd.Series, n: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder) : entre 0 et 100.
    > 70 : surachat (l'action a beaucoup monté) ; < 30 : survente."""
    variation = prix.diff()
    hausse = variation.clip(lower=0)            # R : pmax(variation, 0)
    baisse = -variation.clip(upper=0)
    # Moyenne exponentielle de Wilder (alpha = 1/n)
    moy_h = hausse.ewm(alpha=1 / n, adjust=False).mean()
    moy_b = baisse.ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + moy_h / moy_b)


def indicateurs(prix: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"prix": prix})
    df["MM50"] = prix.rolling(50).mean()          # R : TTR::SMA(prix, 50)
    df["MM200"] = prix.rolling(200).mean()
    df["RSI"] = rsi(prix)
    moy20, ec20 = prix.rolling(20).mean(), prix.rolling(20).std()
    df["Bollinger_haut"] = moy20 + 2 * ec20
    df["Bollinger_bas"] = moy20 - 2 * ec20
    ema12 = prix.ewm(span=12, adjust=False).mean()
    ema26 = prix.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    return df


def signaux_actuels(df: pd.DataFrame) -> dict:
    """Lecture des indicateurs à la dernière date."""
    d = df.iloc[-1]
    out = {}
    out["Tendance (MM50 vs MM200)"] = ("HAUSSIÈRE (golden cross)" if d["MM50"] > d["MM200"]
                                       else "BAISSIÈRE (death cross)")
    out["Prix vs MM200"] = f"{d['prix'] / d['MM200'] - 1:+.1%}"
    if d["RSI"] > 70:
        out["RSI 14"] = f"{d['RSI']:.0f} -> surachat"
    elif d["RSI"] < 30:
        out["RSI 14"] = f"{d['RSI']:.0f} -> survente"
    else:
        out["RSI 14"] = f"{d['RSI']:.0f} -> neutre"
    position = (d["prix"] - d["Bollinger_bas"]) / (d["Bollinger_haut"] - d["Bollinger_bas"])
    out["Position Bollinger"] = f"{position:.0%} (0 % = bande basse, 100 % = bande haute)"
    out["MACD"] = "positif (momentum haussier)" if d["MACD"] > d["MACD_signal"] else \
                  "négatif (momentum baissier)"
    return out


# ---------------------------------------------------------------------------
# 2. Stratégies : chacune renvoie une "position" par jour (1 = investi, 0 = cash)
# ---------------------------------------------------------------------------
def strat_croisement_mm(df: pd.DataFrame) -> pd.Series:
    """Investi quand MM50 > MM200 (tendance de fond haussière)."""
    return (df["MM50"] > df["MM200"]).astype(int)


def strat_rsi(df: pd.DataFrame) -> pd.Series:
    """Retour à la moyenne : on achète en survente (RSI < 30),
    on revend quand le RSI repasse au-dessus de 50."""
    position = pd.Series(np.nan, index=df.index)
    position[df["RSI"] < 30] = 1
    position[df["RSI"] > 50] = 0
    return position.ffill().fillna(0)   # on garde la position jusqu'au prochain signal


def strat_momentum(df: pd.DataFrame) -> pd.Series:
    """Investi si le prix est plus haut qu'il y a 6 mois (126 séances)."""
    return (df["prix"] > df["prix"].shift(126)).astype(int)


STRATEGIES = {
    "Croisement MM50/MM200": strat_croisement_mm,
    "RSI (retour à la moyenne)": strat_rsi,
    "Momentum 6 mois": strat_momentum,
}


def backtest(df: pd.DataFrame, position: pd.Series) -> pd.Series:
    """Valeur d'un portefeuille de 1 € qui suit la position (frais inclus).
    Hors marché, l'argent est placé au taux sans risque."""
    r = df["prix"].pct_change().fillna(0)
    rf_jour = (1 + TAUX_SANS_RISQUE) ** (1 / 252) - 1
    pos = position.shift(1).fillna(0)              # exécution le lendemain
    changements = pos.diff().abs().fillna(0)       # 1 à chaque achat ou vente
    r_strat = pos * r + (1 - pos) * rf_jour - changements * FRAIS
    return (1 + r_strat).cumprod()


def comparer(df: pd.DataFrame) -> tuple:
    """Backteste toutes les stratégies + buy & hold à partir de la date où
    tous les indicateurs existent (après 200 séances)."""
    debut = df["MM200"].first_valid_index()
    d = df.loc[debut:]
    courbes = {"Buy & hold": d["prix"] / d["prix"].iloc[0]}
    for nom, f in STRATEGIES.items():
        courbes[nom] = backtest(d, f(d))
    resultats = {}
    for nom, valeur in courbes.items():
        r = valeur.pct_change().dropna()
        resultats[nom] = {
            "Rendement annualisé": rendement_annualise(valeur),
            "Volatilité": volatilite_annualisee(r),
            "Sharpe": ratio_sharpe(r),
            "Max drawdown": max_drawdown(valeur)["max_drawdown"],
            "Temps investi": 1.0 if nom == "Buy & hold"
                             else STRATEGIES[nom](d).mean(),
            "Nb transactions": 1 if nom == "Buy & hold"
                               else int(STRATEGIES[nom](d).diff().abs().sum()),
        }
    return pd.DataFrame(resultats).T, pd.DataFrame(courbes)


def graphique(df: pd.DataFrame, courbes: pd.DataFrame, ticker: str, fichier: str) -> None:
    d = df.iloc[-500:]   # 2 dernières années pour la lisibilité
    fig, axes = plt.subplots(4, 1, figsize=(11, 12),
                             gridspec_kw={"height_ratios": [3, 1, 1, 2.5]})

    ax = axes[0]
    ax.plot(d["prix"], color="#ECE8DF", lw=1, label="Prix")
    ax.plot(d["MM50"], color="#6EA8FF", lw=1, label="MM50")
    ax.plot(d["MM200"], color="#FF6B5A", lw=1, label="MM200")
    ax.fill_between(d.index, d["Bollinger_bas"], d["Bollinger_haut"],
                    color="#8D94A5", alpha=0.15, label="Bollinger (20, 2σ)")
    ax.set_title(f"{ticker} — analyse technique (2 dernières années)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    axes[1].plot(d["RSI"], color="#B48CFF", lw=1)
    axes[1].axhline(70, color="#FF6B5A", ls="--", lw=0.7)
    axes[1].axhline(30, color="#3BC48F", ls="--", lw=0.7)
    axes[1].set_ylim(0, 100)
    axes[1].set_title("RSI 14")
    axes[1].grid(alpha=0.3)

    axes[2].plot(d["MACD"], label="MACD", lw=1)
    axes[2].plot(d["MACD_signal"], label="Signal", lw=1)
    axes[2].bar(d.index, d["MACD"] - d["MACD_signal"], color="#8D94A5", alpha=0.4)
    axes[2].set_title("MACD (12, 26, 9)")
    axes[2].legend(fontsize=8)
    axes[2].grid(alpha=0.3)

    for nom in courbes.columns:
        axes[3].plot(courbes[nom] * 100, label=nom,
                     lw=2 if nom == "Buy & hold" else 1,
                     color="#ECE8DF" if nom == "Buy & hold" else None)
    axes[3].set_title(f"Backtest des stratégies (base 100, frais {FRAIS:.1%} par transaction)")
    axes[3].legend(fontsize=8)
    axes[3].grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    ticker = sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL"
    print(f"\n=== Partie 5 : analyse technique de {ticker} ===\n")

    df = indicateurs(telecharger_prix(ticker))

    print(f"Signaux au {df.index[-1].date()} :")
    for nom, val in signaux_actuels(df).items():
        print(f"  {nom:<26}: {val}")

    tab, courbes = comparer(df)
    print(f"\nBacktest du {courbes.index[0].date()} au {courbes.index[-1].date()} :")
    affichage = tab.copy()
    for col in ["Rendement annualisé", "Volatilité", "Max drawdown", "Temps investi"]:
        affichage[col] = affichage[col].map("{:.1%}".format)
    affichage["Sharpe"] = affichage["Sharpe"].map("{:.2f}".format)
    affichage["Nb transactions"] = affichage["Nb transactions"].astype(int)
    print(affichage.to_string())

    fichier = f"{ticker}_partie5.png"
    graphique(df, courbes, ticker, fichier)
    print(f"\nGraphique créé : {fichier}\n")
