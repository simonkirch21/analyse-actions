"""
CHEMINS — Où se trouvent les fichiers de l'application et ceux de l'utilisateur
==============================================================================

Deux situations :
  - en développement (on lance les .py du projet) : tout est dans le dossier du projet ;
  - dans l'application autonome (construite avec PyInstaller) : les fichiers de l'application
    (interface, liste d'actions) sont DANS l'app, qui est en lecture seule ; les données de
    l'utilisateur (portefeuille, rapports) vont dans le dossier prévu par le système :
      Mac     : ~/Library/Application Support/Analyse Actions
      Windows : %APPDATA%\\Analyse Actions
      Linux   : ~/.local/share/Analyse Actions
"""

import os
import sys
from pathlib import Path

APPLICATION_AUTONOME = getattr(sys, "frozen", False)
WINDOWS = sys.platform.startswith("win")
MAC = sys.platform == "darwin"


def _dossier_donnees() -> Path:
    if MAC:
        return Path.home() / "Library" / "Application Support" / "Analyse Actions"
    if WINDOWS:
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "Analyse Actions"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "Analyse Actions"


if APPLICATION_AUTONOME:
    RESSOURCES = Path(sys._MEIPASS)        # dossier interne de l'app (PyInstaller)
    DONNEES = _dossier_donnees()
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
