---
name: localdrop-database-migrations
description: Persistance SQLite de LocalDrop avec SQLAlchemy 2 et Alembic (modèles typés, pragmas, durabilité, repositories, création et exécution des migrations, sauvegarde avant migration). À utiliser pour infrastructure/database, migrations/ ou toute modification du schéma (sessions, devices, transfers, transfer_chunks).
---

# SQLite, SQLAlchemy 2, Alembic

Référence : cahier des charges §11, §5.2, §17.3.

## Principes

- SQLite = **métadonnées uniquement**, jamais d'octets de fichier (§11).
- Schéma de référence : §11.1–11.4. Contrainte unique `(transfer_id, chunk_index)` sur `transfer_chunks`.
- **Tout changement de schéma passe par Alembic** (§11.5). `Base.metadata.create_all()` est interdit dans le code applicatif.

## Modèles

- Style SQLAlchemy 2 : `DeclarativeBase`, `Mapped[...]`, `mapped_column(...)`, typés mypy.
- UUID stockés en `String(36)`. Datetimes **UTC timezone-aware**, avec un `TypeDecorator` qui force l'UTC en lecture.
- Statuts en `String` validés par des `Enum` Python côté domaine, plus une contrainte `CHECK`.
- Index : `transfers(status)`, `transfers(device_id)`, `transfers(expires_at)`, `devices(session_id)`.
- Les modèles ORM ne sortent pas de `infrastructure/`. Les repositories renvoient des entités de domaine.

## Moteur et pragmas

À appliquer à chaque connexion (`event.listen(engine, "connect", ...)`) :
```
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
PRAGMA synchronous=FULL;   -- un bloc confirmé doit survivre à une coupure (§9.2-5)
```
- Choix par défaut : SQLAlchemy **synchrone**, appelé depuis les routes async via thread (`run_in_threadpool`). C'est plus simple et plus robuste avec SQLite. Tout changement passe par un ADR (ADR-004).
- Transactions courtes. Les changements d'état passent par des updates conditionnels (voir skill `localdrop-transfer-engine`).

## Alembic

- Dossier `migrations/` à la racine. `render_as_batch=True` dans `env.py`, car SQLite gère mal `ALTER TABLE`.
- Créer une migration :
  `alembic revision --autogenerate -m "description courte"`, puis **relire et corriger** le script généré (l'autogenerate rate les `CHECK` et certains index).
- Appliquer : `alembic upgrade head`. Tester aussi `downgrade -1` puis `upgrade head`.
- Au démarrage de l'application : exécution programmatique (`alembic.command.upgrade`), **précédée d'une sauvegarde** de la base via l'API `sqlite3.Connection.backup` vers `database/backups/<horodatage>.db` (§17.3). Garder les N dernières.
- En mode PyInstaller, `script_location` et la configuration sont résolus depuis le bundle, sans dépendre d'`alembic.ini` sur disque (voir skill `localdrop-packaging-windows`).

## Tests

- Les tests d'intégration créent la base via `alembic upgrade head` dans un `tmp_path`, pour être fidèles à la production.
- Test de persistance : créer un transfert et des blocs, recréer l'app (simuler un redémarrage), vérifier que l'état est retrouvé (§16.2).
