"""
INTERPRÉTATION de la partie 9 : valorisation (multiples, CMPC, DCF interactif, consensus)
et scores de santé financière (Altman, Piotroski).
"""

import html
import json

import numpy as np
import pandas as pd

from interpretation import pct, num, notion, lecture_graphique, niveau, bloc
from interpretation_financiere import pour_cette_action

RECOMMANDATIONS = {"strong_buy": "achat fort", "buy": "achat", "hold": "conserver",
                   "underperform": "sous-performance", "sell": "vente", "strong_sell": "vente forte",
                   "none": "aucune"}


def _x(v, d=1):
    return "n.s." if v is None or pd.isna(v) or v <= 0 else num(v, d)


def section_valorisation(v: dict, ticker: str) -> tuple:
    m, c = v["multiples"], v["consensus"]
    dc = v["devise_cours"]
    n = notion(
        "<p>Une bonne entreprise n'est pas forcément un bon placement : tout dépend du <b>prix</b> "
        "payé. La valorisation cherche à savoir si l'action est <b>chère ou bon marché</b>.</p><ul>"
        "<li><b>Multiples</b> : on compare le prix à ce que l'entreprise gagne. Le <b>PER</b> "
        "(cours / bénéfice) dit combien d'années de bénéfice actuel on paie ; le <b>VE / EBE</b> "
        "fait pareil en incluant la dette (VE = valeur d'entreprise = capitalisation + dette nette). "
        "Un multiple élevé signifie que le marché attend une forte croissance, ou que l'action est chère. "
        "Il faut toujours les comparer à des concurrents.</li>"
        "<li><b>CMPC</b> (coût moyen pondéré du capital, ou WACC) : le rendement minimum exigé par "
        "l'ensemble des financeurs, actionnaires (coût des capitaux propres, via le CAPM) et prêteurs "
        "(coût de la dette après impôt), pondérés par leur poids.</li>"
        "<li><b>DCF</b> (actualisation des flux de trésorerie) : la valeur d'une entreprise est la "
        "somme de tout l'argent qu'elle générera dans le futur, « ramené en euros d'aujourd'hui » au "
        "taux du CMPC. On prévoit 5 années, puis une <b>valeur terminale</b> pour la suite (croissance "
        "constante à l'infini). C'est la méthode du VAN vue en cours, appliquée à toute l'entreprise.</li>"
        "</ul>")

    phrases = []
    per = m["PER (capitalisation / résultat net)"]
    if pd.notna(per) and per > 0:
        lec = ("bas" if per < 12 else "dans la moyenne" if per <= 25 else "élevé")
        phrases.append(f"PER de <b>{num(per, 1)}</b> ({lec}) : on paie {num(per, 0)} années de bénéfice actuel. "
                       f"VE / EBE de {_x(m['VE / EBE'])}.")
    else:
        phrases.append("PER non significatif : l'entreprise est en perte sur le dernier exercice.")
    fcfy = m["Rendement du FCF (FTD / capitalisation)"]
    if pd.notna(fcfy):
        phrases.append(f"Rendement du flux de trésorerie disponible : <b>{pct(fcfy, 1)}</b> par an "
                       "(l'argent généré rapporté au prix de l'entreprise ; à comparer au taux sans risque de 3 %).")
    phrases.append(f"CMPC estimé à <b>{pct(v['cmpc'], 1)}</b> : coût des capitaux propres {pct(v['kcp'], 1)} "
                   f"(bêta {num(v['beta'])}), coût de la dette {pct(v['kd'], 1)} avant impôt, "
                   f"{pct(v['poids_cp'], 0)} de capitaux propres dans le financement.")
    if pd.notna(v["valeur_action"]):
        pot = v["potentiel"]
        if v["valeur_action"] <= 0:
            phrases.append("Le DCF donne une valeur <b>négative</b> : avec ces hypothèses, les flux futurs ne "
                           "suffisent pas à couvrir la dette. Le résultat est très sensible aux hypothèses.")
        else:
            ton = "bon" if pot > 0.15 else "mauvais" if pot < -0.15 else "moyen"
            lib = "Sous-évaluée ?" if pot > 0.15 else "Surévaluée ?" if pot < -0.15 else "Proche du cours"
            phrases.append(f"Valeur DCF : <b>{num(v['valeur_action'], 2)} {dc}</b> par action, contre un cours de "
                           f"{num(v['cours'], 2)} {dc} ({pct(pot, 0, signe=True)}) {niveau(lib, ton)}.")
            if pot < -0.3:
                phrases.append("Un tel écart signifie surtout que <b>le marché anticipe une croissance bien "
                               f"supérieure</b> aux {pct(v['g'], 1)} par an retenus (la croissance passée). "
                               "Utilise les curseurs ci-dessous pour trouver la croissance qui justifie le cours.")
        if v["dcf"] and v["dcf"]["part_vt"] > 0.7:
            phrases.append(f"{pct(v['dcf']['part_vt'], 0)} de la valeur vient de la <b>valeur terminale</b> "
                           "(au-delà de 5 ans) : le résultat dépend beaucoup d'hypothèses lointaines.")
    else:
        phrases.append("DCF non calculable : les flux de trésorerie disponibles récents sont négatifs.")
    if c.get("Objectif de cours moyen") and c.get("Nombre d'analystes"):
        rec = RECOMMANDATIONS.get(c.get("Recommandation") or "none", c.get("Recommandation"))
        ecart = c["Objectif de cours moyen"] / v["cours"] - 1
        phrases.append(f"Les {c['Nombre d\'analystes']} analystes qui suivent l'action visent en moyenne "
                       f"<b>{num(c['Objectif de cours moyen'], 2)} {dc}</b> ({pct(ecart, 0, signe=True)}), "
                       f"recommandation moyenne : « {html.escape(str(rec))} »"
                       + (". Un seul analyste : avis peu représentatif." if c["Nombre d'analystes"] == 1 else "."))

    # Tableaux
    lignes = [
        ("Capitalisation boursière", f"{num(m['Capitalisation boursière'] / 1e6, 0)} M {v['devise_compta']}"),
        ("Valeur d'entreprise (capitalisation + dette nette)",
         f"{num(m['Valeur d\'entreprise (VE = capitalisation + DFN)'] / 1e6, 0)} M {v['devise_compta']}"),
        ("PER", _x(per)), ("PER prévisionnel (consensus)", _x(m["PER prévisionnel (consensus)"])),
        ("VE / EBE", _x(m["VE / EBE"])), ("VE / CA", _x(m["VE / CA"], 2)),
        ("Cours / valeur comptable", _x(m["Cours / valeur comptable (P/B)"], 2)),
        ("Rendement du FCF", pct(fcfy, 1)), ("Rendement du dividende", pct(m["Rendement du dividende"], 1)),
    ]
    t1 = "<div class='carte'><table>" + "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in lignes) + "</table></div>"
    hyp = [
        ("Flux de départ (moyenne des 3 derniers FTD)", f"{num(v['fcf0'] / 1e6, 0)} M {v['devise_compta']}"),
        ("Croissance des 5 prochaines années", f"{pct(v['g'], 1)} (croissance passée du CA, bornée entre 0 et 12 %)"),
        ("Croissance à l'infini", pct(v["g_inf"], 1)),
        ("CMPC (taux d'actualisation)", pct(v["cmpc"], 2)),
        ("Dette financière nette déduite", f"{num(v['dfn'] / 1e6, 0)} M {v['devise_compta']}"),
        ("Nombre d'actions", f"{num(v['actions'] / 1e6, 1)} millions"),
    ]
    t2 = "<div class='carte'><b>Hypothèses du DCF</b><table>" + "".join(
        f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in hyp) + "</table></div>"
    t3 = ""
    if v["sensibilite"] is not None:
        s = v["sensibilite"]
        t3 = ("<div class='carte'><b>Sensibilité de la valeur par action</b> "
              "<span class='note'>(lignes : CMPC ; colonnes : croissance à l'infini)</span><table><tr><th></th>"
              + "".join(f"<th>{html.escape(col).replace('.', ',').replace('%', ' %')}</th>" for col in s.columns) + "</tr>"
              + "".join("<tr><td>" + html.escape(i).replace(".", ",").replace("%", " %") + "</td>" + "".join(
                  f"<td class='{'pos' if x >= v['cours'] else 'neg'}'>{num(x, 1)}</td>" for x in row) + "</tr>"
                  for i, row in zip(s.index, s.values))
              + "</table><p class='note'>En vert : valeur supérieure au cours actuel. "
                "Une petite variation d'hypothèse change beaucoup le résultat : un DCF est un "
                "<b>ordre de grandeur</b>, pas une vérité.</p></div>")

    g = lecture_graphique(
        "<ul><li><b>À gauche</b> : la contribution de chaque année à la valeur DCF (en bleu) et celle de "
        "la valeur terminale (en violet). Plus le violet domine, plus la valeur repose sur un futur lointain.</li>"
        "<li><b>À droite</b> : le cours actuel comparé à la valeur DCF et aux objectifs des analystes. "
        "Si toutes les barres sont à droite du trait pointillé, les estimations jugent l'action sous-évaluée.</li></ul>")
    return n + pour_cette_action(phrases), t1 + t2 + t3, g


def calculatrice_dcf(v: dict) -> str:
    """DCF interactif : curseurs en JavaScript, recalcul instantané dans la page."""
    if not v["dcf"] or not (v["fcf0"] > 0):
        return ""
    p = {"fcf0": v["fcf0"], "dfn": v["dfn"], "actions": v["actions"], "fx": v["fx"], "cours": v["cours"],
         "g": v["g"], "ginf": v["g_inf"], "cmpc": v["cmpc"], "devise": v["devise_cours"]}
    return """
<div class="carte calc" id="calc-dcf">
  <b>À toi de jouer : modifie les hypothèses du DCF</b>
  <div class="curseur"><label>Croissance des flux sur 5 ans : <span id="v-g"></span></label>
    <input type="range" id="c-g" min="-5" max="25" step="0.1"></div>
  <div class="curseur"><label>Croissance à l'infini : <span id="v-ginf"></span></label>
    <input type="range" id="c-ginf" min="0" max="4" step="0.05"></div>
  <div class="curseur"><label>CMPC (taux d'actualisation) : <span id="v-cmpc"></span></label>
    <input type="range" id="c-cmpc" min="4" max="15" step="0.05"></div>
  <div class="resultat-calc"><div><span class="l">Valeur par action</span><span id="r-val" class="v"></span></div>
    <div><span class="l">Écart avec le cours</span><span id="r-pot" class="v"></span></div>
    <div><span class="l">Part de la valeur terminale</span><span id="r-vt" class="v"></span></div></div>
  <p class="note" id="r-msg"></p>
  <button type="button" id="b-reset">Revenir aux hypothèses de départ</button>
</div>
<script>
(function(){
  const P = """ + json.dumps(p) + """;
  const $ = id => document.getElementById(id);
  const fr = (x, d) => x.toLocaleString('fr-FR', {minimumFractionDigits: d, maximumFractionDigits: d});
  function init(){ $('c-g').value = (P.g*100).toFixed(1); $('c-ginf').value = (P.ginf*100).toFixed(2);
                   $('c-cmpc').value = (P.cmpc*100).toFixed(2); calc(); }
  function calc(){
    const g = +$('c-g').value/100, gi = +$('c-ginf').value/100, w = +$('c-cmpc').value/100;
    $('v-g').textContent = fr(g*100,1)+' %'; $('v-ginf').textContent = fr(gi*100,2)+' %';
    $('v-cmpc').textContent = fr(w*100,2)+' %';
    if (w <= gi + 0.0001) { $('r-val').textContent = '—'; $('r-pot').textContent = '—'; $('r-vt').textContent = '—';
      $('r-msg').textContent = "Le CMPC doit être supérieur à la croissance à l'infini, sinon la valeur serait infinie."; return; }
    let ve = 0, f = P.fcf0;
    for (let t = 1; t <= 5; t++) { f = P.fcf0 * Math.pow(1+g, t); ve += f / Math.pow(1+w, t); }
    const vt = f * (1+gi) / (w-gi) / Math.pow(1+w, 5); ve += vt;
    const val = (ve - P.dfn) / P.actions * P.fx, pot = val / P.cours - 1;
    $('r-val').textContent = fr(val,2) + ' ' + P.devise;
    $('r-pot').textContent = (pot>=0?'+':'') + fr(pot*100,0) + ' %';
    $('r-pot').className = 'v ' + (pot >= 0 ? 'pos' : 'neg');
    $('r-vt').textContent = fr(vt/ve*100,0) + ' %';
    $('r-msg').textContent = pot >= 0 ? "Avec ces hypothèses, l'action vaudrait plus que son cours actuel."
                                      : "Avec ces hypothèses, l'action vaudrait moins que son cours actuel.";
  }
  ['c-g','c-ginf','c-cmpc'].forEach(id => $(id).addEventListener('input', calc));
  $('b-reset').addEventListener('click', init);
  init();
})();
</script>"""


def section_scores(v: dict) -> str:
    a, p = v["altman"], v["piotroski"]
    n = notion(
        "<ul><li>Le <b>Z-score d'Altman</b> (1968) combine 4 ou 5 ratios du bilan et du compte de "
        "résultat en une seule note qui estime le <b>risque de faillite</b> à 2 ans. Il existe une "
        "version pour les entreprises industrielles et une version (Z'') pour les services.</li>"
        "<li>Le <b>F-score de Piotroski</b> (2000) fait passer 9 tests simples à l'entreprise "
        "(rentabilité, structure financière, efficacité), notés 0 ou 1 en comparant les deux derniers "
        "exercices. 8 ou 9 : santé solide et en amélioration ; 0 à 3 : signaux de faiblesse.</li></ul>")
    phrases = []
    if pd.notna(a["z"]):
        ton = {"sécurité": "bon", "zone grise": "moyen", "détresse": "mauvais"}[a["zone"]]
        phrases.append(f"Z-score d'Altman ({html.escape(a['version'])}) : <b>{num(a['z'], 2)}</b> "
                       f"{niveau(a['zone'].capitalize(), ton)} (sous {num(a['bornes'][0], 2)} : détresse ; "
                       f"au-dessus de {num(a['bornes'][1], 2)} : sécurité).")
        if a["zone"] == "zone grise":
            phrases.append("La zone grise n'est pas un signal d'alarme pour une grande entreprise rentable : "
                           "le score a été calibré sur des entreprises industrielles américaines des années 1960 "
                           "et pénalise par exemple les entreprises qui ont beaucoup d'actifs immatériels.")
    if pd.notna(p["score"]):
        s = p["score"]
        ton = "bon" if s >= 7 else "moyen" if s >= 4 else "mauvais"
        lib = "Solide" if s >= 7 else "Moyen" if s >= 4 else "Fragile"
        phrases.append(f"F-score de Piotroski : <b>{s} / 9</b> {niveau(lib, ton)}.")
    tests = ""
    if p["tests"]:
        tests = ("<div class='carte'><table><tr><th>Domaine</th><th>Test (dernier exercice vs précédent)</th>"
                 "<th>Résultat</th></tr>" + "".join(
                     f"<tr><td>{c}</td><td>{html.escape(t)}</td><td class='{'pos' if ok else 'neg'}'>"
                     f"{'✓ 1 point' if ok else '✗ 0 point'}</td></tr>" for c, t, ok in p["tests"]) + "</table></div>")
    altman_t = ""
    if pd.notna(a["z"]):
        altman_t = ("<div class='carte'><table><tr><th>Composante du Z-score</th><th>Valeur</th><th>Poids</th>"
                    "<th>Contribution</th></tr>" + "".join(
                        f"<tr><td>{html.escape(nom)}</td><td>{num(x, 2)}</td><td>× {num(w, 2)}</td>"
                        f"<td>{num(x * w, 2)}</td></tr>" for nom, x, w in a["details"]) + "</table></div>")
    return n + pour_cette_action(phrases) + altman_t + tests


CSS = """
.calc { margin-top: 12px; }
.curseur { margin: 12px 0; }
.curseur label { display: block; font-size: 14px; margin-bottom: 4px; }
.curseur span { font-weight: 700; color: var(--accent); }
.curseur input { width: 100%; max-width: 520px; }
.resultat-calc { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin: 14px 0 6px; }
.resultat-calc div { background: var(--fond); border: 1px solid var(--bord); border-radius: 8px; padding: 10px; }
.resultat-calc .l { display: block; color: var(--doux); font-size: 12px; text-transform: uppercase; }
.resultat-calc .v { font-size: 22px; font-weight: 700; }
.calc button { font: inherit; font-size: 13px; padding: 6px 12px; border-radius: 8px; cursor: pointer;
               border: 1px solid var(--bord); background: var(--fond); color: var(--texte); }
"""
