---
name: create-boilerplate
description: Génère un boilerplate complet à partir d'une description libre, demande des précisions si nécessaire, et met à jour les règles du projet via update-rules.
---

# create-boilerplate

Cette skill génère un **squelette de composant prêt à être développé** à partir d'une description libre fournie par l'utilisateur. Elle conduit un **interview structuré** pour cerner précisément le besoin, génère la **structure, la configuration et l'outillage** appropriés en respectant les conventions du projet, puis synchronise les règles du projet via `update-rules`.

> ⚠️ **Règle fondamentale — Boilerplate ≠ Fonctionnel**
>
> Cette skill génère **uniquement** :
> - Fichiers de configuration (manifestes de dépendances, configuration de build, de lint, de types…)
> - Structure de répertoires et stubs de code vides
> - Outillage (CI, conteneurs, Makefile, linting, testing, observabilité)
> - Fichiers d'infrastructure (orchestration de conteneurs, proxy, variables d'environnement…)
>
> Elle ne génère **jamais** :
> - Logique métier
> - Points d'entrée implémentés (uniquement leur déclaration vide)
> - Services fonctionnels
> - Tout code qui appartient aux stories du backlog
>
> L'implémentation fonctionnelle est du ressort des skills `analyse-story` et `treat-story`.
>
> ⚠️ **Adaptation au projet hôte** : les conventions de WindFlow (uv, pnpm, Makefile, `.roo/rules/`, emplacements `55-project-structure.md`) font autorité. Ne jamais introduire un outil ou un gestionnaire concurrent de ceux déjà arbitrés par les règles du projet.

## Usage

Utilise cette skill quand :
- L'utilisateur demande de créer un boilerplate / squelette / setup pour un composant technique
- L'utilisateur décrit un type de composant à générer (module backend, extension frontend, docker, CI/CD, etc.)
- L'utilisateur veut initialiser une nouvelle partie du projet

**Exemples de déclenchements :** `create-boilerplate module backend notifications`, `create-boilerplate docker test`, `create-boilerplate CI/CD`, `create-boilerplate un truc pour monitorer l'appli`.

## Principes directeurs

1. **Interview avant de coder** : conduire une analyse structurée avant toute génération
2. **Pas de liste prédéfinie** : l'IA interprète la demande à partir du texte libre
3. **Questions ciblées et groupées** : poser toutes les questions pertinentes en une seule fois, par thème
4. **Référence aux règles du projet** : toujours lire et respecter `.roo/rules/`
5. **Structure uniquement** : les fichiers de code source sont des stubs vides ou minimaux — pas d'implémentation fonctionnelle
6. **Synchronisation finale** : appeler `update-rules` en fin de génération pour garantir la cohérence des règles
7. **Standards du marché** : meilleures pratiques reconnues pour chaque technologie

## Phase 0 : Analyse approfondie du besoin

### 0.1 Déconstruction de la demande

| Dimension | Questions à se poser |
| --- | --- |
| **Type de composant** | Backend, frontend, CLI, infra, CI/CD, monitoring ? |
| **Domaine fonctionnel** | Module API, worker, pipeline ? |
| **Contraintes implicites** | Perf, sécurité, scale mentionnées ? |
| **Intégrations** | Composants existants (backend, frontend, bus, WebSocket) ? |
| **Environnements** | Dev uniquement, ou dev + prod ? |
| **Maturité** | Prototype ou production-ready ? |

### 0.2 Consultation des règles existantes du projet

Lire `.roo/rules/` pour identifier : la stack en place (éviter les doublus), les outils déjà décidés (ne pas redemander ce qui est arbitré), les contraintes non négociables (sécurité `40`, observabilité `45`, structure `55`).

### 0.3 Exploration de l'état actuel du projet

Vérifier les fichiers existants pour éviter les conflits : répertoires déjà présents, manifestes existants (ne pas écraser, merger), `env.example` (compléter), `Makefile` (ajouter des cibles, ne pas écraser).

## Phase 1 : Interview structuré

Sur la base de l'analyse, formuler **toutes les questions pertinentes en une seule fois**, groupées par thème (Stack & Technologie, Persistance & Données, Authentification & Sécurité, Intégrations, Tests & Qualité, Environnements & Déploiement, Observabilité, CI/CD).

**Règles de l'interview :** ne pas demander ce qui est déjà dans les règles du projet ; ne pas demander par politesse — n'inclure que les questions dont la réponse change concrètement la génération ; proposer des options concrètes avec valeurs par défaut ; un seul round de questions.

## Phase 2 : Synthèse des décisions

Après réception des réponses, formuler une **synthèse des décisions** (tableau dimension → décision) et faire confirmer.

## Phase 3 : Lecture du contexte projet (complémentaire)

Vérifier l'état actuel : fichiers existants à la racine et dans les répertoires concernés, manifestes de dépendances (merger), `env.example` (compléter), `Makefile` (ajouter les cibles), pipeline CI (ajouter les jobs).

## Phase 4 : Planification des fichiers

Lister chaque fichier à créer avec son chemin complet et son contenu principal ; les fichiers existants à compléter avec leurs ajouts.

## Phase 5 : Confirmation

Présenter un résumé complet avant génération (type, stack, fichiers à créer, fichiers à compléter) et faire confirmer.

## Phase 6 : Génération des fichiers

Créer chaque fichier en respectant strictement la frontière **boilerplate / implémentation** :

- **Fichiers de configuration & outillage (complets)** : manifestes, build, types, lint, Docker, CI, `env.example`, Makefile — prêts à l'emploi.
- **Fichiers de code source (stubs uniquement)** : point d'entrée initialisé sans logique métier, routeurs/composants avec stubs marqués `# TODO(STORY-XXX): <ce que la story doit livrer>` (`30` §6), modèles = structure de classes uniquement, services = classes vides avec signatures commentées.
- **Fichiers de test (structure minimale)** : un smoke test par composant, pas de tests fonctionnels complets.

**Ordre de création recommandé :** configuration racine → build/outils → structure + stubs → smoke tests → documentation → complétion des fichiers existants (`Makefile`, `env.example`, `.gitignore`, CI).

## Phase 7 : Synchronisation des règles via `update-rules`

Après la génération, déclencher la skill **[`update-rules`](../update-rules/SKILL.md)** sur les composants concernés : elle compare les règles au code réellement créé et prépare les mises à jour.

> **Attention** : les règles du projet ne sont fusionnées que par leur propriétaire (`02` §5). Se limiter à présenter les divergences et propositions de mise à jour si la validation n'est pas acquise.

## Phase 8 : Vérification post-génération

- [ ] Tous les fichiers déclarés ont été créés
- [ ] `env.example` contient toutes les nouvelles variables (`50` §6)
- [ ] Le `Makefile` contient les nouvelles cibles
- [ ] Pas de conflit avec les fichiers existants
- [ ] Si possible, lancer le lint pour valider
- [ ] `update-rules` a été exécuté (ou les divergences présentées)

## Gestion des erreurs

| Situation | Action |
| --- | --- |
| Demande trop floue | Conduire l'interview structuré (Phase 1) |
| Technologie non reconnue | Demander des précisions, proposer des alternatives |
| Fichier existant risque d'être écrasé | Avertir, proposer un merge plutôt qu'un overwrite |
| Dépendance en conflit avec les règles | Avertir et demander confirmation avant de diverger |
| Erreur pendant la génération | Annuler les modifications partielles, informer |

## Fichiers concernés

| Fichier | Action |
| --- | --- |
| `.agents/skills/create-boilerplate/SKILL.md` | Référence (ce fichier) |
| `.roo/rules/` | Lecture contextuelle (Phase 0) |
| `.agents/skills/update-rules/SKILL.md` | Invoquée (Phase 7) |
| Fichiers boilerplate | Création (Phase 6) |
| `Makefile`, `env.example`, `.gitignore`, CI | Complétion |
