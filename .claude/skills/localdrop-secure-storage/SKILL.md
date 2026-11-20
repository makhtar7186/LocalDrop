---
name: localdrop-secure-storage
description: Stockage disque sécurisé de LocalDrop sous Windows (assainissement des noms de fichiers, anti-traversée de répertoires, collisions sans écrasement, fichiers temporaires, déplacement atomique, espace disque, nettoyage). À utiliser pour tout code dans infrastructure/storage ou qui construit un chemin à partir d'une donnée client.
---

# Stockage sécurisé

Référence : cahier des charges §8.4, §12.2 (points 8 et 9), §13.

## Règle absolue

Le nom envoyé par le client est **une donnée d'affichage**, jamais un chemin. Le serveur construit lui-même tous les chemins (§8.4, §13.2).

## Assainissement du nom (`sanitize_filename`, fonction pure testée avec Hypothesis)

1. Normaliser en Unicode NFC.
2. Garder seulement le dernier segment après découpage sur `/` **et** `\`.
3. Supprimer les caractères de contrôle (< 0x20, 0x7F) et `< > : " / \ | ? *`.
4. Retirer les points et espaces en fin de nom (Windows les ignore silencieusement).
5. Refuser ou préfixer les noms réservés, insensible à la casse, **y compris avec extension** : `CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9` (ex. `con.txt` → `_con.txt`).
6. Tronquer à 255 caractères au maximum en préservant l'extension. Vérifier aussi la longueur du chemin complet.
7. Nom vide après nettoyage (`.`, `..`, chaîne vide) → `fichier`.

## Confinement

```python
final = (root / safe_name).resolve()
if not final.is_relative_to(root.resolve()):
    raise UnsafePath(...)
```
Appliquer ce contrôle à **chaque** chemin dérivé : temporaire, final, dossier configuré.

## Fichiers temporaires

- Nom généré par le serveur : `<transfer_id>.part`. Il ne dérive jamais du nom client.
- Placer le dossier temporaire **sur le même volume que la destination** (ex. `<destination>/.localdrop-tmp/`) pour que le déplacement final soit atomique, même si l'utilisateur choisit un dossier sur un autre lecteur.
- Avant création, vérifier l'espace libre avec `shutil.disk_usage(temp_dir).free >= total_size + marge`. Sinon, erreur `INSUFFICIENT_DISK_SPACE` (507) sans rien écrire. Gérer aussi `OSError` (ENOSPC) en cours d'écriture : le transfert passe en état récupérable, aucun fichier existant n'est touché.

## Publication finale sans écrasement (FR-028)

- Candidats : `nom.ext`, `nom (1).ext`, `nom (2).ext`, …
- Utiliser `os.rename` : sous Windows, il lève `FileExistsError` si la cible existe. Boucler sur les candidats. **Ne pas utiliser `os.replace`** pour la publication : il écrase.
- Tester explicitement la course entre deux finalisations vers le même nom.

## Après réception

- Ne **jamais** ouvrir ni exécuter un fichier reçu (`os.startfile`, `subprocess`…) (§12.2-9). « Ouvrir le dossier » = `explorer /select,<chemin>` uniquement.
- Recommandé : ajouter le flux `Zone.Identifier` (`[ZoneTransfer]\nZoneId=3`) au fichier publié pour que Windows le traite comme provenant du réseau. Échec non bloquant.

## Arborescence et données

- Fichiers reçus : `%USERPROFILE%\Downloads\LocalDrop` par défaut, configurable (FR-030, FR-031).
- Base, logs et état d'exécution : `%LOCALAPPDATA%\LocalDrop`. Jamais dans le dépôt.

## Nettoyage (§13.3, FR-035)

Au démarrage puis périodiquement :
- supprimer les `.part` des transferts expirés ou terminaux, ainsi que les `.part` orphelins sans ligne en base ;
- appliquer la politique de conservation de l'historique ;
- **ne jamais supprimer un fichier final** : le nettoyage ne travaille que dans le dossier temporaire.
