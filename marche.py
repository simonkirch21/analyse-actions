"""
MARCHÉ — Données du tableau de bord de l'accueil
================================================

  - les grands indices boursiers et quelques repères macroéconomiques (pétrole, or, euro/dollar,
    taux américain à 10 ans, indice de volatilité VIX), avec leur historique complet ;
  - les valeurs phares (grandes capitalisations) ;
  - les plus fortes hausses / baisses du jour et les actions les plus volatiles, calculées sur
    l'ensemble du S&P 500 et les 100 actions les plus échangées d'Euronext.

Les calculs sont mis en cache (quelques minutes à une heure) pour que l'accueil s'affiche vite.
"""

import json
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

import chemins
LISTE = chemins.liste_actions()

# (code Yahoo, nom, zone, unité, explication pour débutant)
INDICES = [
    ("^FCHI", "CAC 40", "France", "points",
     "Les 40 plus grandes entreprises cotées à Paris (LVMH, TotalEnergies, Airbus…). C'est le baromètre de la Bourse française."),
    ("^STOXX50E", "Euro Stoxx 50", "Zone euro", "points",
     "Les 50 plus grandes entreprises de la zone euro : l'indice de référence pour l'Europe."),
    ("^GDAXI", "DAX", "Allemagne", "points",
     "Les 40 plus grandes entreprises allemandes. Attention : contrairement au CAC 40, il inclut les dividendes réinvestis."),
    ("^FTSE", "FTSE 100", "Royaume-Uni", "points",
     "Les 100 plus grandes entreprises cotées à Londres, très présentes dans l'énergie, les mines et la banque."),
    ("^GSPC", "S&P 500", "États-Unis", "points",
     "Les 500 plus grandes entreprises américaines : environ 60 % de la capitalisation boursière mondiale."),
    ("^IXIC", "Nasdaq Composite", "États-Unis", "points",
     "Plus de 3 000 valeurs cotées sur le Nasdaq, dominé par la technologie (Apple, Nvidia, Microsoft…)."),
    ("^DJI", "Dow Jones", "États-Unis", "points",
     "Le plus ancien indice (1896) : 30 grandes entreprises américaines, pondérées par leur prix et non leur taille."),
    ("^N225", "Nikkei 225", "Japon", "points",
     "Les 225 principales valeurs de la Bourse de Tokyo."),
    ("^VIX", "VIX (indice de la peur)", "États-Unis", "points",
     "Mesure la volatilité attendue du S&P 500 pour le mois à venir. Sous 15 : marché calme ; au-dessus de 30 : forte inquiétude."),
    ("BZ=F", "Pétrole Brent", "Matières premières", "$ / baril",
     "Le prix du baril de pétrole de la mer du Nord, référence mondiale. Il pèse sur l'inflation et les compagnies aériennes."),
    ("GC=F", "Or", "Matières premières", "$ / once",
     "Valeur refuge : l'or monte souvent quand les investisseurs s'inquiètent ou quand l'inflation augmente."),
    ("EURUSD=X", "Euro / dollar", "Devises", "$ pour 1 €",
     "Combien de dollars vaut un euro. Un euro fort pénalise les exportateurs européens."),
    ("^TNX", "Taux US à 10 ans", "Taux d'intérêt", "%",
     "Le taux auquel l'État américain emprunte sur 10 ans : il sert de référence au coût de l'argent dans le monde."),
]

PHARES = ["MC.PA", "TTE.PA", "AIR.PA", "OR.PA", "RMS.PA", "SAN.PA", "BNP.PA", "SU.PA", "ASML.AS",
          "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "JPM", "LLY", "AVGO"]

_cache = {}
_verrou = threading.Lock()
# Signalé par l'application pendant une analyse : le palmarès (calcul lourd sur 600 actions)
# attend alors son tour, pour ne pas ralentir l'analyse que l'utilisateur vient de lancer.
analyse_en_cours = threading.Event()


def _en_cache(cle: str, duree: float, calcul):
    """Renvoie le résultat en cache s'il a moins de `duree` secondes, sinon le recalcule."""
    with _verrou:
        v = _cache.get(cle)
        if v and time.time() - v[0] < duree:
            return v[1]
    resultat = calcul()
    with _verrou:
        _cache[cle] = (time.time(), resultat)
    return resultat


def _noms() -> dict:
    try:
        return {a["ticker"]: a for a in json.loads(LISTE.read_text(encoding="utf-8"))}
    except Exception:
        return {}


def _telecharger(tickers, periode):
    d = yf.download(tickers, period=periode, auto_adjust=True, progress=False, threads=True)["Close"]
    if isinstance(d, pd.Series):
        d = d.to_frame(tickers[0])
    return d


def _variation(s: pd.Series, jours: int = None, depuis=None) -> float:
    s = s.dropna()
    if len(s) < 2:
        return np.nan
    if depuis is not None:
        avant = s[s.index < depuis]
        return s.iloc[-1] / avant.iloc[-1] - 1 if len(avant) else np.nan
    return s.iloc[-1] / s.iloc[-1 - jours] - 1 if len(s) > jours else np.nan


def _points(s: pd.Series, n: int) -> list:
    """Réduit une série à environ n points [date, valeur] pour les graphiques."""
    s = s.dropna()
    if len(s) > n:
        s = s.iloc[np.linspace(0, len(s) - 1, n).astype(int)]
    return [[d.strftime("%Y-%m-%d"), round(float(v), 4)] for d, v in s.items()]


# ---------------------------------------------------------------------------
# Indices
# ---------------------------------------------------------------------------
def historiques_indices() -> pd.DataFrame:
    return _en_cache("indices_max", 3600, lambda: _telecharger([i[0] for i in INDICES], "max"))


def indices() -> list:
    def calcul():
        h = historiques_indices()
        recent = _telecharger([i[0] for i in INDICES], "5d")      # dernier cours à jour
        debut_annee = pd.Timestamp(pd.Timestamp.today().year, 1, 1)
        res = []
        for code, nom, zone, unite, aide in INDICES:
            s = h[code].dropna() if code in h else pd.Series(dtype=float)
            r = recent[code].dropna() if code in recent else pd.Series(dtype=float)
            if len(r):
                s = pd.concat([s[s.index < r.index[0]], r])
            if s.empty:
                continue
            res.append({
                "code": code, "nom": nom, "zone": zone, "unite": unite, "aide": aide,
                "dernier": float(s.iloc[-1]), "date": s.index[-1].strftime("%d/%m/%Y"),
                "var_jour": _variation(s, 1), "var_annee": _variation(s, depuis=debut_annee),
                "var_1an": _variation(s, 252), "depuis": s.index[0].year,
                "mini": _points(s.iloc[-260:], 60),
            })
        return res
    return _en_cache("indices", 300, calcul)


def historique(code: str, periode: str) -> dict:
    """Série d'un indice pour le grand graphique (1m, 6m, 1y, 5y, max)."""
    if code not in [i[0] for i in INDICES]:
        raise ValueError("Indice inconnu")
    s = historiques_indices()[code].dropna()
    jours = {"1m": 31, "6m": 183, "1y": 366, "5y": 1827, "10y": 3653}.get(periode)
    if jours:
        s = s[s.index >= s.index[-1] - pd.Timedelta(days=jours)]
    info = next(i for i in INDICES if i[0] == code)
    return {"code": code, "nom": info[1], "unite": info[3], "points": _points(s, 500),
            "variation": float(s.iloc[-1] / s.iloc[0] - 1), "maxi": float(s.max()), "mini_v": float(s.min())}


# ---------------------------------------------------------------------------
# Valeurs phares
# ---------------------------------------------------------------------------
def phares() -> list:
    def calcul():
        p = _telecharger(PHARES, "1y")
        noms = _noms()
        debut_annee = pd.Timestamp(pd.Timestamp.today().year, 1, 1)
        res = []
        for t in PHARES:
            if t not in p or p[t].dropna().empty:
                continue
            s = p[t].dropna()
            try:
                capi = yf.Ticker(t).fast_info.get("marketCap")
            except Exception:
                capi = None
            info = noms.get(t, {})
            res.append({"ticker": t, "nom": info.get("nom", t), "place": info.get("place", ""),
                        "devise": info.get("devise", ""), "dernier": float(s.iloc[-1]),
                        "var_jour": _variation(s, 1), "var_annee": _variation(s, depuis=debut_annee),
                        "capi": capi, "mini": _points(s.iloc[-65:], 40)})
        res.sort(key=lambda x: -(x["capi"] or 0))
        return res
    return _en_cache("phares", 900, calcul)


# ---------------------------------------------------------------------------
# Hausses, baisses et volatilité sur un large univers
# ---------------------------------------------------------------------------
def univers() -> list:
    a = json.loads(LISTE.read_text(encoding="utf-8"))
    sp = [x["ticker"] for x in a if x["place"] == "S&P 500"]
    eu = sorted([x for x in a if x["place"] != "S&P 500" and "Growth" not in x["place"]],
                key=lambda x: -x.get("liquidite", 0))[:100]
    return sp + [x["ticker"] for x in eu]


def palmares() -> dict:
    with _verrou:
        deja = _cache.get("palmares")
    if not deja and analyse_en_cours.is_set():
        raise RuntimeError("Palmarès en préparation : une analyse est en cours.")

    def calcul():
        tickers = univers()
        p = _telecharger(tickers, "3mo")
        noms = _noms()
        lignes = []
        for t in p.columns:
            s = p[t].dropna()
            if len(s) < 40:
                continue
            r = s.pct_change().dropna()
            # Variation de plus de 60 % en un jour : très probablement une erreur de données
            # (division d'action mal ajustée…) ; on écarte la série plutôt que d'afficher un faux chiffre
            if r.abs().max() > 0.6:
                continue
            info = noms.get(t, {})
            lignes.append({"ticker": t, "nom": info.get("nom", t), "place": info.get("place", ""),
                           "dernier": float(s.iloc[-1]), "var_jour": _variation(s, 1),
                           "var_mois": _variation(s, 21), "vol": float(r.std() * np.sqrt(252)),
                           "date": s.index[-1]})
        df = pd.DataFrame(lignes)
        with _verrou:
            _cache["variations"] = (time.time(), {l["ticker"]: l for l in lignes})
        # Variation du jour : seulement les actions qui ont coté à la dernière séance de leur place
        dernier_jour = df["date"].max()
        recents = df[df["date"] >= dernier_jour - pd.Timedelta(days=3)]

        def top(d, col, n, croissant=False):
            d = d.dropna(subset=[col]).sort_values(col, ascending=croissant).head(n)
            return d.drop(columns=["date"]).to_dict("records")
        return {
            "nb": len(df),
            "hausses": top(recents, "var_jour", 6),
            "baisses": top(recents, "var_jour", 6, croissant=True),
            "volatiles": top(df, "vol", 8),
            "calmes": top(df, "vol", 5, croissant=True),
            "hausses_mois": top(df, "var_mois", 5),
        }
    return _en_cache("palmares", 1800, calcul)


# ---------------------------------------------------------------------------
# Carte du marché (heatmap) : taille = capitalisation, couleur = variation du jour
# ---------------------------------------------------------------------------
def carte(univers: str = "cac") -> list:
    import base_fondamentale
    base = base_fondamentale.charger(reconstruire_si_perimee=False)
    if not base:
        raise RuntimeError("La base des capitalisations est en préparation (une à quelques minutes, une fois par jour).")
    if univers == "sp":
        choix = [a for a in base if a["place"] == "S&P 500"]
    elif univers == "cac":
        choix = sorted([a for a in base if a["place"] == "Paris"], key=lambda a: -(a.get("capi_eur") or 0))[:40]
    else:
        choix = sorted([a for a in base if a["place"] != "S&P 500"], key=lambda a: -(a.get("capi_eur") or 0))[:100]
    choix = [a for a in choix if a.get("capi_eur")]

    def calcul():
        with _verrou:
            v = _cache.get("variations")
        connues = v[1] if v and time.time() - v[0] < 1800 else {}
        manquants = [a["ticker"] for a in choix if a["ticker"] not in connues]
        if manquants:
            d = _telecharger(manquants, "5d")
            for t in manquants:
                if t in d and d[t].dropna().shape[0] >= 2:
                    s_ = d[t].dropna()
                    connues[t] = {"var_jour": float(s_.iloc[-1] / s_.iloc[-2] - 1), "dernier": float(s_.iloc[-1])}
        return [{"ticker": a["ticker"], "nom": a["nom"], "secteur": a.get("secteur") or "Autre",
                 "capi": a["capi_eur"], "var_jour": connues.get(a["ticker"], {}).get("var_jour"),
                 "dernier": connues.get(a["ticker"], {}).get("dernier")} for a in choix]
    return _en_cache(f"carte_{univers}", 600, calcul)


# ---------------------------------------------------------------------------
# Cours détaillés pour les graphiques interactifs (bougies)
# ---------------------------------------------------------------------------
def ohlc(ticker: str, periode: str = "1y") -> dict:
    def calcul():
        d = yf.download(ticker, period=periode, auto_adjust=True, progress=False)
        if d.empty:
            raise ValueError(f"Pas de cours pour {ticker}.")
        d.columns = d.columns.get_level_values(0)
        d = d.dropna(subset=["Close"])
        if len(d) > 1600:              # historiques très longs : une bougie par semaine
            d = d.resample("W-FRI").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
        if len(d) > 3000:              # près d'un siècle : une bougie par mois
            d = d.resample("ME").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
        noms = _noms()
        return {"ticker": ticker, "nom": noms.get(ticker, {}).get("nom", ticker),
                "devise": noms.get(ticker, {}).get("devise", ""),
                "bougies": [[i.strftime("%Y-%m-%d"), round(float(r.Open), 4), round(float(r.High), 4), round(float(r.Low), 4),
                             round(float(r.Close), 4), float(r.Volume or 0)] for i, r in d.iterrows()]}
    return _en_cache(f"ohlc_{ticker}_{periode}", 600, calcul)


# ---------------------------------------------------------------------------
# Devises, matières premières, cryptomonnaies
# ---------------------------------------------------------------------------
ACTIFS = {
    "Devises": [
        ("EURUSD=X", "Euro / dollar", "$ pour 1 €", "Le taux de change le plus échangé au monde."),
        ("EURGBP=X", "Euro / livre", "£ pour 1 €", "Livre sterling britannique."),
        ("EURJPY=X", "Euro / yen", "¥ pour 1 €", "Le yen sert souvent de valeur refuge en période de crise."),
        ("EURCHF=X", "Euro / franc suisse", "CHF pour 1 €", "Le franc suisse, autre valeur refuge."),
        ("EURCNY=X", "Euro / yuan", "CNY pour 1 €", "Monnaie chinoise, encore encadrée par l'État."),
        ("USDJPY=X", "Dollar / yen", "¥ pour 1 $", "Suivi de près : il reflète l'écart de taux entre les États-Unis et le Japon."),
    ],
    "Matières premières": [
        ("BZ=F", "Pétrole Brent", "$ / baril", "Référence mondiale du pétrole (mer du Nord)."),
        ("CL=F", "Pétrole WTI", "$ / baril", "Référence américaine du pétrole."),
        ("TTF=F", "Gaz naturel européen (TTF)", "€ / MWh", "Prix du gaz en Europe, crucial pour l'électricité et l'industrie."),
        ("NG=F", "Gaz naturel américain", "$ / MMBtu", "Prix du gaz aux États-Unis (Henry Hub)."),
        ("GC=F", "Or", "$ / once", "Valeur refuge par excellence."),
        ("SI=F", "Argent", "$ / once", "Métal précieux et industriel (panneaux solaires, électronique)."),
        ("HG=F", "Cuivre", "$ / livre", "Surnommé « docteur cuivre » : sa demande reflète la santé de l'économie mondiale."),
        ("ZW=F", "Blé", "cents / boisseau", "Céréale clé de l'alimentation mondiale."),
        ("ZC=F", "Maïs", "cents / boisseau", "Alimentation animale et biocarburants."),
        ("KC=F", "Café", "cents / livre", "Très sensible à la météo au Brésil et au Vietnam."),
    ],
    "Cryptomonnaies": [
        ("BTC-USD", "Bitcoin", "$", "La première cryptomonnaie. Extrêmement volatile, sans revenu ni valeur intrinsèque."),
        ("ETH-USD", "Ether", "$", "Cryptomonnaie de la plateforme Ethereum."),
        ("SOL-USD", "Solana", "$", "Autre plateforme de chaîne de blocs, encore plus volatile."),
    ],
}


def actifs() -> list:
    def calcul():
        codes = [c for g in ACTIFS.values() for c, *_ in g]
        h = _telecharger(codes, "1y")
        debut_annee = pd.Timestamp(pd.Timestamp.today().year, 1, 1)
        res = []
        for groupe, liste in ACTIFS.items():
            lignes = []
            for code, nom, unite, aide in liste:
                if code not in h or h[code].dropna().empty:
                    continue
                s_ = h[code].dropna()
                r = s_.pct_change().dropna()
                lignes.append({"code": code, "nom": nom, "unite": unite, "aide": aide, "dernier": float(s_.iloc[-1]),
                               "var_jour": _variation(s_, 1), "var_annee": _variation(s_, depuis=debut_annee),
                               "var_1an": float(s_.iloc[-1] / s_.iloc[0] - 1), "vol": float(r.std() * np.sqrt(252)),
                               "mini": _points(s_, 60)})
            res.append({"groupe": groupe, "actifs": lignes})
        return res
    return _en_cache("actifs", 600, calcul)


def precharger():
    """À lancer au démarrage de l'application, en arrière-plan."""
    for f in (indices, phares, palmares):
        while analyse_en_cours.is_set():       # laisse passer l'analyse de l'utilisateur
            time.sleep(1)
        try:
            f()
        except Exception:
            pass
