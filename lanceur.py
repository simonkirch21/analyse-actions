"""
LANCEUR de l'application autonome
=================================

Ouvre la fenêtre TOUT DE SUITE avec un écran de chargement, puis charge le reste en
arrière-plan (bibliothèques de calcul, serveur local). Au tout premier lancement sur un Mac,
matplotlib doit indexer les polices du système, ce qui peut prendre jusqu'à une minute :
sans cet écran, l'utilisateur verrait une fenêtre vide et croirait que l'app est bloquée.
"""

import socket
import threading
import time

import webview

import chemins

CHARGEMENT = """<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><style>
:root { color-scheme: light dark; }
body { margin: 0; height: 100vh; display: flex; align-items: center; justify-content: center;
       font: 15px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0A0F1C; color: #ECE8DF; }
@media (prefers-color-scheme: dark) { body { background: #0A0F1C; color: #ECE8DF; } p { color: #8D94A5; }
  .roue { border-color: #D4AF6A33 !important; border-top-color: #D4AF6A !important; } }
h1 { font-family: "New York", ui-serif, Cambria, Georgia, serif; font-weight: 600; }
.boite { text-align: center; max-width: 440px; }
h1 { font-size: 26px; margin: 0 0 8px; }
p { color: #8D94A5; line-height: 1.5; }
.roue { width: 34px; height: 34px; margin: 22px auto; border: 3px solid #D4AF6A33; border-top-color: #D4AF6A;
        border-radius: 50%; animation: t 0.9s linear infinite; }
@keyframes t { to { transform: rotate(360deg); } }
</style></head><body><div class="boite"><h1>Analyse Actions</h1><div class="roue"></div>
<p id="m">Démarrage…</p>
<p style="font-size:13px">Au tout premier lancement, la préparation peut prendre jusqu'à une minute.
Les fois suivantes, l'application s'ouvre en quelques secondes.</p></div></body></html>"""


def message(fenetre, texte):
    try:
        fenetre.evaluate_js(f"document.getElementById('m').textContent = {texte!r}")
    except Exception:
        pass


def demarrer(fenetre):
    message(fenetre, "Chargement des outils de calcul…")
    import app                      # import lourd (pandas, matplotlib, scipy…)
    import marche

    chemins.RAPPORTS.mkdir(parents=True, exist_ok=True)
    chemins.UTILISATEUR.mkdir(parents=True, exist_ok=True)
    fenetre.expose(app.Api().enregistrer)        # export PDF / Excel (fenêtre « Enregistrer sous »)

    message(fenetre, "Démarrage du serveur local…")
    port = app.port_libre()
    threading.Thread(target=lambda: app.app.run(host="127.0.0.1", port=port, threaded=True,
                                                use_reloader=False), daemon=True).start()
    threading.Thread(target=marche.precharger, daemon=True).start()
    import base_fondamentale
    import suivi
    base_fondamentale.charger()          # base de ratios (filtre, concurrents), une fois par jour
    suivi.demarrer_surveillance()        # alertes de la liste de suivi
    for _ in range(100):            # attend que le serveur réponde
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    fenetre.load_url(f"http://127.0.0.1:{port}")


def verifier(fichier_resultat: str) -> int:
    """Auto-vérification sans fenêtre (utilisée par la construction automatique sur GitHub) :
    charge tous les modules, interroge le serveur et fabrique un PDF, un classeur et un graphique."""
    lignes, code = [], 0

    def test(nom, fonction):
        nonlocal code
        try:
            r = fonction()
            lignes.append(f"OK    {nom} {r if r is not None else ''}")
        except Exception as e:                       # noqa: BLE001
            code = 1
            lignes.append(f"ECHEC {nom} : {type(e).__name__} {e}")

    import importlib
    for m in ("app", "analyse_complete", "dcf_avance", "note_analyse", "resultats", "qualite", "facteurs",
              "dividendes", "secteurs", "etf", "journal", "portefeuille", "comparaison", "export", "suivi", "marche"):
        test(f"import {m}", lambda m=m: importlib.import_module(m) and None)
    import app
    client = app.app.test_client()
    test("page d'accueil", lambda: client.get("/").status_code)
    test("liste d'actions", lambda: len(client.get("/api/actions").get_json()))
    import export
    test("PDF (xhtml2pdf)", lambda: len(export.page_simple_vers_pdf("<html><head><style></style></head><body><p>Test − β σ</p></body></html>")))
    import openpyxl, io
    def classeur():
        wb = openpyxl.Workbook(); wb.active["A1"] = "=1+1"; b = io.BytesIO(); wb.save(b); return len(b.getvalue())
    test("Excel (openpyxl)", classeur)
    def graphique():
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(); ax.plot([1, 2, 3]); b = io.BytesIO(); fig.savefig(b); plt.close(fig); return len(b.getvalue())
    test("graphique (matplotlib)", graphique)
    test("dossier des données", lambda: str(chemins.DONNEES))
    # Données de marché : informatif (les serveurs de GitHub sont parfois limités par Yahoo)
    try:
        import yfinance as yf
        px = yf.Ticker("MC.PA").history(period="5d")
        lignes.append(f"INFO  cours Yahoo MC.PA : {len(px)} séances")
    except Exception as e:                           # noqa: BLE001
        lignes.append(f"INFO  Yahoo indisponible depuis ce serveur : {e}")
    from pathlib import Path
    Path(fichier_resultat).write_text("\n".join(lignes) + f"\nCODE {code}\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    import sys
    if "--verifier" in sys.argv:
        sys.exit(verifier(sys.argv[sys.argv.index("--verifier") + 1]))
    chemins.UTILISATEUR.mkdir(parents=True, exist_ok=True)
    fenetre = webview.create_window("Analyse Actions", html=CHARGEMENT, width=1300, height=880,
                                    min_size=(900, 600))
    webview.start(demarrer, fenetre, private_mode=False,
                  storage_path=str(chemins.UTILISATEUR / "navigateur"))
