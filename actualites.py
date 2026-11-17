"""
ACTUALITÉS — Économie générale et actualités propres à une entreprise
====================================================================

  - Accueil : flux RSS de la presse économique française (Le Monde, France 24, La Tribune, Investing).
  - Par entreprise : Google Actualités en français (nom de l'entreprise + mots-clés financiers,
    21 derniers jours), complété par les articles de Yahoo Finance (presse anglophone).

Seuls les titres, la source, la date et le lien sont affichés : l'article s'ouvre dans le navigateur.
"""

import html
import re
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import pandas as pd
import requests

ENTETES = {"User-Agent": "Mozilla/5.0 (Macintosh) analyse-action"}
FLUX = {
    "Le Monde": "https://www.lemonde.fr/economie/rss_full.xml",
    "France 24": "https://www.france24.com/fr/eco-tech/rss",
    "La Tribune": "https://www.latribune.fr/feed.xml",
    "Investing.com": "https://fr.investing.com/rss/news_14.rss",
}
# Résultats de recherche qui ne sont pas des articles (pages de cotation, fiches de consensus…)
PAS_UN_ARTICLE = re.compile(r"cours (de l'|de l’)?action|cotation|cours action|consensus .*avis|"
                            r"objectif de cours et consensus|forum|graphique|historique des cours|"
                            r"\|\s*cours\b", re.I)

_cache, _verrou = {}, threading.Lock()


def _en_cache(cle, duree, calcul):
    with _verrou:
        v = _cache.get(cle)
        if v and time.time() - v[0] < duree:
            return v[1]
    r = calcul()
    with _verrou:
        _cache[cle] = (time.time(), r)
    return r


def _date(texte: str):
    if not texte:
        return None
    try:
        d = parsedate_to_datetime(texte)
    except (TypeError, ValueError):
        try:
            d = pd.Timestamp(texte).to_pydatetime()
        except Exception:
            return None
    if d.tzinfo is None:                     # heure de Paris si non précisée
        d = pd.Timestamp(d).tz_localize("Europe/Paris").to_pydatetime()
    return d


def _nettoyer(texte: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", texte or "")).strip()


def _lire_flux(source: str, url: str, n: int = 15) -> list:
    r = requests.get(url, headers=ENTETES, timeout=8)
    r.raise_for_status()
    articles = []
    for it in ET.fromstring(r.content).findall(".//item")[:n]:
        titre = _nettoyer(it.findtext("title"))
        source_it = it.findtext("source") or source
        # Google Actualités ajoute « - Source » à la fin du titre
        if source_it and titre.endswith(" - " + source_it):
            titre = titre[: -len(source_it) - 3]
        d = _date(it.findtext("pubDate"))
        articles.append({"titre": titre, "lien": it.findtext("link"), "source": source_it,
                         "date": d.isoformat() if d else None, "_t": d.timestamp() if d else 0})
    return articles


def generales(n: int = 24) -> list:
    """Dernières actualités économiques, toutes sources confondues."""
    def calcul():
        tous = []
        for source, url in FLUX.items():
            try:
                tous += _lire_flux(source, url)
            except Exception:
                continue
        vus, res = set(), []
        for a in sorted(tous, key=lambda a: -a["_t"]):
            cle = a["titre"].lower()[:60]
            if cle in vus or not a["titre"]:
                continue
            vus.add(cle)
            res.append({k: v for k, v in a.items() if k != "_t"})
        return res[:n]
    return _en_cache("generales", 900, calcul)


def _sans_accent(texte: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", texte or "") if unicodedata.category(c) != "Mn").lower()


def nom_court(nom: str) -> str:
    """« LVMH Moët Hennessy - Louis Vuitton, Société Européenne » -> « LVMH »."""
    nom = re.split(r"[,(]| - ", nom or "")[0]
    nom = re.sub(r"\b(SA|SE|S\.A\.|Inc\.?|Corp\.?|Corporation|plc|N\.V\.|NV|AG|SpA|ASA|Holding|Group|"
                 r"Société Européenne|Société anonyme|Company|Co\.|Ltd\.?|Limited)\b\.?", "", nom, flags=re.I)
    return re.sub(r"\s+", " ", nom).strip(" -.") or nom


def par_entreprise(nom: str, ticker: str, n_fr: int = 8, n_en: int = 5) -> dict:
    """Actualités récentes d'une entreprise : presse française + presse internationale."""
    court = nom_court(nom) or ticker

    def calcul():
        fr = []
        try:
            # Mots-clés financiers : on veut l'actualité de l'entreprise, pas celle de ses produits
            q = (f'"{court}" (bourse OR actionnaires OR résultats OR "titre" OR "chiffre d\'affaires" '
                 'OR analystes OR dividende) when:21d')
            url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
                {"q": q, "hl": "fr", "gl": "FR", "ceid": "FR:fr"})
            cle = _sans_accent(court)
            fr = [a for a in _lire_flux("Google Actualités", url, 40)
                  if not PAS_UN_ARTICLE.search(a["titre"]) and cle in _sans_accent(a["titre"])]
            fr.sort(key=lambda a: -a["_t"])
        except Exception:
            pass
        en = []
        try:
            import yfinance as yf
            for x in yf.Ticker(ticker).news or []:
                c = x.get("content", x)
                lien = (c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url")
                d = _date(c.get("pubDate"))
                en.append({"titre": c.get("title"), "lien": lien, "source": (c.get("provider") or {}).get("displayName", "Yahoo Finance"),
                           "date": d.isoformat() if d else None, "resume": c.get("summary")})
        except Exception:
            pass
        nettoie = lambda l: [{k: v for k, v in a.items() if k != "_t"} for a in l if a.get("titre") and a.get("lien")]
        return {"recherche": court, "fr": nettoie(fr)[:n_fr], "en": nettoie(en)[:n_en]}
    return _en_cache(f"ent_{ticker}", 900, calcul)
