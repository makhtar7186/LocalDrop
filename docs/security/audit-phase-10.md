# Audit de sécurité : phase 10

- Date : 2026-11-20
- Version auditée : commit `c60b7b5` (phase 9), corrections incluses dans le commit de la phase 10
- Référence : cahier des charges §12 (modèle de menace et mesures)

## Résumé

| Gravité | Constat | État |
|---|---|---|
| Moyenne | Le nom d'appareil choisi par le téléphone était affiché en HTML non échappé dans le dialogue d'approbation du PC. | Corrigé |
| Moyenne | Pas de contrôle de l'en-tête `Host` : un site tiers pouvait viser le serveur par « DNS rebinding » et contourner le contrôle d'origine du WebSocket. | Corrigé |
| Faible | Plusieurs envois simultanés pouvaient, ensemble, dépasser l'espace disque libre, chacun n'étant vérifié que seul. | Corrigé |
| Faible | Aucun plafond d'envois non terminés par téléphone. | Corrigé (32 par défaut) |
| Faible | Aucune `Content-Security-Policy` sur les pages de l'interface mobile, alors que le jeton de l'appareil est dans le `localStorage`. | Corrigé |
| Info | Requête `/favicon.ico` en 404 à chaque chargement de page. | Corrigé |
| Accepté | Trafic HTTP en clair sur le réseau local : jeton et fichiers observables par un autre participant. | Risque connu (ADR-006) |

Aucune faille critique. Aucune route sensible n'était accessible sans authentification, et aucun secret n'apparaît dans les journaux ni dans les réponses d'erreur.

## Constats détaillés

### 1. Injection HTML dans le dialogue d'approbation (moyenne)

- **Où** : [approval.py](../../apps/desktop/src/localdrop_desktop/windows/approval.py). Le texte est un `QLabel` en `RichText` construit avec `display_name`, qui vient du téléphone.
- **Scénario** : une personne qui a photographié le QR Code s'appaire avec un nom comme `<span style="font-size:1px">x</span>Mon iPhone (iOS, 192.168.1.20)`. Le dialogue affiche alors un faux nom et une fausse adresse IP, ce qui facilite une approbation par erreur. C'est précisément ce que l'approbation obligatoire (§12.2-3) doit empêcher.
- **Correction** : le nom et l'IP sont échappés (`html.escape`). Test : `test_device_name_cannot_inject_html_in_approval_dialog`.
- **Vérifié** : les autres affichages de données venant du téléphone sont du texte brut (modèles Qt, barre d'état échappée) ou des noms de fichiers déjà assainis, d'où `<` et `>` sont exclus.

### 2. DNS rebinding (moyenne)

- **Où** : aucun middleware ne vérifiait l'en-tête `Host`. Le contrôle d'origine du WebSocket compare `Origin` et `Host`, qui sont identiques lors d'une attaque par rebinding (`site.example` résolu vers l'IP du PC).
- **Impact limité** : l'attaquant n'obtient ni jeton d'appareil (le `localStorage` dépend de l'origine) ni jeton admin (aléatoire, en mémoire). Les routes restent donc protégées. La faille contournait néanmoins une défense prévue.
- **Correction** : `AllowedHostMiddleware` ([middleware.py](../../backend/src/localdrop/api/middleware.py)) n'accepte qu'une IP littérale ou `localhost`, avec un port facultatif. Le QR Code, le desktop et la saisie manuelle n'utilisent que des IP. Les autres requêtes reçoivent 400 `HOST_NOT_ALLOWED`, et le WebSocket est fermé (1008).
- **Conséquence** : un nom d'hôte, par exemple `mon-pc.local`, est refusé. Il faudrait l'ajouter explicitement si un jour il est utilisé.
- **Tests** : `test_host_check.py`, `test_dns_rebinding_host_is_refused`, et sur vrai socket `test_dns_rebinding_is_refused_on_the_real_server`.

### 3. Épuisement de ressources (faible)

Ce risque concerne uniquement un appareil **approuvé**.

- **Espace disque** : `check_free_space` réserve désormais les octets restants de tous les envois non terminés (test `test_free_space_accounts_for_other_unfinished_uploads`).
- **Nombre d'envois** : le plafond `max_active_uploads_per_device` (32 par défaut) renvoie 429 `TOO_MANY_ACTIVE_TRANSFERS`, avec un message en français sur le téléphone.

### 4. CSP de l'interface mobile (faible)

Aucun vecteur d'injection n'a été trouvé : React échappe le texte, et il n'y a ni `innerHTML` ni `eval` dans le code. La CSP est donc une défense en profondeur :

- `script-src 'self'` : aucun script en ligne ou externe ;
- `frame-ancestors 'none'`, `object-src 'none'`, `base-uri 'none'`.

`'unsafe-eval'` est conservé : Safari antérieur à iOS 16 en a besoin pour le WebAssembly de `hash-wasm`. Le test en vrai navigateur vérifie qu'aucune violation de CSP ne se produit pendant un envoi complet.

## Points contrôlés sans constat

| Mesure §12.2 | Contrôle |
|---|---|
| 1. Secrets cryptographiques | `secrets.token_urlsafe(32)` pour les secrets d'appairage, les jetons d'appareil, les tickets et le jeton admin. |
| 2. Expiration du QR Code | Usage unique et rotation, durée de vie de 5 min. |
| 3. Approbation sur le PC | Un appareil en attente reçoit 403 `DEVICE_PENDING` sur les transferts (test `test_pending_device_cannot_use_transfer_routes`). |
| 4. Hashes en base | Seul le SHA-256 des jetons et tickets est stocké, et la comparaison se fait sur le hash. |
| 5. Limitation des tentatives | 10 appairages par minute et par IP (429). |
| 6. Routes authentifiées | Inventaire automatique de toutes les routes `/api` : seules `/health` et `/sessions/join` sont publiques (`test_every_route_except_health_and_join_requires_authentication`). L'administration exige le loopback **et** le jeton. |
| 7. Taille, index et hash des blocs | La taille est vérifiée avant et pendant la lecture du corps ; l'index est borné ; le SHA-256 est vérifié par bloc et pour le fichier entier. |
| 8. Chemins confinés | Nom assaini (testé avec Hypothesis), chemin construit par le serveur, `resolve()` et vérification du parent. |
| 9. Aucune ouverture automatique | Mark-of-the-Web posé ; « Ouvrir le dossier » utilise `explorer /select,`. |
| 10. Journaux | Masquage des jetons, secrets et tickets ; journal d'accès Uvicorn désactivé ; les erreurs ne renvoient jamais la valeur reçue (`test_errors_never_echo_secrets`). |
| 11. Interfaces privées | Écoute sur les IP privées choisies (jamais `0.0.0.0`), et `PrivateNetworkOnlyMiddleware` en défense en profondeur. |
| 12. Révocation | 401 immédiat, y compris sur vrai socket, et WebSocket fermés. |
| Téléchargements | Ticket de 15 min lié à l'appareil et au transfert, revérifié à chaque requête ; fichier servi en `attachment`, `octet-stream`, `CSP: sandbox`. |
| Dépendances | `pip-audit` : aucune vulnérabilité connue. `npm audit --omit=dev` : 0 vulnérabilité. |

## Risques résiduels acceptés

- **HTTP en clair (ADR-006)** : sur un réseau partagé, un participant qui écoute le trafic peut lire le jeton d'appareil et les fichiers. L'avertissement « réseau de confiance » reste affiché en permanence. Le point d'accès du PC ou du téléphone limite l'exposition. Le passage à HTTPS reste à décider par un ADR.
- **Jeton dans le `localStorage`** : il est lisible par un script de la même origine. La CSP et l'absence de vecteur d'injection limitent ce risque.
- **Plusieurs IP sur le même PC** : un autre logiciel local peut joindre le serveur sur `127.0.0.1`. L'administration exige néanmoins le jeton, stocké dans le profil Windows de l'utilisateur.

## Non couvert par cet audit

- **iOS Safari et Android réels** : seul Chromium de bureau en émulation mobile a été testé automatiquement. Voir la matrice [e2e-matrix.md](../testing/e2e-matrix.md).
- **Pare-feu Windows et profils réseau** : vérification manuelle (matrice e2e).
- **Exécutable PyInstaller** (phase 11) : chemins, droits et signature restent à auditer une fois l'exécutable construit.
- **Test d'intrusion** par une personne extérieure au projet.
