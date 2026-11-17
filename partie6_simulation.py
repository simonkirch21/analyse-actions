"""
PARTIE 6 — Simulation Monte Carlo et pricing d'options
======================================================

A. Projection du cours à 1 an par Monte Carlo
   Modèle : mouvement brownien géométrique (GBM), le modèle de Black-Scholes :
       S_{t+dt} = S_t × exp[ (μ - σ²/2) dt + σ √dt Z ],   Z ~ N(0, 1)

B. Prix d'options européennes (call / put) avec trois méthodes :
   1. Formule fermée de Black-Scholes (+ les grecques)
   2. Monte Carlo en probabilité risque-neutre (μ remplacé par r)
   3. Arbre binomial de Cox-Ross-Rubinstein (permet aussi l'option AMÉRICAINE)

Lancer :  .venv/bin/python partie6_simulation.py AAPL
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

from partie1_donnees import telecharger_prix, calculer_rendements
from partie2_performance import JOURS_PAR_AN, TAUX_SANS_RISQUE

GRAINE = 42


# ---------------------------------------------------------------------------
# A. Monte Carlo du cours
# ---------------------------------------------------------------------------
def parametres_gbm(prix: pd.Series) -> tuple:
    """Estime μ (dérive) et σ (volatilité) annuels à partir des rendements log."""
    r_log = calculer_rendements(prix)["log"]
    sigma = r_log.std() * np.sqrt(JOURS_PAR_AN)
    mu = r_log.mean() * JOURS_PAR_AN + sigma ** 2 / 2   # car E[log] = μ - σ²/2
    return mu, sigma


def simuler_gbm(S0: float, mu: float, sigma: float, jours: int = JOURS_PAR_AN,
                n: int = 10_000) -> np.ndarray:
    """Renvoie une matrice (jours + 1) × n : une colonne = une trajectoire."""
    rng = np.random.default_rng(GRAINE)
    dt = 1 / JOURS_PAR_AN
    Z = rng.standard_normal((jours, n))                  # R : matrix(rnorm(...))
    increments = (mu - sigma ** 2 / 2) * dt + sigma * np.sqrt(dt) * Z
    log_chemins = np.vstack([np.zeros(n), np.cumsum(increments, axis=0)])
    return S0 * np.exp(log_chemins)


def resume_simulation(S0: float, finaux: np.ndarray) -> dict:
    return {
        "Prix actuel": S0,
        "Prix médian à 1 an": np.median(finaux),
        "Prix moyen à 1 an": finaux.mean(),
        "Percentile 5 %": np.percentile(finaux, 5),
        "Percentile 95 %": np.percentile(finaux, 95),
        "Probabilité de perte": (finaux < S0).mean(),
        "Probabilité de +20 %": (finaux > 1.2 * S0).mean(),
        "VaR 95 % à 1 an": 1 - np.percentile(finaux, 5) / S0,
    }


# ---------------------------------------------------------------------------
# B1. Black-Scholes
# ---------------------------------------------------------------------------
def black_scholes(S, K, T, r, sigma, type_option="call") -> dict:
    """Prix et grecques d'une option européenne (sans dividende).

    S : prix du sous-jacent, K : strike, T : maturité en années,
    r : taux sans risque (continu), sigma : volatilité annuelle.
    """
    d1 = (np.log(S / K) + (r + sigma ** 2 / 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    N, n = stats.norm.cdf, stats.norm.pdf          # R : pnorm, dnorm

    if type_option == "call":
        prix = S * N(d1) - K * np.exp(-r * T) * N(d2)
        delta = N(d1)
        theta = (-S * n(d1) * sigma / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * N(d2))
        rho = K * T * np.exp(-r * T) * N(d2)
    else:
        prix = K * np.exp(-r * T) * N(-d2) - S * N(-d1)
        delta = N(d1) - 1
        theta = (-S * n(d1) * sigma / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * N(-d2))
        rho = -K * T * np.exp(-r * T) * N(-d2)

    return {
        "Prix": prix,
        "Delta": delta,                                  # ∂Prix/∂S
        "Gamma": n(d1) / (S * sigma * np.sqrt(T)),       # ∂²Prix/∂S²
        "Vega (pour +1 pt de vol)": S * n(d1) * np.sqrt(T) / 100,
        "Theta (par jour)": theta / 365,
        "Rho (pour +1 pt de taux)": rho / 100,
    }


# ---------------------------------------------------------------------------
# B2. Monte Carlo risque-neutre
# ---------------------------------------------------------------------------
def prix_monte_carlo(S, K, T, r, sigma, type_option="call", n=200_000) -> tuple:
    """En univers risque-neutre, le prix = E[payoff] actualisé au taux r."""
    rng = np.random.default_rng(GRAINE)
    Z = rng.standard_normal(n // 2)
    Z = np.concatenate([Z, -Z])     # variables antithétiques : réduit la variance
    ST = S * np.exp((r - sigma ** 2 / 2) * T + sigma * np.sqrt(T) * Z)
    payoff = np.maximum(ST - K, 0) if type_option == "call" else np.maximum(K - ST, 0)
    actualise = np.exp(-r * T) * payoff
    prix = actualise.mean()
    erreur = actualise.std() / np.sqrt(n)
    return prix, (prix - 1.96 * erreur, prix + 1.96 * erreur)


# ---------------------------------------------------------------------------
# B3. Arbre binomial CRR
# ---------------------------------------------------------------------------
def prix_binomial(S, K, T, r, sigma, type_option="put", n=500, americaine=False) -> float:
    """À chaque pas le prix monte (×u) ou baisse (×d).
    Une option américaine peut être exercée à tout moment : on compare
    à chaque nœud la valeur de continuation et la valeur d'exercice immédiat."""
    dt = T / n
    u = np.exp(sigma * np.sqrt(dt))
    d = 1 / u
    p = (np.exp(r * dt) - d) / (u - d)          # probabilité risque-neutre
    actu = np.exp(-r * dt)

    j = np.arange(n + 1)
    ST = S * u ** (n - j) * d ** j               # prix à maturité
    payoff = (lambda s: np.maximum(s - K, 0)) if type_option == "call" \
        else (lambda s: np.maximum(K - s, 0))
    valeur = payoff(ST)

    for etape in range(n - 1, -1, -1):           # on remonte l'arbre
        valeur = actu * (p * valeur[:-1] + (1 - p) * valeur[1:])
        if americaine:
            j = np.arange(etape + 1)
            St = S * u ** (etape - j) * d ** j
            valeur = np.maximum(valeur, payoff(St))
    return valeur[0]


# ---------------------------------------------------------------------------
def volatilite_recente(prix: pd.Series, jours: int = JOURS_PAR_AN) -> float:
    """Volatilité historique sur la dernière année : celle utilisée pour pricer."""
    return calculer_rendements(prix)["log"].iloc[-jours:].std() * np.sqrt(JOURS_PAR_AN)


def analyse_options(S: float, sigma: float, T: float = 0.25) -> dict:
    """Option à la monnaie (K = S), maturité 3 mois par défaut."""
    r = np.log(1 + TAUX_SANS_RISQUE)            # taux continu équivalent
    K = S
    call = black_scholes(S, K, T, r, sigma, "call")
    put = black_scholes(S, K, T, r, sigma, "put")
    mc_call, ic_call = prix_monte_carlo(S, K, T, r, sigma, "call")
    bin_call = prix_binomial(S, K, T, r, sigma, "call")
    bin_put_eu = prix_binomial(S, K, T, r, sigma, "put")
    bin_put_us = prix_binomial(S, K, T, r, sigma, "put", americaine=True)
    # Parité call-put : C - P = S - K e^{-rT}  (doit être vraie à l'arrondi près)
    parite = (call["Prix"] - put["Prix"]) - (S - K * np.exp(-r * T))

    # Prix en fonction du strike (de 80 % à 120 % du cours)
    strikes = S * np.array([0.8, 0.9, 1.0, 1.1, 1.2])
    grille = pd.DataFrame({
        "Strike": strikes,
        "Call": [black_scholes(S, k, T, r, sigma, "call")["Prix"] for k in strikes],
        "Put": [black_scholes(S, k, T, r, sigma, "put")["Prix"] for k in strikes],
    })
    return {
        "S": S, "K": K, "T": T, "r": r, "sigma": sigma,
        "call": call, "put": put,
        "mc_call": mc_call, "ic_call": ic_call,
        "bin_call": bin_call, "bin_put_eu": bin_put_eu, "bin_put_us": bin_put_us,
        "parite": parite, "grille": grille,
    }


def graphique(chemins: np.ndarray, opt: dict, ticker: str, fichier: str) -> None:
    fig = plt.figure(figsize=(11, 9))
    g = fig.add_gridspec(2, 2)
    S0 = chemins[0, 0]

    # 1. Éventail des trajectoires
    ax1 = fig.add_subplot(g[0, :])
    jours = np.arange(chemins.shape[0])
    ax1.plot(jours, chemins[:, :100], color="#6EA8FF", alpha=0.08, lw=0.7)
    for q, style in [(5, "--"), (50, "-"), (95, "--")]:
        ax1.plot(jours, np.percentile(chemins, q, axis=1), color="#ECE8DF", ls=style,
                 label=f"Percentile {q} %")
    ax1.axhline(S0, color="#FF6B5A", lw=0.7)
    ax1.set_title(f"{ticker} — {chemins.shape[1]:,} trajectoires simulées sur 1 an (GBM)"
                  .replace(",", " "))
    ax1.set_xlabel("Jours de bourse")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)

    # 2. Distribution du prix final
    ax2 = fig.add_subplot(g[1, 0])
    finaux = chemins[-1]
    ax2.hist(finaux, bins=80, color="#6EA8FF", alpha=0.7)
    ax2.axvline(S0, color="#FF6B5A", label=f"Prix actuel ({S0:.0f})")
    ax2.set_title(f"Prix dans 1 an (P(perte) = {(finaux < S0).mean():.0%})")
    ax2.legend(fontsize=8)

    # 3. Convergence de l'arbre binomial vers Black-Scholes
    ax3 = fig.add_subplot(g[1, 1])
    pas = np.arange(5, 301, 5)
    valeurs = [prix_binomial(opt["S"], opt["K"], opt["T"], opt["r"], opt["sigma"], "call", n)
               for n in pas]
    ax3.plot(pas, valeurs, lw=1, label="Arbre binomial")
    ax3.axhline(opt["call"]["Prix"], color="#FF6B5A", ls="--", label="Black-Scholes")
    ax3.set_title("Call ATM 3 mois : convergence binomial → BS")
    ax3.set_xlabel("Nombre de pas")
    ax3.legend(fontsize=8)
    ax3.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    ticker = sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL"
    print(f"\n=== Partie 6 : simulation et options sur {ticker} ===\n")

    prix = telecharger_prix(ticker)
    S0 = prix.iloc[-1]
    mu, sigma = parametres_gbm(prix)
    print(f"Paramètres estimés : μ = {mu:.1%} / an, σ = {sigma:.1%} / an\n")

    chemins = simuler_gbm(S0, mu, sigma)
    print("Projection à 1 an (10 000 trajectoires) :")
    for nom, val in resume_simulation(S0, chemins[-1]).items():
        texte = f"{val:.1%}" if ("Probabilité" in nom or "VaR" in nom) else f"{val:.2f}"
        print(f"  {nom:<22}: {texte}")
    print("  ⚠ μ est estimé sur le passé : c'est une hypothèse, pas une prévision.")

    opt = analyse_options(S0, volatilite_recente(prix))
    print(f"\nOptions à la monnaie (K = {opt['K']:.2f}), maturité 3 mois, "
          f"σ historique 1 an = {opt['sigma']:.1%}, r = {TAUX_SANS_RISQUE:.0%}")
    print(f"\n  {'':<26}{'Call':>10}{'Put':>10}")
    for g in opt["call"]:
        print(f"  {g:<26}{opt['call'][g]:>10.4f}{opt['put'][g]:>10.4f}")

    lo, hi = opt["ic_call"]
    print(f"\n  Call — Monte Carlo        : {opt['mc_call']:.4f}  (IC 95 % : {lo:.4f} – {hi:.4f})")
    print(f"  Call — binomial 500 pas   : {opt['bin_call']:.4f}")
    print(f"  Put européen — binomial   : {opt['bin_put_eu']:.4f}")
    print(f"  Put AMÉRICAIN — binomial  : {opt['bin_put_us']:.4f}  "
          f"(prime d'exercice anticipé : {opt['bin_put_us'] - opt['bin_put_eu']:.4f})")
    print(f"  Parité call-put (écart)   : {opt['parite']:.2e}")

    print("\nPrix Black-Scholes selon le strike :")
    print(opt["grille"].round(2).to_string(index=False))

    fichier = f"{ticker}_partie6.png"
    graphique(chemins, opt, ticker, fichier)
    print(f"\nGraphique créé : {fichier}\n")
