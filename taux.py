"""
COURBE DES TAUX — Le prix de l'argent selon la durée
====================================================

La courbe des taux relie les taux d'intérêt des emprunts d'État à leur durée (3 mois … 30 ans).
Normalement elle MONTE : prêter longtemps est plus risqué, donc mieux rémunéré. Quand elle
s'INVERSE (taux courts > taux longs), les marchés anticipent des baisses de taux, souvent à cause
d'un ralentissement : aux États-Unis, presque toutes les récessions depuis 50 ans ont été précédées
d'une inversion.

Sources :
  - États-Unis : rendements des bons du Trésor (FRED, séries DGS…)
  - Zone euro : courbes estimées par la BCE à partir des emprunts d'État notés AAA (proche de
    l'Allemagne) et de tous les emprunts d'État de la zone euro (inclut France, Italie, Espagne…).
"""

import io
import threading
import time

import pandas as pd
import requests

ENTETES = {"User-Agent": "Mozilla/5.0 (Macintosh) analyse-action"}
ECHEANCES = [("3 mois", 0.25), ("6 mois", 0.5), ("1 an", 1), ("2 ans", 2), ("3 ans", 3), ("5 ans", 5),
             ("7 ans", 7), ("10 ans", 10), ("20 ans", 20), ("30 ans", 30)]
FRED_US = {"3 mois": "DGS3MO", "6 mois": "DGS6MO", "1 an": "DGS1", "2 ans": "DGS2", "3 ans": "DGS3", "5 ans": "DGS5",
           "7 ans": "DGS7", "10 ans": "DGS10", "20 ans": "DGS20", "30 ans": "DGS30"}
BCE = {"3 mois": "3M", "6 mois": "6M", "1 an": "1Y", "2 ans": "2Y", "3 ans": "3Y", "5 ans": "5Y", "7 ans": "7Y",
       "10 ans": "10Y", "20 ans": "20Y", "30 ans": "30Y"}
COURBES = {"États-Unis": None, "Zone euro AAA (≈ Allemagne)": "G_N_A", "Zone euro, tous États (≈ France, Italie…)": "G_N_C"}

_cache, _verrou = {}, threading.Lock()


def _fred(code: str) -> pd.Series:
    r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={code}", headers=ENTETES, timeout=20)
    df = pd.read_csv(io.StringIO(r.text))
    return pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").values, index=pd.to_datetime(df.iloc[:, 0])).dropna()


def _bce(type_: str, maturite: str, depuis: str) -> pd.Series:
    url = (f"https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.{type_}.SV_C_YM.SR_{maturite}"
           f"?format=csvdata&startPeriod={depuis}")
    df = pd.read_csv(io.StringIO(requests.get(url, headers=ENTETES, timeout=30).text))
    return pd.Series(df["OBS_VALUE"].values, index=pd.to_datetime(df["TIME_PERIOD"])).dropna()


def _series() -> dict:
    """{courbe: DataFrame (dates × échéances)} sur 3 ans."""
    depuis = (pd.Timestamp.today() - pd.DateOffset(years=3)).strftime("%Y-%m-%d")
    from concurrent.futures import ThreadPoolExecutor

    def une(cle):
        nom, type_, ech = cle
        try:
            s = _fred(FRED_US[ech]) if type_ is None else _bce(type_, BCE[ech], depuis)
            return cle, s[s.index >= depuis]
        except Exception:
            return cle, None
    taches = [(nom, type_, ech) for nom, type_ in COURBES.items() for ech, _ in ECHEANCES]
    with ThreadPoolExecutor(10) as ex:           # 30 téléchargements en parallèle
        resultats = dict(ex.map(une, taches))
    res = {}
    for nom, type_ in COURBES.items():
        cols = {ech: resultats[(nom, type_, ech)] for ech, _ in ECHEANCES if resultats[(nom, type_, ech)] is not None}
        if cols:
            res[nom] = pd.DataFrame(cols).ffill()
    return res


def courbes() -> dict:
    with _verrou:
        v = _cache.get("courbes")
        if v and time.time() - v[0] < 6 * 3600:
            return v[1]
    donnees = _series()
    res = {"echeances": [e for e, _ in ECHEANCES], "annees": [a for _, a in ECHEANCES], "courbes": [], "ecarts": []}
    for nom, df in donnees.items():
        df = df.dropna(how="all")
        if df.empty:
            continue
        aujourd_hui = df.iloc[-1]
        def a_date(delta):
            sous = df[df.index <= df.index[-1] - delta]
            return sous.iloc[-1] if len(sous) else None
        instantanes = {f"Aujourd'hui ({df.index[-1]:%d/%m/%Y})": aujourd_hui,
                       "Il y a 6 mois": a_date(pd.DateOffset(months=6)), "Il y a 1 an": a_date(pd.DateOffset(years=1)),
                       "Il y a 2 ans": a_date(pd.DateOffset(years=2))}
        res["courbes"].append({
            "nom": nom,
            "instantanes": {k: [None if (v is None or pd.isna(v.get(e))) else round(float(v.get(e)), 3)
                                for e, _ in ECHEANCES] for k, v in instantanes.items() if v is not None},
        })
        # Écart 10 ans − 2 ans : négatif = courbe inversée
        if "10 ans" in df and "2 ans" in df:
            ecart = (df["10 ans"] - df["2 ans"]).dropna()
            hebdo = ecart.resample("W-FRI").last().dropna()
            res["ecarts"].append({"nom": nom, "dernier": round(float(ecart.iloc[-1]), 3),
                                  "points": [[d.strftime("%Y-%m-%d"), round(float(x), 3)] for d, x in hebdo.items()]})
    res["lecture"] = lecture(res)
    with _verrou:
        _cache["courbes"] = (time.time(), res)
    return res


def lecture(res: dict) -> list:
    f = lambda x: f"{x:.2f}".replace(".", ",").replace("-", "−")
    phrases = []
    for e in res["ecarts"]:
        x = e["dernier"]
        if x < 0:
            phrases.append(f"{e['nom']} : courbe <b>inversée</b> (10 ans − 2 ans = {f(x)} point) : les marchés anticipent "
                           "des baisses de taux, souvent le signe d'un ralentissement économique attendu.")
        elif x < 0.3:
            phrases.append(f"{e['nom']} : courbe <b>plate</b> (10 ans − 2 ans = {f(x)} point) : peu de différence entre "
                           "prêter à court et à long terme ; l'incertitude sur la croissance est élevée.")
        else:
            phrases.append(f"{e['nom']} : courbe <b>normale</b>, croissante (10 ans − 2 ans = +{f(x)} point) : prêter "
                           "longtemps est mieux rémunéré, situation habituelle d'une économie en croissance.")
    c = {x["nom"]: x for x in res["courbes"]}
    a, t = c.get("Zone euro AAA (≈ Allemagne)"), c.get("Zone euro, tous États (≈ France, Italie…)")
    if a and t:
        i10 = res["echeances"].index("10 ans")
        v_a, v_t = list(a["instantanes"].values())[0][i10], list(t["instantanes"].values())[0][i10]
        if v_a is not None and v_t is not None:
            phrases.append(f"À 10 ans, l'ensemble des États de la zone euro emprunte à {f(v_t)} % contre {f(v_a)} % pour les "
                           f"mieux notés : la prime de risque des pays plus endettés est de {(v_t - v_a) * 100:.0f} points de base.")
    return phrases


if __name__ == "__main__":
    r = courbes()
    for c in r["courbes"]:
        print(c["nom"])
        for k, v in c["instantanes"].items():
            print(f"   {k:28s}", v)
    for e in r["ecarts"]:
        print("écart 10-2 :", e["nom"], e["dernier"], len(e["points"]))
    print(*r["lecture"], sep="\n")
