# ADR-002 : Serveur local hébergé par l'application Windows

- Statut : Accepté
- Date : 2026-11-20
- Exigences liées : FR-001, §6.1, §8.6, §12.2-11

## Contexte
Le téléphone doit joindre le PC sans cloud. Le PC est l'appareil stable, doté d'un disque et d'une interface de contrôle.

## Décision
L'application PySide6 démarre le serveur Uvicorn/FastAPI dans un **thread de travail** du même processus et pilote son arrêt. Le serveur n'écoute que sur les IPv4 privées sélectionnées et `127.0.0.1`, jamais sur `0.0.0.0` par défaut. Les actions d'administration (approbation, révocation, paramètres, transferts sortants) passent par des appels en processus, pas par HTTP.

## Options étudiées
- **Service Windows séparé** : survit à la fermeture de l'UI, mais installation avec droits administrateur et complexité accrue. Hors MVP.
- **Sous-processus** : meilleure isolation des crashs, mais communication inter-processus nécessaire. À reconsidérer si le thread pose problème.

## Conséquences
- Il ne faut jamais bloquer la boucle Qt et toujours passer par des signaux pour mettre à jour l'UI.
- L'arrêt propre (§20-10) est de la responsabilité du desktop.
