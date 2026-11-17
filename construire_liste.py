"""
Construit la liste des actions proposées dans l'application :
  - toutes les actions des marchés Euronext (Paris, Amsterdam, Bruxelles,
    Lisbonne, Dublin, Milan, Oslo), d'après le fichier officiel d'Euronext
  - les ~500 valeurs du S&P 500, d'après Wikipédia

Résultat : data/actions.json (à relancer de temps en temps pour mettre à jour).

Lancer :  .venv/bin/python construire_liste.py
"""

import io
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


if __name__ == "__main__":
    DOSSIER.mkdir(exist_ok=True)
    euronext = liste_euronext()
    sp500 = liste_sp500()
    print(f"Euronext : {len(euronext)} actions")
    print(f"S&P 500  : {len(sp500)} actions")

    # Doublons éventuels (même ticker) : on garde la 1re occurrence
    vus, toutes = set(), []
    for a in sp500 + euronext:
        if a["ticker"] not in vus:
            vus.add(a["ticker"])
            toutes.append(a)

    fichier = DOSSIER / "actions.json"
    fichier.write_text(json.dumps(toutes, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Total    : {len(toutes)} actions -> {fichier}")
