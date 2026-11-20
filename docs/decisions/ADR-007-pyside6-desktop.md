# ADR-007 : PySide6 pour le desktop

- Statut : Accepté
- Date : 2026-11-20
- Exigences liées : FR-040, §8.6, §14.2

## Contexte
L'application Windows doit héberger le serveur, afficher le QR Code, gérer les approbations et superviser les transferts, en Python comme le backend.

## Décision
PySide6 (Qt 6, licence LGPL). Serveur dans un thread de travail, pont des événements vers des signaux Qt, modèles `QAbstractItemModel` pour les listes.

## Options étudiées
- **Tkinter** : léger, mais rendu daté et composants limités (tableaux, thème sombre).
- **Electron / Tauri** : UI web réutilisable, mais second runtime (Node/Rust) et packaging plus lourd.
- **Desktop en WebView (pywebview)** : réutilise React, mais intégration système (zone de notification, glisser-déposer, dialogues) moins maîtrisée.

## Conséquences
- Exécutable PyInstaller plus volumineux, à cause de Qt.
- Les tests UI passent par `pytest-qt`.
