"""
APPLICATION — Analyse d'actions dans une fenêtre Mac
====================================================

Architecture :
  - un petit serveur web local (Flask) qui sert l'interface et lance les analyses ;
  - une fenêtre Mac native (pywebview, moteur WebKit de Safari) qui affiche l'interface ;
  - un « pont » Python ↔ JavaScript (classe Api) pour ouvrir la fenêtre « Enregistrer sous »
    du Mac lors des exports PDF / Excel.

Lancer :  .venv/bin/python app.py              (fenêtre Mac)
          .venv/bin/python app.py --navigateur (dans le navigateur, utile pour déboguer)
"""

import pickle
import re
import socket
import subprocess
import sys
import threading
import uuid
import webbrowser
from pathlib import Path

import matplotlib
matplotlib.use("Agg")   # graphiques sans fenêtre : obligatoire hors du fil principal

from flask import Flask, Response, jsonify, request, send_from_directory, abort

import analyse_complete as ac
import comparaison as cp
import export
import json
import portefeuille as pf
import marche
import actualites
import simulateur
import suivi
import base_fondamentale
import macro
import fictifs
import taux
import calendrier
import options_cotees

import chemins
ICI = chemins.RESSOURCES
RAPPORTS = ac.DOSSIER_RAPPORTS
LISTE = chemins.liste_actions()
# Données personnelles : dans un dossier que la réinstallation de l'application n'écrase pas
UTILISATEUR = chemins.UTILISATEUR
FICHIER_PF = UTILISATEUR / "portefeuille.json"
PERIODES = {"1y", "2y", "5y", "10y", "max"}
NOM_VALIDE = re.compile(r"^[A-Za-z0-9^._=\-]+$")   # noms de rapports autorisés (pas de « ../ »)

app = Flask(__name__, static_folder=str(chemins.INTERFACE), static_url_path="")
app.json.sort_keys = False        # garde l'ordre voulu des séries (légendes, couleurs des courbes)

travaux = {}                 # identifiant -> état d'une analyse en cours
verrou = threading.Lock()    # une analyse à la fois (matplotlib n'aime pas le parallélisme)


@app.get("/")
def accueil():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/actions")
def actions():
    """Liste complète des actions (le filtrage se fait dans l'interface : instantané)."""
    return app.response_class(LISTE.read_text(encoding="utf-8"), mimetype="application/json")


# ---------------------------------------------------------------------------
# Analyses (une action, ou comparaison de deux) lancées en arrière-plan
# ---------------------------------------------------------------------------
def _lancer(travail) -> str:
    id_travail = uuid.uuid4().hex
    etat = travaux[id_travail] = {"statut": "en_cours", "etape": "En attente…", "etapes": 0}

    def progression(message: str):
        etat["etape"] = message
        etat["etapes"] += 1

    def executer():
        with verrou:
            marche.analyse_en_cours.set()
            try:
                etat.update(statut="termine", **travail(progression))
            except Exception as erreur:      # ticker sans données, réseau coupé...
                etat.update(statut="erreur", message=str(erreur))
            finally:
                marche.analyse_en_cours.clear()

    threading.Thread(target=executer, daemon=True).start()
    return id_travail


@app.post("/api/analyse")
def lancer_analyse():
    d = request.get_json(force=True)
    ticker = str(d.get("ticker", "")).strip().upper()
    periode = d.get("periode", "5y")
    if not ticker or periode not in PERIODES or not NOM_VALIDE.match(ticker):
        return jsonify(erreur="Paramètres invalides"), 400

    def travail(progression):
        ac.analyse_en_cache(ticker, periode, progression=progression, forcer=bool(d.get("forcer")))
        nom = ac.nom_rapport(ticker, periode)
        return {"rapport": f"/rapports/{nom}.html", "nom": nom}
    return jsonify(id=_lancer(travail))


@app.post("/api/comparer")
def lancer_comparaison():
    d = request.get_json(force=True)
    t1, t2 = (str(d.get(k, "")).strip().upper() for k in ("t1", "t2"))
    periode = d.get("periode", "5y")
    if not t1 or not t2 or periode not in PERIODES or not (NOM_VALIDE.match(t1) and NOM_VALIDE.match(t2)):
        return jsonify(erreur="Paramètres invalides"), 400

    def travail(progression):
        c = cp.comparer(t1, t2, periode, progression)
        nom = cp.nom_fichier(t1, t2, periode)
        (RAPPORTS / f"{nom}.html").write_text(cp.generer_html(c), encoding="utf-8")
        with open(RAPPORTS / f"{nom}.pkl", "wb") as f:         # pour l'export Excel
            pickle.dump({k: c[k] for k in ("t1", "t2", "lignes")}, f)
        return {"rapport": f"/rapports/{nom}.html", "nom": nom}
    return jsonify(id=_lancer(travail))


# ---------------------------------------------------------------------------
# Accueil : tableau de bord des marchés et actualités
# ---------------------------------------------------------------------------
def _json_propre(objet):
    """NaN -> null (le JSON standard n'accepte pas NaN)."""
    import math
    if isinstance(objet, float) and (math.isnan(objet) or math.isinf(objet)):
        return None
    if isinstance(objet, dict):
        return {k: _json_propre(v) for k, v in objet.items()}
    if isinstance(objet, list):
        return [_json_propre(v) for v in objet]
    return objet


def _reponse(fonction, *args):
    try:
        return jsonify(_json_propre(fonction(*args)))
    except Exception as erreur:
        return jsonify(erreur=str(erreur)), 503


@app.get("/api/marche/indices")
def api_indices():
    return _reponse(marche.indices)


@app.get("/api/marche/indice/<code>")
def api_indice(code):
    periode = request.args.get("periode", "1y")
    if periode not in {"1m", "6m", "1y", "5y", "10y", "max"}:
        abort(400)
    return _reponse(marche.historique, code, periode)


@app.get("/api/marche/phares")
def api_phares():
    return _reponse(marche.phares)


@app.get("/api/marche/palmares")
def api_palmares():
    return _reponse(marche.palmares)


@app.get("/api/actualites")
def api_actualites():
    return _reponse(actualites.generales)


@app.get("/api/actualites/<ticker>")
def api_actualites_action(ticker):
    if not NOM_VALIDE.match(ticker):
        abort(400)
    return _reponse(actualites.par_entreprise, request.args.get("nom", ticker), ticker.upper())


# ---------------------------------------------------------------------------
# Simulateur, filtre d'actions, liste de suivi
# ---------------------------------------------------------------------------
@app.get("/api/simulateur/presets")
def api_presets():
    return jsonify([{"ticker": t, "nom": n, "note": x} for t, n, x in simulateur.PRESETS])


@app.post("/api/simuler")
def api_simuler():
    d = request.get_json(force=True)
    ticker = str(d.get("ticker", "")).strip().upper()
    if not NOM_VALIDE.match(ticker):
        return jsonify(erreur="Actif invalide"), 400
    try:
        initial, mensuel = max(0.0, float(d.get("initial") or 0)), max(0.0, float(d.get("mensuel") or 0))
    except (TypeError, ValueError):
        return jsonify(erreur="Montants invalides"), 400
    if initial + mensuel <= 0:
        return jsonify(erreur="Indique un montant de départ ou un versement mensuel."), 400
    try:
        return jsonify(_json_propre(simulateur.simuler(ticker, initial, mensuel, str(d.get("debut", "2015-01")))))
    except Exception as erreur:
        return jsonify(erreur=str(erreur)), 400


@app.get("/api/filtre")
def api_filtre():
    base = base_fondamentale.charger()
    e = base_fondamentale.etat
    return jsonify(_json_propre({"actions": base, "en_cours": e["en_cours"], "faits": e["faits"], "total": e["total"]}))


@app.get("/api/suivi")
def api_lire_suivi():
    return jsonify(suivi.lire())


@app.post("/api/suivi")
def api_enregistrer_suivi():
    return jsonify(suivi.enregistrer(request.get_json(force=True)))


@app.get("/api/suivi/etat")
def api_etat_suivi():
    return _reponse(suivi.etat)


# ---------------------------------------------------------------------------
# Macroéconomie et portefeuilles fictifs
# ---------------------------------------------------------------------------
@app.get("/api/marche/carte")
def api_carte():
    u = request.args.get("univers", "cac")
    if u not in ("cac", "eu", "sp"):
        abort(400)
    return _reponse(marche.carte, u)


@app.get("/api/marche/ohlc/<ticker>")
def api_ohlc(ticker):
    periode = request.args.get("periode", "1y")
    if not NOM_VALIDE.match(ticker) or periode not in {"1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"}:
        abort(400)
    return _reponse(marche.ohlc, ticker.upper(), periode)


@app.get("/api/marche/actifs")
def api_actifs():
    return _reponse(marche.actifs)


@app.get("/api/taux")
def api_taux():
    return _reponse(taux.courbes)


@app.get("/api/calendrier")
def api_calendrier():
    return _reponse(lambda: {"evenements": calendrier.evenements(), "resultats": calendrier.resultats()})


@app.get("/api/options/<ticker>")
def api_options(ticker):
    if not NOM_VALIDE.match(ticker):
        abort(400)
    return _action_fictive(lambda: options_cotees.chaine(ticker.upper(), request.args.get("echeance") or None))


@app.get("/api/macro")
def api_macro():
    return _reponse(macro.tableau)


def _corps():
    return request.get_json(force=True) or {}


def _action_fictive(fonction):
    try:
        return jsonify(_json_propre(fonction()))
    except ValueError as erreur:            # erreur « métier » : message pour l'utilisateur
        return jsonify(erreur=str(erreur)), 400
    except Exception as erreur:
        return jsonify(erreur=f"Opération impossible ({erreur})."), 503


@app.get("/api/fictifs")
def api_fictifs():
    return _action_fictive(fictifs.liste)


@app.post("/api/fictifs")
def api_creer_fictif():
    d = _corps()
    return _action_fictive(lambda: fictifs.creer(d.get("nom"), d.get("capital", 10000), d.get("date_creation") or None,
                                                 d.get("frais_pct", 0.1), d.get("frais_min", 1)))


@app.get("/api/fictifs/<id_>")
def api_fictif(id_):
    return _action_fictive(lambda: fictifs.detail(id_))


@app.delete("/api/fictifs/<id_>")
def api_supprimer_fictif(id_):
    return _action_fictive(lambda: fictifs.supprimer(id_) or {"ok": True})


@app.post("/api/fictifs/<id_>/ordre")
def api_ordre(id_):
    d = _corps()
    ticker = str(d.get("ticker", "")).upper()
    if not NOM_VALIDE.match(ticker):
        return jsonify(erreur="Action invalide."), 400
    def nombre(x):
        return float(x) if x not in (None, "") else None
    return _action_fictive(lambda: fictifs.ordre(id_, d.get("sens"), ticker, d.get("nom", ""),
                                                 nombre(d.get("quantite")), nombre(d.get("montant")), d.get("date") or None))


@app.post("/api/fictifs/<id_>/annuler")
def api_annuler(id_):
    return _action_fictive(lambda: fictifs.annuler_dernier(id_) or {"ok": True})


@app.get("/api/cotation/<ticker>")
def api_cotation(ticker):
    if not NOM_VALIDE.match(ticker):
        abort(400)
    return _action_fictive(lambda: fictifs.cotation(ticker, request.args.get("date") or None))


@app.get("/api/portefeuille")
def lire_portefeuille():
    try:
        return jsonify(json.loads(FICHIER_PF.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify([])


@app.post("/api/portefeuille")
def enregistrer_portefeuille():
    """Enregistre la liste complète : [{ticker, nom, place, montant}, ...]"""
    lignes = []
    for l in request.get_json(force=True) or []:
        t = str(l.get("ticker", "")).strip().upper()
        if not t or not NOM_VALIDE.match(t) or any(x["ticker"] == t for x in lignes):
            continue
        try:
            montant = max(0.0, float(l.get("montant") or 0))
        except (TypeError, ValueError):
            montant = 0.0
        ligne = {"ticker": t, "nom": str(l.get("nom") or t)[:120],
                 "place": str(l.get("place") or "")[:40], "montant": montant}
        if re.match(r"^\d{4}-\d{2}-\d{2}$", str(l.get("date_achat") or "")):
            ligne["date_achat"] = l["date_achat"]
        try:
            if l.get("prix_achat") not in (None, ""):
                ligne["prix_achat"] = max(0.0, float(l["prix_achat"])) or None
        except (TypeError, ValueError):
            pass
        lignes.append(ligne)
    UTILISATEUR.mkdir(exist_ok=True)
    FICHIER_PF.write_text(json.dumps(lignes, ensure_ascii=False, indent=1), encoding="utf-8")
    return jsonify(lignes)


@app.post("/api/analyse_portefeuille")
def lancer_portefeuille():
    d = request.get_json(force=True)
    periode = d.get("periode", "5y")
    enveloppe = "PEA" if d.get("enveloppe") == "PEA" else "CTO"
    if periode not in PERIODES:
        return jsonify(erreur="Paramètres invalides"), 400
    try:
        lignes = json.loads(FICHIER_PF.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        lignes = []

    def travail(progression):
        p = pf.analyser(lignes, periode, progression, enveloppe)
        progression("Génération des graphiques…")
        graphiques = {k: ac.image_base64(f, p) for k, f in pf.GRAPHIQUES.items()}
        nom = pf.nom_fichier(periode)
        RAPPORTS.mkdir(exist_ok=True)
        (RAPPORTS / f"{nom}.html").write_text(pf.generer_html(p, graphiques), encoding="utf-8")
        with open(RAPPORTS / f"{nom}.pkl", "wb") as f:
            pickle.dump(p, f)
        return {"rapport": f"/rapports/{nom}.html", "nom": nom}
    return jsonify(id=_lancer(travail))


@app.get("/api/statut/<id_travail>")
def statut(id_travail):
    if id_travail not in travaux:
        abort(404)
    return jsonify(travaux[id_travail])


@app.get("/rapports/<path:nom>")
def rapport(nom):
    return send_from_directory(RAPPORTS, nom)


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------
def contenu_export(format_: str, nom: str) -> bytes:
    """PDF ou Excel d'un rapport déjà calculé (identifié par son nom de fichier)."""
    if not NOM_VALIDE.match(nom) or format_ not in {"pdf", "xlsx"}:
        raise ValueError("Export invalide")
    if format_ == "pdf":
        return export.html_vers_pdf((RAPPORTS / f"{nom}.html").read_text(encoding="utf-8"))
    with open(RAPPORTS / f"{nom}.pkl", "rb") as f:
        donnees = pickle.load(f)
    if nom.startswith("comparaison_"):
        return export.classeur_comparaison(donnees)
    if nom.startswith("portefeuille_"):
        return export.classeur_portefeuille(donnees)
    return export.classeur(donnees)


@app.get("/api/export/<format_>/<nom>")
def telecharger(format_, nom):
    """Téléchargement direct (utilisé quand l'interface tourne dans un navigateur)."""
    try:
        contenu = contenu_export(format_, nom)
    except (ValueError, FileNotFoundError):
        abort(404)
    types = {"pdf": "application/pdf",
             "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    return Response(contenu, mimetype=types[format_],
                    headers={"Content-Disposition": f'attachment; filename="{nom}.{format_}"'})


class Api:
    """Fonctions Python appelables depuis la page (window.pywebview.api.…)."""

    def enregistrer(self, format_: str, nom: str) -> str:
        import webview
        fenetre = webview.windows[0]
        choix = fenetre.create_file_dialog(webview.SAVE_DIALOG, save_filename=f"{nom}.{format_}")
        if not choix:
            return ""                                   # l'utilisateur a annulé
        chemin = choix if isinstance(choix, str) else choix[0]
        Path(chemin).write_bytes(contenu_export(format_, nom))
        subprocess.run(["open", "-R", chemin])          # montre le fichier dans le Finder
        return chemin


def port_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


if __name__ == "__main__":
    RAPPORTS.mkdir(parents=True, exist_ok=True)
    UTILISATEUR.mkdir(parents=True, exist_ok=True)

    if "--serveur" in sys.argv:      # serveur seul sur un port fixe (tests)
        threading.Thread(target=marche.precharger, daemon=True).start()
        app.run(host="127.0.0.1", port=5055, threaded=True, use_reloader=False)
        sys.exit()

    # Prépare les données de l'accueil en arrière-plan pendant que la fenêtre s'ouvre
    threading.Thread(target=marche.precharger, daemon=True).start()
    base_fondamentale.charger()          # reconstruit la base de ratios si elle a plus d'un jour
    suivi.demarrer_surveillance()        # alertes de la liste de suivi
    port = port_libre()
    adresse = f"http://127.0.0.1:{port}"
    serveur = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False),
        daemon=True)
    serveur.start()

    if "--navigateur" in sys.argv:
        print(f"Interface : {adresse}  (Ctrl+C pour arrêter)")
        webbrowser.open(adresse)
        serveur.join()
    else:
        import webview   # pywebview
        webview.create_window("Analyse Actions", adresse, width=1300, height=880,
                              min_size=(900, 600), js_api=Api())
        # Mode privé désactivé : la page garde ses réglages (actions récentes) d'un lancement à l'autre
        UTILISATEUR.mkdir(exist_ok=True)
        webview.start(private_mode=False, storage_path=str(UTILISATEUR / "navigateur"))
