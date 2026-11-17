"""
QUALITÉ DES BÉNÉFICES — Les chiffres peuvent-ils mentir ?
=========================================================

Un bénéfice comptable n'est pas de l'argent : il dépend de choix (amortissements, provisions,
reconnaissance du chiffre d'affaires…). Un bénéfice « de qualité » se transforme en trésorerie.

  - Conversion en trésorerie : flux d'exploitation / résultat net (> 1 = sain)
  - Ratio d'accruals de Sloan : (résultat net − flux d'exploitation) / actif total
  - M-score de Beneish (1999) : 8 indices comptables qui, combinés, repèrent les entreprises
    susceptibles de manipuler leurs résultats (il a signalé Enron avant sa chute)
  - Goodwill : la part du bilan qui n'est que la prime payée lors d'acquisitions passées
  - Dilution : l'évolution du nombre d'actions (émissions qui diluent, ou rachats)
"""

import html
import math

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from partie8_analyse_financiere import _ligne

SEUIL_BENEISH = -1.78


def _f(x):
    try:
        x = float(x)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _d(a, b):
    a, b = _f(a), _f(b)
    return a / b if a is not None and b not in (None, 0) else None


def beneish(cr, b, fl, n, n1) -> dict:
    g = lambda df, *noms: _ligne(df, *noms)
    ventes = g(cr, "Total Revenue", "Operating Revenue")
    cout = g(cr, "Cost Of Revenue", "Reconciled Cost Of Revenue")
    creances = g(b, "Accounts Receivable", "Receivables")
    ac, pc_ = g(b, "Current Assets"), g(b, "Current Liabilities")
    immo = g(b, "Net PPE")
    ta = g(b, "Total Assets")
    amort = g(cr, "Reconciled Depreciation").fillna(g(fl, "Depreciation And Amortization"))
    sga = g(cr, "Selling General And Administration")
    dlt = g(b, "Long Term Debt", "Long Term Debt And Capital Lease Obligation").fillna(0)
    rn, cfo = g(cr, "Net Income"), g(fl, "Operating Cash Flow")
    v = lambda s, a: s.get(a)
    mb = lambda a: _d(v(ventes, a) - v(cout, a), v(ventes, a)) if v(cout, a) is not None and not pd.isna(v(cout, a)) else None
    q = lambda a: 1 - ((v(ac, a) or 0) + (v(immo, a) or 0)) / v(ta, a) if v(ta, a) else None
    dep = lambda a: _d(v(amort, a), (v(amort, a) or 0) + (v(immo, a) or 0))
    lev = lambda a: _d((v(pc_, a) or 0) + (v(dlt, a) or 0), v(ta, a))
    ind = {
        "DSRI": (_d(_d(v(creances, n), v(ventes, n)), _d(v(creances, n1), v(ventes, n1))), 0.92,
                 "Créances clients / CA : hausse = ventes peut-être gonflées (livrées mais pas encore payées)."),
        "GMI": (_d(mb(n1), mb(n)), 0.528, "Dégradation de la marge brute : une entreprise sous pression est tentée d'embellir."),
        "AQI": (_d(q(n), q(n1)), 0.404, "Part des actifs « immatériels » en hausse : des charges ont peut-être été immobilisées."),
        "SGI": (_d(v(ventes, n), v(ventes, n1)), 0.892, "Croissance du CA : la forte croissance crée des pressions pour tenir le rythme."),
        "DEPI": (_d(dep(n1), dep(n)), 0.115, "Amortissements ralentis : allonger les durées d'amortissement gonfle le bénéfice."),
        "SGAI": (_d(_d(v(sga, n), v(ventes, n)), _d(v(sga, n1), v(ventes, n1))), -0.172, "Frais commerciaux et administratifs / CA."),
        "TATA": (_d(_f(v(rn, n)) - _f(v(cfo, n)) if _f(v(rn, n)) is not None and _f(v(cfo, n)) is not None else None, v(ta, n)), 4.679,
                 "Bénéfice non encaissé (accruals) / actif : le signal le plus fort du modèle."),
        "LVGI": (_d(lev(n), lev(n1)), -0.327, "Endettement en hausse : contraintes bancaires qui poussent à afficher de bons chiffres."),
    }
    # Indices manquants : valeur neutre (1, ou 0 pour TATA), signalée
    manquants = [k for k, (x, _, _) in ind.items() if x is None]
    if len(manquants) > 3:
        return {"m": None, "manquants": manquants, "indices": ind}
    m = -4.84 + sum(c * (x if x is not None else (0 if k == "TATA" else 1)) for k, (x, c, _) in ind.items())
    return {"m": m, "manquants": manquants, "indices": ind, "annee": n}


def analyser(fin: dict) -> dict:
    if not fin or not fin.get("applicable"):
        return {"applicable": False, "raison": (fin or {}).get("raison", "Comptes indisponibles.")}
    cr, b, fl = fin["brut"]["cr"], fin["brut"]["bilan"], fin["brut"]["flux"]
    ans = fin["annees"]
    rn, cfo = _ligne(cr, "Net Income"), _ligne(fl, "Operating Cash Flow")
    capex = _ligne(fl, "Capital Expenditure")
    ta = _ligne(b, "Total Assets")
    gw = _ligne(b, "Goodwill").fillna(_ligne(b, "Goodwill And Other Intangible Assets"))
    cp = _ligne(b, "Stockholders Equity")
    actions = _ligne(b, "Ordinary Shares Number", "Share Issued")
    annees = [{"annee": int(a), "rn": _f(rn.get(a)), "cfo": _f(cfo.get(a)),
               "fcf": (_f(cfo.get(a)) + _f(capex.get(a))) if _f(cfo.get(a)) is not None and _f(capex.get(a)) is not None else None,
               "conversion": _d(cfo.get(a), rn.get(a)) if (_f(rn.get(a)) or 0) > 0 else None,
               "accruals": _d(_f(rn.get(a)) - _f(cfo.get(a)), ta.get(a)) if _f(rn.get(a)) is not None and _f(cfo.get(a)) is not None else None}
              for a in ans]
    conv = [x["conversion"] for x in annees if x["conversion"] is not None]
    bm = beneish(cr, b, fl, ans[-1], ans[-2]) if len(ans) >= 2 else {"m": None, "manquants": [], "indices": {}}
    a_ = ans[-1]
    act = [(int(a), _f(actions.get(a))) for a in ans if _f(actions.get(a))]
    dilution = None
    if len(act) >= 2:
        dilution = (act[-1][1] / act[0][1]) ** (1 / (act[-1][0] - act[0][0])) - 1 if act[-1][0] > act[0][0] else None
    return {"applicable": True, "annees": annees, "conversion_moyenne": float(np.mean(conv)) if conv else None,
            "beneish": bm, "goodwill": _f(gw.get(a_)), "goodwill_cp": _d(gw.get(a_), cp.get(a_)),
            "goodwill_actif": _d(gw.get(a_), ta.get(a_)), "dilution": dilution, "actions": act, "devise": fin.get("devise", "")}


def _p(x, d=1, signe=False):
    return "—" if x is None else f"{x * 100:{'+' if signe else ''}.{d}f} %".replace(".", ",").replace("-", "−")


def _n(x, d=2):
    return "—" if x is None else f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def graphique(q: dict, fichier: str) -> None:
    a = q["annees"]
    x = np.arange(len(a))
    fig, ax = plt.subplots(figsize=(10, 3.8))
    w = 0.38
    ax.bar(x - w / 2, [(y["rn"] or 0) / 1e9 for y in a], w, label="Résultat net (comptable)", color="#D4AF6A")
    ax.bar(x + w / 2, [(y["cfo"] or 0) / 1e9 for y in a], w, label="Flux d'exploitation (trésorerie)", color="#6EA8FF")
    ax.plot(x, [(y["fcf"] or 0) / 1e9 for y in a], "o-", color="#3BC48F", label="Flux disponible (après investissements)")
    ax.set_xticks(x)
    ax.set_xticklabels([str(y["annee"]) for y in a])
    ax.set_ylabel(f"Milliards ({q['devise']})")
    ax.axhline(0, color="#8D94A5", lw=0.8)
    ax.set_title("Le bénéfice se transforme-t-il en trésorerie ?", loc="left")
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(fichier, dpi=110)
    plt.close(fig)


def section_html(q: dict, graph: str = "") -> str:
    h = "<h2 id='qualite'>Qualité des bénéfices</h2>"
    h += ("<div class='notion'><b>La notion.</b> Le bénéfice comptable dépend de choix : durée des amortissements, provisions, "
          "moment où l'on reconnaît une vente… La trésorerie, elle, ne se discute pas. Un bénéfice <b>de qualité</b> se "
          "retrouve en cash. Quand le bénéfice grimpe mais pas la trésorerie, c'est le premier signal à creuser : les grands "
          "scandales comptables (Enron, Wirecard) affichaient de beaux bénéfices qui ne devenaient jamais de l'argent.</div>")
    if not q or not q.get("applicable"):
        return h + f"<p class='note'>{html.escape((q or {}).get('raison', 'Données indisponibles.'))}</p>"
    lect = []
    c = q["conversion_moyenne"]
    if c is not None:
        lect.append(f"Sur les exercices disponibles, chaque euro de bénéfice a produit en moyenne <b>{_n(c)} €</b> de flux d'exploitation. "
                    + ("Excellent : le bénéfice est largement encaissé (les amortissements, qui ne coûtent rien en trésorerie, y contribuent)."
                       if c >= 1.1 else "Correct." if c >= 0.85 else
                       "Faible : une partie du bénéfice n'est pas encaissée (créances, stocks qui gonflent) ; à surveiller."))
    bm = q["beneish"]
    if bm.get("m") is not None:
        m = bm["m"]
        lect.append(f"<b>M-score de Beneish : {_n(m)}</b> (seuil {_n(SEUIL_BENEISH)}). "
                    + ("En dessous du seuil : rien dans les comptes ne ressemble au profil des entreprises qui ont manipulé leurs résultats."
                       if m < SEUIL_BENEISH else
                       "<b>Au-dessus du seuil</b> : certains indices ressemblent au profil des manipulateurs. Ce n'est pas une preuve "
                       "(une forte croissance ou une acquisition suffisent à faire monter le score), mais une invitation à lire les comptes de près.")
                    + (f" (indices manquants remplacés par une valeur neutre : {', '.join(bm['manquants'])})" if bm["manquants"] else ""))
    if q["goodwill_cp"] is not None and q["goodwill"]:
        g = q["goodwill_cp"]
        lect.append(f"Le <b>goodwill</b> (prime payée lors d'acquisitions) représente {_p(g, 0)} des capitaux propres et {_p(q['goodwill_actif'], 0)} de l'actif. "
                    + ("C'est beaucoup : si ces acquisitions déçoivent, une dépréciation peut effacer une grande partie des capitaux propres d'un coup."
                       if g > 0.8 else "Niveau raisonnable."))
    if q["dilution"] is not None:
        dl = q["dilution"]
        lect.append(f"Nombre d'actions : {_p(dl, 1, True)} par an en moyenne. "
                    + ("L'entreprise <b>rachète</b> ses actions : chaque action restante représente une part plus grande du bénéfice."
                       if dl < -0.005 else "Les actionnaires sont <b>dilués</b> (émissions d'actions, stock-options) : le bénéfice par action progresse moins vite que le bénéfice."
                       if dl > 0.01 else "Stable : ni dilution ni rachats significatifs."))
    h += "<div class='lecture'>" + "".join(f"<p>{x}</p>" for x in lect) + "</div>" + graph
    if bm.get("indices"):
        lignes = "".join(f"<tr><td>{k}</td><td>{_n(x, 3)}</td><td>{_n(cf, 3)}</td><td style='text-align:left'>{html.escape(t)}</td></tr>"
                         for k, (x, cf, t) in bm["indices"].items())
        h += ("<div class='carte'><b>Détail du M-score de Beneish</b> <span class='note'>(exercice " + str(bm.get("annee", "")) + " contre le précédent ; un indice"
              " supérieur à 1 signale une dégradation)</span><table><tr><th>Indice</th><th>Valeur</th><th>Poids</th><th style='text-align:left'>Ce qu'il repère</th></tr>"
              + lignes + "</table><p class='note'>M = −4,84 + Σ poids × indice. Modèle estimé sur des entreprises industrielles américaines : "
              "moins pertinent pour les banques, assurances et entreprises en très forte croissance.</p></div>")
    lignes = "".join(f"<tr><td>{a['annee']}</td><td>{_n((a['rn'] or 0) / 1e9, 2)}</td><td>{_n((a['cfo'] or 0) / 1e9, 2)}</td>"
                     f"<td>{_n(a['conversion'])}</td><td>{_p(a['accruals'], 1)}</td></tr>" for a in q["annees"])
    h += ("<div class='carte'><table><tr><th>Exercice</th><th>Résultat net (Md)</th><th>Flux d'exploitation (Md)</th>"
          "<th>Conversion</th><th>Accruals / actif</th></tr>" + lignes + "</table></div>")
    return h
