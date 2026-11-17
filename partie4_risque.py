"""
PARTIE 4 — Mesurer le risque de perte : VaR et CVaR
===================================================

VaR 95 % à 1 jour = perte qui n'est dépassée que 5 % des jours.
  "Dans 95 % des cas, je ne perdrai pas plus de X % demain."
CVaR 95 % (Expected Shortfall) = perte MOYENNE les 5 % de jours où la VaR est dépassée.
  "Et quand ça se passe mal, je perds en moyenne Y %."

Quatre méthodes de calcul :
  1. Historique   : on lit le quantile directement dans les rendements passés.
  2. Paramétrique : on suppose une loi normale (moyenne, écart-type).
  3. Cornish-Fisher : loi normale corrigée de l'asymétrie et des queues épaisses.
  4. Monte Carlo  : on simule des milliers de rendements avec une loi de Student.

Puis on vérifie la VaR (backtesting) avec le test de Kupiec.

Lancer :  .venv/bin/python partie4_risque.py AAPL
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

from partie1_donnees import telecharger_prix, calculer_rendements

NIVEAUX = [0.95, 0.99]
GRAINE = 42   # graine aléatoire : mêmes résultats à chaque lancement (R : set.seed(42))


# ---------------------------------------------------------------------------
# 1. Forme de la distribution des rendements
# ---------------------------------------------------------------------------
def statistiques_distribution(r: pd.Series) -> dict:
    """Les rendements suivent-ils une loi normale ? (Hypothèse de nombreux modèles.)"""
    jb = stats.jarque_bera(r)
    return {
        "Moyenne journalière": r.mean(),
        "Écart-type journalier": r.std(),
        # Asymétrie : < 0 => les fortes baisses sont plus fréquentes que les fortes hausses
        "Asymétrie (skewness)": stats.skew(r),
        # Excès de kurtosis : > 0 => queues épaisses (événements extrêmes plus fréquents
        # que ne le prévoit la loi normale). Normale = 0.
        "Excès de kurtosis": stats.kurtosis(r),
        "Jarque-Bera (stat)": jb.statistic,
        "Jarque-Bera (p-value)": jb.pvalue,
    }


# ---------------------------------------------------------------------------
# 2. Les quatre méthodes de VaR / CVaR
#    Convention : on renvoie des PERTES positives (ex. 0.025 = perte de 2,5 %)
# ---------------------------------------------------------------------------
def var_historique(r: pd.Series, niveau: float) -> tuple:
    seuil = r.quantile(1 - niveau)                  # R : quantile(r, 0.05)
    cvar = r[r <= seuil].mean()
    return -seuil, -cvar


def var_parametrique(r: pd.Series, niveau: float) -> tuple:
    mu, sigma = r.mean(), r.std()
    z = stats.norm.ppf(1 - niveau)                  # R : qnorm(0.05) = -1.645
    var = -(mu + z * sigma)
    # CVaR d'une loi normale : formule fermée
    cvar = -(mu - sigma * stats.norm.pdf(z) / (1 - niveau))
    return var, cvar


def var_cornish_fisher(r: pd.Series, niveau: float) -> tuple:
    """Ajuste le quantile normal avec l'asymétrie S et l'excès de kurtosis K.

    Attention : c'est un développement limité. Quand la kurtosis est très forte
    (> 5 environ), il devient peu fiable dans les queues extrêmes (99 %) et
    surestime souvent le risque.
    """
    mu, sigma = r.mean(), r.std()
    S, K = stats.skew(r), stats.kurtosis(r)
    z = stats.norm.ppf(1 - niveau)
    z_cf = (z + (z**2 - 1) * S / 6 + (z**3 - 3 * z) * K / 24
            - (2 * z**3 - 5 * z) * S**2 / 36)
    var = -(mu + z_cf * sigma)
    # Pas de formule simple pour la CVaR : on l'approche par la moyenne
    # des quantiles CF au-delà du seuil
    alphas = np.linspace(1e-4, 1 - niveau, 200)
    zs = stats.norm.ppf(alphas)
    zs_cf = (zs + (zs**2 - 1) * S / 6 + (zs**3 - 3 * zs) * K / 24
             - (2 * zs**3 - 5 * zs) * S**2 / 36)
    cvar = -(mu + zs_cf * sigma).mean()
    return var, cvar


def var_monte_carlo(r: pd.Series, niveau: float, n: int = 100_000) -> tuple:
    """Simule n rendements avec une loi de Student ajustée aux données.

    La loi de Student a des queues plus épaisses que la normale :
    elle reproduit mieux les krachs.
    """
    ddl, loc, echelle = stats.t.fit(r)              # estimation par maximum de vraisemblance
    rng = np.random.default_rng(GRAINE)
    simul = stats.t.rvs(ddl, loc, echelle, size=n, random_state=rng)
    seuil = np.quantile(simul, 1 - niveau)
    return -seuil, -simul[simul <= seuil].mean()


METHODES = {
    "Historique": var_historique,
    "Paramétrique (normale)": var_parametrique,
    "Cornish-Fisher": var_cornish_fisher,
    "Monte Carlo (Student)": var_monte_carlo,
}


def tableau_var(r: pd.Series) -> pd.DataFrame:
    """Tableau : une ligne par méthode, VaR et CVaR à 95 % et 99 %."""
    lignes = {}
    for nom, fonction in METHODES.items():
        ligne = {}
        for niv in NIVEAUX:
            var, cvar = fonction(r, niv)
            ligne[f"VaR {niv:.0%}"] = var
            ligne[f"CVaR {niv:.0%}"] = cvar
        lignes[nom] = ligne
    return pd.DataFrame(lignes).T     # .T = transposée (R : t())


# ---------------------------------------------------------------------------
# 3. Backtesting : la VaR prévue a-t-elle été dépassée aussi souvent que prévu ?
# ---------------------------------------------------------------------------
def backtest_var(r: pd.Series, niveau: float = 0.95, fenetre: int = 252) -> dict:
    """Chaque jour, VaR historique calculée sur l'année PRÉCÉDENTE,
    puis on compte les jours où la perte réelle l'a dépassée."""
    var_prevue = -r.rolling(fenetre).quantile(1 - niveau).shift(1)  # shift : pas de triche
    df = pd.DataFrame({"r": r, "var": var_prevue}).dropna()
    exceptions = df["r"] < -df["var"]

    n, x = len(df), int(exceptions.sum())
    p = 1 - niveau
    taux = x / n

    # Test de Kupiec (POF) : rapport de vraisemblance, suit un chi² à 1 ddl
    if 0 < x < n:
        lr = -2 * (np.log((1 - p) ** (n - x) * p ** x)
                   - np.log((1 - taux) ** (n - x) * taux ** x))
    else:
        lr = np.nan
    p_value = 1 - stats.chi2.cdf(lr, df=1)

    return {
        "jours testés": n,
        "exceptions": x,
        "attendues": n * p,
        "taux observé": taux,
        "LR Kupiec": lr,
        "p-value": p_value,
        "valide": p_value > 0.05,
        "p-value indépendance": test_christoffersen(exceptions.values),
        "_serie": df.assign(exception=exceptions),
    }


def test_christoffersen(exc: np.ndarray) -> float:
    """Test d'indépendance de Christoffersen.

    Kupiec vérifie le NOMBRE d'exceptions, pas leur répartition dans le temps.
    Si les exceptions arrivent en grappes (krach : plusieurs jours de suite),
    la VaR réagit trop lentement. On compare :
      π01 = P(exception aujourd'hui | pas d'exception hier)
      π11 = P(exception aujourd'hui | exception hier)
    Sous H0 (indépendance), π01 = π11.
    """
    e = exc.astype(int)
    hier, auj = e[:-1], e[1:]
    n00 = np.sum((hier == 0) & (auj == 0))
    n01 = np.sum((hier == 0) & (auj == 1))
    n10 = np.sum((hier == 1) & (auj == 0))
    n11 = np.sum((hier == 1) & (auj == 1))
    if min(n00 + n01, n10 + n11) == 0 or n11 == 0:
        return np.nan
    pi01, pi11 = n01 / (n00 + n01), n11 / (n10 + n11)
    pi = (n01 + n11) / (n00 + n01 + n10 + n11)
    log_h0 = (n00 + n10) * np.log(1 - pi) + (n01 + n11) * np.log(pi)
    log_h1 = (n00 * np.log(1 - pi01) + n01 * np.log(pi01)
              + n10 * np.log(1 - pi11) + n11 * np.log(pi11))
    lr = -2 * (log_h0 - log_h1)
    return 1 - stats.chi2.cdf(lr, df=1)


def var_horizon(var_1j: float, jours: int) -> float:
    """Règle de la racine du temps (Bâle) : VaR_h = VaR_1j × √h.
    Approximation qui suppose des rendements indépendants."""
    return var_1j * np.sqrt(jours)


def graphique(r: pd.Series, tab: pd.DataFrame, bt: dict, ticker: str, fichier: str) -> None:
    fig = plt.figure(figsize=(11, 9))
    g = fig.add_gridspec(2, 2)

    # 1. Histogramme vs loi normale + VaR
    ax1 = fig.add_subplot(g[0, 0])
    ax1.hist(r * 100, bins=80, density=True, alpha=0.6, color="#6EA8FF", label="Observé")
    x = np.linspace(r.min(), r.max(), 300)
    ax1.plot(x * 100, stats.norm.pdf(x, r.mean(), r.std()) / 100, "--", color="#ECE8DF", label="Loi normale")
    couleurs = {"VaR 95%": "#F2A65A", "VaR 99%": "#FF6B5A"}
    for col, c in couleurs.items():
        v = tab.loc["Historique", col]
        ax1.axvline(-v * 100, color=c, label=f"{col} hist. = {v:.1%}")
    ax1.set_title("Distribution des rendements journaliers")
    ax1.set_xlabel("%")
    ax1.legend(fontsize=8)

    # 2. QQ-plot : si les points s'écartent de la droite aux extrémités => queues épaisses
    ax2 = fig.add_subplot(g[0, 1])
    stats.probplot(r, dist="norm", plot=ax2)        # R : qqnorm(r); qqline(r)
    ax2.set_title("QQ-plot vs loi normale")
    ax2.get_lines()[0].set_markersize(2)
    ax2.get_lines()[0].set_color("#6EA8FF")
    ax2.get_lines()[1].set_color("#FF6B5A")

    # 3. Backtest : rendements et VaR prévue, exceptions en rouge
    ax3 = fig.add_subplot(g[1, :])
    s = bt["_serie"]
    ax3.plot(s.index, s["r"] * 100, color="#8D94A5", lw=0.5, label="Rendement")
    ax3.plot(s.index, -s["var"] * 100, color="#F2A65A", label="−VaR 95 % (1 an glissant)")
    exc = s[s["exception"]]
    ax3.scatter(exc.index, exc["r"] * 100, color="#FF6B5A", s=10,
                label=f"Exceptions : {bt['exceptions']} (attendu ≈ {bt['attendues']:.0f})")
    ax3.set_title(f"{ticker} — backtest de la VaR 95 % historique")
    ax3.set_ylabel("%")
    ax3.legend(fontsize=8)
    ax3.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    ticker = sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL"
    montant = 10_000   # portefeuille fictif de 10 000 € pour traduire en euros

    print(f"\n=== Partie 4 : risque de {ticker} ===\n")
    r = calculer_rendements(telecharger_prix(ticker))["simple"]

    print("Forme de la distribution :")
    for nom, val in statistiques_distribution(r).items():
        print(f"  {nom:<24}: {val:.4f}")

    tab = tableau_var(r)
    print("\nVaR et CVaR à 1 jour (perte en %) :")
    print((tab * 100).round(2).to_string())

    v95 = tab.loc["Historique", "VaR 95%"]
    c95 = tab.loc["Historique", "CVaR 95%"]
    print(f"\nPour {montant:,} € investis (méthode historique) :".replace(",", " "))
    print(f"  VaR 95 % 1 jour  : {v95 * montant:,.0f} €".replace(",", " "))
    print(f"  CVaR 95 % 1 jour : {c95 * montant:,.0f} €".replace(",", " "))
    print(f"  VaR 95 % 10 jours (√10) : {var_horizon(v95, 10) * montant:,.0f} €".replace(",", " "))

    bt = backtest_var(r)
    print("\nBacktest VaR 95 % (test de Kupiec) :")
    print(f"  Exceptions : {bt['exceptions']} sur {bt['jours testés']} jours "
          f"({bt['taux observé']:.1%}, attendu 5 %)")
    print(f"  p-value    : {bt['p-value']:.3f} -> modèle "
          f"{'VALIDÉ' if bt['valide'] else 'REJETÉ'} au seuil de 5 %")
    p_ind = bt["p-value indépendance"]
    print(f"  Indépendance (Christoffersen) : p = {p_ind:.3f} -> "
          f"{'exceptions indépendantes' if p_ind > 0.05 else 'exceptions EN GRAPPES'}")

    fichier = f"{ticker}_partie4.png"
    graphique(r, tab, bt, ticker, fichier)
    print(f"\nGraphique créé : {fichier}\n")
