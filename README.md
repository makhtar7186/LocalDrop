# LocalDrop

Partage de fichiers entre un PC Windows et un smartphone (Android / iOS) sur le réseau local, sans cloud ni compte.
**Scanner, connecter, transférer.**

Spécification : [LocalDrop_Cahier_des_charges_Architecture.md](LocalDrop_Cahier_des_charges_Architecture.md)
Décisions d'architecture : [docs/decisions/](docs/decisions/)

## Utiliser LocalDrop

Décompressez l'archive `LocalDrop-<version>-windows-x64.zip`, lancez `LocalDrop.exe` (autorisez les **réseaux privés** dans la fenêtre du pare-feu), puis scannez le QR Code avec le téléphone. Aucune installation n'est nécessaire sur le téléphone.

Guide complet, avec dépannage réseau : [docs/guide-utilisateur.md](docs/guide-utilisateur.md).

## Développement

### Prérequis

- Windows 10/11
- Python 3.12
- Node.js 20+ et npm

### Installation

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt

npm --prefix apps/web install
```

### Qualité et tests

```powershell
ruff check . ; ruff format --check . ; mypy
pytest

npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web test
npm --prefix apps/web run build
```

Bout en bout sur vrais sockets et en vrai navigateur (Chrome ou Edge sans interface) : `pytest tests/e2e`. Débit par taille de bloc : `python -m localdrop.bench`.

### Lancer depuis les sources

```powershell
python -m localdrop_desktop        # application Windows
python -m localdrop                # serveur seul, QR Code dans le terminal
```

### Construire l'exécutable

```powershell
python scriptsuild_windows.py    # web, tests, PyInstaller, autotest, test de fumée, archive zip
```

Détails et liste de contrôle avant publication : [docs/packaging.md](docs/packaging.md).

### Structure

```
backend/src/localdrop/        serveur FastAPI (api, services, domain, infrastructure)
apps/desktop/src/localdrop_desktop/   application Windows PySide6
apps/web/                     interface mobile React + TypeScript
migrations/                   migrations Alembic
packaging/, localdrop.spec    exécutable Windows (PyInstaller), icône
scripts/                      construction et test de fumée de l'exécutable
tests/                        tests d'intégration et e2e
docs/                         guide utilisateur, ADR, sécurité, tests, packaging
```

## Avertissement

Le MVP communique en HTTP sur le réseau local : utilisez un réseau de confiance et évitez les Wi-Fi publics.
