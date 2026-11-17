"""
NOTE D'ANALYSE — La synthèse d'une page des analystes « sell-side », version pédagogique
=======================================================================================

À partir de l'analyse complète d'une action :
  - FOURCHETTES DE VALEUR par plusieurs méthodes, réunies dans un graphique « football field »
    (le graphique le plus utilisé en banque d'affaires) : DCF (scénarios et sensibilité),
    multiples des comparables (PER, VE/EBITDA), objectifs des analystes, plus bas / plus haut
    sur 52 semaines ;
  - un VERDICT sur la valorisation (décotée / en ligne / exigeante) et une thèse rédigée ;
  - les CATALYSEURS à venir (résultats, dividende, actualité) et les RISQUES principaux ;
  - les CHIFFRES CLÉS, chacun avec sa formule appliquée aux vrais chiffres de l'entreprise,
    son échelle de lecture et son RANG DANS LE SECTEUR (≈ 1 350 entreprises).

Lecture pédagogique des chiffres : ce n'est pas un conseil d'investissement.
"""

import datetime as dt
import html
import json
import math
import re

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

SEUIL_DECOTE = 0.15          # potentiel au-delà duquel on parle de décote (en deçà : surévaluation)
NB_ANALYSTES = "Nombre d'analystes"


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------
def _f(x):
    try:
        x = float(x)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _der(df, col):
    try:
        s = df[col].dropna()
        return _f(s.iloc[-1]) if len(s) else None
    except Exception:
        return None


def nb(x, d=1):
    return "—" if x is None else f"{x:,.{d}f}".replace(",", " ").replace(".", ",").replace("-", "−")


def pc(x, d=1, signe=False):
    if x is None:
        return "—"
    t = f"{x * 100:{'+' if signe else ''}.{d}f} %".replace(".", ",").replace("-", "−")
    return t


def md(x):
    return "—" if x is None else nb(x / 1e9, 1) + " Md"


def _quantiles(valeurs, bas, haut):
    v = sorted(x for x in valeurs if x is not None)
    if len(v) < 3:
        return None
    return float(np.percentile(v, bas)), float(np.median(v)), float(np.percentile(v, haut))


# ---------------------------------------------------------------------------
# 1. Rang dans le secteur
# ---------------------------------------------------------------------------
BORNES = {"per": (0, 200), "ve_ebe": (0, 100), "levier": (-10, 30), "roe": (-2, 3), "marge_nette": (-2, 1),
          "rdt_div": (0, 0.25), "croissance_ca": (-0.9, 3), "beta": (-1, 4), "marge_op": (-2, 1)}


def rang(cible: dict, pairs: list, champ: str, plus_haut_mieux: bool):
    """Position de l'entreprise parmi celles de son secteur (mêmes définitions Yahoo pour toutes)."""
    if not cible or cible.get(champ) is None:
        return None
    lo, hi = BORNES.get(champ, (-1e18, 1e18))
    v = [p[champ] for p in pairs if p.get(champ) is not None and lo < p[champ] < hi]
    x = cible[champ]
    if len(v) < 5 or not (lo < x < hi):
        return None
    dessous = sum(y < x for y in v) / len(v)
    return {"valeur": x, "mediane": float(np.median(v)), "n": len(v),
            "centile": dessous, "meilleur_que": dessous if plus_haut_mieux else 1 - dessous,
            "plus_haut_mieux": plus_haut_mieux}


# ---------------------------------------------------------------------------
# 2. Construction de la note
# ---------------------------------------------------------------------------
def construire(a: dict) -> dict:
    import base_fondamentale
    import dcf_avance

    t = a["ticker"]
    prix = a["prix"]
    cours = float(prix.iloc[-1])
    devise = a["infos"].get("Devise") or ""
    fin, val = a.get("fin") or {}, a.get("val") or {}

    # --- Base sectorielle
    try:
        base = base_fondamentale.charger(reconstruire_si_perimee=False) or []
    except Exception:
        base = []
    cible = next((x for x in base if x["ticker"] == t), None)
    if cible is None:
        try:
            action = next((x for x in base_fondamentale.univers() if x["ticker"] == t), {"ticker": t, "nom": t, "place": ""})
            cible = base_fondamentale._fiche(action, base_fondamentale.TauxVersEuro())
        except Exception:
            cible = None
    secteur = (cible or {}).get("secteur") or a["infos"].get("Secteur") or ""
    pairs_secteur = [x for x in base if x.get("secteur") == secteur and x["ticker"] != t] if secteur else []
    try:
        comparables = base_fondamentale.concurrents(t, n=8)
    except Exception:
        comparables = []
    try:
        date_base = dt.date.fromtimestamp(json.loads(base_fondamentale.FICHIER.read_text(encoding="utf-8"))["date"])
    except Exception:
        date_base = None

    # --- DCF avancé (hypothèses par défaut)
    try:
        d = dcf_avance.calcul(t)
    except Exception:
        d = None

    fourchettes = []

    def ajouter(methode, bas, centre, haut, famille, detail, vote=True):
        vals = [x for x in (bas, centre, haut) if x is not None]
        if len(vals) < 2 or min(vals) <= 0:
            return
        fourchettes.append({"methode": methode, "bas": min(vals), "centre": centre if centre is not None else float(np.mean(vals)),
                            "haut": max(vals), "famille": famille, "detail": detail, "vote": vote and famille == "fondamentale"})

    if d:
        sc = {s["nom"]: s["valeur_action"] for s in d["scenarios"]}
        ajouter("DCF : scénarios", sc.get("Pessimiste"), sc.get("Central"), sc.get("Optimiste"), "fondamentale",
                "Flux de trésorerie actualisés : scénario pessimiste, central et optimiste (croissance et marge ± points).")
        sg = d["sensibilite_gordon"]["valeurs"]
        coeur = [v for ligne in sg[1:4] for v in ligne[1:4] if v is not None]
        if coeur:
            ajouter("DCF : sensibilité CMPC et g", min(coeur), d["resultat"]["valeur_action"], max(coeur), "fondamentale",
                    "Scénario central avec un CMPC à ± 0,5 point et une croissance à l'infini à ± 0,5 point.", vote=False)

    # Multiples des comparables
    per_cible = _f((cible or {}).get("per")) or _f(a["infos"].get("PER"))
    if per_cible and per_cible > 0 and comparables:
        bpa = cours / per_cible
        q = _quantiles([c["per"] for c in comparables if c.get("per") and 3 < c["per"] < 80], 25, 75)
        if q:
            ajouter("Comparables : PER", q[0] * bpa, q[1] * bpa, q[2] * bpa, "fondamentale",
                    f"Bénéfice par action ({nb(bpa, 2)} {devise}) × PER des comparables (1er quartile, médiane, 3e quartile : "
                    f"{nb(q[0])}, {nb(q[1])}, {nb(q[2])}).")
    if d and comparables:
        c = d["contexte"]
        ebitda = _f(c["historique"][-1].get("ebitda"))
        q = _quantiles([x["ve_ebe"] for x in comparables if x.get("ve_ebe") and 2 < x["ve_ebe"] < 40], 25, 75)
        if q and ebitda and ebitda > 0:
            par = lambda m: (m * ebitda - c["dette"] + c["tresorerie"] - c["minoritaires"]) / c["actions_diluees"] * c["fx"]
            ajouter("Comparables : VE / EBITDA", par(q[0]), par(q[1]), par(q[2]), "fondamentale",
                    f"EBITDA × multiple des comparables ({nb(q[0])}, {nb(q[1])}, {nb(q[2])}), moins la dette nette, "
                    "divisé par le nombre d'actions.")
    cons = val.get("consensus") or {}
    if cons.get("Objectif de cours moyen"):
        ajouter("Objectifs des analystes", _f(cons.get("Objectif bas")), _f(cons.get("Objectif de cours moyen")),
                _f(cons.get("Objectif haut")), "marche",
                f"Objectifs de cours à 12 mois de {cons.get(NB_ANALYSTES) or '?'} analystes (le plus bas, la moyenne, le plus haut).")
    an = prix[prix.index >= prix.index[-1] - pd.Timedelta(days=365)]
    ajouter("Plus bas / plus haut sur 52 semaines", float(an.min()), None, float(an.max()), "marche",
            "Ce que les investisseurs ont accepté de payer sur la dernière année : un repère, pas une valeur.")

    # Valeur centrale : moyenne des méthodes fondamentales
    # Valeur centrale : médiane des méthodes fondamentales indépendantes (le DCF ne vote qu'une fois)
    fond = [f["centre"] for f in fourchettes if f.get("vote") and f["centre"]]
    centrale = float(np.median(fond)) if fond else None
    potentiel = centrale / cours - 1 if centrale else None
    dessus = sum(1 for x in fond if x > cours)
    divergence = max(fond) / min(fond) if len(fond) >= 2 else None
    if potentiel is None:
        verdict, ton = "Valorisation non calculable", "neutre"
    elif divergence and divergence > 1.6 and min(fond) < cours < max(fond):
        verdict, ton = "Signaux contradictoires", "neutre"
    elif potentiel > SEUIL_DECOTE:
        verdict, ton = "Décotée", "pos"
    elif potentiel < -SEUIL_DECOTE:
        verdict, ton = "Valorisation exigeante", "neg"
    else:
        verdict, ton = "Correctement valorisée", "neutre"
    if len(fond) == 1 and potentiel is not None:
        verdict += " (une seule méthode)"
    for f in fourchettes:
        f["potentiel"] = f["centre"] / cours - 1 if f["centre"] else None

    chiffres = chiffres_cles(a, d, cible, pairs_secteur, secteur)
    note = {
        "ticker": t, "nom": a["infos"].get("Nom") or t, "secteur": secteur, "devise": devise, "cours": cours,
        "date_cours": str(prix.index[-1].date()), "fourchettes": fourchettes, "valeur_centrale": centrale,
        "potentiel": potentiel, "verdict": verdict, "ton": ton, "methodes_dessus": dessus,
        "methodes_fond": len(fond), "divergence": divergence, "comparables": [{"ticker": c["ticker"], "nom": c["nom"]} for c in comparables],
        "catalyseurs": catalyseurs(a), "risques": risques(a, d), "chiffres": chiffres,
        "annee_comptes": (fin.get("annees") or [None])[-1] if fin.get("applicable") else None,
        "analystes": cons.get(NB_ANALYSTES), "recommandation": cons.get("Recommandation"),
        "date_base": str(date_base) if date_base else None, "taille_base": len(base),
        "cmpc": d["resultat"]["cmpc"] if d else None, "g_marche": d["g_marche"] if d else None,
    }
    note["these"] = these(note, a, d)
    return note


# ---------------------------------------------------------------------------
# 3. Chiffres clés : formule avec les vrais chiffres, échelle de lecture, rang sectoriel
# ---------------------------------------------------------------------------
def chiffres_cles(a, d, cible, pairs, secteur) -> list:
    fin, val, perf, capm = a.get("fin") or {}, a.get("val") or {}, a["perf"], a["capm"]
    sig = fin.get("sig") if fin.get("applicable") else None
    so = fin.get("solvabilite") if fin.get("applicable") else None
    rn = _der(sig, "Résultat net") if sig is not None else None
    ca = _der(sig, "Chiffre d'affaires (CA)") if sig is not None else None
    ebe = _der(sig, "EBE (EBITDA)") if sig is not None else None
    cp = _der(so, "Capitaux propres") if so is not None else None
    dfn = _der(so, "Dette financière nette (DFN)") if so is not None else None
    mult = val.get("multiples") or {}
    capi = _f(mult.get("Capitalisation boursière"))
    ve = _f(mult.get("Valeur d'entreprise (VE = capitalisation + DFN)"))
    dc = val.get("devise_compta") or a["infos"].get("Devise") or ""
    rf = 0.03
    sortie = []

    def ajout(cle, nom, valeur, affichage, definition, formule, lecture, champ=None, haut_mieux=True, phrase=None):
        if valeur is None:
            return
        r = rang(cible, pairs, champ, haut_mieux) if champ else None
        sortie.append({"cle": cle, "nom": nom, "valeur": valeur, "affichage": affichage, "definition": definition,
                       "formule": formule, "lecture": lecture, "rang": r, "phrase_rang": phrase, "champ": champ,
                       "secteur": secteur})

    per = _f(mult.get("PER (capitalisation / résultat net)"))
    if per and per > 0:
        ajout("per", "PER (cours / bénéfice)", per, nb(per),
              "Combien d'années de bénéfices on paie en achetant l'action. Plus il est élevé, plus le marché anticipe une forte croissance (ou plus l'action est chère).",
              f"Capitalisation / résultat net = {md(capi)} / {md(rn)} {dc} = {nb(per)}",
              "Repères : moins de 12 = bon marché ou entreprise en difficulté ; 12 à 20 = dans la moyenne ; plus de 25 = forte croissance attendue.",
              "per", False, "moins cher que")
    ve_ebe = _f(mult.get("VE / EBE"))
    if ve_ebe and ve_ebe > 0:
        ajout("ve_ebe", "VE / EBITDA", ve_ebe, nb(ve_ebe),
              "Le prix de toute l'entreprise (actions + dette nette) rapporté à son excédent brut d'exploitation. C'est le multiple préféré des banques d'affaires, car il ne dépend ni de la dette ni des amortissements.",
              f"(Capitalisation + dette nette) / EBITDA = {md(ve)} / {md(ebe)} {dc} = {nb(ve_ebe)}",
              "Repères : 6 à 10 = dans la moyenne de l'industrie ; plus de 15 = entreprise de croissance ou très rentable.",
              "ve_ebe", False, "moins cher que")
    rdt = _f(mult.get("Rendement du dividende"))
    if rdt is not None and rdt > 0:
        ajout("rdt_div", "Rendement du dividende", rdt, pc(rdt),
              "Le dividende annuel rapporté au cours : le « loyer » que verse l'action chaque année.",
              f"Dividende annuel par action / cours = {pc(rdt)}",
              "Repères : 2 à 4 % en Europe en moyenne ; au-delà de 7 %, vérifier que le dividende n'est pas menacé.",
              "rdt_div", True, "plus généreux que")
    if rn is not None and ca:
        mn = rn / ca
        ajout("marge_nette", "Marge nette", mn, pc(mn),
              "Ce qui reste en bénéfice sur 100 € de chiffre d'affaires, une fois toutes les charges et impôts payés.",
              f"Résultat net / chiffre d'affaires = {md(rn)} / {md(ca)} {dc} = {pc(mn)}",
              "Repères : moins de 5 % = activité à faibles marges (distribution, industrie) ; plus de 20 % = position très forte (luxe, logiciel).",
              "marge_nette", True, "plus rentable que")
    if ebe is not None and ca:
        me = ebe / ca
        ajout("marge_ebitda", "Marge d'EBITDA", me, pc(me),
              "La rentabilité de l'activité elle-même, avant amortissements, intérêts et impôts.",
              f"EBITDA / chiffre d'affaires = {md(ebe)} / {md(ca)} {dc} = {pc(me)}",
              "Repères : 10 à 20 % pour une entreprise industrielle ; plus de 30 % = modèle très rentable.")
    if rn is not None and cp and cp > 0:
        roe = rn / cp
        ajout("roe", "Rentabilité des capitaux propres (ROE)", roe, pc(roe),
              "Ce que rapporte chaque euro investi par les actionnaires. Attention : un ROE très élevé peut venir de capitaux propres réduits par des rachats d'actions ou de la dette.",
              f"Résultat net / capitaux propres = {md(rn)} / {md(cp)} {dc} = {pc(roe)}",
              "Repères : plus de 15 % = très bon ; moins de 8 % = l'entreprise rapporte à peine son coût du capital.",
              "roe", True, "plus rentable que")
    if dfn is not None and ebe and ebe > 0:
        lev = dfn / ebe
        ajout("levier", "Dette nette / EBITDA", lev, nb(lev, 2) + " ×",
              "En combien d'années l'entreprise rembourserait sa dette nette avec son excédent brut d'exploitation. Négatif : plus de trésorerie que de dettes.",
              f"Dette financière nette / EBITDA = {md(dfn)} / {md(ebe)} {dc} = {nb(lev, 2)}",
              "Repères (cours) : moins de 1 = très solide ; 1 à 3 = acceptable ; plus de 3 à 4 = endettement élevé.",
              "levier", False, "moins endettée que")
    tcam = _f(fin.get("tcam_ca")) if fin.get("applicable") else None
    if tcam is not None:
        ans = fin.get("annees") or []
        ajout("croissance", "Croissance annuelle du CA", tcam, pc(tcam, signe=True),
              "Le taux de croissance annuel moyen (TCAM) du chiffre d'affaires sur les exercices disponibles.",
              f"(CA {ans[-1]} / CA {ans[0]})^(1/{len(ans) - 1}) − 1 = {pc(tcam, signe=True)}" if len(ans) > 1 else pc(tcam),
              "Repères : plus vite que l'inflation (2 %) = croissance réelle ; plus de 10 % par an = croissance forte.",
              "croissance_ca", True, "plus dynamique que")
    b = _f(capm.get("beta"))
    ajout("beta", "Bêta", b, nb(b, 2),
          "La sensibilité de l'action aux mouvements du marché : un bêta de 1,3 signifie qu'elle monte ou baisse en moyenne de 1,3 % quand le marché bouge de 1 %.",
          f"Covariance(action, indice) / variance(indice) = {nb(b, 2)} (régression sur la période du rapport)",
          "Repères : moins de 0,8 = défensive ; autour de 1 = comme le marché ; plus de 1,2 = offensive.",
          "beta", False, "moins sensible au marché que")
    vol = _f(perf.get("Volatilité annualisée"))
    ajout("volatilite", "Volatilité annualisée", vol, pc(vol),
          "L'amplitude habituelle des variations du cours sur un an. Environ 2 années sur 3, le rendement reste dans ± une volatilité autour de la moyenne.",
          f"Écart-type des rendements quotidiens × √252 = {pc(vol)}",
          "Repères : 15 à 25 % pour une grande entreprise ; plus de 40 % = action très agitée.")
    sh = _f(perf.get("Sharpe"))
    ra = _f(perf.get("Rendement annualisé"))
    ajout("sharpe", "Ratio de Sharpe", sh, nb(sh, 2),
          "Le rendement obtenu au-delà du taux sans risque, pour chaque unité de risque prise.",
          f"(Rendement annualisé − taux sans risque) / volatilité = ({pc(ra)} − {pc(rf, 0)}) / {pc(vol)} = {nb(sh, 2)}",
          "Repères : moins de 0 = moins bien qu'un livret ; 0,5 = correct ; plus de 1 = excellent.")
    dd = _f(perf.get("Max drawdown"))
    ajout("drawdown", "Perte maximale", dd, pc(dd),
          "La pire baisse subie entre un plus haut et le plus bas qui a suivi, sur la période : ce qu'un investisseur malchanceux aurait vécu.",
          f"Min(cours / plus haut précédent − 1) = {pc(dd)}",
          "Repères : −20 % = correction ; −35 % ou pire = krach pour cette action.")
    if val.get("applicable"):
        pz = val["piotroski"]["score"]
        if pz is not None and not (isinstance(pz, float) and math.isnan(pz)):
            ajout("piotroski", "F-score de Piotroski", float(pz), f"{int(pz)} / 9",
                  "Neuf tests simples (rentabilité, endettement, efficacité) entre les deux derniers exercices : chaque test réussi vaut 1 point.",
                  f"Somme des 9 tests réussis = {int(pz)} / 9",
                  "Repères : 7 à 9 = santé financière solide et en amélioration ; 0 à 3 = signaux de faiblesse.")
    if d:
        w = d["resultat"]["cmpc"]
        h = d["hypotheses"]
        ajout("cmpc", "Coût du capital (CMPC)", w, pc(w, 2),
              "Le rendement minimum exigé par l'ensemble des financeurs (actionnaires et prêteurs). C'est le taux d'actualisation du DCF.",
              f"{pc(h['poids_cp'], 0)} × ({pc(h['rf'])} + {nb(h['beta'], 2)} × {pc(h['prime'])}) + {pc(1 - h['poids_cp'], 0)} × {pc(h['kd'])} × (1 − {pc(h['taux_is'], 0)}) = {pc(w, 2)}",
              "Repères : 6 à 10 % pour la plupart des grandes entreprises.")
    return sortie


# ---------------------------------------------------------------------------
# 4. Catalyseurs, risques, thèse
# ---------------------------------------------------------------------------
def catalyseurs(a) -> list:
    res = []
    auj = dt.date.today()
    try:
        import yfinance as yf
        cal = yf.Ticker(a["ticker"]).calendar or {}
        dates = [x for x in (cal.get("Earnings Date") or []) if isinstance(x, dt.date)]
        if dates:
            x = min(dates)
            if x >= auj:
                attente = ""
                if cal.get("Earnings Average"):
                    attente = f" : bénéfice par action attendu de {nb(_f(cal['Earnings Average']), 2)}"
                res.append({"date": str(x), "texte": f"Publication des résultats{attente}. Le cours réagit à l'écart avec ces attentes, pas au chiffre lui-même."})
            else:
                res.append({"date": str(x), "texte": "Dernière publication des résultats ; la prochaine date n'est pas encore annoncée."})
        exd = cal.get("Ex-Dividend Date")
        if isinstance(exd, dt.date) and exd >= auj:
            res.append({"date": str(exd), "texte": "Détachement du dividende : il faut détenir l'action la veille pour le toucher."})
    except Exception:
        pass
    for x in (a.get("actus") or {}).get("fr", [])[:3]:
        res.append({"date": str(x.get("date") or "")[:10], "texte": "Actualité : " + str(x.get("titre") or ""), "lien": x.get("lien")})
    return res


def risques(a, d) -> list:
    from analyse_complete import synthese
    try:
        _, vigilance = synthese(a)
    except Exception:
        vigilance = []
    r = list(vigilance[:4])
    if d and d["resultat"].get("part_vt") and d["resultat"]["part_vt"] > 0.8:
        r.append(f"Valeur très dépendante du long terme : {pc(d['resultat']['part_vt'], 0)} de la valeur DCF vient d'après l'année 5.")
    return r[:5] or ["Aucun point de vigilance marquant dans les indicateurs."]


def these(n, a, d) -> list:
    ch = {c["cle"]: c for c in n["chiffres"]}
    p = []
    if n["valeur_centrale"]:
        txt = (f"Au cours de {nb(n['cours'], 2)} {n['devise']}, nos méthodes fondamentales situent la valeur de {html.escape(nom_court(n))} "
               f"autour de <b>{nb(n['valeur_centrale'], 2)} {n['devise']}</b> ({pc(n['potentiel'], signe=True)}) ; "
               f"{n['methodes_dessus']} méthode(s) sur {n['methodes_fond']} placent la valeur au-dessus du cours.")
        if "per" in ch and ch["per"]["rang"]:
            r = ch["per"]["rang"]
            txt += (f" L'action se paie {nb(ch['per']['valeur'])} fois ses bénéfices, contre {nb(r['mediane'])} pour la médiane "
                    f"du secteur {html.escape(n['secteur'])}.")
        p.append(txt)
    if n["methodes_fond"] == 1:
        p.append("Une seule méthode de valorisation est applicable ici (pour une banque ou une assurance, le DCF sur flux de "
                 "trésorerie n'a pas de sens) : le verdict n'est qu'indicatif.")
    elif not n["valeur_centrale"]:
        p.append("Aucune méthode fondamentale ne donne de valeur positive : l'entreprise ne dégage pas encore de bénéfices ni de "
                 "flux de trésorerie suffisants. Sa valeur repose sur sa croissance future, très incertaine ; les objectifs des "
                 "analystes et les cours passés restent les seuls repères.")
    if n.get("divergence") and n["divergence"] > 1.6:
        p.append("<b>Attention, les méthodes divergent fortement</b> (la plus haute est "
                 f"{nb(n['divergence'], 1)} fois la plus basse) : le DCF repose sur les flux que l'entreprise produira, les multiples "
                 "sur les prix actuels du secteur. Quand ils racontent deux histoires différentes, la conclusion est fragile : "
                 "regarde quelles hypothèses expliquent l'écart (croissance, marges, multiples du secteur).")
    if n.get("g_marche") is not None:
        p.append(f"Le cours actuel suppose une croissance du chiffre d'affaires d'environ <b>{pc(n['g_marche'])} par an</b> pendant 5 ans "
                 "(DCF inversé) : c'est la question centrale pour l'investisseur.")
    q = []
    if "marge_nette" in ch:
        c = ch["marge_nette"]
        q.append(f"une marge nette de {c['affichage']}" + (f" (meilleure que {pc(c['rang']['meilleur_que'], 0)} du secteur)" if c["rang"] else ""))
    if "roe" in ch:
        q.append(f"un ROE de {ch['roe']['affichage']}")
    if "levier" in ch:
        lv = ch["levier"]["valeur"]
        q.append("une dette nette faible" if lv < 1 else "un endettement modéré" if lv < 3 else "un endettement élevé")
        q[-1] += f" ({ch['levier']['affichage']} l'EBITDA)"
    if q:
        p.append("Qualité de l'entreprise : " + ", ".join(q) + ".")
    if "beta" in ch and "volatilite" in ch:
        b = ch["beta"]["valeur"]
        p.append(f"En bourse, l'action est {'plus' if b > 1.1 else 'moins' if b < 0.9 else 'aussi'} sensible au marché que la moyenne "
                 f"(bêta {ch['beta']['affichage']}, volatilité {ch['volatilite']['affichage']}).")
    return p


# ---------------------------------------------------------------------------
# 5. Graphique « football field »
# ---------------------------------------------------------------------------
def graphique_football(n: dict, fichier=None):
    f = n["fourchettes"]
    if not f:
        return
    fig, ax = plt.subplots(figsize=(10, 0.62 * len(f) + 1.5))
    couleurs = {"fondamentale": "#D4AF6A", "marche": "#6EA8FF"}
    for i, x in enumerate(reversed(f)):
        c = couleurs[x["famille"]]
        ax.barh(i, x["haut"] - x["bas"], left=x["bas"], height=0.52, color=c, edgecolor="none", zorder=2)
        if x["centre"] and x["famille"] == "fondamentale" or x["methode"].startswith("Objectifs"):
            ax.plot([x["centre"]] * 2, [i - 0.26, i + 0.26], color="#0A0F1C", lw=2, zorder=3)
        ax.text(x["bas"], i, f"{nb(x['bas'], 0)}  ", va="center", ha="right", fontsize=9, color="#C9CDD6")
        ax.text(x["haut"], i, f"  {nb(x['haut'], 0)}", va="center", ha="left", fontsize=9, color="#C9CDD6")
    ax.set_yticks(range(len(f)))
    ax.set_yticklabels([x["methode"] for x in reversed(f)], fontsize=10)
    ax.axvline(n["cours"], color="#FF6B5A", lw=1.6, ls="--", zorder=4)
    ax.text(n["cours"], len(f) - 0.35, f" Cours {nb(n['cours'], 2)}", color="#FF6B5A", fontsize=9.5, va="bottom")
    if n["valeur_centrale"]:
        ax.axvline(n["valeur_centrale"], color="#3BC48F", lw=1.4, zorder=4)
        ax.text(n["valeur_centrale"], -0.75, f" Valeur centrale {nb(n['valeur_centrale'], 2)}", color="#3BC48F", fontsize=9.5, va="top")
    lo = min(x["bas"] for x in f + [{"bas": n["cours"]}])
    hi = max(x["haut"] for x in f + [{"haut": n["cours"]}])
    marge = (hi - lo) * 0.14
    ax.set_xlim(max(lo - marge, 0), hi + marge)
    ax.set_ylim(-1.1, len(f) - 0.2)
    ax.set_xlabel(f"Valeur par action ({n['devise']})")
    ax.set_title("Football field : la valeur de l'action selon chaque méthode", loc="left")
    ax.set_axisbelow(True)
    ax.grid(axis="x", alpha=0.25)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.tight_layout()
    if fichier:
        fig.savefig(fichier, dpi=110)
        plt.close(fig)


# ---------------------------------------------------------------------------
# 6. HTML : section du rapport (interactive) et note d'une page (PDF)
# ---------------------------------------------------------------------------
CSS = """
.note-analyse { border: 1px solid var(--bord); border-radius: 14px; padding: 18px 20px; background: var(--carte);
  box-shadow: inset 0 2px 0 var(--or); }
.na-tete { display: flex; justify-content: space-between; gap: 18px; flex-wrap: wrap; align-items: flex-end; }
.na-verdict { font-family: var(--serif); font-size: 26px; font-weight: 600; }
.na-verdict.pos { color: var(--vert); } .na-verdict.neg { color: var(--rouge); } .na-verdict.neutre { color: var(--or); }
.na-chiffres { display: flex; gap: 22px; flex-wrap: wrap; font-family: var(--mono); }
.na-chiffres div { text-align: right; } .na-chiffres .l { font: 11px -apple-system, sans-serif; color: var(--doux);
  text-transform: uppercase; letter-spacing: .04em; } .na-chiffres .v { font-size: 20px; }
.na-these p { margin: 8px 0; }
.na-ff td:not(:first-child) { font-family: var(--mono); }
.na-pastille { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; vertical-align: -1px; }
.na-cles { display: grid; grid-template-columns: repeat(auto-fill, minmax(215px, 1fr)); gap: 10px; margin-top: 10px; }
.na-cle { all: unset; box-sizing: border-box; cursor: pointer; background: var(--fond); border: 1px solid var(--bord);
  border-radius: 10px; padding: 10px 12px; transition: border-color .16s, transform .16s; display: block; }
.na-cle:hover { border-color: var(--or); transform: translateY(-2px); }
.na-cle:focus-visible { outline: 2px solid var(--or); outline-offset: 2px; }
.na-cle .l { font-size: 11.5px; color: var(--doux); } .na-cle .v { font: 600 19px var(--mono); margin: 2px 0 6px; }
.na-barre { position: relative; height: 6px; border-radius: 99px; background: linear-gradient(90deg, #4A2330, #1A2236 50%, #1C4A38); }
.na-barre i { position: absolute; top: -3px; width: 4px; height: 12px; border-radius: 2px; background: var(--or); transform: translateX(-2px); }
.na-barre b { position: absolute; top: -2px; width: 1px; height: 10px; left: 50%; background: var(--doux); }
.na-rang { font-size: 11.5px; color: var(--doux); margin-top: 5px; min-height: 16px; }
.na-tiroir { position: fixed; top: 0; right: 0; bottom: 0; width: min(440px, 92vw); background: var(--carte);
  border-left: 1px solid var(--bord); box-shadow: -20px 0 60px rgba(0,0,0,.5); padding: 22px 22px 30px; overflow-y: auto;
  transform: translateX(105%); transition: transform .24s cubic-bezier(.23,1,.32,1); z-index: 20; }
.na-tiroir.ouvert { transform: none; }
.na-tiroir h3 { margin-top: 0; } .na-tiroir .fermer { float: right; all: unset; cursor: pointer; float: right; font-size: 22px; color: var(--doux); }
.na-tiroir .formule { font-family: var(--mono); font-size: 13px; background: var(--fond); border: 1px solid var(--bord);
  border-radius: 8px; padding: 10px; margin: 10px 0; line-height: 1.5; }
.na-tiroir .lab { font-size: 11px; color: var(--doux); text-transform: uppercase; letter-spacing: .05em; margin-top: 14px; }
.lien-secteur { color: var(--or); }
.kpi[data-x] { cursor: pointer; } .kpi[data-x]:hover { border-color: var(--or); }
@media (prefers-reduced-motion: reduce) { .na-tiroir, .na-cle { transition: none; } }
"""


def _barre(r):
    if not r:
        return '<div class="na-rang">Pas de comparaison sectorielle</div>'
    pos = r["meilleur_que"] * 100
    return (f'<div class="na-barre" aria-hidden="true"><b></b><i style="left:{pos:.0f}%"></i></div>'
            f'<div class="na-rang">Mieux que {pos:.0f} % du secteur</div>')


def section_html(a: dict) -> str:
    n = a.get("note")
    if not n:
        return ""
    e = html.escape
    dev = n["devise"]
    h = "<h2 id='note'>Note d'analyse</h2>"
    h += "<div class='note-analyse'><div class='na-tete'><div>"
    h += f"<div class='note'>Valorisation</div><div class='na-verdict {n['ton']}'>{e(n['verdict'])}</div></div>"
    h += "<div class='na-chiffres'>"
    h += f"<div><div class='l'>Cours</div><div class='v'>{nb(n['cours'], 2)}</div></div>"
    if n["valeur_centrale"]:
        lo = min(f["bas"] for f in n["fourchettes"] if f["famille"] == "fondamentale")
        hi = max(f["haut"] for f in n["fourchettes"] if f["famille"] == "fondamentale")
        h += f"<div><div class='l'>Valeur centrale</div><div class='v'>{nb(n['valeur_centrale'], 2)}</div></div>"
        h += f"<div><div class='l'>Fourchette</div><div class='v'>{nb(lo, 0)} – {nb(hi, 0)}</div></div>"
        cls = "pos" if n["potentiel"] >= 0 else "neg"
        h += f"<div><div class='l'>Potentiel</div><div class='v {cls}'>{pc(n['potentiel'], signe=True)}</div></div>"
    h += f"</div></div><div class='na-these'>" + "".join(f"<p>{x}</p>" for x in n["these"]) + "</div></div>"

    # Football field
    h += "<h3>Fourchettes de valeur par méthode</h3>"
    h += ("<p class='note'>Chaque barre est l'intervalle de valeur donné par une méthode. En <b style='color:#D4AF6A'>or</b>, les "
          "méthodes fondamentales (ce que vaut l'entreprise d'après ses flux et ses comparables) ; en <b style='color:#6EA8FF'>bleu</b>, "
          "les repères de marché. Le trait rouge est le cours, le trait vert la valeur centrale (médiane du DCF et des deux méthodes de comparables). "
          "Quand les barres se recouvrent largement, les méthodes convergent : la conclusion est plus solide.</p>")
    h += a["graphiques"].get("football", "")
    lignes = "".join(
        f"<tr><td><span class='na-pastille' style='background:{'#D4AF6A' if f['famille'] == 'fondamentale' else '#6EA8FF'}'></span>"
        f"{e(f['methode'])}<div class='note'>{e(f['detail'])}</div></td><td>{nb(f['bas'], 2)}</td>"
        f"<td>{nb(f['centre'], 2) if f['famille'] == 'fondamentale' or f['methode'].startswith('Objectifs') else '—'}</td>"
        f"<td>{nb(f['haut'], 2)}</td><td>{pc(f['potentiel'], signe=True) if f['famille'] == 'fondamentale' or f['methode'].startswith('Objectifs') else '—'}</td></tr>"
        for f in n["fourchettes"])
    h += (f"<div class='carte'><table class='na-ff'><tr><th>Méthode</th><th>Bas</th><th>Central</th><th>Haut</th>"
          f"<th>Potentiel</th></tr>{lignes}</table></div>")

    # Catalyseurs et risques
    cat = "".join(f"<li><b>{e(c['date'])}</b> — {e(c['texte'])}</li>" for c in n["catalyseurs"]) or "<li>Aucun événement connu.</li>"
    ris = "".join(f"<li>{x}</li>" for x in n["risques"])
    h += ("<div class='colonnes'><div class='carte'><b>Catalyseurs à venir</b><ul class='fort'>" + cat + "</ul></div>"
          "<div class='carte'><b>Risques principaux</b><ul class='vigil'>" + ris + "</ul></div></div>")

    # Chiffres clés
    h += ("<h3>Chiffres clés</h3><p class='note'>Clique sur un chiffre pour voir <b>d'où il vient</b> : sa définition, le calcul "
          "avec les chiffres de l'entreprise et sa place dans le secteur. Le repère gris au milieu de la barre est la médiane du "
          f"secteur <a href='#' class='lien-secteur' data-secteur='{e(n['secteur'], quote=True)}'>{e(n['secteur'])}</a> "
          "(clique pour son tableau de bord).</p><div class='na-cles'>")
    for c in n["chiffres"]:
        h += (f"<button class='na-cle' data-x='{c['cle']}'><div class='l'>{e(c['nom'])}</div>"
              f"<div class='v'>{e(c['affichage'])}</div>{_barre(c['rang'])}</button>")
    h += "</div>"
    sources = (f"Sources : cours Yahoo Finance au {n['date_cours']}"
               + (f" ; comptes de l'exercice {n['annee_comptes']}" if n["annee_comptes"] else "")
               + (f" ; consensus de {n['analystes']} analystes" if n["analystes"] else "")
               + (f" ; comparaisons sectorielles sur {n['taille_base']} entreprises (base du {n['date_base']})" if n["date_base"] else "")
               + f". Note générée le {dt.date.today()}. Lecture pédagogique des chiffres, pas un conseil d'investissement.")
    h += f"<p class='note'>{e(sources)}</p>"

    # Tiroir d'explication et script
    donnees = {c["cle"]: {**{k: c[k] for k in ("nom", "affichage", "definition", "formule", "lecture", "rang", "phrase_rang", "secteur")},
                          "mediane": fmt_median(c)} for c in n["chiffres"]}
    h += ("<aside class='na-tiroir' id='na-tiroir' role='dialog' aria-modal='false' aria-labelledby='na-t-titre'>"
          "<button class='fermer' id='na-fermer' aria-label='Fermer'>×</button><div id='na-t-contenu'></div></aside>")
    h += "<script>const NA=" + json.dumps(donnees, ensure_ascii=False).replace("</", "<\\/") + ";" + _JS + "</script>"
    return h


_JS = r"""
(function(){
  const t = document.getElementById('na-tiroir'), c = document.getElementById('na-t-contenu');
  const esc = s => String(s).replace(/[&<>"]/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));
  let dernier = null;
  function ouvrir(cle, source){
    const d = NA[cle]; if(!d) return; dernier = source;
    let rang = '<p class="note">Pas assez d\'entreprises comparables dans la base pour situer ce chiffre.</p>';
    if (d.rang){ const r = d.rang;
      rang = `<p>${esc(d.phrase_rang ? 'Cette entreprise est ' + d.phrase_rang + ' ' + Math.round(r.meilleur_que*100) + ' % des ' + r.n + ' entreprises du secteur ' + d.secteur : '')}.</p>
        <p class="note">Médiane du secteur : <b>${esc(d.mediane)}</b>. Le rang utilise les données des 12 derniers mois de Yahoo Finance, identiques pour toutes les entreprises (elles peuvent différer légèrement du chiffre du dernier exercice).</p>`; }
    c.innerHTML = `<h3 id="na-t-titre">${esc(d.nom)}</h3><div style="font:600 30px var(--mono)">${esc(d.affichage)}</div>
      <div class="lab">Ce que c'est</div><p>${esc(d.definition)}</p>
      <div class="lab">Le calcul pour cette entreprise</div><div class="formule">${esc(d.formule)}</div>
      <div class="lab">Comment le lire</div><p>${esc(d.lecture)}</p>
      <div class="lab">Dans son secteur</div>${rang}`;
    t.classList.add('ouvert'); document.getElementById('na-fermer').focus();
  }
  function fermer(){ t.classList.remove('ouvert'); if (dernier) dernier.focus(); }
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-x]');
    if (b) { ouvrir(b.dataset.x, b); return; }
    if (t.classList.contains('ouvert') && !t.contains(e.target)) fermer();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && t.classList.contains('ouvert')) fermer();
    const b = e.target.closest && e.target.closest('.kpi[data-x]');
    if (b && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); ouvrir(b.dataset.x, b); }
  });
  document.getElementById('na-fermer').addEventListener('click', fermer);
  document.querySelectorAll('.lien-secteur').forEach(a => a.addEventListener('click', e => {
    e.preventDefault(); window.parent.postMessage({type: 'secteur', nom: a.dataset.secteur}, '*'); }));
})();
"""


def page_pdf(a: dict) -> str:
    """Note d'une page, pour l'export PDF (mise en page simple compatible xhtml2pdf)."""
    n = a["note"]
    e = html.escape
    dev = n["devise"]
    ff = "".join(f"<tr><td>{e(f['methode'])}</td><td>{nb(f['bas'], 2)}</td><td>{nb(f['centre'], 2) if f['famille'] == 'fondamentale' or f['methode'].startswith('Objectifs') else '—'}</td>"
                 f"<td>{nb(f['haut'], 2)}</td></tr>" for f in n["fourchettes"])
    COURT = {"per": "PER", "roe": "ROE", "levier": "Dette nette / EBITDA", "cmpc": "CMPC", "piotroski": "F-score Piotroski",
             "rdt_div": "Rendement dividende", "croissance": "Croissance du CA", "volatilite": "Volatilité"}
    cel = lambda c: (f"<td style='width:24%;text-align:left'>{e(COURT.get(c['cle'], c['nom']))}</td><td>{e(c['affichage'])}</td><td>{fmt_median(c)}</td>"
                     f"<td>{(str(round(c['rang']['meilleur_que'] * 100)) + ' %') if c['rang'] else '—'}</td>") if c else "<td></td>" * 4
    ch = n["chiffres"]
    moitie = (len(ch) + 1) // 2
    cles = "".join(f"<tr>{cel(ch[i])}<td style='width:12px;border:0'></td>{cel(ch[i + moitie] if i + moitie < len(ch) else None)}</tr>"
                   for i in range(moitie))
    cat = "".join(f"<li><b>{e(c['date'])}</b> — {e(c['texte'])}</li>" for c in n["catalyseurs"][:4])
    ris = "".join(f"<li>{x}</li>" for x in n["risques"][:4])
    couleur = {"pos": "#1a7f5a", "neg": "#c0392b", "neutre": "#9a7a2e"}[n["ton"]]
    resume = (f"Cours {nb(n['cours'], 2)} {dev} · valeur centrale {nb(n['valeur_centrale'], 2)} {dev} · potentiel {pc(n['potentiel'], signe=True)}"
              if n["valeur_centrale"] else f"Cours {nb(n['cours'], 2)} {dev}")
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><style>
@page {{ size: a4 portrait; margin: 1.1cm 1.3cm; }}
body {{ font-family: Helvetica; font-size: 7.6pt; color: #1d1d1f; line-height: 1.3; }} p {{ margin: 0 0 3px; }}
h1 {{ font-size: 14pt; margin: 0; color: #1F2A44; }} h2 {{ font-size: 9pt; color: #1F2A44; margin: 6px 0 2px; padding-bottom: 1px; border-bottom: 1px solid #D4AF6A; }}
.sous {{ color: #6e6e73; font-size: 8pt; }} .verdict {{ font-size: 12pt; font-weight: bold; color: {couleur}; margin-top: 4px; }}
table {{ width: 100%; border-collapse: collapse; }} td, th {{ padding: 1px 4px; border-bottom: 0.5px solid #ddd; text-align: right; }}
td:first-child, th:first-child {{ text-align: left; }} th {{ color: #6e6e73; font-weight: normal; }}
ul {{ margin: 2px 0; padding-left: 12px; }} li {{ margin: 1px 0; }} .pied {{ color: #6e6e73; font-size: 6.8pt; margin-top: 8px; }}
</style></head><body>
<h1>{e(nom_court(n))} ({e(n['ticker'])})</h1>
<div class="sous">Note d'analyse · {e(n['secteur'])} · {dt.date.today()}</div>
<div class="verdict">{e(n['verdict'])}</div><div><b>{resume}</b></div>
<h2>Thèse</h2>{''.join(f'<p>{x}</p>' for x in n['these'])}
<h2>Fourchettes de valeur ({e(dev)})</h2>{a['graphiques'].get('football', '').replace('<img ', '<img style="width:13cm" ')}
<table><tr><th>Méthode</th><th>Bas</th><th>Central</th><th>Haut</th></tr>{ff}</table>
<table><tr><td style="width:50%;vertical-align:top;border:0"><h2>Catalyseurs</h2><ul>{cat or '<li>—</li>'}</ul></td>
<td style="width:50%;vertical-align:top;text-align:left;border:0"><h2>Risques</h2><ul>{ris}</ul></td></tr></table>
<h2>Chiffres clés <span class="sous">(médiane du secteur ; rang = part du secteur que l'entreprise devance)</span></h2>
<table><tr><th>Indicateur</th><th>Valeur</th><th>Secteur</th><th>Rang</th><th style="border:0"></th><th style="text-align:left">Indicateur</th><th>Valeur</th><th>Secteur</th><th>Rang</th></tr>{cles}</table>
<div class="pied">Sources : Yahoo Finance (cours au {n['date_cours']}{', comptes ' + str(n['annee_comptes']) if n['annee_comptes'] else ''}{', ' + str(n['analystes']) + ' analystes' if n['analystes'] else ''}),
base sectorielle de {n['taille_base']} entreprises. Document généré par Analyse Actions, outil pédagogique : ce n'est pas un conseil en investissement.</div>
</body></html>"""


def fmt_median(c):
    r = c["rang"]
    if not r:
        return "—"
    m = r["mediane"]
    return pc(m) if c["cle"] in ("roe", "marge_nette", "rdt_div", "croissance") else nb(m, 2)


def nom_court(n):
    try:
        from analyse_complete import nom_liste
        court = nom_liste(n["ticker"]) or n["nom"]
        return re.sub(r"\s+Act\.?\s*[A-Za-z]?$", "", court)      # « BNP Paribas Act.a » -> « BNP Paribas »
    except Exception:
        return n["nom"]
