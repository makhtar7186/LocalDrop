---
name: localdrop-network
description: Couche réseau de LocalDrop sous Windows (détection des interfaces et IPv4 privées, adaptateurs virtuels, hotspot, bind sur les interfaces choisies, détection de changement d'IP, pare-feu Windows, isolation des clients Wi-Fi, diagnostic). À utiliser pour infrastructure/network, le démarrage d'Uvicorn ou un problème « le téléphone n'atteint pas le PC ».
---

# Réseau local et diagnostic

Référence : cahier des charges §4.1, §8.1, §12.2-11, §12.4, §19.

## Détection des interfaces (FR-002)

- `psutil.net_if_addrs()` + `psutil.net_if_stats()` (interface `isup`). Ajouter `psutil` aux dépendances et le documenter.
- Ne garder que les IPv4 où `ipaddress.ip_address(a).is_private` est vrai, en excluant le loopback et le link-local `169.254.0.0/16`.
- Exclure par défaut les adaptateurs virtuels, avec une liste de motifs configurable : `vEthernet`, `Hyper-V`, `WSL`, `VirtualBox`, `VMware`, `Docker`, `Loopback`, VPN (`Tailscale`, `ZeroTier`, `TAP`…).
- Prioriser les réseaux probables :
  - `192.168.137.0/24` : point d'accès mobile Windows ;
  - `172.20.10.0/28` : hotspot iPhone ;
  - Wi-Fi / Ethernet domestiques.
- **Ne jamais supposer une seule IP** : exposer une liste ordonnée d'URL candidates (§8.1).

## Bind (§12.2-11)

- Lier le serveur **uniquement** aux IP privées sélectionnées, plus `127.0.0.1` pour le desktop. Jamais `0.0.0.0` par défaut.
- Uvicorn n'accepte qu'un `host`. Pour plusieurs interfaces, créer les sockets soi-même et appeler `server.serve(sockets=[...])`.
- Port configurable. En cas de `EADDRINUSE`, erreur explicite avec proposition d'un autre port (FR-006).

## Changement d'IP (FR-003)

Une tâche périodique (3–5 s) compare l'ensemble des IP. Si la sélection change : re-bind si nécessaire, régénération du QR Code, événement `server.network_changed` vers le desktop et les clients.

## Pare-feu Windows (§12.4)

- Le premier bind déclenche la boîte de dialogue Windows. Expliquer à l'utilisateur, **avant**, ce qu'il va voir et recommander « Réseaux privés ».
- Ne jamais créer de règle entrante publique sans consentement explicite. Si une règle est créée (élévation UAC requise), la limiter à `profile=private`, au programme LocalDrop et au port :
  `netsh advfirewall firewall add rule name="LocalDrop" dir=in action=allow protocol=TCP localport=<port> profile=private program="<chemin exe>"`
- Diagnostic : profil réseau courant via `Get-NetConnectionProfile`. Un profil `Public` explique souvent un blocage, il faut le signaler.

## Isolation des clients Wi-Fi (§3.3, §19)

Le PC ne peut pas la détecter directement : si le téléphone n'atteint pas le serveur, la page mobile ne se charge même pas. Le **desktop** affiche donc une aide si aucun `/sessions/join` n'arrive N secondes après l'affichage du QR Code :
- même réseau Wi-Fi ? (sinon, utiliser le hotspot) ;
- point d'accès en « isolation des clients / AP isolation » ;
- pare-feu ou profil réseau Public ;
- copier l'URL et la saisir à la main (FR-005, FR-044).

## Tests

- Détection et filtrage : fonctions pures prenant en entrée la structure retournée par psutil (fixtures), sans dépendre de la machine.
- Les vrais tests Wi-Fi et hotspot font partie de la matrice e2e manuelle (skill `localdrop-testing`).
