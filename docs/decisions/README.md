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

## Décisions prises en phase 7 (historique, maintenance, réseau)

- **Maintenance (FR-035)** : [services/maintenance.py](../../backend/src/localdrop/services/maintenance.py), au démarrage puis toutes les `maintenance_interval_minutes` (15).
  - Transfert actif expiré : annulé (`error_code=EXPIRED`), temporaire supprimé.
  - Échec : temporaire conservé pour diagnostic jusqu'à expiration.
  - Orphelin : supprimé après `orphan_grace_minutes` (60), pour ne pas détruire le temporaire d'un upload en cours de création.
  - Historique terminé : purgé après `history_retention_days` (30, `None` = sans limite).
  - Sessions échues : passées en `expired`.
  - **Aucun fichier final ni fichier source du PC n'est jamais supprimé.**
- **Historique (FR-034)** : `GET /history` (appareil courant uniquement) et `GET /admin/history` (filtre `device_id`), avec `direction`, `status` (répétable), `q`, `limit` ≤ 200 et `offset`, du plus récent au plus ancien.
  - Recherche insensible à la casse **Unicode** : une fonction SQL `casefold` est enregistrée sur chaque connexion, car `lower()` de SQLite ne traite que l'ASCII.
  - Les jokers LIKE saisis (`%`, `_`) sont pris littéralement.
- **Changement de réseau (FR-003)** : [server.py](../../backend/src/localdrop/server.py) (`LocalServer`). Une nouvelle adresse privée déclenche un **redémarrage propre** d'Uvicorn, uniquement par son API publique, sur les nouvelles adresses, avec un QR Code réaffiché.
  - Les sessions et transferts étant persistés, les téléphones se reconnectent seuls (WebSocket avec backoff, uploads par réessai et `resume`).
  - L'arrêt gracieux est limité à 3 s.
- **Aide à la connexion (§3.3)** : sans aucun `join` `join_help_delay_seconds` (60) après le QR Code, le terminal affiche une URL de test `/api/v1/health` pour le téléphone, l'explication de l'isolation des clients, la procédure du point d'accès mobile, et l'avertissement sur un profil Windows « Public » (lu avec `Get-NetConnectionProfile`, au mieux).

## Décisions prises en phase 8 (application Windows)

- **Architecture** : [apps/desktop/](../../apps/desktop/src/localdrop_desktop/).
  - `ServerWorker` fait tourner `LocalServer` dans un thread non démon. L'arrêt passe par `stop()` puis `join` (10 s).
  - `EventBridge` relaie le bus vers des signaux Qt en file.
  - `TaskRunner` exécute tout appel touchant la base ou le disque hors du thread GUI, avec un retour par signal.
  - `AppController` est la façade **en processus** : jamais d'appel HTTP pour l'administration.
- **Écrans (§14.2)** :
  - Tableau de bord : état et démarrage/arrêt (FR-001), QR Code dessiné en `QPainter`, adresses (la copie ne contient **jamais** le secret), appareils (autoriser, refuser, déconnecter, fermer la session), dépôt de fichiers.
  - Transferts (annulation).
  - Historique (recherche, sens, « Ouvrir le dossier » par `explorer /select,`, jamais le fichier lui-même).
  - Paramètres.
- **Approbation (FR-011)** : dialogue non bloquant par appareil, fermé automatiquement si la décision est prise ailleurs. « Refuser » est le bouton par défaut, et « Autoriser » ne peut **jamais** le devenir : Entrée refuse, ce qui est testé au clavier.
- **Paramètres persistés** dans `%LOCALAPPDATA%\LocalDrop\settings.json`, uniquement pour les clés de `USER_EDITABLE`. Priorité : environnement > fichier > défauts. Un fichier invalide n'empêche jamais le démarrage. Les modifications s'appliquent au **prochain démarrage**.
- **Pause/reprise depuis le PC : non proposées.** Le téléphone reprend automatiquement un transfert « en pause » (mécanisme de reprise après redémarrage) : une pause décidée sur le PC serait aussitôt annulée. Il faudrait distinguer la cause de la pause (à étudier). Le PC peut **annuler** dans les deux sens.
- **Instance unique** : `QLockFile` (`staleLockTime=0`, verrou de longue durée) et `QLocalServer`. Une seconde instance réactive la fenêtre puis se ferme.
- **Arrêt propre** : confirmation si des transferts sont actifs, puis fermeture des dialogues, arrêt du serveur (WebSocket fermés), des tâches et de la base, et suppression du jeton admin. Les transferts interrompus sont repris au démarrage suivant (réconciliation de la phase 6).
- **Non fait** (optionnel au cahier) : icône de zone de notification et démarrage automatique avec Windows.

## Décisions prises en phase 9 (interface mobile)

- **Écrans du §14.3** : Accueil (nom du PC, actions Envoyer et Recevoir, compteurs), Envoyer, Recevoir et Historique.
  - Routage par **hash** (`#/envoyer`, `#/recevoir`, `#/historique`), compatible avec le bouton Retour du téléphone.
  - Barre de navigation basse (zone du pouce, `safe-area-inset-bottom`) avec pastilles libellées précisément (« 1 envoi en cours », « 2 fichiers à recevoir »).
- **Écrans toujours montés, simplement masqués** (`hidden`) : un envoi en cours, la recherche ou le défilement ne sont jamais perdus en changeant d'écran.
- **Annulation d'un envoi par le téléphone (FR-025)** : `AbortController` par envoi.
  - Un envoi en file d'attente n'est jamais démarré. Un envoi en cours s'arrête entre deux blocs, y compris pendant les réessais réseau.
  - Le transfert est annulé sur le PC (place libérée), et l'annulation reste effective côté téléphone même si le PC est injoignable.
- **Accessibilité** : le focus va sur le titre de l'écran affiché, avec `aria-current="page"`, des cibles ≥ 44 px, `prefers-reduced-motion` et `lang="fr"`.
- **Barrière d'erreur** : une erreur de rendu affiche un écran « Recharger la page », jamais une page blanche.
- **Bundle** : passage à `zod/mini` (même validation, API fonctionnelle) : 110,7 → 94,4 Ko compressés. Le reste est surtout React 19.

## Décisions prises en phase 10 (sécurité, tests réseau, optimisation)

Rapport complet : [audit-phase-10.md](../security/audit-phase-10.md).

- **En-tête `Host` limité aux IP littérales et à `localhost`** (`AllowedHostMiddleware`), contre le DNS rebinding. Le QR Code, le desktop et la saisie manuelle n'utilisent que des IP. Un nom d'hôte (`mon-pc.local`) devrait être ajouté explicitement.
  - Dans les tests, `TestClient` doit viser une IP (`base_url`), y compris pour le WebSocket : Starlette impose sinon `ws://testserver`.
- **CSP sur les pages de l'interface mobile** : aucun script en ligne ni externe. `'unsafe-eval'` est conservé pour le WebAssembly de `hash-wasm` sur Safari antérieur à iOS 16, qui ignore `'wasm-unsafe-eval'`. Les réponses `/api` n'ont pas de CSP de page (les téléchargements gardent `sandbox`).
- **Nom d'appareil échappé** dans le dialogue d'approbation : toute donnée venant du téléphone affichée en texte enrichi Qt doit passer par `html.escape`.
- **Ressources bornées par téléphone** : 32 envois non terminés au maximum (`max_active_uploads_per_device`). L'espace disque libre doit couvrir le nouvel envoi **et** le reste de tous les envois non terminés.
- **Optimisations mesurées, invariants inchangés** (`fsync` et hash par bloc conservés). Coût par bloc côté PC : 21 → 12,5 ms.
  - `record_chunk` enregistre le bloc et la progression dans **une** transaction (un commit et un fsync de moins).
  - Les fichiers temporaires restent **ouverts** entre deux blocs, dans un cache borné de 8. Sous Windows, fermer un fichier modifié déclenche l'analyse antivirus. Un descripteur est retiré du cache pendant l'écriture, et `close_temp` est appelé avant tout renommage ou suppression (Windows refuse de renommer un fichier ouvert). `AppServices.close()` ferme le cache.
  - « Vu pour la dernière fois » n'est écrit qu'une fois par 30 s, et non à chaque requête.
- **Taille de bloc maintenue à 4 Mio** après banc de mesure (`python -m localdrop.bench`). Le PC absorbe environ 88 Mio/s en envoi, le Wi-Fi sera le goulot. Voir [e2e-matrix.md](../testing/e2e-matrix.md).
- **Tests de bout en bout automatisés** :
  - sur vrais sockets (`tests/e2e/test_real_network.py`), avec `PhoneClient`, client en bibliothèque standard ;
  - en vrai navigateur sans interface (`tests/e2e/test_browser.py`, protocole DevTools, Chrome ou Edge).
  - Ils ne remplacent pas la matrice manuelle (Safari iOS, Wi-Fi réel, pare-feu).
- **Accueil mobile** : la carte d'état de l'appairage disparaît une fois connecté. Elle faisait doublon avec « Connecté à <PC> », ce que les captures du test navigateur ont révélé.

## Décisions ouvertes

- Pause et reprise d'un upload décidées sur le PC (distinguer la cause de la pause).
- Progression octet par octet des téléchargements sortants (actuellement : démarré, puis servi en entier).
- Vérification d'intégrité côté téléphone pour les petits fichiers (téléchargement via `fetch` et hash avant enregistrement).
- Deux blocs en vol par envoi : le lien reste inactif pendant le traitement d'un bloc côté PC (~12 ms), soit environ 6 % sur un Wi-Fi à 20 Mio/s. Ce n'est pas utile tant que la matrice réelle ne le montre pas.
- HTTPS local ou chiffrement applicatif (ADR-006) : à décider avant toute utilisation sur réseau partagé.

Décisions closes : les appareils approuvés sont persistés et restent valables après redémarrage (phase 6) ; l'historique est conservé 30 jours, paramétrable (phase 7).
