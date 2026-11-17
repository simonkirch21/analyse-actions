"""
DIVIDENDES — Historique, croissance, solidité et réinvestissement
=================================================================

  - Dividende par action, année par année, et sa croissance annuelle moyenne (5 et 10 ans)
  - Années consécutives de hausse (les « aristocrates » en comptent 25 et plus) et années de baisse
  - Rendement (dividendes des 12 derniers mois / cours) et taux de distribution (dividendes / bénéfice)
  - Réinvestissement : 10 000 investis il y a 10 ans, dividendes encaissés ou réinvestis
  - Pour un portefeuille : revenu annuel estimé et calendrier des versements, mois par mois
"""

import html
import math

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf

from partie8_analyse_financiere import _ligne

MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def _f(x):
    try:
        x = float(x)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def analyser(ticker: str, fin: dict = None) -> dict:
    k = yf.Ticker(ticker)
    div = k.dividends
    if div is None or div.empty:
        return {"applicable": False, "raison": "Cette entreprise ne verse pas de dividende (ou Yahoo Finance n'en a pas l'historique). "
                "Elle peut réinvestir tous ses bénéfices dans sa croissance, ou rendre l'argent par des rachats d'actions."}
    div.index = div.index.tz_localize(None) if div.index.tz is not None else div.index
    auj = pd.Timestamp.today()
    par_an = div.groupby(div.index.year).sum()
    complet = par_an[par_an.index < auj.year]
    complet = complet[complet.index >= auj.year - 15]
    tcam = lambda n: (complet.iloc[-1] / complet.iloc[-1 - n]) ** (1 / n) - 1 if len(complet) > n and complet.iloc[-1 - n] > 0 else None
    hausses, baisses = 0, []
    for i in range(len(complet) - 1, 0, -1):
        if complet.iloc[i] >= complet.iloc[i - 1] * 0.999:
            hausses += 1
        else:
            break
    for i in range(1, len(complet)):
        if complet.iloc[i] < complet.iloc[i - 1] * 0.97:
            baisses.append(int(complet.index[i]))
    hist = k.history(period="10y", auto_adjust=False)
    hist.index = hist.index.tz_localize(None) if hist.index.tz is not None else hist.index
    cours = float(hist["Close"].dropna().iloc[-1])
    d12 = float(div[div.index > auj - pd.DateOffset(years=1)].sum())
    rendement = d12 / cours if cours else None
    payout = None
    if fin and fin.get("applicable"):
        fl, cr = fin["brut"]["flux"], fin["brut"]["cr"]
        an = fin["annees"][-1]
        verse = _f(-_ligne(fl, "Cash Dividends Paid", "Common Stock Dividend Paid").get(an))
        rn = _f(_ligne(cr, "Net Income").get(an))
        payout = verse / rn if verse and rn and rn > 0 else None
    # Réinvestissement : cours seul (dividendes encaissés à part) contre cours ajusté (dividendes réinvestis)
    reinv = None
    c, adj = hist["Close"].dropna(), hist["Adj Close"].dropna()
    if len(c) > 250:
        mise = 10000.0
        prix_seul = mise * c.iloc[-1] / c.iloc[0]
        reinvesti = mise * adj.iloc[-1] / adj.iloc[0]
        actions = mise / c.iloc[0]
        encaisses = float(div[(div.index >= c.index[0])].sum()) * actions
        annees = (c.index[-1] - c.index[0]).days / 365.25
        reinv = {"debut": str(c.index[0].date()), "annees": annees, "prix_seul": prix_seul, "encaisses": encaisses,
                 "sans_reinvestir": prix_seul + encaisses, "reinvesti": reinvesti,
                 "rdt_prix": (prix_seul / mise) ** (1 / annees) - 1, "rdt_total": (reinvesti / mise) ** (1 / annees) - 1,
                 "serie_prix": [[str(d.date()), float(v)] for d, v in (mise * c / c.iloc[0]).resample("ME").last().items()],
                 "serie_total": [[str(d.date()), float(v)] for d, v in (mise * adj / adj.iloc[0]).resample("ME").last().items()]}
    mois = sorted({d.month for d in div.index if d > auj - pd.DateOffset(years=2)})
    return {"applicable": True, "par_an": {int(a): float(v) for a, v in par_an[par_an.index >= auj.year - 15].items()},
            "annee_en_cours": int(auj.year), "tcam5": tcam(5), "tcam10": tcam(10), "hausses_consecutives": hausses,
            "baisses": baisses, "rendement": rendement, "dividende_12m": d12, "cours": cours, "payout": payout,
            "reinvestissement": reinv, "mois_versement": mois, "devise": (fin or {}).get("devise", "")}


def _p(x, d=1, signe=False):
    return "—" if x is None else f"{x * 100:{'+' if signe else ''}.{d}f} %".replace(".", ",").replace("-", "−")


def _n(x, d=2):
    return "—" if x is None else f"{x:,.{d}f}".replace(",", " ").replace(".", ",").replace("-", "−")


def graphique(d: dict, ticker: str, fichier: str) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.8), gridspec_kw={"width_ratios": [1.1, 1]})
    ans = sorted(d["par_an"])
    vals = [d["par_an"][a] for a in ans]
    couleurs = ["#4A5470" if a == d["annee_en_cours"] else ("#FF6B5A" if a in d["baisses"] else "#D4AF6A") for a in ans]
    a1.bar([str(a) for a in ans], vals, color=couleurs)
    a1.set_title("Dividende par action, par année (en rouge : baisse)", loc="left", fontsize=10.5)
    a1.tick_params(axis="x", rotation=45, labelsize=8)
    a1.set_axisbelow(True)
    a1.grid(axis="y", alpha=0.25)
    r = d.get("reinvestissement")
    if r:
        x1 = pd.to_datetime([p[0] for p in r["serie_total"]])
        a2.plot(x1, [p[1] for p in r["serie_total"]], color="#3BC48F", label="Dividendes réinvestis")
        x2 = pd.to_datetime([p[0] for p in r["serie_prix"]])
        a2.plot(x2, [p[1] for p in r["serie_prix"]], color="#6EA8FF", label="Cours seul")
        a2.set_title("10 000 investis : l'effet du réinvestissement", loc="left", fontsize=10.5)
        a2.legend(fontsize=8.5)
        a2.set_axisbelow(True)
        a2.grid(alpha=0.25)
    else:
        a2.axis("off")
    fig.tight_layout()
    fig.savefig(fichier, dpi=110)
    plt.close(fig)


def section_html(d: dict, graph: str = "") -> str:
    h = "<h2 id='dividendes'>Dividendes</h2>"
    h += ("<div class='notion'><b>La notion.</b> Le dividende est la part du bénéfice versée aux actionnaires. Trois questions : "
          "<b>combien</b> (le rendement, dividende / cours), <b>est-il solide</b> (le taux de distribution, dividende / bénéfice : "
          "au-delà de 80-90 %, l'entreprise distribue presque tout et a peu de marge en cas de coup dur) et <b>grandit-il</b> (sa "
          "croissance sur 5 ou 10 ans). Sur longue période, le réinvestissement des dividendes explique une grande partie de la "
          "performance des actions : c'est l'effet boule de neige des intérêts composés.</div>")
    if not d or not d.get("applicable"):
        return h + f"<p class='note'>{html.escape((d or {}).get('raison', 'Données indisponibles.'))}</p>"
    lect = [f"Dividendes des 12 derniers mois : <b>{_n(d['dividende_12m'])}</b> par action, soit un rendement de <b>{_p(d['rendement'])}</b> au cours actuel."]
    if d["payout"] is not None:
        po = d["payout"]
        lect.append(f"Taux de distribution : <b>{_p(po, 0)}</b> du bénéfice. "
                    + ("Prudent : l'entreprise garde l'essentiel pour investir, le dividende a de la marge." if po < 0.5 else
                       "Équilibré." if po < 0.8 else "Élevé : presque tout le bénéfice est distribué ; une baisse des résultats menacerait le dividende."
                       if po < 1.05 else "Supérieur au bénéfice : le dividende est payé en partie sur les réserves ou la dette, ce n'est pas tenable longtemps."))
    if d["tcam5"] is not None:
        lect.append(f"Croissance du dividende : <b>{_p(d['tcam5'], 1, True)} par an sur 5 ans</b>"
                    + (f", {_p(d['tcam10'], 1, True)} sur 10 ans" if d["tcam10"] is not None else "") + ". "
                    + (f"Il a augmenté (ou été maintenu) {d['hausses_consecutives']} années de suite." if d["hausses_consecutives"] >= 3 else "")
                    + (f" Baisses notables en {', '.join(map(str, d['baisses'][-4:]))}." if d["baisses"] else " Aucune baisse notable sur la période."))
    r = d.get("reinvestissement")
    if r:
        lect.append(f"Depuis le {r['debut']}, 10 000 investis seraient devenus <b>{_n(r['reinvesti'], 0)}</b> en réinvestissant les dividendes "
                    f"({_p(r['rdt_total'], 1, True)} par an), contre {_n(r['sans_reinvestir'], 0)} en les encaissant "
                    f"({_n(r['prix_seul'], 0)} de capital + {_n(r['encaisses'], 0)} de dividendes perçus). "
                    "En France, les dividendes sont imposés à 30 % (flat tax) hors PEA : le PEA permet de les réinvestir sans impôt.")
    if d["mois_versement"]:
        lect.append("Versements habituels en : " + ", ".join(MOIS[m - 1] for m in d["mois_versement"]) + " (dates de détachement).")
    return h + "<div class='lecture'>" + "".join(f"<p>{x}</p>" for x in lect) + "</div>" + graph


# ---------------------------------------------------------------------------
# Portefeuille : revenu estimé et calendrier
# ---------------------------------------------------------------------------
def calendrier_portefeuille(lignes: list) -> dict:
    auj = pd.Timestamp.today()
    res, mois = [], [0.0] * 12
    for l in lignes:
        t, montant = l.get("ticker"), float(l.get("montant") or 0)
        if not t or t == "SANS_RISQUE" or montant <= 0:
            continue
        try:
            k = yf.Ticker(t)
            div = k.dividends
            div.index = div.index.tz_localize(None) if div.index.tz is not None else div.index
            der = div[div.index > auj - pd.DateOffset(years=1)]
            cours = float(k.history(period="5d")["Close"].dropna().iloc[-1])
        except Exception:
            continue
        rdt = float(der.sum()) / cours if cours and len(der) else 0.0
        revenu = montant * rdt
        versements = [(d.month, float(v)) for d, v in der.items()]
        total = sum(v for _, v in versements) or 1
        for m, v in versements:
            mois[m - 1] += revenu * v / total
        res.append({"ticker": t, "nom": l.get("nom") or t, "montant": montant, "rendement": rdt, "revenu": revenu,
                    "mois": sorted({m for m, _ in versements})})
    res.sort(key=lambda x: -x["revenu"])
    total = sum(x["revenu"] for x in res)
    investi = sum(x["montant"] for x in res)
    return {"lignes": res, "par_mois": [{"mois": MOIS[i], "montant": v} for i, v in enumerate(mois)], "total": total,
            "rendement": total / investi if investi else None, "apres_impot": total * 0.7}


if __name__ == "__main__":
    import sys
    import partie8_analyse_financiere as p8
    t = sys.argv[1] if len(sys.argv) > 1 else "TTE.PA"
    d = analyser(t, p8.analyser(t))
    print({k: v for k, v in d.items() if k not in ("reinvestissement",)})
    r = d.get("reinvestissement") or {}
    print({k: v for k, v in r.items() if not k.startswith("serie")})
