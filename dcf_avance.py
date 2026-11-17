"""
DCF AVANCÉ — Le modèle d'évaluation des banques d'affaires, année par année
==========================================================================

Valeur d'une entreprise = flux de trésorerie disponibles pour TOUS les financeurs (FCFF),
actualisés au coût moyen du capital (CMPC), + une valeur terminale.

  Chiffre d'affaires (CA)            croissance année par année (consensus puis convergence)
  × marge d'EBITDA (EBE)           = EBITDA
  − dotations aux amortissements   = EBIT (résultat d'exploitation)
  − impôt sur l'EBIT               = NOPAT
  + amortissements − investissements (capex) − hausse du BFR
                                   = FCFF (flux disponible pour l'entreprise)

  Valeur terminale, deux méthodes :
    - Gordon-Shapiro : FCFF(N+1) / (CMPC − g)
    - Multiple de sortie : EBITDA(N) × VE/EBITDA des concurrents
  Valeur d'entreprise (VE) − dette financière + trésorerie − intérêts minoritaires
                                   = valeur des capitaux propres, ÷ nombre d'actions dilué

Ajoute : trois scénarios pondérés, DCF inversé (croissance anticipée par le cours) et
tables de sensibilité. Montants dans la devise des comptes ; valeur par action dans celle du cours.

Lancer :  .venv/bin/python dcf_avance.py AAPL
"""

import copy
import math
import sys
import threading
import time

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.optimize import brentq

import partie8_analyse_financiere as p8
from partie8_analyse_financiere import _ligne, TAUX_SANS_RISQUE, PRIME_RISQUE
from partie9_valorisation import taux_change

HORIZON = 5
G_INF = 0.02
_cache, _verrou = {}, threading.Lock()


def _f(x, defaut=np.nan):
    try:
        x = float(x)
        return x if math.isfinite(x) else defaut
    except (TypeError, ValueError):
        return defaut


def _moy(s: pd.Series, n: int = 3) -> float:
    s = s.replace([np.inf, -np.inf], np.nan).dropna()
    return float(s.iloc[-n:].mean()) if len(s) else np.nan


def beta_historique(ticker: str) -> float:
    """Bêta brut : covariance des rendements hebdomadaires sur 5 ans avec l'indice de la place
    (rendements hebdomadaires : évite le décalage d'horaires entre places, comme pour le portefeuille)."""
    try:
        from partie3_marche import indice_par_defaut
        indice = indice_par_defaut(ticker)
        px = yf.download([ticker, indice], period="5y", interval="1wk", progress=False, auto_adjust=True)["Close"]
        r = px[[ticker, indice]].pct_change().dropna()
        if len(r) < 52:
            return np.nan
        return float(r[ticker].cov(r[indice]) / r[indice].var())
    except Exception:
        return np.nan


# ---------------------------------------------------------------------------
# 1. Données : historique, hypothèses par défaut, pont VE → capitaux propres
# ---------------------------------------------------------------------------
def donnees(ticker: str) -> dict:
    with _verrou:
        v = _cache.get(ticker)
        if v and time.time() - v[0] < 3600:
            return v[1]
    d = p8.charger(ticker)
    cr, b, fl, info = d["cr"], d["bilan"], d["flux"], d["info"]
    if cr.empty or b.empty:
        raise ValueError("Yahoo Finance ne fournit pas les comptes de cette entreprise.")
    if (info.get("sector") or "") == "Financial Services" and _ligne(b, "Current Assets").isna().all():
        raise ValueError("C'est une banque ou une assurance : un DCF sur flux de trésorerie disponibles n'a pas de sens "
                         "(la dette est sa matière première). On les évalue plutôt par les dividendes ou le P/B.")

    ca = _ligne(cr, "Total Revenue", "Operating Revenue")
    annees = [a for a in ca.dropna().index if a in b.index][-4:]
    if len(annees) < 2:
        raise ValueError("Moins de deux exercices disponibles : modèle impossible.")
    ca = ca.loc[annees]
    da = _ligne(cr, "Reconciled Depreciation").reindex(annees)
    da = da.fillna(_ligne(fl, "Depreciation And Amortization", "Depreciation Amortization Depletion").reindex(annees))
    ebitda = _ligne(cr, "EBITDA", "Normalized EBITDA").reindex(annees)
    ebit = _ligne(cr, "EBIT", "Operating Income").reindex(annees)
    ebitda = ebitda.fillna(ebit + da)
    da = da.fillna(ebitda - ebit)
    capex = -_ligne(fl, "Capital Expenditure").reindex(annees)
    taux = _ligne(cr, "Tax Rate For Calcs").reindex(annees).clip(0, 0.40)
    treso_b = _ligne(b, "Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents").reindex(annees)
    dette_ct = _ligne(b, "Current Debt And Capital Lease Obligation", "Current Debt").reindex(annees).fillna(0)
    bfr = (_ligne(b, "Current Assets").reindex(annees) - treso_b.fillna(0)
           - (_ligne(b, "Current Liabilities").reindex(annees) - dette_ct))
    croissance = ca.pct_change()

    def pc(s):
        return s / ca

    hist = [{"annee": int(a), "ca": _f(ca[a]), "croissance": _f(croissance[a]), "ebitda": _f(ebitda[a]),
             "marge_ebitda": _f(pc(ebitda)[a]), "da": _f(da[a]), "da_ca": _f(pc(da)[a]), "ebit": _f(ebit[a]),
             "capex": _f(capex[a]), "capex_ca": _f(pc(capex)[a]), "bfr_ca": _f(pc(bfr)[a]), "taux_is": _f(taux[a])}
            for a in annees]

    # Hypothèses par défaut : moyenne des 3 derniers exercices, consensus pour la croissance à 1-2 ans
    marge = _moy(pc(ebitda)); marge = marge if pd.notna(marge) else 0.15
    da_ca = _moy(pc(da)); da_ca = da_ca if pd.notna(da_ca) else 0.04
    capex_ca = _moy(pc(capex)); capex_ca = capex_ca if pd.notna(capex_ca) else da_ca
    bfr_ca = _moy(pc(bfr)); bfr_ca = float(np.clip(bfr_ca, -0.3, 0.5)) if pd.notna(bfr_ca) else 0.05
    taux_is = _moy(taux); taux_is = taux_is if pd.notna(taux_is) and taux_is > 0.05 else 0.25
    tcam = (ca.iloc[-1] / ca.iloc[0]) ** (1 / (len(ca) - 1)) - 1 if ca.iloc[0] > 0 else np.nan

    consensus = []
    try:
        est = yf.Ticker(ticker).revenue_estimate
        for per in ("0y", "+1y"):
            g = _f(est.loc[per, "growth"]) if est is not None and per in est.index else np.nan
            consensus.append(float(np.clip(g, -0.3, 0.6)) if pd.notna(g) else None)
    except Exception:
        consensus = [None, None]
    g1 = consensus[0] if consensus and consensus[0] is not None else (float(np.clip(tcam, -0.05, 0.25)) if pd.notna(tcam) else 0.04)
    g2 = consensus[1] if len(consensus) > 1 and consensus[1] is not None else g1
    # Années 3 à 5 : convergence linéaire vers la croissance à l'infini (la croissance forte ne dure pas)
    trajectoire = [g1, g2] + [g2 + (G_INF - g2) * (t - 2) / (HORIZON - 1) for t in range(3, HORIZON + 1)]

    # Pont VE → capitaux propres et nombre d'actions
    an = annees[-1]
    dette = _f(_ligne(b, "Total Debt").get(an), 0.0)
    tresorerie = _f(treso_b.get(an), 0.0)
    minoritaires = _f(_ligne(b, "Minority Interest").get(an), 0.0)
    actions = _f(info.get("sharesOutstanding") or info.get("impliedSharesOutstanding"))
    if pd.isna(actions):
        actions = _f(_ligne(b, "Ordinary Shares Number").get(an))
    dilution = _f(_ligne(cr, "Diluted Average Shares").get(an)) / _f(_ligne(cr, "Basic Average Shares").get(an))
    dilution = float(np.clip(dilution, 1.0, 1.1)) if pd.notna(dilution) else 1.0
    actions_diluees = actions * dilution

    devise_compta = info.get("financialCurrency") or info.get("currency") or ""
    devise_cours = info.get("currency") or devise_compta
    fx = taux_change(devise_compta, devise_cours)
    fx = fx if pd.notna(fx) else 1.0
    cours = _f(info.get("currentPrice") or info.get("regularMarketPrice"))
    if pd.isna(cours):
        cours = float(yf.Ticker(ticker).history(period="5d")["Close"].dropna().iloc[-1])

    # Coût du capital : bêta calculé sur 5 ans de rendements hebdomadaires, ajusté (Blume)
    beta_brut = beta_historique(ticker)
    if pd.isna(beta_brut):
        beta_brut = _f(info.get("beta"), 1.0)
    beta = float(np.clip(0.67 * beta_brut + 0.33, 0.7, 2.5))   # plancher : un bêta passé très bas sous-estime souvent le risque
    frais = _f(_ligne(cr, "Interest Expense", "Interest Expense Non Operating").get(an))
    kd = abs(frais) / dette if dette > 0 and pd.notna(frais) else np.nan
    kd = float(np.clip(kd, 0.02, 0.12)) if pd.notna(kd) else 0.045
    capi_compta = cours * actions / fx
    poids_cp = capi_compta / (capi_compta + max(dette, 0)) if capi_compta > 0 else 0.8

    # Multiple de sortie : VE/EBITDA médian des concurrents (sinon celui de l'entreprise)
    pairs = []
    try:
        import base_fondamentale
        pairs = [{"ticker": c["ticker"], "nom": c["nom"], "ve_ebe": c["ve_ebe"]}
                 for c in base_fondamentale.concurrents(ticker, n=6) if c.get("ve_ebe") and 2 < c["ve_ebe"] < 40]
    except Exception:
        pass
    ve_actuelle = capi_compta + dette - tresorerie + minoritaires
    multiple_propre = ve_actuelle / ebitda.iloc[-1] if _f(ebitda.iloc[-1], 0) > 0 else np.nan
    if len(pairs) >= 2:
        multiple, source_multiple = float(np.median([p["ve_ebe"] for p in pairs])), "médiane des concurrents"
    elif pd.notna(multiple_propre):
        multiple, source_multiple = float(multiple_propre), "multiple actuel de l'entreprise"
    else:
        multiple, source_multiple = 10.0, "valeur standard"
    multiple = round(float(np.clip(multiple, 4, 30)), 1)

    res = {
        "ticker": ticker, "nom": info.get("longName") or info.get("shortName") or ticker,
        "secteur": info.get("sector") or "", "devise_compta": devise_compta, "devise_cours": devise_cours,
        "fx": fx, "cours": cours, "historique": hist, "derniere_annee": int(an), "ca_dernier": _f(ca.iloc[-1]),
        "consensus": consensus, "tcam_ca": _f(tcam), "dette": dette, "tresorerie": tresorerie,
        "minoritaires": minoritaires, "actions": actions, "dilution": dilution, "actions_diluees": actions_diluees,
        "ve_actuelle": ve_actuelle, "beta_brut": _f(beta_brut), "multiple_actuel": _f(multiple_propre), "pairs": pairs,
        "source_multiple": source_multiple,
        "defauts": {
            "croissance": [round(x, 4) for x in trajectoire],
            "marge_ebitda": [round(marge, 4)] * HORIZON, "da_ca": [round(da_ca, 4)] * HORIZON,
            "capex_ca": [round(capex_ca, 4)] * HORIZON, "bfr_ca": round(bfr_ca, 4), "taux_is": round(taux_is, 4),
            "rf": TAUX_SANS_RISQUE, "prime": PRIME_RISQUE, "beta": round(beta, 2), "kd": round(kd, 4),
            "poids_cp": round(poids_cp, 3), "g_inf": G_INF, "multiple_sortie": multiple, "methode_vt": "gordon",
            "demi_annee": False,
            "scenarios": {"pessimiste": {"dg": -0.03, "dm": -0.02, "p": 0.25},
                          "optimiste": {"dg": 0.03, "dm": 0.02, "p": 0.25}},
        },
    }
    with _verrou:
        _cache[ticker] = (time.time(), res)
    return res


# ---------------------------------------------------------------------------
# 2. Le modèle
# ---------------------------------------------------------------------------
def nettoyer(h: dict, defauts: dict) -> dict:
    """Hypothèses reçues de la page, complétées par les valeurs par défaut et bornées."""
    r = copy.deepcopy(defauts)
    for k in ("croissance", "marge_ebitda", "da_ca", "capex_ca"):
        v = h.get(k)
        if isinstance(v, list) and len(v) == HORIZON:
            r[k] = [float(np.clip(_f(x, r[k][i]), -0.9, 5)) for i, x in enumerate(v)]
    bornes = {"bfr_ca": (-1, 2), "taux_is": (0, 0.6), "rf": (-0.02, 0.2), "prime": (0, 0.2), "beta": (0, 4),
              "kd": (0, 0.3), "poids_cp": (0.05, 1), "g_inf": (-0.05, 0.1), "multiple_sortie": (0.5, 100)}
    for k, (lo, hi) in bornes.items():
        if k in h:
            r[k] = float(np.clip(_f(h[k], r[k]), lo, hi))
    if h.get("methode_vt") in ("gordon", "multiple", "moyenne"):
        r["methode_vt"] = h["methode_vt"]
    r["demi_annee"] = bool(h.get("demi_annee", r["demi_annee"]))
    sc = h.get("scenarios") or {}
    for nom in ("pessimiste", "optimiste"):
        for k, (lo, hi) in {"dg": (-0.5, 0.5), "dm": (-0.5, 0.5), "p": (0, 1)}.items():
            if nom in sc and k in sc[nom]:
                r["scenarios"][nom][k] = float(np.clip(_f(sc[nom][k], r["scenarios"][nom][k]), lo, hi))
    return r


def cmpc(h: dict) -> float:
    kcp = h["rf"] + h["beta"] * h["prime"]
    return h["poids_cp"] * kcp + (1 - h["poids_cp"]) * h["kd"] * (1 - h["taux_is"])


def modele(ctx: dict, h: dict, details: bool = True) -> dict:
    """Projection, actualisation et valeur par action pour un jeu d'hypothèses."""
    w, g, N = cmpc(h), h["g_inf"], HORIZON
    ca_prec, lignes = ctx["ca_dernier"], []
    for t in range(1, N + 1):
        i = t - 1
        ca = ca_prec * (1 + h["croissance"][i])
        ebitda = ca * h["marge_ebitda"][i]
        da = ca * h["da_ca"][i]
        ebit = ebitda - da
        impot = max(ebit, 0) * h["taux_is"]
        capex = ca * h["capex_ca"][i]
        dbfr = h["bfr_ca"] * (ca - ca_prec)
        fcff = ebitda - impot - capex - dbfr
        facteur = 1 / (1 + w) ** (t - 0.5 * h["demi_annee"])
        lignes.append({"annee": ctx["derniere_annee"] + t, "ca": ca, "croissance": h["croissance"][i], "ebitda": ebitda,
                       "marge_ebitda": h["marge_ebitda"][i], "da": da, "da_ca": h["da_ca"][i], "ebit": ebit,
                       "impot": impot, "nopat": ebit - impot, "capex": capex, "capex_ca": h["capex_ca"][i],
                       "dbfr": dbfr, "fcff": fcff, "facteur": facteur, "fcff_actualise": fcff * facteur})
        ca_prec = ca
    somme = sum(l["fcff_actualise"] for l in lignes)
    der = lignes[-1]
    vt_gordon = der["fcff"] * (1 + g) / (w - g) if w > g else np.nan
    vt_multiple = der["ebitda"] * h["multiple_sortie"]
    vt = {"gordon": vt_gordon, "multiple": vt_multiple,
          "moyenne": np.nanmean([vt_gordon, vt_multiple]) if pd.notna(vt_gordon) else vt_multiple}[h["methode_vt"]]
    vt_act = vt / (1 + w) ** N
    ve = somme + vt_act
    vcp = ve - ctx["dette"] + ctx["tresorerie"] - ctx["minoritaires"]
    valeur = vcp / ctx["actions_diluees"] * ctx["fx"] if ctx["actions_diluees"] else np.nan
    r = {"cmpc": w, "valeur_action": valeur, "potentiel": valeur / ctx["cours"] - 1 if pd.notna(valeur) else np.nan}
    if not details:
        return r
    # Ce que chaque méthode suppose de l'autre (cohérence de la valeur terminale)
    multiple_implicite = vt_gordon / der["ebitda"] if pd.notna(vt_gordon) and der["ebitda"] > 0 else np.nan
    g_implicite = (vt_multiple * w - der["fcff"]) / (vt_multiple + der["fcff"]) if vt_multiple + der["fcff"] else np.nan
    r.update({
        "kcp": h["rf"] + h["beta"] * h["prime"], "projections": lignes, "somme_fcff_actualises": somme,
        "vt_gordon": vt_gordon, "vt_multiple": vt_multiple, "vt": vt, "vt_actualisee": vt_act,
        "vt_gordon_actualisee": vt_gordon / (1 + w) ** N if pd.notna(vt_gordon) else np.nan,
        "vt_multiple_actualisee": vt_multiple / (1 + w) ** N,
        "multiple_implicite": multiple_implicite, "g_implicite": g_implicite,
        "valeur_entreprise": ve, "valeur_capitaux_propres": vcp, "part_vt": vt_act / ve if ve else np.nan,
        "valeur_gordon": _valeur_vt(ctx, somme, vt_gordon, w), "valeur_multiple": _valeur_vt(ctx, somme, vt_multiple, w),
    })
    return r


def _valeur_vt(ctx, somme, vt, w):
    if pd.isna(vt):
        return np.nan
    vcp = somme + vt / (1 + w) ** HORIZON - ctx["dette"] + ctx["tresorerie"] - ctx["minoritaires"]
    return vcp / ctx["actions_diluees"] * ctx["fx"]


def scenario(h: dict, dg: float, dm: float) -> dict:
    s = copy.deepcopy(h)
    s["croissance"] = [x + dg for x in h["croissance"]]
    s["marge_ebitda"] = [max(x + dm, -0.5) for x in h["marge_ebitda"]]
    return s


def dcf_inverse(ctx: dict, h: dict):
    """Croissance annuelle constante du CA, sur 5 ans, qui donne une valeur égale au cours."""
    def ecart(g):
        s = copy.deepcopy(h)
        s["croissance"] = [g] * HORIZON
        return modele(ctx, s, details=False)["valeur_action"] - ctx["cours"]
    try:
        bas, haut = ecart(-0.5), ecart(1.5)
        if pd.isna(bas) or pd.isna(haut) or bas * haut > 0:
            return None
        return brentq(ecart, -0.5, 1.5, xtol=1e-5)
    except Exception:
        return None


def calcul(ticker: str, hypotheses: dict = None) -> dict:
    ctx = donnees(ticker)
    h = nettoyer(hypotheses or {}, ctx["defauts"])
    if cmpc(h) <= h["g_inf"] and h["methode_vt"] != "multiple":
        raise ValueError("Le CMPC doit être supérieur à la croissance à l'infini, sinon la formule de Gordon-Shapiro "
                         "donne une valeur infinie. Baisse g ou augmente le CMPC.")
    m = modele(ctx, h)

    # Scénarios
    p_pess, p_opt = h["scenarios"]["pessimiste"]["p"], h["scenarios"]["optimiste"]["p"]
    if p_pess + p_opt > 1:
        p_pess, p_opt = p_pess / (p_pess + p_opt), p_opt / (p_pess + p_opt)
    scen = []
    for nom, dg, dm, p in (("Pessimiste", h["scenarios"]["pessimiste"]["dg"], h["scenarios"]["pessimiste"]["dm"], p_pess),
                           ("Central", 0.0, 0.0, 1 - p_pess - p_opt),
                           ("Optimiste", h["scenarios"]["optimiste"]["dg"], h["scenarios"]["optimiste"]["dm"], p_opt)):
        r = modele(ctx, scenario(h, dg, dm), details=False) if (dg or dm) else m
        scen.append({"nom": nom, "dg": dg, "dm": dm, "p": p, "valeur_action": r["valeur_action"], "potentiel": r["potentiel"]})
    vals = [(s["valeur_action"], s["p"]) for s in scen if pd.notna(s["valeur_action"])]
    pondere = sum(v * p for v, p in vals) / sum(p for _, p in vals) if vals and sum(p for _, p in vals) else np.nan

    # DCF inversé
    g_marche = dcf_inverse(ctx, h)
    g_moyenne = float(np.prod([1 + x for x in h["croissance"]]) ** (1 / HORIZON) - 1)

    # Sensibilités
    w = m["cmpc"]
    pas_w = [w - 0.01, w - 0.005, w, w + 0.005, w + 0.01]

    def avec(**k):
        s = copy.deepcopy(h)
        s.update(k)
        return s

    def valeur_w(s, wcible):
        # On fait varier le CMPC en déplaçant le coût des capitaux propres (prime de risque)
        delta = (wcible - cmpc(s)) / s["poids_cp"]
        return modele(ctx, avec(**{**s, "prime": s["prime"] + delta / max(s["beta"], 1e-6)}), details=False)["valeur_action"]

    gs = [h["g_inf"] - 0.01, h["g_inf"] - 0.005, h["g_inf"], h["g_inf"] + 0.005, h["g_inf"] + 0.01]
    mults = [h["multiple_sortie"] + d for d in (-4, -2, 0, 2, 4) if h["multiple_sortie"] + d > 0]
    sens_g = [[valeur_w(avec(g_inf=gg, methode_vt="gordon"), ww) if ww > gg else None for gg in gs] for ww in pas_w]
    sens_m = [[valeur_w(avec(multiple_sortie=mm, methode_vt="multiple"), ww) for mm in mults] for ww in pas_w]

    res = {"ticker": ticker, "nom": ctx["nom"], "contexte": {k: v for k, v in ctx.items() if k != "defauts"},
           "defauts": ctx["defauts"], "hypotheses": h, "resultat": m, "scenarios": scen, "valeur_ponderee": pondere,
           "potentiel_pondere": pondere / ctx["cours"] - 1 if pd.notna(pondere) else np.nan,
           "g_marche": g_marche, "g_modele": g_moyenne,
           "sensibilite_gordon": {"lignes": pas_w, "colonnes": gs, "valeurs": sens_g},
           "sensibilite_multiple": {"lignes": pas_w, "colonnes": mults, "valeurs": sens_m}}
    res["lecture"] = lecture(res)
    return _propre(res)


def _propre(x):
    """NaN → None pour le JSON."""
    if isinstance(x, dict):
        return {k: _propre(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_propre(v) for v in x]
    if isinstance(x, (float, np.floating)):
        return None if not math.isfinite(float(x)) else float(x)
    if isinstance(x, np.integer):
        return int(x)
    return x


# ---------------------------------------------------------------------------
# 3. Lecture pour débutants
# ---------------------------------------------------------------------------
def _p(x, d=1):
    return (f"{x * 100:+.{d}f} %" if x is not None else "—").replace(".", ",").replace("-", "−")


def _pp(x, d=1):
    return (f"{x * 100:.{d}f} %" if x is not None else "—").replace(".", ",").replace("-", "−")


def _n(x, d=2):
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",").replace("-", "−")


def lecture(r: dict) -> list:
    ctx, m, h = r["contexte"], r["resultat"], r["hypotheses"]
    dev = ctx["devise_cours"]
    phrases = []
    v, pot = m["valeur_action"], m["potentiel"]
    if v is not None and v <= 0:
        phrases.append("<b>Valeur négative</b> : avec ces hypothèses, les flux de trésorerie restent négatifs (l'entreprise "
                       "consomme plus d'argent qu'elle n'en produit). Un DCF n'a de sens que si l'entreprise devient rentable : "
                       "augmente la marge d'EBITDA des années 3 à 5 vers celle des concurrents rentables, ou baisse les investissements.")
    elif v is not None and pd.notna(v):
        sens_ = "au-dessus" if pot > 0 else "en dessous"
        phrases.append(f"Avec ces hypothèses, l'action vaut <b>{_n(v)} {dev}</b>, soit {_p(pot)} par rapport au cours de "
                       f"{_n(ctx['cours'])} {dev} : la valeur estimée est {sens_} du prix de marché.")
    if r["g_marche"] is not None:
        g_m, g_mod = r["g_marche"], r["g_modele"]
        compar = ("plus optimiste que ton modèle" if g_m > g_mod + 0.01 else
                  "plus prudent que ton modèle" if g_m < g_mod - 0.01 else "proche de ton modèle")
        phrases.append(f"<b>DCF inversé</b> : pour justifier le cours actuel, le chiffre d'affaires doit croître de "
                       f"<b>{_pp(g_m)} par an</b> pendant {HORIZON} ans (à marges et CMPC inchangés). Ton modèle suppose "
                       f"{_pp(g_mod)} par an en moyenne : le marché est {compar}.")
    else:
        phrases.append("DCF inversé : aucune croissance raisonnable (entre −50 % et +150 % par an) ne permet de retrouver "
                       "le cours avec ces marges et ce CMPC.")
    if m["cmpc"] < 0.06:
        phrases.append(f"Attention : un CMPC de {_pp(m['cmpc'], 2)} est très bas (la plupart des grandes entreprises sont entre "
                       "6 et 10 %). Plus le taux d'actualisation est faible, plus la valeur est élevée : vérifie le bêta et la prime de risque.")
    pv = m.get("part_vt")
    if pv is not None:
        phrases.append(f"La valeur terminale pèse <b>{_pp(pv, 0)}</b> de la valeur d'entreprise : "
                       + ("l'essentiel de la valeur vient d'après l'année 5, le résultat dépend donc beaucoup de g, du CMPC "
                          "ou du multiple de sortie." if pv > 0.7 else "c'est un niveau habituel pour un DCF à 5 ans."))
    mi, gi = m.get("multiple_implicite"), m.get("g_implicite")
    if mi is not None and gi is not None:
        phrases.append(f"Cohérence des deux méthodes : la formule de Gordon (g = {_pp(h['g_inf'])}) revient à revendre "
                       f"l'entreprise à <b>{_n(mi, 1)} fois son EBITDA</b> en année {HORIZON} ; à l'inverse, un multiple de "
                       f"sortie de {_n(h['multiple_sortie'], 1)} suppose une croissance à l'infini de <b>{_pp(gi)}</b>. "
                       + ("Un g implicite au-dessus de 3-4 % est irréaliste à très long terme (au-delà de la croissance "
                          "de l'économie)." if gi > 0.04 else ""))
    if r["valeur_ponderee"] is not None:
        phrases.append(f"En pondérant les trois scénarios, la valeur ressort à <b>{_n(r['valeur_ponderee'])} {dev}</b> "
                       f"({_p(r['potentiel_pondere'])}).")
    return phrases


if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    r = calcul(t)
    c, m = r["contexte"], r["resultat"]
    print(r["nom"], "| cours", round(c["cours"], 2), c["devise_cours"], "| CMPC", round(m["cmpc"], 4))
    for l in m["projections"]:
        print(f"  {l['annee']}  CA {l['ca']/1e9:8.1f}  g {l['croissance']:+.3f}  EBITDA {l['ebitda']/1e9:7.1f}  "
              f"FCFF {l['fcff']/1e9:7.1f}  act {l['fcff_actualise']/1e9:7.1f}")
    print("VE", round(m["valeur_entreprise"] / 1e9, 1), "| valeur/action", round(m["valeur_action"], 2),
          "| potentiel", round(m["potentiel"], 3), "| part VT", round(m["part_vt"], 2))
    print("Gordon", round(m["valeur_gordon"], 2), "| multiple", round(m["valeur_multiple"], 2), "x", r["hypotheses"]["multiple_sortie"],
          c["source_multiple"], [p["ticker"] for p in c["pairs"]])
    print("scénarios", [(s["nom"], round(s["valeur_action"], 1)) for s in r["scenarios"]], "| pondérée", round(r["valeur_ponderee"], 1))
    print("g marché", r["g_marche"], "| g modèle", round(r["g_modele"], 4))
    print(*r["lecture"], sep="\n")


# ---------------------------------------------------------------------------
# 4. Export Excel : le modèle avec de vraies formules
# ---------------------------------------------------------------------------
def classeur(r: dict) -> bytes:
    """Classeur Excel : feuille « Modèle DCF » entièrement en formules (les cellules bleues sont
    les hypothèses, modifiables), plus l'historique, les scénarios et les sensibilités."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter as col

    ctx, h, m = r["contexte"], r["hypotheses"], r["resultat"]
    dev, devc = ctx["devise_compta"], ctx["devise_cours"]
    MD = f'#,##0.0,,," Md {dev}"'.replace("Md ", "Md ")
    PCT, X, NB = "0.0%", '0.0"x"', "#,##0.00"
    BLEU_TXT = Font(color="1F4FBF")                     # convention des banques : hypothèses en bleu
    ENTREE = PatternFill("solid", fgColor="EAF1FF")
    TITRE = Font(bold=True, size=14, color="1F2A44")
    ENTETE = PatternFill("solid", fgColor="1F2A44")
    GRAS = Font(bold=True)
    fin = Side(style="thin", color="C9CED8")

    wb = Workbook()
    ws = wb.active
    ws.title = "Modèle DCF"
    ws["A1"] = f"Modèle DCF — {r['nom']} ({r['ticker']})"
    ws["A1"].font = TITRE
    ws["A2"] = (f"Montants en milliards de {dev}. Cellules bleues = hypothèses : modifie-les, tout se recalcule. "
                "Généré par Analyse Actions (outil pédagogique, pas un conseil en investissement).")
    ws["A2"].font = Font(italic=True, size=9, color="6B6B6B")

    def entree(cellule, valeur, fmt):
        ws[cellule] = valeur
        ws[cellule].font, ws[cellule].fill, ws[cellule].number_format = BLEU_TXT, ENTREE, fmt

    # --- Paramètres (colonnes A-B)
    params = [
        (4, "Cours de bourse (" + devc + ")", ctx["cours"], NB, True),
        (5, "Taux sans risque", h["rf"], PCT, True),
        (6, "Prime de risque du marché", h["prime"], PCT, True),
        (7, "Bêta", h["beta"], "0.00", True),
        (8, "Coût de la dette (avant impôt)", h["kd"], PCT, True),
        (9, "Taux d'impôt", h["taux_is"], PCT, True),
        (10, "Poids des capitaux propres", h["poids_cp"], PCT, True),
        (11, "Coût des capitaux propres = rf + β × prime", "=B5+B7*B6", PCT, False),
        (12, "CMPC (WACC)", "=B10*B11+(1-B10)*B8*(1-B9)", PCT, False),
        (13, "Croissance à l'infini (g)", h["g_inf"], PCT, True),
        (14, "Multiple de sortie (VE / EBITDA)", h["multiple_sortie"], X, True),
        (15, "BFR en % du CA", h["bfr_ca"], PCT, True),
        (16, "Convention de demi-année (1 = oui)", 1 if h["demi_annee"] else 0, "0", True),
        (17, f"Taux de change ({dev} → {devc})", ctx["fx"], "0.0000", False),
    ]
    for ligne, lib, val, fmt, est_entree in params:
        ws[f"A{ligne}"] = lib
        if est_entree:
            entree(f"B{ligne}", val, fmt)
        else:
            ws[f"B{ligne}"] = val
            ws[f"B{ligne}"].number_format = fmt
    ws["B12"].font = GRAS

    # --- Projection (ligne 20 : en-têtes ; C = dernier exercice publié, D à H = années 1 à 5)
    L0 = 20
    ws[f"A{L0}"] = "Projection"
    ws[f"C{L0}"] = f"{ctx['derniere_annee']} (publié)"
    for t in range(1, HORIZON + 1):
        ws[f"{col(3 + t)}{L0}"] = f"{ctx['derniere_annee'] + t} (an {t})"
    for c in range(1, 4 + HORIZON):
        cel = ws.cell(row=L0, column=c)
        cel.font, cel.fill, cel.alignment = Font(bold=True, color="FFFFFF"), ENTETE, Alignment(horizontal="center")
    lib = {1: "Croissance du CA", 2: "Chiffre d'affaires", 3: "Marge d'EBITDA", 4: "EBITDA (EBE)",
           5: "Amortissements en % du CA", 6: "Dotations aux amortissements", 7: "EBIT (résultat d'exploitation)",
           8: "Impôt sur l'EBIT", 9: "Investissements en % du CA", 10: "Investissements (capex)",
           11: "Variation du BFR", 12: "FCFF (flux disponible)", 13: "Période d'actualisation",
           14: "Facteur d'actualisation", 15: "FCFF actualisé"}
    R = {k: L0 + k for k in lib}
    for k, texte in lib.items():
        ws[f"A{R[k]}"] = texte
    for k in (12, 15):
        ws[f"A{R[k]}"].font = GRAS
    ws[f"C{R[2]}"] = ctx["ca_dernier"]
    ws[f"C{R[2]}"].number_format = MD
    for t in range(1, HORIZON + 1):
        c, p, i = col(3 + t), col(2 + t), t - 1
        entree(f"{c}{R[1]}", h["croissance"][i], PCT)
        ws[f"{c}{R[2]}"] = f"={p}{R[2]}*(1+{c}{R[1]})"
        entree(f"{c}{R[3]}", h["marge_ebitda"][i], PCT)
        ws[f"{c}{R[4]}"] = f"={c}{R[2]}*{c}{R[3]}"
        entree(f"{c}{R[5]}", h["da_ca"][i], PCT)
        ws[f"{c}{R[6]}"] = f"=-{c}{R[2]}*{c}{R[5]}"
        ws[f"{c}{R[7]}"] = f"={c}{R[4]}+{c}{R[6]}"
        ws[f"{c}{R[8]}"] = f"=-MAX({c}{R[7]},0)*$B$9"
        entree(f"{c}{R[9]}", h["capex_ca"][i], PCT)
        ws[f"{c}{R[10]}"] = f"=-{c}{R[2]}*{c}{R[9]}"
        ws[f"{c}{R[11]}"] = f"=-$B$15*({c}{R[2]}-{p}{R[2]})"
        ws[f"{c}{R[12]}"] = f"={c}{R[4]}+{c}{R[8]}+{c}{R[10]}+{c}{R[11]}"
        ws[f"{c}{R[13]}"] = f"={t}-0.5*$B$16"
        ws[f"{c}{R[14]}"] = f"=1/(1+$B$12)^{c}{R[13]}"
        ws[f"{c}{R[15]}"] = f"={c}{R[12]}*{c}{R[14]}"
        for k in (2, 4, 6, 7, 8, 10, 11, 12, 15):
            ws[f"{c}{R[k]}"].number_format = MD
        ws[f"{c}{R[13]}"].number_format = "0.0"
        ws[f"{c}{R[14]}"].number_format = "0.000"
        for k in (12, 15):
            ws[f"{c}{R[k]}"].font = GRAS
            ws[f"{c}{R[k]}"].border = Border(top=fin)

    # --- Valorisation
    D, Hc = col(4), col(3 + HORIZON)
    V0 = R[15] + 2
    choix = {"gordon": f"=B{V0 + 1}", "multiple": f"=B{V0 + 2}", "moyenne": f"=AVERAGE(B{V0 + 1},B{V0 + 2})"}[h["methode_vt"]]
    nom_methode = {"gordon": "Gordon-Shapiro", "multiple": "multiple de sortie", "moyenne": "moyenne des deux"}[h["methode_vt"]]
    lignes_v = [
        ("Somme des FCFF actualisés", f"=SUM({D}{R[15]}:{Hc}{R[15]})", MD),
        ("Valeur terminale — Gordon-Shapiro : FCFF(N) × (1+g) / (CMPC − g)", f"={Hc}{R[12]}*(1+B13)/(B12-B13)", MD),
        ("Valeur terminale — multiple de sortie : EBITDA(N) × multiple", f"={Hc}{R[4]}*B14", MD),
        (f"Valeur terminale retenue ({nom_methode})", choix, MD),
        ("Valeur terminale actualisée", f"=B{V0 + 3}/(1+B12)^{HORIZON}", MD),
        ("= Valeur d'entreprise (VE)", f"=B{V0}+B{V0 + 4}", MD),
        ("− Dette financière (y c. dettes de location)", ctx["dette"], MD),
        ("+ Trésorerie et placements", ctx["tresorerie"], MD),
        ("− Intérêts minoritaires", ctx["minoritaires"], MD),
        ("= Valeur des capitaux propres", f"=B{V0 + 5}-B{V0 + 6}+B{V0 + 7}-B{V0 + 8}", MD),
        ("Nombre d'actions dilué (millions)", ctx["actions_diluees"] / 1e6, "#,##0.0"),
        (f"Valeur par action ({devc})", f"=B{V0 + 9}/(B{V0 + 10}*1000000)*B17", NB),
        ("Potentiel par rapport au cours", f"=B{V0 + 11}/B4-1", "+0.0%;-0.0%"),
        ("Part de la valeur terminale dans la VE", f"=B{V0 + 4}/B{V0 + 5}", PCT),
        ("Multiple implicite de la méthode de Gordon", f"=B{V0 + 1}/{Hc}{R[4]}", X),
    ]
    ws[f"A{V0 - 1}"] = "Valorisation"
    ws[f"A{V0 - 1}"].font = Font(bold=True, size=12, color="1F2A44")
    for j, (texte, formule, fmt) in enumerate(lignes_v):
        ws[f"A{V0 + j}"] = texte
        ws[f"B{V0 + j}"] = formule
        ws[f"B{V0 + j}"].number_format = fmt
        if texte.startswith("=") or "Valeur par action" in texte:
            ws[f"A{V0 + j}"].font = ws[f"B{V0 + j}"].font = GRAS
    ws.column_dimensions["A"].width = 58
    for c in range(2, 4 + HORIZON):
        ws.column_dimensions[col(c)].width = 16
    ws.freeze_panes = "B4"

    # --- Historique
    hs = wb.create_sheet("Historique")
    hs["A1"] = "Comptes publiés (Yahoo Finance)"
    hs["A1"].font = TITRE
    champs = [("Chiffre d'affaires", "ca", MD), ("Croissance", "croissance", PCT), ("EBITDA", "ebitda", MD),
              ("Marge d'EBITDA", "marge_ebitda", PCT), ("Amortissements en % du CA", "da_ca", PCT),
              ("Investissements en % du CA", "capex_ca", PCT), ("BFR en % du CA", "bfr_ca", PCT),
              ("Taux d'impôt effectif", "taux_is", PCT)]
    for j, a in enumerate(ctx["historique"]):
        hs.cell(row=3, column=2 + j, value=a["annee"]).font = GRAS
    for i, (texte, k, fmt) in enumerate(champs):
        hs.cell(row=4 + i, column=1, value=texte)
        for j, a in enumerate(ctx["historique"]):
            c = hs.cell(row=4 + i, column=2 + j, value=a.get(k))
            c.number_format = fmt
    hs.column_dimensions["A"].width = 32

    # --- Scénarios et sensibilités (valeurs calculées par l'application)
    ss = wb.create_sheet("Scénarios et sensibilité")
    ss["A1"] = "Scénarios (écarts appliqués à chaque année du scénario central)"
    ss["A1"].font = TITRE
    for j, t in enumerate(["Scénario", "Écart de croissance", "Écart de marge", "Probabilité", f"Valeur par action ({devc})", "Potentiel"]):
        ss.cell(row=3, column=1 + j, value=t).font = GRAS
    for i, s in enumerate(r["scenarios"]):
        for j, (v, fmt) in enumerate([(s["nom"], None), (s["dg"], "+0.0%;-0.0%;0.0%"), (s["dm"], "+0.0%;-0.0%;0.0%"),
                                      (s["p"], "0%"), (s["valeur_action"], NB), (s["potentiel"], "+0.0%;-0.0%")]):
            c = ss.cell(row=4 + i, column=1 + j, value=v)
            if fmt:
                c.number_format = fmt
    ss.cell(row=7, column=1, value="Valeur pondérée").font = GRAS
    ss.cell(row=7, column=5, value="=SUMPRODUCT(D4:D6,E4:E6)/SUM(D4:D6)").number_format = NB

    def table(debut, titre, sens, fmt_col):
        ss.cell(row=debut, column=1, value=titre).font = Font(bold=True, size=12)
        ss.cell(row=debut + 1, column=1, value="CMPC ↓").font = GRAS
        for j, x in enumerate(sens["colonnes"]):
            c = ss.cell(row=debut + 1, column=2 + j, value=x)
            c.number_format, c.font = fmt_col, GRAS
        for i, w in enumerate(sens["lignes"]):
            ss.cell(row=debut + 2 + i, column=1, value=w).number_format = PCT
            for j, v in enumerate(sens["valeurs"][i]):
                ss.cell(row=debut + 2 + i, column=2 + j, value=v).number_format = NB
    table(10, f"Valeur par action ({devc}) selon le CMPC et la croissance à l'infini (Gordon)", r["sensibilite_gordon"], PCT)
    table(19, f"Valeur par action ({devc}) selon le CMPC et le multiple de sortie", r["sensibilite_multiple"], X)
    ss.column_dimensions["A"].width = 22
    for c in range(2, 8):
        ss.column_dimensions[col(c)].width = 18

    sortie = io.BytesIO()
    wb.save(sortie)
    return sortie.getvalue()
