# ADR-004 : SQLite pour les métadonnées, SQLAlchemy synchrone

- Statut : Accepté
- Date : 2026-11-20
- Exigences liées : FR-033, §5.2, §11

## Contexte
Les manifestes de transfert, les sessions et l'historique doivent survivre au redémarrage, sans serveur de base de données séparé.

## Décision
- SQLite dans `%LOCALAPPDATA%\LocalDrop\database`, pour les **métadonnées uniquement**.
- SQLAlchemy 2 en mode **synchrone**, appelé depuis les routes async via thread. Pragmas : `WAL`, `foreign_keys=ON`, `busy_timeout`, `synchronous=FULL` (un bloc confirmé doit survivre à une coupure).
- Schéma géré exclusivement par Alembic (`render_as_batch=True`), avec sauvegarde de la base avant chaque migration au démarrage.

## Options étudiées
- **SQLAlchemy async + aiosqlite** : homogène avec FastAPI, mais un seul écrivain SQLite de toute façon et plus de complexité de test.
- **Fichiers JSON de manifeste** : simple, mais transactions et requêtes d'historique difficiles.

## Conséquences
- Débit d'écriture limité par `synchronous=FULL` : une écriture de ligne par bloc de 4 Mio, ce qui est acceptable. À mesurer.
- Les tests d'intégration migrent la base avec Alembic, pas avec `create_all`.
