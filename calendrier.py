"""
CALENDRIER — Événements économiques et publications de résultats
================================================================

  - Événements économiques de la semaine et de la suivante (décisions des banques centrales,
    inflation, emploi, PIB…), avec leur importance, la prévision et la valeur précédente.
    Source : flux public du calendrier de Forex Factory (titres traduits pour les plus courants).
  - Publications de résultats des grandes entreprises (Yahoo Finance).

Heures affichées en heure de Paris.
"""

import re
import threading
import time

import pandas as pd
import requests

ENTETES = {"User-Agent": "Mozilla/5.0 (Macintosh) analyse-action"}
FLUX = ["https://nfs.faireconomy.media/ff_calendar_thisweek.json",
        "https://nfs.faireconomy.media/ff_calendar_nextweek.json"]
PAYS = {"USD": "🇺🇸 États-Unis", "EUR": "🇪🇺 Zone euro", "GBP": "🇬🇧 Royaume-Uni", "JPY": "🇯🇵 Japon",
        "CHF": "🇨🇭 Suisse", "CAD": "🇨🇦 Canada", "AUD": "🇦🇺 Australie", "NZD": "🇳🇿 Nouvelle-Zélande",
        "CNY": "🇨🇳 Chine", "All": "🌍 Monde"}
IMPORTANCE = {"High": "forte", "Medium": "moyenne", "Low": "faible", "Holiday": "jour férié"}
# Traductions des indicateurs les plus suivis (le reste garde son nom anglais)
TRADUCTIONS = [
    (r"^Core CPI m/m", "Inflation sous-jacente sur un mois (hors énergie et alimentation)"),
    (r"^Core CPI y/y", "Inflation sous-jacente sur un an"),
    (r"^CPI y/y", "Inflation (prix à la consommation) sur un an"), (r"^CPI m/m", "Inflation sur un mois"),
    (r"^Core CPI m/m", "Inflation sous-jacente sur un mois (hors énergie et alimentation)"),
    (r"^Core CPI y/y", "Inflation sous-jacente sur un an"),
    (r"Flash CPI y/y", "Inflation provisoire sur un an"), (r"Final CPI y/y", "Inflation définitive sur un an"),
    (r"Core PCE Price Index", "Inflation PCE sous-jacente (indicateur préféré de la Fed)"),
    (r"PPI m/m", "Prix à la production sur un mois"),
    (r"Non-Farm Employment Change", "Créations d'emplois hors agriculture (« NFP »)"),
    (r"Unemployment Rate", "Taux de chômage"), (r"Unemployment Claims", "Inscriptions hebdomadaires au chômage"),
    (r"Federal Funds Rate", "Décision de taux de la Fed"), (r"FOMC Statement", "Communiqué de la Fed"),
    (r"FOMC Press Conference", "Conférence de presse de la Fed"), (r"FOMC Meeting Minutes", "Compte rendu de la Fed"),
    (r"Main Refinancing Rate", "Décision de taux de la BCE"), (r"Monetary Policy Statement", "Communiqué de politique monétaire"),
    (r"ECB Press Conference", "Conférence de presse de la BCE"),
    (r"Advance GDP q/q|Prelim GDP q/q|Flash GDP q/q|GDP q/q", "Croissance du PIB sur un trimestre"),
    (r"Core Retail Sales m/m", "Ventes au détail hors automobile"), (r"Retail Sales m/m", "Ventes au détail sur un mois"),
    (r"ISM Manufacturing PMI", "Indice ISM de l'industrie"), (r"ISM Services PMI", "Indice ISM des services"),
    (r"Flash Manufacturing PMI", "Indice PMI provisoire de l'industrie"), (r"Flash Services PMI", "Indice PMI provisoire des services"),
    (r"Manufacturing PMI", "Indice PMI de l'industrie"), (r"Services PMI", "Indice PMI des services"),
    (r"German ifo Business Climate", "Climat des affaires allemand (Ifo)"), (r"ZEW Economic Sentiment", "Confiance des investisseurs (ZEW)"),
    (r"Consumer Confidence|CB Consumer Confidence", "Confiance des consommateurs"),
    (r"Prelim UoM Consumer Sentiment|Revised UoM Consumer Sentiment", "Moral des ménages (université du Michigan)"),
    (r"Trade Balance", "Balance commerciale"), (r"Crude Oil Inventories", "Stocks de pétrole américains"),
    (r"Building Permits", "Permis de construire"), (r"Housing Starts", "Mises en chantier"),
    (r"Existing Home Sales", "Ventes de logements anciens"), (r"New Home Sales", "Ventes de logements neufs"),
    (r"Durable Goods Orders", "Commandes de biens durables"), (r"Industrial Production", "Production industrielle"),
    (r"JOLTS Job Openings", "Offres d'emploi (JOLTS)"), (r"ADP Non-Farm Employment Change", "Créations d'emplois privées (ADP)"),
    (r"Average Hourly Earnings", "Salaire horaire moyen"), (r"Bank Holiday", "Jour férié (marchés fermés)"),
    (r"Speaks", "Discours"),
]

_cache, _verrou = {}, threading.Lock()


def _traduire(titre: str) -> str:
    for motif, fr in TRADUCTIONS:
        if re.search(motif, titre):
            if motif == "Speaks":
                return titre.replace("Speaks", "— discours")
            return fr
    return titre


def evenements() -> list:
    with _verrou:
        v = _cache.get("eco")
        if v and time.time() - v[0] < 3600:
            return v[1]
    tous = []
    for url in FLUX:
        try:
            r = requests.get(url, headers=ENTETES, timeout=15)
            if r.status_code == 200:
                tous += r.json()
        except Exception:
            continue
    res = []
    for e in tous:
        try:
            d = pd.Timestamp(e["date"]).tz_convert("Europe/Paris")
        except Exception:
            continue
        res.append({"date": d.strftime("%Y-%m-%d"), "heure": d.strftime("%H:%M") if e.get("impact") != "Holiday" else "",
                    "pays": PAYS.get(e.get("country"), e.get("country")), "code_pays": e.get("country"),
                    "titre": _traduire(e.get("title", "")), "titre_original": e.get("title", ""),
                    "importance": IMPORTANCE.get(e.get("impact"), e.get("impact")), "niveau": e.get("impact"),
                    "prevision": e.get("forecast") or "", "precedent": e.get("previous") or "",
                    "_t": d.timestamp()})
    res.sort(key=lambda x: x["_t"])
    for x in res:
        x.pop("_t")
    import json
    import chemins
    sauvegarde = chemins.UTILISATEUR / "calendrier.json"
    if res:
        with _verrou:
            _cache["eco"] = (time.time(), res)
        try:            # copie de secours si la source limite ensuite le nombre de requêtes
            chemins.UTILISATEUR.mkdir(parents=True, exist_ok=True)
            sauvegarde.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    else:
        try:
            res = json.loads(sauvegarde.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            res = []
    return res


def resultats() -> list:
    """Prochaines publications de résultats des grandes entreprises (Yahoo Finance)."""
    with _verrou:
        v = _cache.get("resultats")
        if v and time.time() - v[0] < 3 * 3600:
            return v[1]
    res = []
    try:
        import yfinance as yf
        df = yf.Calendars().get_earnings_calendar(limit=100)
        df = df.reset_index()
        for _, l in df.iterrows():
            d = pd.Timestamp(l.get("Event Start Date"))
            res.append({"ticker": l.get("Symbol") or l.get("index"), "nom": l.get("Company"),
                        "date": d.strftime("%Y-%m-%d") if not pd.isna(d) else "",
                        "heure": d.tz_convert("Europe/Paris").strftime("%H:%M") if d.tzinfo else "",
                        "capi": float(l.get("Marketcap")) if not pd.isna(l.get("Marketcap")) else None,
                        "bpa_attendu": float(l.get("EPS Estimate")) if not pd.isna(l.get("EPS Estimate")) else None,
                        "moment": {"BMO": "avant l'ouverture", "AMC": "après la clôture"}.get(l.get("Timing"), "")})
        res.sort(key=lambda x: (x["date"], -(x["capi"] or 0)))
    except Exception:
        pass
    if res:                       # un échec ponctuel de Yahoo ne doit pas rester en mémoire 3 heures
        with _verrou:
            _cache["resultats"] = (time.time(), res)
    return res


if __name__ == "__main__":
    ev = evenements()
    print(len(ev), "événements")
    for e in [x for x in ev if x["niveau"] == "High"][:12]:
        print(e["date"], e["heure"], e["pays"], "|", e["titre"], "| prév.", e["prevision"], "| préc.", e["precedent"])
    r = resultats()
    print(len(r), "publications", r[:3])
