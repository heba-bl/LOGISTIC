# Dossier partage SLCC

**Jeu de donnees synthetique - demonstration.** Ces fichiers sont produits a partir de la base de demonstration SLCC. Les identites, les fournisseurs et les references sont fictifs et n'appartiennent a aucune entreprise reelle.

Genere le 29/08/2026 17:59 par `python scripts/generate_excel.py`.

## Organisation

Chaque zone dispose de son sous-dossier et de son fichier. Le fichier partage consolide les douze feuilles de l'ensemble du flux.

| Dossier | Fichier | Contenu |
|---------|---------|---------|
| `00_FICHIER_PARTAGE/` | `SLCC_Logistics_Flow.xlsx` | Fichier partage, 12 feuilles, toutes zones |
| `01_RECEPTION/` | `SLCC_Receiving.xlsx` | Saisie des livraisons fournisseur et historique des receptions |
| `02_INSPECTION/` | `SLCC_Inspection.xlsx` | Saisie des controles par echantillonnage et historique des inspections |
| `03_QUALITE/` | `SLCC_Quality.xlsx` | Decisions qualite et lots bloques en Red Cage |
| `04_ENTREPOT/` | `SLCC_Warehouse.xlsx` | Emplacements, stock disponible et mouvements |
| `05_PRODUCTION/` | `SLCC_Production.xlsx` | Saisie des demandes de pieces et suivi des sorties |

## Comment travailler avec ces fichiers

1. L'operateur ouvre le fichier de sa zone et remplit la feuille `SAISIE`, une ligne par enregistrement. Il ne renomme aucun en-tete.
2. Il enregistre le fichier dans son sous-dossier.
3. Dans SLCC, page **Donnees operationnelles**, le fichier est importe. Chaque ligne est controlee et le lot reste `EN ATTENTE DE VALIDATION`.
4. Un responsable habilite de la zone - obligatoirement une autre personne que celle qui a saisi - approuve ou rejette l'import dans SLCC.
5. Les enregistrements ne sont crees qu'apres cette validation.

**Le mot de passe personnel du responsable n'est jamais saisi dans Excel.** La validation se fait uniquement dans SLCC.

## Regle du stock

Remplir un fichier Excel ne modifie jamais le stock. Le stock ne bouge que sur:

- **STOCK +** : reception -> inspection -> validation qualite -> **confirmation de stockage**
- **STOCK -** : demande -> validation -> preparation -> **sortie confirmee**

Chaque mouvement produit un `StockMovement` et une entree d'audit nominative. Le stock ne peut jamais devenir negatif.

## Feuilles du fichier partage

| Feuille | Lignes |
|---------|--------|
| `OPERATORS` | 25 |
| `PARTS` | 2 239 |
| `VEHICLE_BOM` | 2 200 |
| `RECEIVING` | 322 |
| `INSPECTION` | 258 |
| `QUALITY` | 230 |
| `RED_CAGE` | 36 |
| `WAREHOUSE` | 144 |
| `PRODUCTION` | 156 |
| `STOCK_MOVEMENTS` | 213 |
| `AUDIT` | 1 000 |

Total: 12 feuilles  6 823 lignes de donnees.
