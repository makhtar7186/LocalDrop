# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## État du projet

**LocalDrop** sert à partager des fichiers dans les deux sens entre un PC Windows et un smartphone (Android/iOS) sur le réseau local (Wi-Fi ou hotspot). Pas de cloud, pas de compte. Le téléphone scanne un QR Code et utilise une interface web mobile servie par le PC : il n'y a pas d'application native. L'interface est en **français**.

La source de vérité est le cahier des charges [LocalDrop_Cahier_des_charges_Architecture.md](LocalDrop_Cahier_des_charges_Architecture.md). Il contient les exigences FR-xxx, l'API (§10), le modèle de données (§11), la sécurité (§12), la roadmap (§18) et le MVP (§20). Le consulter plutôt que supposer.

**Avancement : phases 0 à 10 terminées (version candidate).** L'application Windows (PySide6) et l'interface mobile complète sont disponibles, auditées ([audit-phase-10.md](docs/security/audit-phase-10.md)) et testées de bout en bout sur vrais sockets et en vrai navigateur. Les transferts fonctionnent dans les deux sens, en temps réel, avec persistance SQLite, reprise, historique, maintenance et adaptation automatique aux changements de réseau.
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

- Phase 7 :
  - [services/maintenance.py](backend/src/localdrop/services/maintenance.py) (FR-035) ;
  - historique `GET /history` et `/admin/history` (FR-034), ainsi que l'écran Historique mobile ;
  - [server.py](backend/src/localdrop/server.py) : `LocalServer` lie les sockets, **redémarre tout seul** quand une adresse apparaît et affiche l'aide de connexion. Le desktop doit le réutiliser (`run()` bloquant dans un thread, `stop()`, `started`).

- Phase 8 : [apps/desktop/](apps/desktop/src/localdrop_desktop/).
  - `AppController` est la façade en processus. `ServerWorker` fait tourner `LocalServer` dans un thread. `EventBridge` transforme le bus en signaux Qt. `TaskRunner` gère les accès base hors du thread GUI.
  - Ne jamais toucher un widget depuis un autre thread : passer par un signal.
  - Les paramètres utilisateur sont persistés par `load_settings()`/`save_user_settings()` ([core/config.py](backend/src/localdrop/core/config.py)).

- Phase 9 : écrans mobiles du §14.3. [App.tsx](apps/web/src/app/App.tsx) et [useScreen.ts](apps/web/src/app/useScreen.ts) gèrent le routage par hash, [BottomNav.tsx](apps/web/src/components/BottomNav.tsx) la navigation. L'annulation d'un envoi passe par `UploadQueue.cancel` et un `AbortSignal`.
  - Les écrans restent **montés et masqués** : ne jamais conditionner `SendPanel` au routage, sinon les envois en cours sont perdus.
  - Les schémas utilisent **`zod/mini`** (`import * as z from "zod/mini"`). Les modificateurs sont des fonctions : `z.nullable(x)`, `.check(z.minLength(1))`, `z.int().check(z.nonnegative())`.
  - Les tests qui interagissent avec un écran doivent d'abord y **naviguer** : les requêtes par rôle ignorent les éléments masqués.

- Phase 10 : audit de sécurité, tests de bout en bout, optimisation.
  - **`Host` limité aux IP et à `localhost`** (`AllowedHostMiddleware`, anti DNS rebinding). Un `TestClient` doit viser une IP : `base_url=SERVER_URL` dans `conftest.py`. Pour le WebSocket, passer une URL absolue `ws://192.168.1.14:8765/ws`, car Starlette impose sinon `ws://testserver`.
  - CSP sur les pages web (`WEB_UI_CSP`) : pas de script en ligne dans `index.html`.
  - Toute donnée venant du téléphone affichée dans un `QLabel` en texte enrichi passe par `html.escape`.
  - [bench.py](backend/src/localdrop/bench.py) fournit `PhoneClient` (client « téléphone » en bibliothèque standard, keep-alive) et `RunningServer` (vrai serveur dans un thread), réutilisés par `tests/e2e/`.
  - FastAPI 0.165 n'aplatit plus les routeurs inclus (`app.routes` contient des `_IncludedRouter`) : faire l'inventaire des routes avec `app.openapi()["paths"]`.

Prochaine étape : phase 11 (PyInstaller, documentation utilisateur), puis la matrice e2e manuelle avec de vrais téléphones ([e2e-matrix.md](docs/testing/e2e-matrix.md)). Les décisions par phase sont dans [docs/decisions/README.md](docs/decisions/README.md). Les commandes marquées *(phase N)* n'existent pas encore.

Transferts :
- [services/transfers.py](backend/src/localdrop/services/transfers.py) : service **synchrone**, appelé depuis les routes via `run_in_threadpool`. Un verrou par transfert protège les blocs et `complete`.
- [domain/transfers/](backend/src/localdrop/domain/transfers/) : machine à états (table identique au §8.3, testée exhaustivement) et `sanitize_filename` (testé avec Hypothesis).
- [infrastructure/storage/files.py](backend/src/localdrop/infrastructure/storage/files.py) : temporaires `<id>.part` dans `<réception>/.localdrop-tmp`, publication sans écrasement. Les temporaires restent **ouverts** entre deux blocs (cache borné : fermer un fichier modifié déclenche l'antivirus Windows). Appeler `close_temp(id)` avant tout renommage ou suppression ; `publish` et `delete_temp` le font déjà. Une fixture qui crée un `FileStorage` doit appeler `close_all()`.
- Un bloc s'enregistre par `TransferRepository.record_chunk` : bloc et progression dans une seule transaction.
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
.venv/Scripts/python -m localdrop.devtools history [--q mot] [--status completed] [--device id]
# LOCALDROP_LAN_ENABLED=false : loopback seul (évite la boîte de dialogue du pare-feu lors des tests locaux)
.venv/Scripts/uvicorn localdrop.main:create_app --factory --reload --host 127.0.0.1 --port 8765   # dev avec rechargement
# Variables utiles : LOCALDROP_PORT, LOCALDROP_DATA_DIR, LOCALDROP_DEBUG=true (active /api/docs)
.venv/Scripts/python -m localdrop_desktop                    # application Windows (QR Code, approbations, glisser-déposer)
.venv/Scripts/pytest apps/desktop/tests --tb=native           # tests Qt hors écran (QT_QPA_PLATFORM=offscreen via conftest)
.venv/Scripts/alembic revision --autogenerate -m "..."       # base : LOCALDROP_DATA_DIR ; relire le script (CHECK, index)
.venv/Scripts/alembic upgrade head && .venv/Scripts/alembic check   # « No new upgrade operations » attendu

# Web mobile (apps/web : Vite 8, React 19, TS 6, Tailwind 4, Zod 4, Vitest 5, ESLint 10 flat config)
npm --prefix apps/web run dev | build | lint | typecheck
npm --prefix apps/web test                                   # un fichier : npm --prefix apps/web test -- tests/App.test.tsx

# Bout en bout et débit (phase 10)
.venv/Scripts/pytest tests/e2e                               # vrais sockets + vrai navigateur (Chrome/Edge sans interface, page compilée requise)
LOCALDROP_SCREENSHOTS=captures .venv/Scripts/pytest tests/e2e/test_browser.py   # captures d'écran au format téléphone
.venv/Scripts/python -m localdrop.bench [--size-mib 128 --repeat 3 --chunks-mib 1 4 8]   # débit par taille de bloc (loopback)

# Packaging (phase 11)
pyinstaller localdrop.spec --noconfirm --clean
```
Les tests Python sont en `--import-mode=importlib` : **pas de `__init__.py`** dans les dossiers de tests.
Avec PySide6 chargé, pytest peut mettre plus de 30 s à **formater** un échec (`inspect.getmodule` parcourt tous les modules), ce qui ressemble à un blocage. Utiliser `--tb=native`. Dans les tests desktop, préférer `urllib` à `httpx` : sa première initialisation (TLS) est très lente sur cette machine. Le proxy Vite redirige `/api` et `/ws` vers `127.0.0.1:8765`. Ruff ignore `.claude/` et `docs/`.
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
- Un lien `<a download>` ne peut pas envoyer `Authorization` : on utilise un ticket de téléchargement court.
- Mesurer avant d'optimiser : sous Windows, l'antivirus et les `fsync` dominent. La première mesure d'une série peut être deux fois plus lente (fichier en cours d'analyse).
- Pare-feu Windows et profil réseau « Public », isolation des clients sur certains points d'accès : prévoir un diagnostic côté desktop.

## Livraison

Suivre la roadmap §18 phase par phase (skill `localdrop-phase-delivery`). Chaque phase doit être exécutable et testée. Le premier jalon : FastAPI démarré, QR Code affiché, page ouverte sur un téléphone, petit fichier reçu sur le PC. Toute décision structurante fait l'objet d'un ADR dans `docs/decisions/`.
