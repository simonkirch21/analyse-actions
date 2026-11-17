"""
CHEMINS — Où se trouvent les fichiers de l'application et ceux de l'utilisateur
==============================================================================

Deux situations :
  - en développement (on lance les .py du projet) : tout est dans le dossier du projet ;
  - dans l'application autonome (construite avec PyInstaller) : les fichiers de l'application
    (interface, liste d'actions) sont DANS l'app, qui est en lecture seule ; les données de
    l'utilisateur (portefeuille, rapports) vont dans ~/Library/Application Support/Analyse Actions.
"""

import sys
from pathlib import Path

APPLICATION_AUTONOME = getattr(sys, "frozen", False)

if APPLICATION_AUTONOME:
    RESSOURCES = Path(sys._MEIPASS)        # dossier interne de l'app (PyInstaller)
    DONNEES = Path.home() / "Library" / "Application Support" / "Analyse Actions"
else:
    RESSOURCES = Path(__file__).parent
    DONNEES = Path(__file__).parent

RAPPORTS = DONNEES / "rapports"
UTILISATEUR = DONNEES / "utilisateur"
INTERFACE = RESSOURCES / "interface"


def liste_actions() -> Path:
    """Liste des actions : la version mise à jour par l'utilisateur si elle existe, sinon celle de l'app."""
    maj = DONNEES / "data" / "actions.json"
    return maj if maj.exists() else RESSOURCES / "data" / "actions.json"
