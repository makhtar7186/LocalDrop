---
name: localdrop-desktop-pyside6
description: Application Windows PySide6 de LocalDrop (cycle de vie du serveur Uvicorn embarqué dans un thread, pont événements backend → signaux Qt, QR Code, approbation des appareils, écrans Dashboard/Transfers/History/Settings, arrêt propre, instance unique). À utiliser pour tout code dans apps/desktop/.
---

# Application desktop PySide6

Référence : cahier des charges §8.6, §14.1, §14.2, FR-001, FR-006, FR-011, FR-012, FR-040.

## Serveur embarqué

- `uvicorn.Server(config)` exécuté dans un **thread de travail** dédié (`threading.Thread`, daemon=False), jamais dans le thread Qt.
- Les versions récentes d'Uvicorn n'installent pas de gestionnaires de signaux hors du thread principal. Avec une version plus ancienne, surcharger `install_signal_handlers`.
- Arrêt : `server.should_exit = True`, puis `join(timeout)`. Si le délai expire, `force_exit = True`.
- Le thread serveur possède sa propre boucle asyncio. Pour qu'un contrôleur desktop appelle un service async : `asyncio.run_coroutine_threadsafe(coro, server_loop)`. Le résultat est récupéré **hors** du thread GUI, puis renvoyé par signal Qt.
- Les opérations d'administration (approuver, révoquer, créer un transfert sortant, modifier les paramètres) passent par une façade `LocalController` en processus, pas par HTTP.

## Pont backend → Qt

- Le bus d'événements backend (les mêmes événements que le WS) est relayé vers un `QObject` « bridge » qui émet des `Signal`. Les connexions inter-threads de Qt sont en file (queued) et donc sûres.
- **Ne jamais toucher un widget depuis le thread serveur.**
- Les modèles de liste (transferts, appareils, historique) sont des `QAbstractListModel` / `QAbstractTableModel` mis à jour par signaux. Limiter les rafraîchissements de progression.

## Écrans (§14.2)

- **Dashboard** : état du serveur, QR Code, URL(s) avec bouton copier, appareils connectés, démarrer/arrêter, zone de dépôt de fichiers (drag & drop → transferts sortants).
- **Transfers** : entrants et sortants, progression, débit, taille, pause/reprise/annulation.
- **History** : date, nom, direction, taille, statut, recherche et filtres, « Ouvrir le dossier » (`explorer /select,` uniquement, jamais le fichier lui-même).
- **Settings** : dossier de réception, port, taille de bloc, transferts simultanés, expirations, démarrage automatique (optionnel).
- Demande d'approbation d'un appareil : notification et dialogue non bloquant (nom, plateforme, IP), avec Accepter / Refuser.
- Texte en français, thème sombre par défaut, navigation clavier, contrastes suffisants.
- Erreurs réseau et pare-feu affichées clairement, avec l'aide de diagnostic (skill `localdrop-network`).

## Cycle de vie

- **Instance unique** (`QLockFile` dans `%LOCALAPPDATA%\LocalDrop`). Une seconde instance réactive la fenêtre existante (`QLocalServer`/`QLocalSocket`).
- Fermeture (`closeEvent` et `aboutToQuit`) dans cet ordre :
  1. refuser les nouveaux transferts ;
  2. passer les transferts actifs en `paused` (reprise possible) ;
  3. fermer les WS ;
  4. arrêter Uvicorn ;
  5. libérer le moteur SQLAlchemy ;
  6. vider les logs.
- Icône de zone de notification facultative. Si la fermeture de fenêtre réduit l'application dans la zone, l'indiquer clairement.

## QR Code

`qrcode`, rendu en matrice et dessiné avec `QPainter` (ou SVG via `QSvgRenderer`). Il est régénéré sur rotation du secret et sur `server.network_changed`.

## Tests

`pytest-qt` (`qtbot`) pour les contrôleurs et le bridge. Les services backend sont simulés. Tester explicitement l'arrêt propre : démarrage, arrêt, le thread se termine, aucun handle restant.
