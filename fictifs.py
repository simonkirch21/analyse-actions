"""
PORTEFEUILLES FICTIFS — S'entraîner à investir sans risquer d'argent
====================================================================

Tu crées un ou plusieurs portefeuilles avec un capital virtuel (par exemple 10 000 €), puis tu passes
des ordres d'achat et de vente au cours réel de la Bourse. Le portefeuille évolue ensuite avec les
marchés, comme un vrai compte-titres :
  - frais de courtage à chaque ordre (0,1 % par défaut, minimum 1 €) ;
  - dividendes versés automatiquement sur le compte les jours de détachement ;
  - conversion en euros des actions cotées en dollars ou en couronnes ;
  - comparaison avec le CAC 40 et le marché mondial depuis la création.

Pour « tester », un portefeuille peut démarrer dans le passé : les ordres sont alors exécutés au cours
de clôture de la date choisie (toujours dans l'ordre chronologique, pour ne pas tricher).

Données : utilisateur/portefeuilles_fictifs.json
"""

import json
import math
import threading
import time
import uuid
from datetime import date, datetime

import numpy as np
import pandas as pd
import yfinance as yf

import chemins

FICHIER = chemins.UTILISATEUR / "portefeuilles_fictifs.json"
REFERENCES = {"^FCHI": "CAC 40", "URTH": "Marché mondial (MSCI World)"}
_verrou = threading.Lock()
_cache = {}


# ---------------------------------------------------------------------------
# Stockage
# ---------------------------------------------------------------------------
def _lire() -> list:
    try:
        return json.loads(FICHIER.read_text(encoding="utf-8"))["portefeuilles"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return []


def _ecrire(pfs: list) -> None:
    chemins.UTILISATEUR.mkdir(parents=True, exist_ok=True)
    FICHIER.write_text(json.dumps({"portefeuilles": pfs}, ensure_ascii=False, indent=1), encoding="utf-8")
    _cache.clear()


def _trouver(pfs: list, id_: str) -> dict:
    p = next((x for x in pfs if x["id"] == id_), None)
    if not p:
        raise ValueError("Portefeuille introuvable.")
    return p


def creer(nom: str, capital: float, date_creation: str = None, frais_pct: float = 0.1, frais_min: float = 1.0) -> dict:
    capital = float(capital)
    if not 100 <= capital <= 10_000_000:
        raise ValueError("Le capital doit être compris entre 100 € et 10 millions d'euros.")
    d = pd.Timestamp(date_creation or date.today()).normalize()
    if d > pd.Timestamp.today().normalize():
        raise ValueError("La date de création ne peut pas être dans le futur.")
    if d < pd.Timestamp("2000-01-01"):
        raise ValueError("Date de création trop ancienne (2000 au plus tôt).")
    p = {"id": uuid.uuid4().hex[:10], "nom": (nom or "Mon portefeuille").strip()[:60], "capital": capital,
         "date_creation": d.strftime("%Y-%m-%d"), "frais_pct": max(0.0, float(frais_pct)),
         "frais_min": max(0.0, float(frais_min)), "transactions": []}
    with _verrou:
        pfs = _lire()
        pfs.append(p)
        _ecrire(pfs)
    return p


def supprimer(id_: str) -> None:
    with _verrou:
        _ecrire([p for p in _lire() if p["id"] != id_])


def annuler_dernier(id_: str) -> None:
    with _verrou:
        pfs = _lire()
        p = _trouver(pfs, id_)
        if p["transactions"]:
            p["transactions"].pop()
            _ecrire(pfs)


# ---------------------------------------------------------------------------
# Cours
# ---------------------------------------------------------------------------
def _devise(ticker: str) -> str:
    try:
        liste = json.loads(chemins.liste_actions().read_text(encoding="utf-8"))
        dev = next((a.get("devise") for a in liste if a["ticker"] == ticker), None)
        if dev:
            return dev
    except Exception:
        pass
    try:
        return yf.Ticker(ticker).fast_info.get("currency") or "EUR"
    except Exception:
        return "EUR"


def cotation(ticker: str, jour: str = None) -> dict:
    """Prix d'exécution : dernier cours connu (aujourd'hui) ou cours de clôture d'une date passée."""
    ticker = ticker.upper()
    dev = _devise(ticker)
    aujourd_hui = pd.Timestamp.today().normalize()
    d = pd.Timestamp(jour).normalize() if jour else aujourd_hui
    if d > aujourd_hui:
        raise ValueError("Impossible de passer un ordre dans le futur.")
    if d >= aujourd_hui:
        fi = yf.Ticker(ticker).fast_info
        prix = float(fi["last_price"])
        quand = datetime.now().strftime("%d/%m/%Y %H:%M")
        fx = 1.0 if dev == "EUR" else float(yf.Ticker(f"{dev}EUR=X").fast_info["last_price"])
    else:
        h = yf.download(ticker, start=d - pd.Timedelta(days=10), end=d + pd.Timedelta(days=1),
                        auto_adjust=False, progress=False)["Close"].squeeze().dropna()
        if h.empty:
            raise ValueError(f"Pas de cours pour {ticker} à cette date.")
        prix, quand = float(h.iloc[-1]), h.index[-1].strftime("%d/%m/%Y") + " (clôture)"
        fx = 1.0
        if dev != "EUR":
            f = yf.download(f"{dev}EUR=X", start=d - pd.Timedelta(days=10), end=d + pd.Timedelta(days=1),
                            progress=False)["Close"].squeeze().dropna()
            fx = float(f.iloc[-1]) if len(f) else np.nan
    if not prix or math.isnan(prix) or math.isnan(fx):
        raise ValueError(f"Cours indisponible pour {ticker}.")
    return {"ticker": ticker, "prix": prix, "devise": dev, "fx": fx, "prix_eur": prix * fx, "quand": quand,
            "date": d.strftime("%Y-%m-%d")}


# ---------------------------------------------------------------------------
# Ordres
# ---------------------------------------------------------------------------
def _positions(transactions: list) -> dict:
    """Quantité détenue par action d'après l'historique des ordres."""
    q = {}
    for t in transactions:
        q[t["ticker"]] = q.get(t["ticker"], 0) + (t["quantite"] if t["sens"] == "achat" else -t["quantite"])
    return {k: v for k, v in q.items() if v > 1e-9}


def ordre(id_: str, sens: str, ticker: str, nom: str = "", quantite: float = None, montant: float = None,
          jour: str = None) -> dict:
    if sens not in ("achat", "vente"):
        raise ValueError("Sens d'ordre invalide.")
    with _verrou:
        pfs = _lire()
        p = _trouver(pfs, id_)
    jour = jour or date.today().isoformat()
    dernier_jour = max([p["date_creation"]] + [t["date"] for t in p["transactions"]])
    if jour < dernier_jour:
        raise ValueError(f"Les ordres doivent suivre l'ordre chronologique : choisis une date à partir du "
                         f"{pd.Timestamp(dernier_jour):%d/%m/%Y}.")
    c = cotation(ticker, jour)
    if quantite is None:
        if not montant or montant <= 0:
            raise ValueError("Indique une quantité ou un montant.")
        quantite = math.floor(float(montant) / c["prix_eur"])        # actions entières
    quantite = float(quantite)
    if quantite <= 0 or quantite != int(quantite):
        raise ValueError("La quantité doit être un nombre entier d'actions (au moins 1)."
                         + (f" Avec ce montant, une action coûte {c['prix_eur']:.2f} €." if montant else ""))
    brut = quantite * c["prix_eur"]
    frais = max(brut * p["frais_pct"] / 100, p["frais_min"]) if brut else 0.0
    etat = evaluer(p, jusqua=jour, leger=True)
    if sens == "achat" and brut + frais > etat["cash"] + 1e-6:
        raise ValueError(f"Liquidités insuffisantes : il faut {brut + frais:,.2f} €, tu disposes de "
                         f"{etat['cash']:,.2f} €.".replace(",", " ").replace(".", ","))
    if sens == "vente" and quantite > _positions(p["transactions"]).get(c["ticker"], 0) + 1e-9:
        raise ValueError("Tu ne peux pas vendre plus d'actions que tu n'en détiens (pas de vente à découvert).")
    t = {"id": uuid.uuid4().hex[:8], "date": c["date"], "quand": c["quand"], "sens": sens, "ticker": c["ticker"],
         "nom": nom or c["ticker"], "quantite": quantite, "prix": c["prix"], "devise": c["devise"], "fx": c["fx"],
         "montant_eur": brut, "frais_eur": frais}
    with _verrou:
        pfs = _lire()
        _trouver(pfs, id_)["transactions"].append(t)
        _ecrire(pfs)
    return t


# ---------------------------------------------------------------------------
# Valorisation et historique
# ---------------------------------------------------------------------------
def _historiques(tickers: list, debut: pd.Timestamp) -> tuple:
    """Cours de clôture réels (non ajustés) et taux de change vers l'euro, depuis `debut`."""
    if not tickers:
        return pd.DataFrame(), {}
    h = yf.download(tickers, start=debut - pd.Timedelta(days=10), auto_adjust=False, progress=False)["Close"]
    if isinstance(h, pd.Series):
        h = h.to_frame(tickers[0])
    devises = {t: _devise(t) for t in tickers}
    fx = {}
    for dev in {d for d in devises.values() if d != "EUR"}:
        f = yf.download(f"{dev}EUR=X", start=debut - pd.Timedelta(days=10), progress=False)["Close"].squeeze()
        fx[dev] = f
    eur = pd.DataFrame(index=h.index)
    for t in tickers:
        s = h[t] if t in h else pd.Series(np.nan, index=h.index)
        if devises[t] != "EUR":
            s = s * fx[devises[t]].reindex(h.index).ffill().bfill()
        eur[t] = s
    return eur.ffill(), devises


def evaluer(p: dict, jusqua: str = None, leger: bool = False) -> dict:
    """Valeur du portefeuille jour par jour depuis sa création.
    leger=True : seulement les liquidités disponibles à une date (pour valider un ordre)."""
    tx = sorted(p["transactions"], key=lambda t: t["date"])
    debut = pd.Timestamp(p["date_creation"])
    fin = pd.Timestamp(jusqua) if jusqua else pd.Timestamp.today().normalize()
    tickers = sorted({t["ticker"] for t in tx})

    # Dividendes : versés pour chaque action détenue la veille de la date de détachement
    dividendes = []
    for tk in tickers:
        try:
            dv = yf.Ticker(tk).dividends
        except Exception:
            continue
        if dv is None or dv.empty:
            continue
        dv.index = dv.index.tz_localize(None).normalize()
        for d_ex, montant in dv[(dv.index > debut) & (dv.index <= fin)].items():
            qte = sum(t["quantite"] * (1 if t["sens"] == "achat" else -1)
                      for t in tx if t["ticker"] == tk and pd.Timestamp(t["date"]) < d_ex)
            if qte > 1e-9:
                dividendes.append({"date": d_ex, "ticker": tk, "par_action": float(montant), "quantite": qte})

    if leger:
        cash = p["capital"]
        for t in tx:
            if t["date"] <= fin.strftime("%Y-%m-%d"):
                cash += (-1 if t["sens"] == "achat" else 1) * t["montant_eur"] - t["frais_eur"]
        for dvd in dividendes:   # conversion approximative au taux de la transaction d'achat
            tr = next(t for t in tx if t["ticker"] == dvd["ticker"])
            cash += dvd["par_action"] * dvd["quantite"] * tr["fx"]
        return {"cash": cash}

    cle = json.dumps([p, fin.strftime("%Y-%m-%d")], sort_keys=True)
    if cle in _cache and time.time() - _cache[cle][0] < 300:
        return _cache[cle][1]

    cours, devises = _historiques(tickers + list(REFERENCES), debut)
    if cours.empty:
        jours = pd.bdate_range(debut, fin)
        cours = pd.DataFrame(index=jours)
    cours = cours[(cours.index >= debut) & (cours.index <= fin)]
    if cours.empty:
        cours = pd.DataFrame(index=pd.bdate_range(debut, fin))

    # Rejoue l'historique jour par jour : liquidités et quantités détenues
    qte = {t: 0.0 for t in tickers}
    cash, i_tx, i_dv = p["capital"], 0, 0
    dividendes.sort(key=lambda d: d["date"])
    for d in dividendes:     # montant en euros au cours de change du jour
        dev = devises.get(d["ticker"], "EUR")
        taux = 1.0
        if dev != "EUR":
            tr = next(t for t in tx if t["ticker"] == d["ticker"])
            taux = tr["fx"]
        d["montant_eur"] = d["par_action"] * d["quantite"] * taux
    valeurs, liquidites = [], []
    frais_total = sum(t["frais_eur"] for t in tx)
    for jour in cours.index:
        while i_tx < len(tx) and pd.Timestamp(tx[i_tx]["date"]) <= jour:
            t = tx[i_tx]
            signe = 1 if t["sens"] == "achat" else -1
            qte[t["ticker"]] += signe * t["quantite"]
            cash += -signe * t["montant_eur"] - t["frais_eur"]
            i_tx += 1
        while i_dv < len(dividendes) and dividendes[i_dv]["date"] <= jour:
            cash += dividendes[i_dv]["montant_eur"]
            i_dv += 1
        titres = sum(q * cours.at[jour, t] for t, q in qte.items() if q and t in cours and not pd.isna(cours.at[jour, t]))
        valeurs.append(cash + titres)
        liquidites.append(cash)
    # Transactions passées aujourd'hui après la dernière clôture
    while i_tx < len(tx):
        t = tx[i_tx]
        signe = 1 if t["sens"] == "achat" else -1
        qte[t["ticker"]] += signe * t["quantite"]
        cash += -signe * t["montant_eur"] - t["frais_eur"]
        i_tx += 1

    valeur = pd.Series(valeurs, index=cours.index) if valeurs else pd.Series([p["capital"]], index=[debut])

    # Positions actuelles : prix de revient moyen (PRU) et plus-values
    positions, realise = [], 0.0
    for tk in tickers:
        q_, cout = 0.0, 0.0
        for t in tx:
            if t["ticker"] != tk:
                continue
            if t["sens"] == "achat":
                q_ += t["quantite"]
                cout += t["montant_eur"] + t["frais_eur"]
            else:
                part = cout * t["quantite"] / q_ if q_ else 0
                realise += t["montant_eur"] - t["frais_eur"] - part
                cout -= part
                q_ -= t["quantite"]
        if q_ > 1e-9:
            dernier = float(cours[tk].dropna().iloc[-1]) if tk in cours and cours[tk].notna().any() else np.nan
            if fin >= pd.Timestamp.today().normalize():          # cours le plus récent possible
                try:
                    c = cotation(tk)
                    dernier = c["prix_eur"]
                except Exception:
                    pass
            val = q_ * dernier
            nom = next((t["nom"] for t in tx if t["ticker"] == tk), tk)
            positions.append({"ticker": tk, "nom": nom, "quantite": q_, "pru_eur": cout / q_, "cours_eur": dernier,
                              "valeur": val, "plus_value": val - cout, "performance": val / cout - 1 if cout else None,
                              "devise": devises.get(tk, "EUR")})
    total_titres = sum(x["valeur"] for x in positions if not pd.isna(x["valeur"]))
    valeur_totale = cash + total_titres
    if len(valeur):
        valeur.iloc[-1] = valeur_totale
    for x in positions:
        x["poids"] = x["valeur"] / valeur_totale if valeur_totale else 0

    # Comparaison avec les indices (même capital investi le jour de la création)
    refs = {}
    for code, nom in REFERENCES.items():
        if code in cours and cours[code].notna().any():
            s = cours[code].dropna()
            refs[nom] = s / s.iloc[0] * p["capital"]

    r = valeur.pct_change().dropna()
    duree = max((valeur.index[-1] - valeur.index[0]).days / 365.25, 0) if len(valeur) > 1 else 0
    perf = valeur_totale / p["capital"] - 1
    res = {
        "id": p["id"], "nom": p["nom"], "capital": p["capital"], "date_creation": p["date_creation"],
        "frais_pct": p["frais_pct"], "frais_min": p["frais_min"],
        "valeur": valeur_totale, "cash": cash, "titres": total_titres, "performance": perf,
        "performance_annualisee": (1 + perf) ** (1 / duree) - 1 if duree >= 1 else None,
        "plus_value_latente": sum(x["plus_value"] for x in positions if not pd.isna(x["plus_value"])),
        "plus_value_realisee": realise, "dividendes": sum(d["montant_eur"] for d in dividendes), "frais": frais_total,
        "volatilite": float(r.std() * np.sqrt(252)) if len(r) > 20 else None,
        "perte_max": float((valeur / valeur.cummax() - 1).min()) if len(valeur) > 1 else 0.0,
        "positions": sorted(positions, key=lambda x: -(x["valeur"] or 0)),
        "transactions": list(reversed(tx)),
        "dividendes_detail": [{"date": d["date"].strftime("%d/%m/%Y"), "ticker": d["ticker"], "montant_eur": d["montant_eur"]}
                              for d in reversed(dividendes)],
        "references": {n: {"performance": float(s.iloc[-1] / p["capital"] - 1)} for n, s in refs.items()},
        "series": _series_graphique(valeur, refs),
    }
    _cache[cle] = (time.time(), res)
    return res


def _series_graphique(valeur: pd.Series, refs: dict, n: int = 300) -> dict:
    def reduire(s):
        s = s.dropna()
        if len(s) > n:
            s = s.iloc[np.linspace(0, len(s) - 1, n).astype(int)]
        return [[d.strftime("%Y-%m-%d"), round(float(v), 2)] for d, v in s.items()]
    out = {"Ton portefeuille": reduire(valeur)}
    for nom, s in refs.items():
        out[nom] = reduire(s.reindex(valeur.index).ffill())
    return out


def liste() -> list:
    """Résumé de tous les portefeuilles (pour le classement)."""
    res = []
    for p in _lire():
        try:
            e = evaluer(p)
            res.append({k: e[k] for k in ("id", "nom", "capital", "date_creation", "valeur", "performance")}
                       | {"nb_positions": len(e["positions"]), "nb_ordres": len(p["transactions"]),
                          "vs_cac": e["performance"] - e["references"].get("CAC 40", {}).get("performance", 0)})
        except Exception as erreur:
            res.append({"id": p["id"], "nom": p["nom"], "capital": p["capital"], "date_creation": p["date_creation"],
                        "erreur": str(erreur)})
    return sorted(res, key=lambda x: -(x.get("performance") or -9))


def detail(id_: str) -> dict:
    return evaluer(_trouver(_lire(), id_))


if __name__ == "__main__":
    import sys
    p = creer("Test 2022", 10000, "2022-01-03")
    print(ordre(p["id"], "achat", "MC.PA", "LVMH", quantite=5, jour="2022-01-03"))
    print(ordre(p["id"], "achat", "AAPL", "Apple", montant=3000, jour="2022-01-03"))
    print(ordre(p["id"], "vente", "MC.PA", "LVMH", quantite=2, jour="2024-03-01"))
    e = detail(p["id"])
    print({k: e[k] for k in ("valeur", "cash", "performance", "plus_value_latente", "plus_value_realisee", "dividendes", "frais", "perte_max")})
    print([(x["ticker"], x["quantite"], round(x["pru_eur"], 2), round(x["valeur"])) for x in e["positions"]])
    print(e["references"])
    supprimer(p["id"])
