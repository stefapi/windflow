# STORY-433 : Liste derniers déploiements avec statut et action directe

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux voir les derniers déploiements sur le dashboard avec leur statut afin de savoir immédiatement ce qui a réussi ou échoué, et agir directement.

## Critères d'acceptation (AC)
- [ ] AC 1 : Section « Derniers Déploiements » affichée sur le dashboard sous les tuiles compteurs
- [ ] AC 2 : Affiche les 10 derniers déploiements avec : nom, statut (✅/❌), date relative (« il y a 2h »), utilisateur
- [ ] AC 3 : Chaque ligne est cliquable et mène au détail du déploiement/container
- [ ] AC 4 : Un déploiement en échec affiche un bouton « Redéployer » directement sur la ligne
- [ ] AC 5 : Les données proviennent de l'API existante `/api/v1/deployments` (avec tri par date desc, limit 10)
- [ ] AC 6 : Rafraîchissement automatique (polling 30s, cohérent avec les tuiles)

## État d'avancement technique
- [ ] Composant `RecentDeployments.vue`
- [ ] Appel API déploiements récents (service frontend)
- [ ] Formatage dates relatives (composable `useRelativeTime` ou librairie)
- [ ] Bouton redéploiement inline
- [ ] Intégration dans le Dashboard
- [ ] Tests Vitest
