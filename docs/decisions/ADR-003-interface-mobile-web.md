# ADR-003 : Interface mobile web plutôt qu'application native

- Statut : Accepté
- Date : 2026-11-20
- Exigences liées : FR-041, §2.3, §5.3, §9.4

## Contexte
L'utilisateur doit pouvoir transférer des fichiers depuis Android et iOS sans rien installer : un scan de QR Code doit suffire.

## Décision
Client web React + TypeScript (Vite, Tailwind, Zod), compilé en fichiers statiques et servi par FastAPI. Routage par hash.

## Options étudiées
- **Applications natives** : accès complet aux fichiers et en arrière-plan, mais double développement, publication sur les stores et installation obligatoire. Hors périmètre (§2.3).
- **PWA** : nécessite un contexte sécurisé (HTTPS), indisponible en HTTP local (voir ADR-006).

## Conséquences
- Contraintes des navigateurs : suspension en arrière-plan sur iOS, pas d'accès arbitraire au système de fichiers, pas de `crypto.subtle` (hachage par `hash-wasm`).
- La reprise d'un envoi après rechargement de la page exige que l'utilisateur resélectionne le fichier.
