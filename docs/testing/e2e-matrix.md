# Matrice de tests end-to-end (§16.3)

À exécuter avant chaque version candidate. Noter : version, date, résultat (OK / KO + ticket), débit mesuré.

## Environnements

| PC | Téléphone | Navigateur | Réseau |
|---|---|---|---|
| Windows 11 | Android | Chrome | Wi-Fi domestique |
| Windows 11 | Android | Chrome | Hotspot Android |
| Windows 11 | iPhone | Safari | Wi-Fi domestique |
| Windows 11 | iPhone | Safari | Hotspot iPhone |
| Windows 10 | Android ou iPhone | Chrome ou Safari | Wi-Fi domestique |

## Scénarios (pour chaque environnement)

- [ ] Scan du QR Code : la page s'ouvre, puis appairage et approbation sur le PC
- [ ] Appareil refusé, puis révoqué : plus aucun accès
- [ ] Envoi téléphone → PC : petit (< 1 Mio), moyen (~100 Mio), gros (> 1 Gio) ; hash identique
- [ ] Envoi PC → téléphone : petit, moyen, gros
- [ ] Plusieurs fichiers dans une même sélection
- [ ] Noms Unicode (accents, emoji, arabe) et collision de nom : aucun écrasement
- [ ] Coupure du Wi-Fi pendant l'envoi, puis retour : reprise sans renvoi des blocs validés
- [ ] Navigateur fermé pendant l'envoi, puis réouverture et resélection : reprise
- [ ] Redémarrage de LocalDrop pendant un transfert : transfert retrouvé
- [ ] Disque plein : refus propre, aucun fichier corrompu
- [ ] Changement d'IP du PC : QR Code régénéré
- [ ] Pare-feu et profil réseau Public : diagnostic compréhensible
- [ ] Fermeture de l'application : arrêt propre, aucun processus résiduel

## Mesures de débit

| Environnement | Taille de bloc | Débit moyen | Remarques |
|---|---|---|---|
| | | | |
