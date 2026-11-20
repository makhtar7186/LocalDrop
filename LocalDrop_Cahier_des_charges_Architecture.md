# LocalDrop

## Cahier des charges et architecture logicielle

**Version :** 1.0\
**Statut :** Document de référence pour la conception et
l'implémentation\
**Plateforme principale :** Windows 10/11\
**Clients mobiles :** Android et iOS (navigateur web)\
**Mode de fonctionnement :** Réseau local, sans service cloud\
**Langue de l'interface :** Français dans le MVP, internationalisation
prévue

------------------------------------------------------------------------

# 1. Résumé exécutif

LocalDrop est une application de partage de fichiers entre un ordinateur
Windows et un smartphone. L'utilisateur lance l'application sur son PC,
scanne un QR Code avec son téléphone, puis transfère des fichiers dans
les deux sens depuis une interface web mobile.

Le transfert s'effectue directement sur le réseau local : Wi-Fi ou
partage de connexion (hotspot), dès lors que les deux appareils peuvent
communiquer entre eux. Aucun compte, service cloud ou stockage distant
n'est requis.

**Promesse produit :** scanner, connecter, transférer.

## 1.1 Décisions produit confirmées

  -----------------------------------------------------------------------
  Sujet                               Décision
  ----------------------------------- -----------------------------------
  Système hôte                        Windows

  Téléphones                          Android et iOS

  Connexion                           Wi-Fi et hotspot

  Appairage                           QR Code

  Transfert                           Bidirectionnel

  Stockage des fichiers reçus sur PC  Dossier LocalDrop configurable,
                                      valeur par défaut dans
                                      Téléchargements

  Reprise après interruption          Oui

  Utilisateurs                        Usage personnel, avec possibilité
                                      de plusieurs appareils mobiles dans
                                      une session

  Cloud                               Aucun

  Compte utilisateur                  Aucun
  -----------------------------------------------------------------------

## 1.2 Principes directeurs

1.  **Local-first :** les fichiers restent sur les appareils et le
    réseau local.
2.  **Sécurité par défaut :** aucune session sans autorisation
    explicite.
3.  **Résilience :** un transfert interrompu doit pouvoir reprendre sans
    renvoyer les blocs déjà validés.
4.  **Modularité :** interface, API, réseau, stockage et moteur de
    transfert restent découplés.
5.  **Maintenabilité :** typage, tests automatisés, migrations,
    journalisation et documentation.
6.  **Simplicité d'utilisation :** l'utilisateur ne doit pas avoir à
    saisir une adresse IP manuellement dans le parcours normal.

------------------------------------------------------------------------

# 2. Contexte, problème et objectifs

## 2.1 Problème

L'échange ponctuel de documents, photos, vidéos et autres fichiers entre
un PC et un téléphone conduit souvent à utiliser une messagerie ou un
stockage cloud. Ces méthodes ajoutent des étapes, peuvent nécessiter
Internet, peuvent compresser certains médias et impliquent un service
tiers.

## 2.2 Objectifs

-   Établir rapidement une connexion entre le PC et le téléphone.
-   Envoyer des fichiers du PC vers le téléphone.
-   Envoyer des fichiers du téléphone vers le PC.
-   Transférer plusieurs fichiers et des fichiers volumineux.
-   Afficher l'état, la vitesse et la progression des transferts.
-   Reprendre un transfert après une coupure réseau ou un redémarrage.
-   Conserver les fichiers reçus dans un emplacement local configurable.
-   Ne dépendre d'aucun service cloud.

## 2.3 Hors périmètre du MVP

-   Synchronisation automatique permanente de dossiers.
-   Transfert via Internet entre réseaux différents.
-   Comptes, authentification distante et partage public.
-   Application mobile native.
-   Transfert direct téléphone-à-téléphone.
-   Synchronisation du presse-papiers.
-   Gestion collaborative ou multi-utilisateur avec rôles complexes.

Ces éléments pourront être étudiés après stabilisation du produit de
base.

------------------------------------------------------------------------

# 3. Utilisateurs et parcours

## 3.1 Utilisateur cible

Une personne disposant d'un PC Windows et d'un smartphone Android ou
iOS, connectés au même réseau local ou à un hotspot permettant les
communications entre clients.

## 3.2 Parcours nominal

1.  L'utilisateur démarre LocalDrop sur Windows.
2.  Le service local démarre et détecte les interfaces réseau
    disponibles.
3.  L'application affiche un QR Code de session temporaire.
4.  L'utilisateur scanne le QR Code avec l'appareil photo du téléphone.
5.  Le navigateur ouvre l'interface mobile.
6.  L'utilisateur confirme l'appairage sur le PC, si cette validation
    est activée.
7.  Le téléphone est associé à la session.
8.  L'utilisateur sélectionne des fichiers à envoyer ou à télécharger.
9.  La progression est affichée en temps réel.
10. À la fin, l'intégrité du fichier est vérifiée et l'historique est
    actualisé.

## 3.3 Parcours en cas de problème

-   **QR Code inaccessible :** proposer l'adresse locale et un code de
    session saisi manuellement.
-   **Réseau isolé :** expliquer que le point d'accès empêche
    probablement la communication entre appareils.
-   **Session expirée :** demander un nouveau scan.
-   **Transfert interrompu :** conserver l'état temporaire et proposer
    la reprise.
-   **Espace disque insuffisant :** refuser proprement le transfert
    avant ou pendant l'écriture, sans corrompre les fichiers existants.

------------------------------------------------------------------------

# 4. Exigences fonctionnelles

Les exigences sont identifiées afin de faciliter leur traçabilité dans
les tickets et les tests.

## 4.1 Démarrage et réseau

  -----------------------------------------------------------------------
  ID                      Exigence                Priorité
  ----------------------- ----------------------- -----------------------
  FR-001                  Démarrer et arrêter le  Must
                          serveur local depuis    
                          l'application Windows   

  FR-002                  Détecter les interfaces Must
                          réseau et adresses IPv4 
                          privées utilisables     

  FR-003                  Détecter les            Must
                          changements d'adresse   
                          IP et actualiser les    
                          points d'accès          

  FR-004                  Générer un QR Code      Must
                          contenant une URL       
                          locale et un secret de  
                          session temporaire      

  FR-005                  Permettre une connexion Should
                          manuelle par URL/code   
                          en cas de besoin        

  FR-006                  Afficher clairement     Must
                          l'état du serveur et    
                          les erreurs réseau      
  -----------------------------------------------------------------------

## 4.2 Appairage et appareils

  -----------------------------------------------------------------------
  ID                      Exigence                Priorité
  ----------------------- ----------------------- -----------------------
  FR-010                  Authentifier un         Must
                          appareil avec un jeton  
                          à durée limitée         

  FR-011                  Permettre la validation Must
                          ou le refus d'un nouvel 
                          appareil depuis le PC   

  FR-012                  Afficher les appareils  Must
                          connectés et leur état  

  FR-013                  Permettre la révocation Must
                          d'un appareil           

  FR-014                  Expirer les sessions et Must
                          invalider les anciens   
                          QR Codes                
  -----------------------------------------------------------------------

## 4.3 Transferts

  -----------------------------------------------------------------------
  ID                      Exigence                Priorité
  ----------------------- ----------------------- -----------------------
  FR-020                  Transférer des fichiers Must
                          du PC vers le téléphone 

  FR-021                  Transférer des fichiers Must
                          du téléphone vers le PC 

  FR-022                  Accepter plusieurs      Must
                          fichiers dans une même  
                          sélection               

  FR-023                  Accepter tout type de   Must
                          fichier, sous réserve   
                          des limites de sécurité 
                          et de stockage          

  FR-024                  Afficher progression,   Must
                          débit, taille et état   
                          du transfert            

  FR-025                  Annuler un transfert    Must

  FR-026                  Reprendre un transfert  Must
                          interrompu              

  FR-027                  Vérifier l'intégrité    Must
                          des fichiers reçus      

  FR-028                  Éviter l'écrasement     Must
                          silencieux d'un fichier 
                          existant                

  FR-029                  Permettre le            Must
                          téléchargement d'un     
                          fichier depuis le       
                          navigateur mobile       
  -----------------------------------------------------------------------

## 4.4 Stockage et historique

  -----------------------------------------------------------------------
  ID                      Exigence                Priorité
  ----------------------- ----------------------- -----------------------
  FR-030                  Configurer le dossier   Must
                          de réception Windows    

  FR-031                  Utiliser un dossier     Must
                          LocalDrop par défaut    
                          sous le profil          
                          utilisateur             

  FR-032                  Enregistrer les         Must
                          fichiers sous un nom    
                          sûr et éviter les       
                          traversées de           
                          répertoires             

  FR-033                  Conserver les           Must
                          métadonnées des         
                          transferts dans SQLite  

  FR-034                  Afficher et filtrer     Should
                          l'historique            

  FR-035                  Nettoyer les données    Must
                          temporaires expirées    
                          selon une politique     
                          configurable            
  -----------------------------------------------------------------------

## 4.5 Interface

  -----------------------------------------------------------------------
  ID                      Exigence                Priorité
  ----------------------- ----------------------- -----------------------
  FR-040                  Fournir un tableau de   Must
                          bord Windows            

  FR-041                  Fournir une interface   Must
                          mobile responsive       
                          accessible par          
                          navigateur              

  FR-042                  Afficher les transferts Must
                          en temps réel           

  FR-043                  Gérer les états vide,   Must
                          chargement, erreur et   
                          hors connexion          

  FR-044                  Permettre la copie de   Should
                          l'URL locale et         
                          l'affichage du QR Code  
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 5. Exigences non fonctionnelles

## 5.1 Performance

-   Utiliser le streaming et l'écriture par blocs : ne jamais charger un
    fichier entier en mémoire.
-   Rendre configurables la taille des blocs et le nombre de transferts
    simultanés.
-   Fournir une progression fiable basée sur les octets confirmés par le
    serveur.
-   Maintenir l'interface réactive pendant les transferts.
-   Mesurer le débit réel lors des tests sur Wi-Fi et hotspot.

Valeurs initiales à valider par benchmark : - Taille d'un bloc : 4
Mio. - Transferts simultanés : 2 à 3. - Taille maximale : configurable,
limitée principalement par l'espace disque et les capacités du
navigateur. - Conservation d'un transfert interrompu : 24 heures par
défaut, configurable.

Ces valeurs sont des paramètres initiaux, pas des garanties de
performance.

## 5.2 Fiabilité

-   Les métadonnées de transfert doivent survivre au redémarrage du
    processus.
-   Un bloc déjà validé ne doit pas être écrit une seconde fois de
    manière incorrecte.
-   Un fichier final n'est publié dans le dossier de réception qu'après
    validation complète.
-   Les opérations de finalisation doivent être atomiques autant que
    possible.
-   Une erreur doit produire un état explicite et récupérable.

## 5.3 Compatibilité

-   Windows 10 et Windows 11, sous réserve des versions encore prises en
    charge.
-   Android via Chrome ou navigateur compatible avec l'API File.
-   iOS via Safari.
-   Interface adaptée aux petits écrans et aux orientations
    portrait/paysage.

**Limitation à prendre en compte :** les navigateurs mobiles,
particulièrement sur iOS, peuvent suspendre une page en arrière-plan. Le
MVP doit privilégier une page active pendant l'envoi et expliquer à
l'utilisateur qu'il doit garder le navigateur ouvert. Les
téléchargements et l'accès aux fichiers dépendent aussi des capacités du
navigateur et du système mobile.

## 5.4 Maintenabilité

-   Séparation stricte des couches.
-   Contrats API versionnés.
-   Modèles et schémas typés.
-   Migrations de base de données.
-   Tests unitaires, d'intégration et end-to-end.
-   Analyse statique et formatage automatisés.
-   Configuration centralisée.
-   Documentation des décisions d'architecture (ADR).

------------------------------------------------------------------------

# 6. Architecture cible

## 6.1 Décision d'architecture

Adopter un **monolithe modulaire** exécuté localement sur Windows,
plutôt que des microservices.

Cette approche réduit la complexité de déploiement et de maintenance
pour un outil personnel, tout en conservant des frontières internes
claires entre les domaines.

Le processus Python héberge : - l'API HTTP ; - le canal WebSocket ; - le
moteur de transfert ; - la gestion des sessions ; - l'accès SQLite ; -
le serveur des ressources web compilées.

L'application PySide6 contrôle le cycle de vie du serveur et présente
l'interface desktop.

Le smartphone est un client web : aucune installation mobile n'est
nécessaire.

## 6.2 Vue logique

``` text
+-------------------------------------------------------+
|                    PC WINDOWS                         |
|                                                       |
|  +--------------------+     +----------------------+  |
|  | Desktop UI         |     | Local Application    |  |
|  | PySide6            |<--->| Controller            |  |
|  +--------------------+     +----------+-----------+  |
|                                        |              |
|                             +----------v-----------+  |
|                             | FastAPI Application  |  |
|                             |                      |  |
|                             | REST API             |  |
|                             | WebSocket            |  |
|                             | Static Web UI        |  |
|                             +----------+-----------+  |
|                                        |              |
|           +----------------------------+----------+   |
|           |            |             |            |   |
|     +-----v----+ +-----v------+ +----v-----+ +----v--+|
|     | Sessions | | Transfers  | | Storage  | |Network||
|     | Service  | | Engine     | | Service  | |Service||
|     +----------+ +------------+ +----------+ +-------+|
|           |            |             |                 |
|     +-----v------------v-------------v------+          |
|     | SQLite metadata + local file system   |          |
|     +---------------------------------------+          |
+---------------------------+---------------------------+
                            |
                   Wi-Fi / Hotspot local
                            |
                 +----------v-----------+
                 | Smartphone           |
                 | Safari / Chrome      |
                 | React + TypeScript  |
                 +---------------------+
```

## 6.3 Flux de données

### Téléphone vers PC

1.  Le navigateur crée un transfert via l'API.
2.  Le serveur crée un identifiant et un manifeste.
3.  Le navigateur envoie les blocs par requêtes HTTP.
4.  Le serveur valide chaque bloc et l'écrit dans un fichier temporaire.
5.  La progression est publiée via WebSocket.
6.  Le serveur vérifie la taille et le SHA-256 final.
7.  Le fichier est déplacé vers le dossier de réception.
8.  Le transfert passe à l'état `completed`.

### PC vers téléphone

1.  L'interface desktop crée un transfert sortant.
2.  Le serveur prépare les métadonnées et expose les blocs à
    télécharger.
3.  Le navigateur récupère les blocs via HTTP.
4.  L'interface mobile assemble ou télécharge le fichier selon les
    capacités du navigateur.
5.  Le serveur suit l'état de livraison lorsque le protocole le permet.

La progression d'un téléchargement navigateur doit être distinguée de la
simple mise à disposition du fichier par le serveur. Le serveur ne doit
pas annoncer un téléchargement terminé sans signal fiable du client.

------------------------------------------------------------------------

# 7. Stack technique

  -----------------------------------------------------------------------
  Domaine                 Technologie             Justification
  ----------------------- ----------------------- -----------------------
  Langage backend         Python 3.12 ou version  Écosystème et
                          stable compatible       maintenabilité

  Application Windows     PySide6                 Interface native et
                                                  intégration système

  Backend HTTP            FastAPI                 API typée,
                                                  documentation OpenAPI

  Serveur ASGI            Uvicorn                 Hébergement local

  Frontend web            React + TypeScript      Interface mobile
                                                  maintenable

  Build frontend          Vite                    Développement et
                                                  compilation

  CSS                     Tailwind CSS            Système de styles
                                                  cohérent

  Validation frontend     Zod                     Validation des données
                                                  reçues

  Base de données         SQLite                  Stockage local sans
                                                  serveur séparé

  Accès DB                SQLAlchemy 2 + Alembic  Modèles et migrations

  Validation backend      Pydantic                Contrats et paramètres

  Temps réel              WebSocket               Événements de
                                                  progression

  QR Code                 qrcode                  Génération locale

  Intégrité               hashlib SHA-256         Vérification de contenu

  Tests Python            Pytest + HTTPX          Tests unitaires et API

  Tests frontend          Vitest + Testing        Tests composants
                          Library                 

  Qualité Python          Ruff + mypy             Lint, format et typage

  Qualité TypeScript      ESLint + tsc            Contrôle statique

  Packaging               PyInstaller             Distribution Windows
  -----------------------------------------------------------------------

Les versions exactes seront verrouillées dans les fichiers de
dépendances après validation de compatibilité.

------------------------------------------------------------------------

# 8. Conception détaillée des modules

## 8.1 `network`

Responsabilités : - Détecter les interfaces réseau actives. - Identifier
les adresses IPv4 privées. - Exclure les interfaces inutilisables ou
virtuelles selon une politique configurable. - Construire les URL
d'accès. - Surveiller les changements réseau. - Détecter les erreurs de
bind et de pare-feu.

Ne pas supposer qu'une seule adresse IP est toujours disponible.
L'interface doit pouvoir présenter plusieurs URL candidates si
nécessaire.

## 8.2 `sessions`

Responsabilités : - Créer et terminer une session. - Générer les secrets
cryptographiquement aléatoires. - Émettre des jetons d'appairage à durée
limitée. - Valider les appareils. - Révoquer un appareil. - Gérer
l'expiration et le renouvellement.

Le QR Code doit contenir une URL locale, un identifiant de session et un
secret temporaire. Le secret ne doit pas être conservé en clair dans les
journaux.

## 8.3 `transfers`

Responsabilités : - Créer les transferts entrants et sortants. - Gérer
les états et transitions. - Calculer la progression. - Coordonner les
blocs. - Gérer pause, annulation et reprise. - Finaliser ou nettoyer un
transfert.

Les transitions d'état doivent être contrôlées, par exemple :

``` text
created -> waiting -> transferring -> verifying -> completed
                       |                 |
                       v                 v
                    paused             failed
                       |
                       v
                  transferring

created / waiting / transferring / paused -> cancelled
```

Un transfert terminé ne doit plus pouvoir être modifié.

## 8.4 `storage`

Responsabilités : - Gérer le dossier de réception. - Créer les fichiers
temporaires. - Écrire les blocs à leurs positions. - Vérifier l'espace
disque disponible lorsque possible. - Renommer les fichiers en cas de
collision. - Finaliser par déplacement atomique sur le même volume. -
Nettoyer les fichiers temporaires expirés.

Le nom fourni par le client ne doit jamais être utilisé comme chemin de
destination sans normalisation et validation. Le serveur génère lui-même
le chemin final.

## 8.5 `realtime`

Responsabilités : - Publier les événements de session. - Publier les
changements de progression. - Signaler les erreurs et interruptions. -
Réauthentifier les connexions WebSocket. - Nettoyer les connexions
fermées.

Le WebSocket transporte les événements, mais ne constitue pas la source
de vérité. L'état officiel est stocké dans le backend et peut être relu
via REST après reconnexion.

## 8.6 `desktop`

Responsabilités : - Démarrer/arrêter le serveur. - Afficher le QR Code
et les URL. - Afficher les appareils. - Superviser les transferts. -
Gérer les paramètres. - Afficher les notifications et erreurs.

Le serveur doit être lancé dans un thread ou processus de travail
contrôlé, sans bloquer la boucle événementielle Qt. La fermeture de
l'application doit déclencher un arrêt propre.

------------------------------------------------------------------------

# 9. Protocole de transfert résumable

## 9.1 Principe

Le transfert est découpé en blocs indépendants. Chaque bloc possède un
index, une taille attendue et une empreinte de contrôle.

Valeurs de départ : - Taille de bloc : 4 Mio. - Nombre de transferts
simultanés : 2. - Nombre de blocs simultanés par transfert : 1 dans le
MVP. - Reprise : par index de bloc validé.

Une optimisation de parallélisme pourra être introduite après les tests.

## 9.2 Cycle d'un transfert entrant

1.  `POST /api/v1/transfers` : créer le transfert.
2.  Le serveur retourne `transfer_id`, `chunk_size` et `total_chunks`.
3.  `PUT /api/v1/transfers/{id}/chunks/{index}` : envoyer un bloc.
4.  Le serveur valide la taille et l'empreinte du bloc.
5.  Le serveur confirme le bloc après écriture durable.
6.  `GET /api/v1/transfers/{id}` : obtenir les blocs validés.
7.  Après reconnexion, le client renvoie uniquement les blocs manquants.
8.  `POST /api/v1/transfers/{id}/complete` : demander la finalisation.
9.  Le serveur vérifie taille et SHA-256 global.
10. Le fichier est publié dans le dossier final.

## 9.3 Idempotence et cohérence

-   Un bloc déjà reçu avec le même hash doit être reconnu comme déjà
    validé.
-   Un bloc reçu avec un contenu différent pour un index déjà validé
    doit être refusé ou provoquer une réinitialisation contrôlée.
-   Un bloc ne doit être déclaré reçu qu'après écriture et validation.
-   La finalisation doit être protégée contre les appels concurrents.
-   Le manifeste et les états doivent être persistés en base.

## 9.4 Limites navigateur

Le navigateur ne doit pas être supposé capable de lire arbitrairement le
système de fichiers. L'envoi utilise les sélecteurs de fichiers natifs.
Pour la réception, le téléchargement classique du navigateur est le
comportement de base.

L'assemblage côté navigateur de très gros fichiers peut être limité par
la mémoire et les API disponibles. Le MVP doit privilégier un
téléchargement streaming ou une stratégie compatible avec les
navigateurs mobiles testés. La reprise des téléchargements sortants sur
iOS doit être validée expérimentalement avant d'être annoncée comme
garantie.

------------------------------------------------------------------------

# 10. API REST proposée

Toutes les routes sont préfixées par `/api/v1`.

## 10.1 Sessions et appareils

  Méthode   Route                 Description
  --------- --------------------- ------------------------------------
  POST      `/sessions/join`      Demander l'appairage
  POST      `/sessions/approve`   Approuver un appareil depuis le PC
  GET       `/sessions/status`    Consulter l'état de session
  POST      `/sessions/revoke`    Révoquer la session ou l'appareil
  GET       `/devices`            Lister les appareils connectés

## 10.2 Transferts

  -------------------------------------------------------------------------------------------
  Méthode                 Route                                       Description
  ----------------------- ------------------------------------------- -----------------------
  POST                    `/transfers`                                Créer un transfert

  GET                     `/transfers`                                Lister les transferts

  GET                     `/transfers/{transfer_id}`                  Consulter un transfert

  PUT                     `/transfers/{transfer_id}/chunks/{index}`   Envoyer un bloc

  GET                     `/transfers/{transfer_id}/chunks`           Lister les blocs
                                                                      validés

  POST                    `/transfers/{transfer_id}/complete`         Finaliser un transfert
                                                                      entrant

  POST                    `/transfers/{transfer_id}/resume`           Reprendre un transfert

  POST                    `/transfers/{transfer_id}/cancel`           Annuler un transfert

  GET                     `/transfers/{transfer_id}/download`         Télécharger un fichier
                                                                      sortant
  -------------------------------------------------------------------------------------------

## 10.3 Paramètres et santé

  Méthode   Route         Description
  --------- ------------- -----------------------------------
  GET       `/health`     Vérifier la disponibilité
  GET       `/settings`   Lire les paramètres non sensibles
  PATCH     `/settings`   Modifier les paramètres autorisés

## 10.4 WebSocket

Route : `/ws`

Événements serveur : - `device.connected` - `device.disconnected` -
`transfer.created` - `transfer.progress` - `transfer.paused` -
`transfer.completed` - `transfer.failed` - `server.network_changed`

Chaque événement inclut un identifiant, un horodatage et les données
minimales nécessaires à l'interface.

Les clients doivent pouvoir récupérer l'état courant par REST en cas de
perte d'événements.

------------------------------------------------------------------------

# 11. Modèle de données

SQLite est utilisé pour les métadonnées, jamais pour stocker les octets
des fichiers.

## 11.1 Table `sessions`

  Champ        Type       Description
  ------------ ---------- ---------------------------------------
  id           UUID       Identifiant
  token_hash   TEXT       Hash du secret, jamais le secret brut
  created_at   DATETIME   Création
  expires_at   DATETIME   Expiration
  status       TEXT       active, expired, revoked

## 11.2 Table `devices`

  Champ          Type       Description
  -------------- ---------- ----------------------------------
  id             UUID       Identifiant
  session_id     UUID       Session
  display_name   TEXT       Nom affiché
  platform       TEXT       Android, iOS, Windows
  connected_at   DATETIME   Connexion
  last_seen_at   DATETIME   Dernière activité
  status         TEXT       connected, disconnected, revoked

## 11.3 Table `transfers`

  Champ            Type       Description
  ---------------- ---------- -----------------------------
  id               UUID       Identifiant
  device_id        UUID       Appareil source/destination
  direction        TEXT       upload ou download
  filename         TEXT       Nom d'origine
  safe_filename    TEXT       Nom final sécurisé
  total_size       INTEGER    Taille totale
  chunk_size       INTEGER    Taille d'un bloc
  total_chunks     INTEGER    Nombre de blocs
  sha256           TEXT       Hash global
  status           TEXT       État
  received_bytes   INTEGER    Octets confirmés
  created_at       DATETIME   Création
  updated_at       DATETIME   Mise à jour
  expires_at       DATETIME   Expiration temporaire
  final_path       TEXT       Chemin final, si disponible

## 11.4 Table `transfer_chunks`

  Champ         Type       Description
  ------------- ---------- ----------------
  transfer_id   UUID       Transfert
  chunk_index   INTEGER    Index
  size          INTEGER    Taille validée
  sha256        TEXT       Hash du bloc
  received_at   DATETIME   Réception

Contrainte unique : `(transfer_id, chunk_index)`.

## 11.5 Migrations

Toute évolution du schéma doit être réalisée avec Alembic. Les créations
de tables au démarrage ne doivent pas remplacer une stratégie de
migration versionnée.

------------------------------------------------------------------------

# 12. Sécurité et modèle de menace

## 12.1 Risques principaux

-   Un autre appareil du réseau tente de rejoindre la session.
-   Un tiers scanne ou photographie le QR Code.
-   Un client tente d'écrire hors du dossier autorisé.
-   Un nom de fichier contient un chemin malveillant.
-   Un client envoie un volume excessif ou des blocs invalides.
-   Le réseau local est observé par un autre participant.
-   Un navigateur conserve une session après sa révocation.

## 12.2 Mesures

1.  Générer des secrets avec un générateur cryptographique.
2.  Expirer rapidement le jeton de QR Code après appairage ou délai
    défini.
3.  Exiger une approbation sur le PC pour chaque nouvel appareil.
4.  Stocker les hashes des jetons en base, pas les secrets en clair.
5.  Limiter les tentatives d'appairage.
6.  Authentifier chaque route sensible.
7.  Vérifier la taille maximale, les index et les hashes des blocs.
8.  Canonicaliser et contrôler les chemins de stockage.
9.  Éviter toute exécution ou ouverture automatique d'un fichier reçu.
10. Ne pas journaliser les jetons, secrets ou contenus de fichiers.
11. Lier le serveur aux interfaces privées choisies et refuser les
    interfaces publiques par défaut.
12. Proposer une révocation immédiate et une fermeture de session.

## 12.3 HTTP local et chiffrement

Le HTTP sur un réseau local de confiance simplifie la compatibilité
initiale, mais ne chiffre pas les données en transit. Le jeton de
session peut être observé par un participant capable d'écouter le
réseau.

La version de production devra étudier un HTTPS local avec certificat de
confiance ou mécanisme d'appairage cryptographique adapté. Il ne faut
pas supposer qu'un certificat auto-signé sera accepté sans avertissement
par tous les navigateurs mobiles.

Le MVP doit afficher un avertissement clair : utiliser un réseau de
confiance et éviter les réseaux Wi-Fi publics.

## 12.4 Pare-feu Windows

-   Utiliser un port configurable.
-   Expliquer à l'utilisateur la demande d'autorisation Windows.
-   Limiter la règle au profil réseau privé si possible.
-   Ne pas créer de règle entrante publique sans consentement.
-   Afficher un diagnostic si le téléphone ne peut pas joindre le
    serveur.

------------------------------------------------------------------------

# 13. Stockage et cycle de vie des fichiers

## 13.1 Dossiers

Emplacement par défaut :

`%USERPROFILE%\Downloads\LocalDrop`

Structure interne :

``` text
LocalDrop/
├── incoming/
├── temporary/
├── database/
└── logs/
```

Le dossier final peut être configuré dans les paramètres.

## 13.2 Écriture sécurisée

-   Écrire les blocs dans un fichier temporaire généré par le serveur.
-   Ne jamais concaténer directement le nom client au chemin final.
-   Vérifier la taille attendue.
-   Calculer le hash final.
-   Déplacer le fichier vers la destination finale après validation.
-   Gérer les collisions sans écrasement silencieux.
-   Conserver un manifeste pour les transferts incomplets.

## 13.3 Nettoyage

Une tâche de maintenance au démarrage et périodiquement : - identifie
les transferts expirés ; - supprime les fichiers temporaires associés
; - conserve l'historique selon la politique définie ; - ne supprime
jamais un fichier final valide.

------------------------------------------------------------------------

# 14. Interface et expérience utilisateur

## 14.1 Direction visuelle

-   Thème sombre par défaut.
-   Design minimaliste et professionnel.
-   Navigation simple.
-   États de connexion très visibles.
-   Progression des transferts lisible.
-   Responsive sur mobile.
-   Accessibilité clavier et contrastes suffisants.

## 14.2 Écrans Windows

### Dashboard

-   État du serveur.
-   QR Code.
-   URL locale.
-   Appareils connectés.
-   Boutons démarrer/arrêter.
-   Zone de dépôt de fichiers.

### Transfers

-   Transferts entrants et sortants.
-   Progression, débit et taille.
-   Actions pause, reprise et annulation.

### History

-   Date, nom, direction, taille et statut.
-   Recherche et filtres.
-   Ouvrir le dossier de destination.

### Settings

-   Dossier de réception.
-   Port.
-   Taille des blocs.
-   Nombre de transferts simultanés.
-   Expiration des sessions et fichiers temporaires.
-   Démarrage automatique, optionnel.

## 14.3 Écrans mobiles

### Accueil

-   Nom du PC connecté.
-   État de connexion.
-   Actions Envoyer et Recevoir.

### Envoyer

-   Sélecteur de fichiers natif.
-   Sélection multiple.
-   Liste et progression des envois.

### Recevoir

-   Liste des fichiers disponibles.
-   Taille et informations.
-   Téléchargement.

### Historique

-   Liste des transferts de la session.

------------------------------------------------------------------------

# 15. Structure du dépôt

Organisation recommandée en monorepo :

``` text
localdrop/
├── apps/
│   ├── desktop/
│   │   ├── src/localdrop_desktop/
│   │   │   ├── main.py
│   │   │   ├── application.py
│   │   │   ├── windows/
│   │   │   ├── controllers/
│   │   │   ├── workers/
│   │   │   └── resources/
│   │   └── tests/
│   │
│   └── web/
│       ├── src/
│       │   ├── app/
│       │   ├── components/
│       │   ├── features/
│       │   ├── hooks/
│       │   ├── services/
│       │   ├── types/
│       │   └── styles/
│       └── tests/
│
├── backend/
│   └── src/localdrop/
│       ├── main.py
│       ├── api/
│       │   └── v1/
│       ├── core/
│       ├── domain/
│       │   ├── sessions/
│       │   ├── devices/
│       │   └── transfers/
│       ├── services/
│       ├── infrastructure/
│       │   ├── database/
│       │   ├── storage/
│       │   ├── network/
│       │   └── realtime/
│       └── schemas/
│
├── shared/
│   └── api-contracts/
│
├── migrations/
├── tests/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
│
├── scripts/
├── docs/
│   ├── architecture/
│   ├── api/
│   └── decisions/
│
├── pyproject.toml
├── requirements-dev.txt
├── .gitignore
├── README.md
└── LICENSE
```

Les données d'exécution ne doivent pas être stockées dans le dépôt
source. Elles seront placées dans le répertoire de données utilisateur
Windows, par exemple sous `%LOCALAPPDATA%\LocalDrop`, tandis que les
fichiers reçus seront placés dans le dossier de réception choisi.

------------------------------------------------------------------------

# 16. Qualité logicielle et tests

## 16.1 Tests unitaires

-   Génération et validation des jetons.
-   Transitions d'état.
-   Validation des métadonnées.
-   Calcul des hashes.
-   Gestion des noms de fichiers.
-   Calcul des blocs manquants.
-   Détection des collisions.

## 16.2 Tests d'intégration

-   Appairage via API.
-   Révocation d'appareil.
-   Envoi d'un bloc.
-   Reprise après interruption.
-   Finalisation d'un fichier.
-   Téléchargement d'un fichier.
-   Persistance après redémarrage.
-   Réconciliation entre SQLite et fichiers temporaires.

## 16.3 Tests end-to-end

Tester au minimum : - Windows + Android Chrome. - Windows + iPhone
Safari. - Wi-Fi domestique. - Hotspot Android. - Hotspot iPhone. - Perte
puis retour du réseau. - Fichiers de petite, moyenne et grande taille. -
Noms de fichiers Unicode et collisions. - Espace disque insuffisant. -
Fermeture du navigateur pendant un transfert.

## 16.4 Critères d'acceptation

-   Le QR Code permet d'ouvrir l'interface mobile.
-   Un appareil non autorisé ne peut pas transférer de fichier.
-   Les transferts fonctionnent dans les deux sens.
-   Les fichiers reçus sont identiques aux originaux, vérifiés par hash.
-   Une interruption ne force pas à retransmettre les blocs validés.
-   Un redémarrage du serveur permet de retrouver les transferts encore
    valides.
-   Aucun fichier final incomplet n'est présenté comme terminé.
-   Les erreurs réseau et de stockage sont compréhensibles.
-   L'application peut être construite en exécutable Windows.

------------------------------------------------------------------------

# 17. Déploiement et distribution

## 17.1 Mode développement

-   Backend lancé avec Uvicorn.
-   Frontend lancé avec Vite.
-   Interface desktop lancée avec Python.
-   Rechargement automatique activé en développement uniquement.

## 17.2 Mode production

-   Frontend compilé en ressources statiques.
-   Ressources servies par FastAPI.
-   Backend intégré à l'application desktop.
-   Application distribuée sous forme d'exécutable Windows.
-   Base SQLite et données dans le profil utilisateur.
-   Logs rotatifs avec durée de conservation limitée.

Le packaging PyInstaller doit inclure les ressources web, les migrations
et les fichiers nécessaires. Les chemins doivent être résolus de façon
compatible avec le mode exécutable.

## 17.3 Mise à jour

Le MVP pourra être mis à jour par remplacement contrôlé de
l'application. Les migrations de base doivent être exécutées de façon
sûre et précédées d'une sauvegarde de la base locale.

------------------------------------------------------------------------

# 18. Roadmap de réalisation

  Phase   Travaux                                Résultat attendu
  ------- -------------------------------------- ----------------------
  0       Environnement, dépôt, conventions      Socle prêt
  1       FastAPI, configuration, santé          Serveur local
  2       Réseau, QR Code, sessions              Appairage mobile
  3       Transfert simple entrant               Téléphone vers PC
  4       Téléchargement sortant                 PC vers téléphone
  5       WebSocket et progression               Suivi temps réel
  6       Blocs, manifeste, reprise              Transfert résilient
  7       SQLite, historique, nettoyage          Persistance
  8       Interface PySide6                      Application Windows
  9       Interface React responsive             Client mobile
  10      Sécurité, tests réseau, optimisation   Version candidate
  11      PyInstaller et documentation           Version distribuable

## 18.1 Stratégie de livraison

Chaque phase doit produire une version exécutable et testable. Ne pas
développer toutes les interfaces avant d'avoir validé le flux réseau et
le transfert réel.

**Premier jalon technique :** depuis un PC Windows, démarrer FastAPI,
générer une URL et un QR Code, ouvrir la page depuis un téléphone, puis
transférer un petit fichier vers le PC.

------------------------------------------------------------------------

# 19. Risques et décisions à surveiller

  -----------------------------------------------------------------------
  Risque                  Conséquence             Réponse
  ----------------------- ----------------------- -----------------------
  Isolation des clients   Téléphone inaccessible  Diagnostic réseau et
  Wi-Fi                                           message explicatif

  Pare-feu Windows        Connexion bloquée       Assistant de diagnostic
                                                  et règle privée

  IP qui change           QR Code obsolète        Détection et
                                                  régénération

  Restrictions iOS        Transfert suspendu en   Garder la page active
                          arrière-plan            et tester Safari

  Gros fichiers           Pression mémoire ou     Streaming, blocs et
                          disque                  contrôle d'espace

  HTTP non chiffré        Données observables sur Réseau de confiance,
                          le LAN                  évolution HTTPS

  Arrêt brutal            État incohérent         Manifeste persistant et
                                                  réconciliation

  Collision de fichiers   Écrasement              Nom unique et
                                                  confirmation éventuelle
  -----------------------------------------------------------------------

## 19.1 Décisions d'architecture à documenter

Chaque décision structurante doit être enregistrée dans
`docs/decisions/` sous forme d'ADR : - ADR-001 : monolithe modulaire
plutôt que microservices. - ADR-002 : serveur local hébergé par
Windows. - ADR-003 : interface mobile web plutôt qu'application
native. - ADR-004 : SQLite pour les métadonnées. - ADR-005 : protocole
de transfert par blocs. - ADR-006 : HTTP local pour le MVP et stratégie
de sécurisation. - ADR-007 : PySide6 pour le desktop.

------------------------------------------------------------------------

# 20. Définition du MVP

Le MVP est terminé lorsque l'utilisateur peut :

1.  Lancer LocalDrop sur Windows.
2.  Scanner un QR Code depuis Android ou iPhone.
3.  Autoriser l'appareil.
4.  Envoyer un fichier du téléphone vers le PC.
5.  Envoyer un fichier du PC vers le téléphone.
6.  Voir la progression.
7.  Interrompre puis reprendre un transfert entrant.
8.  Vérifier l'intégrité du fichier reçu.
9.  Retrouver le fichier dans le dossier local.
10. Fermer proprement l'application.

Les fonctions secondaires (historique avancé, notifications, découverte
automatique, thèmes personnalisés et transfert téléphone-à-téléphone) ne
doivent pas retarder ce premier objectif.

------------------------------------------------------------------------

# Conclusion

LocalDrop sera développé comme une application locale, modulaire et
maintenable, dont le cœur est un moteur de transfert fiable plutôt
qu'une simple interface d'envoi de fichiers.

La priorité d'ingénierie est de valider les contraintes réelles du
réseau local, les comportements des navigateurs mobiles et la reprise
des transferts avant d'investir dans les finitions graphiques.

**Principe produit : scanner, connecter, transférer.**
