# ADR-001 : Monolithe modulaire plutôt que microservices

- Statut : Accepté
- Date : 2026-11-20
- Exigences liées : §1.2-4, §5.4, §6.1

## Contexte
LocalDrop est un outil personnel exécuté sur un seul PC Windows. Il doit être simple à installer, à démarrer et à arrêter, tout en restant maintenable.

## Décision
Un seul processus Python héberge l'API REST, le WebSocket, le moteur de transfert, les sessions, l'accès SQLite et les fichiers web compilés. Les frontières internes sont des paquets : `api/v1 → services → domain`, plus `infrastructure/`. `domain/` ne dépend d'aucun framework ni d'aucune I/O.

## Options étudiées
- **Microservices** : isolation forte, mais déploiement, communication inter-processus et packaging disproportionnés pour un outil local.
- **Monolithe sans couches** : rapide au début, mais couple l'UI, le réseau et le stockage, ce qui contredit §1.2-4.

## Conséquences
- Un seul exécutable PyInstaller et un seul cycle de vie piloté par le desktop.
- La discipline des couches doit être tenue en revue de code (pas d'import FastAPI/SQLAlchemy dans `domain/`).
