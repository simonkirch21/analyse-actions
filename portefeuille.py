"""
PORTEFEUILLE — Analyser plusieurs actions détenues ensemble
==========================================================

Idée clé : le risque d'un portefeuille n'est PAS la moyenne des risques des actions.
Quand les actions ne bougent pas toutes en même temps (corrélation < 1), leurs hausses
et leurs baisses se compensent en partie : c'est la DIVERSIFICATION (Markowitz, 1952).

Calculs :
  - performance et risque du portefeuille (rendement, volatilité, Sharpe, perte maximale, VaR)
  - comparaison avec le marché mondial (ETF MSCI World) et avec un portefeuille équipondéré
  - matrice de corrélation, gain de diversification, contribution de chaque action au risque
  - frontière efficiente de Markowitz : portefeuille de variance minimale, portefeuille
    de Sharpe maximal, et position du portefeuille actuel
  - répartition par secteur, par place de cotation et par devise

Toutes les valeurs sont converties en euros (taux de change quotidiens).

Lancer :  .venv/bin/python portefeuille.py MC.PA:2000 AAPL:1500 TTE.PA:1000
"""

import sys
import json
import html
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yfinance as yf
from scipy.optimize import minimize

import partie2_performance as p2
import partie4_risque as p4

JOURS = 252
RF = p2.TAUX_SANS_RISQUE
REFERENCE = "URTH"            # ETF iShares MSCI World : ~1 500 grandes entreprises de 23 pays
import chemins
LISTE = chemins.liste_actions()


# ---------------------------------------------------------------------------
# 1. Données
# ---------------------------------------------------------------------------
def infos_liste() -> dict:
    try:
        return {a["ticker"]: a for a in json.loads(LISTE.read_text(encoding="utf-8"))}
    except Exception:
        return {}


def _cours(tickers: list, periode: str) -> pd.DataFrame:
    d = yf.download(tickers, period=periode, auto_adjust=True, progress=False)["Close"]
    if isinstance(d, pd.Series):
        d = d.to_frame(tickers[0])
    return d


def charger(lignes: list, periode: str, progression=print) -> tuple:
    """Cours de chaque action convertis en euros, alignés sur des dates communes."""
    tickers = [l["ticker"] for l in lignes]
    infos = infos_liste()
    progression(f"Téléchargement des cours de {len(tickers)} actions…")
    prix = _cours(tickers + [REFERENCE], periode)

    # Devises : liste de l'application, sinon Yahoo
    devises = {}
    for t in tickers + [REFERENCE]:
        dev = infos.get(t, {}).get("devise")
        if not dev:
            try:
                dev = yf.Ticker(t).fast_info.get("currency")
            except Exception:
                dev = None
        devises[t] = dev or "EUR"

    progression("Conversion en euros…")
    for dev in sorted({d for d in devises.values() if d != "EUR"}):
        fx = _cours([f"{dev}EUR=X"], periode).iloc[:, 0]
        for t in [t for t, d in devises.items() if d == dev]:
            prix[t] = prix[t] * fx.reindex(prix.index).ffill()

    # Les places ont des jours fériés différents : on prolonge le dernier cours connu,
    # puis on ne garde que les dates où toutes les séries existent
    prix = prix.ffill().dropna()
    manquants = [t for t in tickers if t not in prix.columns or prix[t].isna().all()]
    if manquants:
        raise ValueError(f"Pas de cours pour : {', '.join(manquants)}")
    if len(prix) < 60:
        raise ValueError("Historique commun trop court (moins de 60 séances).")
    return prix[tickers], prix[REFERENCE], devises


# Noms de secteurs : la liste S&P 500 (Wikipédia, norme GICS) et Yahoo n'utilisent pas les mêmes
SECTEURS_FR = {
    "Information Technology": "Technologie", "Technology": "Technologie",
    "Health Care": "Santé", "Healthcare": "Santé",
    "Consumer Discretionary": "Consommation cyclique", "Consumer Cyclical": "Consommation cyclique",
    "Consumer Staples": "Consommation de base", "Consumer Defensive": "Consommation de base",
    "Financials": "Finance", "Financial Services": "Finance",
    "Materials": "Matériaux", "Basic Materials": "Matériaux",
    "Industrials": "Industrie", "Energy": "Énergie", "Utilities": "Services aux collectivités",
    "Real Estate": "Immobilier", "Communication Services": "Communication",
}


def secteurs(tickers: list, progression=print) -> dict:
    """Secteur de chaque action (liste S&P 500, sinon Yahoo)."""
    infos, res = infos_liste(), {}
    progression("Recherche des secteurs…")
    for t in tickers:
        s = infos.get(t, {}).get("secteur")
        if not s:
            try:
                s = yf.Ticker(t).info.get("sector")
            except Exception:
                s = None
        res[t] = SECTEURS_FR.get(s, s) if s else "Non renseigné"
    return res


# ---------------------------------------------------------------------------
# 2. Statistiques
# ---------------------------------------------------------------------------
def stats_serie(valeur: pd.Series) -> dict:
    r = valeur.pct_change().dropna()
    return {
        "Rendement annualisé": p2.rendement_annualise(valeur),
        "Volatilité annualisée": p2.volatilite_annualisee(r),
        "Sharpe": p2.ratio_sharpe(r),
        "Perte maximale": p2.max_drawdown(valeur)["max_drawdown"],
        "VaR 95 % 1 jour": p4.var_historique(r, 0.95)[0],
    }


def perf_rv(w, mu, cov):
    rend = float(w @ mu)
    vol = float(np.sqrt(w @ cov @ w))
    return rend, vol


def optimiser(mu, cov, objectif: str) -> np.ndarray:
    """Portefeuille optimal sans vente à découvert (poids entre 0 et 1, somme = 1)."""
    n = len(mu)
    contraintes = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    bornes = [(0, 1)] * n
    if objectif == "variance_min":
        f = lambda w: w @ cov @ w
    else:   # Sharpe maximal
        f = lambda w: -(w @ mu - RF) / np.sqrt(w @ cov @ w)
    res = minimize(f, np.full(n, 1 / n), bounds=bornes, constraints=contraintes, method="SLSQP")
    w = np.clip(res.x, 0, 1)
    return w / w.sum()


def frontiere(mu, cov, points: int = 40) -> tuple:
    """Frontière efficiente : volatilité minimale pour chaque niveau de rendement visé."""
    n = len(mu)
    w_min = optimiser(mu, cov, "variance_min")
    r_min, r_max = float(w_min @ mu), float(mu.max())
    vols, rends = [], []
    for cible in np.linspace(r_min, r_max, points):
        c = [{"type": "eq", "fun": lambda w: w.sum() - 1},
             {"type": "eq", "fun": lambda w, c=cible: w @ mu - c}]
        res = minimize(lambda w: w @ cov @ w, np.full(n, 1 / n), bounds=[(0, 1)] * n,
                       constraints=c, method="SLSQP")
        if res.success:
            vols.append(np.sqrt(res.fun))
            rends.append(cible)
    return np.array(vols), np.array(rends)


SANS_RISQUE = "SANS_RISQUE"   # identifiant de la ligne « placement sans risque »
NOM_SANS_RISQUE = f"Placement sans risque ({RF:.0%} par an)"


def serie_sans_risque(index: pd.DatetimeIndex) -> pd.Series:
    """Valeur d'un placement qui rapporte RF par an, sans aucune variation (livret, monétaire)."""
    jours = (index - index[0]).days.values
    return pd.Series((1 + RF) ** (jours / 365.25), index=index, name=SANS_RISQUE)


def analyser(lignes: list, periode: str = "5y", progression=print, enveloppe: str = "CTO") -> dict:
    """lignes : [{'ticker': 'MC.PA', 'nom': 'LVMH', 'montant': 2000}, ...] (montants en euros).
    Le ticker SANS_RISQUE désigne un placement sans risque rémunéré au taux RF."""
    lignes = [l for l in lignes if float(l.get("montant") or 0) > 0]
    risquees = [l for l in lignes if l["ticker"] != SANS_RISQUE]
    avec_rf = len(risquees) < len(lignes)
    if len(risquees) < 2:
        raise ValueError("Il faut au moins deux actions (avec un montant) pour analyser un portefeuille.")
    tickers = [l["ticker"] for l in risquees]                 # actions seules
    toutes = tickers + ([SANS_RISQUE] if avec_rf else [])     # actions + placement sans risque
    liste = infos_liste()
    noms = {l["ticker"]: l.get("nom") or liste.get(l["ticker"], {}).get("nom") or l["ticker"] for l in risquees}
    if avec_rf:
        noms[SANS_RISQUE] = NOM_SANS_RISQUE
    montants = pd.Series({l["ticker"]: float(l["montant"]) for l in lignes})[toutes]
    poids = montants / montants.sum()

    prix, ref, devises = charger(risquees, periode, progression)
    sect = secteurs(tickers, progression)
    if avec_rf:
        prix[SANS_RISQUE] = serie_sans_risque(prix.index)
        devises[SANS_RISQUE] = "EUR"
        sect[SANS_RISQUE] = "Placement sans risque"
    prix = prix[toutes]
    progression("Calcul du risque et de la diversification…")

    # Portefeuille « acheté puis conservé » : on investit les montants au début de la période
    nb_titres = montants / prix.iloc[0]
    valeur = (prix * nb_titres).sum(axis=1)
    equi = (prix / prix.iloc[0]).mean(axis=1) * montants.sum()
    ref_val = ref / ref.iloc[0] * montants.sum()

    # Rendements HEBDOMADAIRES pour les corrélations et Markowitz : les bourses américaines et
    # européennes ne ferment pas à la même heure, ce qui fausse (vers le bas) les corrélations
    # calculées jour par jour. Sur une semaine, ce décalage devient négligeable.
    r_hebdo = prix[tickers].resample("W-FRI").last().pct_change().dropna()
    mu = r_hebdo.mean().values * 52
    cov = r_hebdo.cov().values * 52
    vols = np.sqrt(np.diag(cov))

    # Le risque s'analyse avec les poids d'AUJOURD'HUI (ils ont dérivé avec les cours)
    poids_actuels = (prix.iloc[-1] * nb_titres) / valeur.iloc[-1]
    w = poids_actuels[tickers].values          # poids des actions dans le portefeuille TOTAL
    w_rf = float(poids_actuels.get(SANS_RISQUE, 0.0))
    rend_p = float(w @ mu) + w_rf * RF
    vol_p = float(np.sqrt(w @ cov @ w))        # le placement sans risque n'ajoute aucun risque

    # Diversification : volatilité moyenne pondérée vs volatilité réelle du portefeuille
    vol_moyenne = float(w @ vols)
    # Contribution de chaque ligne au risque total (somme = 100 % ; 0 % pour le sans risque)
    contrib = w * (cov @ w) / (w @ cov @ w)

    corr = r_hebdo.corr()
    hors_diag = corr.values[np.triu_indices(len(tickers), 1)]

    progression("Optimisation de Markowitz…")
    w_min = optimiser(mu, cov, "variance_min")
    w_sharpe = optimiser(mu, cov, "sharpe")
    fr_vols, fr_rends = frontiere(mu, cov)
    rng = np.random.default_rng(42)
    aleatoires = rng.dirichlet(np.ones(len(tickers)), 3000)
    nuage = np.array([perf_rv(x, mu, cov) for x in aleatoires])
    perf_sharpe = perf_rv(w_sharpe, mu, cov)

    # Séparation de Tobin : pour un même risque que ton portefeuille, la meilleure combinaison est
    # « portefeuille de Sharpe maximal + placement sans risque » (sur la droite de marché des capitaux)
    part_tangent = vol_p / perf_sharpe[1]
    rend_tobin = RF + part_tangent * (perf_sharpe[0] - RF)

    # Rééquilibrage annuel vers les poids de départ (comparé à « acheter et ne plus toucher »)
    progression("Test du rééquilibrage annuel…")
    reequilibre = reequilibrer(prix, poids, montants.sum())
    derive = (prix * nb_titres).div(valeur, axis=0)     # évolution des poids sans rééquilibrage

    try:
        reel = suivi_reel(lignes, enveloppe, progression)
    except Exception as erreur:
        reel = {"erreur": str(erreur)}

    # Bêta du portefeuille par rapport au marché mondial
    r_ref = ref.pct_change().dropna()
    r_val = valeur.pct_change().dropna()
    commun = r_val.index.intersection(r_ref.index)
    beta = float(np.cov(r_val[commun], r_ref[commun])[0, 1] / np.var(r_ref[commun], ddof=1))

    def vecteur(x, valeur_rf):
        sv = pd.Series(x, index=tickers)
        if avec_rf:
            sv[SANS_RISQUE] = valeur_rf
        return sv[toutes]

    tableau = pd.DataFrame({
        "Nom": pd.Series(noms)[toutes],
        "Montant investi": montants,
        "Valeur actuelle": prix.iloc[-1] * nb_titres,
        "Poids actuel": poids_actuels,
        "Poids initial": poids,
        "Rendement annualisé": vecteur(mu, RF),
        "Volatilité": vecteur(vols, 0.0),
        "Contribution au risque": vecteur(contrib, 0.0),
        "Poids variance minimale": vecteur(w_min, np.nan),
        "Poids Sharpe maximal": vecteur(w_sharpe, np.nan),
        "Secteur": pd.Series(sect)[toutes],
        "Devise": pd.Series({t: devises[t] for t in toutes}),
    })

    return {
        "type": "portefeuille", "periode": periode, "tickers": tickers, "noms": noms,
        "avec_rf": avec_rf, "poids_rf": w_rf,
        "debut": prix.index[0], "fin": prix.index[-1],
        "tableau": tableau, "valeur": valeur, "equipondere": equi, "reference": ref_val,
        "reequilibre": reequilibre, "derive": derive, "reel": reel,
        "stats": {"Portefeuille": stats_serie(valeur), "Rééquilibré chaque année": stats_serie(reequilibre),
                  "Équipondéré": stats_serie(equi),
                  "Marché mondial (MSCI World)": stats_serie(ref_val)},
        "beta": beta, "vol_moyenne": vol_moyenne, "vol_portefeuille": vol_p, "rend_portefeuille": rend_p,
        "gain_diversification": 1 - vol_p / vol_moyenne,
        "corr": corr, "corr_moyenne": float(hors_diag.mean()),
        "paire_max": _paire(corr, max), "paire_min": _paire(corr, min),
        "mu": mu, "vols": vols, "w": w, "w_min": w_min, "w_sharpe": w_sharpe,
        "perf_min": perf_rv(w_min, mu, cov), "perf_sharpe": perf_sharpe,
        "part_tangent": part_tangent, "rend_tobin": rend_tobin,
        "frontiere": (fr_vols, fr_rends), "nuage": nuage,
        "par_secteur": tableau.groupby("Secteur")["Poids actuel"].sum().sort_values(ascending=False),
        "par_devise": tableau.groupby("Devise")["Poids actuel"].sum().sort_values(ascending=False),
    }


# ---------------------------------------------------------------------------
# Rééquilibrage : revenir chaque année aux poids de départ
# ---------------------------------------------------------------------------
def reequilibrer(prix: pd.DataFrame, poids: pd.Series, total: float, frais: float = 0.001) -> pd.Series:
    """Valeur d'un portefeuille ramené aux poids cibles à la première séance de chaque année.
    frais : coût de transaction sur les montants achetés ou vendus (0,1 %)."""
    qte = total * poids / prix.iloc[0]
    annee, valeurs = prix.index[0].year, []
    for d, ligne in prix.iterrows():
        v = float((qte * ligne).sum())
        if d.year != annee:                       # nouvelle année : on rééquilibre
            cible = v * poids / ligne
            echanges = float((abs(cible - qte) * ligne).sum())
            v -= echanges * frais
            qte = v * poids / ligne
            annee = d.year
        valeurs.append(v)
    return pd.Series(valeurs, index=prix.index)


# ---------------------------------------------------------------------------
# Suivi réel : prix et dates d'achat, plus-values, dividendes, fiscalité
# ---------------------------------------------------------------------------
TAUX_PFU = 0.30            # « flat tax » : 12,8 % d'impôt sur le revenu + 17,2 % de prélèvements sociaux
TAUX_PS = 0.172            # prélèvements sociaux seuls (PEA de plus de 5 ans)
PAYS_HORS_PEA = {"S&P 500"}  # actions américaines : non éligibles au PEA


def suivi_reel(lignes: list, enveloppe: str = "CTO", progression=print) -> dict:
    """Pour chaque ligne qui a une date d'achat : quantité, valeur, plus-value, dividendes, impôt estimé."""
    avec_date = [l for l in lignes if l.get("date_achat") and float(l.get("montant") or 0) > 0]
    if not avec_date:
        return None
    progression("Suivi réel : cours depuis les dates d'achat…")
    infos = infos_liste()
    debut = min(pd.Timestamp(l["date_achat"]) for l in avec_date)
    aujourd_hui = pd.Timestamp.today().normalize()
    res, alertes = [], []
    for l in avec_date:
        t, montant, d0 = l["ticker"], float(l["montant"]), pd.Timestamp(l["date_achat"])
        annees = max((aujourd_hui - d0).days / 365.25, 0)
        if t == SANS_RISQUE:
            valeur = montant * (1 + RF) ** annees
            res.append({"ticker": t, "nom": NOM_SANS_RISQUE, "date_achat": d0.strftime("%d/%m/%Y"),
                        "montant": montant, "prix_achat": None, "quantite": None, "cours": None,
                        "valeur": valeur, "plus_value": valeur - montant, "dividendes": 0.0,
                        "performance": valeur / montant - 1, "annees": annees, "devise": "EUR"})
            continue
        dev = infos.get(t, {}).get("devise") or "EUR"
        h = yf.download(t, start=d0 - pd.Timedelta(days=7), auto_adjust=False, progress=False)
        if h.empty:
            alertes.append(f"{t} : pas de cours depuis le {d0:%d/%m/%Y}.")
            continue
        cours = h["Close"].squeeze().dropna()          # cours réel (non ajusté des dividendes)
        fx = pd.Series(1.0, index=cours.index)
        if dev != "EUR":
            f = yf.download(f"{dev}EUR=X", start=d0 - pd.Timedelta(days=7), progress=False)["Close"].squeeze()
            fx = f.reindex(cours.index).ffill().bfill()
        avant = cours[cours.index <= d0]
        prix_achat = float(l["prix_achat"]) if l.get("prix_achat") else float((avant if len(avant) else cours).iloc[-1])
        fx_achat = float((fx[fx.index <= d0] if (fx.index <= d0).any() else fx).iloc[-1])
        quantite = montant / (prix_achat * fx_achat)
        valeur = quantite * float(cours.iloc[-1]) * float(fx.iloc[-1])
        try:
            dv = yf.Ticker(t).dividends
            dv.index = dv.index.tz_localize(None)
            dv = dv[dv.index > d0]
            dividendes = float(sum(m * quantite * float(fx.asof(dd) if len(fx) else 1) for dd, m in dv.items()))
        except Exception:
            dividendes = 0.0
        if enveloppe == "PEA" and infos.get(t, {}).get("place") in PAYS_HORS_PEA:
            alertes.append(f"{t} : les actions américaines ne sont pas éligibles au PEA (elles iraient sur un compte-titres).")
        res.append({"ticker": t, "nom": infos.get(t, {}).get("nom", t), "date_achat": d0.strftime("%d/%m/%Y"),
                    "montant": montant, "prix_achat": prix_achat, "quantite": quantite,
                    "cours": float(cours.iloc[-1]), "valeur": valeur, "plus_value": valeur - montant,
                    "dividendes": dividendes, "performance": (valeur + dividendes) / montant - 1,
                    "annees": annees, "devise": dev})
    if not res:
        return None
    df = pd.DataFrame(res)
    investi, valeur, pv, div = df["montant"].sum(), df["valeur"].sum(), df["plus_value"].sum(), df["dividendes"].sum()
    sans_risque = df[df["ticker"] == SANS_RISQUE]["plus_value"].sum()
    pv_actions = pv - sans_risque
    anciennete = float((aujourd_hui - debut).days / 365.25)

    # Fiscalité estimée en cas de vente de tout aujourd'hui (règles françaises simplifiées, 2026)
    if enveloppe == "PEA":
        taux = TAUX_PS if anciennete >= 5 else TAUX_PFU
        gain_imposable = max(pv_actions + div, 0)          # dans un PEA, les dividendes ne sont pas taxés à l'encaissement
        impot = gain_imposable * taux
        impot_div_deja = 0.0
        regle = (f"PEA ouvert depuis {anciennete:.1f} an(s) : ".replace(".", ",") +
                 ("après 5 ans, seuls les prélèvements sociaux (17,2 %) s'appliquent aux gains, sans impôt sur le revenu."
                  if anciennete >= 5 else
                  "avant 5 ans, un retrait déclenche la « flat tax » de 30 % sur les gains et la clôture du plan."))
    else:
        impot = max(pv_actions, 0) * TAUX_PFU
        impot_div_deja = div * TAUX_PFU                    # prélevé au moment du versement
        regle = ("Compte-titres ordinaire : plus-values et dividendes sont soumis à la « flat tax » de 30 % "
                 "(12,8 % d'impôt + 17,2 % de prélèvements sociaux). Les dividendes sont taxés à leur versement ; "
                 "les plus-values au moment de la vente. Les moins-values se déduisent des plus-values.")
    return {
        "lignes": res, "enveloppe": enveloppe, "investi": investi, "valeur": valeur, "plus_value": pv,
        "dividendes": div, "impot_vente": impot, "impot_dividendes": impot_div_deja,
        "net_apres_impot": valeur + div - impot - impot_div_deja,
        "performance_nette": (valeur + div - impot - impot_div_deja) / investi - 1,
        "anciennete": anciennete, "regle": regle, "alertes": alertes,
        "note_sans_risque": "Le placement sans risque est supposé être un livret réglementé, non imposé." if sans_risque else "",
    }


def _paire(corr: pd.DataFrame, choix) -> tuple:
    paires = [(corr.iloc[i, j], corr.index[i], corr.columns[j])
              for i in range(len(corr)) for j in range(i + 1, len(corr))]
    return choix(paires)


# ---------------------------------------------------------------------------
# 3. Graphiques
# ---------------------------------------------------------------------------
def libelle(ticker: str) -> str:
    return "Sans risque" if ticker == SANS_RISQUE else ticker


def graphique_evolution(p: dict, fichier: str) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.4))
    ax1.plot(p["valeur"], lw=2, color="#6EA8FF", label="Ton portefeuille")
    ax1.plot(p["equipondere"], color="#9AA8C7", lw=1, label="Mêmes actions, poids égaux")
    ax1.plot(p["reference"], color="#8D94A5", lw=1, label="Marché mondial (MSCI World)")
    ax1.set_title("Valeur du portefeuille (€)")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)
    for s, c, lab in [(p["valeur"], "#6EA8FF", "Portefeuille"), (p["reference"], "#8D94A5", "MSCI World")]:
        ax2.plot(p2.serie_drawdown(s) * 100, color=c, label=lab)
    ax2.set_title("Baisse depuis le plus haut (%)")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


def graphique_markowitz(p: dict, fichier: str) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.6))
    n = p["nuage"]
    sharpe = (n[:, 0] - RF) / n[:, 1]
    sc = ax.scatter(n[:, 1] * 100, n[:, 0] * 100, c=sharpe, cmap="viridis", s=5, alpha=0.5)
    fig.colorbar(sc, ax=ax, label="Ratio de Sharpe")
    fv, frd = p["frontiere"]
    ax.plot(fv * 100, frd * 100, color="#ECE8DF", lw=2, label="Frontière efficiente")
    for t, x, y in zip(p["tickers"], p["vols"], p["mu"]):
        ax.scatter(x * 100, y * 100, color="#D4AF6A", s=40, zorder=3)
        ax.annotate(t, (x * 100, y * 100), fontsize=8, xytext=(4, 3), textcoords="offset points")
    rm, vm = p["perf_min"]
    rs, vs = p["perf_sharpe"]
    ax.scatter(vm * 100, rm * 100, marker="D", s=90, color="#3BC48F", zorder=4, label="Variance minimale")
    ax.scatter(vs * 100, rs * 100, marker="*", s=220, color="#FF6B5A", zorder=4, label="Sharpe maximal")
    ax.scatter(0, RF * 100, marker="s", s=70, color="#8D94A5", zorder=4, label=f"Placement sans risque ({RF:.0%})")
    ax.scatter(p["vol_portefeuille"] * 100, p["rend_tobin"] * 100, marker="P", s=130, color="#9AA8C7", zorder=5,
               label="Même risque, combinaison optimale (Tobin)")
    ax.scatter(p["vol_portefeuille"] * 100, p["rend_portefeuille"] * 100, marker="o", s=140,
               facecolors="none", edgecolors="#6EA8FF", linewidths=3, zorder=5, label="Ton portefeuille")
    # Droite de marché des capitaux : du taux sans risque au portefeuille de Sharpe maximal
    xs = np.linspace(0, max(p["vols"].max(), vs, p["vol_portefeuille"]) * 100 * 1.1, 50)
    ax.plot(xs, RF * 100 + (rs - RF) / vs * xs, ls="--", color="#FF6B5A", lw=1, label="Droite de marché des capitaux")
    ax.set_xlim(left=-1)
    ax.set_xlabel("Risque : volatilité annualisée (%)")
    ax.set_ylabel("Rendement annualisé historique (%)")
    ax.set_title("Frontière efficiente de Markowitz (3 000 portefeuilles possibles avec tes actions)")
    ax.legend(fontsize=8, loc="best")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


def graphique_correlation(p: dict, fichier: str) -> None:
    c = p["corr"]
    n = len(c)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, max(4.2, 0.45 * n + 2)),
                                   gridspec_kw={"width_ratios": [1.3, 1]})
    im = ax1.imshow(c.values, cmap="RdYlGn_r", vmin=-1, vmax=1)
    ax1.set_xticks(range(n), c.columns, rotation=60, ha="right", fontsize=8)
    ax1.set_yticks(range(n), c.index, fontsize=8)
    if n <= 12:
        for i in range(n):
            for j in range(n):
                ax1.text(j, i, f"{c.values[i, j]:.2f}", ha="center", va="center", fontsize=7, color="#10182A")
    fig.colorbar(im, ax=ax1, fraction=0.046)
    ax1.set_title("Corrélations entre les actions")

    t = p["tableau"]
    x = np.arange(len(t))
    ax2.barh(x - 0.2, t["Poids actuel"] * 100, 0.4, label="Poids dans le portefeuille", color="#6EA8FF")
    ax2.barh(x + 0.2, t["Contribution au risque"] * 100, 0.4, label="Part du risque", color="#FF6B5A")
    ax2.set_yticks(x, [libelle(i) for i in t.index], fontsize=8)
    ax2.invert_yaxis()
    ax2.set_xlabel("%")
    ax2.set_title("Poids vs contribution au risque")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3, axis="x")
    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


def graphique_repartition(p: dict, fichier: str) -> None:
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(12, 4))
    t = p["tableau"]
    ax1.pie(t["Poids actuel"], labels=[libelle(i) for i in t.index], autopct="%1.0f%%", textprops={"fontsize": 8})
    ax1.set_title("Par action")
    ax2.pie(p["par_secteur"], labels=p["par_secteur"].index, autopct="%1.0f%%", textprops={"fontsize": 8})
    ax2.set_title("Par secteur")
    ax3.pie(p["par_devise"], labels=p["par_devise"].index, autopct="%1.0f%%", textprops={"fontsize": 8})
    ax3.set_title("Par devise")
    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


def graphique_reequilibrage(p: dict, fichier: str) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.4))
    ax1.plot(p["valeur"], color="#6EA8FF", lw=2, label="Sans rééquilibrage (on ne touche à rien)")
    ax1.plot(p["reequilibre"], color="#D4AF6A", lw=1.5, label="Rééquilibré chaque 1er janvier")
    ax1.set_title("Valeur du portefeuille (€)")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)
    d = p["derive"]
    ax2.stackplot(d.index, [d[c] * 100 for c in d.columns], labels=[libelle(c) for c in d.columns], alpha=0.85)
    ax2.set_ylim(0, 100)
    ax2.set_title("Dérive des poids si l'on ne rééquilibre jamais (%)")
    ax2.legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


GRAPHIQUES = {"reequilibrage": graphique_reequilibrage,
              "evolution": graphique_evolution, "markowitz": graphique_markowitz,
              "correlation": graphique_correlation, "repartition": graphique_repartition}


# ---------------------------------------------------------------------------
# 4. Rapport HTML
# ---------------------------------------------------------------------------
def generer_html(p: dict, graphiques: dict) -> str:
    import analyse_complete as ac
    import interpretation as ip
    import interpretation_financiere as ipf
    pct, num, niveau = ip.pct, ip.num, ip.niveau
    t = p["tableau"]
    s = p["stats"]["Portefeuille"]
    total_investi, total_actuel = t["Montant investi"].sum(), t["Valeur actuelle"].sum()

    h = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Analyse du portefeuille</title><style>{ac.CSS}{ip.CSS}{ipf.CSS}</style></head><body><main>
<h1>Ton portefeuille <span class="note">({len(p['tickers'])} actions{' + placement sans risque' if p['avec_rf'] else ''})</span></h1>
<div class="sous-titre">Du {p['debut']:%d/%m/%Y} au {p['fin']:%d/%m/%Y} · valeurs en euros · rapport du {date.today()}</div>"""

    kpis = [
        ("Investi au départ", f"{num(total_investi, 0)} €", ""),
        ("Valeur aujourd'hui", f"{num(total_actuel, 0)} €", ""),
        ("Rendement annualisé", pct(s["Rendement annualisé"]), ip.echelle_rendement(s["Rendement annualisé"])),
        ("Volatilité", pct(s["Volatilité annualisée"]), ip.echelle_volatilite(s["Volatilité annualisée"])),
        ("Sharpe", num(s["Sharpe"]), ip.echelle_sharpe(s["Sharpe"])),
        ("Perte maximale", pct(s["Perte maximale"]), ip.echelle_drawdown(s["Perte maximale"])),
        ("Gain de diversification", pct(p["gain_diversification"], 0), ""),
        ("Bêta (vs marché mondial)", num(p["beta"]), ip.echelle_beta(p["beta"])),
    ]
    h += '<div class="kpis">' + "".join(
        f'<div class="kpi"><div class="l">{l}</div><div class="v">{v}</div>{b}</div>' for l, v, b in kpis) + "</div>"

    # Résumé en langage courant
    gd = p["gain_diversification"]
    ref = p["stats"]["Marché mondial (MSCI World)"]
    phr = [
        f"<b>{num(total_investi, 0)} € investis</b> au début de la période dans ces {len(t)} actions "
        f"valent aujourd'hui <b>{num(total_actuel, 0)} €</b> ({pct(total_actuel / total_investi - 1, 0, signe=True)}). "
        f"Le marché mondial a fait {pct(p['reference'].iloc[-1] / p['reference'].iloc[0] - 1, 0, signe=True)} "
        "sur la même période.",
        f"Prises une par une, tes actions ont une volatilité moyenne de {pct(p['vol_moyenne'], 0)} ; "
        f"ensemble, le portefeuille n'a que <b>{pct(p['vol_portefeuille'], 0)}</b>. La diversification "
        f"supprime donc <b>{pct(gd, 0)} du risque</b>, sans rien coûter.",
        (f"<b>{pct(p['poids_rf'], 0)}</b> de ton portefeuille est placé sans risque, à {pct(RF, 0)} par an : "
         "cette part ne bouge pas, elle amortit les baisses mais ne profite pas des hausses."
         if p["avec_rf"] else
         "Ton portefeuille ne contient que des actions. Tu peux ajouter un placement sans risque "
         f"(rémunéré {pct(RF, 0)} par an) pour réduire le risque global : voir la partie 4."),
        f"Corrélation moyenne entre tes actions : <b>{num(p['corr_moyenne'], 2)}</b> "
        + ("(faible : elles bougent assez indépendamment, c'est idéal pour diversifier)." if p["corr_moyenne"] < 0.3 else
           "(moyenne : la diversification fonctionne, mais en partie seulement)." if p["corr_moyenne"] < 0.6 else
           "(forte : tes actions bougent ensemble, la diversification est limitée)."),
    ]
    h += ip.bloc("En résumé, en langage courant", "".join(f"<p>{x}</p>" for x in phr), "resume")

    # Synthèse
    forts, vigil = [], []
    if s["Sharpe"] > ref["Sharpe"]:
        forts.append(f"Meilleur rapport rendement / risque que le marché mondial (Sharpe {num(s['Sharpe'])} "
                     f"contre {num(ref['Sharpe'])}).")
    else:
        vigil.append(f"Rapport rendement / risque inférieur au marché mondial (Sharpe {num(s['Sharpe'])} "
                     f"contre {num(ref['Sharpe'])}) : un simple ETF MSCI World aurait fait mieux.")
    actions_seules = t.drop(index=SANS_RISQUE, errors="ignore")
    poids_max = actions_seules["Poids actuel"].max()
    if poids_max > 0.4:
        vigil.append(f"{actions_seules['Poids actuel'].idxmax()} pèse {pct(poids_max, 0)} du portefeuille : "
                     "forte concentration.")
    if p["avec_rf"] and p["poids_rf"] > 0.5:
        vigil.append(f"{pct(p['poids_rf'], 0)} du portefeuille est placé sans risque : c'est prudent, mais le "
                     f"rendement est limité ({pct(RF, 0)} par an sur cette part).")
    secteurs_actions = p["par_secteur"].drop(index="Placement sans risque", errors="ignore")
    sect_max = secteurs_actions.iloc[0] if len(secteurs_actions) else 0
    if sect_max > 0.5:
        vigil.append(f"Le secteur « {html.escape(secteurs_actions.index[0])} » représente {pct(sect_max, 0)} du "
                     "portefeuille : un choc sur ce secteur toucherait une grande partie de ton argent.")
    elif len(secteurs_actions) >= 3:
        forts.append(f"Portefeuille réparti sur {len(secteurs_actions)} secteurs.")
    if len(p["tickers"]) < 5:
        vigil.append(f"Seulement {len(p['tickers'])} actions : la recherche montre qu'il en faut au moins 15 à 20, de "
                     "secteurs variés, pour éliminer l'essentiel du risque spécifique.")
    c = t["Contribution au risque"] - t["Poids actuel"]
    if c.max() > 0.1:
        vigil.append(f"{c.idxmax()} apporte {pct(t.loc[c.idxmax(), 'Contribution au risque'], 0)} du risque pour "
                     f"seulement {pct(t.loc[c.idxmax(), 'Poids actuel'], 0)} du portefeuille.")
    if gd > 0.2:
        forts.append(f"Bonne diversification : {pct(gd, 0)} du risque éliminé grâce à des actions peu corrélées.")
    h += "<h2 id='synthese'>Synthèse</h2><div class='colonnes'>"
    h += "<div class='carte'><b>Points forts</b><ul class='fort'>" + "".join(f"<li>{x}</li>" for x in forts or ["Aucun point fort marquant."]) + "</ul></div>"
    h += "<div class='carte'><b>Points de vigilance</b><ul class='vigil'>" + "".join(f"<li>{x}</li>" for x in vigil or ["Aucun point de vigilance marquant."]) + "</ul></div></div>"

    # 1. Composition
    h += "<h2>1. Composition</h2>"
    lignes = "".join(
        f"<tr><td><b>{html.escape('Sans risque' if i == SANS_RISQUE else i)}</b> "
        f"<span class='note'>{html.escape(str(r['Nom']))}</span></td>"
        f"<td>{num(r['Montant investi'], 0)} €</td><td>{num(r['Valeur actuelle'], 0)} €</td>"
        f"<td>{pct(r['Poids actuel'], 1)}</td><td>{pct(r['Rendement annualisé'], 1)}</td>"
        f"<td>{pct(r['Volatilité'], 0)}</td><td>{html.escape(str(r['Secteur']))}</td><td>{r['Devise']}</td></tr>"
        for i, r in t.iterrows())
    h += ("<div class='carte'><table><tr><th>Action</th><th>Investi</th><th>Valeur actuelle</th><th>Poids</th>"
          "<th>Rendement annuel</th><th>Volatilité</th><th>Secteur</th><th>Devise</th></tr>" + lignes + "</table>"
          "<p class='note'>Hypothèse : les montants ont été investis au début de la période et conservés sans "
          "rééquilibrage ; les actions en dollars ou en couronnes sont converties en euros chaque jour, "
          "donc les variations de change sont incluses.</p></div>")
    h += graphiques["repartition"]

    h += section_suivi_reel(p)

    # 2. Performance
    h += "<h2>2. Performance et risque</h2>" + ip.notion(
        "<p>On compare ton portefeuille à deux repères : le <b>marché mondial</b> (l'ETF MSCI World, "
        "environ 1 500 grandes entreprises de 23 pays : ce qu'obtient un investisseur passif) et les "
        "<b>mêmes actions à poids égaux</b> (pour voir si tes choix de montants ont aidé ou pénalisé).</p>")
    st = p["stats"]
    h += "<div class='carte'><table><tr><th></th>" + "".join(f"<th>{k}</th>" for k in st) + "</tr>"
    for k, typ in [("Rendement annualisé", "%"), ("Volatilité annualisée", "%"), ("Sharpe", "x"),
                   ("Perte maximale", "%"), ("VaR 95 % 1 jour", "%")]:
        h += f"<tr><td>{k}</td>" + "".join(f"<td>{pct(v[k]) if typ == '%' else num(v[k])}</td>" for v in st.values()) + "</tr>"
    h += "</table></div>"
    h += ip.lecture_graphique("<p><b>À gauche</b> : la valeur de ton portefeuille (bleu) comparée aux deux repères. "
                              "<b>À droite</b> : les baisses depuis le plus haut ; un portefeuille bien diversifié "
                              "plonge moins fort que ses actions prises séparément.</p>")
    h += graphiques["evolution"]

    # 3. Diversification
    pmax, pmin = p["paire_max"], p["paire_min"]
    h += "<h2>3. Diversification et corrélations</h2>" + ip.notion(
        "<ul><li>La <b>corrélation</b> mesure si deux actions bougent ensemble : +1 = toujours dans le même "
        "sens, 0 = indépendamment, −1 = en sens inverse.</li>"
        "<li>Plus les corrélations sont faibles, plus les baisses des unes sont amorties par les autres : "
        "c'est la <b>diversification</b>, « le seul repas gratuit de la finance » (Markowitz). Elle "
        "élimine le <b>risque spécifique</b> (propre à chaque entreprise), mais pas le <b>risque de "
        "marché</b> (une crise générale touche tout le monde), mesuré par le bêta.</li>"
        "<li>La <b>contribution au risque</b> dit quelle part de la volatilité totale vient de chaque action. "
        "Une action peut peser 20 % du montant mais 40 % du risque si elle est très volatile.</li></ul>")
    h += ("<p class='note'>Corrélations calculées sur des rendements hebdomadaires : les bourses "
          "américaines et européennes ne ferment pas à la même heure, ce qui fausserait les corrélations "
          "jour par jour.</p>")
    h += ipf.pour_cette_action([
        f"Paire la plus corrélée : <b>{pmax[1]} / {pmax[2]}</b> ({num(pmax[0], 2)}) : ces deux-là se "
        "« doublonnent » en partie.",
        f"Paire la moins corrélée : <b>{pmin[1]} / {pmin[2]}</b> ({num(pmin[0], 2)}) : elles se "
        "complètent bien.",
        f"Bêta du portefeuille : {num(p['beta'])} : si le marché mondial perd 10 %, ton portefeuille perd en "
        f"moyenne environ {num(p['beta'] * 10, 0)} %.",
    ]).replace("pour cette entreprise", "pour ton portefeuille")
    h += ip.lecture_graphique("<p><b>À gauche</b> : chaque case donne la corrélation entre deux actions "
                              "(vert = faible, rouge = forte). <b>À droite</b> : en bleu le poids de chaque "
                              "action, en rouge sa part du risque. Une barre rouge plus longue que la bleue "
                              "signale une action qui ajoute plus de risque que son poids.</p>")
    h += graphiques["correlation"]

    # 4. Markowitz
    rs, vs = p["perf_sharpe"]
    rm, vm = p["perf_min"]
    h += "<h2>4. Optimisation de Markowitz</h2>" + ip.notion(
        "<p>Avec les mêmes actions, on peut composer une infinité de portefeuilles en changeant les poids. "
        "Chaque point du nuage en est un. La <b>frontière efficiente</b> (courbe noire) relie les "
        "portefeuilles qui offrent le <b>meilleur rendement pour chaque niveau de risque</b> : tout "
        "portefeuille situé en dessous peut être amélioré.</p><ul>"
        "<li><b>Variance minimale</b> (losange vert) : le moins risqué possible avec ces actions.</li>"
        "<li><b>Sharpe maximal</b> (étoile rouge) : le meilleur rendement par unité de risque. La droite "
        "en pointillés (droite de marché des capitaux) part du taux sans risque et le touche : en "
        "combinant ce portefeuille avec un placement sans risque, on obtient les meilleurs couples "
        "rendement / risque possibles.</li></ul>")
    h += ip.bloc("Attention : l'optimisation regarde dans le rétroviseur", (
        "<p>Les poids « optimaux » sont calculés avec les rendements <b>passés</b>, qui se répètent rarement. "
        "Markowitz a tendance à tout miser sur les actions qui ont le plus monté. En pratique, les "
        "gérants limitent les poids et préfèrent souvent le portefeuille de variance minimale, plus "
        "stable car il ne dépend que des risques et des corrélations.</p>"), "lecture")
    h += ip.notion(
        "<p><b>Le rôle du placement sans risque (séparation de Tobin, 1958).</b> Un placement sans risque "
        f"(livret, fonds monétaire, emprunt d'État court) rapporte {pct(RF, 0)} par an sans jamais varier. "
        "En le combinant avec le portefeuille d'actions de <b>Sharpe maximal</b>, on se déplace le long de la "
        "<b>droite de marché des capitaux</b> (pointillés rouges) : plus de sans risque = moins de risque et "
        "moins de rendement, plus d'actions = l'inverse.</p><p>Conséquence : tout investisseur devrait détenir "
        "le <b>même</b> portefeuille d'actions (celui de Sharpe maximal), et régler son niveau de risque "
        "uniquement avec la part placée sans risque. La croix violette montre cette combinaison optimale "
        "pour <b>le même risque</b> que ton portefeuille actuel.</p>")
    part, rt = p["part_tangent"], p["rend_tobin"]
    if part <= 1:
        tobin = (f"Pour le même risque que ton portefeuille ({pct(p['vol_portefeuille'], 1)} de volatilité), la "
                 f"combinaison optimale serait <b>{pct(part, 0)} en portefeuille de Sharpe maximal</b> et "
                 f"<b>{pct(1 - part, 0)} en placement sans risque</b> : rendement attendu {pct(rt, 1)}, "
                 f"contre {pct(p['rend_portefeuille'], 1)} pour ton portefeuille actuel (chiffres historiques).")
    else:
        tobin = (f"Ton portefeuille est plus risqué que le portefeuille de Sharpe maximal : pour atteindre ce "
                 f"niveau de risque sur la droite de marché, il faudrait <b>emprunter</b> au taux sans risque "
                 f"({pct(part - 1, 0)} de la mise) pour investir {pct(part, 0)} en actions.")
    h += ipf.pour_cette_action([
        f"Ton portefeuille : rendement {pct(p['rend_portefeuille'], 1)}, volatilité {pct(p['vol_portefeuille'], 1)}"
        + (f", dont {pct(p['poids_rf'], 0)} placés sans risque." if p["avec_rf"] else "."),
        tobin,
        f"Variance minimale : volatilité {pct(vm, 1)} pour un rendement de {pct(rm, 1)}.",
        f"Sharpe maximal : rendement {pct(rs, 1)} pour une volatilité de {pct(vs, 1)}.",
    ]).replace("pour cette entreprise", "pour ton portefeuille")
    h += ("<div class='carte'><table><tr><th>Ligne</th><th>Poids actuel</th><th>Variance minimale</th>"
          "<th>Sharpe maximal</th></tr>")
    for i, r in t.iterrows():
        h += (f"<tr><td>{html.escape(NOM_SANS_RISQUE if i == SANS_RISQUE else i)}</td><td>{pct(r['Poids actuel'], 0)}</td>"
              f"<td>{pct(r['Poids variance minimale'], 0)}</td><td>{pct(r['Poids Sharpe maximal'], 0)}</td></tr>")
    h += ("</table><p class='note'>Les portefeuilles de variance minimale et de Sharpe maximal ne "
          "contiennent que des actions : la part sans risque se règle ensuite selon le risque souhaité "
          "(voir ci-dessus).</p></div>")
    h += graphiques["markowitz"]

    # 5. Rééquilibrage
    sb, sr = p["stats"]["Portefeuille"], p["stats"]["Rééquilibré chaque année"]
    h += "<h2>5. Faut-il rééquilibrer ?</h2>" + ip.notion(
        "<p>Avec le temps, les actions qui montent prennent de plus en plus de place dans le portefeuille : "
        "les poids <b>dérivent</b>, et le risque avec eux. <b>Rééquilibrer</b>, c'est revenir régulièrement "
        "(ici chaque 1er janvier) aux poids de départ : on vend un peu de ce qui a monté et on rachète ce "
        "qui a baissé. Cela garde le niveau de risque choisi et oblige à « vendre cher, acheter bon "
        "marché », mais coûte des frais (0,1 % par opération ici) et réduit le gain si une action monte "
        "sans s'arrêter.</p>")
    meilleur = "le rééquilibrage annuel" if sr["Rendement annualisé"] > sb["Rendement annualisé"] else "le fait de ne rien toucher"
    h += ipf.pour_cette_action([
        f"Sans rééquilibrage : rendement {pct(sb['Rendement annualisé'])} par an, volatilité "
        f"{pct(sb['Volatilité annualisée'])}, perte maximale {pct(sb['Perte maximale'])}.",
        f"Avec rééquilibrage annuel : rendement {pct(sr['Rendement annualisé'])} par an, volatilité "
        f"{pct(sr['Volatilité annualisée'])}, perte maximale {pct(sr['Perte maximale'])}.",
        f"Sur cette période, c'est <b>{meilleur}</b> qui a le mieux rapporté. Le rééquilibrage sert "
        "surtout à <b>maîtriser le risque</b> : son effet sur le rendement dépend de la période.",
    ]).replace("pour cette entreprise", "pour ton portefeuille")
    h += ip.lecture_graphique("<p><b>À gauche</b> : les deux stratégies avec les mêmes sommes de départ. "
                              "<b>À droite</b> : comment les poids auraient dérivé sans jamais rééquilibrer ; "
                              "une couleur qui s'élargit est une action qui a pris de plus en plus de place.</p>")
    h += graphiques["reequilibrage"]
    h += ip.lexique()
    return h + "</main></body></html>"


def section_suivi_reel(p: dict) -> str:
    import interpretation as ip
    import interpretation_financiere as ipf
    pct, num = ip.pct, ip.num
    r = p.get("reel")
    if not r:
        return ("<p class='note'>Astuce : indique la <b>date d'achat</b> (et si tu veux le prix payé) de chaque "
                "ligne dans « Mon portefeuille » pour obtenir le suivi réel : plus-values, dividendes reçus et "
                "impôt estimé.</p>")
    if "erreur" in r:
        return f"<p class='note'>Suivi réel indisponible : {html.escape(r['erreur'])}</p>"
    h = f"<h2>Suivi réel de tes placements <span class='note'>({html.escape(r['enveloppe'])})</span></h2>"
    h += ip.notion(
        "<p>Cette partie utilise tes <b>vraies dates et prix d'achat</b> : elle montre ce que tu as gagné ou "
        "perdu depuis l'achat, les dividendes encaissés, et l'impôt que tu paierais si tu vendais tout "
        "aujourd'hui. La <b>plus-value latente</b> est un gain « sur le papier » : elle n'est réalisée (et "
        "imposée) qu'au moment de la vente.</p>")
    lignes = ""
    for l in r["lignes"]:
        lignes += (f"<tr><td><b>{html.escape('Sans risque' if l['ticker'] == SANS_RISQUE else l['ticker'])}</b> "
                   f"<span class='note'>{html.escape(l['nom'])}</span></td><td>{l['date_achat']}</td>"
                   f"<td>{num(l['montant'], 0)} €</td>"
                   f"<td>{num(l['prix_achat']) + ' ' + l['devise'] if l['prix_achat'] else '—'}</td>"
                   f"<td>{num(l['quantite'], 2) if l['quantite'] else '—'}</td>"
                   f"<td>{num(l['valeur'], 0)} €</td>"
                   f"<td class='{'pos' if l['plus_value'] >= 0 else 'neg'}'>{num(l['plus_value'], 0)} €</td>"
                   f"<td>{num(l['dividendes'], 0)} €</td><td>{pct(l['performance'], 1, signe=True)}</td></tr>")
    h += ("<div class='carte'><table><tr><th>Ligne</th><th>Achat</th><th>Investi</th><th>Prix payé</th>"
          "<th>Quantité</th><th>Valeur</th><th>Plus-value latente</th><th>Dividendes reçus (bruts)</th>"
          "<th>Performance totale</th></tr>" + lignes +
          f"<tr><td><b>Total</b></td><td></td><td><b>{num(r['investi'], 0)} €</b></td><td></td><td></td>"
          f"<td><b>{num(r['valeur'], 0)} €</b></td><td><b>{num(r['plus_value'], 0)} €</b></td>"
          f"<td><b>{num(r['dividendes'], 0)} €</b></td><td></td></tr></table></div>")
    phrases = [
        f"Tu as investi <b>{num(r['investi'], 0)} €</b> ; ton portefeuille vaut <b>{num(r['valeur'], 0)} €</b>, "
        f"et tu as reçu {num(r['dividendes'], 0)} € de dividendes bruts.",
        f"Si tu vendais tout aujourd'hui : impôt estimé de <b>{num(r['impot_vente'], 0)} €</b>"
        + (f" (plus {num(r['impot_dividendes'], 0)} € déjà prélevés sur les dividendes)" if r["impot_dividendes"] else "")
        + f", soit <b>{num(r['net_apres_impot'], 0)} €</b> nets ({pct(r['performance_nette'], 1, signe=True)} après impôt).",
        html.escape(r["regle"]),
    ] + [html.escape(a) for a in r["alertes"]] + ([r["note_sans_risque"]] if r["note_sans_risque"] else [])
    h += ipf.pour_cette_action(phrases).replace("pour cette entreprise", "pour toi")
    h += ("<p class='note'>Estimation pédagogique, règles françaises simplifiées : sans abattements, crédits "
          "d'impôt ni option pour le barème progressif. Le prix payé est le cours de clôture du jour d'achat "
          "si tu ne l'as pas indiqué.</p>")
    return h


def nom_fichier(periode: str) -> str:
    from datetime import datetime
    return f"portefeuille_{periode}_{datetime.now():%Y-%m-%d_%H%M%S}"


if __name__ == "__main__":
    import analyse_complete as ac
    lignes = []
    for x in sys.argv[1:] or ["MC.PA:2000", "AAPL:1500", "TTE.PA:1000", "ASML.AS:1000"]:
        t, _, m = x.partition(":")
        lignes.append({"ticker": t.upper(), "montant": float(m or 1000)})
    p = analyser(lignes)
    g = {k: ac.image_base64(f, p) for k, f in GRAPHIQUES.items()}
    ac.DOSSIER_RAPPORTS.mkdir(exist_ok=True)
    fichier = ac.DOSSIER_RAPPORTS / f"{nom_fichier('5y')}.html"
    fichier.write_text(generer_html(p, g), encoding="utf-8")
    print(p["tableau"].round(3).to_string())
    print({k: round(v, 3) for k, v in p["stats"]["Portefeuille"].items()}, "gain div", round(p["gain_diversification"], 3))
    print(f"Rapport : {fichier}")
