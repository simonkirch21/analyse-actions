"""
EXPORT — Rapport en PDF et tableaux de chiffres en Excel
=======================================================

PDF  : le rapport HTML est converti avec xhtml2pdf (bibliothèque Python, sans logiciel
       externe), après quelques adaptations pour l'impression (thème clair, chiffres clés
       en grille, calculatrice interactive retirée).
Excel: une feuille par partie (performance, CAPM, VaR, SIG, bilan fonctionnel, …),
       pour refaire ou vérifier les calculs soi-même (prérequis Excel du cours).
"""

import io
import re

import numpy as np
import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
CSS_PDF = """
:root { --fond: #ffffff; --carte: #ffffff; --texte: #10182B; --doux: #5E6574; --bord: #E2DCCE; --accent: #1B3A6B;
        --or: #A8812F; --vert: #1E8A5A; --rouge: #C2412D; --notion-fond: #ECEFF5; --lecture-fond: #F5EEDC; }
img { border-radius: 6px; }
@page { size: a4 portrait; margin: 1.4cm 1.3cm; }
body { background: #ffffff; color: #1d1d1f; font-family: Helvetica; font-size: 9.5pt; }
main { padding: 0; }
h1 { font-size: 18pt; } h2 { font-size: 14pt; -pdf-keep-with-next: true; } h3 { font-size: 11.5pt; -pdf-keep-with-next: true; }
.carte, .notion, .lecture, .verdict, .resume { padding: 7px 9px; margin: 6px 0; }
.notion { background: #eef4fd; border-left: 3px solid #0a66d8; }
.lecture { background: #f3effb; border-left: 3px solid #8a63d2; }
.verdict { background: #ffffff; border: 1px solid #e3e3e0; border-left: 3px solid #1a7f37; }
.carte, .resume { background: #ffffff; border: 1px solid #e3e3e0; }
table { width: 100%; } th, td { padding: 2px 4px; font-size: 8.5pt; }
img { width: 17.5cm; }
.kpi-table td { border: 1px solid #e3e3e0; padding: 5px; vertical-align: top; }
.kpi-table .l { color: #6b6b6b; font-size: 7pt; } .kpi-table .v { font-size: 13pt; font-weight: bold; }
.niveau { font-size: 7pt; padding: 0 4px; }
.sommaire, .calc, script { display: none; }
"""


def retirer_media(texte: str) -> str:
    """Supprime les blocs « @media … { … } » en comptant les accolades imbriquées."""
    sortie, i = [], 0
    while True:
        j = texte.find("@media", i)
        if j < 0:
            sortie.append(texte[i:])
            return "".join(sortie)
        sortie.append(texte[i:j])
        k = texte.find("{", j)
        profondeur, k = 1, k + 1
        while profondeur and k < len(texte):
            profondeur += {"{": 1, "}": -1}.get(texte[k], 0)
            k += 1
        i = k


def html_vers_pdf(page: str) -> bytes:
    from xhtml2pdf import pisa   # import ici : seulement si on exporte

    # 1. Thème clair : xhtml2pdf ignore les conditions @media et appliquerait les couleurs du
    #    mode sombre ; on retire donc tous les blocs @media.
    p = retirer_media(page)
    p = p.replace("✓ 1 point", "Oui : 1 point").replace("✗ 0 point", "Non : 0 point")
    # 2. Chiffres clés : la grille CSS n'est pas gérée -> tableau de 4 colonnes
    m = re.search(r'<div class="kpis">(.*?)</div>(?=<p class=\'note\'>)', p, flags=re.S)
    if m:
        cases = re.findall(r'<div class="kpi"[^>]*>(.*?)</div>(?=<div class="kpi"|$)', m.group(1) + "", flags=re.S)
        if not cases:
            cases = re.split(r'<div class="kpi"[^>]*>', m.group(1))[1:]
        cellules = [f"<td>{c.replace('</div></div>', '</div>')}</td>" for c in cases]
        lignes = ["<tr>" + "".join(cellules[i:i + 4]) + "</tr>" for i in range(0, len(cellules), 4)]
        p = p.replace(m.group(0), "<table class='kpi-table'>" + "".join(lignes) + "</table>")
    # 3. Éléments interactifs inutiles sur papier
    p = re.sub(r'<div class="carte calc".*?</script>', "<p class='note'>Le calculateur DCF interactif est "
               "disponible dans l'application et dans la version HTML du rapport.</p>", p, flags=re.S)
    p = re.sub(r"<script.*?</script>", "", p, flags=re.S)
    p = re.sub(r"<td><button class='btn-comparer'.*?</button></td>", "<td></td>", p, flags=re.S)
    p = re.sub(r"<p class='lien-dcf'>.*?</p>", "", p, flags=re.S)
    p = re.sub(r"<nav class='sommaire'>.*?</nav>", "", p, flags=re.S)
    p = re.sub(r"<p class='note'>Passe la souris.*?</p>", "", p, flags=re.S)
    # 4. Police complète (β, σ, ≤, →, −…) : DejaVu Sans, fournie avec matplotlib
    from pathlib import Path
    import matplotlib
    polices = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    police = (f"@font-face {{ font-family: DejaVu; src: url('{polices / 'DejaVuSans.ttf'}'); }}"
              f"@font-face {{ font-family: DejaVu; font-weight: bold; src: url('{polices / 'DejaVuSans-Bold.ttf'}'); }}"
              "body, td, th, p, li, div, span, b, h1, h2, h3 { font-family: DejaVu; }")
    p = p.replace("</style>", CSS_PDF + police + "</style>", 1)
    tampon = io.BytesIO()
    pisa.CreatePDF(p, dest=tampon, encoding="utf-8")
    return tampon.getvalue()


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------
BLEU = PatternFill("solid", fgColor="1F4E8C")
GRIS = PatternFill("solid", fgColor="EEF2F8")


def _feuille(writer, nom: str, df: pd.DataFrame, titre: str, format_nombre: str = "#,##0.00",
             note: str = "") -> None:
    """Écrit un tableau avec un titre, des en-têtes colorés et des largeurs de colonnes lisibles."""
    nom = nom[:31]                                   # limite d'Excel
    df = df.copy()
    df.index = df.index.map(str)
    df.to_excel(writer, sheet_name=nom, startrow=2 if not note else 3)
    ws = writer.sheets[nom]
    ws["A1"] = titre
    ws["A1"].font = Font(bold=True, size=13, color="1F4E8C")
    if note:
        ws["A2"] = note
        ws["A2"].font = Font(italic=True, size=9, color="6B6B6B")
    debut = 3 if not note else 4
    for cell in ws[debut]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = BLEU
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
    for ligne in ws.iter_rows(min_row=debut + 1, max_row=ws.max_row):
        ligne[0].font = Font(bold=True)
        ligne[0].fill = GRIS
        for cell in ligne[1:]:
            if isinstance(cell.value, (int, float)):
                cell.number_format = format_nombre
    ws.column_dimensions["A"].width = max(18, min(60, max(len(str(i)) for i in df.index) + 2)) if len(df) else 20
    for j in range(2, ws.max_column + 1):
        ws.column_dimensions[get_column_letter(j)].width = 16
    ws.freeze_panes = ws.cell(row=debut + 1, column=2)


def _annees(df: pd.DataFrame) -> pd.DataFrame:
    """Tableaux de la partie 8 : années en colonnes, comme dans un dossier d'analyse."""
    t = df.T
    t.columns = [str(c) for c in t.columns]
    return t


def classeur(a: dict) -> bytes:
    """Classeur Excel complet d'une analyse (résultat de analyse_complete.analyser)."""
    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as w:
        perf = {k: v for k, v in a["perf"].items() if not k.startswith("_")}
        _feuille(w, "Performance", pd.DataFrame({"Valeur": perf}), f"Performance de {a['ticker']}",
                 "0.0000", "Rendements et volatilité en décimal (0,195 = 19,5 %).")
        _feuille(w, "Rendements annuels", pd.DataFrame({"Rendement": a["annuels"]}), "Rendements par année civile", "0.0%")
        capm = {k: v for k, v in a["capm"].items() if k != "beta_ic95"}
        _feuille(w, "Marché (CAPM)", pd.DataFrame({"Valeur": {**capm, **a["relatif"]}}),
                 f"Comparaison à l'indice {a['indice']}", "0.0000")
        _feuille(w, "Risque (VaR)", a["tab_var"], "VaR et CVaR à 1 jour (pertes en décimal)", "0.00%")
        _feuille(w, "Distribution", pd.DataFrame({"Valeur": a["distrib"]}), "Forme de la distribution", "0.0000")
        _feuille(w, "Stratégies", a["tab_strat"], "Backtest des stratégies techniques", "0.0000")
        _feuille(w, "Simulation", pd.DataFrame({"Valeur": a["simu"]}), "Projection Monte Carlo à 1 an", "0.00")
        opt = a["opt"]
        _feuille(w, "Options", pd.DataFrame({"Call": opt["call"], "Put": opt["put"]}),
                 f"Options à la monnaie, 3 mois (K = {opt['K']:.2f}, σ = {opt['sigma']:.1%})", "0.0000")

        f = a.get("fin", {})
        if f.get("applicable"):
            note = f"Montants en {f['devise']} (unités). Source : Yahoo Finance, comptes IFRS."
            _feuille(w, "SIG", _annees(f["sig"]), "Soldes intermédiaires de gestion", "#,##0", note)
            _feuille(w, "Marges", _annees(f["marges"]), "Ratios de profitabilité", "0.0%")
            _feuille(w, "Point mort", _annees(f["point_mort"]), "Point mort et levier opérationnel", "#,##0.00")
            _feuille(w, "Bilan fonctionnel", _annees(f["fonctionnel"]), "Bilan fonctionnel : FR, BFR, TN", "#,##0", note)
            _feuille(w, "BFR et délais", _annees(f["ratios_bfr"]), "BFR normatif et délais (jours)", "0.0")
            _feuille(w, "Investissements", _annees(f["investissements"]), "Politique d'investissement", "#,##0.00")
            _feuille(w, "Flux de trésorerie", _annees(f["flux"]), "De l'EBE au flux de trésorerie disponible", "#,##0.00", note)
            _feuille(w, "Dividendes", _annees(f["dividendes"]), "Politique de dividendes", "0.00")
            _feuille(w, "Solvabilité", _annees(f["solvabilite"]), "Solvabilité", "#,##0.00", note)
            _feuille(w, "Liquidité", _annees(f["liquidite"]), "Ratios de liquidité", "0.00")
            _feuille(w, "Rentabilité", _annees(f["rentabilite"]), "Rentabilité économique et financière", "0.0000")
            brut = f["brut"]
            for nom, cle in [("Compte de résultat (brut)", "cr"), ("Bilan (brut)", "bilan"), ("Flux (brut)", "flux")]:
                _feuille(w, nom, brut[cle].T.dropna(how="all"), f"{nom} — données Yahoo Finance", "#,##0", note)

        v = a.get("val", {})
        if v.get("applicable"):
            _feuille(w, "Valorisation", pd.DataFrame({"Valeur": {
                **v["multiples"], "Coût des capitaux propres": v["kcp"], "Coût de la dette": v["kd"],
                "Poids des capitaux propres": v["poids_cp"], "CMPC": v["cmpc"], "Flux de départ (FCF0)": v["fcf0"],
                "Croissance 5 ans": v["g"], "Croissance à l'infini": v["g_inf"],
                "Valeur DCF par action": v["valeur_action"], "Cours": v["cours"], "Potentiel": v["potentiel"],
                **{f"Consensus — {k}": x for k, x in v["consensus"].items()}}}),
                "Valorisation : multiples, CMPC, DCF, consensus", "#,##0.0000")
            if v["sensibilite"] is not None:
                _feuille(w, "DCF sensibilité", v["sensibilite"],
                         "Valeur par action : CMPC (lignes) × croissance à l'infini (colonnes)", "0.00")
            pz = pd.DataFrame(v["piotroski"]["tests"], columns=["Domaine", "Test", "Réussi"]).set_index("Domaine")
            _feuille(w, "Piotroski", pz, f"F-score de Piotroski : {v['piotroski']['score']}/9")
            alt = pd.DataFrame(v["altman"]["details"], columns=["Composante", "Valeur", "Poids"]).set_index("Composante")
            _feuille(w, "Altman", alt, f"Z-score d'Altman {v['altman']['version']} : {v['altman']['z']:.2f} "
                                       f"({v['altman']['zone']})", "0.0000")

        prix = pd.DataFrame({"Cours ajusté": a["prix"], a["indice"]: a["prix_indice"]})
        prix.index = prix.index.date
        _feuille(w, "Cours", prix, "Historique des cours (ajustés des dividendes)", "0.00")
    return tampon.getvalue()


def classeur_portefeuille(p: dict) -> bytes:
    """Classeur Excel d'une analyse de portefeuille."""
    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as w:
        _feuille(w, "Composition", p["tableau"], "Composition du portefeuille (montants en euros)",
                 "#,##0.0000", "Poids, rendements et volatilités en décimal (0,25 = 25 %).")
        _feuille(w, "Performance", pd.DataFrame(p["stats"]), "Performance et risque comparés", "0.0000")
        _feuille(w, "Corrélations", p["corr"], "Matrice de corrélation (rendements hebdomadaires)", "0.00")
        _feuille(w, "Synthèse risque", pd.DataFrame({"Valeur": {
            "Volatilité du portefeuille": p["vol_portefeuille"],
            "Volatilité moyenne pondérée des actions": p["vol_moyenne"],
            "Gain de diversification": p["gain_diversification"],
            "Corrélation moyenne": p["corr_moyenne"], "Bêta (vs MSCI World)": p["beta"],
            "Variance minimale : rendement": p["perf_min"][0], "Variance minimale : volatilité": p["perf_min"][1],
            "Sharpe maximal : rendement": p["perf_sharpe"][0], "Sharpe maximal : volatilité": p["perf_sharpe"][1],
        }}), "Diversification et Markowitz", "0.0000")
        r = p.get("reel")
        if r and "lignes" in r:
            reel = pd.DataFrame(r["lignes"]).set_index("ticker")
            _feuille(w, "Suivi réel", reel, f"Suivi réel ({r['enveloppe']}) : impôt estimé {r['impot_vente']:,.0f} € "
                                             f"en cas de vente, net après impôt {r['net_apres_impot']:,.0f} €", "#,##0.00")
        valeurs = pd.DataFrame({"Portefeuille": p["valeur"], "Rééquilibré chaque année": p.get("reequilibre"),
                                "Poids égaux": p["equipondere"], "MSCI World": p["reference"]})
        valeurs.index = valeurs.index.date
        _feuille(w, "Valeur quotidienne", valeurs, "Valeur du portefeuille et des repères (€)", "#,##0.00")
    return tampon.getvalue()


def classeur_comparaison(c: dict) -> bytes:
    """Classeur Excel d'une comparaison : tableau côte à côte."""
    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as w:
        df = pd.DataFrame(c["lignes"], columns=["Catégorie", "Indicateur", c["t1"], c["t2"], "Meilleur"])
        df = df.set_index("Indicateur")
        _feuille(w, "Comparaison", df, f"Comparaison {c['t1']} / {c['t2']}", "0.0000")
    return tampon.getvalue()
