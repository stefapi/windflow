# EPIC-008 : Couverture Frontend des APIs Backend

**Statut :** TODO
**Priorité :** Haute

## Vision
Combler le fossé entre les APIs backend disponibles et leur utilisation dans le frontend WindFlow. Actuellement, environ 23 endpoints API backend ne sont pas exploités par l'interface utilisateur, limitant les fonctionnalités accessibles aux utilisateurs.

## Description
Cette epic vise à implémenter progressivement les interfaces frontend pour les APIs backend existantes, en priorisant les fonctionnalités les plus utiles pour les utilisateurs finaux. Les travaux sont classés en 3 vagues de priorité :

### Priorité Haute (Core)
- Gestion des images Docker (liste, pull, suppression)
- Export/Import de stacks (partage et sauvegarde)
- Mise à jour des déploiements existants

### Priorité Moyenne (UX)
- Gestion des volumes Docker
- Gestion des réseaux Docker
- Statistiques détaillées des stacks
- Amélioration du terminal (choix du shell)
- Informations système Docker

### Priorité Basse (Nice-to-have)
- Création manuelle de containers
- Informations de version/ping Docker

## Liste des Stories liées

### 🔴 Priorité Haute
- [ ] STORY-XXX : Gestion des images Docker - Liste et visualisation
- [ ] STORY-XXX : Gestion des images Docker - Pull et suppression
- [ ] STORY-XXX : Export de stacks au format JSON
- [ ] STORY-XXX : Import de stacks depuis fichier JSON
- [ ] STORY-XXX : Mise à jour des déploiements existants

### 🟡 Priorité Moyenne
- [ ] STORY-XXX : Gestion des volumes Docker - Liste et création
- [ ] STORY-XXX : Gestion des volumes Docker - Suppression
- [ ] STORY-XXX : Visualisation des réseaux Docker
- [ ] STORY-XXX : Statistiques détaillées par stack
- [ ] STORY-XXX : Sélection du shell dans le terminal container
- [ ] STORY-XXX : Widget informations système Docker

### 🟢 Priorité Basse
- [ ] STORY-XXX : Création manuelle de containers Docker

## Critères de succès (Definition of Done)
- [ ] Toutes les APIs backend documentées sont accessibles via le frontend
- [ ] Tests E2E couvrant les nouveaux flux utilisateur
- [ ] Documentation utilisateur mise à jour
- [ ] Pas de régression sur les fonctionnalités existantes

## Notes de conception
- Réutiliser les composants existants (tables, formulaires, dialogues Element Plus)
- Suivre les patterns établis dans `frontend/src/services/api.ts`
- Utiliser les WebSockets pour les données temps réel quand disponible
- Respecter le design system défini dans `doc/DESIGN-SYSTEM.md`

## Risques et dépendances
- **Risque** : Volume de travail important - découper en stories fines
- **Dépendance** : EPIC-002 (VM Management) pour les fonctionnalités futures
- **Attention** : Ne pas dupliquer les fonctionnalités déjà couvertes par WebSocket
