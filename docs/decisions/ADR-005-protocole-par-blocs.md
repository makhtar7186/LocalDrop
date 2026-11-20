# ADR-005 : Protocole de transfert par blocs

- Statut : Accepté (points ouverts listés plus bas)
- Date : 2026-11-20
- Exigences liées : FR-024 à FR-029, §5.1, §9

## Contexte
Les transferts doivent supporter des fichiers volumineux sur un Wi-Fi instable et reprendre sans renvoyer les données déjà validées.

## Décision
- Blocs de taille fixe (4 Mio par défaut, configurable), un bloc en vol par transfert, 2 transferts simultanés.
- `PUT /api/v1/transfers/{id}/chunks/{index}` avec corps brut et en-tête `X-Chunk-SHA256`. Le bloc est confirmé seulement après écriture positionnelle, `fsync`, vérification du hash et commit en base.
- Idempotence : même index et même hash donnent un succès sans réécriture ; même index et hash différent donnent 409.
- Le hash SHA-256 global est calculé incrémentalement par le client et transmis à `POST /complete`. Le serveur le recalcule avant publication.
- Machine à états du §8.3, avec transitions en base par update conditionnel.

## Options étudiées
- **Upload multipart unique** : pas de reprise.
- **tus.io** : protocole standard de reprise, mais ajoute une dépendance et ne couvre pas le sens PC → téléphone ni notre machine à états.

## Points ouverts
- Accusé de réception fiable pour les téléchargements sortants.
- Authentification des liens de téléchargement (ticket court).

## Conséquences
Les tests d'interruption, de reprise et de concurrence sur `/complete` sont obligatoires (§16.2).
