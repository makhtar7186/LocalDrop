# Matrice de tests end-to-end (§16.3)

À exécuter avant chaque version candidate. Noter la version, la date, le résultat (OK, ou KO avec ticket) et le débit mesuré.

## Ce qui est automatisé (phase 10)

Ces scénarios tournent à chaque `pytest`, sur de **vrais sockets** : Uvicorn, SQLite et disque réels, client HTTP brut qui joue le téléphone.

| Scénario §16.3 | Test |
|---|---|
| Aller-retour complet, noms Unicode (accents, emoji), collision sans écrasement, hash identique | `tests/e2e/test_real_network.py::test_round_trip_with_unicode_names_collision_and_range_resume` |
| Téléchargement PC → téléphone repris en deux morceaux (`Range`) | idem |
| Redémarrage du PC en plein envoi, même port : seuls les blocs manquants sont renvoyés | `test_server_restart_mid_upload_only_missing_chunks_are_sent` |
| Connexion coupée au milieu d'un bloc : rien n'est confirmé, le bloc est renvoyé ensuite | `test_connection_cut_in_the_middle_of_a_chunk_is_not_recorded` |
| Révocation : 401 immédiat | `test_revoked_phone_is_cut_off_immediately` |
| Espace disque insuffisant : 507 explicite | `test_disk_full_is_reported_clearly` |
| Attaque par DNS rebinding refusée | `test_dns_rebinding_is_refused_on_the_real_server` |

**En vrai navigateur** (`tests/e2e/test_browser.py`). Chrome ou Edge sans interface, en émulation Android (390 × 844), contre le vrai serveur et la page compilée. Le parcours :

1. lien du QR Code ;
2. attente puis approbation ;
3. envoi de 5 blocs (WebAssembly `hash-wasm` sous CSP) ;
4. fichier proposé par le PC ;
5. historique.

Le test échoue sur toute exception JavaScript, violation de CSP ou ressource en erreur. Il est ignoré si aucun navigateur n'est installé ou si la page n'est pas compilée. Pour obtenir des captures :

```bash
npm --prefix apps/web run build
LOCALDROP_SCREENSHOTS=captures .venv/Scripts/pytest tests/e2e/test_browser.py
```

Limites : ni Safari iOS ni vrai lien radio. De plus, `127.0.0.1` est un « secure context », contrairement à l'IP du PC sur le réseau. La matrice manuelle ci-dessous reste donc indispensable.

## Environnements (manuel)

| PC | Téléphone | Navigateur | Réseau |
|---|---|---|---|
| Windows 11 | Android | Chrome | Wi-Fi domestique |
| Windows 11 | Android | Chrome | Hotspot Android |
| Windows 11 | Android | Chrome | Point d'accès mobile du PC |
| Windows 11 | iPhone | Safari | Wi-Fi domestique |
| Windows 11 | iPhone | Safari | Hotspot iPhone |
| Windows 10 | Android ou iPhone | Chrome ou Safari | Wi-Fi domestique |

## Scénarios (pour chaque environnement)

- [ ] Scan du QR Code : la page s'ouvre, puis appairage et approbation sur le PC
- [ ] Appareil refusé, puis révoqué : plus aucun accès
- [ ] Envoi téléphone → PC : petit (< 1 Mio), moyen (~100 Mio), gros (> 1 Gio) ; hash identique
- [ ] Envoi PC → téléphone : petit, moyen, gros (le fichier s'ouvre sur le téléphone)
- [ ] Plusieurs fichiers dans une même sélection, puis annulation de l'un d'eux
- [ ] Noms Unicode (accents, emoji, arabe) et collision de nom : aucun écrasement
- [ ] Coupure du Wi-Fi pendant l'envoi, puis retour : reprise sans renvoi des blocs validés
- [ ] Écran verrouillé ou application changée pendant l'envoi (iOS en particulier) : comportement noté
- [ ] Navigateur fermé pendant l'envoi, puis réouverture et resélection : reprise
- [ ] Redémarrage de LocalDrop pendant un transfert : transfert retrouvé
- [ ] Disque plein : refus propre, aucun fichier corrompu
- [ ] Changement d'IP du PC (activation du point d'accès après le lancement) : QR Code régénéré
- [ ] Pare-feu et profil réseau Public : diagnostic compréhensible
- [ ] iOS < 16 si disponible : l'envoi fonctionne (WebAssembly sous CSP)
- [ ] Fermeture de l'application : arrêt propre, aucun processus résiduel

## Mesures de débit

### Coût côté PC par taille de bloc (loopback, automatisé)

`python -m localdrop.bench --size-mib 128 --repeat 3`

Ce banc démarre un vrai serveur par taille de bloc, puis envoie et télécharge un fichier de 128 Mio. Il garde la meilleure des 3 mesures. Sur loopback, le réseau n'est pas le goulot : ces chiffres mesurent ce que **le PC** peut absorber.

Mesures du 2026-11-20 sur le PC de développement (Windows 11, SSD, antivirus actif) :

| Bloc | Envoi, phase 9 | Envoi, phase 10 | Gain | Téléchargement |
|---|---|---|---|---|
| 1 Mio | 32,2 Mio/s | 51,5 Mio/s | +60 % | ~265 Mio/s |
| 2 Mio | 50,8 Mio/s | 72,2 Mio/s | +42 % | ~265 Mio/s |
| **4 Mio** (défaut) | 69,1 Mio/s | **88,3 Mio/s** | +28 % | ~265 Mio/s |
| 8 Mio | 81,3 Mio/s | 98,7 Mio/s | +21 % | ~265 Mio/s |
| 16 Mio | 86,5 Mio/s | 102,4 Mio/s | +18 % | ~265 Mio/s |

Coût fixe par bloc côté serveur, mesuré par profilage : **21,2 → 12,5 ms**. Deux changements y contribuent :

- un seul commit SQLite par bloc au lieu de deux ;
- les fichiers temporaires restent ouverts entre deux blocs. Sous Windows, fermer un fichier modifié déclenche l'analyse antivirus, qui coûtait environ 7 ms par bloc.

Le hash, le `fsync` par bloc et la vérification finale sont conservés.

Les variations d'une exécution à l'autre atteignent ±10 %. La première mesure d'une série peut être deux fois plus lente si l'antivirus analyse encore le fichier source ; le banc fait un préchauffage pour l'éviter.

**Conclusion : la taille de bloc reste à 4 Mio.** Le PC absorbe environ 88 Mio/s, bien au-delà d'un Wi-Fi domestique (10 à 40 Mio/s en pratique) : le réseau sera le goulot. Des blocs plus gros gagneraient peu, mais coûteraient plus de mémoire au téléphone (chaque bloc est lu et haché en mémoire) et plus de données à renvoyer après une coupure.

### Débit réel (manuel, à remplir)

| Environnement | Taille de bloc | Fichier | Débit moyen | Remarques |
|---|---|---|---|---|
| | 4 Mio | | | |
