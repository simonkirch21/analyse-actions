"""
SECTEURS — Tableau de bord de chaque secteur, à partir de la base fondamentale (~1 350 entreprises)
==================================================================================================

  - Vue d'ensemble : pour chaque secteur, nombre d'entreprises, capitalisation totale, performance
    médiane sur un an, PER et marge médians
  - Détail d'un secteur : entreprises classées par taille, médianes (PER, VE/EBITDA, marge, ROE,
    croissance, rendement, endettement), meilleures et moins bonnes sur chaque critère, et lecture
"""

import numpy as np

import base_fondamentale

CRITERES = [  # (champ, libellé, plus haut = mieux, pourcentage)
    ("var_1an", "Performance sur 1 an", True, True),
    ("per", "PER", False, False),
    ("ve_ebe", "VE / EBITDA", False, False),
    ("marge_nette", "Marge nette", True, True),
    ("roe", "ROE", True, True),
    ("croissance_ca", "Croissance du CA", True, True),
    ("rdt_div", "Rendement du dividende", True, True),
    ("levier", "Dette nette / EBITDA", False, False),
]
BORNES = {"per": (3, 200), "ve_ebe": (1, 100), "levier": (-10, 30), "roe": (-2, 3), "marge_nette": (-2, 1),
          "rdt_div": (0, 0.25), "croissance_ca": (-0.9, 3), "var_1an": (-0.95, 10)}


def _valeurs(actions, champ):
    lo, hi = BORNES.get(champ, (-1e18, 1e18))
    return [a[champ] for a in actions if a.get(champ) is not None and lo < a[champ] < hi]


def _med(actions, champ):
    v = _valeurs(actions, champ)
    return float(np.median(v)) if len(v) >= 3 else None


def _base():
    b = base_fondamentale.charger(reconstruire_si_perimee=False) or []
    return [a for a in b if a.get("secteur") and a["secteur"] != "Non renseigné"]


def vue_ensemble() -> dict:
    b = _base()
    secteurs = {}
    for a in b:
        secteurs.setdefault(a["secteur"], []).append(a)
    lignes = []
    for nom, acts in secteurs.items():
        if len(acts) < 5:
            continue
        lignes.append({"secteur": nom, "nb": len(acts), "capi": sum(a.get("capi_eur") or 0 for a in acts),
                       **{c: _med(acts, c) for c, *_ in CRITERES}})
    lignes.sort(key=lambda x: -x["capi"])
    return {"secteurs": lignes, "marche": {c: _med(b, c) for c, *_ in CRITERES}, "nb": len(b)}


def detail(secteur: str, univers: str = "") -> dict:
    b = _base()
    acts = [a for a in b if a["secteur"] == secteur]
    if univers == "eu":
        acts = [a for a in acts if a.get("place") and a["place"] != "S&P 500"]
    elif univers == "us":
        acts = [a for a in acts if a.get("place") == "S&P 500"]
    if not acts:
        raise ValueError("Secteur inconnu ou vide.")
    medianes = {c: _med(acts, c) for c, *_ in CRITERES}
    marche = {c: _med(b, c) for c, *_ in CRITERES}
    classements = []
    for c, lib, haut, pct in CRITERES:
        lo, hi = BORNES.get(c, (-1e18, 1e18))
        v = [a for a in acts if a.get(c) is not None and lo < a[c] < hi]
        v.sort(key=lambda a: a[c], reverse=haut)
        cle = lambda a: {"ticker": a["ticker"], "nom": a["nom"], "valeur": a[c]}
        classements.append({"champ": c, "libelle": lib, "pourcentage": pct, "meilleurs": [cle(a) for a in v[:3]],
                            "moins_bons": [cle(a) for a in v[-3:][::-1]] if len(v) > 6 else []})
    industries = {}
    for a in acts:
        industries[a.get("industrie") or "Autre"] = industries.get(a.get("industrie") or "Autre", 0) + 1
    entreprises = sorted(acts, key=lambda a: -(a.get("capi_eur") or 0))
    champs = ["ticker", "nom", "place", "industrie", "capi_eur", "var_1an", "per", "ve_ebe", "marge_nette", "roe",
              "croissance_ca", "rdt_div", "levier", "potentiel_analystes"]
    return {"secteur": secteur, "nb": len(acts), "capi": sum(a.get("capi_eur") or 0 for a in acts), "medianes": medianes,
            "marche": marche, "classements": classements,
            "industries": sorted(industries.items(), key=lambda x: -x[1])[:8],
            "entreprises": [{k: a.get(k) for k in champs} for a in entreprises], "lecture": lecture(secteur, medianes, marche)}


def lecture(secteur, m, marche) -> list:
    f = lambda x, p=False: "—" if x is None else (f"{x * 100:.1f} %" if p else f"{x:.1f}").replace(".", ",").replace("-", "−")
    ph = []
    if m["per"] and marche["per"]:
        ecart = m["per"] / marche["per"] - 1
        ph.append(f"Le secteur {secteur} se paie en médiane <b>{f(m['per'])} fois ses bénéfices</b>, contre {f(marche['per'])} pour "
                  "l'ensemble de la base : " + ("une prime, le marché attend plus de croissance ou de stabilité qu'ailleurs."
                                                if ecart > 0.15 else "une décote : le marché le juge plus cyclique, plus risqué ou en déclin."
                                                if ecart < -0.15 else "une valorisation dans la moyenne."))
    if m["marge_nette"] is not None and marche["marge_nette"] is not None:
        ph.append(f"Marge nette médiane de {f(m['marge_nette'], True)} (ensemble : {f(marche['marge_nette'], True)})"
                  + (" : un secteur à forte rentabilité (pouvoir de fixer ses prix, peu de capital à mobiliser)." if m["marge_nette"] > marche["marge_nette"] * 1.4 else
                     " : un secteur à faibles marges, où le volume et la maîtrise des coûts font la différence." if m["marge_nette"] < marche["marge_nette"] * 0.7 else "."))
    if m["var_1an"] is not None and marche["var_1an"] is not None:
        ph.append(f"Sur un an, l'action médiane du secteur a fait {f(m['var_1an'], True)}, contre {f(marche['var_1an'], True)} pour l'ensemble.")
    if m["levier"] is not None:
        ph.append(f"Endettement médian : {f(m['levier'])} fois l'EBITDA" + (" (secteur gourmand en capital : infrastructures, réseaux, immobilier)." if m["levier"] > 3 else "."))
    return ph


if __name__ == "__main__":
    v = vue_ensemble()
    for s in v["secteurs"]:
        print(f"{s['secteur']:28s} {s['nb']:4d}  capi {s['capi'] / 1e12:6.2f} T€  PER {s['per']}  1 an {s['var_1an']}")
    d = detail(v["secteurs"][0]["secteur"])
    print(d["lecture"])
    print(d["classements"][0])
