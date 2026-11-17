"""
PARTIE 7 — Analyse complète d'une action en une commande
========================================================

Assemble les parties 1 à 6 et produit un rapport HTML autonome
(un seul fichier, graphiques inclus) qui s'ouvre dans le navigateur.

Lancer :  .venv/bin/python analyse_complete.py AAPL
          .venv/bin/python analyse_complete.py MC.PA --indice ^STOXX50E
          .venv/bin/python analyse_complete.py TTE.PA --periode 10y --sans-ouvrir
"""

import argparse          # lecture propre des options de ligne de commande
import base64
import html
import pickle
import re
import tempfile
import webbrowser
from datetime import date
from pathlib import Path  # manipulation de chemins de fichiers

import numpy as np
import pandas as pd

import partie1_donnees as p1
import partie2_performance as p2
import partie3_marche as p3
import partie4_risque as p4
import partie5_technique as p5
import partie6_simulation as p6
import interpretation as ip
import partie8_analyse_financiere as p8
import interpretation_financiere as ipf
import partie9_valorisation as p9
import interpretation_valorisation as ipv
import actualites
import base_fondamentale
import note_analyse

import chemins
DOSSIER_RAPPORTS = chemins.RAPPORTS


# ---------------------------------------------------------------------------
# Petits outils de mise en forme
# ---------------------------------------------------------------------------
def pct(x, d=1):
    return "—" if x is None or pd.isna(x) else f"{x * 100:.{d}f} %".replace(".", ",")


def num(x, d=2):
    return "—" if x is None or pd.isna(x) else f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def image_base64(fonction_graphique, *args) -> str:
    """Exécute une fonction de graphique des parties précédentes dans un fichier
    temporaire, puis l'encode en base64 pour l'intégrer directement au HTML."""
    with tempfile.TemporaryDirectory() as dossier:
        chemin = Path(dossier) / "graphique.png"
        fonction_graphique(*args, str(chemin))
        donnees = base64.b64encode(chemin.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{donnees}" alt="graphique">'


def tableau(lignes: list, entetes: list = None) -> str:
    """Construit un tableau HTML à partir d'une liste de lignes."""
    h = "<table>"
    if entetes:
        h += "<tr>" + "".join(f"<th>{html.escape(str(e))}</th>" for e in entetes) + "</tr>"
    for ligne in lignes:
        h += "<tr>" + "".join(f"<td>{c}</td>" for c in ligne) + "</tr>"
    return h + "</table>"


# ---------------------------------------------------------------------------
# Analyse
# ---------------------------------------------------------------------------
def analyser(ticker: str, indice: str, periode: str, progression=print) -> dict:
    """progression : fonction appelée à chaque étape (print dans le terminal,
    mise à jour de l'écran dans l'application)."""
    progression(f"[1/6] Téléchargement de {ticker} et {indice}…")
    prix = p1.telecharger_prix(ticker, periode)
    prix_indice = p1.telecharger_prix(indice, periode)
    infos = p1.infos_entreprise(ticker)
    rend = p1.calculer_rendements(prix)
    r = rend["simple"]

    # Actualités de l'entreprise (nom court de la liste de l'application : « LVMH » plutôt que
    # « LVMH Moët Hennessy - Louis Vuitton, Société Européenne »)
    try:
        actus = actualites.par_entreprise(nom_liste(ticker) or infos.get("Nom") or ticker, ticker)
    except Exception:
        actus = {"fr": [], "en": []}

    try:
        concurrents = base_fondamentale.concurrents(ticker)
    except Exception:
        concurrents = []
    actionnaires = lire_actionnaires(ticker)

    progression("[2/6] Performance…")
    perf = p2.analyse_performance(prix)
    annuels = p2.rendements_annuels(prix)

    progression("[3/6] Comparaison au marché (CAPM)…")
    r_aligne = p3.aligner(prix, prix_indice)
    capm = p3.regression_capm(r_aligne)
    relatif = p3.autres_indicateurs(r_aligne, capm["beta"])

    progression("[4/6] Risque (VaR / CVaR)…")
    distrib = p4.statistiques_distribution(r)
    tab_var = p4.tableau_var(r)
    bt = p4.backtest_var(r)

    progression("[5/6] Analyse technique et backtest…")
    tech = p5.indicateurs(prix)
    signaux = p5.signaux_actuels(tech)
    tab_strat, courbes = p5.comparer(tech)

    progression("[6/6] Monte Carlo et options…")
    S0 = prix.iloc[-1]
    mu, sigma = p6.parametres_gbm(prix)
    chemins = p6.simuler_gbm(S0, mu, sigma)
    simu = p6.resume_simulation(S0, chemins[-1])
    opt = p6.analyse_options(S0, p6.volatilite_recente(prix))

    progression("Analyse financière des comptes de l'entreprise…")
    try:
        fin = p8.analyser(ticker, beta=capm["beta"], cours=S0)
    except Exception as erreur:     # comptes absents ou incomplets : le reste du rapport reste valable
        fin = {"applicable": False, "raison": f"Les comptes de l'entreprise n'ont pas pu être analysés ({erreur})."}
    try:
        val = p9.analyser(fin, S0, capm["beta"])
    except Exception as erreur:
        val = {"applicable": False, "raison": f"La valorisation n'a pas pu être calculée ({erreur})."}

    progression("Génération des graphiques…")
    graphiques = {
        "p1": image_base64(p1.graphique, prix, rend),
        "p2": image_base64(p2.graphique, {ticker: prix, indice: prix_indice}),
        "p3": image_base64(p3.graphique, r_aligne, capm, ticker, indice),
        "p4": image_base64(p4.graphique, r, tab_var, bt, ticker),
        "p5": image_base64(p5.graphique, tech, courbes, ticker),
        "p6": image_base64(p6.graphique, chemins, opt, ticker),
    }
    if fin["applicable"]:
        for nom, fonction in p8.GRAPHIQUES.items():
            graphiques["fin_" + nom] = image_base64(fonction, fin)
    if val["applicable"]:
        graphiques["valorisation"] = image_base64(p9.graphique, val, ticker)

    a = dict(ticker=ticker, indice=indice, periode=periode, prix=prix, infos=infos,
             prix_indice=prix_indice, fin=fin, val=val, actus=actus, concurrents=concurrents, actionnaires=actionnaires,
             perf=perf, annuels=annuels, capm=capm, relatif=relatif,
             distrib=distrib, tab_var=tab_var, bt=bt, signaux=signaux,
             tab_strat=tab_strat, mu=mu, sigma=sigma, simu=simu, opt=opt,
             graphiques=graphiques)

    # Note d'analyse : fourchettes de valeur (DCF, comparables, analystes), thèse, chiffres clés
    progression("Note d'analyse : méthodes de valorisation et comparaisons sectorielles…")
    try:
        a["note"] = note_analyse.construire(a)
        if a["note"]["fourchettes"]:
            graphiques["football"] = image_base64(note_analyse.graphique_football, a["note"])
    except Exception as erreur:
        a["note"] = None
        print("Note d'analyse impossible :", erreur)
    return a


def section_analyse_financiere(a: dict) -> str:
    """Section 7 : analyse des comptes de l'entreprise, selon le plan du cours."""
    fin, g = a["fin"], a["graphiques"]
    h = "<h2>7. Analyse financière de l'entreprise</h2>"
    if not fin["applicable"]:
        return h + ip.bloc("Analyse non disponible", f"<p>{html.escape(fin['raison'])}</p>", "lecture")
    h += ipf.introduction(fin)

    texte, tableaux, guide1, tableau_pm, guide2 = ipf.profitabilite(fin)
    h += "<h3>7.1 Profitabilité et marges</h3>" + texte + tableaux + guide1 + g["fin_profitabilite"]
    h += "<h3>Le point mort</h3>" + tableau_pm + guide2 + g["fin_point_mort"]

    texte, tableaux, guide = ipf.structure(fin)
    h += "<h3>7.2 Structure financière : bilan fonctionnel, BFR et investissements</h3>"
    h += texte + tableaux + guide + g["fin_structure"]

    texte, tableaux, guide = ipf.financement(fin)
    h += "<h3>7.3 Financement : flux de trésorerie, dividendes, solvabilité et liquidité</h3>"
    h += texte + tableaux + guide + g["fin_flux"]

    texte, tableaux, guide = ipf.rentabilite(fin)
    h += "<h3>7.4 Rentabilité économique, rentabilité financière et effet de levier</h3>"
    h += texte + tableaux + guide + g["fin_rentabilite"]
    return h


def nom_liste(ticker: str) -> str:
    """Nom de l'entreprise dans la liste de l'application (data/actions.json)."""
    try:
        import json
        liste = json.loads(chemins.liste_actions().read_text(encoding="utf-8"))
        return next((x["nom"] for x in liste if x["ticker"] == ticker), "")
    except Exception:
        return ""


def section_actualites(a: dict) -> str:
    """Derniers articles de presse sur l'entreprise (liens vers les articles)."""
    actus = a.get("actus") or {}
    fr_, en = actus.get("fr", []), actus.get("en", [])
    if not fr_ and not en:
        return ""

    def liste(articles):
        lignes = []
        for x in articles:
            date_txt = ""
            if x.get("date"):
                try:
                    date_txt = pd.Timestamp(x["date"]).strftime("%d/%m/%Y")
                except Exception:
                    pass
            lignes.append(f"<li><a href='{html.escape(x['lien'])}' target='_blank' rel='noopener'>"
                          f"{html.escape(x['titre'])}</a><span class='note'> — {html.escape(x.get('source') or '')}"
                          f"{' · ' + date_txt if date_txt else ''}</span></li>")
        return "<ul class='liste-actus'>" + "".join(lignes) + "</ul>"

    h = "<h2 id='actus'>Actualités récentes</h2>"
    h += ip.notion("<p>Le cours d'une action réagit à l'actualité : publication des résultats, annonces de "
                   "dividendes, rachats, changements de direction, contexte du secteur. Lire la presse aide à "
                   "<b>comprendre pourquoi</b> les chiffres de ce rapport évoluent. Attention : un titre de presse "
                   "n'est pas une analyse, et les informations sont souvent déjà intégrées dans le cours.</p>")
    h += "<div class='colonnes'>"
    if fr_:
        h += "<div class='carte'><b>Presse française</b>" + liste(fr_) + "</div>"
    if en:
        h += "<div class='carte'><b>Presse internationale</b> <span class='note'>(en anglais)</span>" + liste(en) + "</div>"
    h += "</div><p class='note'>Sources : Google Actualités (21 derniers jours) et Yahoo Finance. "
    h += "Les articles s'ouvrent dans ton navigateur.</p>"
    return h


def lire_actionnaires(ticker: str) -> dict:
    """Répartition du capital, principaux fonds actionnaires et transactions des dirigeants (Yahoo Finance)."""
    import yfinance as yf
    res = {}
    try:
        k = yf.Ticker(ticker)
        mh = k.major_holders
        if mh is not None and len(mh):
            v = mh.iloc[:, 0].to_dict()
            res["repartition"] = {"dirigeants": v.get("insidersPercentHeld"), "institutions": v.get("institutionsPercentHeld"),
                                  "nb_institutions": v.get("institutionsCount")}
        ih = k.institutional_holders
        if ih is not None and len(ih):
            res["fonds"] = [{"nom": l["Holder"], "part": float(l["pctHeld"]), "variation": float(l.get("pctChange") or 0),
                             "date": str(l["Date Reported"])[:10]} for _, l in ih.head(10).iterrows()]
        it = k.insider_transactions
        if it is not None and len(it):
            tr = []
            for _, l in it.head(40).iterrows():
                texte = str(l.get("Text") or "")
                genre = ("Vente" if "Sale" in texte else "Achat" if "Purchase" in texte else
                         "Attribution" if ("Award" in texte or "Grant" in texte) else "Don" if "Gift" in texte else
                         "Exercice d'options" if "Option" in texte or "Exercise" in texte else "Autre")
                tr.append({"date": str(l.get("Start Date"))[:10], "dirigeant": str(l.get("Insider") or "").title(),
                           "fonction": str(l.get("Position") or ""), "genre": genre,
                           "actions": float(l.get("Shares") or 0), "valeur": float(l.get("Value") or 0)})
            res["dirigeants"] = tr
    except Exception:
        pass
    return res


def section_actionnaires(a: dict) -> str:
    x = a.get("actionnaires") or {}
    if not x:
        return ""
    h = "<h2 id='actionnaires'>Qui détient l'action ?</h2>"
    h += ip.notion("<p>Savoir qui possède une entreprise aide à comprendre qui la contrôle et qui pèse sur son cours. "
                   "Une forte part détenue par les <b>dirigeants ou une famille</b> signifie un actionnaire de "
                   "contrôle, souvent stable et tourné vers le long terme, mais qui décide presque seul. Les "
                   "<b>investisseurs institutionnels</b> (fonds, assureurs, caisses de retraite) suivent l'entreprise "
                   "de près. Enfin, les <b>achats d'actions par les dirigeants</b> avec leur propre argent sont un signal "
                   "de confiance suivi par les marchés ; leurs ventes sont moins parlantes (impôts, diversification…).</p>")
    phrases = []
    r = x.get("repartition") or {}
    if r.get("dirigeants") is not None:
        d, i_ = r["dirigeants"], r.get("institutions") or 0
        phrases.append(f"Dirigeants et actionnaires de contrôle : <b>{pct(d, 1)}</b> du capital ; institutions : "
                       f"<b>{pct(i_, 1)}</b>" + (f" ({num(r['nb_institutions'], 0)} institutions)." if r.get("nb_institutions") else ".")
                       + (" Une famille ou un fondateur contrôle l'entreprise." if d > 0.3 else ""))
    tr = x.get("dirigeants") or []
    if tr:
        un_an = (pd.Timestamp.today() - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
        recents = [t for t in tr if t["date"] >= un_an]
        achats = [t for t in recents if t["genre"] == "Achat"]
        ventes = [t for t in recents if t["genre"] == "Vente"]
        phrases.append(f"Sur un an : <b>{len(achats)} achat(s)</b> par des dirigeants ({num(sum(t['valeur'] for t in achats) / 1e6, 1)} M) "
                       f"et <b>{len(ventes)} vente(s)</b> ({num(sum(t['valeur'] for t in ventes) / 1e6, 1)} M).")
    if phrases:
        h += ipf.pour_cette_action(phrases).replace("pour cette entreprise", "sur l'actionnariat")
    if x.get("fonds"):
        h += ("<div class='carte'><b>Principaux investisseurs institutionnels</b><table><tr><th>Investisseur</th>"
              "<th>Part du capital</th><th>Variation récente</th><th>Déclaré le</th></tr>" + "".join(
                  f"<tr><td>{html.escape(f['nom'])}</td><td>{pct(f['part'], 2)}</td>"
                  f"<td class='{'pos' if f['variation'] >= 0 else 'neg'}'>{pct(f['variation'], 1)}</td><td>{f['date']}</td></tr>"
                  for f in x["fonds"]) + "</table></div>")
    if tr:
        h += ("<div class='carte'><b>Dernières transactions des dirigeants</b><table><tr><th>Date</th><th>Dirigeant</th>"
              "<th>Fonction</th><th>Opération</th><th>Actions</th><th>Valeur</th></tr>" + "".join(
                  f"<tr><td>{t['date']}</td><td>{html.escape(t['dirigeant'])}</td><td>{html.escape(t['fonction'])}</td>"
                  f"<td class='{'pos' if t['genre'] == 'Achat' else 'neg' if t['genre'] == 'Vente' else ''}'>{t['genre']}</td>"
                  f"<td>{num(t['actions'], 0)}</td><td>{num(t['valeur'], 0)}</td></tr>" for t in tr[:10]) + "</table>"
              "<p class='note'>Déclarations publiées par l'autorité des marchés américaine (SEC) ; peu de données pour "
              "les entreprises européennes.</p></div>")
    return h


def section_concurrents(a: dict) -> str:
    """Entreprises comparables (même industrie, taille proche) avec un bouton pour les comparer."""
    c = a.get("concurrents") or []
    if not c:
        return ""
    t = html.escape(a["ticker"])
    lignes = ""
    for x in c:
        ct = html.escape(x["ticker"])
        f = lambda v, typ: "—" if v is None else (pct(v) if typ == "%" else num(v, 1))
        lignes += (f"<tr><td><b>{ct}</b> <span class='note'>{html.escape(x['nom'])}</span></td>"
                   f"<td>{html.escape(x.get('industrie') or x.get('secteur') or '')}</td>"
                   f"<td>{num((x.get('capi_eur') or 0) / 1e9, 0)} Md €</td><td>{f(x.get('per'), 'x')}</td>"
                   f"<td>{f(x.get('marge_nette'), '%')}</td><td>{f(x.get('roe'), '%')}</td>"
                   f"<td><button class='btn-comparer' data-t1='{t}' data-t2='{ct}'>Comparer</button></td></tr>")
    h = "<h2 id='concurrents'>Concurrents à comparer</h2>"
    h += ("<p class='note'>Entreprises de la même industrie (sinon du même secteur) et de taille comparable, "
          "trouvées automatiquement. Pour ton dossier, vérifie qu'elles exercent vraiment le même métier : le cours "
          "rappelle que les frontières d'un secteur sont souvent floues.</p>")
    h += ("<div class='carte'><table><tr><th>Entreprise</th><th>Industrie</th><th>Capitalisation</th><th>PER</th>"
          "<th>Marge nette</th><th>ROE</th><th></th></tr>" + lignes + "</table></div>")
    # Dans l'application, le bouton demande à la fenêtre principale de lancer la comparaison
    h += ("<script>document.querySelectorAll('.btn-comparer').forEach(b => b.addEventListener('click', () => "
          "window.parent.postMessage({type: 'comparer', t1: b.dataset.t1, t2: b.dataset.t2}, '*')));</script>")
    return h


def section_valorisation(a: dict) -> str:
    """Section 8 : l'action est-elle chère ? + scores de santé financière."""
    v = a["val"]
    h = "<h2>8. Valorisation et scores</h2>"
    if not v["applicable"]:
        return h + ip.bloc("Analyse non disponible", f"<p>{html.escape(v['raison'])}</p>", "lecture")
    texte, tableaux, guide = ipv.section_valorisation(v, a["ticker"])
    h += "<h3>8.1 L'action est-elle chère ? Multiples, CMPC et DCF</h3>" + texte + tableaux
    h += ipv.calculatrice_dcf(v) + guide + a["graphiques"]["valorisation"]
    # Dans l'application : ouvre le modèle DCF complet (scénarios, DCF inversé, export Excel)
    t = html.escape(a["ticker"], quote=True)
    h += (f"<p class='lien-dcf'><button class='btn-comparer btn-dcf' data-t='{t}'>Ouvrir le modèle DCF complet "
          "(projection année par année, scénarios, DCF inversé, Excel) →</button></p>"
          "<script>document.querySelectorAll('.btn-dcf').forEach(b => b.addEventListener('click', () => "
          "window.parent.postMessage({type: 'dcf', ticker: b.dataset.t}, '*')));</script>")
    h += "<h3>8.2 Scores de santé financière : Altman et Piotroski</h3>" + ipv.section_scores(v)
    return h


def synthese(a: dict) -> tuple:
    """Points forts / points de vigilance, déduits des indicateurs.
    Lecture pédagogique des chiffres, PAS un conseil d'investissement."""
    forts, vigilance = [], []
    perf, capm = a["perf"], a["capm"]

    if perf["Sharpe"] > 0.5:
        forts.append(f"Bonne rémunération du risque (Sharpe {num(perf['Sharpe'])}).")
    elif perf["Sharpe"] < 0:
        vigilance.append(f"A fait moins bien que le taux sans risque (Sharpe {num(perf['Sharpe'])}).")

    if a["relatif"]["Information ratio"] > 0:
        forts.append(f"A battu son indice ({pct(a['relatif']['Rendement annualisé action'])} "
                     f"contre {pct(a['relatif']['Rendement annualisé marché'])} par an).")
    else:
        vigilance.append(f"A fait moins bien que son indice "
                         f"({pct(a['relatif']['Rendement annualisé action'])} contre "
                         f"{pct(a['relatif']['Rendement annualisé marché'])} par an).")

    if perf["Max drawdown"] < -0.4:
        vigilance.append(f"Perte maximale sévère : {pct(perf['Max drawdown'])}.")
    if a["perf"]["_drawdown"]["recuperation"] is None:
        vigilance.append("L'action n'a pas encore retrouvé son plus haut de la période.")

    if capm["beta"] > 1.2:
        vigilance.append(f"Action offensive (β = {num(capm['beta'])}) : amplifie les baisses du marché.")
    elif capm["beta"] < 0.8:
        forts.append(f"Action défensive (β = {num(capm['beta'])}) : intéressante pour diversifier.")

    if capm["p_alpha"] < 0.05:
        (forts if capm["alpha_annuel"] > 0 else vigilance).append(
            f"Alpha significatif de {pct(capm['alpha_annuel'])} par an.")

    if a["distrib"]["Excès de kurtosis"] > 3:
        vigilance.append("Queues épaisses : les journées extrêmes sont bien plus fréquentes "
                         "qu'avec une loi normale.")
    if not np.isnan(a["bt"]["p-value indépendance"]) and a["bt"]["p-value indépendance"] < 0.05:
        vigilance.append("Les fortes pertes arrivent en grappes (test de Christoffersen) : "
                         "la VaR historique réagit trop lentement aux crises.")

    if "HAUSSIÈRE" in a["signaux"]["Tendance (MM50 vs MM200)"]:
        forts.append("Tendance technique de fond haussière (MM50 au-dessus de la MM200).")
    else:
        vigilance.append("Tendance technique de fond baissière (MM50 sous la MM200).")

    f_forts, f_vigil = ipf.points_synthese(a["fin"])
    v = a["val"]
    if v.get("applicable"):
        pz = v["piotroski"]["score"]
        if pd.notna(pz) and pz >= 7:
            f_forts.append(f"F-score de Piotroski de {pz}/9 : santé financière solide.")
        elif pd.notna(pz) and pz <= 3:
            f_vigil.append(f"F-score de Piotroski de {pz}/9 : signaux de faiblesse.")
        if v["altman"]["zone"] == "détresse":
            f_vigil.append("Z-score d'Altman en zone de détresse : risque de défaillance à surveiller.")
    return forts + f_forts, vigilance + f_vigil


# ---------------------------------------------------------------------------
# Rapport HTML
# ---------------------------------------------------------------------------
CSS = """
.liste-actus { margin: 8px 0 0; padding-left: 18px; }
.btn-comparer { font: inherit; font-size: 13px; padding: 4px 10px; border-radius: 8px; cursor: pointer;
                border: 1px solid var(--accent); background: none; color: var(--accent); }
.liste-actus li { margin: 7px 0; line-height: 1.4; }
.liste-actus a { color: var(--texte); text-decoration: none; }
.liste-actus a:hover { color: var(--accent); text-decoration: underline; }
/* Thème « salle des marchés » : papier ivoire et encre marine, or pour l'accent */
:root { --fond:#0A0F1C; --carte:#10182A; --texte:#ECE8DF; --doux:#8D94A5; --bord:#1E2940;
        --accent:#D4AF6A; --or:#D4AF6A; --vert:#3BC48F; --rouge:#FF6B5A; color-scheme: dark;
        --serif: "New York", ui-serif, "Iowan Old Style", Georgia, serif;
        --mono: ui-monospace, "SF Mono", Menlo, monospace; }
@media (prefers-color-scheme: dark) {
  :root { --fond:#0A0F1C; --carte:#10182A; --texte:#ECE8DF; --doux:#8D94A5; --bord:#1E2940;
          --accent:#D4AF6A; --or:#D4AF6A; --vert:#3BC48F; --rouge:#FF6B5A; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--fond); color:var(--texte);
       font: 15px/1.6 -apple-system, "Segoe UI", Roboto, sans-serif; font-variant-numeric: tabular-nums;
       -webkit-font-smoothing: antialiased; }
h1, h2, h3 { font-family: var(--serif); font-weight: 600; letter-spacing: -0.01em; }
.kpi .v { font-family: var(--mono); letter-spacing: -0.03em; font-size: 19px !important; white-space: nowrap; }
td { font-variant-numeric: tabular-nums; }
main { max-width: 1000px; margin: 0 auto; padding: 24px 16px 60px; }
h1 { margin: 0 0 4px; font-size: 30px; }
h2 { margin: 44px 0 12px; font-size: 22px; padding-bottom: 6px; border-bottom: 1px solid var(--bord);
     background: linear-gradient(var(--or), var(--or)) left bottom / 56px 2px no-repeat; }
.sous-titre { color: var(--doux); margin-bottom: 20px; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.kpi { background: var(--carte); border: 1px solid var(--bord); border-radius: 12px; padding: 12px;
       box-shadow: 0 1px 2px rgba(16,24,43,.05); }
.kpi .v { font-size: 22px; font-weight: 600; }
.kpi .l { color: var(--doux); font-size: 12px; text-transform: uppercase; letter-spacing: .03em; }
.carte { background: var(--carte); border: 1px solid var(--bord); border-radius: 12px;
         padding: 16px; margin: 12px 0; overflow-x: auto; }
.colonnes { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 700px) { .colonnes { grid-template-columns: 1fr; } }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { padding: 6px 10px; border-bottom: 1px solid var(--bord); text-align: right; }
th:first-child, td:first-child { text-align: left; }
th { color: var(--doux); font-weight: 500; }
img { width: 100%; height: auto; border-radius: 6px; }
.fort li::marker { color: var(--vert); }
.vigil li::marker { color: var(--rouge); }
.pos { color: var(--vert); } .neg { color: var(--rouge); }
.note { color: var(--doux); font-size: 13px; }
"""


def signe(x, texte):
    return f'<span class="{"pos" if x >= 0 else "neg"}">{texte}</span>'


KPI_EXPLIQUES = {"Volatilité": "volatilite", "Sharpe": "sharpe", "Perte maximale": "drawdown", "Bêta": "beta"}


def _x(a: dict, libelle: str) -> str:
    """Rend une tuile cliquable (« d'où vient ce chiffre ? ») si la note d'analyse l'explique."""
    cle = KPI_EXPLIQUES.get(libelle)
    n = a.get("note")
    if cle and n and any(c["cle"] == cle for c in n["chiffres"]):
        return f' data-x="{cle}" tabindex="0" role="button"'
    return ""


def generer_html(a: dict) -> str:
    t, i = html.escape(a["ticker"]), html.escape(ip.nom_indice(a["indice"]))
    infos, perf, capm, rel = a["infos"], a["perf"], a["capm"], a["relatif"]
    prix = a["prix"]
    nom = html.escape(infos.get("Nom") or t)
    devise = infos.get("Devise") or ""
    forts, vigilance = synthese(a)
    pastilles = ip.pastilles_kpi(a)

    # --- En-tête et chiffres clés
    kpis = [
        ("Dernier cours", f"{num(prix.iloc[-1])} {devise}"),
        ("Rendement annualisé", signe(perf["Rendement annualisé"], pct(perf["Rendement annualisé"]))),
        ("Volatilité", pct(perf["Volatilité annualisée"])),
        ("Sharpe", num(perf["Sharpe"])),
        ("Perte maximale", pct(perf["Max drawdown"])),
        ("Bêta", num(capm["beta"])),
        ("VaR 95 % 1 jour", pct(a["tab_var"].loc["Historique", "VaR 95%"])),
        ("P(perte) à 1 an", pct(a["simu"]["Probabilité de perte"], 0)),
    ]
    h = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="data:,"><title>Analyse {t}</title><style>{CSS}{ip.CSS}{ipf.CSS}{ipv.CSS}{note_analyse.CSS}</style></head><body><main>
<h1>{nom} <span class="note">({t})</span></h1>
<div class="sous-titre">{html.escape(str(infos.get('Secteur') or ''))}
 · {html.escape(str(infos.get('Pays') or ''))} · indice de référence {i}
 · données du {prix.index[0].date()} au {prix.index[-1].date()} · rapport du {date.today()}</div>
<div class="kpis">""" + "".join(
        f'<div class="kpi"{_x(a, l)} title="{html.escape(ip.AIDE_KPI.get(l, ""))}"><div class="l">{l}</div>'
        f'<div class="v">{v}</div>{pastilles.get(l, "")}</div>' for l, v in kpis
    ) + "</div>"
    h += ("<p class='note'>Passe la souris sur un chiffre pour voir sa définition (clique sur ceux encadrés d'or au survol pour le détail du calcul). "
          "Chaque partie commence par une explication de la notion, puis ce qu'il faut "
          "retenir pour cette action, puis les chiffres détaillés et les graphiques.</p>")
    h += ip.resume_debutant(a)
    h += ("<nav class='sommaire'><b>Sommaire :</b> " + ("<a href='#note'>Note d'analyse</a>" if a.get("note") else "") + "<a href='#synthese'>Synthèse</a><a href='#actus'>Actualités</a><a href='#concurrents'>Concurrents</a><a href='#actionnaires'>Actionnaires</a>"
          "<a href='#s1'>1. Données</a><a href='#s2'>2. Performance</a><a href='#s3'>3. Marché</a>"
          "<a href='#s4'>4. Risque</a><a href='#s5'>5. Technique</a><a href='#s6'>6. Simulation</a>"
          "<a href='#s7'>7. Analyse financière de l'entreprise</a>"
          "<a href='#s8'>8. Valorisation et scores</a></nav>")

    h += note_analyse.section_html(a)

    # --- Synthèse
    h += "<h2>Synthèse</h2><div class='colonnes'>"
    h += "<div class='carte'><b>Points forts</b><ul class='fort'>" + \
         "".join(f"<li>{x}</li>" for x in forts or ["Aucun point fort marquant."]) + "</ul></div>"
    h += "<div class='carte'><b>Points de vigilance</b><ul class='vigil'>" + \
         "".join(f"<li>{x}</li>" for x in vigilance or ["Aucun point de vigilance marquant."]) + \
         "</ul></div></div>"
    h += ("<p class='note'>Lecture automatique des indicateurs, à but pédagogique. "
          "Les performances passées ne préjugent pas des performances futures ; "
          "ce rapport n'est pas un conseil d'investissement.</p>")

    h += section_actualites(a)
    h += section_concurrents(a)
    h += section_actionnaires(a)

    # --- 1. Données
    capi = infos.get("Capitalisation")
    texte, guide = ip.section_donnees(a)
    h += "<h2>1. Données</h2>" + texte + "<div class='carte'>" + tableau([
        ["Capitalisation", f"{num(capi / 1e9, 1)} Md {devise}" if capi else "—"],
        ["PER", num(infos.get("PER"))],
        ["Nombre de séances", str(len(prix))],
        ["Performance totale", signe(prix.iloc[-1] / prix.iloc[0] - 1,
                                     pct(prix.iloc[-1] / prix.iloc[0] - 1))],
    ]) + "</div>" + guide + a["graphiques"]["p1"]

    # --- 2. Performance
    dd = perf["_drawdown"]
    recup = dd["recuperation"].date() if dd["recuperation"] is not None else "pas encore"
    lignes = [
        ["Rendement annualisé (CAGR)", pct(perf["Rendement annualisé"])],
        ["Volatilité annualisée", pct(perf["Volatilité annualisée"])],
        ["Ratio de Sharpe", num(perf["Sharpe"])],
        ["Ratio de Sortino", num(perf["Sortino"])],
        ["Perte maximale", f"{pct(perf['Max drawdown'])} ({dd['sommet'].date()} → {dd['creux'].date()}, "
                           f"récupération : {recup})"],
        ["Ratio de Calmar", num(perf["Calmar"])],
        ["Meilleur / pire jour", f"{pct(perf['Meilleur jour'])} / {pct(perf['Pire jour'])}"],
        ["Jours positifs", pct(perf["% jours positifs"])],
    ]
    annuels = [[str(an), signe(v, pct(v))] for an, v in a["annuels"].items()]
    texte, guide = ip.section_performance(a)
    h += "<h2>2. Performance</h2>" + texte + "<div class='colonnes'>"
    h += "<div class='carte'>" + tableau(lignes) + "</div>"
    h += "<div class='carte'>" + tableau(annuels, ["Année", "Rendement"]) + "</div></div>"
    h += f"<p class='note'>Taux sans risque : {pct(p2.TAUX_SANS_RISQUE, 0)}. "\
         "La première et la dernière année sont partielles.</p>" + guide + a["graphiques"]["p2"]

    # --- 3. Marché
    lo, hi = capm["beta_ic95"]
    texte, guide = ip.section_marche(a)
    h += f"<h2>3. Comparaison au marché ({i})</h2>" + texte + \
         "<div class='colonnes'><div class='carte'>" + tableau([
        ["Bêta", f"{num(capm['beta'])} (IC 95 % : {num(lo)} – {num(hi)})"],
        ["Alpha annualisé", f"{pct(capm['alpha_annuel'])} (p = {num(capm['p_alpha'], 3)})"],
        ["Corrélation", num(capm["correlation"])],
        ["R² (risque systématique)", pct(capm["r2"], 0)],
    ]) + "</div><div class='carte'>" + tableau([
        ["Rendement action / marché", f"{pct(rel['Rendement annualisé action'])} / "
                                      f"{pct(rel['Rendement annualisé marché'])}"],
        ["Tracking error", pct(rel["Tracking error"])],
        ["Information ratio", num(rel["Information ratio"])],
        ["Ratio de Treynor", pct(rel["Treynor"])],
        ["Capture hausse / baisse", f"{num(rel['Capture hausse'])} / {num(rel['Capture baisse'])}"],
    ]) + "</div></div>"
    h += ("<p class='note'>Si l'indice est un indice de prix (sans dividendes, ex. ^FCHI) alors que "
          "l'action est en dividendes réinvestis, l'alpha est légèrement surestimé.</p>")
    h += guide + a["graphiques"]["p3"]

    # --- 4. Risque
    d, bt = a["distrib"], a["bt"]
    tv = a["tab_var"]
    texte, guide = ip.section_risque(a)
    h += "<h2>4. Risque de perte</h2>" + texte + "<div class='carte'>" + tableau(
        [[m] + [pct(tv.loc[m, c], 2) for c in tv.columns] for m in tv.index],
        ["Méthode (1 jour)"] + list(tv.columns)) + "</div>"
    h += "<div class='colonnes'><div class='carte'>" + tableau([
        ["Asymétrie", num(d["Asymétrie (skewness)"])],
        ["Excès de kurtosis", num(d["Excès de kurtosis"])],
        ["Jarque-Bera (p-value)", num(d["Jarque-Bera (p-value)"], 4)],
        ["Normalité", "rejetée" if d["Jarque-Bera (p-value)"] < 0.05 else "non rejetée"],
    ]) + "</div><div class='carte'>" + tableau([
        ["Exceptions VaR 95 %", f"{bt['exceptions']} / {bt['jours testés']} ({pct(bt['taux observé'])})"],
        ["Kupiec (nombre)", f"p = {num(bt['p-value'], 3)} → {'validé' if bt['valide'] else 'rejeté'}"],
        ["Christoffersen (indépendance)",
         f"p = {num(bt['p-value indépendance'], 3)} → "
         f"{'indépendantes' if bt['p-value indépendance'] > 0.05 else 'en grappes'}"],
    ]) + "</div></div>" + guide + a["graphiques"]["p4"]

    # --- 5. Technique
    ts = a["tab_strat"]
    texte, guide = ip.section_technique(a)
    h += "<h2>5. Analyse technique et stratégies</h2>" + texte + "<div class='carte'>" + tableau(
        [[k, html.escape(ip.chiffre_fr(v) if "%" in v else v)] for k, v in a["signaux"].items()]) + "</div>"
    h += "<div class='carte'>" + tableau(
        [[s, pct(ts.loc[s, "Rendement annualisé"]), pct(ts.loc[s, "Volatilité"]),
          num(ts.loc[s, "Sharpe"]), pct(ts.loc[s, "Max drawdown"]),
          pct(ts.loc[s, "Temps investi"], 0), str(int(ts.loc[s, "Nb transactions"]))]
         for s in ts.index],
        ["Stratégie", "Rdt annualisé", "Volatilité", "Sharpe", "Perte max",
         "Temps investi", "Transactions"]) + "</div>"
    h += (f"<p class='note'>Frais de {pct(p5.FRAIS)} par transaction ; signal exécuté le "
          "lendemain ; hors marché, l'argent est rémunéré au taux sans risque.</p>")
    h += guide + a["graphiques"]["p5"]

    # --- 6. Simulation et options
    s, o = a["simu"], a["opt"]
    texte, guide = ip.section_simulation(a)
    h += "<h2>6. Simulation Monte Carlo et options</h2>" + texte + \
         "<div class='colonnes'><div class='carte'>"
    h += f"<b>Projection à 1 an</b> <span class='note'>(μ = {pct(a['mu'])}, σ = {pct(a['sigma'])})</span>"
    h += tableau([
        ["Prix médian", num(s["Prix médian à 1 an"])],
        ["Intervalle 90 %", f"{num(s['Percentile 5 %'])} – {num(s['Percentile 95 %'])}"],
        ["Probabilité de perte", pct(s["Probabilité de perte"])],
        ["Probabilité de +20 %", pct(s["Probabilité de +20 %"])],
    ]) + "</div><div class='carte'>"
    h += (f"<b>Options à la monnaie, 3 mois</b> <span class='note'>(K = {num(o['K'])}, "
          f"σ 1 an = {pct(o['sigma'])})</span>")
    h += tableau([[g, num(o["call"][g], 4), num(o["put"][g], 4)] for g in o["call"]],
                 ["", "Call", "Put"])
    h += "</div></div><div class='carte'>" + tableau([
        ["Call — Black-Scholes", num(o["call"]["Prix"], 4)],
        ["Call — Monte Carlo (IC 95 %)", f"{num(o['mc_call'], 4)} ({num(o['ic_call'][0], 4)} – "
                                         f"{num(o['ic_call'][1], 4)})"],
        ["Call — arbre binomial (500 pas)", num(o["bin_call"], 4)],
        ["Put américain — binomial", f"{num(o['bin_put_us'], 4)} (prime d'exercice anticipé "
                                     f"{num(o['bin_put_us'] - o['bin_put_eu'], 4)})"],
    ]) + "</div>"
    h += ("<p class='note'>μ est estimé sur le passé : la projection illustre le modèle, "
          "ce n'est pas une prévision.</p>") + guide + a["graphiques"]["p6"]

    h += section_analyse_financiere(a)
    h += section_valorisation(a)
    h += ip.lexique()
    # Ancres pour le sommaire : <h2>1. ...</h2> -> <h2 id="s1">1. ...</h2>
    h = re.sub(r"<h2>(\d)\. ", lambda m: f"<h2 id='s{m.group(1)}'>{m.group(1)}. ", h)
    h = h.replace("<h2>Synthèse</h2>", "<h2 id='synthese'>Synthèse</h2>")
    return h + "</main></body></html>"


def nom_rapport(ticker: str, periode: str) -> str:
    return f"{ticker}_{periode}_{date.today()}"


def analyse_en_cache(ticker: str, periode: str = "5y", indice: str = None, progression=print,
                     forcer: bool = False) -> dict:
    """Analyse une action, enregistre le rapport HTML et garde les résultats du jour en cache
    (fichier .pkl) : une comparaison ou un export n'ont pas à tout recalculer."""
    indice = (indice or p3.indice_par_defaut(ticker)).upper()
    DOSSIER_RAPPORTS.mkdir(exist_ok=True)
    # (pas de with_suffix : « MC.PA_5y » serait lu comme un fichier d'extension « .PA_5y »)
    base = str(DOSSIER_RAPPORTS / nom_rapport(ticker, periode))
    cache, page = Path(base + ".pkl"), Path(base + ".html")
    if cache.exists() and page.exists() and not forcer:
        with open(cache, "rb") as fichier:
            return pickle.load(fichier)
    a = analyser(ticker, indice, periode, progression)
    page.write_text(generer_html(a), encoding="utf-8")
    with open(cache, "wb") as fichier:
        pickle.dump(a, fichier)
    return a


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyse financière complète d'une action")
    parser.add_argument("ticker", help="ex. AAPL, MC.PA, TTE.PA")
    parser.add_argument("--indice", help="indice de référence (par défaut selon la place)")
    parser.add_argument("--periode", default="5y", help="1y, 2y, 5y, 10y, max (défaut 5y)")
    parser.add_argument("--sans-ouvrir", action="store_true", help="ne pas ouvrir le navigateur")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    indice = (args.indice or p3.indice_par_defaut(ticker)).upper()

    print(f"\n=== Analyse complète de {ticker} (référence {indice}, {args.periode}) ===\n")
    try:
        analyse_en_cache(ticker, args.periode, indice, forcer=True)
    except ValueError as erreur:          # ticker inconnu, pas de données...
        raise SystemExit(f"\nErreur : {erreur}\n"
                         "Exemples de tickers : AAPL, MSFT, MC.PA, TTE.PA, AIR.PA, SAP.DE\n")

    fichier = DOSSIER_RAPPORTS / (nom_rapport(ticker, args.periode) + ".html")
    print(f"\nRapport créé : {fichier}\n")

    if not args.sans_ouvrir:
        webbrowser.open(fichier.as_uri())
