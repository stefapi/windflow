# STORY-422 : Typographie (Inter + JetBrains Mono)

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux une typographie technique et lisible afin d'avoir une interface d'outil professionnel — sobre et sans fantaisie.

## Critères d'acceptation (AC)
- [x] AC 1 : La police UI principale est **Inter** (ou IBM Plex Sans en fallback)
- [x] AC 2 : La police monospace (code, logs, terminal) est **JetBrains Mono** (ou Fira Code en fallback)
- [x] AC 3 : Les polices sont chargées localement (self-hosted, pas de CDN externe) pour respecter le self-hosting
- [x] AC 4 : Les tailles de texte sont tokenisées (headings, body, caption, code) dans le design system
- [x] AC 5 : La hiérarchie typographique est cohérente sur toutes les pages (h1 > h2 > body > caption)
- [x] AC 6 : Le composant de logs (`DeploymentLogs.vue`) et le terminal (`ContainerTerminal.vue`) utilisent JetBrains Mono

## État d'avancement technique
- [x] Installation des polices Inter et JetBrains Mono (fichiers woff2)
- [x] Déclaration `@font-face` dans les styles globaux
- [x] Tokens typographiques dans `theme.css`
- [x] Migration des composants existants vers les tokens typo
- [x] Vérification sur les vues existantes (Dashboard, Stacks, Terminal, Logs)

## Notes d'implémentation

### Fichiers modifiés/créés
- `frontend/src/assets/fonts/inter/Inter-Regular.woff2` (créé)
- `frontend/src/assets/fonts/inter/Inter-Medium.woff2` (créé)
- `frontend/src/assets/fonts/inter/Inter-SemiBold.woff2` (créé)
- `frontend/src/assets/fonts/jetbrains-mono/JetBrainsMono-Regular.woff2` (créé)
- `frontend/src/assets/fonts/jetbrains-mono/JetBrainsMono-Medium.woff2` (créé)
- `frontend/src/styles/theme.css` (modifié - ajout @font-face, tokens typo, font-family sur body)
- `frontend/src/components/ContainerTerminal.vue` (modifié - utilise var(--font-mono))
- `frontend/src/components/DeploymentLogs.vue` (modifié - utilise var(--font-mono))
- `frontend/src/views/Stacks.vue` (modifié - utilise var(--font-mono))
- `frontend/src/composables/useSidebar.ts` (correction erreur TypeScript)

### Décisions techniques
1. **Self-hosting des polices** : Les polices sont hébergées localement en format woff2 pour des performances optimales et l'indépendance vis-à-vis des CDN externes.
2. **Tokens typographiques CSS** : Utilisation de variables CSS natives (`--font-sans`, `--font-mono`, `--text-*`, `--leading-*`, `--font-*`) pour une cohérence globale.
3. **Fallback chain** : Inter avec fallback vers IBM Plex Sans et system-ui; JetBrains Mono avec fallback vers Fira Code, Cascadia Code, Consolas.
4. **font-display: swap** : Permet un affichage rapide du texte avec la police système avant chargement des polices personnalisées.

### Tests
- Build frontend réussi (`pnpm build`)
