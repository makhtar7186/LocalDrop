# ADR-006 : HTTP local pour le MVP et stratégie de sécurisation

- Statut : Accepté
- Date : 2026-11-20
- Exigences liées : §12.1 à §12.3

## Contexte
Un certificat auto-signé provoque des avertissements bloquants sur les navigateurs mobiles. Le HTTP en clair expose en revanche le trafic aux autres participants du réseau.

## Décision
Pour le MVP :
- HTTP sur les IPv4 privées uniquement.
- Le secret d'appairage est transmis dans le **fragment `#`** de l'URL du QR Code. Il n'est donc jamais envoyé dans une ligne de requête ni journalisé.
- Le secret d'appairage tourne après chaque appairage, l'approbation sur le PC est obligatoire, et le jeton d'appareil est révocable.
- Hashes seuls en base, aucun secret dans les logs.
- Avertissement permanent « réseau de confiance » sur le desktop et le mobile.

## Options étudiées
- **HTTPS auto-signé** : avertissements, et refus total de certains navigateurs.
- **Certificat de confiance via une autorité locale installée sur le téléphone** : trop de friction pour le MVP.
- **Chiffrement applicatif de bout en bout** : à étudier après le MVP.

## Conséquences
- Pas de « secure context » côté navigateur : `crypto.subtle`, `crypto.randomUUID`, Clipboard API, Service Worker et Wake Lock sont indisponibles. Il faut prévoir des solutions de repli.
- Un ADR ultérieur définira la stratégie HTTPS de production.

## Mesures complémentaires (phase 10)
- En-tête `Host` limité aux IP et à `localhost` (anti DNS rebinding).
- `Content-Security-Policy` sur les pages de l'interface mobile, le jeton de l'appareil étant dans le `localStorage`.
- Audit : [docs/security/audit-phase-10.md](../security/audit-phase-10.md).
