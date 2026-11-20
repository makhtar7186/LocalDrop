---
name: localdrop-backend-api
description: Conventions du backend FastAPI de LocalDrop (couches, routes /api/v1, authentification des appareils et du desktop, erreurs, streaming). À utiliser pour créer ou modifier une route, un schéma Pydantic, une dépendance FastAPI, un service ou la configuration du serveur dans backend/src/localdrop/.
---

# Backend FastAPI LocalDrop

Référence : cahier des charges §6, §8, §10, §12.

## Couches (dépendances dans un seul sens)

```
api/v1  →  services  →  domain
   ↘          ↘
    schemas    infrastructure (database, storage, network, realtime)
```

- `domain/` : Python pur. Entités, machine à états, règles (calcul des blocs, validation). **Aucun import** de `fastapi`, `sqlalchemy`, `starlette` ni d'I/O.
- `services/` : orchestration des cas d'usage, transactions, appels aux dépôts/stockage, publication d'événements.
- `infrastructure/` : implémentations concrètes (repositories SQLAlchemy, écriture disque, détection réseau, hub WebSocket).
- `api/v1/` : routers minces. Ils valident l'entrée (schémas), appellent un service et mappent les erreurs. Aucune logique métier.
- `schemas/` : modèles Pydantic des contrats HTTP/WS. Ils sont distincts des modèles ORM.
- `core/` : configuration (`Settings` Pydantic, préfixe d'env `LOCALDROP_`), journalisation, chemins, erreurs de base.

`main.py` expose une fabrique `create_app(settings: Settings) -> FastAPI` : pas d'état global à l'import, ce qui permet de tester l'app et de l'embarquer dans le desktop.

## Authentification

Il existe deux types d'appelants :

1. **Appareil mobile** : `Authorization: Bearer <device_token>`, via la dépendance `require_device`. Elle vérifie le hash du jeton en base, le statut `connected` (non révoqué) et l'expiration de la session, puis met à jour `last_seen_at`.
2. **Desktop (administration)** : approve, revoke, PATCH settings et création de transferts sortants. Le contrôleur desktop appelle de préférence les services **en processus**. Si une route HTTP admin existe, elle exige un jeton admin généré au démarrage **et** un client `127.0.0.1`.

Règles :
- Toute route hors `/health` et `/sessions/join` est authentifiée (§12.2-6).
- Comparer les jetons avec `hmac.compare_digest`.
- Vérifier `Origin` et `Host` sur le WebSocket et les routes admin (protection DNS rebinding).
- Ne jamais journaliser les en-têtes `Authorization` ni les jetons. Désactiver ou filtrer l'access log d'Uvicorn s'il affiche des query strings sensibles.

## Erreurs

Format unique : `{"error": {"code": "TRANSFER_NOT_FOUND", "message": "…", "details": {…}}}`.
- `code` est stable, en anglais, en MAJUSCULES. C'est le client qui affiche le message en français.
- Lever des exceptions de domaine typées (`InvalidTransition`, `ChunkHashMismatch`, `InsufficientDiskSpace`…). Un handler unique les mappe vers HTTP (404, 409, 422, 413, 507…).
- Une erreur laisse toujours le transfert dans un état explicite et récupérable (§5.2).

## Streaming et performance

- Blocs entrants : `PUT` avec corps brut `application/octet-stream` et en-tête `X-Chunk-SHA256`. Lire via `request.stream()`, **pas** `UploadFile` ni `await request.body()` sans limite. Couper dès que la taille dépasse la taille attendue du bloc (413).
- L'écriture disque, le `fsync` et le hachage de gros fichiers s'exécutent dans un thread (`anyio.to_thread.run_sync`). Ne jamais bloquer la boucle d'événements.
- Téléchargements sortants : réponse en streaming avec support `Range` (reprise). Vérifier le support natif de `FileResponse` dans la version de Starlette verrouillée, sinon implémenter `Range` explicitement. `Content-Disposition: attachment; filename*=UTF-8''<nom encodé RFC 5987>`.
- Jamais de fichier entier en mémoire (§5.1).

## Ajouter une route : checklist

1. Schémas requête/réponse dans `schemas/`, avec `model_config = ConfigDict(extra="forbid")` pour les entrées.
2. Logique dans un service, règles pures dans `domain/`.
3. Router dans `api/v1/`, avec la dépendance d'auth appropriée.
4. Si l'état change, publier l'événement WS **après le commit** (voir skill `localdrop-transfer-engine`).
5. Tests : unitaire (domaine) et intégration HTTPX (voir skill `localdrop-testing`).
6. Mettre à jour le contrat dans `shared/api-contracts/` (export OpenAPI) si la forme publique change.
