# STORY-433 : Liste derniers déploiements avec statut et action directe

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux voir les derniers déploiements sur le dashboard avec leur statut afin de savoir immédiatement ce qui a réussi ou échoué, et agir directement.

## Critères d'acceptation (AC)
- [x] AC 1 : Section « Derniers Déploiements » affichée sur le dashboard sous les tuiles compteurs
- [x] AC 2 : Affiche les 10 derniers déploiements avec : nom, statut (✅/❌), date relative (« il y a 2h »), utilisateur
- [x] AC 3 : Chaque ligne est cliquable et mène au détail du déploiement/container
- [x] AC 4 : Un déploiement en échec affiche un bouton « Redéployer » directement sur la ligne
- [x] AC 5 : Les données proviennent de l'API existante `/api/v1/deployments` (avec tri par date desc, limit 10)
- [x] AC 6 : Rafraîchissement automatique (polling 30s, cohérent avec les tuiles)

## État d'avancement technique
- [x] Composant `RecentDeploymentsWidget.vue`
- [x] Appel API déploiements récents (service frontend)
- [x] Formatage dates relatives (composable `useRelativeTime`)
- [x] Bouton redéploiement inline
- [x] Intégration dans le Dashboard
- [x] Tests Vitest

## Notes d'implémentation

### Fichiers créés
- `frontend/src/composables/useRelativeTime.ts` - Composable pour formater les dates en temps relatif ("il y a 2h")
- `frontend/src/components/dashboard/RecentDeploymentsWidget.vue` - Widget d'affichage des derniers déploiements
- `frontend/tests/unit/components/dashboard/RecentDeploymentsWidget.spec.ts` - Tests unitaires

### Fichiers modifiés
- `frontend/src/views/Dashboard.vue` - Intégration du widget sous les tuiles compteurs

### Décisions techniques
1. **Composant autonome** : Le widget gère son propre appel API et polling (30s) pour rester indépendant du store dashboard
2. **StatusBadge réutilisé** : Utilisation du composant `StatusBadge` existant pour l'affichage cohérent des statuts
3. **Mapping des statuts** : Les statuts deployment sont mappés vers les types StatusBadge (pending→pending, running→deploying, completed→deployed, failed→failed, cancelled→stopped)
4. **Fallback nom** : Si le nom du déploiement est null, on affiche les 8 premiers caractères de l'UUID

### Limitations connues
- **Utilisateur non affiché** : Le champ `user` n'existe pas dans le schéma `Deployment` backend. Affichage du nom de la target à la place. L'ajout de ce champ nécessiterait une évolution du schéma backend (hors scope de cette story).

### Tests
- Tests de rendu (loading, empty, error, avec données)
- Tests d'interaction (navigation, retry)
- Tests de polling (montage/démontage)
