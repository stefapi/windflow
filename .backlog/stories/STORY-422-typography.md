# STORY-422 : Typographie (Inter + JetBrains Mono)

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux une typographie technique et lisible afin d'avoir une interface d'outil professionnel — sobre et sans fantaisie.

## Critères d'acceptation (AC)
- [ ] AC 1 : La police UI principale est **Inter** (ou IBM Plex Sans en fallback)
- [ ] AC 2 : La police monospace (code, logs, terminal) est **JetBrains Mono** (ou Fira Code en fallback)
- [ ] AC 3 : Les polices sont chargées localement (self-hosted, pas de CDN externe) pour respecter le self-hosting
- [ ] AC 4 : Les tailles de texte sont tokenisées (headings, body, caption, code) dans le design system
- [ ] AC 5 : La hiérarchie typographique est cohérente sur toutes les pages (h1 > h2 > body > caption)
- [ ] AC 6 : Le composant de logs (`DeploymentLogs.vue`) et le terminal (`ContainerTerminal.vue`) utilisent JetBrains Mono

## État d'avancement technique
- [ ] Installation des polices Inter et JetBrains Mono (fichiers woff2)
- [ ] Déclaration `@font-face` dans les styles globaux
- [ ] Tokens typographiques dans `uno.config.ts`
- [ ] Migration des composants existants vers les tokens typo
- [ ] Vérification sur les vues existantes (Dashboard, Stacks, Terminal, Logs)
