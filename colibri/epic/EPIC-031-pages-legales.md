# EPIC-031 : Pages Légales

**Statut :** TODO
**Priorité :** Basse

## Vision
Pages légales générées automatiquement incluant la politique de confidentialité, les conditions d'utilisation et les informations de licence. Les pages sont accessibles depuis l'interface et peuvent être personnalisées.

## Liste des Stories liées
- [ ] STORY-001 : Voir la politique de confidentialité
- [ ] STORY-002 : Voir les conditions d'utilisation
- [ ] STORY-003 : Voir les informations de licence
- [ ] STORY-004 : Les pages sont générées automatiquement depuis les templates

## Notes de conception
- Pages dans src/routes/legal/privacy/ et src/routes/legal/license/
- Génération automatique via scripts/generate-legal-pages.ts
- Templates dans src/lib/data/
- Support du format Markdown pour le contenu
- Liens dans le footer de l'application
- Accessible sans authentification
- Mise à jour automatique lors des nouvelles versions
