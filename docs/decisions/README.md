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

## Décisions prises en phase 4 (PC → téléphone)

- **Pas de copie** : le PC propose un fichier à **un** appareil approuvé. Le chemin, la taille et `mtime_ns` sont mémorisés. À chaque téléchargement, la source est revérifiée : un fichier modifié ou supprimé donne 410 (`SOURCE_CHANGED` / `SOURCE_UNAVAILABLE`).
- **Authentification des liens** : le téléphone obtient par Bearer un **ticket** (`POST /transfers/{id}/download-ticket`, 15 min). Ce ticket est lié au transfert et à l'appareil, et **réutilisable pendant sa durée de vie** pour permettre la reprise par `Range`. Il est révoqué à la confirmation, à l'annulation, et dès que l'appareil est révoqué. Le client le récupère à l'avance et affiche un vrai `<a href download>` : le tap direct évite les blocages iOS des téléchargements lancés après un `await`. Le ticket figure dans l'URL, mais les logs d'accès sont désactivés, le filtre masque `ticket=` et `Referrer-Policy: no-referrer` est en place.
- **Accusé de réception** (§6.3) : le premier téléchargement fait passer en `transferring`. Un envoi complet jusqu'au dernier octet est noté `fully_served`, ce qui reste **indicatif**. Seul `POST /transfers/{id}/confirm` (bouton « J'ai reçu le fichier ») fait passer en `completed`.
- **Sécurité du contenu servi** : toujours `application/octet-stream`, en `attachment`, avec `Content-Security-Policy: sandbox` et `nosniff`. Un `.html` proposé par le PC ne peut donc jamais s'exécuter dans l'origine LocalDrop.
- **Reprise** : `Range` est géré nativement par le `FileResponse` de Starlette (testé : 206 et assemblage identique).

## Décisions prises en phase 5 (temps réel)

- **Protocole `/ws`** :
  - authentification par **premier message** `{"type":"auth","token":…}` en moins de 5 s (`ws_auth_timeout_seconds`), donc jamais de jeton dans l'URL ;
  - les appareils **en attente** sont admis, pour apprendre leur approbation instantanément ;
  - le PC s'authentifie avec `{"type":"auth","admin_token":…}`, depuis le loopback uniquement ;
  - enveloppe `{id, type, ts, data}`, `ping`/`pong` applicatif ;
  - codes de fermeture : 4401 (non autorisé ou révoqué), 4403 (origine étrangère ou appareil refusé), 4408 (authentification trop tardive), 4409 (client trop lent, à resynchroniser), 1001 (arrêt).
- **Origine** : un navigateur doit présenter une `Origin` identique à `Host`, sinon la poignée de main est refusée (HTTP 403, anti-CSWSH). Les clients non navigateurs, sans `Origin`, sont admis.
- **Hub** :
  - les événements publiés depuis n'importe quel thread sont reportés sur la boucle asyncio **de chaque connexion** ;
  - une seule file d'envoi par connexion, donc ordre garanti ;
  - abonnement au bus idempotent ;
  - un appareil ne voit que `transfer.*` et `device.*` le concernant ;
  - `device.revoked` ou `device.rejected` ferment immédiatement ses sockets.
- **Présence (FR-012)** : le premier socket ouvert passe l'appareil en `connected`, la fermeture du dernier le passe en `disconnected`. Toute requête authentifiée le rebascule en `connected`.
- **Client** : le WebSocket n'est **jamais** la source de vérité. Chaque événement pertinent et chaque (re)connexion déclenchent une relecture REST, et l'actualisation périodique reste en filet de sécurité (30 s connecté, 15 s réception). Il n'y a pas de reconnexion après 4401/4403. La reconnexion est immédiate au retour au premier plan (`visibilitychange`, iOS).

## Décisions prises en phase 6 (persistance et reprise)

- **SQLite dès la phase 6** (ADR-004), dans `%LOCALAPPDATA%\LocalDrop\database\localdrop.db`, pour les tables `sessions`, `devices`, `transfers` et `transfer_chunks` (§11).
  - Migration `0001` écrite à la main, avec les `CHECK` et les index. Un test vérifie qu'elle est identique aux modèles ORM, et `alembic check` reste propre.
  - Pragmas : WAL, `foreign_keys`, `synchronous=FULL`.
  - Au démarrage, la migration est appliquée par code, précédée d'une sauvegarde par l'API backup de SQLite (5 conservées).
- **Appareils persistés** : un téléphone approuvé le reste après un redémarrage du PC, tant que la session (12 h) est valide. Le secret d'appairage n'est jamais stocké : chaque démarrage affiche un nouveau QR Code dans la **même** session. Cela tranche la décision ouverte sur la persistance des appareils.
- **Réconciliation au démarrage** :
  - un upload qui recevait des blocs passe en `paused` ;
  - un upload sans fichier temporaire passe en `failed` (`TEMP_FILE_MISSING`), en suivant le chemin légal de la machine à états ;
  - une vérification interrompue est **rejouée**, grâce au hash annoncé mémorisé (`expected_sha256`) ;
  - les `.part` orphelins sont supprimés ;
  - un fichier final n'est jamais touché.
- **API** : `POST /transfers/{id}/pause` et `/resume` (idempotent). Un bloc envoyé sur un transfert en pause reçoit 409 `TRANSFER_PAUSED`, et le client reprend alors tout seul.
- **Accès base hors de la boucle asyncio** : les routes qui touchent SQLite sont des `def`, exécutées par FastAPI dans un thread. Le hub WebSocket passe par `asyncio.to_thread`.
- **Tests** : `persistence="memory"` par défaut pour la vitesse. Le contrat des dépôts est testé sur les deux implémentations, et des tests dédiés couvrent SQLite, la migration et le redémarrage.
- **Client, reprise après rechargement** : les envois en cours sont mémorisés dans `localStorage`. Une section « Envois interrompus » permet de resélectionner le fichier, qui est accepté sur **nom et taille** : le sélecteur iOS peut changer la date de modification. Le SHA-256 global vérifié par le serveur empêche de publier un contenu différent. Seuls les blocs manquants sont renvoyés, mais tout le fichier est relu pour le hash.

## Décisions ouvertes

- Progression octet par octet des téléchargements sortants (actuellement : démarré, puis servi en entier).
- Vérification d'intégrité côté téléphone pour les petits fichiers (téléchargement via `fetch` et hash avant enregistrement) : à évaluer en phase 9.
- Persistance des appareils approuvés après redémarrage du PC (ou nouvel appairage obligatoire).
- Politique de conservation de l'historique.
