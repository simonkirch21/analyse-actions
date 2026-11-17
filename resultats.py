"""
PUBLICATIONS DE RÉSULTATS — Au-dessus ou en dessous des attentes, et la réaction du cours
=========================================================================================

Quatre fois par an (deux fois pour beaucoup d'entreprises européennes), l'entreprise publie ses
résultats. Le marché ne réagit pas au chiffre lui-même mais à l'ÉCART avec le consensus des
analystes : un bénéfice en hausse de 20 % peut faire baisser l'action si on attendait +30 %.

Pour chaque publication : bénéfice par action (BPA) attendu, publié, surprise en %, et réaction
du cours le jour de la publication (comparée à celle de l'indice, pour isoler l'effet propre).
"""

import html
import math

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf


def _f(x):
    try:
        x = float(x)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def analyser(ticker: str, indice: str) -> dict:
    try:
        d = yf.Ticker(ticker).get_earnings_dates(limit=16)
    except Exception:
        d = None
    if d is None or d.empty:
        return {"applicable": False, "raison": "Yahoo Finance ne fournit pas l'historique des publications de cette entreprise "
                "(fréquent pour les entreprises européennes qui ne publient leurs bénéfices que deux fois par an)."}
    d = d.sort_index()
    px = yf.download([ticker, indice], period="5y", progress=False, auto_adjust=True)["Close"].dropna(how="all")
    if px.index.tz is None:
        px.index = px.index.tz_localize("UTC")
    tz_place = "Europe/Paris" if "." in ticker and not ticker.endswith((".L",)) else "America/New_York"
    if ticker.endswith(".L"):
        tz_place = "Europe/London"
    fermeture = 17 if tz_place != "America/New_York" else 16
    jours = pd.DatetimeIndex(px.index.tz_convert(tz_place).date)

    publications, futures = [], []
    for quand, l in d.iterrows():
        local = quand.tz_convert(tz_place)
        est, pub, sur = _f(l.get("EPS Estimate")), _f(l.get("Reported EPS")), _f(l.get("Surprise(%)"))
        if pub is None:
            if local.date() >= pd.Timestamp.now(tz=tz_place).date():
                futures.append({"date": str(local.date()), "bpa_attendu": est})
            continue
        # Jour de réaction : le jour même si publié avant/pendant la séance, le lendemain si après la clôture
        jour = pd.Timestamp(local.date())
        if local.hour >= fermeture:
            jour += pd.Timedelta(days=1)
        pos = jours.searchsorted(jour)
        if pos <= 0 or pos >= len(jours):
            continue
        avant, apres = px.iloc[pos - 1], px.iloc[pos]
        reac = _f(apres[ticker] / avant[ticker] - 1)
        reac_ind = _f(apres[indice] / avant[indice] - 1)
        publications.append({"date": str(local.date()), "bpa_attendu": est, "bpa_publie": pub,
                             "surprise": sur / 100 if sur is not None else None, "reaction": reac,
                             "reaction_indice": reac_ind, "reaction_propre": (reac - reac_ind) if reac is not None and reac_ind is not None else None})
    if not publications:
        return {"applicable": False, "raison": "Pas de publication passée exploitable dans les données de Yahoo Finance."}

    pubs = publications[-12:]
    battues = [p for p in pubs if p["surprise"] is not None and p["surprise"] > 0]
    ratees = [p for p in pubs if p["surprise"] is not None and p["surprise"] < 0]
    moy = lambda xs: float(np.mean(xs)) if xs else None
    reac_b = moy([p["reaction_propre"] for p in battues if p["reaction_propre"] is not None])
    reac_r = moy([p["reaction_propre"] for p in ratees if p["reaction_propre"] is not None])
    paradoxes = [p for p in pubs if p["surprise"] and p["reaction_propre"] is not None and p["surprise"] > 0 and p["reaction_propre"] < -0.02]
    return {"applicable": True, "publications": pubs, "prochaines": futures[:1], "nb": len(pubs),
            "taux_battues": len(battues) / len(pubs), "surprise_moyenne": moy([p["surprise"] for p in pubs if p["surprise"] is not None]),
            "reaction_battues": reac_b, "reaction_ratees": reac_r,
            "mouvement_moyen": moy([abs(p["reaction"]) for p in pubs if p["reaction"] is not None]),
            "paradoxes": paradoxes}


def _p(x, d=1, signe=True):
    return "—" if x is None else f"{x * 100:{'+' if signe else ''}.{d}f} %".replace(".", ",").replace("-", "−")


def _n(x, d=2):
    return "—" if x is None else f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def graphique(r: dict, ticker: str, fichier: str) -> None:
    p = r["publications"]
    x = np.arange(len(p))
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 5.6), sharex=True)
    s = [q["surprise"] * 100 if q["surprise"] is not None else 0 for q in p]
    a1.bar(x, s, color=["#3BC48F" if v >= 0 else "#FF6B5A" for v in s], width=0.6)
    a1.axhline(0, color="#8D94A5", lw=0.8)
    a1.set_ylabel("Surprise sur le BPA (%)")
    a1.set_title(f"{ticker} : écart entre bénéfice publié et attendu, et réaction du cours", loc="left")
    rp = [q["reaction_propre"] * 100 if q["reaction_propre"] is not None else 0 for q in p]
    a2.bar(x, rp, color=["#3BC48F" if v >= 0 else "#FF6B5A" for v in rp], width=0.6)
    a2.axhline(0, color="#8D94A5", lw=0.8)
    a2.set_ylabel("Réaction du cours\nvs indice (%)")
    a2.set_xticks(x)
    a2.set_xticklabels([q["date"][:7] for q in p], rotation=45, ha="right", fontsize=8.5)
    for a in (a1, a2):
        a.set_axisbelow(True)
        a.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(fichier, dpi=110)
    plt.close(fig)


def section_html(r: dict, graph: str = "") -> str:
    h = "<h2 id='resultats'>Publications de résultats</h2>"
    h += ("<div class='notion'><b>La notion.</b> Avant chaque publication, les analystes estiment le bénéfice par action (BPA). "
          "Le cours ne réagit pas au résultat lui-même mais à la <b>surprise</b> : l'écart entre le publié et l'attendu. "
          "Une entreprise peut annoncer un bénéfice record et chuter si le marché espérait plus, ou si ses prévisions pour la "
          "suite déçoivent. La réaction est mesurée le jour de la publication (le lendemain si elle a lieu après la clôture), "
          "en retirant le mouvement de l'indice ce jour-là.</div>")
    if not r or not r.get("applicable"):
        return h + f"<p class='note'>{html.escape((r or {}).get('raison', 'Données indisponibles.'))}</p>"
    lect = [f"Sur les {r['nb']} dernières publications, l'entreprise a <b>dépassé les attentes {round(r['taux_battues'] * r['nb'])} fois</b> "
            f"({_p(r['taux_battues'], 0, False)}), avec une surprise moyenne de {_p(r['surprise_moyenne'])}. "
            + ("Battre le consensus est courant (les entreprises guident les analystes vers des chiffres atteignables) : c'est "
               "surtout un échec qui inquiète." if r["taux_battues"] >= 0.6 else "C'est peu : les analystes sont souvent trop optimistes sur cette entreprise.")]
    if r["mouvement_moyen"] is not None:
        lect.append(f"Le jour d'une publication, l'action bouge en moyenne de <b>±{_p(r['mouvement_moyen'], 1, False)}</b>"
                    + (f" ; après une bonne surprise, elle a fait en moyenne {_p(r['reaction_battues'])} de mieux que l'indice"
                       if r["reaction_battues"] is not None else "")
                    + (f", après une mauvaise {_p(r['reaction_ratees'])}" if r["reaction_ratees"] is not None else "") + ".")
    if r["paradoxes"]:
        x = r["paradoxes"][-1]
        lect.append(f"<b>Le paradoxe</b> : le {x['date']}, le bénéfice a dépassé les attentes de {_p(x['surprise'])} et pourtant "
                    f"l'action a fait {_p(x['reaction_propre'])} de moins que l'indice. Le marché regardait autre chose : "
                    "les perspectives annoncées, le chiffre d'affaires, ou des attentes officieuses plus élevées que le consensus.")
    if r["prochaines"]:
        q = r["prochaines"][0]
        lect.append(f"Prochaine publication attendue le <b>{q['date']}</b>"
                    + (f", avec un BPA attendu de {_n(q['bpa_attendu'])}." if q["bpa_attendu"] is not None else "."))
    h += "<div class='lecture'>" + "".join(f"<p>{x}</p>" for x in lect) + "</div>"
    lignes = "".join(
        f"<tr><td>{p['date']}</td><td>{_n(p['bpa_attendu'])}</td><td>{_n(p['bpa_publie'])}</td>"
        f"<td class='{'pos' if (p['surprise'] or 0) >= 0 else 'neg'}'>{_p(p['surprise'])}</td>"
        f"<td>{_p(p['reaction'])}</td><td class='{'pos' if (p['reaction_propre'] or 0) >= 0 else 'neg'}'>{_p(p['reaction_propre'])}</td></tr>"
        for p in reversed(r["publications"]))
    h += ("<div class='carte'><table><tr><th>Date</th><th>BPA attendu</th><th>BPA publié</th><th>Surprise</th>"
          f"<th>Réaction du cours</th><th>Réaction vs indice</th></tr>{lignes}</table></div>")
    return h + graph + "<p class='note'>Source : Yahoo Finance (BPA ajusté, consensus des analystes au moment de la publication).</p>"


if __name__ == "__main__":
    import sys
    r = analyser(sys.argv[1] if len(sys.argv) > 1 else "AIR.PA", sys.argv[2] if len(sys.argv) > 2 else "^FCHI")
    print({k: v for k, v in r.items() if k not in ("publications",)})
    for p in r.get("publications", [])[-5:]:
        print(p)
