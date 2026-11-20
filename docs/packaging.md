# Construire et publier LocalDrop pour Windows

Destiné aux mainteneurs. Pour les utilisateurs, voir [guide-utilisateur.md](guide-utilisateur.md). Choix et alternatives : [ADR-008](decisions/ADR-008-distribution-windows.md).

## Prérequis

- Windows 10 ou 11 64 bits, Python 3.12, Node.js 20+.
- Environnement de développement complet, PyInstaller compris :
  ```powershell
  py -3.12 -m venv .venv
  .venv\Scripts\pip install -r requirements-dev.txt
  npm --prefix apps/web ci
  ```

## Construction complète (recommandée)

```powershell
.venv\Scripts\python scripts\build_windows.py
```

Le script s'arrête à la première erreur. Il enchaîne :

1. le build de l'interface web (`--clean-web` pour repartir d'un `npm ci`) ;
2. ruff, mypy, pytest, puis lint, typage et tests web (`--skip-checks` pour les sauter, déconseillé pour une publication) ;
3. `pyinstaller localdrop.spec --noconfirm --clean` ;
4. l'**autotest dans l'exécutable gelé** (`LocalDrop.exe --self-test`) ;
5. le **test de fumée** de l'application réelle, avec sa fenêtre, en isolement (dossier temporaire, loopback seul, donc pas de fenêtre du pare-feu) :
   - démarrage, appairage, envoi et téléchargement vérifiés par SHA-256 ;
   - fermeture normale, sans processus résiduel ;
   - relance avec historique retrouvé ;
6. l'archive `dist\LocalDrop-<version>-windows-x64.zip`, avec `LISEZ-MOI.md` (le guide utilisateur) et le fichier `.sha256`.

Durée indicative : 3 à 4 minutes, dont la moitié pour PyInstaller.

## Étapes séparées

```powershell
npm --prefix apps/web run build
.venv\Scripts\pyinstaller localdrop.spec --noconfirm --clean     # -> dist\LocalDrop\LocalDrop.exe
start /wait dist\LocalDrop\LocalDrop.exe --self-test rapport.json  # code 0 = OK
.venv\Scripts\python scripts\smoke_test_exe.py                     # application réelle
.venv\Scripts\python packaging\make_icon.py                        # régénère packaging\localdrop.ico
```

## Avant de publier

- [ ] Numéro de version mis à jour dans `backend/src/localdrop/__init__.py` **et** `pyproject.toml` (un test vérifie qu'ils sont identiques), ainsi que dans `apps/web/package.json`.
- [ ] `scripts\build_windows.py` réussi sans `--skip-checks`.
- [ ] Archive testée sur un **Windows propre**, sans Python ni Node (VM ou autre PC) :
  - décompression, lancement, fenêtre du pare-feu (« Réseaux privés ») ;
  - QR Code scanné par un vrai téléphone.
- [ ] Lignes de la [matrice e2e](testing/e2e-matrix.md) exécutées avec de vrais téléphones (Android **et** iPhone).
- [ ] Mise à jour depuis la version précédente : remplacer le dossier ; l'historique est conservé et une sauvegarde de la base est créée dans `%LOCALAPPDATA%\LocalDrop\database\backups`.
- [ ] Publication de l'archive **et** de son `.sha256`.

## Problèmes connus

- **« Windows a protégé votre ordinateur » (SmartScreen)** : l'exécutable n'est pas signé. Il faudra un certificat de signature de code avant une diffusion large.
- **Antivirus** : les exécutables PyInstaller sont parfois signalés à tort. UPX est désactivé pour limiter ce risque. En cas de signalement, soumettre le fichier à l'éditeur de l'antivirus.
- **Le pare-feu redemande l'autorisation** dès que le dossier change d'emplacement : la règle est liée au chemin de l'exécutable.
- **Ajouter une ressource** lue à l'exécution : l'ajouter à `datas` dans `localdrop.spec`, la résoudre dans `core/paths.py` et la vérifier dans l'autotest (`apps/desktop/src/localdrop_desktop/selftest.py`).
- **Ajouter une dépendance chargée dynamiquement** (plugin, `importlib`) : la déclarer dans `hiddenimports`. L'autotest gelé révèle ces oublis.
