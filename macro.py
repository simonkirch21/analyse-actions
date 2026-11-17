"""
MACROÉCONOMIE — Les grands indicateurs qui font bouger les marchés
=================================================================

Source : FRED (Banque fédérale de réserve de Saint-Louis), qui republie gratuitement les séries
officielles du BLS, de la Fed, de la BCE, d'Eurostat et de l'OCDE. Aucune clé n'est nécessaire.

Cinq thèmes : inflation, taux directeurs des banques centrales, taux d'emprunt d'État à 10 ans,
chômage, croissance du PIB. Pour chacun : historique, dernière valeur, évolution sur un an,
explication pour débutant et lecture automatique de la situation.
"""

import io
import threading
import time

import numpy as np
import pandas as pd
import requests

ENTETES = {"User-Agent": "Mozilla/5.0 (Macintosh) analyse-action"}
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"

# Chaque série : (code FRED, nom affiché, transformation)
#   "niveau" : la valeur telle quelle (taux en %)
#   "glissement" : variation sur 12 mois d'un indice de prix, en %
#   "glissement_trim" : variation sur 4 trimestres d'un PIB en volume, en %
THEMES = [
    {
        "id": "inflation", "titre": "Inflation", "unite": "% sur un an",
        "series": [("CP0000EZ19M086NEST", "Zone euro", "glissement"), ("CP0000FRM086NEST", "France", "glissement"),
                   ("CPIAUCSL", "États-Unis", "glissement")],
        "repere": 2.0, "repere_nom": "Objectif des banques centrales (2 %)",
        "aide": ("L'inflation mesure la hausse des prix à la consommation sur un an. Les banques centrales visent "
                 "environ 2 % : assez pour éviter la baisse des prix (qui pousse à reporter ses achats), sans "
                 "rogner le pouvoir d'achat. Une inflation élevée pousse les banques centrales à monter leurs taux, "
                 "ce qui pèse en général sur la Bourse."),
    },
    {
        "id": "taux_directeurs", "titre": "Taux directeurs", "unite": "%",
        "series": [("ECBDFR", "BCE (taux de dépôt)", "niveau"), ("FEDFUNDS", "Fed (taux des fonds fédéraux)", "niveau")],
        "aide": ("Le taux auquel les banques se refinancent auprès de la banque centrale. Il se répercute sur tous les "
                 "taux de l'économie (crédits immobiliers, livrets, obligations). La banque centrale le monte pour "
                 "freiner l'inflation et le baisse pour soutenir l'activité. Des taux qui baissent sont souvent une "
                 "bonne nouvelle pour les actions : l'argent coûte moins cher et les placements sans risque rapportent moins."),
    },
    {
        "id": "taux_longs", "titre": "Taux d'emprunt d'État à 10 ans", "unite": "%",
        "series": [("IRLTLT01FRM156N", "France (OAT)", "niveau"), ("IRLTLT01DEM156N", "Allemagne (Bund)", "niveau"),
                   ("DGS10", "États-Unis (Treasury)", "niveau")],
        "aide": ("Le taux auquel un État emprunte sur 10 ans sur les marchés. C'est la référence du « taux sans risque » "
                 "à long terme : quand il monte, les actions deviennent relativement moins attractives et la valeur "
                 "actuelle des bénéfices futurs baisse (c'est le taux d'actualisation du DCF). L'écart entre la France "
                 "et l'Allemagne (le « spread ») mesure la confiance des investisseurs dans la dette française."),
    },
    {
        "id": "chomage", "titre": "Chômage", "unite": "% de la population active",
        "series": [("LRHUTTTTFRM156S", "France", "niveau"), ("LRHUTTTTDEM156S", "Allemagne", "niveau"),
                   ("UNRATE", "États-Unis", "niveau")],
        "aide": ("La part des personnes qui cherchent un emploi sans en trouver. Un chômage bas signale une économie "
                 "solide, mais aussi un risque de hausse des salaires et donc d'inflation. Une hausse rapide du "
                 "chômage annonce souvent une récession."),
    },
    {
        "id": "croissance", "titre": "Croissance du PIB", "unite": "% sur un an",
        "series": [("CLVMNACSCAB1GQEA19", "Zone euro", "glissement_trim"), ("CLVMNACSCAB1GQFR", "France", "glissement_trim"),
                   ("GDPC1", "États-Unis", "glissement_trim")],
        "repere": 0.0, "repere_nom": "Zéro (en dessous : l'économie se contracte)",
        "aide": ("Le PIB mesure la richesse produite en un an. Sa croissance, corrigée de l'inflation (« en volume »), "
                 "indique si l'économie accélère ou ralentit. Deux trimestres de baisse consécutifs sont souvent "
                 "qualifiés de récession. Les bénéfices des entreprises suivent en général la croissance."),
    },
]

_cache, _verrou = {}, threading.Lock()


def _serie(code: str) -> pd.Series:
    r = requests.get(URL.format(code), headers=ENTETES, timeout=20)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").values, index=pd.to_datetime(df.iloc[:, 0])).dropna()
    return s


def _transformer(s: pd.Series, mode: str) -> pd.Series:
    if mode == "glissement":
        s = s.resample("MS").last().dropna()
        return (s / s.shift(12) - 1).dropna() * 100
    if mode == "glissement_trim":
        s = s.resample("QS").last().dropna()
        return (s / s.shift(4) - 1).dropna() * 100
    return s.resample("MS").mean().dropna()       # séries quotidiennes -> moyennes mensuelles


def _lecture(theme: dict, series: list) -> list:
    """Quelques phrases qui interprètent la situation actuelle."""
    v = {s["nom"]: s for s in series}
    f = lambda x: f"{x:.1f}".replace(".", ",").replace("-", "−")
    phrases = []
    tid = theme["id"]
    if tid == "inflation":
        for nom in ("Zone euro", "États-Unis"):
            s = v.get(nom)
            if not s:
                continue
            x = s["dernier"]
            etat = ("proche de l'objectif de 2 %" if 1.5 <= x <= 2.5 else
                    "au-dessus de l'objectif : les banques centrales restent vigilantes" if x > 2.5 else
                    "sous l'objectif : de quoi permettre des baisses de taux")
            sens = "en baisse" if s["dernier"] < s["il_y_a_1an"] else "en hausse"
            phrases.append(f"{nom} : {f(x)} % sur un an ({sens} par rapport à il y a un an, {f(s['il_y_a_1an'])} %), {etat}.")
    elif tid == "taux_directeurs":
        for s in series:
            d = s["dernier"] - s["il_y_a_1an"]
            mouv = ("a baissé" if d < -0.1 else "a monté" if d > 0.1 else "est stable")
            phrases.append(f"{s['nom']} : {f(s['dernier'])} % ; il {mouv} en un an ({f(s['il_y_a_1an'])} % il y a un an).")
        # (le taux « réel » est ajouté dans tableau(), car il a besoin de l'inflation)
    elif tid == "taux_longs":
        fr_, de = v.get("France (OAT)"), v.get("Allemagne (Bund)")
        if fr_ and de:
            ecart = (fr_["dernier"] - de["dernier"]) * 100
            phrases.append(f"La France emprunte à {f(fr_['dernier'])} % sur 10 ans, l'Allemagne à {f(de['dernier'])} % : "
                           f"écart (spread) de {ecart:.0f} points de base"
                           + (" — élevé, signe d'inquiétude sur les finances publiques françaises." if ecart > 70 else "."))
        us = v.get("États-Unis (Treasury)")
        if us:
            phrases.append(f"Le taux américain à 10 ans est à {f(us['dernier'])} % : c'est la référence mondiale du coût de l'argent.")
    elif tid == "chomage":
        for s in series:
            d = s["dernier"] - s["il_y_a_1an"]
            phrases.append(f"{s['nom']} : {f(s['dernier'])} % "
                           + ("(en hausse sur un an : à surveiller)." if d > 0.3 else
                              "(en baisse sur un an)." if d < -0.3 else "(stable sur un an)."))
    elif tid == "croissance":
        for s in series:
            x = s["dernier"]
            etat = ("croissance solide" if x > 2 else "croissance modérée" if x > 0.5 else
                    "quasi-stagnation" if x >= 0 else "contraction de l'économie")
            phrases.append(f"{s['nom']} : {f(x)} % sur un an ({etat}).")
    return phrases


def tableau() -> list:
    """Tous les thèmes, avec historiques mensuels (cache de 6 heures)."""
    with _verrou:
        v = _cache.get("macro")
        if v and time.time() - v[0] < 6 * 3600:
            return v[1]
    res = []
    for th in THEMES:
        series = []
        for code, nom, mode in th["series"]:
            try:
                s = _transformer(_serie(code), mode)
            except Exception:
                continue
            if s.empty:
                continue
            un_an = s[s.index <= s.index[-1] - pd.DateOffset(years=1)]
            series.append({
                "code": code, "nom": nom, "dernier": round(float(s.iloc[-1]), 3),
                "date": s.index[-1].strftime("%m/%Y"),
                "il_y_a_1an": round(float(un_an.iloc[-1]), 3) if len(un_an) else None,
                "points": [[d.strftime("%Y-%m-%d"), round(float(x), 3)] for d, x in s.items()],
            })
        if series:
            res.append({"id": th["id"], "titre": th["titre"], "unite": th["unite"], "aide": th["aide"],
                        "repere": th.get("repere"), "repere_nom": th.get("repere_nom"),
                        "series": series, "lecture": _lecture(th, series)})
    # Taux réel = taux directeur − inflation : positif, la politique monétaire freine ; négatif, elle soutient
    themes = {t["id"]: t for t in res}
    if "taux_directeurs" in themes and "inflation" in themes:
        infl = {s["nom"]: s["dernier"] for s in themes["inflation"]["series"]}
        f = lambda x: f"{x:.1f}".replace(".", ",").replace("-", "−")
        for nom_taux, nom_infl in (("BCE (taux de dépôt)", "Zone euro"), ("Fed (taux des fonds fédéraux)", "États-Unis")):
            t = next((s["dernier"] for s in themes["taux_directeurs"]["series"] if s["nom"] == nom_taux), None)
            if t is not None and nom_infl in infl:
                reel = t - infl[nom_infl]
                themes["taux_directeurs"]["lecture"].append(
                    f"Taux réel {nom_taux.split(' ')[0]} : {f(t)} % − {f(infl[nom_infl])} % d'inflation = {f(reel)} % : "
                    + ("positif, la politique monétaire freine l'économie." if reel > 0.25 else
                       "négatif, la politique monétaire reste favorable à l'activité malgré le niveau des taux." if reel < -0.25
                       else "proche de zéro : politique monétaire plutôt neutre."))
    with _verrou:
        _cache["macro"] = (time.time(), res)
    return res


if __name__ == "__main__":
    for th in tableau():
        print(f"\n== {th['titre']} ==")
        for s in th["series"]:
            print(f"  {s['nom']:<32} {s['dernier']:7.2f} ({s['date']})  il y a 1 an : {s['il_y_a_1an']}  depuis {s['points'][0][0]}")
        for p in th["lecture"]:
            print("  •", p)
