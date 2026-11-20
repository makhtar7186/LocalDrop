# LocalDrop

Partage de fichiers entre un PC Windows et un smartphone (Android / iOS) sur le réseau local, sans cloud ni compte.
**Scanner, connecter, transférer.**

Spécification : [LocalDrop_Cahier_des_charges_Architecture.md](LocalDrop_Cahier_des_charges_Architecture.md)
Décisions d'architecture : [docs/decisions/](docs/decisions/)

## Prérequis

- Windows 10/11
- Python 3.12
- Node.js 20+ et npm

## Installation (développement)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt

npm --prefix apps/web install
```

## Qualité et tests

```powershell
ruff check . ; ruff format --check . ; mypy
pytest

npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web test
npm --prefix apps/web run build
```

## Structure

```
backend/src/localdrop/        serveur FastAPI (api, services, domain, infrastructure)
apps/desktop/src/localdrop_desktop/   application Windows PySide6
apps/web/                     interface mobile React + TypeScript
migrations/                   migrations Alembic
tests/                        tests d'intégration et e2e
docs/                         architecture, API, ADR
```

## Avertissement

Le MVP communique en HTTP sur le réseau local : utilisez un réseau de confiance et évitez les Wi-Fi publics.
