"""
Construit la liste des actions proposées dans l'application :
  - toutes les actions des marchés Euronext (Paris, Amsterdam, Bruxelles,
    Lisbonne, Dublin, Milan, Oslo), d'après le fichier officiel d'Euronext
  - les ~500 valeurs du S&P 500, d'après Wikipédia
  - toutes les actions cotées aux États-Unis (Nasdaq, NYSE, NYSE American), d'après les fichiers
    publics de Nasdaq Trader (hors ETF, warrants, droits, unités et actions de préférence)
  - les grands indices européens hors Euronext : DAX, FTSE 100 et 250, SMI, IBEX 35, OMX Stockholm 30
  (toute autre action connue de Yahoo Finance reste accessible par la recherche en direct de l'application)

Résultat : data/actions.json (à relancer de temps en temps pour mettre à jour).

Lancer :  .venv/bin/python construire_liste.py
"""

import io
import re
import json
from pathlib import Path

import pandas as pd
import requests

import chemins
DOSSIER = chemins.DONNEES / "data"
ENTETES = {"User-Agent": "Mozilla/5.0 (Macintosh) analyse-action"}

# Marché Euronext -> (suffixe Yahoo Finance, nom court de la place)
PLACES = {
    "Paris": (".PA", "Paris"),
    "Amsterdam": (".AS", "Amsterdam"),
    "Brussels": (".BR", "Bruxelles"),
    "Lisbon": (".LS", "Lisbonne"),
    "Dublin": (".IR", "Dublin"),
    "Milan": (".MI", "Milan"),
    "Oslo": (".OL", "Oslo"),
}
# On ignore les compartiments sans vraie cotation continue des actions locales
EXCLUS = ("Global Equity", "After Hours", "EuroTLX", "Access", "Expert")


def joli_nom(nom: str) -> str:
    """Euronext écrit tout en majuscules : "ASML HOLDING" -> "ASML Holding".
    Les mots de 4 lettres ou moins restent en majuscules (sigles : LVMH, BNP, EDP)."""
    return " ".join(m if len(m) <= 4 else m.capitalize() for m in nom.strip().split())


def liste_euronext() -> list:
    reponse = requests.post(
        "https://live.euronext.com/en/pd_es/data/stocks/download?mics=dm_all_stock",
        data={"args[fe_type]": "csv", "args[fe_decimal_separator]": ".",
              "args[fe_date_format]": "d/m/Y"},
        headers=ENTETES, timeout=60,
    )
    reponse.raise_for_status()
    # Les lignes 2 à 4 du fichier sont des commentaires : on les saute
    df = pd.read_csv(io.StringIO(reponse.content.decode("utf-8-sig")), sep=";",
                     skiprows=[1, 2, 3])
    actions = []
    for _, ligne in df.iterrows():
        marche = str(ligne["Market"])
        if any(x in marche for x in EXCLUS):
            continue
        premiere_place = marche.split(",")[0]          # "Euronext Paris, Brussels" -> Paris
        for cle, (suffixe, place) in PLACES.items():
            if cle in premiere_place:
                break
        else:                                          # aucune place reconnue
            continue
        symbole = str(ligne["Symbol"]).strip()
        if not symbole or symbole == "nan":
            continue
        if str(ligne["Name"]).startswith("W "):        # warrants (bons), pas des actions
            continue
        capitaux = pd.to_numeric(ligne["Turnover"], errors="coerce")
        actions.append({
            "ticker": symbole + suffixe,
            "nom": joli_nom(str(ligne["Name"])),
            "place": place + (" (Growth)" if "Growth" in marche else ""),
            "isin": ligne["ISIN"],
            "devise": ligne["Currency"],
            "liquidite": 0 if pd.isna(capitaux) else float(capitaux),
        })
    return actions


def liste_sp500() -> list:
    page = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                        headers=ENTETES, timeout=60)
    page.raise_for_status()
    df = pd.read_html(io.StringIO(page.text))[0]
    return [{
        "ticker": str(l["Symbol"]).replace(".", "-"),   # BRK.B -> BRK-B (format Yahoo)
        "nom": str(l["Security"]),
        "place": "S&P 500",
        "secteur": str(l["GICS Sector"]),
        "devise": "USD",
        "liquidite": 1e12,          # les grandes valeurs US remontent en tête
    } for _, l in df.iterrows()]


EXCLUS_US = ("warrant", "right", " unit", "units", "preferred", "depositary shares representing", " notes", "debenture",
             "%", "subordinated", "trust preferred", "acquisition corp", "be redeemable")
BOURSES_US = {"N": "NYSE", "A": "NYSE American", "P": "NYSE Arca", "Z": "Cboe BZX", "V": "IEX"}


def _nom_us(nom: str) -> str:
    """« Apple Inc. - Common Stock » -> « Apple Inc. »"""
    for coupe in (" - Common Stock", " Common Stock", " - Class A", " Class A Common", " - Ordinary Shares", " Ordinary Shares",
                  " - American Depositary Shares", " American Depositary Shares", " - American Depositary Share"):
        if coupe in nom:
            nom = nom.split(coupe)[0]
    return nom.strip(" -,")


def liste_usa() -> list:
    """Toutes les actions cotées aux États-Unis (fichiers publics de Nasdaq Trader)."""
    actions = []
    for url, place_fixe in (("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt", "Nasdaq"),
                            ("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt", None)):
        texte = requests.get(url, headers=ENTETES, timeout=60).text
        df = pd.read_csv(io.StringIO(texte), sep="|", dtype=str).fillna("")
        df = df[~df.iloc[:, 0].str.startswith("File Creation")]
        for _, l in df.iterrows():
            symbole = l.get("Symbol") or l.get("ACT Symbol")
            nom = l["Security Name"]
            if l.get("ETF") == "Y" or l.get("Test Issue") == "Y" or not symbole or "$" in symbole:
                continue
            if any(x in nom.lower() for x in EXCLUS_US):
                continue
            place = place_fixe or BOURSES_US.get(l.get("Exchange"), "États-Unis")
            if place in ("NYSE Arca", "Cboe BZX", "IEX"):
                continue
            actions.append({"ticker": symbole.replace(".", "-"), "nom": _nom_us(nom), "place": place,
                            "devise": "USD", "liquidite": 0})
    return actions


def _depuis_wikipedia(url: str, colonne: str, suffixe: str, place: str, devise: str, transformer=None) -> list:
    tables = pd.read_html(io.StringIO(requests.get(url, headers=ENTETES, timeout=60).text))
    for t in tables:
        cols = [str(c) for c in t.columns]
        if colonne in cols and len(t) >= 19:
            nom_col = next((c for c in ("Company", "Name", "Security") if c in cols), None)
            res = []
            for _, l in t.iterrows():
                tk = str(l[colonne]).strip()
                if not tk or tk == "nan":
                    continue
                tk = transformer(tk) if transformer else tk
                if not re.search(r"\.[A-Z]{1,2}$", tk):      # déjà un suffixe de place (ex. AIR.PA dans le DAX) : on garde
                    tk += suffixe
                res.append({"ticker": tk, "nom": str(l[nom_col]).strip() if nom_col else tk, "place": place,
                            "devise": devise, "liquidite": 0})
            return res
    return []


def liste_europe() -> list:
    sources = [
        ("https://en.wikipedia.org/wiki/DAX", "Ticker", ".DE", "Francfort (DAX)", "EUR", None),
        ("https://en.wikipedia.org/wiki/FTSE_100_Index", "Ticker", ".L", "Londres (FTSE 100)", "GBP", lambda t: t.replace(".", "-").rstrip("-")),
        ("https://en.wikipedia.org/wiki/FTSE_250_Index", "Ticker", ".L", "Londres (FTSE 250)", "GBP", lambda t: t.replace(".", "-").rstrip("-")),
        ("https://en.wikipedia.org/wiki/Swiss_Market_Index", "Ticker", ".SW", "Zurich (SMI)", "CHF", lambda t: t.split(".")[0]),
        ("https://en.wikipedia.org/wiki/IBEX_35", "Ticker", ".MC", "Madrid (IBEX 35)", "EUR", lambda t: t.split(".")[0]),
        ("https://en.wikipedia.org/wiki/OMX_Stockholm_30", "Ticker", ".ST", "Stockholm (OMXS30)", "SEK", lambda t: t.replace(" ", "-")),
    ]
    res = []
    for url, col, suf, place, dev, f in sources:
        try:
            l = _depuis_wikipedia(url, col, suf, place, dev, f)
            print(f"  {place:22s}: {len(l)}")
            res += l
        except Exception as e:
            print(f"  {place:22s}: échec ({e})")
    return res


if __name__ == "__main__":
    DOSSIER.mkdir(exist_ok=True)
    euronext = liste_euronext()
    sp500 = liste_sp500()
    print(f"Euronext : {len(euronext)} actions")
    print(f"S&P 500  : {len(sp500)} actions")
    usa = liste_usa()
    print(f"États-Unis (toutes cotations) : {len(usa)} actions")
    europe = liste_europe()

    # Doublons éventuels (même ticker) : on garde la 1re occurrence (S&P 500 et Euronext d'abord)
    vus, toutes = set(), []
    for a in sp500 + euronext + europe + usa:
        if a["ticker"] not in vus:
            vus.add(a["ticker"])
            toutes.append(a)

    fichier = DOSSIER / "actions.json"
    fichier.write_text(json.dumps(toutes, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Total    : {len(toutes)} actions -> {fichier}")
