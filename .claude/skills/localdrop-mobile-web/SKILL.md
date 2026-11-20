---
name: localdrop-mobile-web
description: Client web mobile de LocalDrop (React, TypeScript, Vite, Tailwind, Zod) servi en HTTP local à Safari iOS et Chrome Android. Couvre l'envoi par blocs avec reprise, le hachage sans crypto.subtle, le téléchargement, le WebSocket, les limites iOS, l'UI française en thème sombre. À utiliser pour tout code dans apps/web/.
---

# Client web mobile

Référence : cahier des charges §5.3, §9.4, §14.1, §14.3, FR-041 à FR-044.

## Piège n°1 : pas de « secure context »

La page est servie en `http://192.168.x.x`, ce qui n'est **pas** un contexte sécurisé. Ces API sont donc **indisponibles** :
- `crypto.subtle` → utiliser `hash-wasm` (`createSHA256()`, incrémental et rapide) pour les hashes de blocs et le hash global ;
- `crypto.randomUUID` → utiliser `crypto.getRandomValues` ou un id fourni par le serveur ;
- `navigator.clipboard` → repli `document.execCommand('copy')` ou sélection manuelle ;
- Service Worker / PWA, Screen Wake Lock → absents. Afficher « Gardez cette page ouverte et l'écran allumé pendant le transfert » (§5.3).

Ne jamais coder une fonctionnalité qui suppose HTTPS sans repli.

## Structure

`src/app` (routing, providers), `features/{pairing,send,receive,history}`, `services` (client API, WS, uploader), `components` (UI réutilisable), `hooks`, `types`, `styles`.
- Routing par **hash** (`#/join`, `#/send`…). Le secret d'appairage arrive dans le fragment (skill `localdrop-sessions-pairing`) et le serveur statique reste trivial.
- **Toute** réponse REST et tout message WS est validé par un schéma Zod avant usage. Les types dérivent de `z.infer`.

## Envoi (téléphone → PC)

1. Sélecteur natif `<input type="file" multiple>`, sans `accept` restrictif (FR-022, FR-023).
2. `POST /transfers` → `transfer_id`, `chunk_size`, `total_chunks`.
3. Pour chaque bloc : `file.slice(start, end)`, `arrayBuffer()`, hash, puis `PUT` avec `X-Chunk-SHA256`. Un seul bloc en vol par transfert, 2 transferts simultanés (paramétrables).
4. Hash global calculé **incrémentalement** pendant l'envoi et transmis à `POST /complete`.
5. Progression = **octets confirmés par le serveur**, pas ceux envoyés (§5.1). Débit calculé sur une fenêtre glissante.
6. Erreur réseau : réessai avec backoff exponentiel. Au retour, `GET /transfers/{id}/chunks` puis envoi des seuls blocs manquants.
7. Rechargement de page : l'objet `File` est perdu. Les transferts en cours (`id`, nom, taille, `lastModified`) sont persistés dans `localStorage`, et l'utilisateur doit **resélectionner le même fichier** (vérification nom + taille + date). Le hash global est alors recalculé en entier.

Ne jamais charger un fichier entier en mémoire, ne jamais concaténer de `Blob` géant.

## Réception (PC → téléphone)

- Téléchargement natif du navigateur via lien (ticket de téléchargement court en query, car un `<a>` ne peut pas envoyer `Authorization`). Pas d'assemblage en mémoire côté JS (§9.4).
- Signaler la fin au serveur uniquement si un signal fiable existe. Sinon, l'état reste « mis à disposition » et non « reçu ».
- Sur iOS, la reprise de téléchargement n'est **pas garantie** tant qu'elle n'a pas été validée par la matrice e2e (§9.4).

## Temps réel

- WS avec authentification au premier message, reconnexion avec backoff, et **resynchronisation REST** après chaque reconnexion (le WS n'est pas la source de vérité).
- Événement `visibilitychange` : au retour au premier plan, resynchroniser l'état et relancer les envois suspendus.
- 401 → effacer le jeton et afficher l'écran « Scannez à nouveau le QR Code ».

## UI

- Textes en **français**, centralisés dans un module de messages pour préparer l'i18n.
- Thème sombre par défaut, contrastes WCAG AA, cibles tactiles ≥ 44 px, `env(safe-area-inset-*)` pour iOS, portrait et paysage.
- États obligatoires sur chaque écran : vide, chargement, erreur, hors connexion (FR-043).
- Écrans : Accueil (nom du PC, état de connexion, Envoyer/Recevoir), Envoyer, Recevoir, Historique (§14.3).
- Bandeau permanent : réseau de confiance (§12.3).

## Build et dev

- `npm run build` produit `apps/web/dist/`, servi par FastAPI en production et embarqué par PyInstaller.
- En dev, le serveur Vite proxifie `/api` et `/ws` vers le backend. Pour tester sur un vrai téléphone, le plus fiable est de servir le build depuis FastAPI.
- Qualité : `npm run lint`, `npm run typecheck` (`tsc --noEmit`), `npm test` (Vitest + Testing Library). Le client uploader se teste avec un faux `fetch`, en simulant coupure puis reprise.
