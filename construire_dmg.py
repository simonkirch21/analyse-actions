"""
Construit l'application AUTONOME « Analyse Actions » à partager avec d'autres Mac.

Contrairement à creer_app.py (qui utilise le Python de ce Mac), l'application produite ici
embarque Python et toutes les bibliothèques : elle fonctionne sur n'importe quel Mac à puce
Apple (M1 et suivants), sans rien installer.

Étapes :
  1. icône  2. PyInstaller (emballe Python + code + bibliothèques)
  3. signature « ad hoc » (obligatoire pour lancer une app sur Mac à puce Apple)
  4. image disque .dmg avec un raccourci vers Applications et une notice

Lancer :  .venv/bin/python construire_dmg.py
Résultat : distribution/Analyse-Actions.dmg
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import creer_app   # réutilise le dessin de l'icône

PROJET = Path(__file__).parent.resolve()
NOM = "Analyse Actions"
VERSION = "1.0"
TRAVAIL = Path(tempfile.gettempdir()) / "analyse-actions-construction"
SORTIE = PROJET / "distribution"

NOTICE = f"""INSTALLER {NOM.upper()}
{'=' * (11 + len(NOM))}

1. Glisse « {NOM} » sur le dossier « Applications » (dans cette fenêtre).

2. Premier lancement : macOS bloque les applications qui ne viennent pas de l'App Store
   ou d'un développeur enregistré chez Apple. C'est normal, il faut l'autoriser une fois :

   - Ouvre l'application (double-clic). Un message dit qu'elle ne peut pas être ouverte.
     Clique sur « Terminé » (ou « OK »).
   - Va dans Réglages Système > Confidentialité et sécurité, descends en bas de la page :
     à côté de « {NOM} a été bloquée », clique sur « Ouvrir quand même », puis confirme.

   Sur les anciennes versions de macOS, il suffit de faire un clic droit sur l'application,
   puis « Ouvrir ».

   Si le bouton « Ouvrir quand même » n'apparaît pas : ouvre l'application Terminal, colle
   cette ligne puis appuie sur Entrée (elle retire le blocage pour cette application seulement) :

   xattr -dr com.apple.quarantine "/Applications/{NOM}.app"

3. Ensuite, l'application s'ouvre normalement, comme les autres. Le tout premier lancement
   prend jusqu'à une minute (un écran « Préparation » s'affiche), les suivants quelques secondes.

Configuration requise : Mac à puce Apple (M1, M2, M3, M4…), macOS 12 ou plus récent,
connexion internet (les cours et les comptes viennent de Yahoo Finance).

Tes données (portefeuille, rapports) sont enregistrées dans :
~/Library/Application Support/{NOM}

Projet pédagogique : les analyses ne sont pas des conseils d'investissement.
"""


def etape(texte):
    print(f"\n=== {texte} ===")


def main():
    if TRAVAIL.exists():
        shutil.rmtree(TRAVAIL)
    TRAVAIL.mkdir(parents=True)

    etape("1/4 Icône")
    png = TRAVAIL / "icone.png"
    icns = TRAVAIL / "icone.icns"
    creer_app.dessiner_icone(png)
    creer_app.creer_icns(png, icns)

    etape("2/4 PyInstaller (quelques minutes)")
    commande = [
        sys.executable, "-m", "PyInstaller", str(PROJET / "lanceur.py"),
        "--name", NOM, "--windowed", "--noconfirm", "--clean",
        "--icon", str(icns),
        "--osx-bundle-identifier", "local.analyse-actions",
        "--distpath", str(TRAVAIL / "dist"), "--workpath", str(TRAVAIL / "build"),
        "--specpath", str(TRAVAIL),
        "--add-data", f"{PROJET / 'interface'}:interface",
        "--add-data", f"{PROJET / 'data' / 'actions.json'}:data",
        "--collect-all", "webview",        # fichiers JavaScript de pywebview
        "--collect-all", "curl_cffi",      # bibliothèque réseau utilisée par yfinance
        "--collect-all", "xhtml2pdf", "--collect-all", "reportlab",   # modules chargés dynamiquement
        "--collect-all", "openpyxl",
        "--collect-data", "certifi",
        "--exclude-module", "tkinter",
    ]
    subprocess.run(commande, check=True, cwd=PROJET)
    app = TRAVAIL / "dist" / f"{NOM}.app"

    # Version et nom affichés par macOS
    plist = app / "Contents" / "Info.plist"
    for cle, valeur in [("CFBundleShortVersionString", VERSION), ("CFBundleVersion", VERSION),
                        ("CFBundleDisplayName", NOM), ("LSMinimumSystemVersion", "12.0"),
                        ("NSHighResolutionCapable", "true")]:
        type_ = "-bool" if valeur == "true" else "-string"
        subprocess.run(["defaults", "write", str(plist), cle, type_, valeur], check=True)

    etape("3/4 Signature ad hoc")
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
    subprocess.run(["codesign", "--verify", "--deep", str(app)], check=True)

    etape("4/4 Image disque .dmg")
    contenu = TRAVAIL / "dmg"
    contenu.mkdir()
    shutil.copytree(app, contenu / f"{NOM}.app", symlinks=True)
    (contenu / "Applications").symlink_to("/Applications")
    (contenu / "LISEZ-MOI.txt").write_text(NOTICE, encoding="utf-8")
    SORTIE.mkdir(exist_ok=True)
    dmg = SORTIE / "Analyse-Actions.dmg"
    if dmg.exists():
        dmg.unlink()
    subprocess.run(["hdiutil", "create", "-volname", NOM, "-srcfolder", str(contenu),
                    "-ov", "-format", "UDZO", str(dmg)], check=True, stdout=subprocess.DEVNULL)
    taille = dmg.stat().st_size / 1e6
    print(f"\nTerminé : {dmg} ({taille:.0f} Mo)")
    print(f"Application testable directement : {app}")


if __name__ == "__main__":
    main()
