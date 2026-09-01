# Reprise — refonte visuelle SLCC

Note de passage pour une session neuve. La précédente a atteint sa limite
d'images : impossible d'y afficher une capture, donc impossible d'y juger un
écran. Tout le code est sur le disque, rien n'est à refaire.

## Démarrer

```bash
cd backend  && ../.venv/Scripts/python.exe -m uvicorn app.main:app --port 8001
cd frontend && npm run dev            # http://localhost:5173
```

Connexion : `LM-001` / `LOG2026` (responsable logistique).
Les autres comptes autorisés : `LM-002`, `WH-M01` (`WHS2026`), `PM-001`,
`PM-002` (`PRD2026`). `RM-004` et `QM-002` sont refusés **exprès** — ils
valident dans Excel, pas ici.

## Règle absolue

Ne pas toucher à la logique métier : `stock_service.py`, BOM, catalogue
(2 239 références), Maker/Checker, sync Excel → API → DB, endpoints, Power BI.
**Couche présentation uniquement.**

## Fait

**Phase 1-2 — design system** (`frontend/src/index.css`)
Une couleur, un sens : vert = sain, bleu = information et flux (et la marque),
ambre = à surveiller, rouge = à traiter. Cyan et violet **uniquement** comme
séries de graphique. Vert/rouge séparés par la clarté, validés en OKLab sous
protanopie / deutéranopie / tritanopie : 0 échec sur les deux thèmes. Thème
sombre conçu à part, pas inversé. Durées `--t-fast/base/slow` = 150/220/340 ms.
Six boutons (`.btn-primary`, `-secondary`, `-success`, `-danger`, `-ghost`,
`-icon`). Squelette de chargement en balayage.

**Phase 4 — navigation** (`frontend/src/layouts/Sidebar.tsx`)
Rail repliable à 84 px, mémorisé (`slcc.nav.collapsed`). Infobulles au survol
et au focus quand replié. Pastille d'alerte sur Inspection, alimentée par
`dashboardApi.get()`. Sous-entrées Analytics dépliées seulement dans la section
courante. Plaque de survol qui voyage sur ressort, barre active en `layoutId`.

**Hors phases, déjà en place**
- Barre du haut **supprimée** ; ses contrôles sont au pied du rail.
- Entrée cinématographique `/` : portes qui s'ouvrent au défilement, verrou
  relâché à la fin et sur Échap (`features/entry/ScrollLockedHero.tsx`).
- Login réel `POST /api/auth/login` : même code de validation que dans Excel,
  même SHA-256. Garde sur `AppLayout`.
- Marque TATA : `components/BrandMark.tsx` prend `public/brand/*.png` si présent,
  sinon retombe sur le SVG de `components/TataMark.tsx`.
  **À faire : y déposer les vrais PNG.**
- Composants partagés relevés : tuile KPI, `ChartCard`, `FilterBar`, tableaux
  (en-têtes collants, accent au survol), `PageHeader`, `Badge`.
- Radar fournisseur sur Inspection (`features/analytics/radar.tsx`).

## À faire

**Phase 3 — `/analytics` (priorité absolue)**
En faire une vraie Mission Control. KPI avec sparkline, évolution et infobulle.
Section « État des opérations » : donut conforme/non conforme, barres stock vs
besoin, jauge taux de service, funnel réception → sortie. Section « Décisions » :
**3 à 5 cartes maximum**, pas un mur de texte — titre court, raison, impact,
action recommandée.

**Phase 5** autres pages · **Phase 6** responsive (1680/1440/1366/1024/820/768/420/375)
**Phase 7** balayage FR/EN complet · **Phase 8** relecture des deux thèmes
**Phase 9** tests

## Absents du menu, volontairement

Red Cage, Sorties et Copilot n'ont **pas de route** dans `App.tsx`. Ils ne sont
pas dans la navigation : un lien mort est pire qu'une absence. Les ajouter
demande d'abord de créer les pages.

## Vérifications à relancer après chaque phase

```bash
cd frontend && npx tsc --noEmit && npm run build
```

Puis ouvrir les écrans et **regarder** : c'est l'étape qui a manqué.
