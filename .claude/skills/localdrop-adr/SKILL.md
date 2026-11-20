---
name: localdrop-adr
description: Rédaction des Architecture Decision Records de LocalDrop dans docs/decisions/ (modèle, numérotation, liste des ADR prévus ADR-001 à ADR-007 et décisions ouvertes). À utiliser quand une décision structurante est prise ou modifiée, ou quand on demande d'écrire ou de mettre à jour un ADR.
---

# ADR LocalDrop

Référence : cahier des charges §5.4, §19.1.

## Emplacement et nommage

`docs/decisions/ADR-NNN-titre-en-kebab-case.md`, avec une numérotation continue qui n'est jamais réutilisée. Un ADR remplacé passe au statut `Remplacé par ADR-XXX`. On ne le supprime pas.

## Modèle

```markdown
# ADR-NNN : <titre>

- Statut : Proposé | Accepté | Remplacé par ADR-XXX
- Date : AAAA-MM-JJ
- Exigences liées : FR-xxx, §x.y du cahier des charges

## Contexte
<problème, contraintes (Windows, navigateurs mobiles, réseau local), forces en présence>

## Décision
<ce qui est décidé, formulé de façon vérifiable>

## Options étudiées
<option : avantages / inconvénients>, pour chacune

## Conséquences
<positives, négatives, ce que cela impose au code et aux tests>
```

## ADR prévus (§19.1)

- ADR-001 : monolithe modulaire plutôt que microservices.
- ADR-002 : serveur local hébergé par Windows.
- ADR-003 : interface mobile web plutôt qu'application native.
- ADR-004 : SQLite pour les métadonnées (inclure SQLAlchemy synchrone en thread vs async).
- ADR-005 : protocole de transfert par blocs.
- ADR-006 : HTTP local pour le MVP et stratégie de sécurisation (HTTPS futur, absence de secure context côté navigateur).
- ADR-007 : PySide6 pour le desktop.

## Décisions ouvertes à trancher par ADR

- Accusé de réception des téléchargements sortants (§6.3) : quel signal client fiable ?
- Authentification des téléchargements par lien (ticket court à usage unique, ou cookie).
- Transport du hash global (à la création ou à la finalisation) et recalcul après rechargement de page.
- Bind multi-interfaces (sockets multiples) vs une seule interface choisie.
- Politique de conservation de l'historique.
