"""
INTERPRÉTATION — Expliquer les chiffres et les graphiques à un débutant
=======================================================================

Pour chaque partie du rapport, trois niveaux :
  1. « C'est quoi ? »       : la notion expliquée simplement, sans formule ;
  2. « Comment lire le graphique » : ce que montre chaque graphique ;
  3. « Pour cette action »  : les chiffres de l'action traduits en phrases.

Tout est déterministe (règles + seuils) : aucun service externe n'est appelé.
"""

import html

import numpy as np
import pandas as pd

MISE = 1000   # montant fictif utilisé dans les exemples : 1 000 €


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------
def pct(x, d=1, signe=False):
    if x is None or pd.isna(x):
        return "—"
    s = f"{x * 100:+.{d}f} %" if signe else f"{x * 100:.{d}f} %"
    return s.replace(".", ",").replace("-", "−")


def num(x, d=2):
    if x is None or pd.isna(x):
        return "—"
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",").replace("-", "−")


def euros(x):
    return f"{num(x, 0)} €"


def bloc(titre: str, contenu: str, classe: str) -> str:
    return f'<div class="{classe}"><div class="bloc-titre">{titre}</div>{contenu}</div>'


def notion(contenu: str) -> str:
    """Encadré « C'est quoi ? » (explication générale)."""
    return bloc("C'est quoi ?", contenu, "notion")


def lecture_graphique(contenu: str) -> str:
    return bloc("Comment lire le graphique", contenu, "lecture")


def pour_cette_action(phrases: list) -> str:
    items = "".join(f"<li>{p}</li>" for p in phrases if p)
    return bloc("Ce qu'il faut retenir pour cette action", f"<ul>{items}</ul>", "verdict")


def niveau(etiquette: str, ton: str) -> str:
    """Pastille colorée : ton = bon / moyen / mauvais / neutre."""
    return f'<span class="niveau {ton}">{etiquette}</span>'


# ---------------------------------------------------------------------------
# Échelles de lecture (seuils indicatifs pour une action individuelle)
# ---------------------------------------------------------------------------
def echelle_sharpe(s):
    if s >= 1:
        return niveau("Très bon", "bon")
    if s >= 0.5:
        return niveau("Correct", "bon")
    if s >= 0:
        return niveau("Faible", "moyen")
    return niveau("Négatif", "mauvais")


def echelle_volatilite(v):
    if v < 0.20:
        return niveau("Faible", "bon")
    if v < 0.35:
        return niveau("Moyenne", "moyen")
    return niveau("Élevée", "mauvais")


def echelle_drawdown(d):
    if d > -0.20:
        return niveau("Limitée", "bon")
    if d > -0.40:
        return niveau("Importante", "moyen")
    return niveau("Sévère", "mauvais")


def echelle_beta(b):
    if b < 0.8:
        return niveau("Défensive", "neutre")
    if b <= 1.2:
        return niveau("Comme le marché", "neutre")
    return niveau("Offensive", "neutre")


def echelle_rendement(r):
    if r >= 0.10:
        return niveau("Élevé", "bon")
    if r >= 0.03:
        return niveau("Modéré", "moyen")
    if r >= 0:
        return niveau("Faible", "moyen")
    return niveau("Négatif", "mauvais")


def echelle_var(v):
    if v < 0.02:
        return niveau("Faible", "bon")
    if v < 0.035:
        return niveau("Moyen", "moyen")
    return niveau("Élevé", "mauvais")


def echelle_proba_perte(p):
    if p < 0.30:
        return niveau("Faible", "bon")
    if p < 0.45:
        return niveau("Moyenne", "moyen")
    return niveau("Élevée", "mauvais")


# Aide affichée au survol de chaque chiffre clé
AIDE_KPI = {
    "Dernier cours": "Le dernier prix de clôture connu d'une action.",
    "Rendement annualisé": "Ce que l'action a rapporté en moyenne chaque année, dividendes compris.",
    "Volatilité": "L'ampleur habituelle des variations du prix sur un an. Plus elle est haute, plus le prix bouge.",
    "Sharpe": "Le rendement obtenu en plus d'un placement sans risque, pour chaque unité de risque prise.",
    "Perte maximale": "La pire chute entre un plus haut et le point le plus bas qui a suivi.",
    "Bêta": "La sensibilité de l'action aux mouvements du marché (1 = elle bouge comme le marché).",
    "VaR 95 % 1 jour": "La perte qui n'est dépassée qu'un jour sur vingt environ.",
    "P(perte) à 1 an": "La part des 10 000 scénarios simulés où l'action vaut moins qu'aujourd'hui dans un an.",
}


def pastilles_kpi(a: dict) -> dict:
    """Une pastille de lecture sous chaque chiffre clé."""
    perf, capm = a["perf"], a["capm"]
    return {
        "Rendement annualisé": echelle_rendement(perf["Rendement annualisé"]),
        "Volatilité": echelle_volatilite(perf["Volatilité annualisée"]),
        "Sharpe": echelle_sharpe(perf["Sharpe"]),
        "Perte maximale": echelle_drawdown(perf["Max drawdown"]),
        "Bêta": echelle_beta(capm["beta"]),
        "VaR 95 % 1 jour": echelle_var(a["tab_var"].loc["Historique", "VaR 95%"]),
        "P(perte) à 1 an": echelle_proba_perte(a["simu"]["Probabilité de perte"]),
    }


# ---------------------------------------------------------------------------
# Résumé en langage courant (en haut du rapport)
# ---------------------------------------------------------------------------
NOMS_INDICES = {
    "^FCHI": "CAC 40", "^GSPC": "S&P 500", "^GDAXI": "DAX", "^FTSE": "FTSE 100",
    "^AEX": "AEX", "^BFX": "BEL 20", "FTSEMIB.MI": "FTSE MIB", "^SSMI": "SMI",
    "^N225": "Nikkei 225", "^STOXX50E": "Euro Stoxx 50", "PSI20.LS": "PSI",
    "^ISEQ": "ISEQ", "OBX.OL": "OBX",
}


def nom_indice(code: str) -> str:
    return NOMS_INDICES.get(code, code)


def chiffre_fr(texte: str) -> str:
    """'+18.5%' -> '+18,5 %' (format français)."""
    return texte.replace(".", ",").replace("%", " %").replace("-", "−")


def duree_texte(prix: pd.Series) -> str:
    annees = (prix.index[-1] - prix.index[0]).days / 365.25
    if annees >= 1.5:
        return f"{round(annees)} ans"
    if annees >= 0.9:
        return "1 an"
    return f"{round(annees * 12)} mois"


def resume_debutant(a: dict) -> str:
    prix, pi = a["prix"], a["prix_indice"]
    perf, capm = a["perf"], a["capm"]
    nom = html.escape(a["infos"].get("Nom") or a["ticker"])
    duree = duree_texte(prix)

    final = MISE * prix.iloc[-1] / prix.iloc[0]
    communs = pi.loc[pi.index >= prix.index[0]]
    final_indice = MISE * communs.iloc[-1] / communs.iloc[0]

    phrases = []
    verbe = "seraient devenus" if final >= MISE else "ne vaudraient plus que"
    phrases.append(
        f"<b>{euros(MISE)} investis dans {nom} il y a {duree} {verbe} {euros(final)}</b> "
        f"aujourd'hui ({pct(final / MISE - 1, 0, signe=True)}), dividendes réinvestis.")
    compare = "mieux" if final > final_indice else "moins bien"
    phrases.append(
        f"Sur la même période, la même somme placée sur l'indice {html.escape(nom_indice(a['indice']))} "
        f"(le marché dans son ensemble) serait arrivée à {euros(final_indice)} : "
        f"l'action a donc fait <b>{compare} que le marché</b>.")

    vol = perf["Volatilité annualisée"]
    jour_typique = vol / np.sqrt(252)
    phrases.append(
        f"Le prix bouge d'environ <b>±{pct(jour_typique)} par jour</b> en temps normal "
        f"(volatilité de {pct(vol, 0)} par an {echelle_volatilite(vol)}).")

    dd = perf["Max drawdown"]
    phrases.append(
        f"Au pire moment, quelqu'un qui avait acheté au plus haut perdait "
        f"<b>{pct(-dd, 0)}</b> de sa mise ({euros(MISE * -dd)} sur {euros(MISE)}). "
        + ("Il a fini par revenir à l'équilibre." if perf["_drawdown"]["recuperation"] is not None
           else "<b>Le prix n'est toujours pas revenu à ce plus haut.</b>"))

    b = capm["beta"]
    if b > 1.2:
        phrases.append(f"C'est une action <b>offensive</b> : quand le marché baisse de 10 %, "
                       f"elle baisse en moyenne d'environ {num(b * 10, 0)} %.")
    elif b < 0.8:
        phrases.append(f"C'est une action <b>défensive</b> : quand le marché baisse de 10 %, "
                       f"elle ne baisse en moyenne que d'environ {num(b * 10, 0)} %.")
    else:
        phrases.append("Elle suit globalement les mouvements du marché.")

    contenu = "".join(f"<p>{p}</p>" for p in phrases)
    return bloc("En résumé, en langage courant", contenu, "resume")


# ---------------------------------------------------------------------------
# 1. Données
# ---------------------------------------------------------------------------
def section_donnees(a: dict) -> str:
    infos = a["infos"]
    capi, per = infos.get("Capitalisation"), infos.get("PER")
    devise = infos.get("Devise") or ""

    n = notion(
        "<p>Le <b>ticker</b> est le code de l'action en bourse (par exemple <code>MC.PA</code> pour "
        "LVMH à Paris). Le <b>cours</b> est son prix. Ici, il est <b>ajusté</b> : on fait comme si "
        "les dividendes versés avaient été réinvestis, pour mesurer le vrai gain d'un actionnaire.</p>"
        "<p>La <b>capitalisation</b>, c'est le prix de toute l'entreprise en bourse (prix d'une action "
        "× nombre d'actions). Le <b>PER</b> (Price Earnings Ratio) indique combien d'années de "
        "bénéfices actuels il faudrait pour « rembourser » le prix de l'action. Un PER élevé veut "
        "dire que les investisseurs attendent une forte croissance, ou que l'action est chère.</p>")

    phrases = []
    if capi:
        md = capi / 1e9
        taille = ("une très grande entreprise" if md >= 100 else "une grande entreprise" if md >= 10
                  else "une entreprise moyenne" if md >= 2 else "une petite entreprise")
        phrases.append(f"Avec {num(md, 1)} milliards {html.escape(devise)} de capitalisation, "
                       f"c'est {taille}. Les petites entreprises sont en général plus risquées.")
    if per and per > 0:
        if per < 10:
            lec = "bas : le marché est prudent sur l'avenir de l'entreprise, ou elle est peu chère"
        elif per <= 25:
            lec = "dans la moyenne des grandes entreprises (environ 10 à 25)"
        else:
            lec = "élevé : les investisseurs parient sur une forte croissance des bénéfices"
        phrases.append(f"Le PER de {num(per, 1)} est {lec}. À comparer avec les entreprises du même secteur.")
    elif per is not None and per <= 0:
        phrases.append("Le PER est négatif : l'entreprise a perdu de l'argent sur la dernière année.")

    g = lecture_graphique(
        "<p><b>En haut</b> : l'évolution du prix. <b>En bas</b> : la variation de chaque jour, en %. "
        "Chaque trait est une séance de bourse ; les grands pics sont des journées agitées "
        "(résultats, annonces, crises).</p>"
        "<p>On remarque souvent que les journées agitées <b>arrivent en groupe</b> : après un choc, "
        "le marché reste nerveux quelque temps. C'est ce qu'on appelle le regroupement de volatilité.</p>")
    return n + (pour_cette_action(phrases) if phrases else ""), g


# ---------------------------------------------------------------------------
# 2. Performance
# ---------------------------------------------------------------------------
def section_performance(a: dict) -> str:
    perf = a["perf"]
    n = notion(
        "<ul>"
        "<li><b>Rendement annualisé</b> : le gain moyen par an, intérêts composés compris. "
        "10 % par an pendant 7 ans, c'est presque doubler sa mise.</li>"
        "<li><b>Volatilité</b> : l'ampleur des variations. C'est la mesure du risque la plus utilisée. "
        "Une action a souvent entre 20 % et 35 %, un indice comme le CAC 40 plutôt 15 à 20 %.</li>"
        "<li><b>Ratio de Sharpe</b> : il répond à la question « ai-je été bien payé pour le risque "
        "pris ? ». Il compare le gain obtenu en plus d'un placement sans risque (ici 3 % par an, "
        "comme un livret) à la volatilité. Au-dessus de 0,5 c'est correct, au-dessus de 1 c'est très bon.</li>"
        "<li><b>Ratio de Sortino</b> : comme le Sharpe, mais seules les <i>baisses</i> comptent comme "
        "du risque (les fortes hausses ne gênent personne).</li>"
        "<li><b>Perte maximale</b> (max drawdown) : la pire chute subie entre un sommet et le creux "
        "suivant. C'est ce que ressent vraiment un investisseur malchanceux.</li>"
        "<li><b>Ratio de Calmar</b> : rendement annuel divisé par la perte maximale.</li>"
        "</ul>")

    r, s = perf["Rendement annualisé"], perf["Sharpe"]
    v = perf["Volatilité annualisée"]
    phrases = [
        f"Rendement : <b>{pct(r)} par an</b> {echelle_rendement(r)}. "
        f"Volatilité : <b>{pct(v, 0)} par an</b> {echelle_volatilite(v)}.",
    ]
    if s < 0:
        phrases.append(f"Sharpe de {num(s)} {echelle_sharpe(s)} : l'action a rapporté <b>moins qu'un "
                       "placement sans risque</b>. Le risque pris n'a pas été récompensé.")
    elif s < 0.5:
        phrases.append(f"Sharpe de {num(s)} {echelle_sharpe(s)} : le gain est faible au regard des "
                       "variations subies.")
    else:
        phrases.append(f"Sharpe de {num(s)} {echelle_sharpe(s)} : le risque pris a été bien récompensé.")

    if perf["Sortino"] > s * 1.3 and s > 0:
        phrases.append("Le Sortino est nettement plus élevé que le Sharpe : une bonne partie de la "
                       "volatilité vient de <b>hausses</b> brutales, pas de baisses.")

    dd = perf["_drawdown"]
    phrases.append(
        f"Perte maximale de {pct(perf['Max drawdown'], 0)} {echelle_drawdown(perf['Max drawdown'])}, "
        f"du {dd['sommet']:%d/%m/%Y} au {dd['creux']:%d/%m/%Y}"
        + (f", effacée le {dd['recuperation']:%d/%m/%Y}." if dd["recuperation"] is not None
           else ", <b>pas encore effacée</b>."))

    annuels = a["annuels"]
    positives = int((annuels > 0).sum())
    phrases.append(
        f"{positives} année(s) en hausse sur {len(annuels)}, et {pct(perf['% jours positifs'], 0)} "
        "des jours en hausse. Même une action qui monte sur la durée baisse presque un jour sur "
        "deux : en bourse, c'est la durée qui fait le résultat, pas chaque journée.")

    g = lecture_graphique(
        "<ul>"
        "<li><b>Évolution base 100</b> : les deux courbes partent de 100 pour comparer l'action à son "
        "indice. Une courbe à 150 signifie +50 % depuis le départ.</li>"
        "<li><b>Drawdown</b> : à chaque date, de combien le prix est sous son dernier plus haut. "
        "0 = au sommet ; plus la courbe plonge, plus la chute est forte ; plus elle reste longtemps "
        "sous 0, plus l'attente a été longue.</li>"
        "<li><b>Volatilité glissante</b> : le niveau de risque mesuré sur les 3 derniers mois. "
        "Les pics correspondent aux périodes de crise ou d'incertitude.</li>"
        "</ul>")
    return n + pour_cette_action(phrases), g


# ---------------------------------------------------------------------------
# 3. Comparaison au marché
# ---------------------------------------------------------------------------
def section_marche(a: dict) -> str:
    capm, rel = a["capm"], a["relatif"]
    n = notion(
        "<p>On compare l'action à son <b>indice de référence</b> (CAC 40 pour Paris, S&amp;P 500 pour "
        "les États-Unis…), qui représente « le marché ». C'est le modèle <b>CAPM</b> "
        "(MEDAF en français), un classique des cours de finance.</p><ul>"
        "<li><b>Bêta (β)</b> : la sensibilité au marché. β = 1 : l'action bouge comme le marché ; "
        "β = 1,5 : elle amplifie ses mouvements de 50 % ; β = 0,5 : elle les amortit de moitié.</li>"
        "<li><b>Alpha (α)</b> : la performance que le marché n'explique pas. Un alpha positif "
        "signifie que l'action a fait mieux que ce que son bêta laissait prévoir.</li>"
        "<li><b>p-value</b> : la probabilité d'obtenir un alpha pareil <i>par pur hasard</i>. "
        "En dessous de 5 %, on considère que l'alpha est réel ; au-dessus, il peut s'agir de chance.</li>"
        "<li><b>R²</b> : la part du risque qui vient du marché. Le reste est propre à l'entreprise "
        "(un mauvais résultat, un procès…) et peut être réduit en détenant plusieurs actions : "
        "c'est la <b>diversification</b>.</li></ul>")

    b, p, r2 = capm["beta"], capm["p_alpha"], capm["r2"]
    phrases = [f"Bêta de <b>{num(b)}</b> {echelle_beta(b)} : si le marché perd 10 %, cette action perd en "
               f"moyenne environ {num(b * 10, 0)} % ; s'il gagne 10 %, elle gagne environ {num(b * 10, 0)} %."]
    if p < 0.05:
        sens = "mieux" if capm["alpha_annuel"] > 0 else "moins bien"
        phrases.append(f"Alpha de {pct(capm['alpha_annuel'], signe=True)} par an avec une p-value de "
                       f"{num(p, 3)} : l'action a <b>réellement</b> fait {sens} que le marché, "
                       "au-delà du hasard.")
    else:
        phrases.append(f"Alpha de {pct(capm['alpha_annuel'], signe=True)} par an, mais p-value de "
                       f"{num(p, 2)} : on <b>ne peut pas exclure le hasard</b>. C'est le cas de la "
                       "plupart des actions : battre le marché durablement est très difficile.")
    phrases.append(f"{pct(r2, 0)} du risque vient du marché et {pct(1 - r2, 0)} est propre à "
                   "l'entreprise" + (" : cette action apporte beaucoup de <b>diversification</b> "
                                    "à un portefeuille." if r2 < 0.3 else "."))
    ch, cb = rel["Capture hausse"], rel["Capture baisse"]
    if cb > ch:
        phrases.append(f"Elle subit davantage les baisses du marché ({num(cb)}×) qu'elle ne profite "
                       f"de ses hausses ({num(ch)}×) : profil défavorable.")
    else:
        phrases.append(f"Elle profite davantage des hausses du marché ({num(ch)}×) qu'elle ne subit "
                       f"ses baisses ({num(cb)}×) : profil favorable.")

    g = lecture_graphique(
        "<ul>"
        "<li><b>Nuage de points</b> : chaque point est une journée. À l'horizontal, la variation du "
        "marché ; à la verticale, celle de l'action. La <b>pente de la droite rouge est le bêta</b>. "
        "Plus les points sont serrés autour de la droite, plus l'action suit le marché (R² élevé).</li>"
        "<li><b>Camembert</b> : la répartition du risque entre marché et entreprise.</li>"
        "<li><b>En bas</b> : l'action et l'indice en base 100, et en rouge le bêta recalculé sur "
        "chaque année glissante. Un bêta qui varie beaucoup montre que le comportement de l'action "
        "change selon les périodes.</li></ul>")
    return n + pour_cette_action(phrases), g


# ---------------------------------------------------------------------------
# 4. Risque
# ---------------------------------------------------------------------------
def section_risque(a: dict) -> str:
    tv, d, bt = a["tab_var"], a["distrib"], a["bt"]
    n = notion(
        "<ul>"
        "<li><b>VaR 95 %</b> (Value at Risk) : la perte qui n'est dépassée qu'<b>un jour sur 20</b>. "
        "La VaR 99 % : un jour sur 100. C'est l'outil de mesure du risque des banques.</li>"
        "<li><b>CVaR</b> (ou Expected Shortfall) : la perte <b>moyenne</b> les jours où la VaR est "
        "dépassée. Elle répond à : « et quand ça va mal, je perds combien ? ».</li>"
        "<li>On la calcule de 4 façons : à partir de l'historique réel, avec une courbe en cloche "
        "(loi normale), avec une correction pour les événements extrêmes (Cornish-Fisher), et par "
        "simulation. Si les méthodes divergent, c'est que les événements extrêmes comptent beaucoup.</li>"
        "<li><b>Backtest</b> : on vérifie après coup si la VaR a été dépassée aussi souvent que prévu "
        "(environ 5 % des jours). Le test de <b>Kupiec</b> contrôle le nombre de dépassements, celui "
        "de <b>Christoffersen</b> vérifie qu'ils n'arrivent pas tous en même temps.</li></ul>")

    v95, c95 = tv.loc["Historique", "VaR 95%"], tv.loc["Historique", "CVaR 95%"]
    v99 = tv.loc["Historique", "VaR 99%"]
    phrases = [
        f"Risque quotidien {echelle_var(v95)} : sur {euros(MISE)} investis, <b>un jour sur 20</b> "
        f"on peut perdre plus de <b>{euros(MISE * v95)}</b> ; ces jours-là, la perte moyenne est de "
        f"{euros(MISE * c95)}.",
        f"<b>Un jour sur 100</b>, la perte dépasse {euros(MISE * v99)}.",
    ]
    k = d["Excès de kurtosis"]
    if d["Jarque-Bera (p-value)"] < 0.05:
        phrases.append(
            "Les variations <b>ne suivent pas une courbe en cloche</b> (test de Jarque-Bera)"
            + (f" : les journées extrêmes sont bien plus fréquentes que prévu (kurtosis de {num(k, 1)}). "
               "Les modèles basés sur la loi normale <b>sous-estiment le risque de krach</b>."
               if k > 1 else "."))
    if bt["valide"]:
        phrases.append(f"La VaR a été dépassée {bt['exceptions']} fois sur {bt['jours testés']} jours "
                       f"({pct(bt['taux observé'])}, pour 5 % attendus) : la mesure est <b>fiable</b> en nombre.")
    else:
        phrases.append(f"La VaR a été dépassée {bt['exceptions']} fois sur {bt['jours testés']} jours "
                       f"({pct(bt['taux observé'])}, pour 5 % attendus) : la mesure n'est <b>pas fiable</b>.")
    pi = bt["p-value indépendance"]
    if not pd.isna(pi) and pi < 0.05:
        phrases.append("Mais les dépassements <b>arrivent en grappes</b> : pendant les crises, les "
                       "fortes pertes s'enchaînent et la VaR réagit trop lentement.")

    g = lecture_graphique(
        "<ul>"
        "<li><b>Histogramme</b> : combien de jours ont eu chaque variation. La courbe pointillée est la "
        "courbe en cloche théorique. Les barres qui dépassent loin à gauche et à droite sont les "
        "journées extrêmes que la courbe ne prévoit pas. Les traits verticaux sont les VaR 95 % et 99 %.</li>"
        "<li><b>QQ-plot</b> : si les variations suivaient une loi normale, tous les points seraient "
        "sur la droite rouge. Les points qui s'en écartent aux deux bouts montrent des « queues "
        "épaisses » : plus de krachs et d'envolées que prévu.</li>"
        "<li><b>Backtest</b> : en gris, les variations de chaque jour ; en orange, la VaR prévue "
        "la veille. Chaque point rouge est un jour où la perte a dépassé la VaR.</li></ul>")
    return n + pour_cette_action(phrases), g


# ---------------------------------------------------------------------------
# 5. Analyse technique
# ---------------------------------------------------------------------------
def section_technique(a: dict) -> str:
    sig, ts = a["signaux"], a["tab_strat"]
    n = notion(
        "<p>L'<b>analyse technique</b> cherche des signaux dans l'historique des prix. Elle est très "
        "utilisée, mais <b>son efficacité est contestée</b> par la recherche académique.</p><ul>"
        "<li><b>Moyennes mobiles 50 et 200 jours</b> : le prix moyen sur 50 et 200 séances, qui "
        "lisse les variations. Quand la courte passe au-dessus de la longue (« golden cross »), la "
        "tendance est jugée haussière ; l'inverse (« death cross ») est jugé baissier.</li>"
        "<li><b>RSI</b> : une jauge de 0 à 100. Au-dessus de 70, l'action a beaucoup monté récemment "
        "(« surachat ») ; en dessous de 30, elle a beaucoup baissé (« survente »).</li>"
        "<li><b>Bandes de Bollinger</b> : un couloir autour de la moyenne des 20 derniers jours. "
        "Le prix en sort rarement ; un couloir qui s'élargit signale plus d'agitation.</li>"
        "<li><b>MACD</b> : mesure si la hausse ou la baisse accélère (le « momentum »).</li>"
        "<li><b>Backtest</b> : on teste des règles d'achat et de vente simples sur le passé, frais "
        "compris, et on les compare au fait d'acheter et de garder l'action (« buy &amp; hold »).</li></ul>")

    phrases = []
    tendance = sig["Tendance (MM50 vs MM200)"]
    phrases.append(f"Tendance de fond : <b>{'haussière' if 'HAUSSIÈRE' in tendance else 'baissière'}</b> "
                   f"(prix {chiffre_fr(sig['Prix vs MM200'])} par rapport à sa moyenne 200 jours).")
    rsi_txt = sig["RSI 14"]
    if "surachat" in rsi_txt:
        phrases.append("RSI en zone de <b>surachat</b> : l'action a beaucoup monté récemment, une pause "
                       "ou un repli est fréquent, mais pas garanti.")
    elif "survente" in rsi_txt:
        phrases.append("RSI en zone de <b>survente</b> : l'action a beaucoup baissé récemment, un "
                       "rebond est fréquent, mais pas garanti.")
    else:
        phrases.append("RSI neutre : ni excès de hausse, ni excès de baisse récents.")

    bh = ts.loc["Buy & hold", "Rendement annualisé"]
    meilleure = ts["Sharpe"].idxmax()
    autres = ts.drop("Buy & hold")
    battent = autres[autres["Rendement annualisé"] > bh]
    if battent.empty:
        phrases.append(f"Aucune des 3 stratégies testées n'a rapporté plus que d'acheter et garder "
                       f"l'action ({pct(bh)} par an). C'est le cas le plus fréquent.")
    else:
        noms = ", ".join(battent.index)
        phrases.append(f"Stratégie(s) ayant rapporté plus que l'achat simple ({pct(bh)} par an) : {noms}. "
                       "Attention : une règle qui a marché sur le passé peut échouer à l'avenir.")
    if meilleure != "Buy & hold":
        phrases.append(f"La stratégie « {meilleure} » a le meilleur rapport gain/risque (Sharpe "
                       f"{num(ts.loc[meilleure, 'Sharpe'])}), notamment parce qu'elle reste hors du "
                       "marché une partie du temps, ce qui réduit les pertes.")

    g = lecture_graphique(
        "<ul>"
        "<li><b>Graphique du haut</b> : le prix (noir), les moyennes 50 jours (bleu) et 200 jours "
        "(rouge), et le couloir de Bollinger (gris). Le croisement des lignes bleue et rouge donne "
        "le signal de tendance.</li>"
        "<li><b>RSI</b> : les pointillés marquent les seuils 70 (surachat) et 30 (survente).</li>"
        "<li><b>MACD</b> : quand la ligne bleue passe au-dessus de l'orange, le momentum devient "
        "haussier ; les barres grises montrent l'écart entre les deux.</li>"
        "<li><b>Backtest</b> : ce qu'auraient donné 100 € avec chaque stratégie. Les plateaux "
        "horizontaux sont les périodes où la stratégie était hors du marché.</li></ul>")
    return n + pour_cette_action(phrases), g


# ---------------------------------------------------------------------------
# 6. Simulation et options
# ---------------------------------------------------------------------------
def section_simulation(a: dict) -> str:
    s, o = a["simu"], a["opt"]
    S0 = s["Prix actuel"]
    n = notion(
        "<p><b>Monte Carlo</b> : on imagine 10 000 avenirs possibles pour le prix, en tirant au hasard "
        "des variations qui ont la même tendance et la même volatilité que par le passé. On regarde "
        "ensuite la répartition des résultats. C'est <b>une illustration du risque, pas une "
        "prévision</b> : le modèle suppose que l'avenir ressemble au passé.</p>"
        "<p>Une <b>option</b> est un contrat qui donne le <i>droit</i> (pas l'obligation) d'acheter "
        "(<b>call</b>) ou de vendre (<b>put</b>) l'action à un prix fixé à l'avance (le "
        "<b>strike</b>), jusqu'à une date donnée. On paie ce droit : c'est la <b>prime</b>. Un call "
        "permet de parier sur la hausse en risquant seulement la prime ; un put sert d'assurance "
        "contre la baisse. La formule de <b>Black-Scholes</b> (prix Nobel 1997) calcule cette prime.</p>"
        "<ul><li><b>Delta</b> : de combien la prime bouge quand l'action bouge de 1.</li>"
        "<li><b>Theta</b> : ce que l'option perd chaque jour qui passe (le temps joue contre l'acheteur).</li>"
        "<li><b>Vega</b> : de combien la prime augmente si la volatilité monte d'un point.</li></ul>")

    phrases = [
        f"Si l'avenir ressemble au passé, dans 90 % des scénarios le prix dans un an serait entre "
        f"<b>{num(s['Percentile 5 %'])}</b> et <b>{num(s['Percentile 95 %'])}</b> "
        f"(aujourd'hui : {num(S0)}).",
        f"Probabilité de perte {echelle_proba_perte(s['Probabilité de perte'])} : dans "
        f"<b>{pct(s['Probabilité de perte'], 0)} des scénarios</b>, l'action vaut moins "
        "qu'aujourd'hui dans un an.",
    ]
    if a["mu"] > 0.15:
        phrases.append("Attention : ces scénarios prolongent une forte hausse passée "
                       f"({pct(a['mu'], 0)} par an), ce qui les rend probablement <b>trop optimistes</b>.")
    elif a["mu"] < 0:
        phrases.append("Ces scénarios prolongent une baisse passée : ils sont probablement "
                       "<b>trop pessimistes</b> si la situation de l'entreprise s'améliore.")
    prime = o["call"]["Prix"]
    phrases.append(
        f"Un <b>call</b> à 3 mois au prix actuel ({num(o['K'])}) coûte environ <b>{num(prime)}</b> par "
        f"action, soit {pct(prime / S0)} du prix. Pour être gagnant à l'échéance, l'action doit "
        f"dépasser {num(o['K'] + prime)} (strike + prime).")
    phrases.append(
        f"Un <b>put</b> (assurance contre la baisse) coûte environ {num(o['put']['Prix'])}, soit "
        f"{pct(o['put']['Prix'] / S0)} du prix pour se protéger 3 mois. Le temps coûte "
        f"{num(-o['call']['Theta (par jour)'])} par jour à l'acheteur du call (theta).")

    g = lecture_graphique(
        "<ul>"
        "<li><b>Éventail</b> : 100 des 10 000 trajectoires simulées (en bleu clair). La ligne noire "
        "pleine est le scénario médian ; les pointillés encadrent 90 % des scénarios. L'éventail "
        "s'ouvre avec le temps : <b>plus l'horizon est lointain, plus l'incertitude est grande</b>.</li>"
        "<li><b>Histogramme</b> : la répartition des prix dans un an. Le trait rouge est le prix "
        "actuel : tout ce qui est à sa gauche correspond aux scénarios de perte.</li>"
        "<li><b>Convergence</b> : le prix de l'option calculé avec un arbre binomial (on découpe le "
        "temps en étapes où le prix monte ou baisse) se rapproche de la formule de Black-Scholes "
        "quand on augmente le nombre d'étapes. Cela vérifie que les deux méthodes concordent.</li></ul>")
    return n + pour_cette_action(phrases), g


# ---------------------------------------------------------------------------
# Lexique
# ---------------------------------------------------------------------------
LEXIQUE = [
    ("Action", "Une part de propriété d'une entreprise. L'actionnaire profite de la hausse du prix et des dividendes."),
    ("Dividende", "La part des bénéfices versée chaque année aux actionnaires."),
    ("Indice", "Un panier d'actions qui représente un marché (CAC 40 : les 40 plus grandes entreprises françaises ; S&P 500 : 500 grandes entreprises américaines)."),
    ("Rendement", "Le gain ou la perte, en pourcentage de la somme investie."),
    ("Volatilité", "L'ampleur des variations du prix. C'est la mesure du risque la plus courante."),
    ("Taux sans risque", "Ce que rapporte un placement sans risque (livret, emprunt d'État court). Ici 3 % par an."),
    ("Diversification", "Répartir son argent sur plusieurs actions pour que la chute de l'une soit compensée par les autres."),
    ("Drawdown", "La baisse depuis le dernier plus haut."),
    ("Bêta", "La sensibilité d'une action aux mouvements du marché."),
    ("Alpha", "La performance qui ne s'explique pas par les mouvements du marché."),
    ("VaR", "Value at Risk : la perte qui n'est dépassée que dans un petit pourcentage des cas (5 % ou 1 %)."),
    ("Loi normale", "La « courbe en cloche » : un modèle où les événements extrêmes sont très rares. Les marchés en ont plus que ce qu'elle prévoit."),
    ("Backtest", "Tester une stratégie sur des données passées, comme si on l'avait appliquée à l'époque."),
    ("Option", "Un contrat qui donne le droit d'acheter (call) ou de vendre (put) une action à un prix fixé, jusqu'à une date donnée."),
    ("Strike", "Le prix d'achat ou de vente fixé dans une option."),
    ("Monte Carlo", "Une méthode qui simule des milliers de scénarios au hasard pour étudier les résultats possibles."),
]


def lexique() -> str:
    lignes = "".join(f"<dt>{html.escape(t)}</dt><dd>{html.escape(d)}</dd>" for t, d in LEXIQUE)
    return f"<details class='lexique'><summary>Lexique : les mots de la finance</summary><dl>{lignes}</dl></details>"


CSS = """
.notion, .lecture, .verdict, .resume { border-radius: 10px; padding: 14px 16px; margin: 12px 0; }
.notion { background: var(--notion-fond); border-left: 4px solid var(--accent); }
.lecture { background: var(--lecture-fond); border-left: 4px solid var(--or, #A8812F); }
.verdict { background: var(--carte); border: 1px solid var(--bord); border-left: 4px solid var(--vert); }
.resume { background: var(--carte); border: 1px solid var(--bord); font-size: 16px; }
.resume p { margin: 6px 0; }
.bloc-titre { font-weight: 700; font-size: 13px; text-transform: uppercase; letter-spacing: .04em;
              color: var(--doux); margin-bottom: 6px; }
.notion p, .lecture p { margin: 6px 0; }
.notion ul, .lecture ul, .verdict ul { margin: 4px 0; padding-left: 20px; }
.notion li, .lecture li, .verdict li { margin: 4px 0; }
.niveau { display: inline-block; font-size: 11px; font-weight: 700; padding: 1px 8px; border-radius: 99px;
          vertical-align: 1px; margin-left: 2px; }
.niveau.bon { background: #143d22; color: #7fe0a0; }
.niveau.moyen { background: #3d2f12; color: #f3c46b; }
.niveau.mauvais { background: #45201b; color: #ff9d90; }
.niveau.neutre { background: #182c4a; color: #9cc3ff; }
.kpi .niveau { margin: 4px 0 0; }
.kpi[title] { cursor: help; }
.lexique { background: var(--carte); border: 1px solid var(--bord); border-radius: 10px; padding: 12px 16px; margin-top: 40px; }
.lexique summary { cursor: pointer; font-weight: 600; }
.lexique dt { font-weight: 700; margin-top: 10px; }
.lexique dd { margin: 2px 0 0; color: var(--doux); }
code { font-family: ui-monospace, Menlo, monospace; font-size: 13px; }
:root { --notion-fond: #121D33; --lecture-fond: #1E1B14; }
@media (prefers-color-scheme: dark) {
  :root { --notion-fond: #121D33; --lecture-fond: #1E1B14; }
  .niveau.bon { background: #143d22; color: #7fe0a0; }
  .niveau.moyen { background: #3d2f12; color: #f3c46b; }
  .niveau.mauvais { background: #45201b; color: #ff9d90; }
  .niveau.neutre { background: #182c4a; color: #9cc3ff; }
}
"""
