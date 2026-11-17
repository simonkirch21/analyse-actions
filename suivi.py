"""
SUIVI — Liste de suivi, agenda (résultats, dividendes) et alertes
=================================================================

  - Liste de suivi : les actions que tu surveilles sans forcément les détenir, avec pour chacune
    des seuils d'alerte (baisse du jour en %, cours plancher, cours plafond).
  - Agenda : prochaines publications de résultats et dates de dividendes des actions suivies
    et de celles du portefeuille.
  - Alertes : vérifiées toutes les 15 minutes tant que l'application est ouverte ; une
    notification macOS est envoyée (une seule fois par jour et par alerte).
"""

import json
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

import pandas as pd
import yfinance as yf

import chemins

FICHIER = chemins.UTILISATEUR / "suivi.json"
FICHIER_PF = chemins.UTILISATEUR / "portefeuille.json"
FICHIER_ALERTES = chemins.UTILISATEUR / "alertes.json"
BAISSE_DEFAUT = 5.0     # alerte si l'action perd plus de 5 % dans la journée

_cache = {}


def lire(fichier=FICHIER) -> list:
    try:
        return json.loads(fichier.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def enregistrer(lignes: list) -> list:
    propres, vus = [], set()
    for l in lignes or []:
        t = str(l.get("ticker", "")).strip().upper()
        if not t or t in vus or t == "SANS_RISQUE":
            continue
        vus.add(t)

        def nombre(x):
            try:
                return float(x) if x not in (None, "") else None
            except (TypeError, ValueError):
                return None
        propres.append({"ticker": t, "nom": str(l.get("nom") or t)[:120], "place": str(l.get("place") or "")[:40],
                        "baisse": nombre(l.get("baisse")) if "baisse" in l else BAISSE_DEFAUT,
                        "haut": nombre(l.get("haut")), "bas": nombre(l.get("bas"))})
    chemins.UTILISATEUR.mkdir(parents=True, exist_ok=True)
    FICHIER.write_text(json.dumps(propres, ensure_ascii=False, indent=1), encoding="utf-8")
    _cache.pop("etat", None)
    return propres


def _cours(tickers: list) -> dict:
    if not tickers:
        return {}
    d = yf.download(tickers, period="10d", auto_adjust=True, progress=False)["Close"]
    if isinstance(d, pd.Series):
        d = d.to_frame(tickers[0])
    res = {}
    for t in tickers:
        if t in d and d[t].dropna().shape[0] >= 2:
            s = d[t].dropna()
            res[t] = {"dernier": float(s.iloc[-1]), "var_jour": float(s.iloc[-1] / s.iloc[-2] - 1),
                      "date": s.index[-1].strftime("%d/%m")}
    return res


def _agenda_action(t: str) -> list:
    evts = []
    try:
        c = yf.Ticker(t).calendar or {}
    except Exception:
        return evts
    aujourd_hui = date.today()
    for d in c.get("Earnings Date") or []:
        if isinstance(d, date) and d >= aujourd_hui:
            detail = ""
            if c.get("Earnings Average"):
                detail = f"bénéfice par action attendu : {fr(c['Earnings Average'])}"
            evts.append({"date": d.isoformat(), "type": "Résultats", "ticker": t, "detail": detail})
    for cle, lib in (("Ex-Dividend Date", "Détachement du dividende"), ("Dividend Date", "Paiement du dividende")):
        d = c.get(cle)
        if isinstance(d, date) and d >= aujourd_hui:
            evts.append({"date": d.isoformat(), "type": lib, "ticker": t, "detail": ""})
    return evts


def etat() -> dict:
    """Cours des actions suivies + agenda des actions suivies et du portefeuille (cache 10 min)."""
    suivies = lire()
    pf = [l for l in lire(FICHIER_PF) if l.get("ticker") != "SANS_RISQUE"]
    # Cache valable 10 minutes et seulement pour la même liste d'actions (et les mêmes seuils)
    cle = json.dumps([suivies, [l["ticker"] for l in pf]], sort_keys=True)
    v = _cache.get("etat")
    if v and v[2] == cle and time.time() - v[0] < 600:
        return v[1]
    noms = {l["ticker"]: l.get("nom", l["ticker"]) for l in pf + suivies}
    tous = list(dict.fromkeys([l["ticker"] for l in suivies] + [l["ticker"] for l in pf]))
    cours = _cours(tous)
    with ThreadPoolExecutor(6) as ex:
        agenda = [e for evts in ex.map(_agenda_action, tous) for e in evts]
    for e in agenda:
        e["nom"] = noms.get(e["ticker"], e["ticker"])
        e["source"] = "portefeuille" if any(l["ticker"] == e["ticker"] for l in pf) else "suivi"
    agenda.sort(key=lambda e: e["date"])
    lignes = [{**l, **cours.get(l["ticker"], {})} for l in suivies]
    res = {"lignes": lignes, "agenda": agenda, "alertes": alertes_recentes()}
    _cache["etat"] = (time.time(), res, cle)
    return res


# ---------------------------------------------------------------------------
# Alertes
# ---------------------------------------------------------------------------
def alertes_recentes(n: int = 15) -> list:
    return lire(FICHIER_ALERTES)[-n:][::-1]


def notifier(titre: str, texte: str) -> None:
    """Notification macOS (centre de notifications)."""
    t = texte.replace('"', "'")
    subprocess.run(["osascript", "-e", f'display notification "{t}" with title "{titre}" sound name "Glass"'],
                   capture_output=True)


def fr(x: float, d: int = 2) -> str:
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def verifier_alertes() -> list:
    suivies = lire()
    if not suivies:
        return []
    cours = _cours([l["ticker"] for l in suivies])
    historique = lire(FICHIER_ALERTES)
    deja = {(a["ticker"], a["regle"], a["jour"]) for a in historique}
    jour = date.today().isoformat()
    nouvelles = []
    for l in suivies:
        c = cours.get(l["ticker"])
        if not c:
            continue
        regles = []
        if l.get("baisse") and c["var_jour"] <= -abs(l["baisse"]) / 100:
            regles.append(("baisse", f"{l['nom']} recule de {fr(abs(c['var_jour']) * 100, 1)} % aujourd'hui"))
        if l.get("haut") and c["dernier"] >= l["haut"]:
            regles.append(("haut", f"{l['nom']} dépasse {fr(l['haut'])} (cours : {fr(c['dernier'])})"))
        if l.get("bas") and c["dernier"] <= l["bas"]:
            regles.append(("bas", f"{l['nom']} passe sous {fr(l['bas'])} (cours : {fr(c['dernier'])})"))
        for regle, texte in regles:
            if (l["ticker"], regle, jour) in deja:
                continue
            a = {"ticker": l["ticker"], "regle": regle, "jour": jour, "texte": texte,
                 "heure": datetime.now().strftime("%d/%m %H:%M")}
            nouvelles.append(a)
            notifier("Analyse Actions : alerte", texte)
    if nouvelles:
        FICHIER_ALERTES.write_text(json.dumps((historique + nouvelles)[-200:], ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        _cache.pop("etat", None)
    return nouvelles


def surveiller(intervalle: int = 900) -> None:
    """Boucle d'arrière-plan : vérifie les alertes toutes les 15 minutes."""
    time.sleep(60)
    while True:
        try:
            verifier_alertes()
        except Exception:
            pass
        time.sleep(intervalle)


def demarrer_surveillance() -> None:
    threading.Thread(target=surveiller, daemon=True).start()
