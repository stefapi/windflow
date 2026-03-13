# STORY-421 : Palette de couleurs thème sombre (tokens UnoCSS)

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux un thème sombre par défaut avec des couleurs cohérentes et fonctionnelles afin d'avoir une interface agréable pour le self-hosting (souvent utilisée le soir).

## Critères d'acceptation (AC)
- [ ] AC 1 : Les tokens de couleur sont définis dans `frontend/uno.config.ts` (pas de couleurs en dur dans les composants)
- [ ] AC 2 : Fond principal : `#0f1117`, fond cartes : `#1a1d27`, bordures : `#2a2d37`
- [ ] AC 3 : Texte principal : `#e1e4eb`, texte secondaire : `#8b8fa3`
- [ ] AC 4 : Accent principal (actions/liens) : `#3b82f6` (bleu)
- [ ] AC 5 : Statuts : succès `#22c55e` (vert), erreur `#ef4444` (rouge), warning `#f59e0b` (orange)
- [ ] AC 6 : Un thème clair est disponible via toggle (préférence persistée en localStorage) — peut être un stub minimal
- [ ] AC 7 : Les composants Element Plus utilisent les tokens de couleur (override du thème EP via CSS variables)
- [ ] AC 8 : Le contraste WCAG AA est respecté pour tout texte sur fond (ratio ≥ 4.5:1)

## État d'avancement technique
- [ ] Définition des tokens dans `uno.config.ts` (shortcuts + theme extend)
- [ ] Override du thème Element Plus via CSS custom properties
- [ ] Création d'un fichier `frontend/src/styles/theme.css` (variables CSS globales)
- [ ] Migration des couleurs en dur existantes vers les tokens
- [ ] Toggle thème clair/sombre (composant + localStorage)
- [ ] Vérification contraste WCAG AA (outil axe ou Lighthouse)
