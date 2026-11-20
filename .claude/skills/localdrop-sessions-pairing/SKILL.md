---
name: localdrop-sessions-pairing
description: Sessions, appairage par QR Code, approbation, jetons d'appareil, révocation et limitation des tentatives dans LocalDrop. À utiliser pour domain/sessions, domain/devices, les routes /sessions/* et /devices, la génération du QR Code ou tout ce qui manipule un secret.
---

# Sessions et appairage

Référence : cahier des charges §3.2, §3.3, §4.2, §8.2, §11.1, §11.2, §12.

## Secrets

- Génération : `secrets.token_urlsafe(32)` uniquement.
- Stockage : `token_hash = sha256(secret)` (l'entropie élevée rend un KDF lent inutile). Jamais le secret brut en base, en log ou en message d'erreur.
- Comparaison : `hmac.compare_digest`.
- Filtre de journalisation qui masque tout ce qui ressemble à un jeton.

## Flux d'appairage

1. Au démarrage du serveur, création d'une session (`active`, `expires_at`) et d'un **secret d'appairage** court.
2. URL du QR Code : `http://<ip>:<port>/#/join?s=<session_id>&k=<secret>`. Le secret est placé dans le **fragment `#`**, qui n'est jamais envoyé au serveur dans la requête : il n'apparaît ni dans les logs d'accès ni dans l'en-tête Referer.
3. La page mobile lit le fragment, l'efface de l'historique (`history.replaceState`), puis envoie `POST /sessions/join` avec `{session_id, secret, display_name, platform}` dans le corps.
4. Le serveur crée un appareil en attente et le desktop affiche une demande d'approbation (FR-011, §12.2-3). Le mobile attend en interrogeant `/sessions/status`.
5. Après approbation, le mobile reçoit un **jeton d'appareil** distinct, valable pour la durée de la session. Le refus est définitif pour cette demande.
6. **Rotation du secret d'appairage** après chaque appairage réussi et à son expiration. Le QR Code est régénéré, ce qui invalide l'ancien (FR-014, §12.2-2) tout en permettant plusieurs appareils.

## Connexion manuelle (FR-005)

Le code court saisi à la main a une faible entropie. Il faut une durée de vie courte, une limitation stricte des tentatives et une approbation sur le PC obligatoire.

## Limitation des tentatives (§12.2-5)

Compteur en mémoire par IP et par session sur `/sessions/join`, avec refus temporaire (429) au-delà du seuil. Journaliser l'événement sans le secret.

## Révocation (FR-013, §12.2-12)

- `devices.status = revoked`. Toutes les requêtes suivantes reçoivent 401, et les WebSocket de l'appareil sont fermés **immédiatement**.
- La fermeture de session révoque tous les appareils et invalide le QR Code.
- Le client mobile gère le 401 en effaçant son jeton et en affichant « Session terminée, scannez à nouveau le QR Code ».

## Expiration

Une session expirée passe à `expired`. La tâche de maintenance met à jour les statuts. Côté mobile, on demande un nouveau scan (§3.3).

## QR Code

- Bibliothèque `qrcode`. Côté desktop, rendu SVG ou matrice → `QPainter`, sans dépendance à PIL si possible.
- Régénéré à chaque rotation de secret et à chaque changement d'IP (`server.network_changed`).
- Plusieurs IP candidates : un QR Code par URL, ou un sélecteur (voir skill `localdrop-network`).

## Avertissement HTTP (§12.3)

En HTTP local, le jeton peut être intercepté sur le LAN. L'interface (desktop et mobile) affiche en permanence : « Utilisez un réseau de confiance, évitez les Wi-Fi publics ». Le passage à HTTPS fera l'objet d'un ADR dédié (ADR-006).
