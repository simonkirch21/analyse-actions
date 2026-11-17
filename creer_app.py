"""
Crée l'application Mac « Analyse Actions.app » (double-cliquable, avec icône).

Une application Mac est simplement un dossier qui finit par .app et contient :
  Contents/Info.plist        -> fiche d'identité (nom, icône, programme à lancer)
  Contents/MacOS/<programme> -> ce qui est exécuté au double-clic
  Contents/Resources/        -> l'icône (.icns)

Ici, le programme est un petit script qui lance app.py avec le Python du projet.

Lancer :  .venv/bin/python creer_app.py
"""

import platform
import plistlib
import shutil
import subprocess
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np

PROJET = Path(__file__).parent.resolve()
NOM = "Analyse Actions"
# macOS interdit aux applications lancées depuis le Finder de lire le Bureau,
# les Documents et les Téléchargements sans autorisation. On installe donc une
# copie du code dans un dossier non protégé, et l'application dans ~/Applications.
INSTALL = Path.home() / "Library" / "Application Support" / NOM
APP = Path.home() / "Applications" / f"{NOM}.app"
A_COPIER = ["partie1_donnees.py", "partie2_performance.py", "partie3_marche.py",
            "partie4_risque.py", "partie5_technique.py", "partie6_simulation.py",
            "analyse_complete.py", "interpretation.py", "construire_liste.py", "app.py",
            "partie8_analyse_financiere.py", "interpretation_financiere.py",
            "partie9_valorisation.py", "interpretation_valorisation.py", "comparaison.py", "export.py",
            "portefeuille.py", "marche.py", "actualites.py", "chemins.py",
            "simulateur.py", "suivi.py", "base_fondamentale.py", "macro.py", "fictifs.py", "taux.py", "calendrier.py", "options_cotees.py", "dcf_avance.py", "note_analyse.py",
            "requirements.txt",
            "interface", "data"]


def installer_code() -> None:
    """Copie le code, l'interface, la liste d'actions et l'environnement Python."""
    INSTALL.mkdir(parents=True, exist_ok=True)
    for nom in A_COPIER:
        source, cible = PROJET / nom, INSTALL / nom
        if source.is_dir():
            shutil.copytree(source, cible, dirs_exist_ok=True)
        else:
            shutil.copy2(source, cible)
    # Les rapports déjà calculés sont effacés : ils ont été faits avec l'ancien code
    shutil.rmtree(INSTALL / "rapports", ignore_errors=True)
    # L'environnement Python n'est copié que la première fois (il est lourd)
    if not (INSTALL / ".venv").exists():
        shutil.copytree(PROJET / ".venv", INSTALL / ".venv", symlinks=True)
    # Ajoute les bibliothèques qui manqueraient (nouvelles fonctionnalités)
    subprocess.run([str(INSTALL / ".venv" / "bin" / "python"), "-m", "pip", "install", "-q",
                    "-r", str(INSTALL / "requirements.txt")], check=True)
    print(f"Code installé dans : {INSTALL}")


def dessiner_icone(fichier_png: Path) -> None:
    """Icône 1024×1024 : carré arrondi bleu avec une courbe boursière."""
    fig = plt.figure(figsize=(10.24, 10.24), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_alpha(0)
    # Fond : carré aux coins arrondis (format des icônes macOS)
    ax.add_patch(FancyBboxPatch((0.1, 0.1), 0.8, 0.8, boxstyle="round,pad=0,rounding_size=0.18",
                                facecolor="#14305A", edgecolor="none"))
    ax.add_patch(FancyBboxPatch((0.1, 0.1), 0.8, 0.4, boxstyle="round,pad=0,rounding_size=0.18",
                                facecolor="#1B3A6B", edgecolor="none", alpha=0.5))
    # Barres
    for i, h in enumerate([0.14, 0.22, 0.18, 0.30, 0.38]):
        ax.add_patch(FancyBboxPatch((0.22 + i * 0.12, 0.2), 0.07, h,
                                    boxstyle="round,pad=0,rounding_size=0.015",
                                    facecolor="white", alpha=0.25, edgecolor="none"))
    # Courbe
    x = np.linspace(0.2, 0.8, 60)
    rng = np.random.default_rng(3)
    y = 0.35 + 0.38 * (x - 0.2) / 0.6 + np.cumsum(rng.normal(0, 0.012, 60)) * 0.6
    ax.plot(x, y, color="white", lw=26, solid_capstyle="round", solid_joinstyle="round")
    ax.scatter([x[-1]], [y[-1]], s=2200, color="#D4AF6A", zorder=3, edgecolors="white", linewidths=8)
    fig.savefig(fichier_png, transparent=True)
    plt.close(fig)


def creer_icns(png: Path, icns: Path) -> None:
    """Convertit le PNG en .icns (format d'icône macOS) avec les outils du système."""
    with tempfile.TemporaryDirectory() as dossier:
        iconset = Path(dossier) / "icone.iconset"
        iconset.mkdir()
        for taille in [16, 32, 128, 256, 512]:
            for echelle in [1, 2]:
                px = taille * echelle
                suffixe = "" if echelle == 1 else "@2x"
                subprocess.run(["sips", "-z", str(px), str(px), str(png), "--out",
                                str(iconset / f"icon_{taille}x{taille}{suffixe}.png")],
                               check=True, capture_output=True)
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)], check=True)


def creer_application() -> None:
    installer_code()
    if APP.exists():
        shutil.rmtree(APP)
    macos = APP / "Contents" / "MacOS"
    ressources = APP / "Contents" / "Resources"
    macos.mkdir(parents=True)
    ressources.mkdir(parents=True)

    # 1. Le programme lancé au double-clic
    lanceur = macos / "AnalyseActions"
    lanceur.write_text(f"""#!/bin/bash
# Lance l'application avec le Python du projet ; les erreurs vont dans app.log
DOSSIER="{INSTALL}"
cd "$DOSSIER" || exit 1
# arch : force l'architecture du processeur (sinon macOS peut lancer Python en mode Intel)
exec arch -{platform.machine()} "$DOSSIER/.venv/bin/python" "$DOSSIER/app.py" >> "$DOSSIER/app.log" 2>&1
""")
    lanceur.chmod(0o755)

    # 2. L'icône
    with tempfile.TemporaryDirectory() as dossier:
        png = Path(dossier) / "icone.png"
        dessiner_icone(png)
        creer_icns(png, ressources / "icone.icns")

    # 3. La fiche d'identité
    with open(APP / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump({
            "CFBundleName": NOM,
            "CFBundleDisplayName": NOM,
            "CFBundleIdentifier": "local.analyse-actions",
            "CFBundleVersion": "1.0",
            "CFBundleShortVersionString": "1.0",
            "CFBundleExecutable": "AnalyseActions",
            "CFBundleIconFile": "icone",
            "CFBundlePackageType": "APPL",
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
        }, f)

    # Indique au Finder que l'application a changé (rafraîchit l'icône)
    subprocess.run(["touch", str(APP)])
    print(f"Application créée : {APP}")
    print("Après une modification du code, relance ce script pour mettre l'application à jour.")


if __name__ == "__main__":
    creer_application()
