# STORY-432 : Tuiles compteurs Containers / VMs / Stacks

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux voir des tuiles synthétiques sur le dashboard (Containers, VMs, Stacks) avec le nombre de ressources par statut afin de connaître l'état global de mon infrastructure.

## Critères d'acceptation (AC)
- [ ] AC 1 : 3 tuiles compteurs affichées : Containers, VMs, Stacks
- [ ] AC 2 : Chaque tuile montre : nombre running (🟢), nombre stopped (🔴), total
- [ ] AC 3 : Chaque tuile est cliquable et redirige vers la liste correspondante
- [ ] AC 4 : Les tuiles utilisent le composant `CounterCard.vue` (STORY-423)
- [ ] AC 5 : La tuile VMs affiche « 0 VMs — Bientôt disponible » tant qu'EPIC-002 n'est pas livrée
- [ ] AC 6 : Les données proviennent de l'API (endpoint stats existant ou nouveau `/api/v1/stats/summary`)
- [ ] AC 7 : Les compteurs se mettent à jour automatiquement (polling 30s)

## État d'avancement technique
- [ ] Vérification/création endpoint API stats summary
- [ ] Intégration des 3 `CounterCard.vue` dans le Dashboard
- [ ] Liaison clics → routes /containers, /vms, /stacks
- [ ] Gestion du cas VMs non disponibles (stub gracieux)
- [ ] Polling automatique
- [ ] Tests Vitest
