# STORY-451 : Page Settings — Organisations, Environnements, Utilisateurs

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'administrateur, je veux une page Settings avec onglets pour gérer les organisations, environnements et utilisateurs afin de configurer WindFlow sans passer par l'API directement.

## Critères d'acceptation (AC)
- [x] AC 1 : Vue `Settings.vue` accessible via `/settings` dans la sidebar (section Administration)
- [x] AC 2 : Onglet « Organisations » : liste des organisations, création, édition, suppression
- [x] AC 3 : Onglet « Environnements » : liste des environnements par organisation, CRUD
- [x] AC 4 : Onglet « Utilisateurs » : tableau avec nom, email, rôle, dernière connexion, actions (éditer, supprimer)
- [x] AC 5 : Formulaires de création/édition via drawer ou modale Element Plus
- [x] AC 6 : Confirmation avant suppression d'un utilisateur ou d'une organisation
- [x] AC 7 : Les données proviennent des APIs existantes (`/api/v1/organizations`, `/api/v1/users`, `/api/v1/targets`)
- [x] AC 8 : Accès restreint aux rôles admin/super_admin (sinon redirection ou message d'erreur)

## Contexte technique

### Patterns existants à réutiliser
| Pattern | Fichier source | Utilisation |
|---------|---------------|-------------|
| el-table + el-dialog CRUD | `frontend/src/views/Targets.vue` | Structure tableau + dialog |
| ActionButtons component | `frontend/src/views/Targets.vue` | Boutons edit/delete inline |
| StatusBadge component | `frontend/src/components/` | Badges is_active |
| DynamicFormField | `frontend/src/components/DynamicFormField.vue` | Champs de formulaire dynamiques |
| el-tabs | Element Plus | Navigation par onglets |

### APIs backend disponibles
- `GET/POST/PUT/DELETE /api/v1/organizations` — CRUD organisations (superuser uniquement pour liste globale)
- `GET/POST/PUT/DELETE /api/v1/users` — CRUD utilisateurs (org-scoped)
- `GET/POST/PUT/DELETE /api/v1/targets` — CRUD targets/environnements (org-scoped)
- `GET /api/v1/users/me` — Profil utilisateur courant

### Types TypeScript disponibles (`frontend/src/types/api.ts`)
- `Organization`, `OrganizationCreate`, `OrganizationUpdate`
- `User`, `UserCreate`, `UserUpdate`
- `Target`, `TargetCreate`, `TargetUpdate`

### Services frontend existants (`frontend/src/services/`)
- `organizationsApi` — méthodes CRUD complètes
- `usersApi` — méthodes CRUD complètes
- `targetsApi` — méthodes CRUD complètes

### Store Auth (`frontend/src/stores/auth.ts`)
- Getter `isSuperuser` pour vérifier le rôle admin
- Propriété `user` avec `organization_id`

### Route existante
- `/settings` déjà configurée dans `frontend/src/router/index.ts`
- Entrée sidebar dans `SidebarNav.vue` (section Administration)

## Dépendances
- Aucune story pré-requise (APIs et services déjà existants)
- Store `auth` pour la vérification des droits

## Tâches d'implémentation détaillées

### Phase 1 : Structure de base
1. **Modifier `frontend/src/views/Settings.vue`** — Remplacer le stub par une structure avec `el-tabs`
   - Ajouter 3 onglets : "Organisations", "Environnements", "Utilisateurs"
   - Ajouter un guard de vérification du rôle (`authStore.isSuperuser`)
   - Afficher un message d'erreur si non autorisé
   - Utiliser `el-page-header` pour le titre de la page

### Phase 2 : Onglet Organisations
2. **Créer le composable `frontend/src/composables/useOrganizations.ts`**
   - `organizations` (ref) — liste des organisations
   - `loading` (ref) — état de chargement
   - `fetchOrganizations()` — récupérer la liste
   - `createOrganization(data)` — créer une organisation
   - `updateOrganization(id, data)` — mettre à jour
   - `deleteOrganization(id)` — supprimer

3. **Implémenter l'onglet Organisations dans Settings.vue**
   - Table avec colonnes : nom, description, statut (is_active), actions
   - Dialog création/édition avec formulaire (nom, description)
   - Bouton "Nouvelle organisation"
   - Confirmation `ElMessageBox` avant suppression
   - N/B : Seuls les superusers peuvent voir toutes les organisations

### Phase 3 : Onglet Environnements (Targets)
4. **Créer le composable `frontend/src/composables/useEnvironments.ts`**
   - Réutiliser `targetsApi` existant
   - `environments` (ref) — liste des targets
   - `loading` (ref) — état de chargement
   - `fetchEnvironments()` — récupérer la liste
   - `createEnvironment(data)` — créer un target
   - `updateEnvironment(id, data)` — mettre à jour
   - `deleteEnvironment(id)` — supprimer

5. **Implémenter l'onglet Environnements dans Settings.vue**
   - Table avec colonnes : nom, type, host:port, statut (is_active), actions
   - Dialog création/édition avec formulaire (nom, type, host, port, description)
   - Sélecteur de type : docker, ssh, kubernetes, docker_swarm, nomad
   - Bouton "Nouvel environnement"
   - Confirmation `ElMessageBox` avant suppression

### Phase 4 : Onglet Utilisateurs
6. **Créer le composable `frontend/src/composables/useUsers.ts`**
   - `users` (ref) — liste des utilisateurs
   - `loading` (ref) — état de chargement
   - `fetchUsers()` — récupérer la liste
   - `createUser(data)` — créer un utilisateur
   - `updateUser(id, data)` — mettre à jour
   - `deleteUser(id)` — supprimer

7. **Implémenter l'onglet Utilisateurs dans Settings.vue**
   - Table avec colonnes : username, email, full_name, is_superuser (badge), is_active (badge), updated_at, actions
   - Drawer création/édition avec formulaire complet
   - Champs : username, email, full_name, password (création uniquement), is_active, is_superuser (si superuser)
   - Bouton "Nouvel utilisateur"
   - Confirmation `ElMessageBox` avant suppression
   - Empêcher l'auto-suppression (cacher le bouton delete pour l'utilisateur courant)

### Phase 5 : Guard de rôle et finalisation
8. **Ajouter le guard de rôle dans Settings.vue**
   - Vérifier `authStore.isSuperuser` au montage
   - Si non-superuser : afficher `el-result` avec message "Accès réservé aux administrateurs"
   - Alternative : redirection vers dashboard avec notification

9. **Styling et responsive**
   - Appliquer les variables UnoCSS du thème sombre
   - S'assurer que les dialogs/drawers sont responsive
   - Tester sur mobile (sidebar rétractée)

## Tests à écrire

### Tests unitaires (`frontend/tests/unit/views/Settings.spec.ts`)
- [ ] Render du composant avec utilisateur superuser
- [ ] Render du composant avec utilisateur non-superuser (message d'erreur)
- [ ] Changement d'onglets fonctionne
- [ ] Onglet Organisations : affiche la liste, ouvre dialog création
- [ ] Onglet Environnements : affiche la liste, ouvre dialog création
- [ ] Onglet Utilisateurs : affiche la liste, ouvre drawer édition
- [ ] Confirmation de suppression affichée
- [ ] Appels API mockés correctement

### Tests d'intégration (optionnel)
- [ ] Flux complet création → édition → suppression d'une organisation
- [ ] Flux complet création → édition → suppression d'un utilisateur

## État d'avancement technique
- [x] Création `frontend/src/views/Settings.vue` avec el-tabs
- [x] Onglet Organisations (CRUD)
- [x] Onglet Environnements (CRUD)
- [x] Onglet Utilisateurs (liste + dialog édition)
- [x] Guard de rôle pour vérifier le rôle (isSuperuser)
- [x] Services frontend pour les appels API orgs/users (déjà existants)
- [x] Tests Vitest

## Notes d'implémentation

### Fichiers créés
- `frontend/src/views/Settings.vue` — Page complète avec 3 onglets (Organisations, Environnements, Utilisateurs)
- `frontend/src/composables/useOrganizations.ts` — Composable CRUD pour les organisations
- `frontend/src/composables/useEnvironments.ts` — Composable CRUD pour les environnements (targets)
- `frontend/src/composables/useUsers.ts` — Composable CRUD pour les utilisateurs
- `frontend/tests/unit/views/Settings.spec.ts` — Tests unitaires

### Fichiers modifiés
- `frontend/src/composables/useOrganizations.ts` — Suppression import inutilisé

### Décisions techniques
1. **Dialog vs Drawer** : Utilisation de `el-dialog` pour tous les formulaires (plus simple pour petits formulaires)
2. **Type formulaire User** : Création d'un type local `UserDialogForm` pour gérer `is_active` qui n'est pas dans `UserCreate`
3. **Scan environnement** : Ajout d'un bouton "Scanner" pour les environnements (action `scan`)
4. **Guard de rôle** : Vérification côté template avec `v-if="!authStore.isSuperuser"` pour afficher message d'erreur

### Tests
- Tests unitaires couvrant: montage, contrôle d'accès, fetch données, structure onglets, CRUD dialogs, handlers d'actions
- Build frontend réussi (16.24 kB pour Settings.js)
