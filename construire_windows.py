"""
Construit la version Windows de l'application : un dossier « Analyse Actions » avec
« Analyse Actions.exe », compressé en distribution/Analyse-Actions-Windows.zip.

PyInstaller ne fabrique une application que pour le système sur lequel il tourne : ce script
s'exécute donc sur une machine Windows, en pratique celle de GitHub Actions
(.github/workflows/windows.yml), à chaque nouvelle version.

Lancer (sous Windows) :  python construire_windows.py
"""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PROJET = Path(__file__).parent
NOM = "Analyse Actions"
TRAVAIL = PROJET / "build_windows"
SORTIE = PROJET / "distribution" / "Analyse-Actions-Windows.zip"
SEP = os.pathsep          # séparateur de --add-data : « ; » sous Windows


def etape(t):
    print(f"\n=== {t} ===", flush=True)


def icone() -> Path:
    """Icône .ico à partir du dessin de l'icône Mac (plusieurs tailles dans un seul fichier)."""
    import creer_app
    from PIL import Image
    png, ico = TRAVAIL / "icone.png", TRAVAIL / "icone.ico"
    creer_app.dessiner_icone(png)
    Image.open(png).save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return ico


def main():
    if TRAVAIL.exists():
        shutil.rmtree(TRAVAIL)
    TRAVAIL.mkdir(parents=True)
    etape("1/3 Icône")
    ico = icone()

    etape("2/3 PyInstaller")
    commande = [
        sys.executable, "-m", "PyInstaller", str(PROJET / "lanceur.py"),
        "--name", NOM, "--windowed", "--noconfirm", "--clean", "--icon", str(ico),
        "--distpath", str(TRAVAIL / "dist"), "--workpath", str(TRAVAIL / "build"), "--specpath", str(TRAVAIL),
        "--add-data", f"{PROJET / 'interface'}{SEP}interface",
        "--add-data", f"{PROJET / 'data' / 'actions.json'}{SEP}data",
        "--collect-all", "webview",        # fichiers JavaScript et DLL de pywebview (WebView2)
        "--collect-all", "clr_loader", "--collect-all", "pythonnet",   # pont .NET utilisé par pywebview sous Windows
        "--collect-all", "curl_cffi",      # bibliothèque réseau utilisée par yfinance
        "--collect-all", "xhtml2pdf", "--collect-all", "reportlab", "--collect-all", "openpyxl",
        "--collect-data", "certifi", "--collect-data", "matplotlib",
        "--exclude-module", "tkinter",
    ]
    subprocess.run(commande, check=True, cwd=PROJET)
    dossier = TRAVAIL / "dist" / NOM

    etape("3/3 Archive zip")
    SORTIE.parent.mkdir(exist_ok=True)
    if SORTIE.exists():
        SORTIE.unlink()
    (dossier / "LISEZ-MOI.txt").write_text(LISEZ_MOI, encoding="utf-8")
    with zipfile.ZipFile(SORTIE, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in dossier.rglob("*"):
            z.write(f, Path(NOM) / f.relative_to(dossier))
    print(f"Terminé : {SORTIE} ({SORTIE.stat().st_size / 1e6:.0f} Mo)")


LISEZ_MOI = """ANALYSE ACTIONS pour Windows
============================

1. Extrayez tout le contenu du fichier zip (clic droit > Extraire tout…), par exemple dans « Documents ».
2. Ouvrez le dossier « Analyse Actions » et double-cliquez sur « Analyse Actions.exe ».
3. Windows affiche peut-être « Windows a protégé votre ordinateur » (l'application n'est pas signée
   par un éditeur payant) : cliquez sur « Informations complémentaires », puis « Exécuter quand même ».
4. Le premier lancement peut prendre jusqu'à une minute. Ensuite, quelques secondes.

Astuce : clic droit sur « Analyse Actions.exe » > Afficher d'autres options > Envoyer vers > Bureau
(créer un raccourci) pour la retrouver facilement.

L'application utilise Microsoft Edge WebView2, présent sur Windows 10 et 11. S'il manquait, Windows
propose de l'installer gratuitement.

Outil pédagogique : ce n'est pas un conseil en investissement.
"""

if __name__ == "__main__":
    main()
