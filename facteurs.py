"""
MODÈLE À FACTEURS — Fama-French (5 facteurs) + momentum
=======================================================

Le CAPM explique le rendement d'une action par un seul facteur : le marché (bêta). Fama et French
ont montré que d'autres « styles » expliquent une grande partie des écarts de rendement :

  Mkt-RF  le marché (comme le bêta du CAPM)
  SMB     Small Minus Big : petites capitalisations contre grandes
  HML     High Minus Low : actions « value » (bon marché, valeur comptable élevée) contre « growth »
  RMW     Robust Minus Weak : entreprises très rentables contre peu rentables
  CMA     Conservative Minus Aggressive : entreprises qui investissent peu contre beaucoup
  MOM     Momentum (Carhart) : gagnantes des 12 derniers mois contre perdantes

La régression des rendements de l'action sur ces facteurs donne son « ADN de style » ; l'alpha est
ce qui reste inexpliqué. Données : bibliothèque de Kenneth French (Dartmouth), zone Europe ou
États-Unis, rendements quotidiens en dollars.
"""

import io
import math
import time
import zipfile

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import requests
import yfinance as yf
from scipy import stats

import chemins

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FICHIERS = {"us": ("F-F_Research_Data_5_Factors_2x3_daily_CSV.zip", "F-F_Momentum_Factor_daily_CSV.zip"),
            "europe": ("Europe_5_Factors_Daily_CSV.zip", "Europe_Mom_Factor_Daily_CSV.zip")}
NOMS = {"Mkt-RF": "Marché", "SMB": "Taille (petites − grandes)", "HML": "Value (décotées − croissance)",
        "RMW": "Rentabilité (fortes − faibles)", "CMA": "Investissement (prudentes − agressives)", "MOM": "Momentum"}
ENTETES = {"User-Agent": "Mozilla/5.0 (Macintosh) analyse-action"}


def _lire_zip(contenu: bytes) -> pd.DataFrame:
    z = zipfile.ZipFile(io.BytesIO(contenu))
    texte = z.read(z.namelist()[0]).decode("latin-1")
    lignes = texte.splitlines()
    debut = next(i for i, l in enumerate(lignes) if l.strip() and l.split(",")[0].strip().isdigit() and len(l.split(",")[0].strip()) == 8)
    entete = lignes[debut - 1]
    corps = []
    for l in lignes[debut:]:
        c = l.split(",")[0].strip()
        if not (c.isdigit() and len(c) == 8):
            break
        corps.append(l)
    df = pd.read_csv(io.StringIO(entete + "\n" + "\n".join(corps)), index_col=0)
    df.index = pd.to_datetime(df.index.astype(str), format="%Y%m%d")
    df.columns = [c.strip() for c in df.columns]
    return df.apply(pd.to_numeric, errors="coerce") / 100


def facteurs(zone: str) -> pd.DataFrame:
    """Facteurs quotidiens (fichier local rafraîchi tous les 15 jours)."""
    cache = chemins.UTILISATEUR / f"facteurs_{zone}.pkl"
    try:
        if time.time() - cache.stat().st_mtime < 15 * 86400:
            return pd.read_pickle(cache)
    except OSError:
        pass
    try:
        cinq, mom = (requests.get(BASE + f, headers=ENTETES, timeout=40).content for f in FICHIERS[zone])
        df = _lire_zip(cinq).join(_lire_zip(mom).iloc[:, :1].rename(columns=lambda c: "MOM"), how="inner")
        chemins.UTILISATEUR.mkdir(parents=True, exist_ok=True)
        df.to_pickle(cache)
        return df
    except Exception:
        if cache.exists():
            return pd.read_pickle(cache)
        raise


def analyser(ticker: str, devise: str = "") -> dict:
    zone = "us" if "." not in ticker else "europe"
    if ticker.endswith((".T", ".HK", ".AX")):
        return {"applicable": False, "raison": "Facteurs disponibles seulement pour les actions européennes et américaines."}
    ff = facteurs(zone)
    debut = ff.index[-1] - pd.DateOffset(years=3)
    px = yf.download(ticker, start=debut.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)["Close"].squeeze().dropna()
    r = px.pct_change().dropna()
    r.index = r.index.tz_localize(None) if r.index.tz is not None else r.index
    # Facteurs européens exprimés en dollars : on convertit les rendements de l'action en dollars
    if zone == "europe" and devise and devise != "USD":
        fx = yf.download(f"{devise}USD=X", start=debut.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)["Close"].squeeze().dropna()
        fx.index = fx.index.tz_localize(None) if fx.index.tz is not None else fx.index
        rfx = fx.pct_change().reindex(r.index).fillna(0)
        r = (1 + r) * (1 + rfx) - 1
    d = pd.concat([r.rename("r"), ff], axis=1, join="inner").dropna()
    d = d[d.index >= debut]
    if len(d) < 150:
        return {"applicable": False, "raison": "Historique commun trop court avec les facteurs."}
    noms = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "MOM"]
    y = (d["r"] - d["RF"]).values
    X = np.column_stack([np.ones(len(d))] + [d[c].values for c in noms])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ coef
    n, k = X.shape
    s2 = res @ res / (n - k)
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    t = coef / se
    r2 = 1 - res.var() / y.var()
    # CAPM simple pour comparer le pouvoir explicatif
    Xc = X[:, :2]
    cc, *_ = np.linalg.lstsq(Xc, y, rcond=None)
    r2_capm = 1 - (y - Xc @ cc).var() / y.var()
    charges = [{"facteur": c, "nom": NOMS[c], "beta": float(coef[i + 1]), "t": float(t[i + 1]),
                "significatif": abs(t[i + 1]) > 2, "ic": float(1.96 * se[i + 1])} for i, c in enumerate(noms)]
    return {"applicable": True, "zone": "Europe" if zone == "europe" else "États-Unis", "debut": str(d.index[0].date()),
            "fin": str(d.index[-1].date()), "jours": len(d), "alpha_annuel": float(coef[0] * 252), "t_alpha": float(t[0]),
            "p_alpha": float(2 * (1 - stats.t.cdf(abs(t[0]), n - k))), "r2": float(r2), "r2_capm": float(r2_capm),
            "charges": charges, "profil": profil(charges)}


def profil(charges: list) -> str:
    c = {x["facteur"]: x for x in charges}
    mots = []
    s = c["SMB"]
    if s["significatif"]:
        mots.append("de petite capitalisation" if s["beta"] > 0.15 else "de grande capitalisation" if s["beta"] < -0.15 else "")
    h = c["HML"]
    if h["significatif"]:
        mots.append("de style « value » (décotée)" if h["beta"] > 0.15 else "de croissance (« growth »)" if h["beta"] < -0.15 else "")
    q = c["RMW"]
    if q["significatif"]:
        mots.append("très rentable (« qualité »)" if q["beta"] > 0.15 else "peu rentable" if q["beta"] < -0.15 else "")
    i = c["CMA"]
    if i["significatif"]:
        mots.append("qui investit prudemment" if i["beta"] > 0.15 else "qui investit agressivement" if i["beta"] < -0.15 else "")
    m = c["MOM"]
    if m["significatif"]:
        mots.append("qui suit la tendance (momentum)" if m["beta"] > 0.1 else "à contre-tendance" if m["beta"] < -0.1 else "")
    mots = [x for x in mots if x]
    b = c["Mkt-RF"]["beta"]
    debut = "plus sensible au marché que la moyenne" if b > 1.15 else "moins sensible au marché que la moyenne" if b < 0.85 else "aussi sensible au marché que la moyenne"
    return f"Cette action se comporte comme une entreprise {debut}" + (", " + ", ".join(mots) if mots else ", sans style marqué") + "."


def _n(x, d=2):
    return "—" if x is None else f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def _p(x, d=1, signe=True):
    return "—" if x is None else f"{x * 100:{'+' if signe else ''}.{d}f} %".replace(".", ",").replace("-", "−")


def graphique(f: dict, ticker: str, fichier: str) -> None:
    c = f["charges"]
    fig, ax = plt.subplots(figsize=(10, 3.6))
    y = np.arange(len(c))[::-1]
    couleurs = ["#D4AF6A" if x["significatif"] else "#4A5470" for x in c]
    ax.barh(y, [x["beta"] for x in c], xerr=[x["ic"] for x in c], color=couleurs, ecolor="#8D94A5", capsize=3, height=0.55)
    ax.axvline(0, color="#8D94A5", lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels([x["nom"] for x in c], fontsize=9.5)
    ax.set_title(f"{ticker} : exposition aux facteurs (en or : significatif, |t| > 2 ; trait : intervalle à 95 %)", loc="left", fontsize=10.5)
    ax.set_axisbelow(True)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(fichier, dpi=110)
    plt.close(fig)


def section_html(f: dict, graph: str = "") -> str:
    h = "<h2 id='facteurs'>Modèle à facteurs (Fama-French)</h2>"
    h += ("<div class='notion'><b>La notion.</b> Le CAPM n'utilise qu'un facteur, le marché. Fama et French (prix Nobel 2013 pour "
          "Fama) ont montré que les actions se distinguent aussi par leur <b>style</b> : taille (petites ou grandes), valorisation "
          "(value ou croissance), rentabilité, politique d'investissement, et dynamique récente (momentum, Carhart). Une "
          "régression sur ces facteurs donne l'« ADN » de l'action ; l'<b>alpha</b> est ce qu'aucun style n'explique. "
          "Une exposition positive à un facteur signifie que l'action monte quand ce style surperforme.</div>")
    if not f or not f.get("applicable"):
        return h + f"<p class='note'>{html_esc((f or {}).get('raison', 'Données indisponibles.'))}</p>"
    lect = [f"<b>{f['profil']}</b>",
            f"Les six facteurs expliquent <b>{_p(f['r2'], 0, False)}</b> des variations quotidiennes de l'action, contre "
            f"{_p(f['r2_capm'], 0, False)} pour le marché seul (CAPM) : "
            + ("les styles apportent une vraie information en plus du bêta." if f["r2"] - f["r2_capm"] > 0.05 else "le marché explique déjà presque tout ce que les styles expliquent."),
            f"Alpha annualisé : <b>{_p(f['alpha_annuel'])}</b> (p = {_n(f['p_alpha'], 3)}). "
            + ("Significatif : une surperformance que les styles n'expliquent pas (talent, avantage concurrentiel… ou chance sur la période)."
               if f["p_alpha"] < 0.05 else "Non significatif : une fois les styles pris en compte, rien ne distingue statistiquement l'action.")]
    h += "<div class='lecture'>" + "".join(f"<p>{x}</p>" for x in lect) + "</div>" + graph
    lignes = "".join(f"<tr><td>{x['nom']} <span class='note'>({x['facteur']})</span></td><td>{_n(x['beta'])}</td>"
                     f"<td>{_n(x['t'])}</td><td>{'oui' if x['significatif'] else 'non'}</td></tr>" for x in f["charges"])
    h += ("<div class='carte'><table><tr><th>Facteur</th><th>Exposition (β)</th><th>t de Student</th><th>Significatif</th></tr>"
          + lignes + "</table></div>")
    return h + (f"<p class='note'>Régression des rendements quotidiens en dollars (au-delà du taux sans risque) du {f['debut']} au "
                f"{f['fin']} ({f['jours']} séances), facteurs {f['zone']} de la bibliothèque de Kenneth French.</p>")


def html_esc(s):
    import html
    return html.escape(str(s))


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "AIR.PA"
    r = analyser(t, sys.argv[2] if len(sys.argv) > 2 else "EUR")
    print({k: v for k, v in r.items() if k != "charges"})
    for c in r.get("charges", []):
        print(f"  {c['facteur']:7s} {c['beta']:+.3f}  t={c['t']:+.2f}")
