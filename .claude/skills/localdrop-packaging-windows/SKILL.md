---
name: localdrop-packaging-windows
description: Packaging Windows de LocalDrop avec PyInstaller (résolution des chemins en mode gelé, inclusion du build web, des migrations Alembic et des ressources Qt, données utilisateur dans %LOCALAPPDATA%, logs rotatifs, pare-feu, test de fumée). À utiliser pour la phase 11, le fichier .spec, ou un bug qui n'apparaît que dans l'exécutable.
---

# Packaging Windows (PyInstaller)

Référence : cahier des charges §17. Le skill global `anthropic-skills:packaging-pyinstaller-windows` couvre l'outillage générique (Inno Setup, signature…). Ce skill couvre ce qui est propre à LocalDrop.

## Résolution des chemins

Un seul module `core/paths.py` :
```python
import os, sys
from pathlib import Path

def resource_root() -> Path:
    # ressources embarquées (lecture seule)
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[N]))

def user_data_root() -> Path:
    # données d'exécution (écriture)
    return Path(os.environ["LOCALAPPDATA"]) / "LocalDrop"
```
- **Aucun** autre code ne calcule de chemin à partir de `__file__` ou du répertoire courant.
- Ressources embarquées : `apps/web/dist` (UI mobile), `migrations/` (scripts Alembic), ressources Qt et icônes.
- Données d'exécution : `%LOCALAPPDATA%\LocalDrop\{database,logs,state}`. Fichiers reçus : dossier configuré (par défaut `Downloads\LocalDrop`).

## Fichier .spec

- `--windowed` (pas de console). Mode **onedir** de préférence : démarrage plus rapide et moins de faux positifs antivirus que onefile.
- `datas` : build web, migrations, ressources.
- `hiddenimports` : vérifier ce dont Uvicorn a besoin (`uvicorn.protocols.*`, `uvicorn.lifespan.on`, `uvicorn.loops.auto`), ainsi que les dialectes SQLAlchemy SQLite et les modules Alembic chargés dynamiquement.
- Alembic configuré **par code** (`Config()` + `set_main_option("script_location", str(resource_root()/"migrations"))`), sans dépendre d'un `alembic.ini` externe.
- Pas d'access log Uvicorn vers stdout (pas de console). Logs rotatifs via `logging.handlers.RotatingFileHandler`, avec durée de conservation limitée (§17.2).

## Procédure de build

1. `npm --prefix apps/web ci && npm --prefix apps/web run build`
2. Suite complète de tests et de qualité (skill `localdrop-testing`).
3. `pyinstaller localdrop.spec --noconfirm --clean`
4. **Test de fumée sur l'exécutable**, idéalement sur une machine ou VM Windows propre :
   - lancement, QR Code affiché, page mobile servie ;
   - appairage, envoi d'un petit fichier, réception d'un fichier ;
   - fermeture propre, sans processus résiduel ;
   - relance : la base est migrée et l'historique retrouvé.

## Spécificités

- La boîte de dialogue du pare-feu Windows est liée au **chemin de l'exécutable**. Changer d'emplacement la redéclenche.
- Mise à jour (§17.3) : remplacement contrôlé de l'application. La migration au démarrage est précédée d'une sauvegarde de la base (skill `localdrop-database-migrations`).
- Pas de dépendance à un Python installé, ni à Node à l'exécution.
