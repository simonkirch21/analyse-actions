"""
BASE FONDAMENTALE — Les principaux ratios de ~1 500 entreprises
==============================================================

Télécharge, pour le S&P 500 et toutes les actions des marchés réglementés d'Euronext,
les ratios de valorisation, de rentabilité et d'endettement publiés par Yahoo Finance.
Sert à deux choses :
  - le FILTRE d'actions (screener) de l'application ;
  - la recherche automatique de CONCURRENTS (même industrie, taille comparable).

La base est enregistrée sur le disque et reconstruite au plus une fois par jour
(environ une minute, en arrière-plan).
"""

import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import yfinance as yf

import chemins
from portefeuille import SECTEURS_FR

FICHIER = chemins.UTILISATEUR / "base_fondamentale.json"
DUREE_VALIDITE = 24 * 3600

etat = {"en_cours": False, "faits": 0, "total": 0}
_verrou = threading.Lock()


def _f(x):
    """Nombre propre (None si absent, infini ou aberrant)."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) or math.isinf(x) else x


def univers() -> list:
    liste = json.loads(chemins.liste_actions().read_text(encoding="utf-8"))
    return [a for a in liste if "Growth" not in a["place"]]


def _fiche(action: dict, taux: dict) -> dict:
    i = {}
    for essai in range(4):           # Yahoo limite le nombre de requêtes : on réessaie en attendant
        try:
            i = yf.Ticker(action["ticker"]).info or {}
            if i.get("marketCap") or i.get("quoteType"):
                break
        except Exception:
            pass
        time.sleep(1.5 * 2 ** essai)
    if not i.get("marketCap"):
        return None
    devise = i.get("financialCurrency") or i.get("currency") or action.get("devise") or "EUR"
    vers_eur = taux.get(i.get("currency") or devise, 1.0)
    dette, cash, ebitda = _f(i.get("totalDebt")), _f(i.get("totalCash")), _f(i.get("ebitda"))
    levier = (dette - cash) / ebitda if None not in (dette, cash, ebitda) and ebitda > 0 else None
    rdt = _f(i.get("dividendYield"))
    rdt = rdt / 100 if rdt is not None else None                 # Yahoo donne 3,2 pour 3,2 %
    cours, objectif = _f(i.get("currentPrice")), _f(i.get("targetMeanPrice"))
    return {
        "ticker": action["ticker"], "nom": action["nom"], "place": action["place"],
        "secteur": SECTEURS_FR.get(i.get("sector"), i.get("sector") or "Non renseigné"),
        "industrie": i.get("industry") or "", "cle_industrie": i.get("industryKey") or "",
        "cle_secteur": i.get("sectorKey") or "",
        "capi_eur": _f(i.get("marketCap")) * vers_eur if vers_eur else None,
        "per": _f(i.get("trailingPE")), "per_prev": _f(i.get("forwardPE")),
        "pb": _f(i.get("priceToBook")), "ve_ebe": _f(i.get("enterpriseToEbitda")),
        "rdt_div": rdt, "roe": _f(i.get("returnOnEquity")), "marge_nette": _f(i.get("profitMargins")),
        "marge_op": _f(i.get("operatingMargins")), "croissance_ca": _f(i.get("revenueGrowth")),
        "levier": _f(levier), "beta": _f(i.get("beta")), "var_1an": _f(i.get("52WeekChange")),
        "potentiel_analystes": (objectif / cours - 1) if cours and objectif else None,
        "recommandation": i.get("recommendationKey"),
    }


def construire() -> list:
    with _verrou:
        if etat["en_cours"]:
            return None
        etat.update(en_cours=True, faits=0)
    try:
        actions = univers()
        etat["total"] = len(actions)
        taux = {"EUR": 1.0}
        for dev in ("USD", "NOK", "GBP", "CHF", "SEK", "DKK"):
            try:
                taux[dev] = float(yf.Ticker(f"{dev}EUR=X").fast_info["last_price"])
            except Exception:
                pass

        def tache(a):
            r = _fiche(a, taux)
            etat["faits"] += 1
            return r

        with ThreadPoolExecutor(6) as ex:
            fiches = [f for f in ex.map(tache, actions) if f]
        # Les entreprises que Yahoo n'a pas renvoyées cette fois (limite de requêtes) gardent
        # leurs données de la veille
        try:
            anciennes = json.loads(FICHIER.read_text(encoding="utf-8"))["actions"]
            presents = {f["ticker"] for f in fiches}
            fiches += [a for a in anciennes if a["ticker"] not in presents]
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass
        chemins.UTILISATEUR.mkdir(parents=True, exist_ok=True)
        FICHIER.write_text(json.dumps({"date": time.time(), "actions": fiches}, ensure_ascii=False),
                           encoding="utf-8")
        return fiches
    finally:
        etat["en_cours"] = False


def charger(reconstruire_si_perimee: bool = True):
    """La base si elle existe (et la relance en arrière-plan si elle a plus d'un jour)."""
    try:
        d = json.loads(FICHIER.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        d = None
    if d:
        # Secteur manquant chez Yahoo : on reprend celui de la liste du S&P 500 (Wikipédia)
        secteurs_liste = {a["ticker"]: a.get("secteur") for a in univers()}
        for a in d["actions"]:
            if a.get("secteur") in (None, "", "Non renseigné") and secteurs_liste.get(a["ticker"]):
                a["secteur"] = SECTEURS_FR.get(secteurs_liste[a["ticker"]], secteurs_liste[a["ticker"]])
    perimee = d is None or time.time() - d["date"] > DUREE_VALIDITE
    if perimee and reconstruire_si_perimee and not etat["en_cours"]:
        threading.Thread(target=construire, daemon=True).start()
    return d["actions"] if d else None


def concurrents(ticker: str, n: int = 4) -> list:
    """Entreprises de la même industrie (sinon du même secteur), de taille la plus proche."""
    base = charger()
    if not base:
        return []
    cible = next((a for a in base if a["ticker"] == ticker), None)
    if not cible:                       # absente de la base : on la consulte directement
        action = next((a for a in univers() if a["ticker"] == ticker), {"ticker": ticker, "nom": ticker, "place": ""})
        cible = _fiche(action, {"EUR": 1.0, "USD": 0.92})
    if not cible or not cible.get("capi_eur"):
        return []
    def distance(a):
        return abs(math.log(a["capi_eur"] / cible["capi_eur"]))
    # Concurrents de taille comparable (entre 1/20 et 20 fois la capitalisation de l'entreprise) :
    # d'abord dans la même industrie, sinon dans le même secteur
    for cle in ("cle_industrie", "cle_secteur", "secteur"):
        if not cible.get(cle):
            continue
        candidats = [a for a in base if a["ticker"] != ticker and a.get(cle) == cible[cle]
                     and a.get("capi_eur") and distance(a) < math.log(20)]
        if len(candidats) >= 2:
            return sorted(candidats, key=distance)[:n]
    return []


if __name__ == "__main__":
    t = time.time()
    b = construire()
    print(f"{len(b)} entreprises en {time.time() - t:.0f} s")
    for t_ in ("MC.PA", "AIR.PA", "BNP.PA", "AAPL"):
        print(t_, "->", [(c["ticker"], c["nom"]) for c in concurrents(t_)])
