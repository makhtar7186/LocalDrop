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

## Décisions prises en phase 2 (à formaliser si elles évoluent)

- **Bind** : sockets explicites sur `127.0.0.1` et sur chaque IPv4 privée détectée (`SO_EXCLUSIVEADDRUSE`), jamais `0.0.0.0`. Un middleware refuse en plus tout client hors réseau privé ou loopback. Une nouvelle IP apparue après le démarrage exige un redémarrage du serveur (`server.network_changed`, `restart_required`), que le desktop pilotera.
- **Administration HTTP** : client loopback **et** en-tête `X-LocalDrop-Admin` (jeton aléatoire par démarrage, écrit dans `%LOCALAPPDATA%\LocalDrop\state\admin.token`). Le desktop appellera les services en processus.
- **Appairage** : un jeton d'appareil est émis dès `join` (statut `pending`). Il n'ouvre les routes de transfert qu'après approbation. Le secret du QR Code tourne après chaque `join` réussi.
- **Sessions en mémoire** : dépôt `InMemorySessionRepository` derrière le port `SessionRepository`. Il sera remplacé par SQLite (phase 6/7) sans changer les services.

## Décisions prises en phase 3

- **Arborescence de réception** : les fichiers vérifiés sont publiés **directement** dans le dossier de réception (`Downloads\LocalDrop` par défaut). Les temporaires `<id>.part` sont dans `<réception>\.localdrop-tmp` (caché, même volume, donc renommage atomique). La base et les logs restent dans `%LOCALAPPDATA%\LocalDrop` (§15), ce qui remplace la structure `incoming/temporary/database/logs` du §13.1.
- **Protocole** : le protocole par blocs complet du §9.2 est en place dès la phase 3. Le hash global est envoyé à `POST /complete`. Un bloc tient en mémoire (≤ `chunk_size`), jamais le fichier entier. L'écriture sur disque, le hachage et la publication tournent dans un thread.
- **Concurrence** : verrou par transfert pour les blocs et la finalisation, plus un update conditionnel `transferring → verifying`.
- **Transferts en mémoire** (`InMemoryTransferRepository`) : la persistance et la reprise après redémarrage arrivent avec SQLite (phase 6/7).
- **Fichiers reçus** : marqués `Zone.Identifier` (ZoneId=3), jamais ouverts ni exécutés.

## Décisions ouvertes

- Accusé de réception fiable des téléchargements sortants (§6.3).
- Authentification des téléchargements par lien (ticket court à usage unique ou cookie).
- Persistance des appareils approuvés après redémarrage du PC (ou nouvel appairage obligatoire).
- Politique de conservation de l'historique.
