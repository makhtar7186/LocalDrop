# Décisions d'architecture (ADR)

Format et règles : skill `.claude/skills/localdrop-adr`. Un ADR remplacé n'est jamais supprimé.

| ADR | Titre | Statut |
|---|---|---|
| [ADR-001](ADR-001-monolithe-modulaire.md) | Monolithe modulaire plutôt que microservices | Accepté |
| [ADR-002](ADR-002-serveur-local-windows.md) | Serveur local hébergé par l'application Windows | Accepté |
| [ADR-003](ADR-003-interface-mobile-web.md) | Interface mobile web plutôt qu'application native | Accepté |
| [ADR-004](ADR-004-sqlite-metadonnees.md) | SQLite pour les métadonnées, SQLAlchemy synchrone | Accepté |
| [ADR-005](ADR-005-protocole-par-blocs.md) | Protocole de transfert par blocs | Accepté (points ouverts) |
| [ADR-006](ADR-006-http-local-mvp.md) | HTTP local pour le MVP et stratégie de sécurisation | Accepté |
| [ADR-007](ADR-007-pyside6-desktop.md) | PySide6 pour le desktop | Accepté |

## Décisions ouvertes

- Accusé de réception fiable des téléchargements sortants (§6.3).
- Authentification des téléchargements par lien (ticket court à usage unique ou cookie).
- Bind multi-interfaces (sockets multiples) ou une seule interface choisie.
- Politique de conservation de l'historique.
