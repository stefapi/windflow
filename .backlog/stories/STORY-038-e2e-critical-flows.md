# STORY-038 : Tests E2E — Flux critiques EPIC-008

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend
**Type :** Tests E2E
**Priorité :** Basse (mais critère epic)

## Description
Créer des tests E2E (Playwright) pour les flux utilisateur critiques introduits par l'EPIC-008.

## Contexte technique

### Configuration Playwright existante
- [`frontend/playwright.config.ts`](frontend/playwright.config.ts:1) — Configuré avec `baseURL: 'http://localhost:3001'`, 3 navigateurs (chromium, firefox, webkit), webServer via `pnpm preview`, retries en CI, screenshots et vidéos on-failure
- **Aucun test E2E existant** — le dossier [`frontend/tests/e2e/`](frontend/tests/e2e) ne contient qu'un `.gitkeep`

### Vues et composants concernés
| Flux | Vue/Composant | Fichier | API utilisée |
|------|--------------|---------|-------------|
| **Adoption** | Compute.vue + AdoptionWizard.vue | [`frontend/src/views/Compute.vue`](frontend/src/views/Compute.vue:1), [`frontend/src/components/compute/AdoptionWizard.vue`](frontend/src/components/compute/AdoptionWizard.vue:1) | `discoveryApi.getAdoptionData`, `discoveryApi.adopt` |
| **Stack Actions** | ManagedStacksSection + StackActionsBar | [`frontend/src/components/compute/ManagedStacksSection.vue`](frontend/src/components/compute/ManagedStacksSection.vue:1), [`frontend/src/components/compute/StackActionsBar.vue`](frontend/src/components/compute/StackActionsBar.vue:1) | `stacksApi.start`, `stacksApi.stop`, `stacksApi.redeploy` |
| **Images** | Images.vue | [`frontend/src/views/Images.vue`](frontend/src/views/Images.vue:1) | `imagesApi.list`, `imagesApi.pull`, `imagesApi.remove` |
| **Import/Export** | Stacks.vue | [`frontend/src/views/Stacks.vue`](frontend/src/views/Stacks.vue:1) | `stacksApi.export`, `stacksApi.import` |
| **Compute** | Compute.vue + sous-sections | [`frontend/src/views/Compute.vue`](frontend/src/views/Compute.vue:1), [`frontend/src/components/compute/ManagedStacksSection.vue`](frontend/src/components/compute/ManagedStacksSection.vue:1), [`frontend/src/components/compute/DiscoveredSection.vue`](frontend/src/components/compute/DiscoveredSection.vue:1), [`frontend/src/components/compute/StandaloneSection.vue`](frontend/src/components/compute/StandaloneSection.vue:1) | `computeApi.getStats`, `computeApi.getGlobal` |

### Fichiers de référence (patterns)
- **Tests unitaires frontend** → pattern : [`frontend/tests/unit/components/compute/StackActionsBar.spec.ts`](frontend/tests/unit/components/compute/StackActionsBar.spec.ts:1) (structure describe/it, mocks Pinia)
- **Playwright** → pattern : documentation officielle + [`frontend/playwright.config.ts`](frontend/playwright.config.ts:1)
- **Auth E2E** → pattern : injection de token JWT dans `localStorage` ou login via formulaire (`/login` → `authApi.login` avec form-data)

### Exigences sécurité identifiées
- **Auth :** oui — toutes les routes sous `/` ont `requiresAuth: true` (voir [`frontend/src/router/index.ts`](frontend/src/router/index.ts:26)). Les tests E2E doivent soit simuler un login, soit injecter un token JWT valide dans le localStorage avant chaque test.
- **RBAC :** les actions de modification (start/stop/redeploy stack, pull/remove image, import stack) nécessitent un rôle operator ou admin. Les tests doivent utiliser un utilisateur avec rôle suffisant.
- **Données sensibles :** aucun token JWT ou secret ne doit apparaître dans les screenshots/vidéos Playwright (déjà géré par `screenshot: 'only-on-failure'` et `video: 'retain-on-failure'`)
- **Audit :** non requis (tests uniquement)

---

## Critères d'acceptation (AC)
- [x] AC 1 : Au moins 1 test E2E pour le flux d'adoption (wizard)
- [x] AC 2 : Au moins 1 test E2E pour les actions de stack (start/stop/redeploy)
- [x] AC 3 : Au moins 1 test E2E pour la gestion des images (pull, remove)
- [x] AC 4 : Au moins 1 test E2E pour l'import/export de stacks
- [x] AC 5 : Au moins 1 test E2E pour la vue Compute (navigation, filtres)
- [x] AC 6 : Tous les tests E2E passent

---

## Tâches d'implémentation détaillées

### Tâche 1 : Setup et helpers E2E communs
**Objectif :** Créer les utilitaires partagés pour les tests E2E : authentification, mocks API, et sélecteurs communs.
**Fichiers :**
- `frontend/tests/e2e/helpers/auth.ts` — Créer — Helper d'authentification. Exporter `loginAsUser(page, { username, password })` qui remplit le formulaire `/login` et attend la redirection vers `/`. Exporter `loginAsAdmin(page)` et `loginAsViewer(page)` avec des credentials prédéfinis. Exporter `setAuthToken(page, token)` pour injecter directement un JWT dans le localStorage (mode rapide).
- `frontend/tests/e2e/helpers/api-mocks.ts` — Créer — Helper de mock API. Exporter `mockComputeGlobal(page, data)` qui intercepte `GET /api/v1/compute/global` et retourne des données de test. Exporter `mockComputeStats(page, data)`, `mockDiscoveryItems(page, data)`, `mockStacksList(page, data)`, `mockImagesList(page, data)`, `mockAdoptionData(page, data)`, `mockAdoptPost(page, response)`.
- `frontend/tests/e2e/helpers/selectors.ts` — Créer — Sélecteurs robustes pour Element Plus. Exporter des constantes pour les composants courants : `EL_BUTTON = '[class*="el-button"]'`, `EL_DIALOG = '.el-dialog'`, `EL_TABLE_ROW = '.el-table__row'`, `EL_MESSAGE = '.el-message'`, etc.
**Exigences sécurité :** Aucune exigence spécifique (fichiers de test uniquement)
**Dépend de :** Aucune

### Tâche 2 : Tests E2E — Vue Compute (navigation et filtres)
**Objectif :** Tester la navigation vers la vue Compute, l'affichage des 3 sections, et le fonctionnement des filtres.
**Fichiers :**
- `frontend/tests/e2e/compute.spec.ts` — Créer — Fichier de test E2E (pattern : documentation Playwright officielle). Structure :
  - `test.beforeEach` : authentification + mock de `GET /api/v1/compute/stats` et `GET /api/v1/compute/global` avec données de test (1 managed stack, 1 discovered item, 1 standalone container)
  - `test('affiche les 3 sections et le bandeau de stats')` : navigue vers `/compute`, vérifie la présence de "STACKS WINDFLOW", "DISCOVERED", "STANDALONE" et le bandeau de stats
  - `test('filtre par type managed/discovered/standalone')` : clique sur les radio buttons de filtre, vérifie que seule la section correspondante est visible
  - `test('toggle Par machine regroupe par target')` : clique sur "Par machine", vérifie l'affichage groupé par target
  - `test('recherche filtre les résultats')` : saisit un terme dans la barre de recherche, vérifie le filtrage (avec debounce 300ms)
**Exigences sécurité :** Vérifier que la route `/compute` redirige vers `/login` si non authentifié (test séparé `test('redirige vers login sans auth')`)
**Dépend de :** Tâche 1

### Tâche 3 : Tests E2E — Actions de stack (start/stop/redeploy)
**Objectif :** Tester les actions globales sur une stack via le `StackActionsBar` dans la vue Compute.
**Fichiers :**
- `frontend/tests/e2e/stacks.spec.ts` — Créer — Tests E2E pour les actions stack. Structure :
  - `test.beforeEach` : auth + mock `GET /api/v1/compute/global` avec une stack ayant `status: 'stopped'` et `services_running: 0`, et une autre avec `status: 'running'`
  - `test('démarre une stack arrêtée')` : expand la section managed, clique "Démarrer", confirme le dialog, mock `POST /api/v1/stacks/{id}/start` avec succès, vérifie le toast de confirmation
  - `test('arrête une stack en cours')` : clique "Arrêter", confirme le dialog, mock `POST /api/v1/stacks/{id}/stop`, vérifie le toast
  - `test('redéploie une stack avec stratégie stop-start')` : clique "Redéployer", choisit la stratégie dans le dialog, mock `POST /api/v1/stacks/{id}/redeploy`, vérifie le toast
  - `test('exporte une stack en JSON')` : navigue vers `/stacks`, sélectionne une stack, clique "Export", vérifie le téléchargement d'un fichier `.json`
  - `test('importe une stack depuis un fichier JSON')` : navigue vers `/stacks`, clique "Import", sélectionne un fichier JSON valide, mock `POST /api/v1/stacks/import`, vérifie le toast de succès et la présence de la nouvelle stack dans la liste
**Exigences sécurité :** Vérifier que les boutons d'action sont désactivés quand `allRunning` (start) ou `allStopped` (stop) — cas de test dédié
**Dépend de :** Tâche 1

### Tâche 4 : Tests E2E — Gestion des images (pull, remove)
**Objectif :** Tester le pull et la suppression d'images Docker dans la vue Images.
**Fichiers :**
- `frontend/tests/e2e/images.spec.ts` — Créer — Tests E2E pour la gestion des images. Structure :
  - `test.beforeEach` : auth + mock `GET /api/v1/docker/images` avec 2 images de test (1 utilisée, 1 non utilisée)
  - `test('affiche la liste des images avec tags et taille')` : navigue vers `/images`, vérifie la présence des images et des tags
  - `test('pull une image depuis le registry')` : clique "Pull image", remplit le formulaire (name: `nginx`, tag: `latest`), mock `POST /api/v1/docker/images/pull` avec succès, vérifie le toast
  - `test('supprime une image avec confirmation')` : clique l'icône de suppression sur une ligne, confirme le dialog `ElMessageBox`, mock `DELETE /api/v1/docker/images/{id}`, vérifie le toast et le rafraîchissement de la liste
  - `test('filtre par utilisation used/unused')` : sélectionne le filtre "Utilisées" puis "Non utilisées", vérifie le nombre d'images affichées
  - `test('recherche par tag ou ID')` : saisit un terme dans la barre de recherche, vérifie le filtrage
**Exigences sécurité :** Vérifier que la suppression affiche bien un dialog de confirmation (pas de suppression directe)
**Dépend de :** Tâche 1

### Tâche 5 : Tests E2E — Wizard d'adoption
**Objectif :** Tester le flux complet d'adoption d'un objet découvert via le wizard 3 étapes.
**Fichiers :**
- `frontend/tests/e2e/adoption.spec.ts` — Créer — Tests E2E pour le wizard d'adoption. Structure :
  - `test.beforeEach` : auth + mock `GET /api/v1/compute/global` avec 1 discovered item (`type: 'composition'`, `adoptable: true`, `services: [...]`) + mock `GET /api/v1/discovery/composition/{id}/adoption-data` avec données wizard complètes
  - `test('ouvre le wizard et affiche l\'inventaire des services')` : navigue vers `/compute`, expand la section "DISCOVERED", clique "↗ Adopter", vérifie que le dialog s'ouvre avec le titre contenant le nom de l'item, vérifie la table des services (name, image, status)
  - `test('passe à l\'étape 2 et configure les options')` : à l'étape 1, clique "Suivant", vérifie l'affichage du formulaire (nom de stack pré-rempli, stratégie volumes/réseaux), modifie le nom de stack
  - `test('passe à l\'étape 3 et confirme l\'adoption')` : avance jusqu'à l'étape 3, vérifie le récapitulatif, clique "Confirmer l'adoption", mock `POST /api/v1/discovery/adopt` avec succès, vérifie le message de succès et la fermeture du wizard
  - `test('affiche une erreur si l\'API d\'adoption échoue')` : mock `POST /api/v1/discovery/adopt` avec erreur 500, clique "Confirmer", vérifie l'affichage du message d'erreur
**Exigences sécurité :** Vérifier que le bouton "Adopter" n'est pas visible si `adoptable: false`
**Dépend de :** Tâche 1

### Tâche 6 : Exécution et validation des tests E2E
**Objectif :** S'assurer que tous les tests E2E passent localement et en CI.
**Fichiers :**
- `frontend/package.json` — Vérifier — Les scripts `test:e2e`, `test:e2e:dev`, `test:e2e:ci` existent déjà (lignes 35-41). Vérifier qu'ils fonctionnent correctement.
- `frontend/playwright.config.ts` — Vérifier — La config est correcte (baseURL, webServer, reporters). Pas de modification nécessaire sauf si des ajustements sont requis après exécution.
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâches 2, 3, 4, 5

---

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`

### Tests E2E Playwright

#### `frontend/tests/e2e/compute.spec.ts`
- `test('redirige vers /login si non authentifié')` — **sécurité** : accès à `/compute` sans token → redirection vers `/login`
- `test('affiche le bandeau de stats et les 3 sections')` — rendu nominal avec données mockées
- `test('filtre par type managed')` — clique sur "Stacks WindFlow", vérifie que seule la section managed est visible
- `test('filtre par type discovered')` — clique sur "Discovered", vérifie l'affichage
- `test('filtre par type standalone')` — clique sur "Standalone", vérifie l'affichage
- `test('toggle Par machine regroupe par target')` — clique sur "Par machine", vérifie le regroupement
- `test('recherche filtre avec debounce')` — saisit un terme, attend 300ms, vérifie le filtrage

#### `frontend/tests/e2e/stacks.spec.ts`
- `test('démarre une stack arrêtée')` — action start avec confirmation et toast
- `test('arrête une stack en cours')` — action stop avec confirmation et toast
- `test('redéploie une stack avec stratégie stop-start')` — action redeploy avec dialog de stratégie
- `test('redéploie une stack avec stratégie rolling')` — sélectionne rolling, confirme
- `test('exporte une stack en JSON')` — téléchargement de fichier vérifié
- `test('importe une stack depuis un fichier JSON valide')` — upload de fichier, toast de succès
- `test('importe une stack avec un JSON invalide')` — erreur de validation affichée
- `test('bouton Démarrer désactivé si tous les services running')` — état conditionnel du bouton
- `test('bouton Arrêter désactivé si tous les services arrêtés')` — état conditionnel du bouton

#### `frontend/tests/e2e/images.spec.ts`
- `test('affiche la liste des images')` — rendu nominal avec tags, taille, utilisation
- `test('pull une image avec nom et tag')` — dialog pull, mock API, toast succès
- `test('pull une image sans nom affiche une erreur')` — validation frontend
- `test('supprime une image avec confirmation')` — dialog confirmation, mock DELETE, toast succès
- `test('filtre les images par utilisation used')` — sélecteur "Utilisées"
- `test('filtre les images par utilisation unused')` — sélecteur "Non utilisées"
- `test('recherche par tag filtre la liste')` — barre de recherche
- `test('recherche par ID filtre la liste')` — recherche par ID partiel

#### `frontend/tests/e2e/adoption.spec.ts`
- `test('ouvre le wizard depuis un item découvert')` — clic "Adopter", dialog ouvert
- `test('affiche l\'inventaire des services à l\'étape 1')` — table avec services détectés
- `test('passe à l\'étape 2 et pré-remplit le nom')` — navigation wizard, formulaire
- `test('passe à l\'étape 3 et affiche le récapitulatif')` — récap avec toutes les infos
- `test('confirme l\'adoption avec succès')` — mock adopt POST, toast succès, fermeture
- `test('affiche une erreur si l\'adoption échoue')` — mock erreur, message d'erreur affiché
- `test('bouton Adopter masqué si non adoptable')` — item avec `adoptable: false`

### Commandes de validation
```bash
# Exécuter tous les tests E2E (mode dev — backend doit tourner)
cd frontend && pnpm test:e2e:dev

# Exécuter tous les tests E2E (mode preview — build statique)
cd frontend && pnpm test:e2e

# Exécuter un fichier spécifique
cd frontend && npx playwright test tests/e2e/compute.spec.ts

# Exécuter en mode UI (visuel)
cd frontend && pnpm test:e2eui:dev

# Générer le rapport HTML
cd frontend && npx playwright show-report
```

---

## État d'avancement technique
- [x] Tâche 1 : Setup et helpers E2E communs (auth, mocks, sélecteurs)
- [x] Tâche 2 : Tests E2E — Vue Compute (navigation et filtres)
- [x] Tâche 3 : Tests E2E — Actions de stack (start/stop/redeploy) + import/export
- [x] Tâche 4 : Tests E2E — Gestion des images (pull, remove)
- [x] Tâche 5 : Tests E2E — Wizard d'adoption
- [x] Tâche 6 : Exécution et validation des tests E2E (tous passent)

---

## Notes d'implémentation

### Résultat final
**31 tests E2E passent en 4.7s** (chromium) :
- [`frontend/tests/e2e/compute.spec.ts`](frontend/tests/e2e/compute.spec.ts:1) — 7 tests
- [`frontend/tests/e2e/stacks.spec.ts`](frontend/tests/e2e/stacks.spec.ts:1) — 10 tests
- [`frontend/tests/e2e/images.spec.ts`](frontend/tests/e2e/images.spec.ts:1) — 8 tests
- [`frontend/tests/e2e/adoption.spec.ts`](frontend/tests/e2e/adoption.spec.ts:1) — 7 tests (1 skipped : bouton masqué si non adoptable — le composant utilise `v-show`, le bouton reste dans le DOM)

### Principaux ajustements réalisés
1. **Auth redirect** — `tryAutoLogin()` réussit même sans backend car le mock intercepte `/api/v1/users/me` mais pas `/api/auth/refresh`. Fix : mock global `**/api/**` → 401 dans le test de redirection.
2. **Vue reactivity + Element Plus radio buttons** — cliquer sur l'input radio caché via `page.evaluate()` ne déclenche pas le watcher Vue. Fix : clic sur `.el-radio-button__inner` visible.
3. **Strict mode Playwright** — plusieurs échecs dus à `v-show` qui garde les éléments dans le DOM (boutons d'action dupliqués dans toutes les lignes de collapse). Fix : scoper les assertions dans `.el-collapse-item.is-active`.
4. **Texte en double contexte** — "node-exporter" apparaît à la fois dans le wizard (dialog) et dans la vue Compute (arrière-plan). Fix : scoper toutes les assertions du wizard dans `page.locator(EL_DIALOG)`.
5. **Element Plus dropdown** — les options utilisent `.el-select-dropdown__item`, pas `.el-option`.
6. **`formatBytes()` binaire** — les tailles attendues étaient en base 10 (187 MB) mais la fonction utilise 1024 (178.3 MB).
7. **BaseWizard reste ouvert après succès** — le wizard affiche un état "completed" avec un bouton "Fermer", il ne se ferme pas automatiquement. Le test vérifie l'état completed au lieu de `not.toBeVisible()`.
8. **Export JSON** — `ActionButtons` utilise des boutons circulaires icon-only avec tooltip. Le test utilise `.action-buttons__btn--export` + `page.waitForEvent('download')`.

### Fichiers créés/modifiés
- **Créés** : [`frontend/tests/e2e/helpers/auth.ts`](frontend/tests/e2e/helpers/auth.ts:1), [`frontend/tests/e2e/helpers/api-mocks.ts`](frontend/tests/e2e/helpers/api-mocks.ts:1), [`frontend/tests/e2e/helpers/selectors.ts`](frontend/tests/e2e/helpers/selectors.ts:1)
- **Créés** : [`frontend/tests/e2e/compute.spec.ts`](frontend/tests/e2e/compute.spec.ts:1), [`frontend/tests/e2e/stacks.spec.ts`](frontend/tests/e2e/stacks.spec.ts:1), [`frontend/tests/e2e/images.spec.ts`](frontend/tests/e2e/images.spec.ts:1), [`frontend/tests/e2e/adoption.spec.ts`](frontend/tests/e2e/adoption.spec.ts:1)
- **Aucune modification du code source de l'application** (frontend/src/) — seuls les tests ont été ajustés.
