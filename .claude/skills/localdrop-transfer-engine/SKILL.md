---
name: localdrop-transfer-engine
description: Moteur de transfert résumable de LocalDrop (protocole par blocs, machine à états, idempotence, finalisation atomique, reprise, téléchargements sortants, événements WebSocket de progression). À utiliser pour toute modification de domain/transfers, services de transfert, routes /transfers/* ou /ws.
---

# Moteur de transfert résumable

Référence : cahier des charges §6.3, §8.3, §8.5, §9, §10.2, §10.4. C'est le cœur du produit : la fiabilité passe avant tout.

## Machine à états (domain, Python pur)

```
created → waiting → transferring → verifying → completed
                    transferring ⇄ paused
                    verifying → failed
created | waiting | transferring | paused → cancelled
```

- Les transitions autorisées sont déclarées dans une table (`dict[Status, frozenset[Status]]`). `transition()` lève `InvalidTransition` pour toute autre transition.
- `completed`, `cancelled` et `failed` sont terminaux. Un transfert `completed` est immuable.
- En base, le changement d'état se fait par **update conditionnel** : `UPDATE transfers SET status=:new WHERE id=:id AND status=:expected`. Si `rowcount != 1`, c'est un conflit (409). C'est la garde contre les appels concurrents.

## Calcul des blocs

- `total_chunks = ceil(total_size / chunk_size)`. Pour un fichier de 0 octet : `total_chunks = 0`, finalisation directe.
- Taille attendue du bloc `i` : `chunk_size`, sauf le dernier : `total_size - chunk_size * (total_chunks - 1)`.
- Valider `0 <= index < total_chunks` et la taille exacte, sinon 422.
- `received_bytes` = somme des tailles des blocs validés en base. Ne jamais l'incrémenter de façon optimiste.

## Réception d'un bloc (PUT /transfers/{id}/chunks/{index})

1. Vérifier l'appareil propriétaire, l'état (`waiting` passe à `transferring` au premier bloc ; `paused` → 409, il faut appeler `/resume`).
2. Si le bloc existe déjà en base : même SHA-256 → 200 idempotent sans réécriture ; hash différent → 409 `CHUNK_CONFLICT` (§9.3).
3. Streamer le corps en calculant le SHA-256 à la volée, avec limite de taille.
4. Écrire à l'offset `index * chunk_size` dans le fichier temporaire (`r+b`, `seek`, `write`, `flush`, `os.fsync`), dans un thread.
5. Comparer le hash reçu avec `X-Chunk-SHA256`. S'il diffère, 422 et rien n'est enregistré.
6. Insérer la ligne `transfer_chunks`, contrainte unique `(transfer_id, chunk_index)`, puis commit. **Le bloc n'est confirmé qu'après ce commit.**
7. Publier `transfer.progress` (après commit, avec limitation de fréquence).

Si le processus meurt entre l'écriture et le commit, le bloc est simplement renvoyé plus tard : l'écriture positionnelle est idempotente.

## Finalisation (POST /transfers/{id}/complete)

1. Update conditionnel `transferring → verifying`. Si ça échoue, 409 : protection contre les doubles appels.
2. Vérifier que tous les blocs sont présents et que la taille du fichier temporaire est égale à `total_size`.
3. SHA-256 global en streaming (thread), comparé à celui fourni par le client. En cas d'échec : `failed`, le fichier temporaire est conservé pour diagnostic jusqu'à expiration.
4. Publication via `storage.finalize()`, sans écrasement (voir skill `localdrop-secure-storage`). Puis `completed`, `final_path`, `safe_filename`.
5. Événement `transfer.completed` ou `transfer.failed`.

## Reprise

- `GET /transfers/{id}/chunks` renvoie les index validés. Le client n'envoie que les manquants (§9.2-7).
- Les transferts non terminés survivent au redémarrage. Au démarrage, une **réconciliation** compare la base et les fichiers temporaires : fichier temporaire absent → `failed` ; fichier temporaire orphelin → supprimé.
- Expiration : 24 h par défaut (paramétrable), traitée par la tâche de maintenance.

## Sortants (PC → téléphone)

- Créés par le desktop (`direction = "download"`). Le fichier source n'est pas copié : on stocke son chemin et on vérifie à chaque requête qu'il existe toujours avec la même taille et le même mtime.
- Servi en streaming avec `Range`.
- **Ne jamais marquer `completed` sans un signal explicite du client** (§6.3). Le servir entièrement ne prouve pas la livraison. Le mécanisme d'accusé de réception est à figer par ADR (proposition : `POST /complete` envoyé par le client mobile après le téléchargement).
- Les liens `<a download>` ne peuvent pas porter d'en-tête `Authorization`. Prévoir un ticket de téléchargement court, à usage unique, passé en query, et le documenter en ADR.

## Événements temps réel (/ws)

- Enveloppe : `{"id": "<uuid>", "type": "transfer.progress", "ts": "<ISO8601 UTC>", "data": {…}}`.
- Types du §10.4 : `device.connected`, `device.disconnected`, `transfer.created`, `transfer.progress`, `transfer.paused`, `transfer.completed`, `transfer.failed`, `server.network_changed`.
- Publier **après commit** uniquement. Limiter `transfer.progress` à environ 4 par seconde et par transfert.
- Le WS n'est **pas** la source de vérité : à la reconnexion, le client relit l'état par REST.
- Authentification WS : premier message `{"type":"auth","token":…}` avec délai court. Pas de jeton dans l'URL, sinon il finit dans les logs. Fermer immédiatement les sockets d'un appareil révoqué.
- Le hub est aussi branché au desktop (bus d'événements en processus).

## Paramètres de départ (§5.1, §9.1)

Bloc de 4 Mio, 2 transferts simultanés, 1 bloc en vol par transfert. Ce sont des paramètres configurables, pas des garanties. Toute optimisation de parallélisme passe après les benchmarks.
