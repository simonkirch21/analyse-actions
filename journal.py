"""
JOURNAL D'INVESTISSEMENT — Écrire pourquoi on achète, pour ne pas se mentir ensuite
==================================================================================

Pour chaque action : la thèse (« pourquoi j'achète »), ce qui me ferait changer d'avis, un prix
d'achat et un prix de vente visés, et la date. Le journal est rappelé à chaque nouvelle analyse :
c'est une discipline de professionnel contre les biais (on oublie ses raisons, on garde une
action par fierté, on vend par panique).
"""

import json
from datetime import date

import chemins

FICHIER = chemins.UTILISATEUR / "journal.json"


def lire() -> dict:
    try:
        return json.loads(FICHIER.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _nombre(x):
    try:
        return float(x) if x not in (None, "") else None
    except (TypeError, ValueError):
        return None


def enregistrer(ticker: str, entree: dict) -> dict:
    j = lire()
    texte = str(entree.get("these") or "").strip()[:4000]
    risque = str(entree.get("risque") or "").strip()[:2000]
    if not texte and not risque and entree.get("achat") in (None, "") and entree.get("vente") in (None, ""):
        j.pop(ticker, None)                        # entrée vidée : on la supprime
    else:
        ancien = j.get(ticker, {})
        j[ticker] = {"nom": str(entree.get("nom") or ancien.get("nom") or ticker)[:120], "these": texte, "risque": risque,
                     "achat": _nombre(entree.get("achat")), "vente": _nombre(entree.get("vente")),
                     "cree": ancien.get("cree") or date.today().isoformat(), "maj": date.today().isoformat()}
    chemins.UTILISATEUR.mkdir(parents=True, exist_ok=True)
    FICHIER.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    return j.get(ticker, {})
