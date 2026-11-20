---
name: localdrop-phase-delivery
description: Démarche pour réaliser une phase de la roadmap LocalDrop (phases 0 à 11) en tranche verticale livrable et testable, avec les skills à charger par phase et la définition de terminé. À utiliser quand on demande « commence la phase N », « implémente <fonctionnalité du cahier des charges> » ou « quelle est la prochaine étape ».
---

# Livraison par phase

Référence : cahier des charges §18 (roadmap) et §20 (définition du MVP).

## Règles

- Chaque phase produit une version **exécutable et testable** (§18.1).
- Valider le flux réseau et le transfert réel **avant** de développer les interfaces complètes.
- Premier jalon : FastAPI démarré, URL et QR Code générés, page ouverte depuis un téléphone, petit fichier envoyé vers le PC.
- Les fonctions secondaires (historique avancé, notifications, thèmes, téléphone-à-téléphone) ne doivent pas retarder le MVP (§20).

## Démarche pour une phase

1. Relire les sections du cahier des charges concernées et lister les FR-xxx visés.
2. Charger les skills de la phase (tableau ci-dessous).
3. Écrire une définition de terminé vérifiable : tests à faire passer, démonstration manuelle.
4. Implémenter la plus petite tranche verticale qui fonctionne de bout en bout, puis élargir.
5. Tests, ruff, mypy, eslint, tsc (skill `localdrop-testing`).
6. Si une décision structurante a été prise, écrire l'ADR (skill `localdrop-adr`).
7. Si des commandes ou la structure ont changé, mettre à jour CLAUDE.md.

## Phases et skills

| Phase | Contenu | Skills |
|---|---|---|
| 0 | Dépôt, `pyproject.toml`, `requirements-dev.txt`, `apps/web` Vite, ruff/mypy/eslint, `.gitignore`, git init | testing, adr |
| 1 | `create_app`, `Settings`, logs, `/health` | backend-api |
| 2 | Interfaces réseau, QR Code, sessions, appairage, approbation | network, sessions-pairing, backend-api |
| 3 | Envoi simple téléphone → PC (page minimale) | transfer-engine, secure-storage, mobile-web |
| 4 | Téléchargement PC → téléphone | transfer-engine, mobile-web |
| 5 | WebSocket et progression | transfer-engine, backend-api |
| 6 | Blocs, manifeste, reprise | transfer-engine, secure-storage, database-migrations |
| 7 | SQLite, historique, nettoyage | database-migrations, secure-storage |
| 8 | Interface PySide6 | desktop-pyside6 |
| 9 | Interface React complète | mobile-web |
| 10 | Sécurité, tests réseau, optimisation | sessions-pairing, network, testing (+ skill global `security-review`) |
| 11 | PyInstaller, documentation | packaging-windows |

Tous les noms de skills sont préfixés par `localdrop-`.

Note : SQLite et Alembic peuvent être introduits dès la phase 3 ou 6 si la reprise l'exige. La phase 7 complète alors l'historique et le nettoyage.
