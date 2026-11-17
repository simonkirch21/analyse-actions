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
       font: 15px -apple-system, BlinkMacSystemFont, sans-serif; background: #0A0F1C; color: #ECE8DF; }
@media (prefers-color-scheme: dark) { body { background: #0A0F1C; color: #ECE8DF; } p { color: #8D94A5; }
  .roue { border-color: #D4AF6A33 !important; border-top-color: #D4AF6A !important; } }
h1 { font-family: "New York", ui-serif, Georgia, serif; font-weight: 600; }
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


if __name__ == "__main__":
    chemins.UTILISATEUR.mkdir(parents=True, exist_ok=True)
    fenetre = webview.create_window("Analyse Actions", html=CHARGEMENT, width=1300, height=880,
                                    min_size=(900, 600))
    webview.start(demarrer, fenetre, private_mode=False,
                  storage_path=str(chemins.UTILISATEUR / "navigateur"))
