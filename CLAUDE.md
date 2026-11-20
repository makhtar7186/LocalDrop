# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## État du projet

**LocalDrop** sert à partager des fichiers dans les deux sens entre un PC Windows et un smartphone (Android/iOS) sur le réseau local (Wi-Fi ou hotspot). Pas de cloud, pas de compte. Le téléphone scanne un QR Code et utilise une interface web mobile servie par le PC : il n'y a pas d'application native. L'interface est en **français**.

La source de vérité est le cahier des charges [LocalDrop_Cahier_des_charges_Architecture.md](LocalDrop_Cahier_des_charges_Architecture.md). Il contient les exigences FR-xxx, l'API (§10), le modèle de données (§11), la sécurité (§12), la roadmap (§18) et le MVP (§20). Le consulter plutôt que supposer.

**Avancement : phases 0 à 6 terminées.** Les transferts fonctionnent dans les deux sens, en temps réel, avec persistance SQLite et reprise après redémarrage ou rechargement.
- Phases 0 et 1 : socle, ADR-001 à 007, `create_app`, `Settings`, logs avec masquage des secrets, `/health`, format d'erreur unique, en-têtes de sécurité, UI statique.
- Phase 2 : détection réseau, QR Code dans le terminal, sessions, appairage, approbation et révocation via `devtools`, page mobile d'appairage.
- Phase 3 : protocole par blocs complet. On a `POST /transfers`, `PUT …/chunks/{i}` avec `X-Chunk-SHA256` et `POST …/complete` avec le SHA-256 global, ainsi que `GET …/chunks` et `cancel`. Côté mobile : envoi multi-fichiers, 2 simultanés, progression confirmée par le serveur.

- Phase 4 : PC → téléphone via [services/downloads.py](backend/src/localdrop/services/downloads.py). Le fichier source n'est pas copié. Le téléchargement passe par un ticket court en query, avec reprise `Range`, et n'est `completed` que sur accusé `POST …/confirm`. Les opérations d'upload refusent les transferts sortants (`_own_upload`).

- Phase 5 : `/ws`, géré par [infrastructure/realtime/hub.py](backend/src/localdrop/infrastructure/realtime/hub.py) (protocole et codes de fermeture en tête du fichier).
  - Côté serveur : les événements viennent du bus (`services.events`) et ne sont publiés qu'**après** enregistrement de l'état. Un nouvel événement `transfer.*` ou `device.*` doit porter `device_id` dans `data`, sinon aucun téléphone ne le reçoit.
  - Côté web : [realtime.ts](apps/web/src/services/realtime.ts) gère la connexion, et [useRealtimeNudge](apps/web/src/hooks/useRealtimeNudge.ts) déclenche une relecture REST, jamais d'état dérivé du WebSocket seul.
  - Tests : injecter `FakeRealtime` ([tests/fakes.ts](apps/web/tests/fakes.ts)) dans tout rendu d'`<App>`.

- Phase 6 : SQLite et Alembic ([infrastructure/database/](backend/src/localdrop/infrastructure/database/), [migrations/](migrations/)).
  - Sessions, appareils et transferts sont persistés. `TransferService.reconcile()` s'exécute au démarrage (`AppServices.reconcile_report`).
  - `pause`/`resume`, avec 409 `TRANSFER_PAUSED`.
  - Côté web : [pendingUploads.ts](apps/web/src/services/pendingUploads.ts) mémorise les envois, et `uploadFile(file, deps, { resume })` les reprend.

Prochaine étape : phase 7 (historique et nettoyage : tâche de maintenance, expiration des temporaires, FR-034/FR-035). Les décisions par phase sont dans [docs/decisions/README.md](docs/decisions/README.md). Les commandes marquées *(phase N)* n'existent pas encore.

Transferts :
- [services/transfers.py](backend/src/localdrop/services/transfers.py) : service **synchrone**, appelé depuis les routes via `run_in_threadpool`. Un verrou par transfert protège les blocs et `complete`.
- [domain/transfers/](backend/src/localdrop/domain/transfers/) : machine à états (table identique au §8.3, testée exhaustivement) et `sanitize_filename` (testé avec Hypothesis).
- [infrastructure/storage/files.py](backend/src/localdrop/infrastructure/storage/files.py) : temporaires `<id>.part` dans `<réception>/.localdrop-tmp`, publication sans écrasement.
- Côté web : [uploader.ts](apps/web/src/services/uploader.ts) hache avec `hash-wasm`, jamais `crypto.subtle`. [uploadQueue.ts](apps/web/src/services/uploadQueue.ts) gère la file hors de React, via `useSyncExternalStore`.
- Les types Zod de [schemas.ts](apps/web/src/services/schemas.ts) doivent suivre les schémas Pydantic. Tout changement de forme de l'API se reporte des deux côtés.

Points d'ancrage du backend :
- [main.py](backend/src/localdrop/main.py) : fabrique `create_app(settings, services)`, cycle de vie (surveillance réseau), middlewares. `_WebUIMount` ignore `/api` et `/ws` pour ne pas masquer les 404/405 JSON.
- [services/container.py](backend/src/localdrop/services/container.py) : `build_services()` assemble `AppServices` (bus d'événements, `PairingService`, `NetworkMonitor`, jeton admin). Il est partagé par l'API (`app.state.services`) et par le futur desktop.
- [api/deps.py](backend/src/localdrop/api/deps.py) :
  - `DeviceDep` : appareil **approuvé**, à utiliser sur toutes les routes de transfert ;
  - `AdminDep` : loopback + en-tête `X-LocalDrop-Admin`.
- [api/middleware.py](backend/src/localdrop/api/middleware.py) : `PrivateNetworkOnlyMiddleware` refuse les clients hors réseau privé.
- [core/config.py](backend/src/localdrop/core/config.py) : tous les paramètres, surchargeables par `LOCALDROP_*`. [core/paths.py](backend/src/localdrop/core/paths.py) est le seul endroit qui calcule des chemins.
- [api/errors.py](backend/src/localdrop/api/errors.py) : mapping des erreurs. Lever des sous-classes de `LocalDropError` ([core/errors.py](backend/src/localdrop/core/errors.py)) avec un `code` explicite, jamais `HTTPException` dans les services.
- Persistance derrière les ports `SessionRepository` / `TransferRepository`, avec deux implémentations : mémoire et SQLite (`Settings.persistence`).
  - Tout nouveau champ va dans **trois** endroits : domaine, `models.py` et une **nouvelle migration**. Le test `test_migrated_schema_matches_orm_models` échoue sinon.
  - Les changements d'état concurrents passent par `save(..., expected_status=...)` (UPDATE conditionnel).
  - Les routes qui touchent la base sont des `def` (thread), jamais des `async def` qui appellent un service directement.
- `build_services()` ouvre un moteur SQLite : appeler `services.close()` à l'arrêt (déjà fait par `__main__` et les fixtures).

Tests :
- Fixtures partagées dans [tests/conftest.py](tests/conftest.py) :
  - `client` = téléphone en `192.168.1.50` ;
  - `admin` = loopback + jeton ;
  - `make_client(ip, headers)` ;
  - adresse réseau simulée `192.168.1.14`.
- Ces fixtures utilisent `persistence="memory"`. Pour SQLite et les redémarrages, voir [test_persistence.py](tests/integration/test_persistence.py) et [test_resume_api.py](tests/integration/test_resume_api.py).
- Le client par défaut de `TestClient` (`testclient`) est **refusé** par le middleware : toujours passer `client=(ip, port)`.
- [test_architecture.py](backend/tests/unit/test_architecture.py) échoue si `domain/` importe un framework ou l'infrastructure.

Web : `main.tsx` consomme le fragment `#/join?s=&k=` **avant** le rendu React, ce qui efface le secret de l'URL. `usePairing` garantit un seul `join`, même sous StrictMode, puisque le secret est à usage unique.

## Skills du projet (`.claude/skills/`)

Charger le skill correspondant avant de toucher au module :

| Skill | Périmètre |
|---|---|
| `localdrop-phase-delivery` | Démarrer ou réaliser une phase de la roadmap ; liste des skills à charger par phase |
| `localdrop-backend-api` | Couches FastAPI, routes `/api/v1`, auth, erreurs, streaming |
| `localdrop-transfer-engine` | Protocole par blocs, machine à états, finalisation, reprise, sortants, `/ws` |
| `localdrop-secure-storage` | Noms de fichiers, chemins, temporaires, publication sans écrasement, nettoyage |
| `localdrop-sessions-pairing` | Secrets, QR Code, appairage, approbation, révocation |
| `localdrop-network` | Interfaces, IP privées, bind, changement d'IP, pare-feu, isolation Wi-Fi |
| `localdrop-database-migrations` | SQLAlchemy 2, pragmas SQLite, Alembic, sauvegarde |
| `localdrop-mobile-web` | React/TS/Vite/Tailwind/Zod, uploader, limites iOS et HTTP |
| `localdrop-desktop-pyside6` | Serveur embarqué en thread, pont Qt, écrans, arrêt propre |
| `localdrop-testing` | pytest/HTTPX/Hypothesis/pytest-qt/Vitest, matrice e2e, critères d'acceptation |
| `localdrop-packaging-windows` | PyInstaller, chemins en mode gelé, test de fumée |
| `localdrop-adr` | Modèle d'ADR, ADR-001 à 007, décisions ouvertes |

## Commandes

Le `python` par défaut de la machine est en **3.10** : toujours passer par `py -3.12` ou par le venv (`.venv/Scripts/...`).

```bash
# Python : un seul pyproject.toml à la racine (paquets localdrop + localdrop_desktop, installés en éditable)
py -3.12 -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/pytest                                         # tous les tests Python (backend/tests, apps/desktop/tests, tests/)
.venv/Scripts/pytest backend/tests/unit/test_package.py::test_package_exposes_version -x -vv
.venv/Scripts/pytest -m unit                                 # marqueurs : unit, integration, e2e (--strict-markers)
.venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .
.venv/Scripts/mypy                                           # strict, paquets configurés dans pyproject.toml
.venv/Scripts/python -m localdrop                            # serveur : lie 127.0.0.1 + IP privées, affiche le QR Code
.venv/Scripts/python -m localdrop.devtools qr|devices|transfers|approve <id>|reject <id>|revoke [<id>]   # admin en dev
.venv/Scripts/python -m localdrop.devtools send <fichier> [--device <id>] | cancel <transfer_id>   # PC -> téléphone
.venv/Scripts/python -m localdrop.devtools watch             # événements temps réel (WebSocket admin)
# LOCALDROP_LAN_ENABLED=false : loopback seul (évite la boîte de dialogue du pare-feu lors des tests locaux)
.venv/Scripts/uvicorn localdrop.main:create_app --factory --reload --host 127.0.0.1 --port 8765   # dev avec rechargement
# Variables utiles : LOCALDROP_PORT, LOCALDROP_DATA_DIR, LOCALDROP_DEBUG=true (active /api/docs)
.venv/Scripts/python -m localdrop_desktop                    # (phase 8)
.venv/Scripts/alembic revision --autogenerate -m "..."       # base : LOCALDROP_DATA_DIR ; relire le script (CHECK, index)
.venv/Scripts/alembic upgrade head && .venv/Scripts/alembic check   # « No new upgrade operations » attendu

# Web mobile (apps/web : Vite 8, React 19, TS 6, Tailwind 4, Zod 4, Vitest 5, ESLint 10 flat config)
npm --prefix apps/web run dev | build | lint | typecheck
npm --prefix apps/web test                                   # un fichier : npm --prefix apps/web test -- tests/App.test.tsx

# Packaging (phase 11)
pyinstaller localdrop.spec --noconfirm --clean
```
Les tests Python sont en `--import-mode=importlib` : **pas de `__init__.py`** dans les dossiers de tests. Le proxy Vite redirige `/api` et `/ws` vers `127.0.0.1:8765`. Ruff ignore `.claude/` et `docs/`.
Pour tester avec un vrai téléphone, servir le build web depuis FastAPI lié à l'IP privée du PC (pas `127.0.0.1`).

## Architecture

Monolithe modulaire : un seul processus Python héberge l'API REST, le WebSocket, le moteur de transfert, les sessions, SQLite et les fichiers web compilés. PySide6 pilote le cycle de vie du serveur, qui tourne dans un thread de travail et jamais dans la boucle Qt.

```
apps/desktop (PySide6) ──en processus──► backend/src/localdrop
apps/web (React, servi en statique) ──HTTP/WS LAN──► api/v1 → services → domain
                                                     infrastructure/{database,storage,network,realtime}
```
`domain/` est du Python pur, sans FastAPI, SQLAlchemy ni I/O. Les routers restent minces.

## Invariants transverses (ne jamais violer)

- **Un bloc n'est confirmé qu'après écriture, `fsync`, hash vérifié et commit en base.** Le renvoi d'un bloc identique est idempotent ; un hash différent sur un index validé donne 409.
- **Machine à états contrôlée** (§8.3). Les changements d'état passent par un update conditionnel, ce qui protège `/complete` des appels concurrents. `completed` est immuable.
- **Un fichier n'est publié qu'après vérification de la taille et du SHA-256 global**, par déplacement atomique sur le même volume et **sans écrasement** (`os.rename` + `nom (n).ext`, jamais `os.replace`).
- **Le nom client n'est jamais un chemin.** Il est assaini (noms réservés Windows inclus), puis le chemin est construit par le serveur et confiné par `resolve()` + `is_relative_to`.
- **Le WebSocket n'est pas la source de vérité.** Les événements sont publiés après commit, et le client resynchronise par REST.
- **Aucun téléchargement sortant n'est marqué `completed` sans signal fiable du client.**
- **Secrets** : `secrets.token_urlsafe`, hash seul en base, jamais en log. Le secret du QR Code passe dans le **fragment `#`** de l'URL. Approbation sur le PC obligatoire. Le serveur est lié aux IP privées uniquement.
- **SQLite = métadonnées seulement**, schéma modifié uniquement via Alembic.
- **Jamais de fichier entier en mémoire**, côté serveur comme côté navigateur.
- **Données d'exécution** dans `%LOCALAPPDATA%\LocalDrop`, fichiers reçus dans `%USERPROFILE%\Downloads\LocalDrop` (configurable). Rien de tout cela dans le dépôt.

## Pièges connus

- La page mobile est en HTTP sur une IP LAN, donc **pas de secure context** : `crypto.subtle`, `crypto.randomUUID`, Clipboard API, Service Worker et Wake Lock sont indisponibles. Hacher avec `hash-wasm`.
- iOS Safari suspend les pages en arrière-plan : garder la page active, et ne pas annoncer la reprise des téléchargements iOS sans validation e2e.
- Un lien `<a download>` ne peut pas envoyer `Authorization` : il faut un ticket de téléchargement court (à figer par ADR).
- Pare-feu Windows et profil réseau « Public », isolation des clients sur certains points d'accès : prévoir un diagnostic côté desktop.

## Livraison

Suivre la roadmap §18 phase par phase (skill `localdrop-phase-delivery`). Chaque phase doit être exécutable et testée. Le premier jalon : FastAPI démarré, QR Code affiché, page ouverte sur un téléphone, petit fichier reçu sur le PC. Toute décision structurante fait l'objet d'un ADR dans `docs/decisions/`.
