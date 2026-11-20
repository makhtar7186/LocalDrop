# ADR-008 : distribution Windows en dossier PyInstaller, livré en archive zip

- Statut : Accepté
- Date : 2026-11-20
- Exigences liées : §17.2, §17.3, §16.4 (« l'application peut être construite en exécutable Windows »)

## Contexte

L'application doit être livrée en exécutable Windows qui embarque Python, PySide6, l'interface web compilée et les migrations Alembic, sans exiger Python ni Node sur le poste. Les données restent dans le profil de l'utilisateur. La mise à jour se fait par remplacement contrôlé de l'application.

## Décision

- **PyInstaller, mode « onedir », fenêtré** (`localdrop.spec`) : `LocalDrop.exe` accompagné d'un dossier `_internal`.
- **Sans UPX**, et **sans signature de code** pour cette version candidate.
- **Livraison en archive zip portable** : `dist/LocalDrop-<version>-windows-x64.zip`, accompagnée de son SHA-256 et du guide utilisateur (`LISEZ-MOI.md`). Pas d'installateur.
- **Ressources embarquées** : `web/`, `migrations/` (copiées telles quelles, car Alembic les charge depuis le disque) et `localdrop.ico`. Elles sont résolues uniquement par `core/paths.py` (`sys._MEIPASS`).
- **Autotest intégré** : `LocalDrop.exe --self-test [rapport.json]`. Il vérifie, dans un dossier temporaire et en loopback, les ressources, la migration, le serveur, la page, le WebSocket, un envoi et un téléchargement réels, et Qt. Le résultat est donné par le code de sortie et un rapport JSON, car l'exécutable n'a pas de console.
- **Construction reproductible** : `scripts/build_windows.py` enchaîne le build web, les contrôles, PyInstaller, l'autotest gelé, le test de fumée de l'application réelle (`scripts/smoke_test_exe.py`) et l'archive.
- **Version unique** : `localdrop.__version__`, identique à `pyproject.toml` (vérifié par un test). Elle est reprise dans la ressource de version de l'exécutable.

## Options étudiées

- **Onefile** : un seul `.exe`, mais extraction dans `%TEMP%` à chaque lancement (démarrage lent), plus de faux positifs antivirus, et le chemin change à chaque lancement. Or la règle du pare-feu Windows est liée au chemin de l'exécutable : l'autorisation serait redemandée.
- **Installateur Inno Setup** : raccourcis et désinstallation propres. Il n'est pas installé sur le poste de construction, et un script d'installateur non testé ne doit pas être livré. C'est l'évolution naturelle, qui réutiliserait le dossier onedir tel quel.
- **Nuitka ou cx_Freeze** : aucun gain décisif sur le MVP, et moins de hooks prêts pour PySide6 et Uvicorn.
- **UPX** : archive plus petite, mais faux positifs antivirus fréquents.

## Conséquences

- Taille : environ 140 Mo décompressé, dont l'essentiel vient de Qt. Les modules Qt jamais importés (WebEngine, QML, Multimedia…) sont exclus.
- SmartScreen affiche « Windows a protégé votre ordinateur » tant que l'exécutable n'est pas signé. Le guide utilisateur l'explique. La signature de code devient nécessaire avant une diffusion large.
- Le pare-feu redemande l'autorisation si le dossier est déplacé. Le guide recommande un emplacement stable.
- Mise à jour : remplacer le dossier. Les données dans `%LOCALAPPDATA%\LocalDrop` sont conservées, et la base est sauvegardée avant migration (§17.3).
- Toute nouvelle ressource lue à l'exécution doit être ajoutée à `datas` dans `localdrop.spec`, résolue par `core/paths.py` et vérifiée par l'autotest.
