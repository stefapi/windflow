# EPIC-026 : Préférences Utilisateur

**Statut :** TODO
**Priorité :** Moyenne

## Vision
Système de préférences utilisateur permettant de personnaliser l'expérience : colonnes visibles dans les grilles, groupes de favoris, disposition du dashboard, thème et autres paramètres d'affichage.

## Liste des Stories liées
- [ ] STORY-001 : Configurer les colonnes visibles dans les grilles de données
- [ ] STORY-002 : Créer et gérer des groupes de favoris
- [ ] STORY-003 : Personnaliser la disposition du dashboard
- [ ] STORY-004 : Sauvegarder les préférences de tri et filtrage
- [ ] STORY-005 : Les préférences sont persistées par utilisateur et par environnement

## Notes de conception
- Table user_preferences avec clé composite (user_id, environment_id, key)
- Stockage JSON pour les préférences complexes (colonnes, grille)
- Préférences par environnement pour les grilles
- Préférences globales pour le thème et le dashboard
- Synchronisation en temps réel via stores Svelte
- Support des préférences par défaut
- Import/export des préférences
