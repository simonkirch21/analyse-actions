"""
INTERPRÉTATION de la partie 8 (analyse financière des comptes de l'entreprise)
==============================================================================

Même logique que interpretation.py : pour chaque partie du cours,
« C'est quoi ? », « Ce qu'il faut retenir pour cette entreprise », les tableaux
sur plusieurs exercices (analyse en TENDANCE) avec une colonne « Repère »
(analyse NORMATIVE et COMPARATIVE, d'après les seuils du cours), et la lecture
des graphiques.
"""

import html

import numpy as np
import pandas as pd

from interpretation import (pct, num, notion, lecture_graphique, niveau, bloc)


def pour_cette_action(phrases: list) -> str:
    """Encadré de conclusion (ici, on parle de l'entreprise et non de l'action)."""
    items = "".join(f"<li>{p}</li>" for p in phrases if p)
    return bloc("Ce qu'il faut retenir pour cette entreprise", f"<ul>{items}</ul>", "verdict")
import partie8_analyse_financiere as p8


# ---------------------------------------------------------------------------
# Repères sectoriels du cours (Banque de France 2022, entreprises françaises)
# ---------------------------------------------------------------------------
SECTEUR_BDF = {
    "Technology": "Information et communication",
    "Communication Services": "Information et communication",
    "Industrials": "Industrie manufacturière",
    "Basic Materials": "Industrie manufacturière",
    "Energy": "Industrie manufacturière",
    "Healthcare": "Industrie manufacturière",
    "Consumer Defensive": "Commerce",
    "Consumer Cyclical": "Commerce",
    "Real Estate": "Activités spécialisées",
}
BFR_JOURS_BDF = {"Industrie manufacturière": 47, "Construction": 26, "Commerce": 16, "Transports": 8,
                 "Hébergement et restauration": -30, "Information et communication": 4}
GEARING_BDF = {"Industrie manufacturière": 0.43, "Construction": 0.42, "Commerce": 0.44,
               "Transports": 0.74, "Hébergement et restauration": 0.93,
               "Information et communication": 0.28, "Activités spécialisées": 0.31}


# ---------------------------------------------------------------------------
# Mise en forme des tableaux pluriannuels
# ---------------------------------------------------------------------------
def fmt(v, type_):
    if v is None or pd.isna(v):
        return "—"
    if type_ == "M":
        return num(v / 1e6, 0)
    if type_ == "%":
        return pct(v, 1)
    if type_ == "j":
        return f"{num(v, 0)} j"
    if type_ == "€":
        return num(v, 2)
    return num(v, 2)


def tableau_annees(a: dict, lignes: list, devise_titre: bool = False) -> str:
    """lignes : (libellé, série, type, repère). Une colonne par exercice + une colonne Repère."""
    annees = a["annees"]
    entete = "".join(f"<th>{an}</th>" for an in annees)
    repere = any(l[3] for l in lignes)
    h = "<table class='t-annees'><tr><th></th>" + entete + ("<th class='repere'>Repère</th>" if repere else "") + "</tr>"
    for libelle, serie, type_, rep in lignes:
        cellules = "".join(f"<td>{fmt(serie.get(an, np.nan), type_)}</td>" for an in annees)
        h += f"<tr><td>{html.escape(libelle)}</td>{cellules}"
        h += f"<td class='repere'>{html.escape(rep or '')}</td>" if repere else ""
        h += "</tr>"
    h += "</table>"
    if devise_titre:
        h = f"<p class='note'>Montants en millions {html.escape(a['devise'])}.</p>" + h
    return "<div class='carte'>" + h + "</div>"


def dernier(serie: pd.Series):
    s = serie.dropna()
    return s.iloc[-1] if len(s) else np.nan


def tendance(serie: pd.Series) -> str:
    """Hausse / baisse / stable entre le premier et le dernier exercice connus."""
    s = serie.dropna()
    if len(s) < 2:
        return "stable"
    debut, fin = s.iloc[0], s.iloc[-1]
    ecart = fin - debut
    base = max(abs(debut), 1e-9)
    if abs(ecart) / base < 0.05:
        return "stable"
    return "en hausse" if ecart > 0 else "en baisse"


# ---------------------------------------------------------------------------
# 7.0 Introduction : les 3 méthodes du cours
# ---------------------------------------------------------------------------
def introduction(f: dict) -> str:
    secteur_bdf = SECTEUR_BDF.get(f["secteur"])
    txt = notion(
        "<p>Jusqu'ici, on a étudié le <b>cours de bourse</b>. L'<b>analyse financière</b> étudie "
        "l'<b>entreprise elle-même</b> à partir de ses comptes : le <b>compte de résultat</b> (le film "
        "de l'année : ventes, charges, bénéfice), le <b>bilan</b> (la photo du patrimoine : ce que "
        "l'entreprise possède et ce qu'elle doit) et le <b>tableau des flux de trésorerie</b> "
        "(l'argent réellement encaissé et dépensé).</p>"
        "<p>Elle cherche à répondre à deux questions : l'entreprise <b>crée-t-elle de la valeur</b> ? "
        "Reste-t-elle <b>solvable</b> (capable de payer ses dettes) ? On suit le plan du cours : "
        "« la génération de richesse nécessite des investissements qui doivent être financés et "
        "être suffisamment rentables ».</p>"
        "<p>Trois méthodes sont combinées : l'analyse en <b>tendance</b> (l'évolution sur plusieurs "
        "exercices, en colonnes dans les tableaux), l'analyse <b>normative</b> (comparaison à des "
        "seuils reconnus, colonne « Repère ») et l'analyse <b>comparative</b> (comparaison au "
        "secteur" + (f", ici « {html.escape(secteur_bdf)} » selon la Banque de France" if secteur_bdf else "")
        + ").</p>")
    limites = bloc("Limites à connaître", (
        "<ul><li>Les comptes viennent de Yahoo Finance, au format international <b>IFRS</b> "
        "(présentation « par fonction »). Les soldes du Plan Comptable Général qui supposent une "
        "présentation « par nature » (production de l'exercice, valeur ajoutée, charges de "
        "personnel) <b>ne sont pas disponibles</b> : on part directement de la marge brute et de l'EBE.</li>"
        "<li>Le <b>point mort</b> demande de séparer charges fixes et variables, ce que les comptes "
        "publiés ne font pas. Hypothèse retenue : le coût des ventes est variable, les autres charges "
        "d'exploitation (frais commerciaux, administratifs, R&amp;D, amortissements) sont fixes.</li>"
        "<li>L'impôt est calculé au taux <b>normatif de 25 %</b>, comme dans le cours.</li>"
        "<li>La <b>notation ESG</b> (partie 1 du cours) n'est pas fournie gratuitement par Yahoo "
        "Finance : elle n'apparaît donc pas ici.</li></ul>"), "lecture")
    return txt + limites


# ---------------------------------------------------------------------------
# 7.1 Profitabilité et marges (partie 2 du cours)
# ---------------------------------------------------------------------------
def profitabilite(f: dict) -> tuple:
    sig, m, pm = f["sig"], f["marges"], f["point_mort"]
    n = notion(
        "<p>Le <b>résultat net</b> seul ne suffit pas : on décompose sa formation en une <b>cascade de "
        "soldes</b> pour voir <i>où</i> la richesse est créée et <i>où</i> elle est consommée.</p><ul>"
        "<li><b>Marge brute</b> = chiffre d'affaires − coût des ventes : ce qui reste après avoir "
        "payé ce qui est vendu. Elle mesure le <b>pouvoir de fixer ses prix</b>.</li>"
        "<li><b>EBE (EBITDA)</b> : le flux généré par l'exploitation, avant amortissements, intérêts "
        "et impôt. C'est le ratio de référence pour comparer des entreprises d'un même secteur.</li>"
        "<li><b>Résultat d'exploitation (REX)</b> = EBE − amortissements : la performance économique "
        "après usure des équipements.</li>"
        "<li><b>CAF</b> (capacité d'autofinancement) : l'argent généré par l'activité, disponible pour "
        "investir, rembourser les dettes ou verser des dividendes sans aide extérieure.</li>"
        "<li><b>Effet ciseau</b> : si les charges augmentent plus vite que les ventes, la marge "
        "se réduit « comme deux lames de ciseaux qui se rapprochent ».</li>"
        "<li><b>Point mort</b> : le chiffre d'affaires à partir duquel l'entreprise ne perd plus "
        "d'argent. L'<b>indice de sécurité</b> (CA / point mort) dit à quelle distance elle en est ; "
        "le <b>levier opérationnel</b> dit de combien le résultat varie quand le CA varie de 1 %.</li>"
        "</ul>")

    ca = sig["Chiffre d'affaires (CA)"]
    me, mo = m["Marge d'EBE"], m["Marge opérationnelle (REX / CA)"]
    phrases = [
        f"Chiffre d'affaires {tendance(ca)} : croissance moyenne de <b>{pct(f['tcam_ca'], 1, signe=True)} "
        f"par an</b> sur la période.",
        f"Sur 100 de ventes, l'entreprise dégage <b>{num(dernier(me) * 100, 1)} d'EBE</b> et "
        f"<b>{num(dernier(m['Marge nette']) * 100, 1)} de bénéfice net</b> (dernier exercice). "
        f"La marge opérationnelle est {tendance(mo)}.",
    ]
    tc, tch = f["tcam_ca"], f["tcam_charges"]
    if pd.notna(tch):
        if tch > tc + 0.005:
            phrases.append(f"<b>Effet ciseau défavorable</b> {niveau('Vigilance', 'mauvais')} : les charges "
                           f"d'exploitation progressent de {pct(tch, 1)} par an contre {pct(tc, 1)} pour les "
                           "ventes, ce qui comprime la marge.")
        elif tch < tc - 0.005:
            phrases.append(f"<b>Effet ciseau favorable</b> {niveau('Bon', 'bon')} : les ventes progressent "
                           f"plus vite ({pct(tc, 1)} par an) que les charges ({pct(tch, 1)}), "
                           "signe d'économies d'échelle ou de gains de productivité.")
        else:
            phrases.append("Ventes et charges évoluent au même rythme : pas d'effet ciseau marqué.")

    p = pm.iloc[-1]
    ind, lo = p["Indice de sécurité (CA / point mort)"], p["Levier opérationnel (MCV / REX)"]
    if pd.notna(ind):
        if ind > 1:
            phrases.append(f"Le CA dépasse le point mort de {pct(ind - 1, 0)} (indice de sécurité "
                           f"{num(ind)} {niveau('Confortable', 'bon') if ind > 1.2 else niveau('Juste', 'moyen')}) : "
                           f"le chiffre d'affaires pourrait baisser d'environ {pct(1 - 1 / ind, 0)} avant "
                           "que l'exploitation ne devienne déficitaire.")
        else:
            phrases.append(f"Le CA est <b>sous le point mort</b> (indice {num(ind)}) "
                           f"{niveau('Zone dangereuse', 'mauvais')} : l'exploitation ne couvre pas ses charges.")
    if pd.notna(lo) and lo > 0:
        phrases.append(f"Levier opérationnel de {num(lo, 1)} : si le CA baisse de 10 %, le résultat "
                       f"d'exploitation baisse d'environ {num(min(lo * 10, 100), 0)} %. "
                       + ("Résultat <b>très sensible</b> à l'activité (charges fixes lourdes)."
                          if lo > 4 else "Sensibilité modérée."))
    pt = p["Position CA / point mort total"]
    if pd.notna(pt):
        phrases.append(
            f"En ajoutant les frais financiers et la rémunération attendue par les actionnaires "
            f"({pct(f['kcp'], 1)} par an, coût des capitaux propres estimé avec le bêta), on obtient le "
            f"<b>point mort total</b> : le CA {'le dépasse' if pt > 0 else 'est en dessous'} de "
            f"{pct(abs(pt), 0)}. "
            + ("L'entreprise rémunère correctement tous ses financeurs." if pt > 0 else
               "L'entreprise ne dégage pas assez pour rémunérer ses actionnaires au niveau attendu."))

    t1 = tableau_annees(f, [
        ("Chiffre d'affaires", ca, "M", ""),
        ("Marge brute", sig["Marge brute"], "M", ""),
        ("EBE (EBITDA)", sig["EBE (EBITDA)"], "M", ""),
        ("− Dotations aux amortissements", sig["Dotations aux amortissements"], "M", ""),
        ("Résultat d'exploitation (REX)", sig["Résultat d'exploitation (REX)"], "M", ""),
        ("− Frais financiers", sig["Frais financiers"], "M", ""),
        ("Résultat courant avant impôt", sig["Résultat courant avant impôt (RCAI)"], "M", ""),
        ("− Impôt sur les sociétés", sig["Impôt sur les sociétés"], "M", ""),
        ("Résultat net", sig["Résultat net"], "M", ""),
        ("Capacité d'autofinancement (CAF)", f["caf"], "M", ""),
    ], devise_titre=True)
    t2 = tableau_annees(f, [
        ("Croissance du CA", m["Croissance du CA"], "%", ""),
        ("Taux de marge brute", m["Taux de marge brute"], "%", "pouvoir de prix"),
        ("Marge d'EBE", me, "%", "ratio de référence"),
        ("Marge opérationnelle", mo, "%", ""),
        ("Marge nette", m["Marge nette"], "%", ""),
        ("CAF / CA", m["CAF / CA"], "%", ""),
    ])
    t3 = tableau_annees(f, [
        ("Charges fixes estimées", pm["Charges fixes (estimées)"], "M", ""),
        ("Taux de marge sur coûts variables", pm["Taux de marge sur coûts variables"], "%", ""),
        ("Point mort d'exploitation", pm["Point mort d'exploitation"], "M", ""),
        ("Indice de sécurité (CA / point mort)", pm["Indice de sécurité (CA / point mort)"], "x", "> 1 confortable"),
        ("Levier opérationnel (MCV / REX)", pm["Levier opérationnel (MCV / REX)"], "x", "élevé = sensible"),
        ("Point mort financier", pm["Point mort financier"], "M", "+ frais financiers"),
        ("Point mort total", pm["Point mort total"], "M", "+ rémunération actionnaires"),
        ("Écart CA / point mort total", pm["Position CA / point mort total"], "%", "> 0"),
    ])
    g1 = lecture_graphique(
        "<ul><li><b>À gauche</b> : les barres sont le chiffre d'affaires de chaque exercice, les courbes "
        "les taux de marge. Des courbes qui descendent alors que les barres montent signalent une "
        "croissance qui coûte cher.</li>"
        "<li><b>À droite</b> : produits et charges ramenés à 100 la première année. Si la courbe des "
        "charges passe au-dessus de celle des produits, c'est l'<b>effet ciseau</b> : les lames se "
        "referment sur la marge.</li></ul>")
    g2 = lecture_graphique(
        "<p>Le schéma du cours : la droite noire est le chiffre d'affaires, la rouge les coûts totaux "
        "(fixes + variables). Elles se croisent au <b>point mort</b> (pointillés bleus). À gauche, "
        "l'entreprise perd de l'argent ; à droite, elle en gagne. Le trait vert est le CA réel : "
        "plus il est loin à droite du point mort, plus l'entreprise est en sécurité.</p>")
    return n + pour_cette_action(phrases), t1 + t2, g1, t3, g2


# ---------------------------------------------------------------------------
# 7.2 Structure financière : bilan fonctionnel, BFR, investissements (partie 3)
# ---------------------------------------------------------------------------
def structure(f: dict) -> tuple:
    fo, r, inv = f["fonctionnel"], f["ratios_bfr"], f["investissements"]
    secteur_bdf = SECTEUR_BDF.get(f["secteur"])
    n = notion(
        "<p>Le <b>bilan fonctionnel</b> classe le bilan selon les grands cycles de l'entreprise :</p><ul>"
        "<li><b>Cycle long</b> (haut du bilan) : les <b>emplois stables</b> (usines, marques, "
        "équipements) doivent être financés par des <b>ressources stables</b> (capitaux propres et "
        "dettes à plus d'un an). La différence est le <b>fonds de roulement (FR)</b>, un matelas de "
        "sécurité.</li>"
        "<li><b>Cycle court</b> (exploitation) : l'entreprise paie ses fournisseurs et stocke avant "
        "d'être payée par ses clients. Ce décalage crée un <b>besoin en fonds de roulement (BFR)</b>. "
        "Un BFR négatif est une chance : les clients paient avant que l'entreprise ne règle ses "
        "fournisseurs (grande distribution, abonnements…).</li>"
        "<li><b>Trésorerie nette (TN) = FR − BFR</b> : ce qui reste quand le matelas a financé le "
        "besoin. C'est l'équation fondamentale du cours.</li>"
        "<li>On exprime le BFR <b>en jours de chiffre d'affaires</b> (BFR normatif) et on le "
        "décompose en délais : clients, stocks, fournisseurs.</li>"
        "<li>L'<b>outil industriel</b> : la <b>vétusté</b> (part de la valeur des équipements pas "
        "encore amortie) et l'effort d'<b>investissement</b> (CAPEX) comparé aux amortissements.</li></ul>")

    frv, bfrv, tnv = (dernier(fo["Fonds de roulement (FR)"]), dernier(fo["Besoin en fonds de roulement (BFR)"]),
                      dernier(fo["Trésorerie nette (TN = FR − BFR)"]))
    d = f["devise"]
    phrases = []
    if pd.notna(frv):
        phrases.append(f"Fonds de roulement {'positif' if frv > 0 else '<b>négatif</b>'} "
                       f"({num(frv / 1e6, 0)} M {d}) : les emplois stables sont "
                       + ("entièrement financés par des ressources stables "
                          + niveau("Équilibre respecté", "bon") if frv > 0 else
                          "en partie financés par du court terme " + niveau("Déséquilibre", "mauvais")) + ".")
    jours = dernier(r["BFR normatif (jours de CA)"])
    if pd.notna(bfrv):
        if bfrv < 0:
            phrases.append(f"<b>BFR négatif</b> ({num(jours, 0)} jours de CA) {niveau('Atout', 'bon')} : "
                           "l'exploitation <b>dégage</b> de la trésorerie au lieu d'en consommer.")
        else:
            rep = BFR_JOURS_BDF.get(secteur_bdf)
            comp = (f" (repère du secteur « {html.escape(secteur_bdf)} » : {rep} jours)" if rep is not None else "")
            phrases.append(f"Le BFR représente <b>{num(jours, 0)} jours de chiffre d'affaires</b>{comp} : "
                           "c'est l'argent immobilisé dans le cycle d'exploitation.")
    stock_j = dernier(r["Rotation des stocks (jours)"])
    if pd.notna(stock_j) and stock_j > 120:
        phrases.append(f"Les stocks représentent environ <b>{num(stock_j, 0)} jours</b> de coût des ventes : "
                       "un cycle de production ou de vente très long (vieillissement, collections…), "
                       "qui pèse sur le BFR.")
    if pd.notna(tnv):
        phrases.append(f"Trésorerie nette {'positive' if tnv > 0 else '<b>négative</b>'} "
                       f"({num(tnv / 1e6, 0)} M {d}) : "
                       + ("le fonds de roulement couvre le BFR." if tnv > 0 else
                          "le BFR est en partie financé par des dettes bancaires à court terme."))
    couv = dernier(r["Taux de couverture du BFR (FR / BFR)"])
    if pd.notna(couv) and pd.notna(bfrv) and bfrv > 0:
        if couv < 0.5:
            phrases.append(f"Taux de couverture du BFR de {pct(couv, 0)} {niveau('Tension', 'mauvais')} : "
                           "fortes tensions de trésorerie et dépendance bancaire (norme du cours : 70 à 80 %).")
        elif couv < 0.7:
            phrases.append(f"Taux de couverture du BFR de {pct(couv, 0)} {niveau('Juste', 'moyen')} "
                           "(norme : 70 à 80 %).")
        else:
            phrases.append(f"Taux de couverture du BFR de {pct(couv, 0)} "
                           + (f"{niveau('Conforme', 'bon')} (norme : 70 à 80 %)." if couv <= 0.8 else
                              f"{niveau('Confortable', 'bon')} : le fonds de roulement finance tout le BFR "
                              "(au-delà de la norme de 70 à 80 %)."))
    vet = dernier(inv["Vétusté (immo. nettes / brutes)"])
    if pd.notna(vet):
        phrases.append(f"Vétusté de l'outil : {pct(vet, 0)} de la valeur des équipements reste à amortir "
                       + (niveau("Outil vieillissant", "mauvais") + " (seuil d'alerte du cours : 30 %)."
                          if vet < 0.3 else niveau("Outil récent", "bon") + "." if vet > 0.5 else
                          niveau("Moyen", "moyen") + "."))
    poids = dernier(inv["Poids des invest. de croissance (CAPEX / dotations)"])
    if pd.notna(poids):
        phrases.append(f"L'entreprise investit {num(poids, 2)} fois ses dotations aux amortissements : "
                       + ("elle <b>développe</b> son outil (investissements de croissance)." if poids > 1 else
                          "elle <b>renouvelle à peine</b> son outil, voire le laisse vieillir."))
    acq = inv["Acquisitions d'entreprises (croissance externe)"].clip(lower=0).sum()
    if pd.notna(acq) and acq > 0:
        phrases.append(f"Croissance externe : {num(acq / 1e6, 0)} M {d} d'acquisitions sur la période. "
                       "Le cours rappelle les risques : intégration difficile, surpaiement, périmètre instable.")
    imm = dernier(inv["Part de l'immatériel (goodwill + incorporels / actif)"])
    if pd.notna(imm) and imm > 0.3:
        phrases.append(f"{pct(imm, 0)} de l'actif est <b>immatériel</b> (marques, écarts d'acquisition) : "
                       "des actifs difficiles à revendre, que les prêteurs financent avec réticence.")

    t1 = tableau_annees(f, [
        ("Emplois stables (actif immobilisé)", fo["Emplois stables (actif immobilisé)"], "M", ""),
        ("Ressources stables (CP + dettes > 1 an)", fo["Ressources stables (CP + dettes > 1 an)"], "M", ""),
        ("Fonds de roulement (FR)", fo["Fonds de roulement (FR)"], "M", "> 0"),
        ("Besoin en fonds de roulement (BFR)", fo["Besoin en fonds de roulement (BFR)"], "M", ""),
        ("Trésorerie nette (TN = FR − BFR)", fo["Trésorerie nette (TN = FR − BFR)"], "M", "> 0"),
    ], devise_titre=True)
    rep_bfr = (f"secteur : {BFR_JOURS_BDF[secteur_bdf]} j" if secteur_bdf in BFR_JOURS_BDF else "")
    t2 = tableau_annees(f, [
        ("BFR normatif (jours de CA)", r["BFR normatif (jours de CA)"], "j", rep_bfr),
        ("Délai clients", r["Délai clients (jours)"], "j", "loi LME : 60 j max"),
        ("Rotation des stocks", r["Rotation des stocks (jours)"], "j", ""),
        ("Délai fournisseurs", r["Délai fournisseurs (jours)"], "j", ""),
        ("Ratio de FR (RS / ES)", r["Ratio de FR (RS / ES)"], "x", "> 1"),
        ("Taux de couverture du BFR (FR / BFR)", r["Taux de couverture du BFR (FR / BFR)"], "%", "70 à 80 %"),
    ])
    t3 = tableau_annees(f, [
        ("Investissements (CAPEX)", inv["Investissements (CAPEX)"], "M", ""),
        ("Acquisitions (croissance externe)", inv["Acquisitions d'entreprises (croissance externe)"], "M", ""),
        ("Vétusté (immo. nettes / brutes)", inv["Vétusté (immo. nettes / brutes)"], "%", "< 30 % = vieillissant"),
        ("Taux d'amortissement", inv["Taux d'amortissement (amort. cumulés / brutes)"], "%", ""),
        ("Taux de renouvellement (CAPEX / immo. brutes)", inv["Taux de renouvellement (CAPEX / immo. brutes)"], "%", "industrie : 8 à 12 %"),
        ("Poids des invest. de croissance (CAPEX / dotations)", inv["Poids des invest. de croissance (CAPEX / dotations)"], "x", "> 1 = croissance"),
        ("Taux d'investissement (CAPEX / CA)", inv["Taux d'investissement (CAPEX / CA)"], "%", ""),
        ("Part de l'immatériel dans l'actif", inv["Part de l'immatériel (goodwill + incorporels / actif)"], "%", ""),
    ])
    g = lecture_graphique(
        "<ul><li><b>À gauche</b> : pour chaque exercice, le fonds de roulement (bleu), le BFR (orange) "
        "et la trésorerie nette (vert). La barre verte est toujours égale à la bleue moins l'orange. "
        "Un BFR qui grandit plus vite que le FR fait plonger la trésorerie : c'est le « dérapage » "
        "décrit dans le cours.</li>"
        "<li><b>À droite</b> : les délais en jours. La courbe noire (BFR en jours) monte quand les "
        "clients paient plus lentement ou quand les stocks s'accumulent ; elle baisse quand les "
        "fournisseurs sont payés plus tard.</li></ul>")
    return n + pour_cette_action(phrases), t1 + t2 + t3, g


# ---------------------------------------------------------------------------
# 7.3 Financement : flux, dividendes, solvabilité, liquidité (partie 4)
# ---------------------------------------------------------------------------
def financement(f: dict) -> tuple:
    fl, dv, so, li = f["flux"], f["dividendes"], f["solvabilite"], f["liquidite"]
    secteur_bdf = SECTEUR_BDF.get(f["secteur"])
    d = f["devise"]
    n = notion(
        "<ul><li><b>Flux de trésorerie disponible (FTD, ou free cash flow)</b> = EBE − impôt − "
        "variation du BFR − investissements. C'est l'argent qui reste vraiment, une fois l'activité "
        "financée, pour rembourser les prêteurs et rémunérer les actionnaires. Le ratio <b>FTD / REX</b> "
        "dit quelle part du résultat se transforme réellement en trésorerie.</li>"
        "<li><b>Autofinancement</b> = CAF − dividendes : la part des ressources gardée pour investir. "
        "Le cours oppose la <b>spirale vertueuse</b> (activité rentable → flux croissants → "
        "autofinancement → désendettement) et le <b>cercle vicieux</b> (BFR incontrôlé et "
        "investissements lourds → flux négatifs → endettement → asphyxie).</li>"
        "<li><b>Politique de dividendes</b> : le <b>taux de distribution</b> (dividende / bénéfice) "
        "arbitre entre rémunérer les actionnaires et garder des ressources pour la croissance.</li>"
        "<li><b>Solvabilité</b> : la capacité à rembourser ses dettes. Le <b>levier</b> (dette nette / "
        "EBE) dit en combien d'années d'EBE la dette pourrait être remboursée ; c'est le ratio "
        "surveillé par les banques et les agences de notation (norme : 3 au maximum).</li>"
        "<li><b>Liquidité</b> : la capacité à payer les dettes à court terme avec les actifs "
        "à court terme.</li></ul>")

    phrases = []
    ftd, rex_conv = dernier(fl["= Flux de trésorerie disponible (FTD)"]), dernier(fl["FTD / REX (transformation en trésorerie)"])
    if pd.notna(ftd):
        if ftd > 0:
            phrases.append(f"Flux de trésorerie disponible <b>positif</b> ({num(ftd / 1e6, 0)} M {d}) "
                           f"{niveau('Bon', 'bon')} : l'activité finance ses investissements et dégage un surplus.")
        else:
            phrases.append(f"Flux de trésorerie disponible <b>négatif</b> ({num(ftd / 1e6, 0)} M {d}) "
                           f"{niveau('Vigilance', 'mauvais')} : l'entreprise doit emprunter ou lever des "
                           "capitaux pour financer son activité.")
    if pd.notna(rex_conv) and rex_conv > 0:
        phrases.append(f"{pct(min(rex_conv, 9.99), 0)} du résultat d'exploitation se transforme en "
                       "trésorerie disponible" + (" : une bonne conversion." if rex_conv > 0.6 else
                                                  " : une partie est absorbée par les investissements ou le BFR."))
    taux_auto = dernier(fl["Taux d'autofinancement (autofin. / CAPEX)"])
    if pd.notna(taux_auto):
        phrases.append(f"L'autofinancement couvre {num(taux_auto, 1)} fois les investissements : "
                       + ("l'entreprise <b>n'a pas besoin de financement extérieur</b> pour investir."
                          if taux_auto >= 1 else "elle doit compléter par de la dette ou des capitaux propres."))
    payout = dernier(dv["Taux de distribution (DPA / BPA)"])
    if pd.notna(payout) and payout > 0:
        rd = f["rendement_div"]
        phrases.append(f"Elle reverse <b>{pct(payout, 0)} de son bénéfice</b> en dividendes"
                       + (f" (rendement de {pct(rd, 1)} au cours actuel)" if pd.notna(rd) else "") + ". "
                       + ("Taux élevé : peu de bénéfice conservé pour la croissance." if payout > 0.7 else
                          "Équilibre entre rémunération des actionnaires et réinvestissement."))
    elif dv["Dividende par action (DPA)"].dropna().empty:
        phrases.append("Aucun dividende versé sur la période : tout le bénéfice éventuel est conservé.")

    lev = dernier(so["Levier (DFN / EBE)"])
    if pd.notna(lev):
        if lev <= 0:
            phrases.append(f"<b>Trésorerie supérieure aux dettes financières</b> {niveau('Très solide', 'bon')} : "
                           "l'entreprise pourrait rembourser toute sa dette immédiatement.")
        else:
            ton = "bon" if lev <= 3 else "moyen" if lev <= 4.5 else "mauvais"
            phrases.append(f"Levier de <b>{num(lev, 1)}</b> {niveau('≤ 3 : conforme' if lev <= 3 else '&gt; 3 : au-delà de la norme', ton)} : "
                           f"la dette nette représente {num(lev, 1)} années d'EBE. Équivalent indicatif de "
                           f"notation (grille S&amp;P du cours) : <b>{p8.note_equivalente(lev)}</b>.")
    icr = dernier(so["Couverture des frais financiers (ICR = REX / FF)"])
    if pd.notna(icr):
        phrases.append(f"Le résultat d'exploitation couvre {num(icr, 1)} fois les frais financiers "
                       + (niveau("Alerte : &lt; 4", "mauvais") if icr < 4 else niveau("Confortable", "bon")) + ".")
    g_ = dernier(so["Gearing (DFN / CP)"])
    if pd.notna(g_) and g_ > 0:
        rep = GEARING_BDF.get(secteur_bdf)
        phrases.append(f"Gearing de {num(g_, 2)} : la dette nette représente {pct(g_, 0)} des capitaux propres "
                       + (niveau("&lt; 1 : conforme", "bon") if g_ < 1 else niveau("&gt; 1", "mauvais"))
                       + (f" (médiane du secteur « {html.escape(secteur_bdf)} » : {num(rep, 2)})" if rep else "") + ".")
    lg, lr = dernier(li["Liquidité générale"]), dernier(li["Liquidité réduite"])
    if pd.notna(lg):
        phrases.append(f"Liquidité générale de {num(lg)} : les actifs à court terme couvrent "
                       f"{'' if lg >= 1 else '<b>moins que</b> '}les dettes à court terme"
                       + (f" ; sans les stocks (liquidité réduite), le ratio tombe à {num(lr)}." if pd.notna(lr) else "."))

    t1 = tableau_annees(f, [
        ("EBE", fl["EBE"], "M", ""),
        ("− Impôt", fl["− Impôt"], "M", ""),
        ("− Variation du BFR", fl["− Variation du BFR"], "M", ""),
        ("− Investissements (CAPEX)", fl["− Investissements (CAPEX)"], "M", ""),
        ("= Flux de trésorerie disponible (FTD)", fl["= Flux de trésorerie disponible (FTD)"], "M", "> 0"),
        ("CAF", fl["Capacité d'autofinancement (CAF)"], "M", ""),
        ("− Dividendes versés", fl["Dividendes versés"], "M", ""),
        ("= Autofinancement", fl["Autofinancement (CAF − dividendes)"], "M", ""),
    ], devise_titre=True)
    t2 = tableau_annees(f, [
        ("FTD / REX", fl["FTD / REX (transformation en trésorerie)"], "%", ""),
        ("Taux d'autofinancement (autofin. / CAPEX)", fl["Taux d'autofinancement (autofin. / CAPEX)"], "x", "≥ 1"),
        ("Dividende par action", dv["Dividende par action (DPA)"], "€", ""),
        ("Bénéfice par action", dv["Bénéfice par action (BPA)"], "€", ""),
        ("Taux de distribution (DPA / BPA)", dv["Taux de distribution (DPA / BPA)"], "%", ""),
        ("Variation de la politique (ΔDPA / ΔBPA)", dv["Variation de la politique (ΔDPA / ΔBPA)"], "x", ""),
    ])
    t3 = tableau_annees(f, [
        ("Dettes financières", so["Dettes financières"], "M", ""),
        ("− Trésorerie", so["Trésorerie"], "M", ""),
        ("= Dette financière nette (DFN)", so["Dette financière nette (DFN)"], "M", ""),
        ("Capitaux propres", so["Capitaux propres"], "M", ""),
        ("Levier (DFN / EBE)", so["Levier (DFN / EBE)"], "x", "≤ 3"),
        ("Couverture du service de la dette (DSCR)", so["Couverture du service de la dette (DSCR)"], "x", "> 1,1 à 1,2"),
        ("Couverture des frais financiers (ICR)", so["Couverture des frais financiers (ICR = REX / FF)"], "x", "≥ 4"),
        ("Gearing (DFN / CP)", so["Gearing (DFN / CP)"], "x", "< 1"),
        ("Indépendance financière (CP / dettes fin.)", so["Indépendance financière (CP / dettes fin.)"], "x", ""),
        ("Liquidité générale", li["Liquidité générale"], "x", "> 1"),
        ("Liquidité réduite (hors stocks)", li["Liquidité réduite"], "x", ""),
        ("Liquidité immédiate", li["Liquidité immédiate"], "x", ""),
    ])
    g = lecture_graphique(
        "<ul><li><b>À gauche</b> : la cascade du cours, de l'EBE au flux de trésorerie disponible. "
        "Chaque barre rouge est un prélèvement (impôt, hausse du BFR, investissements) ; la barre bleue "
        "est ce qui reste réellement.</li>"
        "<li><b>À droite</b> : chaque année, ce que l'entreprise génère (CAF, en bleu), ce qu'elle "
        "investit (orange) et ce qu'elle distribue (violet). Si l'orange et le violet dépassent "
        "durablement le bleu, l'entreprise s'endette pour tenir.</li></ul>")
    return n + pour_cette_action(phrases), t1 + t2 + t3, g


# ---------------------------------------------------------------------------
# 7.4 Rentabilité (partie 5)
# ---------------------------------------------------------------------------
def rentabilite(f: dict) -> tuple:
    r = f["rentabilite"]
    n = notion(
        "<ul><li><b>Rentabilité économique (Re, ou ROIC)</b> = résultat d'exploitation après impôt / "
        "actif économique. Elle mesure ce que rapportent <b>tous</b> les capitaux engagés dans "
        "l'exploitation, quelle que soit leur origine (actionnaires ou prêteurs). L'<b>actif économique</b> "
        "= immobilisations + BFR = capitaux propres + dette nette.</li>"
        "<li>Elle se décompose en <b>marge × rotation</b> : certaines entreprises gagnent beaucoup sur "
        "chaque vente mais ont besoin de beaucoup d'actifs (modèle de <b>marge</b> : luxe, cognac, "
        "satellites) ; d'autres gagnent peu par vente mais font tourner leurs actifs très vite "
        "(modèle de <b>rotation</b> : grande distribution).</li>"
        "<li><b>Rentabilité financière (ROE)</b> = résultat net / capitaux propres de l'année "
        "précédente : ce que gagnent les <b>actionnaires</b>.</li>"
        "<li><b>Effet de levier</b> : ROE = Re + (Re − i) × Dette / Capitaux propres, où i est le "
        "coût de la dette après impôt. Si l'outil rapporte plus que ce que coûte la dette (Re &gt; i), "
        "s'endetter <b>augmente</b> la rentabilité des actionnaires. Sinon c'est l'<b>effet de "
        "massue</b> : la dette la détruit.</li></ul>")

    re_, i_, roe = dernier(r["Rentabilité économique Re (ROIC)"]), dernier(r["Coût net de la dette i"]), dernier(r["ROE observé (RN / CP n−1)"])
    marge, rot = dernier(r["Marge économique (REX × (1 − IS) / CA)"]), dernier(r["Rotation de l'actif (CA / actif éco.)"])
    phrases = []
    if pd.notna(re_):
        phrases.append(f"Rentabilité économique de <b>{pct(re_, 1)}</b> : pour 100 de capitaux engagés dans "
                       f"l'exploitation, l'entreprise dégage {num(re_ * 100, 1)} de résultat après impôt "
                       + (niveau("Élevée", "bon") if re_ > 0.12 else niveau("Correcte", "moyen") if re_ > 0.06
                          else niveau("Faible", "mauvais")) + ".")
    if pd.notna(marge) and pd.notna(rot):
        if rot > 2 and marge > 0.10:
            modele = ("un profil <b>exceptionnel</b> : fortes marges ET actifs qui tournent vite "
                      "(peu de capitaux engagés pour beaucoup de ventes)")
        elif rot > 2:
            modele = "un <b>modèle de rotation</b> (marges faibles, actifs qui tournent vite)"
        elif rot < 1 and marge > 0.10:
            modele = "un <b>modèle de marge</b> (fortes marges, actifs lourds)"
        else:
            modele = "un modèle intermédiaire entre marge et rotation"
        phrases.append(f"Décomposition : marge de {pct(marge, 1)} × rotation de {num(rot, 2)} : c'est {modele}.")
    if pd.notna(re_) and pd.notna(i_):
        if re_ > i_:
            phrases.append(f"Re ({pct(re_, 1)}) &gt; coût de la dette i ({pct(i_, 1)}) : <b>effet de levier "
                           f"positif</b> {niveau('Levier', 'bon')}, la dette augmente la rentabilité des actionnaires.")
        else:
            phrases.append(f"Re ({pct(re_, 1)}) &lt; coût de la dette i ({pct(i_, 1)}) : <b>effet de massue</b> "
                           f"{niveau('Massue', 'mauvais')}, la dette détruit de la rentabilité pour les actionnaires.")
    elif dernier(f["solvabilite"]["Dette financière nette (DFN)"]) <= 0:
        phrases.append("L'entreprise a plus de trésorerie que de dettes : il n'y a <b>pas d'effet de levier</b>. "
                       "L'actif économique est réduit par cette trésorerie, ce qui peut gonfler le ROIC.")
    if pd.notna(roe):
        cp = dernier(f["solvabilite"]["Capitaux propres"])
        if roe > 1 or (pd.notna(cp) and cp <= 0):
            phrases.append(f"ROE de {pct(roe, 0)} : chiffre <b>trompeur</b>. Les capitaux propres comptables "
                           "sont très faibles (rachats d'actions massifs ou pertes passées) ; comme le dit le "
                           "cours, le ratio perd alors sa signification.")
        else:
            rcp = dernier(r["Rcp théorique = Re + (Re − i) × D/CP"])
            phrases.append(f"ROE de <b>{pct(roe, 1)}</b> pour les actionnaires"
                           + (f" ; la formule de l'effet de levier donne {pct(rcp, 1)}, l'écart venant des "
                              "éléments non courants, des intérêts minoritaires et de l'impôt réel."
                              if pd.notna(rcp) else "."))
        kcp = f["kcp"]
        if pd.notna(roe) and roe < 1:
            phrases.append(f"Comparé au coût des capitaux propres ({pct(kcp, 1)}, rendement exigé par les "
                           "actionnaires d'après le CAPM), l'entreprise "
                           + ("<b>crée de la valeur</b> pour ses actionnaires." if roe > kcp else
                              "<b>ne crée pas assez de valeur</b> pour ses actionnaires."))
    t1 = tableau_annees(f, [
        ("Actif économique (CP + DFN)", r["Actif économique (CP + DFN)"], "M", ""),
        ("Rentabilité économique Re (ROIC)", r["Rentabilité économique Re (ROIC)"], "%", ""),
        ("ROCE (avant impôt)", r["ROCE (REX / capitaux investis)"], "%", ""),
        ("Marge économique", r["Marge économique (REX × (1 − IS) / CA)"], "%", ""),
        ("× Rotation de l'actif", r["Rotation de l'actif (CA / actif éco.)"], "x", ""),
        ("Coût net de la dette i", r["Coût net de la dette i"], "%", "< Re"),
        ("Bras de levier (DFN / CP)", r["Bras de levier (DFN / CP)"], "x", ""),
        ("Effet de levier (Re − i) × D/CP", r["Effet de levier (Re − i) × D/CP"], "%", "> 0"),
        ("ROE théorique (Re + effet de levier)", r["Rcp théorique = Re + (Re − i) × D/CP"], "%", ""),
        ("ROE observé (RN / CP n−1)", r["ROE observé (RN / CP n−1)"], "%", f"> {pct(f['kcp'], 1)}"),
        ("ROC marginal (Damodaran)", r["ROC marginal"], "%", ""),
    ], devise_titre=True)
    g = lecture_graphique(
        "<ul><li><b>À gauche</b> : le graphique « marge × rotation » vu en cours (Vernimmen). Chaque "
        "point est un exercice. Les courbes en pointillés relient toutes les combinaisons qui donnent "
        "la même rentabilité économique (5 %, 10 %, 15 %…). Un point qui se déplace vers le haut "
        "ou vers la droite améliore sa rentabilité.</li>"
        "<li><b>À droite</b> : la rentabilité économique (bleu), le coût de la dette (orange) et le "
        "ROE (vert). Quand le bleu dépasse l'orange, la dette joue en faveur des actionnaires : le "
        "vert passe au-dessus du bleu.</li></ul>")
    return n + pour_cette_action(phrases), t1, g


# ---------------------------------------------------------------------------
# Points forts / vigilance pour la synthèse générale
# ---------------------------------------------------------------------------
def points_synthese(f: dict) -> tuple:
    forts, vigil = [], []
    if not f.get("applicable"):
        return forts, vigil
    lev = dernier(f["solvabilite"]["Levier (DFN / EBE)"])
    if pd.notna(lev):
        if lev <= 1:
            forts.append(f"Endettement très faible (dette nette = {num(max(lev, 0), 1)} année d'EBE).")
        elif lev > 3:
            vigil.append(f"Endettement au-delà de la norme bancaire (dette nette = {num(lev, 1)} années d'EBE).")
    ftd = dernier(f["flux"]["= Flux de trésorerie disponible (FTD)"])
    if pd.notna(ftd):
        (forts if ftd > 0 else vigil).append(
            "Flux de trésorerie disponible " + ("positif : l'activité s'autofinance." if ftd > 0 else
                                                "négatif : l'activité consomme plus de trésorerie qu'elle n'en génère."))
    tc, tch = f["tcam_ca"], f["tcam_charges"]
    if pd.notna(tch) and tch > tc + 0.005:
        vigil.append("Effet ciseau : les charges augmentent plus vite que les ventes.")
    re_, i_ = dernier(f["rentabilite"]["Rentabilité économique Re (ROIC)"]), dernier(f["rentabilite"]["Coût net de la dette i"])
    if pd.notna(re_) and re_ > 0.12:
        forts.append(f"Rentabilité économique élevée ({pct(re_, 0)} des capitaux engagés).")
    if pd.notna(re_) and pd.notna(i_) and re_ < i_:
        vigil.append("Effet de massue : l'outil rapporte moins que ce que coûte la dette.")
    ind = dernier(f["point_mort"]["Indice de sécurité (CA / point mort)"])
    if pd.notna(ind) and ind < 1.1:
        vigil.append("Chiffre d'affaires proche (ou sous) le point mort : résultat fragile.")
    return forts, vigil


CSS = """
.t-annees td.repere { color: var(--doux); font-size: 12px; text-align: left; white-space: nowrap; }
.t-annees th.repere { text-align: left; }
.t-annees td:first-child { max-width: 320px; }
h3 { margin: 28px 0 8px; font-size: 17px; }
.sommaire { background: var(--carte); border: 1px solid var(--bord); border-radius: 10px; padding: 10px 16px; margin: 16px 0; font-size: 14px; }
.sommaire a { color: var(--accent); text-decoration: none; margin-right: 14px; white-space: nowrap; }
"""
