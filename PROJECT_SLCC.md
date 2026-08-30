# Smart Logistics Control Center (SLCC)
## Cahier des charges + contexte projet + instructions Claude Code

> **Objectif :** développer une plateforme web intelligente de supervision des flux logistiques des pièces, depuis la réception jusqu'à leur consommation en production.
>
> **Contrainte importante :** le projet est une simulation sur PC. Il ne doit pas communiquer directement avec une machine ou un véhicule réel.

---

# 1. VISION DU PROJET

Le projet est un **Smart Logistics Control Center** destiné au responsable logistique.

Il digitalise et centralise le flux :

**Fournisseur → Réception → Inspection → Qualité → Warehouse → Production**

L'application doit permettre de savoir :

- quelles pièces/lots sont reçus ;
- quelles pièces sont en inspection ;
- quels lots sont validés ou bloqués ;
- où les pièces sont stockées ;
- quelle quantité est réellement disponible ;
- quelles demandes de production sont en attente ;
- quelles pièces ont été sorties ;
- qui a effectué chaque action et quand ;
- quels problèmes sont prioritaires ;
- quels risques peuvent apparaître.

Le projet comporte trois couches :

### 1. Application opérationnelle
Elle permet de réaliser les actions métier.

### 2. Power BI
Il permet d'analyser les données, les tendances et les performances.

### 3. IA
Elle analyse les données et assiste le responsable logistique dans la prise de décision.

---

# 2. PROBLÈME MÉTIER

Dans le processus actuel, certaines informations sont informatisées, notamment via des fichiers Excel ou des systèmes existants, mais certaines opérations restent manuelles et les informations ne sont pas toujours traitées en temps réel.

Le projet doit créer une couche digitale de supervision et de traçabilité.

Le but n'est pas de remplacer brutalement les processus existants mais de construire une **simulation complète et cohérente** du processus logistique.

---

# 3. PROCESSUS MÉTIER À RESPECTER

## Étape 1 — Réception

Un fournisseur livre un lot de pièces.

Le réceptionnaire vérifie principalement la quantité reçue par rapport à la quantité attendue/commandée.

Exemple :

Commande : 500
Réception : 500

Le lot est enregistré.

### Règle importante

Pour certaines petites pièces, une marge de réception pouvant aller jusqu'à **5 %** peut être autorisée selon les règles métier.

Pour les grandes pièces, la quantité attendue est considérée comme exacte.

Cette règle doit être configurable.

NE PAS mettre le 5 % en dur partout dans le code.

---

# 4. INSPECTION QUALITÉ

La qualité ne contrôle pas nécessairement toutes les pièces.

Elle réalise un **échantillonnage**.

Exemple :

Lot = 500 pièces
Échantillon = 20 pièces

Le résultat peut être :

### Conforme
Le lot poursuit le processus.

### Non conforme
Le lot passe en **RED CAGE**.

La Red Cage représente une zone de quarantaine/blocage dans laquelle les pièces attendent une décision.

IMPORTANT :

Une réception ne signifie PAS automatiquement que les pièces deviennent disponibles en stock.

---

# 5. VALIDATION QUALITÉ

Après inspection, le lot doit être validé selon le workflow.

États possibles :

- PENDING_INSPECTION
- INSPECTION_IN_PROGRESS
- QUALITY_PENDING
- APPROVED
- REJECTED
- RED_CAGE

Un lot non validé ne doit pas être considéré comme du stock disponible.

---

# 6. WAREHOUSE

Après validation, les pièces doivent être stockées.

Le Warehouse contient plusieurs zones/racks/emplacements.

Une référence possède généralement une adresse principale.

Mais une référence peut avoir plusieurs adresses secondaires.

Exemple :

Référence : BR-145

Adresse principale :
WH-A-03

Adresses secondaires :
WH-B-02
WH-C-05

Cela peut arriver lorsqu'une pièce est volumineuse ou lorsque la quantité reçue dépasse la capacité de l'emplacement principal.

---

# 7. CONFIRMATION DU STOCKAGE

Le stock ne doit PAS être incrémenté simplement parce que la pièce a été reçue.

Le stock est incrémenté uniquement lorsque :

1. la qualité a validé le lot ;
2. le magasinier a confirmé le stockage ;
3. l'emplacement est renseigné.

Exemple :

Lot BR-145
Quantité validée : 120

Après confirmation du stockage :

Stock BR-145 = Stock précédent + 120

Créer un mouvement de stock :

type = IN
quantity = 120
location = WH-A-03
lot = LOT-xxx
actor = utilisateur
timestamp = date/heure

---

# 8. PRODUCTION

La production demande des pièces.

Un **Leader de station** peut créer une demande.

Exemple :

Station 02
Référence : BR-145
Quantité : 20

La demande doit ensuite suivre le workflow de validation prévu, notamment la validation par le responsable/chef de production dans la simulation.

États possibles :

- DRAFT
- SUBMITTED
- APPROVED
- PREPARING
- READY
- ISSUED
- REJECTED
- CANCELLED

---

# 9. DÉCRÉMENTATION DU STOCK

Le stock ne doit PAS être décrémenté au moment où une demande est simplement créée.

Le stock est décrémenté uniquement après :

Demande
→ Validation
→ Préparation
→ Confirmation de sortie par le magasinier

Exemple :

Stock = 500

Demande = 20

Après sortie confirmée :

Stock = 480

Créer un mouvement :

type = OUT
quantity = 20
reference = BR-145
station = Station 02
request = PR-xxx
actor = magasinier
timestamp = date/heure

---

# 10. TRAÇABILITÉ

Chaque événement important doit être enregistré.

Le système doit pouvoir répondre :

- Qui ?
- Quoi ?
- Quand ?
- Quelle quantité ?
- Quel lot ?
- Quelle référence ?
- Quel emplacement ?
- Quel statut avant ?
- Quel statut après ?
- Pourquoi ?

Créer un AuditLog.

Exemple :

LOT-2026-001

08:10 — Réception
08:35 — Inspection
09:00 — Validation qualité
09:25 — Stockage WH-A-03
14:10 — Demande production
14:30 — Validation
15:00 — Sortie magasin

---

# 11. RÈGLE FONDAMENTALE DU STOCK

Cette logique est NON NÉGOCIABLE :

## Entrée

Réception
→ Inspection
→ Validation qualité
→ Stockage confirmé
→ STOCK +

## Sortie

Demande production
→ Validation
→ Préparation
→ Sortie confirmée
→ STOCK -

Ne jamais modifier le stock simplement parce qu'un formulaire a été créé.

---

# 12. RÔLES UTILISATEURS

Créer des rôles simulés :

## Receptionist
- créer une réception ;
- vérifier quantité ;
- consulter ses réceptions.

## Quality Inspector
- consulter les lots à inspecter ;
- définir l'échantillon ;
- enregistrer le résultat.

## Quality Manager
- valider/refuser ;
- envoyer en Red Cage.

## Warehouse Operator
- confirmer le stockage ;
- sélectionner l'emplacement ;
- confirmer les sorties ;
- consulter le stock.

## Station Leader
- créer une demande de production.

## Production Manager
- valider/refuser les demandes.

## Logistics Manager
- supervision globale ;
- analytics ;
- alertes ;
- assistant IA ;
- traçabilité.

Les utilisateurs n'ont pas besoin d'être physiquement connectés à des machines.

Tout est simulé dans l'application.

---

# 13. APPLICATION WEB

Nom :

**Smart Logistics Control Center**

Nom court :

**SLCC**

L'application doit ressembler à un logiciel industriel professionnel, pas à un CRUD étudiant.

Style :

- dark industrial ;
- moderne ;
- professionnel ;
- bleu comme couleur principale ;
- vert = OK ;
- orange = warning ;
- rouge = critique ;
- animations discrètes ;
- excellente hiérarchie visuelle.

Inspirations visuelles possibles :

- Palantir ;
- Siemens ;
- Tesla ;
- IBM Carbon ;
- centres de contrôle industriels.

Ne pas copier leurs interfaces.

---

# 14. NAVIGATION

Sidebar :

1. Mission Control
2. Réception
3. Inspection
4. Qualité
5. Warehouse
6. Production
7. Traçabilité
8. Analytics
9. AI Assistant
10. Settings

---

# 15. MISSION CONTROL

C'est l'écran principal et le plus impressionnant.

Il représente une **vue vivante du flux logistique**.

Flux :

Supplier
↓
Receiving
↓
Inspection
↓
Quality
↓
Warehouse
↓
Production

Des cartons/caisses représentent les lots.

Exemple :

LOT-145
BR-201
120 pcs

Les lots peuvent être animés dans le flux.

Couleurs :

Vert = conforme/disponible
Orange = attente
Rouge = bloqué
Bleu = en mouvement/sortie

Cliquer sur un lot ouvre :

- lot ;
- référence ;
- quantité ;
- statut ;
- emplacement ;
- destination ;
- historique.

---

# 16. WAREHOUSE INTERACTIF

Créer une représentation visuelle du Warehouse.

Exemple :

A01 A02 A03 A04
B01 B02 B03 B04
C01 C02 C03 C04

Chaque emplacement peut afficher un état :

Vert = normal
Orange = presque plein
Rouge = saturé

Cliquer sur un emplacement affiche :

- capacité ;
- occupation ;
- références ;
- quantités ;
- lots ;
- historique.

---

# 17. KPI DU MISSION CONTROL

Afficher notamment :

- Lots reçus
- Lots en inspection
- Stock disponible
- Occupation Warehouse
- Demandes production
- Alertes

Les valeurs peuvent être simulées au début, puis alimentées par l'API.

---

# 18. ACTIVITY FEED

Afficher les dernières actions :

08:10
Lot reçu

08:35
Inspection terminée

09:00
Validation qualité

09:25
Stockage confirmé

14:10
Nouvelle demande production

---

# 19. SMART ALERTS

Exemples :

- Rack A03 presque saturé ;
- Lot L220 en attente de validation ;
- Production attend BR-145 ;
- Inspection en retard ;
- risque de rupture ;
- demande prioritaire.

---

# 20. POWER BI

Power BI n'est pas le cœur opérationnel.

L'application sert à agir.

Power BI sert à analyser.

Architecture :

React
↓
FastAPI
↓
PostgreSQL
↓
Power BI

Power BI devra afficher :

## Stock
- stock par catégorie ;
- stock par référence ;
- stock par emplacement ;
- occupation Warehouse ;
- évolution du stock.

## Flux
- lots reçus ;
- lots inspectés ;
- lots validés ;
- lots bloqués ;
- temps moyen entre étapes ;
- goulots d'étranglement.

## Qualité
- taux de conformité ;
- taux de non-conformité ;
- lots Red Cage ;
- défauts par référence ;
- défauts par fournisseur.

## Production
- demandes par station ;
- quantités demandées ;
- quantités sorties ;
- demandes en attente ;
- consommation.

Créer une page Analytics dans l'application pour accéder au reporting Power BI.

L'intégration Power BI doit être conçue après que la base et les données soient stables.

---

# 21. IA

NE PAS ajouter de l'IA juste pour avoir un chatbot.

L'IA doit résoudre de vrais problèmes.

## Fonction 1 — Risque de rupture

Entrées possibles :

- stock actuel ;
- demandes validées ;
- consommation ;
- lots en attente ;
- réceptions prévues ;
- délais historiques.

Sortie :

Risque faible / moyen / élevé.

Exemple :

"BR-145 présente un risque élevé d'insuffisance pour la prochaine demande de production."

---

# 22. IA — Priorisation

L'IA peut classer les situations :

Priorité 1 :
production en risque.

Priorité 2 :
lot bloqué depuis longtemps.

Priorité 3 :
emplacement saturé.

L'objectif est d'aider le responsable logistique à savoir **quoi traiter en premier**.

---

# 23. IA — Optimisation

L'IA peut recommander :

- un emplacement secondaire ;
- une action logistique ;
- une priorité de traitement ;
- une meilleure répartition du stock ;
- une surveillance particulière d'une référence.

Les recommandations doivent être expliquées.

Ne jamais produire une recommandation sans justification.

---

# 24. AI COPILOT

Créer un assistant :

**Logistics Copilot**

Questions possibles :

"Quelles sont les priorités aujourd'hui ?"

"Quels lots sont bloqués ?"

"Quels racks sont presque pleins ?"

"Y a-t-il un risque de rupture ?"

"Pourquoi le stock de BR-145 diminue-t-il ?"

"Quelle action dois-je traiter en premier ?"

Les réponses doivent être basées sur les données du système.

---

# 25. SIMULATION

Le projet fonctionne avec des données simulées.

Créer un mécanisme permettant de simuler :

- arrivée d'un camion ;
- réception d'un lot ;
- inspection ;
- validation ;
- stockage ;
- demande production ;
- validation ;
- sortie.

Le scénario de démonstration doit être reproductible.

Exemple :

1. Un camion arrive.
2. Lot L-001 reçu.
3. Quantité vérifiée.
4. Inspection.
5. Validation qualité.
6. Lot devient disponible.
7. Magasinier choisit WH-A-03.
8. Stock augmente.
9. Station 02 demande 20 pièces.
10. Chef production valide.
11. Magasinier confirme la sortie.
12. Stock diminue.
13. AuditLog est mis à jour.
14. Dashboard change.
15. Power BI peut analyser le nouvel état.
16. IA analyse la situation.

---

# 26. ARCHITECTURE TECHNIQUE

## Frontend

React
TypeScript
Vite
TailwindCSS
Framer Motion
Lucide React
React Router
Axios

## Backend

Python
FastAPI
SQLAlchemy
Pydantic
Alembic

## Database

PostgreSQL

## Analytics

Power BI

## IA

Python + modèle adapté au cas d'utilisation.

---

# 27. DOCKER

Docker est OPTIONNEL.

Ne pas utiliser Docker si cela ralentit inutilement le développement.

Si PostgreSQL est installé localement et fonctionne correctement, utiliser PostgreSQL directement.

Priorité :

Frontend + Backend + PostgreSQL fonctionnels.

---

# 28. BASE DE DONNÉES À PRÉVOIR

Entités principales :

User
Role

Supplier

Part
Category

Lot
Reception

Inspection
QualityValidation

Warehouse
WarehouseLocation

Stock
StockMovement

ProductionStation
ProductionRequest

AuditLog

AIRecommendation

Plus tard éventuellement :

VehicleProductionPlan
DemandForecast

Ne pas créer de tables inutiles.

---

# 29. RELATIONS IMPORTANTES

Supplier
→ Lot

Part
→ Lot

Lot
→ Inspection

Lot
→ QualityValidation

Lot
→ WarehouseLocation

Part
→ Stock

Stock
→ StockMovement

ProductionStation
→ ProductionRequest

ProductionRequest
→ StockMovement

Tous les événements importants
→ AuditLog

---

# 30. API À PRÉVOIR

Exemples :

GET /api/health

GET /api/lots

POST /api/lots

GET /api/lots/{id}

POST /api/lots/{id}/inspect

POST /api/lots/{id}/quality/approve

POST /api/lots/{id}/quality/reject

POST /api/lots/{id}/storage/confirm

GET /api/stock

GET /api/stock/{part_id}

GET /api/warehouse/locations

POST /api/production/requests

POST /api/production/requests/{id}/approve

POST /api/production/requests/{id}/issue

GET /api/traceability/{lot_id}

GET /api/dashboard

Les noms peuvent être adaptés si une meilleure architecture REST est nécessaire.

---

# 31. ARCHITECTURE FRONTEND

Créer des composants réutilisables.

Structure recommandée :

frontend/src/

components/
layouts/
pages/
features/
services/
hooks/
types/
utils/
data/

Features :

mission-control/
receiving/
inspection/
quality/
warehouse/
production/
traceability/
analytics/
ai/

Ne pas mettre toute la logique dans les pages.

---

# 32. ARCHITECTURE BACKEND

backend/app/

main.py

api/
models/
schemas/
services/
repositories/
core/
db/

Ne pas mettre toute la logique dans main.py.

Utiliser une séparation claire :

Router
→ Service
→ Repository
→ Database

---

# 33. ÉTAPES DE DÉVELOPPEMENT

Le projet doit être réalisé par phases.

## PHASE 1
Fondation

- frontend ;
- backend ;
- PostgreSQL ;
- configuration ;
- navigation ;
- design system.

## PHASE 2
Base de données

- modèles ;
- relations ;
- migrations ;
- seed data.

## PHASE 3
Réception

- création lot ;
- vérification quantité ;
- historique.

## PHASE 4
Inspection + Qualité

- échantillonnage ;
- validation ;
- Red Cage.

## PHASE 5
Warehouse

- emplacements ;
- stockage ;
- stock ;
- mouvements.

## PHASE 6
Production

- demandes ;
- validations ;
- sorties ;
- décrémentation.

## PHASE 7
Traçabilité

- AuditLog ;
- timeline ;
- recherche.

## PHASE 8
Mission Control

- flux animé ;
- KPI ;
- alertes ;
- activity feed.

## PHASE 9
Simulation

- scénario complet ;
- données dynamiques ;
- mise à jour du dashboard.

## PHASE 10
Power BI

- modèle analytique ;
- dashboards ;
- mesures ;
- intégration.

## PHASE 11
IA

- risque rupture ;
- priorisation ;
- optimisation ;
- Copilot.

## PHASE 12
Finalisation

- tests ;
- sécurité basique ;
- UX ;
- responsive ;
- démo ;
- documentation.

---

# 34. CONTRAINTE TEMPS

Le projet doit rester réalisable dans un délai court.

Priorités absolues :

1. Workflow fonctionnel.
2. Stock cohérent.
3. Traçabilité.
4. Interface professionnelle.
5. Simulation complète.
6. Power BI.
7. IA.

Si une fonctionnalité est trop ambitieuse, construire d'abord une version simple et fonctionnelle.

Ne jamais sacrifier le workflow principal pour une animation.

---

# 35. ORDRE DE TRAVAIL AVEC CLAUDE CODE

Claude Code ne doit PAS essayer de créer toute la plateforme en une seule réponse.

Pour chaque phase :

1. Inspecter le projet.
2. Comprendre l'architecture existante.
3. Expliquer brièvement le plan.
4. Implémenter uniquement la phase demandée.
5. Tester.
6. Corriger les erreurs.
7. Vérifier que les fonctionnalités précédentes fonctionnent toujours.
8. Résumer les changements.
9. Attendre la phase suivante.

Avant toute modification importante, vérifier les fichiers existants.

Ne pas supprimer du code fonctionnel sans raison.

---

# 36. RÈGLES DE CODE

- TypeScript strict.
- Pas de `any` inutile.
- Variables et fonctions clairement nommées.
- Components réutilisables.
- API séparée de l'UI.
- Validation backend obligatoire.
- Gestion des erreurs.
- États de workflow explicites.
- Transactions pour les opérations critiques de stock.
- Audit des opérations importantes.
- Configuration via `.env`.
- Aucun secret dans Git.
- README toujours maintenu.

---

# 37. RÈGLE CRITIQUE DE COHÉRENCE

Le frontend ne doit jamais décider seul qu'une opération est validée.

Exemple :

Le bouton "Confirm Storage" appelle le backend.

Le backend vérifie :

- lot valide ;
- qualité approuvée ;
- quantité valide ;
- emplacement valide.

Puis seulement :

- créer mouvement de stock ;
- augmenter stock ;
- enregistrer AuditLog.

Même principe pour les sorties.

---

# 38. DONNÉES DE DÉMONSTRATION

Créer un dataset cohérent avec :

- plusieurs fournisseurs ;
- plusieurs catégories ;
- plusieurs références ;
- plusieurs lots ;
- plusieurs emplacements ;
- plusieurs stations ;
- quelques lots conformes ;
- quelques lots en inspection ;
- quelques lots Red Cage ;
- quelques demandes production ;
- quelques alertes.

Les données doivent être suffisamment réalistes pour alimenter Power BI et l'IA.

---

# 39. DÉMO FINALE

La démonstration doit raconter une histoire.

### Scénario

Un nouveau lot arrive.

Réception.

Inspection.

Validation qualité.

Stockage.

Stock mis à jour.

Demande production.

Validation.

Sortie.

Stock décrémenté.

Traçabilité.

Power BI.

IA.

Le jury doit voir une chaîne complète et cohérente.

---

# 40. PROMPT DE DÉMARRAGE CLAUDE CODE

Lorsque le projet est vide, utiliser ce prompt :

"Tu es le lead developer du projet Smart Logistics Control Center.

Lis entièrement le fichier PROJECT.md avant de commencer.

Nous allons développer le projet par phases.

Pour cette session, travaille uniquement sur la phase demandée.

Commence par inspecter le repository.

Si le projet est vide, crée la fondation conformément aux technologies et à l'architecture définies dans PROJECT.md.

Ne développe pas encore les fonctionnalités des phases futures.

Après implémentation :

1. lance les vérifications disponibles ;
2. corrige les erreurs ;
3. vérifie que le projet démarre ;
4. explique les fichiers créés/modifiés ;
5. indique les commandes pour lancer le projet ;
6. indique clairement ce qui est terminé et ce qui ne l'est pas.

Ne remplace pas les règles métier définies dans PROJECT.md.

Le stock doit toujours respecter :

Réception
→ Inspection
→ Validation qualité
→ Stockage confirmé
→ STOCK +

et :

Demande production
→ Validation
→ Préparation
→ Sortie confirmée
→ STOCK -

Commence maintenant par PHASE 1."

---

# 41. IMPORTANT POUR CLAUDE

Ce fichier est la **source de vérité fonctionnelle** du projet.

Si une décision technique doit changer :

- expliquer pourquoi ;
- vérifier qu'elle ne casse pas les règles métier ;
- mettre à jour la documentation.

Ne pas inventer de processus métier qui n'est pas défini.

Si une information métier manque, utiliser une hypothèse configurable et la documenter plutôt que de coder une règle fixe.

---

# 42. OBJECTIF FINAL

Le résultat final doit être une plateforme qui donne cette impression :

**Mission Control**
→ voir ce qui se passe maintenant.

**Operational Modules**
→ effectuer les opérations.

**Warehouse**
→ visualiser et gérer les emplacements.

**Traceability**
→ savoir ce qui s'est passé.

**Power BI**
→ comprendre les tendances.

**AI Copilot**
→ savoir quoi traiter en priorité.

Le projet final doit être une démonstration cohérente d'un système de pilotage logistique intelligent, et non une collection de pages indépendantes.
