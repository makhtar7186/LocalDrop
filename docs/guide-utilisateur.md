# LocalDrop : guide d'utilisation

LocalDrop échange des fichiers entre votre PC Windows et votre téléphone (Android ou iPhone) **sur votre réseau local**. Il n'y a ni cloud, ni compte, ni application à installer sur le téléphone : il suffit de scanner un QR Code.

## Installation

1. Décompressez l'archive `LocalDrop-<version>-windows-x64.zip`, par exemple dans `C:\Programmes\LocalDrop` ou dans vos Documents.
   - Gardez tout le dossier : `LocalDrop.exe` a besoin du dossier `_internal` placé à côté.
2. Lancez `LocalDrop.exe`. Vous pouvez épingler l'icône à la barre des tâches.

Windows peut afficher « Windows a protégé votre ordinateur » : l'application n'est pas signée par un éditeur reconnu. Cliquez sur **Informations complémentaires**, puis sur **Exécuter quand même**.

### La demande du pare-feu Windows

Au premier lancement, Windows demande si LocalDrop peut communiquer sur le réseau.

- Cochez **Réseaux privés** (domicile, point d'accès de votre téléphone).
- Ne cochez **pas** « Réseaux publics », sauf si vous savez pourquoi.

Sans cette autorisation, le téléphone ne pourra pas joindre le PC. Si vous déplacez le dossier de LocalDrop, Windows reposera la question.

## Connecter un téléphone

1. Le PC et le téléphone doivent être sur le **même réseau** : même Wi-Fi, ou le téléphone connecté au point d'accès mobile du PC (ou l'inverse). Les données mobiles 4G/5G ne fonctionnent pas.
2. Sur le PC, l'onglet **Tableau de bord** affiche un QR Code.
3. Scannez-le avec l'**appareil photo** du téléphone, puis ouvrez le lien proposé.
4. Sur le PC, une fenêtre **« Nouvel appareil »** s'ouvre. Vérifiez que le nom est bien celui de votre téléphone, puis cliquez sur **Autoriser**.
   - La touche Entrée **refuse** par sécurité.
   - N'autorisez jamais un appareil que vous ne connaissez pas.
5. Le téléphone affiche « Connecté à <nom du PC> ».

Le QR Code ne sert qu'**une seule fois** : chaque téléphone scanne le QR Code affiché à ce moment-là. Un téléphone autorisé le reste jusqu'à la fin de la session (12 h par défaut), même si vous redémarrez LocalDrop.

## Envoyer des fichiers du téléphone vers le PC

1. Sur le téléphone, touchez **Envoyer**, puis **Choisir des fichiers**.
2. Choisissez un ou plusieurs fichiers. Une barre de progression s'affiche pour chacun.
3. Lorsque « Reçu sur le PC ✓ » apparaît, le fichier est arrivé et a été vérifié. Il se trouve dans `Téléchargements\LocalDrop` (dossier modifiable dans les Paramètres).

**Gardez la page ouverte et l'écran allumé** pendant l'envoi. Sur iPhone surtout, une page en arrière-plan est mise en pause.

Si un fichier du même nom existe déjà, LocalDrop n'écrase rien : le nouveau fichier s'appelle `photo (1).jpg`. Un fichier reçu n'est jamais ouvert automatiquement.

### Après une coupure

- **Wi-Fi coupé un instant** : l'envoi reprend tout seul là où il s'était arrêté.
- **Page fermée ou téléphone redémarré** : rouvrez LocalDrop sur le téléphone. La section « Envois interrompus » indique où l'envoi s'était arrêté. Sélectionnez à nouveau **le même fichier** : seule la partie manquante est envoyée.
- **PC redémarré** : les envois inachevés sont conservés 24 h et reprennent de la même façon.

## Envoyer des fichiers du PC vers le téléphone

1. Sur le PC, dans le Tableau de bord, sélectionnez le téléphone dans la liste **Appareils**.
2. Glissez des fichiers dans la zone **« Glissez des fichiers ici… »** ou cliquez sur **Choisir des fichiers…**.
3. Sur le téléphone, touchez **Recevoir**, puis **Télécharger**. Le navigateur enregistre le fichier, en général dans Téléchargements, ou dans l'app Fichiers sur iPhone.
4. Une fois le fichier bien reçu, touchez **J'ai reçu le fichier** : le PC le marque alors comme livré.

## Historique et paramètres

- **Historique** (PC et téléphone) : tous les transferts, avec recherche par nom.
  - Sur le PC, **Ouvrir le dossier** affiche le fichier dans l'Explorateur, sans l'ouvrir.
  - L'historique est conservé 30 jours par défaut ; les fichiers reçus ne sont jamais supprimés.
- **Paramètres** (PC) : dossier de réception, port, taille des blocs, transferts simultanés, durées de conservation, et la case **« Accepter les connexions du réseau local (téléphones) »**. Les modifications s'appliquent au prochain démarrage.

## Sécurité

- La connexion n'est **pas chiffrée** : utilisez votre réseau domestique ou le point d'accès de votre téléphone ou du PC, et **évitez les Wi-Fi publics** (gare, café, hôtel).
- Chaque téléphone doit être autorisé sur le PC.
  - **Déconnecter** retire immédiatement l'accès à un téléphone.
  - **Fermer la session** déconnecte tous les téléphones et rend le QR Code actuel inutilisable.
- LocalDrop n'accepte que des appareils de votre réseau local et n'envoie rien sur Internet.

## Dépannage

**La page ne s'ouvre pas sur le téléphone après le scan.**

1. Vérifiez que le téléphone est bien sur le même Wi-Fi que le PC, et non en 4G/5G.
2. Au bout d'une minute sans connexion, le Tableau de bord affiche une aide avec une adresse de test. Ouvrez-la dans le navigateur du téléphone :
   - si `{"status":"ok"…}` s'affiche, le réseau fonctionne : rescannez le QR Code ;
   - si rien ne charge, le réseau bloque les échanges entre appareils.
3. Les réseaux d'entreprise, d'hôtel ou « invité » isolent souvent les appareils entre eux. **Solution** : activez le point d'accès mobile du PC (Paramètres Windows > Réseau et Internet > Point d'accès sans fil mobile) et connectez-y le téléphone. LocalDrop détecte la nouvelle adresse et affiche un nouveau QR Code.
4. Si Windows classe votre réseau en « Public », le pare-feu peut bloquer LocalDrop. S'il s'agit de votre réseau, passez-le en « Privé » (Paramètres Windows > Réseau et Internet > propriétés du réseau).

**« Connexions des téléphones désactivées ».** Cochez « Accepter les connexions du réseau local (téléphones) » dans les Paramètres, puis redémarrez LocalDrop.

**« Session terminée, scannez à nouveau le QR Code ».** Le téléphone a été déconnecté, ou la session a expiré : scannez le QR Code actuel.

**« Espace disque insuffisant sur le PC ».** Libérez de la place, ou choisissez un autre dossier de réception dans les Paramètres.

**Le port est déjà utilisé.** Un autre logiciel utilise le port 8765 : choisissez un autre port dans les Paramètres.

**LocalDrop est déjà ouvert.** Un second lancement remet simplement la fenêtre existante au premier plan.

## Où sont mes données ?

| Quoi | Où |
|---|---|
| Fichiers reçus | `%USERPROFILE%\Downloads\LocalDrop` (modifiable) |
| Base, journaux, paramètres | `%LOCALAPPDATA%\LocalDrop` |
| Fichiers en cours de réception | `Downloads\LocalDrop\.localdrop-tmp` (dossier caché, nettoyé automatiquement) |

**Mettre à jour** : fermez LocalDrop, remplacez le dossier de l'application par la nouvelle version, puis relancez-la. Vos données, votre historique et vos paramètres sont conservés, et la base est sauvegardée automatiquement avant toute mise à jour de son format.

**Désinstaller** : supprimez le dossier de l'application. Pour effacer aussi vos données, supprimez `%LOCALAPPDATA%\LocalDrop`. Les fichiers reçus restent dans Téléchargements.

**Vérifier l'installation** : dans une invite de commandes ouverte dans le dossier de LocalDrop, lancez `start /wait LocalDrop.exe --self-test`, puis `echo %ERRORLEVEL%`. `0` signifie que tout fonctionne. Le détail est écrit dans `%TEMP%\localdrop-selftest.json`. Ce test n'utilise ni vos données ni le réseau.
