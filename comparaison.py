"""
COMPARAISON — Deux entreprises côte à côte (l'« analyse comparative » du cours)
==============================================================================

Le cours demande d'analyser deux entreprises concurrentes d'un même secteur.
Ce module reprend tous les indicateurs des rapports individuels et les met face à face :
  - tableau côte à côte, la meilleure valeur mise en évidence ;
  - graphiques superposés ;
  - conclusion automatique par grande partie.

Lancer :  .venv/bin/python comparaison.py MC.PA KER.PA
"""

import argparse
import html
import webbrowser
from datetime import date

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import analyse_complete as ac
import interpretation as ip
import interpretation_financiere as ipf
import partie2_performance as p2

COULEURS = ("#6EA8FF", "#D4AF6A")


# ---------------------------------------------------------------------------
# Indicateurs comparés : (catégorie, libellé, fonction d'extraction, sens, format)
#   sens = +1 : plus c'est haut, mieux c'est ; −1 : plus c'est bas, mieux c'est ; 0 : neutre
# ---------------------------------------------------------------------------
def _d(f, cle, col):
    """Dernière valeur connue d'un tableau de la partie 8."""
    if not f.get("applicable"):
        return np.nan
    return ipf.dernier(f[cle][col])


def _v(a, cle):
    v = a.get("val", {})
    return v.get(cle, np.nan) if v.get("applicable") else np.nan


def _m(a, cle):
    v = a.get("val", {})
    return v["multiples"].get(cle, np.nan) if v.get("applicable") else np.nan


def _roe(a):
    r = _d(a["fin"], "rentabilite", "ROE observé (RN / CP n−1)")
    return np.nan if pd.notna(r) and abs(r) > 1 else r    # ROE > 100 % : non significatif


def _objectif(a):
    v = a.get("val", {})
    if not v.get("applicable") or not v["consensus"].get("Objectif de cours moyen"):
        return np.nan
    return v["consensus"]["Objectif de cours moyen"] / v["cours"] - 1


def _per(a):
    x = _m(a, "PER (capitalisation / résultat net)")
    return x if pd.notna(x) and x > 0 else np.nan


INDICATEURS = [
    ("Bourse", "Rendement annualisé", lambda a: a["perf"]["Rendement annualisé"], 1, "%"),
    ("Bourse", "Volatilité annualisée", lambda a: a["perf"]["Volatilité annualisée"], -1, "%"),
    ("Bourse", "Ratio de Sharpe", lambda a: a["perf"]["Sharpe"], 1, "x"),
    ("Bourse", "Ratio de Sortino", lambda a: a["perf"]["Sortino"], 1, "x"),
    ("Bourse", "Perte maximale", lambda a: a["perf"]["Max drawdown"], 1, "%"),
    ("Bourse", "Bêta", lambda a: a["capm"]["beta"], 0, "x"),
    ("Bourse", "Alpha annualisé", lambda a: a["capm"]["alpha_annuel"], 1, "%"),
    ("Risque", "VaR 95 % à 1 jour", lambda a: a["tab_var"].loc["Historique", "VaR 95%"], -1, "%"),
    ("Risque", "CVaR 95 % à 1 jour", lambda a: a["tab_var"].loc["Historique", "CVaR 95%"], -1, "%"),
    ("Risque", "Probabilité de perte à 1 an (simulation)", lambda a: a["simu"]["Probabilité de perte"], -1, "%"),
    ("Profitabilité", "Croissance annuelle moyenne du CA",
     lambda a: a["fin"].get("tcam_ca", np.nan) if a["fin"].get("applicable") else np.nan, 1, "%"),
    ("Profitabilité", "Taux de marge brute", lambda a: _d(a["fin"], "marges", "Taux de marge brute"), 1, "%"),
    ("Profitabilité", "Marge d'EBE", lambda a: _d(a["fin"], "marges", "Marge d'EBE"), 1, "%"),
    ("Profitabilité", "Marge opérationnelle", lambda a: _d(a["fin"], "marges", "Marge opérationnelle (REX / CA)"), 1, "%"),
    ("Profitabilité", "Marge nette", lambda a: _d(a["fin"], "marges", "Marge nette"), 1, "%"),
    ("Profitabilité", "Indice de sécurité (CA / point mort)",
     lambda a: _d(a["fin"], "point_mort", "Indice de sécurité (CA / point mort)"), 1, "x"),
    ("Profitabilité", "Levier opérationnel", lambda a: _d(a["fin"], "point_mort", "Levier opérationnel (MCV / REX)"), -1, "x"),
    ("Structure", "BFR normatif (jours de CA)", lambda a: _d(a["fin"], "ratios_bfr", "BFR normatif (jours de CA)"), -1, "j"),
    ("Structure", "Délai clients", lambda a: _d(a["fin"], "ratios_bfr", "Délai clients (jours)"), -1, "j"),
    ("Structure", "Rotation des stocks", lambda a: _d(a["fin"], "ratios_bfr", "Rotation des stocks (jours)"), -1, "j"),
    ("Structure", "Délai fournisseurs", lambda a: _d(a["fin"], "ratios_bfr", "Délai fournisseurs (jours)"), 0, "j"),
    ("Structure", "Vétusté de l'outil (part restant à amortir)",
     lambda a: _d(a["fin"], "investissements", "Vétusté (immo. nettes / brutes)"), 1, "%"),
    ("Structure", "Investissements / dotations",
     lambda a: _d(a["fin"], "investissements", "Poids des invest. de croissance (CAPEX / dotations)"), 0, "x"),
    ("Financement", "FTD / résultat d'exploitation",
     lambda a: _d(a["fin"], "flux", "FTD / REX (transformation en trésorerie)"), 1, "%"),
    ("Financement", "Taux d'autofinancement (autofin. / CAPEX)",
     lambda a: _d(a["fin"], "flux", "Taux d'autofinancement (autofin. / CAPEX)"), 1, "x"),
    ("Financement", "Taux de distribution des bénéfices",
     lambda a: _d(a["fin"], "dividendes", "Taux de distribution (DPA / BPA)"), 0, "%"),
    ("Financement", "Levier (dette nette / EBE)", lambda a: _d(a["fin"], "solvabilite", "Levier (DFN / EBE)"), -1, "x"),
    ("Financement", "Couverture des frais financiers (ICR)",
     lambda a: _d(a["fin"], "solvabilite", "Couverture des frais financiers (ICR = REX / FF)"), 1, "x"),
    ("Financement", "Gearing (dette nette / capitaux propres)", lambda a: _d(a["fin"], "solvabilite", "Gearing (DFN / CP)"), -1, "x"),
    ("Financement", "Liquidité générale", lambda a: _d(a["fin"], "liquidite", "Liquidité générale"), 1, "x"),
    ("Rentabilité", "Rentabilité économique (ROIC)",
     lambda a: _d(a["fin"], "rentabilite", "Rentabilité économique Re (ROIC)"), 1, "%"),
    ("Rentabilité", "ROCE", lambda a: _d(a["fin"], "rentabilite", "ROCE (REX / capitaux investis)"), 1, "%"),
    ("Rentabilité", "Marge économique", lambda a: _d(a["fin"], "rentabilite", "Marge économique (REX × (1 − IS) / CA)"), 1, "%"),
    ("Rentabilité", "Rotation de l'actif économique",
     lambda a: _d(a["fin"], "rentabilite", "Rotation de l'actif (CA / actif éco.)"), 1, "x"),
    ("Rentabilité", "ROE (rentabilité financière)", _roe, 1, "%"),
    ("Valorisation", "PER", _per, -1, "x"),
    ("Valorisation", "VE / EBE", lambda a: _m(a, "VE / EBE"), -1, "x"),
    ("Valorisation", "Cours / valeur comptable", lambda a: _m(a, "Cours / valeur comptable (P/B)"), -1, "x"),
    ("Valorisation", "Rendement du FCF", lambda a: _m(a, "Rendement du FCF (FTD / capitalisation)"), 1, "%"),
    ("Valorisation", "Rendement du dividende", lambda a: _m(a, "Rendement du dividende"), 1, "%"),
    ("Valorisation", "Écart valeur DCF / cours", lambda a: _v(a, "potentiel"), 1, "%"),
    ("Valorisation", "Écart objectif des analystes / cours", _objectif, 1, "%"),
    ("Scores", "F-score de Piotroski (sur 9)",
     lambda a: a["val"]["piotroski"]["score"] if a.get("val", {}).get("applicable") else np.nan, 1, "n"),
    ("Scores", "Z-score d'Altman",
     lambda a: a["val"]["altman"]["z"] if a.get("val", {}).get("applicable") else np.nan, 1, "x"),
]


def fmt(x, type_):
    if x is None or pd.isna(x):
        return "—"
    return {"%": ip.pct(x, 1), "j": f"{ip.num(x, 0)} j", "n": ip.num(x, 0)}.get(type_, ip.num(x, 2))


def _sur(fonction, a):
    try:
        x = fonction(a)
        return float(x) if x is not None else np.nan
    except Exception:
        return np.nan


# ---------------------------------------------------------------------------
# Comparaison
# ---------------------------------------------------------------------------
def comparer(t1: str, t2: str, periode: str = "5y", progression=print) -> dict:
    a1 = ac.analyse_en_cache(t1, periode, progression=lambda m: progression(f"{t1} — {m}"))
    a2 = ac.analyse_en_cache(t2, periode, progression=lambda m: progression(f"{t2} — {m}"))
    progression("Comparaison des deux entreprises…")

    lignes, details = [], []
    for cat, lib, fonction, sens, type_ in INDICATEURS:
        x1, x2 = _sur(fonction, a1), _sur(fonction, a2)
        meilleur = ""
        # pas de « meilleur » si les deux valeurs sont quasi égales (écart relatif < 2 %)
        proches = pd.notna(x1) and pd.notna(x2) and abs(x1 - x2) <= 0.02 * max(abs(x1), abs(x2), 1e-9)
        if sens and pd.notna(x1) and pd.notna(x2) and not proches:
            meilleur = t1 if (x1 > x2) == (sens > 0) else t2
        lignes.append((cat, lib, x1, x2, meilleur))
        details.append((cat, lib, x1, x2, meilleur, sens, type_))

    graphiques = {
        "bourse": ac.image_base64(graphique_bourse, a1, a2),
        "comptes": ac.image_base64(graphique_comptes, a1, a2),
        "structure": ac.image_base64(graphique_structure, a1, a2),
    }
    return {"t1": t1, "t2": t2, "a1": a1, "a2": a2, "periode": periode,
            "lignes": lignes, "details": details, "graphiques": graphiques}


# ---------------------------------------------------------------------------
# Graphiques superposés
# ---------------------------------------------------------------------------
def graphique_bourse(a1, a2, fichier):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.4))
    debut = max(a1["prix"].index[0], a2["prix"].index[0])
    for a, c in zip((a1, a2), COULEURS):
        p = a["prix"].loc[debut:]
        ax1.plot(p / p.iloc[0] * 100, color=c, label=a["ticker"])
        ax2.plot(p2.serie_drawdown(p) * 100, color=c, label=a["ticker"])
    ax1.set_title("Évolution du cours (base 100)")
    ax2.set_title("Drawdown : baisse depuis le plus haut (%)")
    for ax in (ax1, ax2):
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


def graphique_comptes(a1, a2, fichier):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))
    rot = np.linspace(0.05, 4, 300)
    for niveau in [0.05, 0.10, 0.15, 0.25, 0.40]:
        ax2.plot(rot, niveau / rot * 100, color="#8D94A5", lw=0.6, ls="--")
        ax2.text(3.9, niveau / 3.9 * 100, f"Re {niveau:.0%}", fontsize=7, color="#8D94A5", ha="right", va="bottom")
    ymax, xmax = 40, 4
    for a, c in zip((a1, a2), COULEURS):
        f = a["fin"]
        if not f.get("applicable"):
            continue
        m = f["marges"]
        x = [str(y) for y in f["annees"]]
        ax1.plot(x, m["Marge d'EBE"] * 100, marker="o", color=c, label=f"{a['ticker']} — marge d'EBE")
        ax1.plot(x, m["Marge nette"] * 100, marker="o", ls="--", color=c, label=f"{a['ticker']} — marge nette")
        r = f["rentabilite"]
        mx, my = r["Rotation de l'actif (CA / actif éco.)"], r["Marge économique (REX × (1 − IS) / CA)"] * 100
        ax2.plot(mx, my, color=c, marker="o", label=a["ticker"])
        for an, xx, yy in zip(f["annees"], mx, my):
            if pd.notna(xx) and pd.notna(yy):
                ax2.annotate(str(an), (xx, yy), fontsize=7, xytext=(3, 3), textcoords="offset points", color=c)
        if my.notna().any():
            ymax = max(ymax, my.max() * 1.2)
        if mx.notna().any():
            xmax = max(xmax, mx.max() * 1.15)
    ax1.set_title("Taux de marge (%)")
    ax1.axhline(0, color="#8D94A5", lw=0.5)
    ax2.set_xlim(0, xmax)
    ax2.set_ylim(0, ymax)
    ax2.set_xlabel("Rotation de l'actif économique")
    ax2.set_ylabel("Marge économique après IS (%)")
    ax2.set_title("Rentabilité économique = marge × rotation")
    for ax in (ax1, ax2):
        ax.legend(fontsize=7)
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


def graphique_structure(a1, a2, fichier):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.2))
    for a, c in zip((a1, a2), COULEURS):
        f = a["fin"]
        if not f.get("applicable"):
            continue
        x = [str(y) for y in f["annees"]]
        ax1.plot(x, f["ratios_bfr"]["BFR normatif (jours de CA)"], marker="o", color=c, label=a["ticker"])
        ax2.plot(x, f["solvabilite"]["Levier (DFN / EBE)"], marker="o", color=c, label=a["ticker"])
    ax1.set_title("BFR en jours de chiffre d'affaires")
    ax2.axhline(3, color="#FF6B5A", ls="--", lw=0.8, label="Norme du cours : 3")
    ax2.set_title("Levier : dette nette / EBE (années)")
    for ax in (ax1, ax2):
        ax.axhline(0, color="#8D94A5", lw=0.5)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Conclusion automatique
# ---------------------------------------------------------------------------
LECTURES = {
    "Bourse": "la performance et le risque du cours",
    "Risque": "le risque de perte",
    "Profitabilité": "les marges et la croissance",
    "Structure": "le cycle d'exploitation et l'outil industriel",
    "Financement": "la solidité financière et la trésorerie",
    "Rentabilité": "la rentabilité des capitaux engagés",
    "Valorisation": "le prix de l'action : l'avantage va à la moins chère",
    "Scores": "les scores de santé financière",
}


def conclusion(c: dict) -> list:
    t1, t2 = c["t1"], c["t2"]
    phrases, total = [], {t1: 0, t2: 0}
    for cat in LECTURES:
        lignes = [d for d in c["details"] if d[0] == cat and d[4]]
        if not lignes:
            continue
        v1 = sum(1 for d in lignes if d[4] == t1)
        v2 = len(lignes) - v1
        total[t1] += v1
        total[t2] += v2
        # les deux écarts les plus nets de la catégorie, pour illustrer
        def ecart(d):
            x1, x2 = d[2], d[3]
            return abs(x1 - x2) / max(abs(x1), abs(x2), 1e-9)
        gagnant = t1 if v1 >= v2 else t2
        exemples = sorted([d for d in lignes if d[4] == gagnant], key=ecart, reverse=True)[:2]
        ex = " ; ".join(f"{html.escape(d[1])} : {fmt(d[2], d[6])} contre {fmt(d[3], d[6])}" for d in exemples)
        if v1 == v2:
            phrases.append(f"<b>{cat}</b> ({LECTURES[cat]}) : <b>égalité</b> ({v1} indicateurs partout). {ex}.")
        else:
            phrases.append(f"<b>{cat}</b> ({LECTURES[cat]}) : avantage <b>{html.escape(gagnant)}</b> "
                           f"({max(v1, v2)} indicateurs sur {len(lignes)}). {ex}.")
    if total[t1] != total[t2]:
        g = t1 if total[t1] > total[t2] else t2
        phrases.append(f"Au total, <b>{html.escape(g)}</b> l'emporte sur {max(total.values())} indicateurs sur "
                       f"{sum(total.values())}. Ce décompte donne le même poids à chaque ratio : c'est un point de "
                       "départ pour l'analyse, pas une conclusion. Pour ton dossier, justifie quels critères "
                       "comptent le plus selon le secteur.")
    return phrases


# ---------------------------------------------------------------------------
# Page HTML
# ---------------------------------------------------------------------------
def generer_html(c: dict) -> str:
    t1, t2, a1, a2 = c["t1"], c["t2"], c["a1"], c["a2"]
    n1 = html.escape(a1["infos"].get("Nom") or t1)
    n2 = html.escape(a2["infos"].get("Nom") or t2)
    s1, s2 = a1["infos"].get("Secteur") or "", a2["infos"].get("Secteur") or ""

    # 1 000 € investis dans chacune, sur la période commune
    debut = max(a1["prix"].index[0], a2["prix"].index[0])
    f1 = 1000 * a1["prix"].iloc[-1] / a1["prix"].loc[debut:].iloc[0]
    f2 = 1000 * a2["prix"].iloc[-1] / a2["prix"].loc[debut:].iloc[0]

    css = ac.CSS + ip.CSS + ipf.CSS + """
    .t-comp td.gagne { font-weight: 700; color: var(--vert); }
    .t-comp td.gagne::after { content: " ●"; font-size: 9px; }
    .t-comp td.cat { background: var(--fond); font-weight: 700; color: var(--accent); text-align: left; }
    .duo { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .duo .carte { border-top: 4px solid var(--c); }
    @media (max-width: 700px) { .duo { grid-template-columns: 1fr; } }
    .liens a { color: var(--accent); margin-right: 16px; }
    """
    h = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Comparaison {html.escape(t1)} / {html.escape(t2)}</title><style>{css}</style></head><body><main>
<h1>{n1} <span class="note">vs</span> {n2}</h1>
<div class="sous-titre">Analyse comparative · période {html.escape(c['periode'])} · rapport du {date.today()}</div>
<div class="duo">"""
    for a, nom, f_, col in ((a1, n1, f1, COULEURS[0]), (a2, n2, f2, COULEURS[1])):
        dev = a["infos"].get("Devise") or ""
        h += (f"<div class='carte' style='--c:{col}'><b style='color:{col}'>{nom}</b> "
              f"<span class='note'>({html.escape(a['ticker'])} · {html.escape(a['infos'].get('Secteur') or '—')})</span>"
              f"<p>1 000 {html.escape(dev)} investis au début de la période valent aujourd'hui "
              f"<b>{ip.num(f_, 0)} {html.escape(dev)}</b> ({ip.pct(f_ / 1000 - 1, 0, signe=True)}).</p></div>")
    h += "</div>"
    h += ("<p class='liens'>Rapports complets : "
          f"<a href='{ac.nom_rapport(t1, c['periode'])}.html'>{html.escape(t1)}</a>"
          f"<a href='{ac.nom_rapport(t2, c['periode'])}.html'>{html.escape(t2)}</a></p>")

    if s1 and s2 and s1 != s2:
        h += ip.bloc("Attention : secteurs différents", (
            f"<p>{n1} est classée « {html.escape(s1)} » et {n2} « {html.escape(s2)} ». Le cours rappelle "
            "que l'analyse comparative n'a de sens qu'entre entreprises <b>similaires, d'un même secteur</b> : "
            "les niveaux de marge, de BFR ou d'endettement normaux varient beaucoup d'un secteur à l'autre.</p>"), "lecture")

    h += "<h2>Conclusion</h2>" + ip.notion(
        "<p>Pour chaque indicateur, la meilleure des deux valeurs est en <b style='color:var(--vert)'>vert</b>. "
        "« Meilleure » veut dire : plus haute pour une marge ou une rentabilité, plus basse pour un risque, "
        "une dette ou un multiple de valorisation (une action moins chère). Certains indicateurs sont "
        "neutres (le bêta, le délai fournisseurs…) : ils décrivent un profil sans être bons ou mauvais.</p>")
    h += ip.bloc("Ce qu'il faut retenir", "<ul>" + "".join(f"<li>{p}</li>" for p in conclusion(c)) + "</ul>", "verdict")

    h += "<h2>Tableau comparatif</h2><div class='carte'><table class='t-comp'>"
    h += f"<tr><th>Indicateur</th><th style='color:{COULEURS[0]}'>{html.escape(t1)}</th>" \
         f"<th style='color:{COULEURS[1]}'>{html.escape(t2)}</th></tr>"
    cat_prec = None
    for cat, lib, x1, x2, meilleur, sens, type_ in c["details"]:
        if cat != cat_prec:
            h += f"<tr><td class='cat' colspan='3'>{cat}</td></tr>"
            cat_prec = cat
        c1 = " class='gagne'" if meilleur == t1 else ""
        c2 = " class='gagne'" if meilleur == t2 else ""
        h += f"<tr><td>{html.escape(lib)}</td><td{c1}>{fmt(x1, type_)}</td><td{c2}>{fmt(x2, type_)}</td></tr>"
    h += "</table><p class='note'>Valeurs du dernier exercice disponible pour les comptes ; ROE non affiché "
    h += "s'il dépasse 100 % (capitaux propres trop faibles pour être significatifs).</p></div>"

    h += "<h2>Graphiques</h2>"
    h += ip.lecture_graphique("<p>Courbes <b style='color:#1B3A6B'>bleues</b> : " + html.escape(t1)
                              + " ; courbes <b style='color:#A8812F'>orange</b> : " + html.escape(t2) + ".</p>")
    h += "<h3>Le cours de bourse</h3>" + c["graphiques"]["bourse"]
    h += "<h3>Marges et rentabilité économique</h3>" + c["graphiques"]["comptes"]
    h += ip.lecture_graphique(
        "<p>À droite, chaque point est un exercice. Une entreprise plus haute a de meilleures marges, "
        "une entreprise plus à droite fait mieux tourner ses actifs. Les courbes en pointillés relient "
        "les combinaisons de même rentabilité économique.</p>")
    h += "<h3>BFR et endettement</h3>" + c["graphiques"]["structure"]
    h += ip.lexique()
    return h + "</main></body></html>"


def nom_fichier(t1: str, t2: str, periode: str) -> str:
    return f"comparaison_{t1}_{t2}_{periode}_{date.today()}"


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Comparer deux entreprises")
    p.add_argument("ticker1")
    p.add_argument("ticker2")
    p.add_argument("--periode", default="5y")
    p.add_argument("--sans-ouvrir", action="store_true")
    args = p.parse_args()
    c = comparer(args.ticker1.upper(), args.ticker2.upper(), args.periode)
    ac.DOSSIER_RAPPORTS.mkdir(exist_ok=True)
    fichier = ac.DOSSIER_RAPPORTS / (nom_fichier(c["t1"], c["t2"], args.periode) + ".html")
    fichier.write_text(generer_html(c), encoding="utf-8")
    print(f"\nComparaison créée : {fichier}\n")
    if not args.sans_ouvrir:
        webbrowser.open(fichier.as_uri())
