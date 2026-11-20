---
name: localdrop-testing
description: Stratégie et outillage de tests de LocalDrop (pytest + HTTPX, Hypothesis, pytest-qt, Vitest, tests d'interruption et de reprise, persistance après redémarrage, matrice e2e Windows/Android/iOS Wi-Fi/hotspot, traçabilité FR-xxx, critères d'acceptation). À utiliser pour écrire ou exécuter des tests, ou vérifier qu'une phase est terminée.
---

# Tests LocalDrop

Référence : cahier des charges §16 (tests et critères d'acceptation), §20 (définition du MVP).

## Commandes

```bash
pytest                                   # tout le Python
pytest -m unit                           # unitaires seulement
pytest tests/integration/test_resume.py::test_resume_after_disconnect -x -vv   # un test
pytest -k "FR_026"                       # tests d'une exigence
ruff check . && ruff format --check . && mypy backend/src apps/desktop/src
npm --prefix apps/web test               # Vitest
npm --prefix apps/web run lint && npm --prefix apps/web run typecheck
```
Si ces commandes changent, mettre à jour CLAUDE.md.

## Organisation

- Unitaires (sans I/O, rapides) : à côté des paquets ou dans `backend/tests/unit/`, marqueur `unit`.
- Intégration : `tests/integration/`, marqueur `integration`. App réelle via `create_app(settings)`, base migrée par Alembic dans `tmp_path`, dossiers de stockage dans `tmp_path`.
- e2e manuels : `tests/e2e/` et checklist `docs/testing/e2e-matrix.md`.
- Traçabilité : chaque test lié à une exigence porte l'ID dans son nom (`test_FR_026_resume_sends_only_missing_chunks`).

## Fixtures clés

- `settings` : chemins temporaires, petite taille de bloc (ex. 64 Kio) pour des tests rapides avec plusieurs blocs.
- `app`, `client` : `httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")`.
- `paired_device` : session et appareil approuvé, avec renvoi des en-têtes d'auth.
- `random_file(size)` : octets aléatoires et SHA-256 attendu.
- WebSocket : `starlette.testclient.TestClient` (`websocket_connect`).

## Cas incontournables

Unitaires (§16.1) :
- jetons (génération, hash, comparaison) ;
- toutes les transitions d'état, valides et invalides ;
- calcul des blocs (0 octet, taille exacte multiple, dernier bloc partiel) et des blocs manquants ;
- `sanitize_filename` avec **Hypothesis** (le résultat reste toujours confiné, sans nom réservé ni caractère interdit), Unicode, collisions.

Intégration (§16.2) :
- appairage → approbation → jeton ; refus ; limitation des tentatives ; révocation (401 et WS fermé) ;
- bloc valide, bloc au mauvais hash, bloc hors index, bloc trop grand, bloc renvoyé identique (idempotent) ou différent (409) ;
- **interruption puis reprise** : n'envoyer qu'une partie, interroger `/chunks`, compléter et vérifier qu'aucun bloc validé n'est renvoyé ;
- finalisation : hash global correct et incorrect ; deux `/complete` concurrents donnent un seul succès ; collision de nom sans écrasement ;
- **redémarrage** : recréer l'app sur la même base et retrouver le transfert ;
- réconciliation base ↔ fichiers temporaires ; nettoyage qui ne supprime jamais un fichier final ;
- espace disque insuffisant (simuler `shutil.disk_usage` et `ENOSPC`) ;
- téléchargement sortant avec `Range` ; pas de `completed` sans signal client.

Desktop : `pytest-qt`, démarrage et arrêt propre du serveur embarqué.
Web : uploader (coupure, reprise, resélection du fichier), validation Zod, états vide/chargement/erreur/hors connexion.

## Matrice e2e manuelle (§16.3)

Windows + Android Chrome / iPhone Safari × Wi-Fi domestique / hotspot Android / hotspot iPhone. À chaque fois :
- petit, moyen et gros fichier (> 1 Gio) ;
- noms Unicode et collisions ;
- coupure puis retour réseau ;
- navigateur fermé en cours de transfert ;
- disque plein ;
- mesure du débit réel pour calibrer la taille de bloc (§5.1).

## Définition de « terminé »

Tests verts, ruff, mypy, eslint et tsc propres, et critères du §16.4 couverts par au moins un test (ou une ligne de la matrice e2e) pour la phase concernée.
